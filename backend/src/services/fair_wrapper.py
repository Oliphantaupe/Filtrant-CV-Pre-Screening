class EGWrapper:
    """Wraps ExponentiatedGradient + scaler into a sklearn-compatible object."""
    def __init__(self, scaler, eg):
        self.scaler = scaler
        self.eg = eg

    def predict(self, X):
        return self.eg.predict(self.scaler.transform(X))

    def predict_proba(self, X):
        return self.eg._pmf_predict(self.scaler.transform(X))
