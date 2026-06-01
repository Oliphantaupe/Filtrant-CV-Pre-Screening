"""
Unit tests for src.services.predictor.predict().
Models are mocked — no real joblib artifacts needed.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, patch as mock_patch


def _make_mock_pipeline(proba: float = 0.8):
    """Return a mock sklearn Pipeline that predicts a fixed probability."""
    pipe = MagicMock()
    pipe.predict_proba.return_value = np.array([[1 - proba, proba]])
    pipe.named_steps = {}
    return pipe


def _make_artifact(model_key: str = "fair", proba: float = 0.8):
    return {
        "pipeline": _make_mock_pipeline(proba),
        "feature_columns": [f"f{i}" for i in range(22)],
        "model_name": "MockModel",
        "fairness_mitigated": model_key == "fair",
        "decision_threshold": 0.5,
        "calibrator": None,
        "calibrator_logit_transform": False,
        "temperature": None,
    }


@pytest.fixture(autouse=True)
def reset_predictor():
    """Reset global predictor state between tests."""
    import src.services.predictor as pred
    pred._initialized = False
    pred._state = {
        "fair": {"model": None, "explainer": None, "feat_cols": None,
                 "calibrator": None, "calibrator_logit": False, "threshold": 0.5},
        "base": {"model": None, "explainer": None, "feat_cols": None,
                 "calibrator": None, "calibrator_logit": False, "threshold": 0.5},
    }
    yield
    # Reset again after test
    pred._initialized = False
    pred._state = {
        "fair": {"model": None, "explainer": None, "feat_cols": None,
                 "calibrator": None, "calibrator_logit": False, "threshold": 0.5},
        "base": {"model": None, "explainer": None, "feat_cols": None,
                 "calibrator": None, "calibrator_logit": False, "threshold": 0.5},
    }


def test_predict_returns_pending_when_no_model():
    """With no model loaded (_initialized=True but model=None), returns pending."""
    import src.services.predictor as pred
    from src.services.predictor import predict

    pred._initialized = True  # skip _load_models, models stay None
    rec, conf, expl = predict({"f0": 1.0})
    assert rec == "pending"
    assert conf is None
    assert expl is None


def test_predict_invite_above_threshold():
    import src.services.predictor as pred
    from src.services.predictor import predict

    artifact = _make_artifact("fair", proba=0.9)
    pred._state["fair"]["model"] = artifact["pipeline"]
    pred._state["fair"]["feat_cols"] = artifact["feature_columns"]
    pred._state["fair"]["threshold"] = 0.5
    pred._initialized = True

    features = {f"f{i}": float(i) for i in range(22)}
    rec, conf, expl = predict(features, model="fair")

    assert rec == "Invite"
    assert conf == pytest.approx(0.9, abs=0.001)


def test_predict_reject_below_threshold():
    import src.services.predictor as pred
    from src.services.predictor import predict

    artifact = _make_artifact("fair", proba=0.2)
    pred._state["fair"]["model"] = artifact["pipeline"]
    pred._state["fair"]["feat_cols"] = artifact["feature_columns"]
    pred._state["fair"]["threshold"] = 0.5
    pred._initialized = True

    features = {f"f{i}": float(i) for i in range(22)}
    rec, conf, expl = predict(features, model="fair")

    assert rec == "Reject"
    assert conf == pytest.approx(0.8, abs=0.001)  # confidence = prob of predicted class


def test_predict_base_model_independent():
    """base and fair models are independent state."""
    import src.services.predictor as pred
    from src.services.predictor import predict

    pred._state["fair"]["model"] = _make_mock_pipeline(proba=0.9)
    pred._state["fair"]["feat_cols"] = [f"f{i}" for i in range(22)]
    pred._state["fair"]["threshold"] = 0.5

    pred._state["base"]["model"] = _make_mock_pipeline(proba=0.2)
    pred._state["base"]["feat_cols"] = [f"f{i}" for i in range(22)]
    pred._state["base"]["threshold"] = 0.5

    pred._initialized = True

    features = {f"f{i}": 1.0 for i in range(22)}
    rec_fair, _, _ = predict(features, model="fair")
    rec_base, _, _ = predict(features, model="base")

    assert rec_fair == "Invite"
    assert rec_base == "Reject"


def test_predict_missing_features_default_to_zero():
    """Features not in the input dict should default to 0 without raising."""
    import src.services.predictor as pred
    from src.services.predictor import predict

    pred._state["fair"]["model"] = _make_mock_pipeline(proba=0.7)
    pred._state["fair"]["feat_cols"] = ["f0", "f1", "f2"]
    pred._state["fair"]["threshold"] = 0.5
    pred._initialized = True

    rec, conf, _ = predict({}, model="fair")  # empty features dict
    assert rec in ("Invite", "Reject")


def test_predict_threshold_at_boundary():
    """predict_proba exactly equal to threshold → Invite (>=)."""
    import src.services.predictor as pred
    from src.services.predictor import predict

    pred._state["fair"]["model"] = _make_mock_pipeline(proba=0.5)
    pred._state["fair"]["feat_cols"] = ["f0"]
    pred._state["fair"]["threshold"] = 0.5
    pred._initialized = True

    rec, _, _ = predict({"f0": 1.0}, model="fair")
    assert rec == "Invite"


def test_predict_with_calibrator():
    """Calibrator adjusts the raw probability."""
    import src.services.predictor as pred
    from src.services.predictor import predict

    calibrator = MagicMock()
    calibrator.predict_proba.return_value = np.array([[0.3, 0.7]])

    pred._state["fair"]["model"] = _make_mock_pipeline(proba=0.4)
    pred._state["fair"]["feat_cols"] = ["f0"]
    pred._state["fair"]["threshold"] = 0.5
    pred._state["fair"]["calibrator"] = calibrator
    pred._state["fair"]["calibrator_logit"] = False
    pred._initialized = True

    rec, conf, _ = predict({"f0": 1.0}, model="fair")
    assert rec == "Invite"
    assert conf == pytest.approx(0.7, abs=0.001)


def test_load_models_idempotent():
    """_initialized flag prevents double loading."""
    import src.services.predictor as pred
    from src.services.predictor import predict

    load_count = 0
    original_load = pred._load_models if hasattr(pred, "_load_models") else None

    def counting_load():
        nonlocal load_count
        load_count += 1
        pred._initialized = True  # simulate successful load

    pred._initialized = False
    with patch.object(pred, "_load_models", counting_load):
        predict({"f0": 1.0})
        predict({"f0": 1.0})

    assert load_count == 1
