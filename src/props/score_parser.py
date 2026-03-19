"""Score parser for Sackmann tennis score strings.

Extracts (winner_games, loser_games) from standard ATP score strings.
Returns None for retirements, walkovers, defaults, and invalid/empty inputs.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_SET_PATTERN = re.compile(r"(\d+)-(\d+)(?:\(\d+\))?")


def parse_score(score: str) -> Optional[Tuple[int, int]]:
    """
    Parse a Sackmann score string and return (winner_games, loser_games).

    Parameters
    ----------
    score : str or None
        ATP score string, e.g. "6-3 7-5", "6-3 6-4 7-6(5)", "6-3 4-2 RET".

    Returns
    -------
    tuple of (int, int) or None
        (winner_total_games, loser_total_games) if the match completed normally.
        None if the match was a retirement, walkover, default, or invalid.

    Examples
    --------
    >>> parse_score("6-3 7-5")
    (13, 8)
    >>> parse_score("6-3 6-4 7-6(5)")
    (19, 13)
    >>> parse_score("6-3 4-2 RET")
    None
    >>> parse_score("W/O")
    None
    """
    if not score:
        return None

    score_upper = score.strip().upper()

    # Return None for retirements, walkovers, defaults
    if "RET" in score_upper or score_upper == "W/O" or score_upper == "DEF":
        return None

    sets = _SET_PATTERN.findall(score)
    if not sets:
        return None

    winner_games = sum(int(w) for w, l in sets)
    loser_games = sum(int(l) for w, l in sets)
    return (winner_games, loser_games)
