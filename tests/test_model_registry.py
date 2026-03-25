"""Tests for model registry structure and logistic model interface."""
import sqlite3
import os
import numpy as np
import pytest

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "db", "schema.sql")


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH) as f:
        sql = f.read()
    lines = [l for l in sql.splitlines() if "journal_mode" not in l]
    conn.executescript("\n".join(lines))
    return conn


class TestModelRegistry:
    def test_registry_contains_logistic_v1(self):
        from src.model import MODEL_REGISTRY
        assert "logistic_v1" in MODEL_REGISTRY

    def test_registry_contains_bayesian_v1(self):
        from src.model import MODEL_REGISTRY
        assert "bayesian_v1" in MODEL_REGISTRY

    def test_registry_has_three_models(self):
        from src.model import MODEL_REGISTRY
        assert len(MODEL_REGISTRY) >= 3

    def test_registry_entry_has_train_and_predict(self):
        from src.model import MODEL_REGISTRY
        for key, entry in MODEL_REGISTRY.items():
            assert "train" in entry, f"{key} missing 'train'"
            assert "predict" in entry, f"{key} missing 'predict'"
            assert callable(entry["train"]), f"{key} train not callable"
            assert callable(entry["predict"]), f"{key} predict not callable"

    def test_logistic_train_callable_signature(self):
        """logistic train accepts (conn, config) and returns (model, metrics)."""
        from src.model import MODEL_REGISTRY
        train_fn = MODEL_REGISTRY["logistic_v1"]["train"]
        import inspect
        sig = inspect.signature(train_fn)
        params = list(sig.parameters.keys())
        assert "conn" in params
        assert "config" in params

    def test_logistic_predict_callable_signature(self):
        """logistic predict accepts (model, features) and returns dict."""
        from src.model import MODEL_REGISTRY
        predict_fn = MODEL_REGISTRY["logistic_v1"]["predict"]
        import inspect
        sig = inspect.signature(predict_fn)
        params = list(sig.parameters.keys())
        assert "model" in params
        assert "features" in params


class TestBaseImports:
    def test_base_exports_logistic_features(self):
        from src.model.base import LOGISTIC_FEATURES
        assert len(LOGISTIC_FEATURES) == 16
        assert "elo_diff" in LOGISTIC_FEATURES

    def test_base_exports_build_training_matrix(self):
        from src.model.base import build_training_matrix
        assert callable(build_training_matrix)

    def test_base_exports_save_load_model(self):
        from src.model.base import save_model, load_model
        assert callable(save_model)
        assert callable(load_model)


class TestTrainerShimBackwardCompat:
    def test_trainer_exports_logistic_features(self):
        from src.model.trainer import LOGISTIC_FEATURES
        assert len(LOGISTIC_FEATURES) == 16

    def test_trainer_exports_train_and_calibrate(self):
        from src.model.trainer import train_and_calibrate
        assert callable(train_and_calibrate)

    def test_trainer_exports_build_training_matrix(self):
        from src.model.trainer import build_training_matrix
        assert callable(build_training_matrix)

    def test_trainer_exports_save_load(self):
        from src.model.trainer import save_model, load_model
        assert callable(save_model)
        assert callable(load_model)


class TestSchemaHasCIColumns:
    def test_predictions_table_has_p5_p50_p95(self):
        conn = make_conn()
        cursor = conn.execute("PRAGMA table_info(predictions)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "p5" in columns, "predictions table missing p5 column"
        assert "p50" in columns, "predictions table missing p50 column"
        assert "p95" in columns, "predictions table missing p95 column"

    def test_ci_columns_accept_null(self):
        """CI columns should accept NULL for non-Bayesian models."""
        conn = make_conn()
        # Insert a tournament and match first for FK
        conn.execute("INSERT INTO tournaments VALUES ('T1','ATP','Test',NULL,NULL,NULL,'2023-01-01')")
        conn.execute("INSERT INTO matches (tourney_id,match_num,tour,winner_id,loser_id,tourney_date) VALUES ('T1',1,'ATP',1,2,'2023-01-01')")
        conn.execute(
            """INSERT INTO predictions
               (tourney_id,match_num,tour,player_id,model_version,
                calibrated_prob,predicted_at,p5,p50,p95)
               VALUES ('T1',1,'ATP',1,'logistic_v1',0.6,'2023-01-01T00:00:00Z',NULL,NULL,NULL)"""
        )
        conn.commit()
        row = conn.execute("SELECT p5,p50,p95 FROM predictions WHERE player_id=1").fetchone()
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None


class TestPinnacleRegistryVersions:
    def test_registry_has_pinnacle_versions(self):
        from src.model import MODEL_REGISTRY
        assert "logistic_v3_pinnacle" in MODEL_REGISTRY
        assert "xgboost_v2_pinnacle" in MODEL_REGISTRY

    def test_registry_existing_versions_intact(self):
        from src.model import MODEL_REGISTRY
        for v in ("logistic_v1", "xgboost_v1", "bayesian_v1", "ensemble_v1"):
            assert v in MODEL_REGISTRY, f"Existing version {v} missing from registry"

    def test_registry_pinnacle_entries_have_train_predict(self):
        from src.model import MODEL_REGISTRY
        for v in ("logistic_v3_pinnacle", "xgboost_v2_pinnacle"):
            entry = MODEL_REGISTRY[v]
            assert "train" in entry, f"{v} missing 'train' key"
            assert "predict" in entry, f"{v} missing 'predict' key"
            assert callable(entry["train"]), f"{v} train not callable"
            assert callable(entry["predict"]), f"{v} predict not callable"


class TestEnsembleV2Pinnacle:
    def test_ensemble_v2_pinnacle_in_registry(self):
        """ensemble_v2_pinnacle must exist in MODEL_REGISTRY with train and predict keys."""
        from src.model import MODEL_REGISTRY
        assert "ensemble_v2_pinnacle" in MODEL_REGISTRY
        entry = MODEL_REGISTRY["ensemble_v2_pinnacle"]
        assert "train" in entry
        assert "predict" in entry
        assert callable(entry["train"])
        assert callable(entry["predict"])

    def test_pinnacle_component_models(self):
        """PINNACLE_COMPONENT_MODELS must equal the two pinnacle model keys."""
        from src.model.ensemble import PINNACLE_COMPONENT_MODELS
        assert PINNACLE_COMPONENT_MODELS == ["logistic_v3_pinnacle", "xgboost_v2_pinnacle"]

    def test_ensemble_v1_unchanged(self):
        """Original COMPONENT_MODELS must remain unchanged after adding pinnacle ensemble."""
        from src.model.ensemble import COMPONENT_MODELS
        assert COMPONENT_MODELS == ["logistic_v1", "xgboost_v1", "bayesian_v1"]

    def test_ensemble_v2_train_uses_pinnacle_components(self):
        """train_pinnacle calls each component's train function and compute_weights."""
        from unittest.mock import MagicMock, patch
        import sqlite3
        from src.model.ensemble import train_pinnacle

        fake_conn = MagicMock(spec=sqlite3.Connection)

        # Fake return values from component train functions
        fake_log_model = MagicMock()
        fake_xgb_model = MagicMock()
        fake_log_metrics = {"val_brier_score": 0.20}
        fake_xgb_metrics = {"val_brier_score": 0.18}

        fake_registry = {
            "logistic_v3_pinnacle": {
                "train": MagicMock(return_value=(fake_log_model, fake_log_metrics)),
                "predict": MagicMock(),
            },
            "xgboost_v2_pinnacle": {
                "train": MagicMock(return_value=(fake_xgb_model, fake_xgb_metrics)),
                "predict": MagicMock(),
            },
        }

        # Stub build_training_matrix / compute_time_weights / temporal_split
        import numpy as np
        fake_X = np.zeros((10, 2))
        fake_y = np.ones(10)
        fake_dates = ["2020-01-01"] * 10
        fake_split = {
            "X_train": fake_X, "y_train": fake_y,
            "X_val": fake_X, "y_val": fake_y,
            "w_train": np.ones(10),
            "train_dates": fake_dates, "val_dates": fake_dates,
        }

        with patch("src.model.ensemble.MODEL_REGISTRY", fake_registry), \
             patch("src.model.ensemble.build_training_matrix",
                   return_value=(fake_X, fake_y, fake_dates)), \
             patch("src.model.ensemble.compute_time_weights",
                   return_value=np.ones(10)), \
             patch("src.model.ensemble.temporal_split",
                   return_value=fake_split):
            state, metrics = train_pinnacle(fake_conn)

        # Both components were trained
        fake_registry["logistic_v3_pinnacle"]["train"].assert_called_once()
        fake_registry["xgboost_v2_pinnacle"]["train"].assert_called_once()

        # Returned state contains both models and their weights
        assert "logistic_v3_pinnacle" in state["models"]
        assert "xgboost_v2_pinnacle" in state["models"]
        assert "logistic_v3_pinnacle" in state["weights"]
        assert "xgboost_v2_pinnacle" in state["weights"]
