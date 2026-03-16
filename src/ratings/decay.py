"""
Surface-specific inactivity rating decay toward mean.

Tennis players may be inactive on certain surfaces for extended periods
(e.g., grass courts for most of the year). This module applies a gentle
multiplicative decay toward the mean rating after surface-specific
inactivity thresholds are exceeded.

Decay mechanism:
  1. Glicko-2 RD growth handles uncertainty increase (via did_not_compete).
  2. This module applies an *additional* mean-reversion to the rating itself.

Thresholds are aligned with the ATP seasonal calendar:
  - Hard:  3 months  (90 days)  — played year-round
  - Clay:  6 months  (180 days) — European clay season
  - Grass: 11 months (330 days) — short Wimbledon window

Usage:
    from src.ratings.decay import apply_decay_if_needed, SURFACE_THRESHOLDS
    new_rating = apply_decay_if_needed(current_rating, "Hard", days_inactive)
"""

# Surface-specific inactivity thresholds in days
SURFACE_THRESHOLDS: dict[str, int] = {
    "Hard": 90,
    "Clay": 180,
    "Grass": 330,
}

# Mean rating toward which ratings decay
MEAN_RATING: float = 1500.0

# Decay rate per full month (30 days) over the threshold
DECAY_PER_MONTH: float = 0.025  # 2.5%


def apply_decay_if_needed(
    player_rating: float,
    surface: str,
    days_inactive: int,
) -> float:
    """
    Apply mean-reversion decay if the player has been inactive beyond the
    surface-specific threshold.

    The decay formula is multiplicative:
        gap = player_rating - MEAN_RATING
        decayed_gap = gap * (1 - DECAY_PER_MONTH) ** months_over_threshold
        new_rating = MEAN_RATING + decayed_gap

    This ensures ratings move toward 1500 but never cross it (assuming the
    rating started above 1500; players below 1500 move up toward it).

    Parameters
    ----------
    player_rating : float
        Current Glicko-2 rating.
    surface : str
        Surface name ('Hard', 'Clay', 'Grass', or 'Overall').
        'Overall' uses the Hard threshold as a proxy.
    days_inactive : int
        Number of days since the player last competed on this surface.

    Returns
    -------
    float
        Decayed (or unchanged) rating.
    """
    threshold = SURFACE_THRESHOLDS.get(surface, SURFACE_THRESHOLDS["Hard"])

    if days_inactive <= threshold:
        return player_rating

    days_over = days_inactive - threshold
    months_over = days_over / 30.0

    gap = player_rating - MEAN_RATING
    decayed_gap = gap * (1.0 - DECAY_PER_MONTH) ** months_over

    return MEAN_RATING + decayed_gap
