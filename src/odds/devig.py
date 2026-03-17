"""
Power method devigging for two-outcome markets (tennis match).

Algorithm: find exponent k such that r_a^(1/k) + r_b^(1/k) = 1,
where r_i = 1 / decimal_i (naive implied probability).

This distributes the overround proportionally to each outcome's probability —
the standard approach for Pinnacle's pricing model.

Source: implied R package (CRAN) vignette; scipy.optimize.brentq docs.
"""
from scipy.optimize import brentq


_MIN_ODDS = 1.01  # Minimum valid decimal odds (probability < ~0.99)


def power_method_devig(decimal_a: float, decimal_b: float) -> tuple:
    """
    Power method devigging for a two-outcome market.

    Returns (p_a, p_b) where p_a + p_b == 1.0 (within floating point tolerance).
    p_a corresponds to decimal_a, p_b corresponds to decimal_b.

    Args:
        decimal_a: Decimal odds for outcome A (e.g., 1.95). Must be >= 1.01.
        decimal_b: Decimal odds for outcome B (e.g., 1.95). Must be >= 1.01.

    Returns:
        Tuple (p_a, p_b) of devigged true probabilities.

    Raises:
        ValueError: If either odds value is < 1.01 (invalid market).
    """
    if decimal_a < _MIN_ODDS:
        raise ValueError(
            f"decimal_a must be >= {_MIN_ODDS}, got {decimal_a}"
        )
    if decimal_b < _MIN_ODDS:
        raise ValueError(
            f"decimal_b must be >= {_MIN_ODDS}, got {decimal_b}"
        )

    r_a = 1.0 / decimal_a
    r_b = 1.0 / decimal_b

    def objective(k: float) -> float:
        return r_a ** (1.0 / k) + r_b ** (1.0 / k) - 1.0

    # Bracket [0.01, 10.0] is wider than typical [0.5, 2.0] to handle extreme odds.
    # brentq guarantees convergence if a sign change exists in the bracket.
    # For valid odds (sum of 1/d > 1), a solution always exists in this range.
    k = brentq(objective, 0.01, 10.0, xtol=1e-10)

    p_a = r_a ** (1.0 / k)
    p_b = r_b ** (1.0 / k)
    return p_a, p_b
