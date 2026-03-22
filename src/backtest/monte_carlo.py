"""
Monte Carlo bankroll simulation and Sharpe ratio computation.

Key exports:
  - run_monte_carlo: Vectorized season resampling from backtest returns
  - compute_sharpe: Annualized Sharpe ratio from per-bet P&L
"""
from __future__ import annotations

import numpy as np


def run_monte_carlo(
    pnl_ratios: np.ndarray,
    n_seasons: int = 1000,
    n_bets_per_season: int = 200,
    initial_bankroll: float = 1000.0,
    seed: int = 42,
) -> dict:
    """
    Run Monte Carlo bankroll simulation.

    Parameters
    ----------
    pnl_ratios : array of per-bet return ratios (pnl_kelly / bankroll_before)
    n_seasons : number of simulated seasons (1000-10000)
    n_bets_per_season : bets per season (derived from annual bet count)
    initial_bankroll : starting bankroll
    seed : RNG seed for reproducibility

    Returns
    -------
    dict with keys: p_ruin, expected_terminal, sharpe_ratio, paths (list of dicts
    with step/p5/p25/p50/p75/p95), terminal_distribution (list of floats)
    """
    rng = np.random.default_rng(seed)
    sampled = rng.choice(pnl_ratios, size=(n_seasons, n_bets_per_season), replace=True)
    compound = np.cumprod(1 + sampled, axis=1) * initial_bankroll
    terminal = compound[:, -1]
    ruin_mask = np.any(compound <= 0, axis=1)
    p_ruin = float(ruin_mask.mean())
    expected_terminal = float(np.mean(terminal))

    # Sharpe from terminal returns
    terminal_returns = (terminal - initial_bankroll) / initial_bankroll
    sharpe = float(np.mean(terminal_returns) / np.std(terminal_returns, ddof=1)) if np.std(terminal_returns, ddof=1) > 0 else 0.0

    # Percentile paths at 20 evenly spaced checkpoints
    n_checkpoints = 20
    checkpoints = np.linspace(0, n_bets_per_season - 1, n_checkpoints, dtype=int)
    paths = []
    for idx, step in enumerate(checkpoints):
        col = compound[:, step]
        paths.append({
            "step": int(idx),
            "p5": float(np.percentile(col, 5)),
            "p25": float(np.percentile(col, 25)),
            "p50": float(np.percentile(col, 50)),
            "p75": float(np.percentile(col, 75)),
            "p95": float(np.percentile(col, 95)),
        })

    return {
        "p_ruin": p_ruin,
        "expected_terminal": expected_terminal,
        "sharpe_ratio": sharpe,
        "paths": paths,
        "terminal_distribution": terminal.tolist(),
    }


def compute_sharpe(
    pnl_values: list[float],
    bankroll_before_values: list[float],
    bets_per_year: float = 200.0,
) -> float:
    """
    Compute annualized Sharpe ratio from per-bet P&L.

    Sharpe = mean(r) / std(r) * sqrt(bets_per_year)
    where r = pnl / bankroll_before for each bet.
    """
    if len(pnl_values) < 2:
        return 0.0
    returns = np.array(pnl_values) / np.array(bankroll_before_values)
    mean_r = float(np.mean(returns))
    std_r = float(np.std(returns, ddof=1))
    if std_r == 0:
        return 0.0
    return float(mean_r / std_r * np.sqrt(bets_per_year))
