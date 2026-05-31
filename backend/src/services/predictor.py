"""
predictor.py — ML inference + SHAP explanations (WP2)
======================================================
Loads both model_fair.joblib and model.joblib at startup.
Exposes predict(features, model='fair'|'base') for dual-model support.
"""
import logging
import os
import numpy as np
from src.config import settings
from src.services.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

FAIR_MODEL_PATH = os.path.join(os.path.dirname(settings.ml_model_path), "model_fair.joblib")
BASE_MODEL_PATH = settings.ml_model_path

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

# Per-model state keyed by 'fair' | 'base'
_state: dict[str, dict] = {
    "fair": {"model": None, "explainer": None, "feat_cols": None,
             "calibrator": None, "calibrator_logit": False, "threshold": 0.5},
    "base": {"model": None, "explainer": None, "feat_cols": None,
             "calibrator": None, "calibrator_logit": False, "threshold": 0.5},
}
_initialized = False


def _load_artifact(path: str, key: str) -> None:
    if not os.path.exists(path):
        logger.warning("Model not found at %s — %s predictions will return 'pending'", path, key)
        return
    import joblib
    artifact = joblib.load(path)
    s = _state[key]
    if isinstance(artifact, dict) and "pipeline" in artifact:
        s["model"]            = artifact["pipeline"]
        s["feat_cols"]        = artifact.get("feature_columns", artifact.get("effective_features", FEATURE_COLUMNS))
        s["calibrator"]       = artifact.get("calibrator")
        s["calibrator_logit"] = artifact.get("calibrator_logit_transform", False)
        s["threshold"]        = float(artifact.get("decision_threshold", 0.5))
        logger.info("Loaded %s model: %s (fair=%s, T=%s) — %d features",
                    key, artifact.get("model_name"),
                    artifact.get("fairness_mitigated"),
                    f"{artifact['temperature']:.2f}" if artifact.get("temperature") else "none",
                    len(s["feat_cols"]))
    else:
        s["model"]     = artifact
        s["feat_cols"] = FEATURE_COLUMNS
        logger.info("Loaded %s model (legacy) — %d features", key, len(s["feat_cols"]))

    _build_explainer(key)


def _build_explainer(key: str) -> None:
    s = _state[key]
    model, feat_cols = s["model"], s["feat_cols"]
    try:
        import shap
        clf = getattr(model, "named_steps", {}).get("clf") or model
        if hasattr(clf, "feature_importances_"):
            s["explainer"] = shap.TreeExplainer(clf)
        elif hasattr(clf, "coef_"):
            s["explainer"] = shap.LinearExplainer(
                clf, masker=shap.maskers.Independent(np.zeros((1, len(feat_cols))))
            )
        else:
            s["explainer"] = None
            logger.info("SHAP (%s): no compatible explainer", key)
    except Exception as e:
        s["explainer"] = None
        logger.warning("SHAP explainer (%s) could not be built: %s", key, e)


def _load_models() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True
    _load_artifact(FAIR_MODEL_PATH, "fair")
    _load_artifact(BASE_MODEL_PATH, "base")


def _compute_shap(key: str, X_scaled: np.ndarray) -> dict | None:
    s = _state[key]
    if s["explainer"] is None:
        return None
    try:
        import shap
        shap_values = s["explainer"].shap_values(X_scaled)
        sv = shap_values[1][0] if isinstance(shap_values, list) else shap_values[0]
        contributions = [
            {"feature": f, "label": FEATURE_LABELS.get(f, f), "contribution": round(float(v), 4)}
            for f, v in zip(s["feat_cols"], sv)
        ]
        contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        return {
            "positive": [c for c in contributions if c["contribution"] > 0][:3],
            "negative": [c for c in contributions if c["contribution"] < 0][:3],
        }
    except Exception as e:
        logger.warning("SHAP computation (%s) failed: %s", key, e)
        return None


def predict(features: dict, model: str = "fair") -> tuple[str, float | None, dict | None]:
    """
    Returns (recommendation, confidence, explanation) for the given model key.
    model: 'fair' (default, production model) | 'base' (baseline for comparison)
    """
    _load_models()
    s = _state.get(model, _state["fair"])
    if s["model"] is None:
        return "pending", None, None

    feat_cols = s["feat_cols"]
    X_raw = np.array([[features.get(col, 0) for col in feat_cols]])
    proba = s["model"].predict_proba(X_raw)[0]

    if s["calibrator"] is not None:
        raw_p = float(np.clip(proba[1], 1e-7, 1 - 1e-7))
        if s["calibrator_logit"]:
            import math
            logit_p = math.log(raw_p / (1 - raw_p))
            p_cal = float(s["calibrator"].predict_proba([[logit_p]])[0, 1])
        else:
            p_cal = float(s["calibrator"].predict_proba([[raw_p]])[0, 1])
        proba = np.array([1 - p_cal, p_cal])

    is_invite      = bool(proba[1] >= s["threshold"])
    label_idx      = 1 if is_invite else 0
    confidence     = round(float(proba[label_idx]), 3)
    recommendation = "Invite" if is_invite else "Reject"

    # SHAP — scale through the pipeline's scaler step if present
    scaler = getattr(s["model"], "named_steps", {}).get("scaler")
    X_scaled = scaler.transform(X_raw) if scaler is not None else X_raw
    explanation = _compute_shap(model, X_scaled)

    return recommendation, confidence, explanation


# Kept for backward compat with any code that still imports these directly
def _load_model():
    _load_models()

_model              = property(lambda self: _state["fair"]["model"])
_decision_threshold = property(lambda self: _state["fair"]["threshold"])
