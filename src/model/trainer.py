"""
Backward-compatible shim — re-exports from base.py and logistic.py.

All callers that import from src.model.trainer continue to work unchanged:
  - src/backtest/walk_forward.py
  - src/api/main.py
  - src/odds/cli.py
  - tests/test_model.py

New code should import directly from src.model.base or src.model.logistic.
"""

from src.model.base import (
    LOGISTIC_FEATURES,
    build_training_matrix,
    compute_time_weights,
    temporal_split,
    save_model,
    load_model,
)
from src.model.logistic import train_and_calibrate

__all__ = [
    "LOGISTIC_FEATURES",
    "build_training_matrix",
    "compute_time_weights",
    "temporal_split",
    "train_and_calibrate",
    "save_model",
    "load_model",
]
