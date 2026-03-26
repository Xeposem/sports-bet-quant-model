"""Score parser for Sackmann tennis score strings.

Extracts (winner_games, loser_games) from standard ATP score strings.
Returns None for retirements, walkovers, defaults, and invalid/empty inputs.

Also provides:
  - parse_sets: returns (winner_sets, loser_sets) set counts
  - parse_first_set_winner: returns 1 if match winner won set 1, 0 if match loser did
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_SET_PATTERN = re.compile(r"(\d+)-(\d+)(?:\(\d+\))?")


def _is_invalid(score: str) -> bool:
    """Return True if score represents a retirement, walkover, default, or is empty."""
    if not score:
        return True
    score_upper = score.strip().upper()
    return "RET" in score_upper or score_upper in ("W/O", "DEF")


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
    if _is_invalid(score):
        return None

    sets = _SET_PATTERN.findall(score)
    if not sets:
        return None

    winner_games = sum(int(w) for w, l in sets)
    loser_games = sum(int(l) for w, l in sets)
    return (winner_games, loser_games)


def parse_sets(score: str) -> Optional[Tuple[int, int]]:
    """
    Parse a Sackmann score string and return (winner_sets, loser_sets).

    Parameters
    ----------
    score : str or None
        ATP score string, e.g. "6-3 7-5", "7-6(5) 3-6 6-4".

    Returns
    -------
    tuple of (int, int) or None
        (winner_sets_won, loser_sets_won) if valid completed match.
        None if retirement, walkover, default, or invalid.

    Examples
    --------
    >>> parse_sets("6-3 7-5")
    (2, 0)
    >>> parse_sets("7-6(5) 3-6 6-4")
    (2, 1)
    >>> parse_sets("RET")
    None
    """
    if _is_invalid(score):
        return None

    sets = _SET_PATTERN.findall(score)
    if not sets:
        return None

    winner_sets = sum(1 for w, l in sets if int(w) > int(l))
    loser_sets = sum(1 for w, l in sets if int(l) > int(w))
    return (winner_sets, loser_sets)


def parse_first_set_winner(score: str) -> Optional[int]:
    """
    Return 1 if the match winner won set 1, 0 if the match loser won set 1.

    Parameters
    ----------
    score : str or None
        ATP score string.

    Returns
    -------
    int or None
        1 if match winner won the first set,
        0 if match loser won the first set,
        None if retirement, walkover, default, or invalid.

    Examples
    --------
    >>> parse_first_set_winner("6-3 7-5")
    1
    >>> parse_first_set_winner("3-6 7-5 6-3")
    0
    """
    if _is_invalid(score):
        return None

    sets = _SET_PATTERN.findall(score)
    if not sets:
        return None

    w, l = int(sets[0][0]), int(sets[0][1])
    if w > l:
        return 1  # match winner won first set
    elif l > w:
        return 0  # match loser won first set
    return None  # tied set (should not occur in valid ATP matches)
