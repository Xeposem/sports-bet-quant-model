"""Double faults stat model — Poisson/NegBin GLM predicting double fault count."""


def train(conn, config=None) -> dict:
    """Train the double_faults GLM model. Implemented in Task 2."""
    raise NotImplementedError("double_faults.train() implemented in Task 2")


def predict(trained: dict, feature_row: dict) -> dict:
    """Predict PMF for double fault count. Implemented in Task 2."""
    raise NotImplementedError("double_faults.predict() implemented in Task 2")
