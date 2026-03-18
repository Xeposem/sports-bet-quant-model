"""Tests for ensemble weight computation and blending."""
import numpy as np
import pytest


class TestComputeWeights:
    def test_weights_sum_to_one(self):
        from src.model.ensemble import compute_weights
        w = compute_weights({"a": 0.20, "b": 0.25, "c": 0.22})
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_lower_brier_gets_higher_weight(self):
        from src.model.ensemble import compute_weights
        w = compute_weights({"good": 0.18, "bad": 0.30})
        assert w["good"] > w["bad"]

    def test_filters_none_values(self):
        from src.model.ensemble import compute_weights
        w = compute_weights({"a": 0.20, "b": None, "c": 0.25})
        assert "b" not in w
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_single_model(self):
        from src.model.ensemble import compute_weights
        w = compute_weights({"only": 0.22})
        assert w == {"only": 1.0}

    def test_raises_on_all_none(self):
        from src.model.ensemble import compute_weights
        with pytest.raises(ValueError):
            compute_weights({"a": None, "b": None})

    def test_filters_zero_brier(self):
        from src.model.ensemble import compute_weights
        w = compute_weights({"a": 0.0, "b": 0.25})
        # Zero Brier would cause division by zero — should be filtered
        assert "a" not in w or w.get("b", 0) == 1.0


class TestBlend:
    def test_weighted_average(self):
        from src.model.ensemble import blend
        predictions = {"a": 0.6, "b": 0.8}
        weights = {"a": 0.4, "b": 0.6}
        result = blend(predictions, weights)
        expected = 0.6 * 0.4 + 0.8 * 0.6  # 0.72
        assert abs(result - expected) < 1e-9

    def test_equal_weights(self):
        from src.model.ensemble import blend
        predictions = {"a": 0.5, "b": 0.7}
        weights = {"a": 0.5, "b": 0.5}
        result = blend(predictions, weights)
        assert abs(result - 0.6) < 1e-9

    def test_single_model_passthrough(self):
        from src.model.ensemble import blend
        result = blend({"only": 0.65}, {"only": 1.0})
        assert abs(result - 0.65) < 1e-9


class TestEnsembleEVIntegration:
    def test_ensemble_prob_works_with_compute_ev(self):
        """Ensemble calibrated_prob feeds into compute_ev unchanged."""
        from src.model.ensemble import blend
        from src.model.predictor import compute_ev
        prob = blend({"a": 0.6, "b": 0.7}, {"a": 0.5, "b": 0.5})
        ev = compute_ev(prob, 2.10)
        expected_ev = (0.65 * 2.10) - 1.0  # 0.365
        assert abs(ev - expected_ev) < 1e-9


class TestEnsembleRegistry:
    def test_registry_contains_ensemble_v1(self):
        from src.model import MODEL_REGISTRY
        assert "ensemble_v1" in MODEL_REGISTRY

    def test_registry_has_four_models(self):
        from src.model import MODEL_REGISTRY
        assert len(MODEL_REGISTRY) >= 4
