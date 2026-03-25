"""
Tests for XGBoost model — XGB_FEATURES constant, build_xgb_training_matrix,
train_fold, predict, Optuna tuning, feature importances, and registry entry.

Uses synthetic data (n=300, seed=42, 27 features). Optuna mocked to n_trials=2
for speed in CI.
"""
from __future__ import annotations

import sqlite3
import os
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "db", "schema.sql")


def make_conn() -> sqlite3.Connection:
    """In-memory SQLite connection with full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH) as f:
        sql = f.read()
    lines = [line for line in sql.splitlines() if "journal_mode" not in line]
    conn.executescript("\n".join(lines))
    return conn


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

def make_synthetic_data(n=300, n_features=30, seed=42):
    """30-column synthetic data to match XGB_FEATURES length."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, n_features))
    y = rng.integers(0, 2, size=n).astype(np.float64)
    weights = np.ones(n)
    return X, y, weights


# ---------------------------------------------------------------------------
# Task 1: XGB_FEATURES constant and build_xgb_training_matrix
# ---------------------------------------------------------------------------

class TestXGBFeatures:
    def test_xgb_features_length(self):
        from src.model.base import XGB_FEATURES
        # 16 logistic (including 2 pinnacle) + 11 new numeric (RD diffs, serve stats, h2h_surface, sentiment, sets_7d)
        # + 5 one-hot context (surface_clay, surface_grass, surface_hard, level_G, level_M) - 1 (round_ordinal already counted)
        assert len(XGB_FEATURES) == 31

    def test_xgb_features_superset_of_logistic(self):
        from src.model.base import LOGISTIC_FEATURES, XGB_FEATURES
        for f in LOGISTIC_FEATURES:
            assert f in XGB_FEATURES, f"LOGISTIC_FEATURES item {f} missing from XGB_FEATURES"

    def test_build_xgb_training_matrix_callable(self):
        from src.model.base import build_xgb_training_matrix
        assert callable(build_xgb_training_matrix)

    def test_build_xgb_training_matrix_empty_db(self):
        """Empty DB returns zero-row arrays without error."""
        from src.model.base import build_xgb_training_matrix, XGB_FEATURES
        conn = make_conn()
        X, y, dates = build_xgb_training_matrix(conn)
        assert X.shape == (0, len(XGB_FEATURES))
        assert y.shape == (0,)
        assert dates == []

    def test_xgb_features_includes_pinnacle(self):
        from src.model.base import XGB_FEATURES
        assert "pinnacle_prob_diff" in XGB_FEATURES
        assert "has_no_pinnacle" in XGB_FEATURES

    def test_build_xgb_matrix_sql_has_pinnacle(self):
        from src.model.base import _BUILD_XGB_MATRIX_SQL
        assert "pinnacle_prob_diff" in _BUILD_XGB_MATRIX_SQL
        assert "has_no_pinnacle" in _BUILD_XGB_MATRIX_SQL

    def test_build_xgb_training_matrix_train_end_filters(self):
        """train_end parameter filters rows to before the cutoff date."""
        from src.model.base import build_xgb_training_matrix, XGB_FEATURES
        conn = make_conn()
        # Insert two matches at different dates
        conn.execute("INSERT INTO tournaments VALUES ('T1','ATP','Test','Hard',32,'A','2020-01-10')")
        conn.execute("INSERT INTO matches (tourney_id,match_num,tour,winner_id,loser_id,tourney_date) VALUES ('T1',1,'ATP',1,2,'2020-01-10')")
        conn.execute("INSERT INTO tournaments VALUES ('T2','ATP','Test2','Clay',32,'M','2021-06-01')")
        conn.execute("INSERT INTO matches (tourney_id,match_num,tour,winner_id,loser_id,tourney_date) VALUES ('T2',1,'ATP',3,4,'2021-06-01')")
        # Insert minimal match_features for both matches (winner + loser rows)
        for tourney_id, match_num, date_str in [('T1', 1, '2020-01-10'), ('T2', 1, '2021-06-01')]:
            for role in ('winner', 'loser'):
                conn.execute(
                    "INSERT INTO match_features (tourney_id, match_num, tour, player_role, surface, tourney_level) "
                    "VALUES (?, ?, 'ATP', ?, 'Hard', 'A')",
                    (tourney_id, match_num, role)
                )
        conn.commit()
        # With train_end='2021-01-01', only the 2020 match should be returned
        X, y, dates = build_xgb_training_matrix(conn, train_end="2021-01-01")
        assert len(dates) == 1
        assert dates[0] == '2020-01-10'


# ---------------------------------------------------------------------------
# Task 2: XGBoost model with Optuna tuning and dual calibration
# ---------------------------------------------------------------------------

class TestXGBoostTrainFold:
    """train_fold returns (model, metrics) with expected structure."""

    def test_train_fold_returns_tuple(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]
        w_train = w[:split]
        config = {"n_trials": 2}
        result = train_fold(X_train, y_train, X_val, y_val, w_train, config)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_train_fold_model_has_predict_proba(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        model, _ = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        assert hasattr(model, "predict_proba")

    def test_train_fold_predict_proba_in_unit_interval(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        model, _ = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        proba = model.predict_proba(X[split:])[:, 1]
        assert np.all(proba >= 0.0)
        assert np.all(proba <= 1.0)

    def test_train_fold_metrics_keys(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        _, metrics = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        expected_keys = {
            "calibration_method", "val_brier_score", "val_log_loss",
            "brier_sigmoid", "brier_isotonic", "feature_importances",
        }
        for key in expected_keys:
            assert key in metrics, f"metrics missing key: {key}"

    def test_train_fold_calibration_method_valid(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        _, metrics = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        assert metrics["calibration_method"] in ("sigmoid", "isotonic")


class TestXGBoostTuning:
    """Optuna objective returns float and best_params has expected keys."""

    def test_objective_returns_float(self):
        from src.model.xgboost_model import _objective
        import optuna
        X, y, w = make_synthetic_data(n=100)
        study = optuna.create_study(direction="minimize")
        study.optimize(
            lambda trial: _objective(trial, X, y, w, n_splits=2),
            n_trials=1,
        )
        assert isinstance(study.best_value, float)

    def test_best_params_keys(self):
        from src.model.xgboost_model import _objective
        import optuna
        X, y, w = make_synthetic_data(n=100)
        study = optuna.create_study(direction="minimize")
        study.optimize(
            lambda trial: _objective(trial, X, y, w, n_splits=2),
            n_trials=1,
        )
        expected_keys = {"n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree"}
        for key in expected_keys:
            assert key in study.best_params, f"best_params missing: {key}"


class TestXGBoostImportance:
    """feature_importances in metrics is a 27-entry dict with non-negative values."""

    def test_feature_importances_is_dict(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        _, metrics = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        assert isinstance(metrics["feature_importances"], dict)

    def test_feature_importances_length_matches_xgb_features(self):
        from src.model.xgboost_model import train_fold
        from src.model.base import XGB_FEATURES
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        _, metrics = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        assert len(metrics["feature_importances"]) == len(XGB_FEATURES)

    def test_feature_importances_keys_match_xgb_features(self):
        from src.model.xgboost_model import train_fold
        from src.model.base import XGB_FEATURES
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        _, metrics = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        importances = metrics["feature_importances"]
        for feat in XGB_FEATURES:
            assert feat in importances, f"feature_importances missing key: {feat}"

    def test_feature_importances_non_negative(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        _, metrics = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        for feat, val in metrics["feature_importances"].items():
            assert val >= 0, f"negative importance for {feat}: {val}"


class TestXGBoostPredict:
    """predict returns dict with calibrated_prob float in [0, 1]."""

    def _trained_model(self):
        from src.model.xgboost_model import train_fold
        X, y, w = make_synthetic_data()
        n = len(y)
        split = int(0.8 * n)
        config = {"n_trials": 2}
        model, _ = train_fold(X[:split], y[:split], X[split:], y[split:], w[:split], config)
        return model, X

    def test_predict_returns_dict(self):
        from src.model.xgboost_model import predict
        model, X = self._trained_model()
        result = predict(model, X[0])
        assert isinstance(result, dict)

    def test_predict_has_calibrated_prob_key(self):
        from src.model.xgboost_model import predict
        model, X = self._trained_model()
        result = predict(model, X[0])
        assert "calibrated_prob" in result

    def test_predict_calibrated_prob_is_float(self):
        from src.model.xgboost_model import predict
        model, X = self._trained_model()
        result = predict(model, X[0])
        assert isinstance(result["calibrated_prob"], float)

    def test_predict_calibrated_prob_in_unit_interval(self):
        from src.model.xgboost_model import predict
        model, X = self._trained_model()
        for i in range(10):
            result = predict(model, X[i])
            assert 0.0 <= result["calibrated_prob"] <= 1.0

    def test_predict_accepts_2d_input(self):
        from src.model.xgboost_model import predict
        model, X = self._trained_model()
        # 2D array with single row
        result = predict(model, X[:1])
        assert 0.0 <= result["calibrated_prob"] <= 1.0


class TestXGBoostRegistry:
    """MODEL_REGISTRY contains xgboost_v1 with callable train/predict."""

    def test_registry_has_xgboost_v1(self):
        from src.model import MODEL_REGISTRY
        assert "xgboost_v1" in MODEL_REGISTRY

    def test_registry_xgboost_v1_has_train(self):
        from src.model import MODEL_REGISTRY
        assert "train" in MODEL_REGISTRY["xgboost_v1"]
        assert callable(MODEL_REGISTRY["xgboost_v1"]["train"])

    def test_registry_xgboost_v1_has_predict(self):
        from src.model import MODEL_REGISTRY
        assert "predict" in MODEL_REGISTRY["xgboost_v1"]
        assert callable(MODEL_REGISTRY["xgboost_v1"]["predict"])

    def test_registry_logistic_v1_still_present(self):
        """Adding xgboost_v1 must not break the existing logistic_v1 entry."""
        from src.model import MODEL_REGISTRY
        assert "logistic_v1" in MODEL_REGISTRY
