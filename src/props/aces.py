"""Aces stat model — Poisson/NegBin GLM predicting ace count per match."""


def train(conn, config=None) -> dict:
    """Train the aces GLM model. Implemented in Task 2."""
    raise NotImplementedError("aces.train() implemented in Task 2")


def predict(trained: dict, feature_row: dict) -> dict:
    """Predict PMF for ace count. Implemented in Task 2."""
    raise NotImplementedError("aces.predict() implemented in Task 2")
