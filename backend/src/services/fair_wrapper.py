import numpy as np


class EGWrapper:
    """Wraps ExponentiatedGradient + scaler into a sklearn-compatible object."""
    def __init__(self, scaler, eg):
        self.scaler = scaler
        self.eg = eg

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
        return proba
