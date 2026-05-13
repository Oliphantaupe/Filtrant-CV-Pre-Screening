"""
predictor.py — ML inference + SHAP explanations (WP2)
======================================================
Loads model_fair.joblib (fair model) with fallback to model.joblib (baseline).
Returns prediction + top contributing features via SHAP.
"""
import logging
import os
import numpy as np
from src.config import settings
from src.services.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_model      = None
_explainer  = None
_feat_cols  = None

FAIR_MODEL_PATH = os.path.join(os.path.dirname(settings.ml_model_path), "model_fair.joblib")

FEATURE_LABELS = {
    "total_years_experience":     "Years of experience",
    "num_positions":              "Number of positions held",
    "avg_tenure_months":          "Average tenure per role",
    "education_level_score":      "Education level",
    "total_skills_count":         "Total skills listed",
    "has_certifications":         "Has certifications",
    "language_count":             "Number of languages",
    "section_completeness_score": "CV completeness",
    "max_language_score":         "Best language level",
    "has_senior_title":           "Senior/Lead title",
    "career_gap_months":          "Career gap duration",
    "latest_job_duration":        "Duration of latest role",
    "has_summary":                "Has professional summary",
    "num_certifications":         "Number of certifications",
    "parse_quality_score":        "CV parse quality",
    "experience_education_ratio": "Experience / education ratio",
    "certs_per_year":             "Certifications per year",
    "experience_x_seniority":     "Experience × seniority",
    "experience_x_education":     "Experience × education",
    "career_trajectory_score":    "Career progression",
    "latest_title_seniority":     "Current role seniority",
}


def _load_model():
    global _model, _explainer, _feat_cols
    import joblib

    # Prefer fair model, fall back to baseline
    path = FAIR_MODEL_PATH if os.path.exists(FAIR_MODEL_PATH) else settings.ml_model_path
    if not os.path.exists(path):
        return

    artifact = joblib.load(path)
    if isinstance(artifact, dict) and "pipeline" in artifact:
        _model     = artifact["pipeline"]
        _feat_cols = artifact.get("feature_columns", artifact.get("effective_features", FEATURE_COLUMNS))
        is_fair    = artifact.get("fairness_mitigated", False)
        logger.info("Loaded model: %s (fair=%s) — %d features", artifact.get("model_name"), is_fair, len(_feat_cols))
    else:
        _model     = artifact
        _feat_cols = FEATURE_COLUMNS
        logger.info("Loaded model (legacy) — %d features", len(_feat_cols))

    _build_explainer()


def _build_explainer():
    global _explainer
    try:
        import shap
        clf = getattr(_model, "named_steps", {}).get("clf") or _model
        if hasattr(clf, "feature_importances_"):
            _explainer = shap.TreeExplainer(clf)
        elif hasattr(clf, "coef_"):
            _explainer = shap.LinearExplainer(clf, masker=shap.maskers.Independent(np.zeros((1, len(_feat_cols)))))
        else:
            _explainer = None
            logger.info("SHAP: no compatible explainer for this model type")
    except Exception as e:
        _explainer = None
        logger.warning("SHAP explainer could not be built: %s", e)


def _compute_shap(X_scaled: np.ndarray) -> list[dict] | None:
    if _explainer is None:
        return None
    try:
        import shap
        shap_values = _explainer.shap_values(X_scaled)
        # For binary classifiers TreeExplainer returns list [class0, class1]
        if isinstance(shap_values, list):
            sv = shap_values[1][0]
        else:
            sv = shap_values[0]

        contributions = [
            {"feature": f, "label": FEATURE_LABELS.get(f, f), "contribution": round(float(v), 4)}
            for f, v in zip(_feat_cols, sv)
        ]
        contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        positive = [c for c in contributions if c["contribution"] > 0][:3]
        negative = [c for c in contributions if c["contribution"] < 0][:3]
        return {"positive": positive, "negative": negative}
    except Exception as e:
        logger.warning("SHAP computation failed: %s", e)
        return None


def _get_scaled_input(features: dict) -> np.ndarray:
    """Run only the scaler step on raw features, return scaled array."""
    X_raw = np.array([[features.get(col, 0) for col in _feat_cols]])
    scaler = getattr(_model, "named_steps", {}).get("scaler")
    if scaler is not None:
        return scaler.transform(X_raw)
    return X_raw


def predict(features: dict) -> tuple[str, float | None, dict | None]:
    """
    Returns (recommendation, confidence, explanation).
    recommendation : 'Invite' | 'Reject' | 'pending'
    confidence     : 0.0–1.0 or None
    explanation    : {'positive': [...], 'negative': [...]} or None
    """
    if _model is None:
        _load_model()
    if _model is None:
        return "pending", None, None

    X_raw = np.array([[features.get(col, 0) for col in _feat_cols]])
    proba = _model.predict_proba(X_raw)[0]
    label_idx      = int(np.argmax(proba))
    confidence     = round(float(proba[label_idx]), 3)
    recommendation = "Invite" if label_idx == 1 else "Reject"

    # SHAP on the scaled representation
    X_scaled  = _get_scaled_input(features)
    explanation = _compute_shap(X_scaled)

    return recommendation, confidence, explanation
