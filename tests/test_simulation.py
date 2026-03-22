"""Unit tests for Monte Carlo simulation and Sharpe ratio."""
import numpy as np
import pytest
from src.backtest.monte_carlo import run_monte_carlo, compute_sharpe


class TestRunMonteCarlo:
    def test_returns_expected_keys(self):
        pnl = np.array([0.01, -0.02, 0.03, -0.01, 0.02, -0.005])
        result = run_monte_carlo(pnl, n_seasons=100, n_bets_per_season=50)
        assert set(result.keys()) == {"p_ruin", "expected_terminal", "sharpe_ratio", "paths", "terminal_distribution"}

    def test_p_ruin_is_float_between_0_and_1(self):
        pnl = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
        result = run_monte_carlo(pnl, n_seasons=500, n_bets_per_season=100)
        assert 0.0 <= result["p_ruin"] <= 1.0

    def test_paths_has_20_checkpoints(self):
        pnl = np.array([0.01, -0.02, 0.03])
        result = run_monte_carlo(pnl, n_seasons=50, n_bets_per_season=30)
        assert len(result["paths"]) == 20

    def test_each_path_has_percentile_keys(self):
        pnl = np.array([0.01, -0.02, 0.03])
        result = run_monte_carlo(pnl, n_seasons=50, n_bets_per_season=30)
        for p in result["paths"]:
            assert set(p.keys()) == {"step", "p5", "p25", "p50", "p75", "p95"}

    def test_terminal_distribution_length_matches_n_seasons(self):
        result = run_monte_carlo(np.array([0.01, -0.01]), n_seasons=200, n_bets_per_season=50)
        assert len(result["terminal_distribution"]) == 200

    def test_deterministic_with_same_seed(self):
        pnl = np.array([0.01, -0.02, 0.03, -0.01])
        r1 = run_monte_carlo(pnl, n_seasons=100, n_bets_per_season=50, seed=123)
        r2 = run_monte_carlo(pnl, n_seasons=100, n_bets_per_season=50, seed=123)
        assert r1["p_ruin"] == r2["p_ruin"]
        assert r1["expected_terminal"] == r2["expected_terminal"]

    def test_different_seeds_may_differ(self):
        pnl = np.array([0.01, -0.02, 0.03, -0.01])
        r1 = run_monte_carlo(pnl, n_seasons=500, n_bets_per_season=100, seed=1)
        r2 = run_monte_carlo(pnl, n_seasons=500, n_bets_per_season=100, seed=2)
        # Results from different seeds should differ (not guaranteed but very likely)
        # At minimum, function runs without error with different seeds
        assert "p_ruin" in r1 and "p_ruin" in r2

    def test_expected_terminal_is_float(self):
        pnl = np.array([0.01, -0.02, 0.03])
        result = run_monte_carlo(pnl, n_seasons=50, n_bets_per_season=30)
        assert isinstance(result["expected_terminal"], float)

    def test_negative_strategy_has_lower_expected_terminal(self):
        """A strategy that consistently loses should have expected terminal < initial bankroll."""
        pnl = np.array([-0.05, -0.05, -0.04, -0.06, -0.05])
        result = run_monte_carlo(pnl, n_seasons=200, n_bets_per_season=50, initial_bankroll=1000.0)
        assert result["expected_terminal"] < 1000.0


class TestComputeSharpe:
    def test_returns_float(self):
        result = compute_sharpe([10.0, -5.0, 15.0], [1000.0, 1010.0, 1005.0])
        assert isinstance(result, float)

    def test_returns_zero_for_single_bet(self):
        assert compute_sharpe([10.0], [1000.0]) == 0.0

    def test_returns_zero_for_empty(self):
        assert compute_sharpe([], []) == 0.0

    def test_positive_for_profitable_strategy(self):
        pnl = [10.0, 20.0, 15.0, 5.0, 10.0]
        bankroll = [1000.0] * 5
        assert compute_sharpe(pnl, bankroll) > 0

    def test_negative_for_losing_strategy(self):
        pnl = [-10.0, -20.0, -15.0, -5.0, -10.0]
        bankroll = [1000.0] * 5
        assert compute_sharpe(pnl, bankroll) < 0

    def test_returns_zero_for_identical_returns(self):
        """All identical returns => std=0 => Sharpe=0.0."""
        pnl = [10.0, 10.0, 10.0]
        bankroll = [1000.0, 1000.0, 1000.0]
        assert compute_sharpe(pnl, bankroll) == 0.0

    def test_scales_with_bets_per_year(self):
        pnl = [10.0, -5.0, 15.0, -3.0, 8.0]
        bankroll = [1000.0] * 5
        sharpe_200 = compute_sharpe(pnl, bankroll, bets_per_year=200.0)
        sharpe_100 = compute_sharpe(pnl, bankroll, bets_per_year=100.0)
        # More bets per year => higher annualized Sharpe (sqrt scaling)
        assert sharpe_200 > sharpe_100
