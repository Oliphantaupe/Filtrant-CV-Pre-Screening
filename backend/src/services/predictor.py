"""
Loads the trained ML model and produces Invite/Reject predictions.
Returns "pending" if no model file is found yet.

v2: Supports the new model artifact format (dict with pipeline + metadata)
    as well as the legacy format (bare pipeline) for backward compatibility.
"""
import os
import logging
import numpy as np
from src.config import settings
from src.services.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_model = None
_effective_features = None  # features actually used by the model (may exclude constants)


def _load_model():
    global _model, _effective_features
    if not os.path.exists(settings.ml_model_path):
        return

    import joblib
    artifact = joblib.load(settings.ml_model_path)

    # v2 format: dict with pipeline + metadata
    if isinstance(artifact, dict) and "pipeline" in artifact:
        _model = artifact["pipeline"]
        _effective_features = artifact.get("effective_features", FEATURE_COLUMNS)
        model_name = artifact.get("model_name", "unknown")
        logger.info(
            "Loaded ML model (v2): %s — %d features, AUC=%.3f, F1_cv=%.3f, SMOTE=%s",
            model_name,
            len(_effective_features),
            artifact.get("best_auc", 0),
            artifact.get("best_f1_cv", 0),
            artifact.get("smote_used", False),
        )
    else:
        # Legacy format: bare pipeline
        _model = artifact
        _effective_features = FEATURE_COLUMNS
        logger.info("Loaded ML model (legacy format) — %d features", len(_effective_features))

    # Verify class ordering: pipeline exposes classes_ via the final step
    clf = _model.named_steps.get("clf") or _model
    classes = list(getattr(clf, "classes_", [0, 1]))
    if classes != [0, 1]:
        logger.warning(
            "Unexpected model class ordering %s — predictions may be inverted. "
            "Retrain with 0=Reject / 1=Invite.", classes
        )


def _compute_derived_features(features: dict) -> dict:
    """Compute derived features from the base features (matching train.py logic)."""
    total_years = features.get("total_years_experience", 0)
    education_score = features.get("education_level_score", 1)
    num_certs = features.get("num_certifications", 0)
    has_senior = features.get("has_senior_title", 0)

    features["experience_education_ratio"] = round(total_years / max(education_score, 1), 2)
    features["certs_per_year"] = round(num_certs / max(total_years, 0.5), 2)
    features["experience_x_seniority"] = round(total_years * has_senior, 2)
    features["experience_x_education"] = round(total_years * education_score, 2)

    return features


def predict(features: dict) -> tuple[str, float | None]:
    """
    Returns (recommendation, confidence).
    recommendation: "Invite" | "Reject" | "pending"
    confidence: 0.0–1.0 or None
    """
    if _model is None:
        _load_model()

    if _model is None:
        return "pending", None

    # Ensure derived features are computed
    features = _compute_derived_features(features)

    X = np.array([[features.get(col, 0) for col in _effective_features]])
    proba = _model.predict_proba(X)[0]
    label_idx = int(np.argmax(proba))

    confidence = round(float(proba[label_idx]), 3)

    # Model classes: 0 = Reject, 1 = Invite
    recommendation = "Invite" if label_idx == 1 else "Reject"
    return recommendation, confidence
