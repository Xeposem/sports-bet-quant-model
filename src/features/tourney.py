"""
Tournament level ordinal encoding.

Mapping follows ATP tournament hierarchy:
  G (Grand Slam)   -> 4  highest prestige
  M (Masters 1000) -> 3
  A (ATP 500)      -> 2
  F (Tour Finals)  -> 2  same prestige tier as ATP 500 for model purposes
  D (Davis Cup)    -> 1
  C (Challenger)   -> 1
  Unknown / None   -> 0
"""
from __future__ import annotations

from typing import Optional

_LEVEL_MAP: dict[str, int] = {
    "G": 4,  # Grand Slam
    "M": 3,  # Masters 1000
    "A": 2,  # ATP 500
    "F": 2,  # Tour Finals
    "D": 1,  # Davis Cup
    "C": 1,  # Challenger
}


def encode_tourney_level(level: Optional[str]) -> int:
    """
    Encode tournament level as an ordinal integer.

    Parameters
    ----------
    level : str or None
        Single-character ATP tournament level code, or None.

    Returns
    -------
    int
        Ordinal encoding (0 for unknown or None).
    """
    if level is None:
        return 0
    return _LEVEL_MAP.get(level, 0)
