"""Games won stat model — NegBin GLM predicting total games won per match."""

from src.props.score_parser import parse_score  # noqa: F401 — imported for Task 2 use


def train(conn, config=None) -> dict:
    """Train the games_won GLM model. Implemented in Task 2."""
    raise NotImplementedError("games_won.train() implemented in Task 2")


def predict(trained: dict, feature_row: dict) -> dict:
    """Predict PMF for games won. Implemented in Task 2."""
    raise NotImplementedError("games_won.predict() implemented in Task 2")
