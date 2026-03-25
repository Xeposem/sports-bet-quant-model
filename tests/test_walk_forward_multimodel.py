"""Tests for walk_forward.py multi-model dispatch (Task 2, Plan 07-04)."""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_logistic_model(prob=0.65):
    """Return a mock sklearn-compatible model with predict_proba."""
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[1 - prob, prob]])
    return mock_model


def _make_mock_xgb_model(prob=0.70):
    """Return a mock XGBoost-compatible model with predict_proba."""
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[1 - prob, prob]])
    return mock_model


def _make_mock_ensemble_state(log_prob=0.65, xgb_prob=0.70):
    """Return a minimal ensemble state dict with mock component models."""
    log_model = MagicMock()
    log_model.predict_proba.return_value = np.array([[1 - log_prob, log_prob]])
    xgb_model = MagicMock()
    xgb_model.predict_proba.return_value = np.array([[1 - xgb_prob, xgb_prob]])
    return {
        "models": {
            "logistic_v1": log_model,
            "xgboost_v1": xgb_model,
        },
        "weights": {
            "logistic_v1": 0.6,
            "xgboost_v1": 0.4,
        },
        "brier_scores": {
            "logistic_v1": 0.22,
            "xgboost_v1": 0.20,
        },
    }


# ---------------------------------------------------------------------------
# Tests for _train_model_for_fold
# ---------------------------------------------------------------------------

class TestTrainModelForFold:

    def test_logistic_calls_train_and_calibrate(self):
        """logistic_v1 should delegate to train_and_calibrate with the pre-built arrays."""
        from src.backtest.walk_forward import _train_model_for_fold

        X12 = np.ones((100, 12))
        y = np.ones(100)
        w = np.ones(100)
        mock_model = _make_mock_logistic_model()
        mock_metrics = {"val_brier_score": 0.22, "val_log_loss": 0.55}

        with patch("src.backtest.walk_forward.train_and_calibrate",
                   return_value=(mock_model, mock_metrics)) as mock_tac:
            model, metrics = _train_model_for_fold(
                "logistic_v1", X12, y, X12, y, w, {}, conn=None, train_end=None
            )

        mock_tac.assert_called_once()
        assert metrics["val_brier_score"] == 0.22

    def test_xgboost_calls_build_xgb_training_matrix(self):
        """xgboost_v1 should call build_xgb_training_matrix with conn + train_end."""
        from src.backtest.walk_forward import _train_model_for_fold

        X12 = np.ones((100, 12))
        y = np.ones(100)
        w = np.ones(100)
        X28 = np.ones((100, 28))

        mock_conn = MagicMock()
        mock_xgb_model = _make_mock_xgb_model()
        mock_metrics = {"val_brier_score": 0.20}
        mock_dates = ["2020-01-01"] * 100

        with patch("src.backtest.walk_forward.build_xgb_training_matrix",
                   return_value=(X28, y, mock_dates)) as mock_build, \
             patch("src.backtest.walk_forward.compute_time_weights",
                   return_value=w) as mock_weights, \
             patch("src.backtest.walk_forward.temporal_split",
                   return_value={
                       "X_train": X28[:80], "y_train": y[:80], "w_train": w[:80],
                       "X_val": X28[80:], "y_val": y[80:],
                   }) as mock_split, \
             patch("src.model.xgboost_model.train_fold",
                   return_value=(mock_xgb_model, mock_metrics)):
            model, metrics = _train_model_for_fold(
                "xgboost_v1", X12, y, X12, y, w, {},
                conn=mock_conn, train_end="2021-01-01"
            )

        mock_build.assert_called_once_with(mock_conn, "2021-01-01")
        assert metrics["val_brier_score"] == 0.20

    def test_xgboost_raises_without_conn(self):
        """xgboost_v1 should raise ValueError when conn is None."""
        from src.backtest.walk_forward import _train_model_for_fold

        X12 = np.ones((100, 12))
        y = np.ones(100)
        w = np.ones(100)

        with pytest.raises(ValueError, match="xgboost_v1 requires"):
            _train_model_for_fold(
                "xgboost_v1", X12, y, X12, y, w, {}, conn=None, train_end=None
            )

    def test_unknown_model_version_raises(self):
        """Unknown model_version should raise ValueError."""
        from src.backtest.walk_forward import _train_model_for_fold

        X12 = np.ones((100, 12))
        y = np.ones(100)
        w = np.ones(100)

        with pytest.raises(ValueError, match="Unknown model_version"):
            _train_model_for_fold(
                "unknown_v99", X12, y, X12, y, w, {}, conn=None, train_end=None
            )


# ---------------------------------------------------------------------------
# Tests for _predict_with_model
# ---------------------------------------------------------------------------

class TestPredictWithModel:

    def test_logistic_returns_float_in_0_1(self):
        """logistic_v1 predict returns a float in [0, 1]."""
        from src.backtest.walk_forward import _predict_with_model

        mock_model = _make_mock_logistic_model(prob=0.65)
        features_12 = np.ones((1, 12))

        result = _predict_with_model("logistic_v1", mock_model, features_12)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
        assert abs(result - 0.65) < 1e-9

    def test_xgboost_with_27col_returns_float_in_0_1(self):
        """xgboost_v1 predict with 28-col XGB features returns a float in [0, 1]."""
        from src.backtest.walk_forward import _predict_with_model

        mock_model = _make_mock_xgb_model(prob=0.70)
        features_12 = np.ones((1, 12))
        features_28 = np.ones((1, 28))

        result = _predict_with_model(
            "xgboost_v1", mock_model, features_12, xgb_feature_vec=features_28
        )
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
        assert abs(result - 0.70) < 1e-9

    def test_xgboost_without_xgb_features_raises(self):
        """xgboost_v1 predict without xgb_feature_vec raises ValueError."""
        from src.backtest.walk_forward import _predict_with_model

        mock_model = _make_mock_xgb_model()
        features_12 = np.ones((1, 12))

        with pytest.raises(ValueError, match="xgboost_v1 prediction requires"):
            _predict_with_model("xgboost_v1", mock_model, features_12, xgb_feature_vec=None)

    def test_ensemble_with_xgb_features_returns_float(self):
        """ensemble_v1 predict blends logistic and xgboost component predictions."""
        from src.backtest.walk_forward import _predict_with_model

        ensemble_state = _make_mock_ensemble_state(log_prob=0.65, xgb_prob=0.70)
        features_12 = np.ones((1, 12))
        features_28 = np.ones((1, 28))

        result = _predict_with_model(
            "ensemble_v1", ensemble_state, features_12, xgb_feature_vec=features_28
        )
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
        # Expected: logistic=0.65 * weight=0.6 + xgboost=0.70 * weight=0.4 = 0.67
        expected = 0.65 * 0.6 + 0.70 * 0.4
        assert abs(result - expected) < 1e-6

    def test_predict_unknown_model_version_raises(self):
        """Unknown model_version in _predict_with_model raises ValueError."""
        from src.backtest.walk_forward import _predict_with_model

        mock_model = MagicMock()
        features_12 = np.ones((1, 12))

        with pytest.raises(ValueError, match="Unknown model_version"):
            _predict_with_model("unknown_v99", mock_model, features_12)

    def test_xgboost_uses_xgb_feature_vec_not_logistic_vec(self):
        """xgboost_v1 predict_proba is called with xgb_feature_vec, not feature_vec."""
        from src.backtest.walk_forward import _predict_with_model

        mock_model = _make_mock_xgb_model(prob=0.72)
        features_12 = np.zeros((1, 12))   # all zeros
        features_28 = np.ones((1, 28))    # all ones — distinct

        _predict_with_model(
            "xgboost_v1", mock_model, features_12, xgb_feature_vec=features_28
        )

        # Verify predict_proba was called with the 28-column vector (ones), not the 12-column (zeros)
        call_args = mock_model.predict_proba.call_args[0][0]
        assert call_args.shape == (1, 28)
        assert np.all(call_args == 1.0)


# ---------------------------------------------------------------------------
# Phase 13: CLV threshold threading tests
# ---------------------------------------------------------------------------


class TestCLVThreadingInWalkForward:
    def test_clv_threshold_in_fold_config(self):
        """run_walk_forward passes clv_threshold from config into run_fold's config dict."""
        from src.backtest.walk_forward import run_walk_forward
        import sqlite3

        mock_conn = MagicMock(spec=sqlite3.Connection)

        with patch("src.backtest.walk_forward.generate_folds") as mock_gen_folds, \
             patch("src.backtest.walk_forward.run_fold") as mock_run_fold, \
             patch("src.backtest.walk_forward._store_backtest_results"):
            mock_gen_folds.return_value = [("2022-01-01", "2022-01-01", "2023-01-01")]
            mock_run_fold.return_value = ([], 1000.0)

            run_walk_forward(mock_conn, {"clv_threshold": 0.07})

            assert mock_run_fold.called
            call_args = mock_run_fold.call_args[0]
            fold_config_arg = call_args[5]  # 6th positional arg is config
            assert fold_config_arg.get("clv_threshold") == 0.07, (
                f"Expected 0.07, got {fold_config_arg.get('clv_threshold')}"
            )

    def test_clv_threshold_default_zero_in_fold_config(self):
        """run_walk_forward defaults clv_threshold to 0.0 if not in config (backward compat)."""
        from src.backtest.walk_forward import run_walk_forward
        import sqlite3

        mock_conn = MagicMock(spec=sqlite3.Connection)

        with patch("src.backtest.walk_forward.generate_folds") as mock_gen_folds, \
             patch("src.backtest.walk_forward.run_fold") as mock_run_fold, \
             patch("src.backtest.walk_forward._store_backtest_results"):
            mock_gen_folds.return_value = [("2022-01-01", "2022-01-01", "2023-01-01")]
            mock_run_fold.return_value = ([], 1000.0)

            run_walk_forward(mock_conn, {})  # no clv_threshold → should default to 0.0

            assert mock_run_fold.called
            fold_config_arg = mock_run_fold.call_args[0][5]  # 6th positional arg is config
            assert fold_config_arg.get("clv_threshold") == 0.0, (
                f"Expected default 0.0, got {fold_config_arg.get('clv_threshold')}"
            )
