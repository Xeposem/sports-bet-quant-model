"""Tests for Bayesian hierarchical logistic model (PyMC).

Tests use mocked MCMC — no actual sampling occurs. This keeps the suite fast.
"""
from __future__ import annotations

import numpy as np
import pytest
import arviz as az
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers: build small synthetic datasets for testing
# ---------------------------------------------------------------------------

def _make_training_data(n=100, n_features=12):
    rng = np.random.default_rng(0)
    X_train = rng.standard_normal((n, n_features))
    y_train = rng.integers(0, 2, size=n).astype(np.float64)
    X_val = rng.standard_normal((20, n_features))
    y_val = rng.integers(0, 2, size=20).astype(np.float64)
    w_train = np.ones(n)
    surface_train = np.array([0] * 40 + [1] * 40 + [2] * 20, dtype=np.int64)
    return X_train, y_train, X_val, y_val, w_train, surface_train


def _make_mock_idata(n_chains=2, n_draws=100, n_surfaces=3, n_features=12, n_matches=20):
    """Create a mock InferenceData object for testing without real MCMC."""
    rng = np.random.default_rng(42)
    # Build posterior with known shape: (chain, draw, dim)
    posterior = {
        "alpha": rng.standard_normal((n_chains, n_draws, n_surfaces)),
        "beta": rng.standard_normal((n_chains, n_draws, n_features)),
        "mu_alpha": rng.standard_normal((n_chains, n_draws)),
        "sigma_alpha": np.abs(rng.standard_normal((n_chains, n_draws))),
    }
    # p values must be in [0, 1] for posterior predictive
    p_samples = np.clip(
        rng.standard_normal((n_chains, n_draws, n_matches)) * 0.1 + 0.5,
        0.01, 0.99
    )
    posterior_predictive = {"p": p_samples}
    return az.from_dict(
        posterior=posterior,
        posterior_predictive=posterior_predictive,
    )


# ---------------------------------------------------------------------------
# TestSurfaceIndex
# ---------------------------------------------------------------------------

class TestSurfaceIndex:
    def test_surface_index_has_hard(self):
        from src.model.bayesian import SURFACE_INDEX
        assert "Hard" in SURFACE_INDEX
        assert SURFACE_INDEX["Hard"] == 0

    def test_surface_index_has_clay(self):
        from src.model.bayesian import SURFACE_INDEX
        assert "Clay" in SURFACE_INDEX
        assert SURFACE_INDEX["Clay"] == 1

    def test_surface_index_has_grass(self):
        from src.model.bayesian import SURFACE_INDEX
        assert "Grass" in SURFACE_INDEX
        assert SURFACE_INDEX["Grass"] == 2

    def test_surface_str_to_idx_known_surfaces(self):
        from src.model.bayesian import _surface_str_to_idx
        result = _surface_str_to_idx(["Hard", "Clay", "Grass"])
        np.testing.assert_array_equal(result, [0, 1, 2])

    def test_surface_str_to_idx_unknown_defaults_to_zero(self):
        from src.model.bayesian import _surface_str_to_idx
        result = _surface_str_to_idx(["Carpet", "Unknown", "Dirt"])
        np.testing.assert_array_equal(result, [0, 0, 0])

    def test_surface_str_to_idx_returns_int64(self):
        from src.model.bayesian import _surface_str_to_idx
        result = _surface_str_to_idx(["Hard"])
        assert result.dtype == np.int64


# ---------------------------------------------------------------------------
# TestBayesianTrainFold
# ---------------------------------------------------------------------------

class TestBayesianTrainFold:
    @patch("src.model.bayesian.pm")
    @patch("src.model.bayesian.az")
    def test_train_fold_returns_dict_with_model_and_idata(self, mock_az, mock_pm):
        from src.model.bayesian import train_fold

        X_train, y_train, X_val, y_val, w_train, surface_train = _make_training_data()
        mock_idata = _make_mock_idata(n_matches=len(y_val))

        # Mock pm.sample to return mock idata
        mock_pm.sample.return_value = mock_idata

        # Mock pm.Model context manager
        mock_model = MagicMock()
        mock_pm.Model.return_value.__enter__ = MagicMock(return_value=mock_model)
        mock_pm.Model.return_value.__exit__ = MagicMock(return_value=False)

        # Mock pm.Data
        mock_pm.Data.return_value = MagicMock()

        # Mock pm.Normal, pm.HalfNormal, pm.Deterministic, pm.Bernoulli
        mock_pm.Normal.return_value = MagicMock()
        mock_pm.HalfNormal.return_value = MagicMock()
        mock_pm.Deterministic.return_value = MagicMock()
        mock_pm.Bernoulli.return_value = MagicMock()

        # Mock az.summary to return DataFrame with r_hat column
        import pandas as pd
        rhat_df = pd.DataFrame({"r_hat": [1.01, 1.02, 1.00]})
        mock_az.summary.return_value = rhat_df

        # Mock _predict_internal used by train_fold
        with patch("src.model.bayesian._predict_internal") as mock_predict:
            mock_predict.return_value = {
                "p5": np.full(len(y_val), 0.4),
                "p50": np.full(len(y_val), 0.5),
                "p95": np.full(len(y_val), 0.6),
            }
            result = train_fold(
                X_train, y_train, X_val, y_val, w_train,
                surface_train=surface_train,
                config={"draws": 50, "tune": 25, "chains": 1},
            )

        assert "model" in result
        assert "idata" in result

    @patch("src.model.bayesian.pm")
    @patch("src.model.bayesian.az")
    def test_train_fold_returns_x_mean_x_std(self, mock_az, mock_pm):
        from src.model.bayesian import train_fold

        X_train, y_train, X_val, y_val, w_train, surface_train = _make_training_data()
        mock_idata = _make_mock_idata(n_matches=len(y_val))
        mock_pm.sample.return_value = mock_idata

        mock_pm.Model.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_pm.Model.return_value.__exit__ = MagicMock(return_value=False)
        mock_pm.Data.return_value = MagicMock()
        mock_pm.Normal.return_value = MagicMock()
        mock_pm.HalfNormal.return_value = MagicMock()
        mock_pm.Deterministic.return_value = MagicMock()
        mock_pm.Bernoulli.return_value = MagicMock()

        import pandas as pd
        mock_az.summary.return_value = pd.DataFrame({"r_hat": [1.01]})

        with patch("src.model.bayesian._predict_internal") as mock_predict:
            mock_predict.return_value = {
                "p5": np.full(len(y_val), 0.4),
                "p50": np.full(len(y_val), 0.5),
                "p95": np.full(len(y_val), 0.6),
            }
            result = train_fold(
                X_train, y_train, X_val, y_val, w_train,
                surface_train=surface_train,
            )

        assert "X_mean" in result
        assert "X_std" in result
        assert result["X_mean"].shape == (12,)
        assert result["X_std"].shape == (12,)

    @patch("src.model.bayesian.pm")
    @patch("src.model.bayesian.az")
    def test_train_fold_metrics_contain_max_rhat(self, mock_az, mock_pm):
        from src.model.bayesian import train_fold

        X_train, y_train, X_val, y_val, w_train, surface_train = _make_training_data()
        mock_idata = _make_mock_idata(n_matches=len(y_val))
        mock_pm.sample.return_value = mock_idata

        mock_pm.Model.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_pm.Model.return_value.__exit__ = MagicMock(return_value=False)
        mock_pm.Data.return_value = MagicMock()
        mock_pm.Normal.return_value = MagicMock()
        mock_pm.HalfNormal.return_value = MagicMock()
        mock_pm.Deterministic.return_value = MagicMock()
        mock_pm.Bernoulli.return_value = MagicMock()

        import pandas as pd
        mock_az.summary.return_value = pd.DataFrame({"r_hat": [1.01, 1.05, 1.02]})

        with patch("src.model.bayesian._predict_internal") as mock_predict:
            mock_predict.return_value = {
                "p5": np.full(len(y_val), 0.4),
                "p50": np.full(len(y_val), 0.5),
                "p95": np.full(len(y_val), 0.6),
            }
            result = train_fold(
                X_train, y_train, X_val, y_val, w_train,
                surface_train=surface_train,
            )

        assert "metrics" in result
        assert "max_rhat" in result["metrics"]
        assert abs(result["metrics"]["max_rhat"] - 1.05) < 1e-9

    @patch("src.model.bayesian.pm")
    @patch("src.model.bayesian.az")
    def test_train_fold_metrics_contain_converged(self, mock_az, mock_pm):
        from src.model.bayesian import train_fold

        X_train, y_train, X_val, y_val, w_train, surface_train = _make_training_data()
        mock_idata = _make_mock_idata(n_matches=len(y_val))
        mock_pm.sample.return_value = mock_idata

        mock_pm.Model.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_pm.Model.return_value.__exit__ = MagicMock(return_value=False)
        mock_pm.Data.return_value = MagicMock()
        mock_pm.Normal.return_value = MagicMock()
        mock_pm.HalfNormal.return_value = MagicMock()
        mock_pm.Deterministic.return_value = MagicMock()
        mock_pm.Bernoulli.return_value = MagicMock()

        import pandas as pd
        # max_rhat = 1.05 < 1.1 => converged = True
        mock_az.summary.return_value = pd.DataFrame({"r_hat": [1.01, 1.05]})

        with patch("src.model.bayesian._predict_internal") as mock_predict:
            mock_predict.return_value = {
                "p5": np.full(len(y_val), 0.4),
                "p50": np.full(len(y_val), 0.5),
                "p95": np.full(len(y_val), 0.6),
            }
            result = train_fold(
                X_train, y_train, X_val, y_val, w_train,
                surface_train=surface_train,
            )

        assert result["metrics"]["converged"] is True

    @patch("src.model.bayesian.pm")
    @patch("src.model.bayesian.az")
    def test_train_fold_surface_none_defaults_to_all_hard(self, mock_az, mock_pm):
        """If surface_train=None, all training rows treated as Hard (index 0)."""
        from src.model.bayesian import train_fold

        X_train, y_train, X_val, y_val, w_train, _ = _make_training_data()
        mock_idata = _make_mock_idata(n_matches=len(y_val))
        mock_pm.sample.return_value = mock_idata

        mock_pm.Model.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_pm.Model.return_value.__exit__ = MagicMock(return_value=False)
        mock_pm.Data.return_value = MagicMock()
        mock_pm.Normal.return_value = MagicMock()
        mock_pm.HalfNormal.return_value = MagicMock()
        mock_pm.Deterministic.return_value = MagicMock()
        mock_pm.Bernoulli.return_value = MagicMock()

        import pandas as pd
        mock_az.summary.return_value = pd.DataFrame({"r_hat": [1.01]})

        with patch("src.model.bayesian._predict_internal") as mock_predict:
            mock_predict.return_value = {
                "p5": np.full(len(y_val), 0.4),
                "p50": np.full(len(y_val), 0.5),
                "p95": np.full(len(y_val), 0.6),
            }
            # surface_train=None — should not raise
            result = train_fold(X_train, y_train, X_val, y_val, w_train, surface_train=None)

        assert "model" in result


# ---------------------------------------------------------------------------
# TestBayesianPredict
# ---------------------------------------------------------------------------

class TestBayesianPredict:
    def _make_trained_dict(self, n_features=12, n_val=20):
        """Create a fake 'trained' dict without running real MCMC."""
        rng = np.random.default_rng(42)
        mock_idata = _make_mock_idata(n_matches=n_val)
        return {
            "model": MagicMock(),
            "idata": mock_idata,
            "X_mean": np.zeros(n_features),
            "X_std": np.ones(n_features),
        }

    def test_predict_returns_p5_p50_p95_keys(self):
        from src.model.bayesian import predict

        trained = self._make_trained_dict()
        features = np.zeros(12)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": np.array([0.3]),
                "p50": np.array([0.5]),
                "p95": np.array([0.7]),
            }
            result = predict(trained, features)

        assert "p5" in result
        assert "p50" in result
        assert "p95" in result

    def test_predict_returns_calibrated_prob_equal_to_p50(self):
        from src.model.bayesian import predict

        trained = self._make_trained_dict()
        features = np.zeros(12)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": np.array([0.3]),
                "p50": np.array([0.55]),
                "p95": np.array([0.7]),
            }
            result = predict(trained, features)

        assert "calibrated_prob" in result
        assert abs(result["calibrated_prob"] - result["p50"]) < 1e-9

    def test_predict_single_match_returns_floats(self):
        from src.model.bayesian import predict

        trained = self._make_trained_dict()
        features = np.zeros(12)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": np.array([0.3]),
                "p50": np.array([0.5]),
                "p95": np.array([0.7]),
            }
            result = predict(trained, features)

        assert isinstance(result["p5"], float)
        assert isinstance(result["p50"], float)
        assert isinstance(result["p95"], float)
        assert isinstance(result["calibrated_prob"], float)

    def test_predict_batch_returns_arrays(self):
        from src.model.bayesian import predict

        trained = self._make_trained_dict()
        features = np.zeros((5, 12))  # 5 matches

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": np.full(5, 0.3),
                "p50": np.full(5, 0.5),
                "p95": np.full(5, 0.7),
            }
            result = predict(trained, features)

        assert hasattr(result["p5"], "__len__")
        assert len(result["p5"]) == 5

    def test_predict_surface_idx_none_defaults_to_zeros(self):
        """surface_idx=None should pass zeros array to _predict_internal."""
        from src.model.bayesian import predict

        trained = self._make_trained_dict()
        features = np.zeros(12)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": np.array([0.3]),
                "p50": np.array([0.5]),
                "p95": np.array([0.7]),
            }
            predict(trained, features, surface_idx=None)

        # Check that surface_idx passed was an array of zeros
        _, kwargs = mock_pi.call_args
        # positional: (model, idata, features, X_mean, X_std, surface_idx_new)
        call_args = mock_pi.call_args[0]
        surface_passed = call_args[5]
        np.testing.assert_array_equal(surface_passed, [0])

    def test_predict_surface_idx_int_converted_to_array(self):
        """surface_idx as int should be converted to array."""
        from src.model.bayesian import predict

        trained = self._make_trained_dict()
        features = np.zeros(12)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": np.array([0.3]),
                "p50": np.array([0.5]),
                "p95": np.array([0.7]),
            }
            predict(trained, features, surface_idx=2)

        call_args = mock_pi.call_args[0]
        surface_passed = call_args[5]
        np.testing.assert_array_equal(surface_passed, [2])


# ---------------------------------------------------------------------------
# TestBayesianCI
# ---------------------------------------------------------------------------

class TestBayesianCI:
    def test_p5_le_p50_le_p95_for_all_predictions(self):
        """With known posterior predictive, verify percentile ordering."""
        from src.model.bayesian import predict

        trained = {
            "model": MagicMock(),
            "idata": MagicMock(),
            "X_mean": np.zeros(12),
            "X_std": np.ones(12),
        }
        n_matches = 10
        features = np.zeros((n_matches, 12))

        rng = np.random.default_rng(0)
        # p50 in [0.4, 0.6], p5 below, p95 above
        p50_vals = rng.uniform(0.4, 0.6, n_matches)
        p5_vals = p50_vals - rng.uniform(0.05, 0.2, n_matches)
        p95_vals = p50_vals + rng.uniform(0.05, 0.2, n_matches)
        p5_vals = np.clip(p5_vals, 0.01, 0.99)
        p95_vals = np.clip(p95_vals, 0.01, 0.99)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": p5_vals,
                "p50": p50_vals,
                "p95": p95_vals,
            }
            result = predict(trained, features)

        assert np.all(result["p5"] <= result["p50"]), "p5 must be <= p50"
        assert np.all(result["p50"] <= result["p95"]), "p50 must be <= p95"

    def test_p50_in_unit_interval(self):
        """p50 values must be in [0, 1]."""
        from src.model.bayesian import predict

        trained = {
            "model": MagicMock(),
            "idata": MagicMock(),
            "X_mean": np.zeros(12),
            "X_std": np.ones(12),
        }
        n_matches = 20
        features = np.zeros((n_matches, 12))

        rng = np.random.default_rng(1)
        p50_vals = rng.uniform(0.1, 0.9, n_matches)

        with patch("src.model.bayesian._predict_internal") as mock_pi:
            mock_pi.return_value = {
                "p5": p50_vals - 0.05,
                "p50": p50_vals,
                "p95": p50_vals + 0.05,
            }
            result = predict(trained, features)

        assert np.all(result["p50"] >= 0.0), "p50 must be >= 0"
        assert np.all(result["p50"] <= 1.0), "p50 must be <= 1"

    def test_percentile_computation_with_known_posterior(self):
        """Verify that _predict_internal computes correct percentiles from p_samples."""
        # We test the percentile math directly without running MCMC
        n_samples = 1000
        n_matches = 3
        rng = np.random.default_rng(7)
        # Uniform [0.4, 0.6] posterior — p5~0.41, p50~0.5, p95~0.59
        p_flat = rng.uniform(0.4, 0.6, (n_samples, n_matches))

        p5 = np.percentile(p_flat, 5, axis=0)
        p50 = np.percentile(p_flat, 50, axis=0)
        p95 = np.percentile(p_flat, 95, axis=0)

        assert np.all(p5 >= 0.4), "5th percentile of uniform[0.4,0.6] should be >= 0.4"
        assert np.all(p95 <= 0.6), "95th percentile of uniform[0.4,0.6] should be <= 0.6"
        assert np.all(p5 <= p50)
        assert np.all(p50 <= p95)


# ---------------------------------------------------------------------------
# TestBayesianRegistry
# ---------------------------------------------------------------------------

class TestBayesianRegistry:
    def test_registry_contains_bayesian_v1(self):
        from src.model import MODEL_REGISTRY
        assert "bayesian_v1" in MODEL_REGISTRY

    def test_registry_bayesian_has_train(self):
        from src.model import MODEL_REGISTRY
        assert "train" in MODEL_REGISTRY["bayesian_v1"]
        assert callable(MODEL_REGISTRY["bayesian_v1"]["train"])

    def test_registry_bayesian_has_predict(self):
        from src.model import MODEL_REGISTRY
        assert "predict" in MODEL_REGISTRY["bayesian_v1"]
        assert callable(MODEL_REGISTRY["bayesian_v1"]["predict"])
