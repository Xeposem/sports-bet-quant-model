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
        assert len(LOGISTIC_FEATURES) == 12
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
        assert len(LOGISTIC_FEATURES) == 12

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
