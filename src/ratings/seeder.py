"""
Rank-based initial Glicko-2 rating seeder.

Maps ATP ranking to an initial Glicko-2 rating using a piecewise logarithmic
curve anchored at three key reference points:
  - Rank 1   -> ~1800  (elite)
  - Rank 100 -> ~1500  (mid-field anchor)
  - Rank 300 -> ~1350  (lower tier / clamp boundary)

Fallback: 1500.0 when rank is None or <= 0.

Usage:
    from src.ratings.seeder import seed_rating_from_rank
    initial_rating = seed_rating_from_rank(player_rank)
"""

import math


# Rating boundaries
_RATING_TOP = 1800.0    # rank 1
_RATING_MID = 1500.0    # rank 100 (anchor)
_RATING_BOT = 1350.0    # rank 300
_RANK_TOP = 1           # anchor: top
_RANK_MID = 100         # anchor: mid
_RANK_MAX = 300         # clamp boundary


def seed_rating_from_rank(rank: "int | None") -> float:
    """
    Return an initial Glicko-2 rating based on ATP ranking.

    Uses a piecewise logarithmic interpolation:
    - Ranks 1–100: interpolates from 1800 to 1500 using log(rank)/log(100)
    - Ranks 100–300: interpolates from 1500 to 1350 using log(rank/100)/log(3)
    - Ranks > 300: clamped to 1350

    Parameters
    ----------
    rank : int or None
        Current ATP ranking. None or <= 0 returns the default 1500.0.

    Returns
    -------
    float
        Initial Glicko-2 rating in the range [1350.0, 1800.0].
    """
    if rank is None or rank <= 0:
        return 1500.0

    if rank <= 1:
        return _RATING_TOP

    if rank <= _RANK_MID:
        # Segment 1: rank 1 to 100, log(1)=0 to log(100)
        # t=0 at rank 1 -> 1800, t=1 at rank 100 -> 1500
        t = math.log(rank) / math.log(_RANK_MID)
        return _RATING_TOP + t * (_RATING_MID - _RATING_TOP)

    # Segment 2: rank 100 to 300+
    # Clamp at 300
    rank = min(rank, _RANK_MAX)
    # t=0 at rank 100 -> 1500, t=1 at rank 300 -> 1350
    t = math.log(rank / _RANK_MID) / math.log(_RANK_MAX / _RANK_MID)
    return _RATING_MID + t * (_RATING_BOT - _RATING_MID)
