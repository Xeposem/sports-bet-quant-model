"""
Model quality metrics for the logistic regression prediction pipeline.

Primary metrics per requirements MOD-05: Brier score and log loss (not accuracy).
These measure probability calibration quality, which is required for valid EV calculation.

Key exports:
  - compute_metrics: Brier score, log loss, and sample count
  - calibration_curve_data: bin midpoints and empirical frequencies for calibration plots
"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import calibration_curve as _sklearn_calibration_curve
from sklearn.metrics import brier_score_loss, log_loss


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    """
    Compute primary model quality metrics.

    Uses Brier score and log loss per requirements MOD-05.
    Accuracy is intentionally excluded — it does not measure probability calibration.

    Parameters
    ----------
    y_true:
        Array of true binary labels (0.0 or 1.0).
    y_prob:
        Array of predicted probabilities in [0, 1].

    Returns
    -------
    dict with keys:
        brier_score: float — mean squared error between probability and outcome
        log_loss: float — cross-entropy loss
        n_samples: int — number of samples evaluated
    """
    return {
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob)),
        "n_samples": int(len(y_true)),
    }


def calibration_curve_data(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> dict:
    """
    Compute calibration curve data for visualization.

    Splits predictions into n_bins probability buckets and computes the
    empirical positive rate per bucket. Well-calibrated models have
    empirical_freq ≈ bin_midpoints (diagonal line on calibration plot).

    Parameters
    ----------
    y_true:
        Array of true binary labels.
    y_prob:
        Array of predicted probabilities.
    n_bins:
        Number of probability bins. Default 10.

    Returns
    -------
    dict with keys:
        bin_midpoints: list[float] — mean predicted probability per bin
        empirical_freq: list[float] — fraction of positives per bin
    """
    fraction_of_positives, mean_predicted_value = _sklearn_calibration_curve(
        y_true, y_prob, n_bins=n_bins
    )
    return {
        "bin_midpoints": mean_predicted_value.tolist(),
        "empirical_freq": fraction_of_positives.tolist(),
    }
