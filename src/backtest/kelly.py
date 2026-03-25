"""
Kelly bet sizing module for walk-forward backtesting.

Implements fractional Kelly criterion with cap enforcement and minimum EV threshold.

Key exports:
  - compute_kelly_bet: Compute fractional Kelly bet size with cap
  - apply_bet_result: Update bankroll after bet resolution
"""

from __future__ import annotations

from typing import Optional


def compute_kelly_bet(
    prob: float,
    decimal_odds: float,
    bankroll: float,
    kelly_fraction: float = 0.25,
    max_fraction: float = 0.03,
    min_ev: float = 0.0,
    clv_threshold: float = 0.0,
    pinnacle_prob: Optional[float] = None,
    has_no_pinnacle: int = 1,
) -> float:
    """
    Compute fractional Kelly bet size with cap enforcement.

    Steps:
    1. CLV gate: if Pinnacle data available and threshold > 0, require
       model_prob - pinnacle_prob > clv_threshold (D-01, D-02, D-03).
    2. Compute EV = (prob * decimal_odds) - 1. If EV < min_ev, return 0.
    3. Compute full Kelly = (b*p - q) / b where b = decimal_odds - 1.
    4. If full_kelly <= 0, return 0 (negative Kelly = no edge).
    5. Apply fraction: fractional = full_kelly * kelly_fraction.
    6. Cap: min(fractional * bankroll, max_fraction * bankroll).

    Parameters
    ----------
    prob:
        Calibrated model probability for the outcome (0, 1).
    decimal_odds:
        Bookmaker decimal odds (e.g., 2.10).
    bankroll:
        Current bankroll value.
    kelly_fraction:
        Fractional Kelly multiplier (default 0.25 = quarter Kelly).
    max_fraction:
        Maximum fraction of bankroll to risk per bet (default 0.03 = 3%).
    min_ev:
        Minimum EV threshold. Bets with EV < min_ev are skipped (default 0.0).
    clv_threshold:
        Minimum CLV (model_prob - pinnacle_prob) required to place bet (default 0.0
        = no CLV filtering). Low-level default is 0.0 for backward compatibility;
        CLI and API entry points default to 0.03 per D-04.
    pinnacle_prob:
        Pinnacle devigged market probability for this outcome. Required when
        has_no_pinnacle=0 and clv_threshold > 0.
    has_no_pinnacle:
        1 if no Pinnacle data for this match (pre-Pinnacle era), 0 if available.
        When 1, CLV gate is bypassed entirely (D-03).

    Returns
    -------
    float: Bet size in bankroll units. 0.0 if no bet.
    """
    # CLV gate: only when Pinnacle data available and threshold > 0 (D-01, D-02, D-03)
    if has_no_pinnacle == 0 and clv_threshold > 0.0 and pinnacle_prob is not None:
        clv = prob - pinnacle_prob
        if clv <= clv_threshold:
            return 0.0

    # Step 1: EV check
    ev = float(prob * decimal_odds) - 1.0
    if ev < min_ev:
        return 0.0

    # Step 2: Full Kelly fraction
    b = decimal_odds - 1.0  # net odds (profit per unit staked)
    p = prob
    q = 1.0 - prob
    full_kelly = (b * p - q) / b

    # Step 3: Skip negative Kelly
    if full_kelly <= 0.0:
        return 0.0

    # Step 4: Apply fraction
    fractional = full_kelly * kelly_fraction

    # Step 5: Cap at max_fraction of bankroll
    bet = min(fractional * bankroll, max_fraction * bankroll)
    return float(bet)


def apply_bet_result(
    bankroll: float,
    bet_size: float,
    decimal_odds: float,
    won: bool,
) -> float:
    """
    Update bankroll after bet resolution.

    If won: bankroll + bet_size * (decimal_odds - 1)
    If lost: bankroll - bet_size

    Parameters
    ----------
    bankroll:
        Bankroll before the bet.
    bet_size:
        Amount staked.
    decimal_odds:
        Decimal odds at which the bet was placed.
    won:
        True if the bet won, False if lost.

    Returns
    -------
    float: Updated bankroll.
    """
    if won:
        return float(bankroll + bet_size * (decimal_odds - 1.0))
    else:
        return float(bankroll - bet_size)
