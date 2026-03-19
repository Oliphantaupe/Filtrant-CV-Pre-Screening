"""
Loads the trained ML model and produces Invite/Reject predictions.
Returns "pending" if no model file is found yet.
"""
import os
import numpy as np
from src.config import settings
from src.services.features import FEATURE_COLUMNS

_model = None


def _load_model():
    global _model
    if os.path.exists(settings.ml_model_path):
        import joblib
        _model = joblib.load(settings.ml_model_path)


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

    X = np.array([[features[col] for col in FEATURE_COLUMNS]])
    proba = _model.predict_proba(X)[0]
    label_idx = int(np.argmax(proba))
    confidence = round(float(proba[label_idx]), 3)

    # Model classes: 0 = Reject, 1 = Invite
    recommendation = "Invite" if label_idx == 1 else "Reject"
    return recommendation, confidence
