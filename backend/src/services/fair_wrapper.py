import numpy as np


class EGWrapper:
    """Wraps ExponentiatedGradient + scaler into a sklearn-compatible object."""
    def __init__(self, scaler, eg, calibrator=None):
        self.scaler = scaler
        self.eg = eg
        self.calibrator = calibrator

    def predict(self, X):
        return self.eg.predict(self.scaler.transform(X))

    def predict_proba(self, X):
        X_scaled = self.scaler.transform(X)
        proba = np.zeros((X_scaled.shape[0], 2))
        for w, clf in zip(self.eg.weights_, self.eg.predictors_):
            if hasattr(clf, "predict_proba"):
                proba += w * clf.predict_proba(X_scaled)
            else:
                pred = clf.predict(X_scaled).astype(float)
                proba[:, 1] += w * pred
                proba[:, 0] += w * (1.0 - pred)
        if self.calibrator is not None:
            raw_p = np.clip(proba[:, 1], 1e-7, 1 - 1e-7)
            if getattr(self, "calibrator_logit_transform", False):
                # Temperature scaling: LR fitted on logit(raw_proba) — preserves ranking
                from scipy.special import logit as _logit
                logit_p = _logit(raw_p).reshape(-1, 1)
                p = self.calibrator.predict_proba(logit_p)[:, 1]
            elif hasattr(self.calibrator, "predict_proba"):
                p = self.calibrator.predict_proba(raw_p.reshape(-1, 1))[:, 1]
            else:
                p = np.clip(self.calibrator.predict(raw_p), 0, 1)
            proba = np.column_stack([1 - p, p])
        return proba
