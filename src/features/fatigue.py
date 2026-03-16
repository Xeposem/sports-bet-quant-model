"""
Fatigue and scheduling feature computation.

TEMPORAL SAFETY: All queries use tourney_date < match_date (strict less-than)
to prevent look-ahead bias. The 7-day window uses [match_date - 7 days, match_date).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Optional


def _count_sets_in_score(score: Optional[str]) -> int:
    """
    Parse a match score string and count the number of sets played.

    Counting strategy: each set result is separated by spaces; sets contain
    a hyphen between game counts (e.g., "6-3"). Tiebreak annotations like
    "(7)" are stripped. Special scores (W/O, DEF, RET-only) return 0.

    Examples
    --------
    "6-3 6-4"       -> 2
    "6-4 3-6 6-2"   -> 3
    "6-3 6-4 RET"   -> 2  (incomplete set not counted separately)
    "W/O"           -> 0
    """
    if not score:
        return 0
    parts = score.strip().split()
    set_count = 0
    for part in parts:
        # Strip tiebreak annotation, e.g. "7-6(5)" -> "7-6"
        clean = part.split("(")[0]
        if "-" in clean:
            try:
                left, right = clean.split("-", 1)
                int(left)
                int(right)
                set_count += 1
            except ValueError:
                pass
    return set_count


def get_fatigue_features(
    conn: sqlite3.Connection,
    player_id: int,
    match_date: str,
) -> dict:
    """
    Compute fatigue and scheduling features for a player before a given match.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    player_id : int
        The player whose fatigue to compute.
    match_date : str
        ISO date string "YYYY-MM-DD" of the upcoming match (exclusive).

    Returns
    -------
    dict with keys:
        "days_since_last"  : int or None — days since the player's last match,
                             None if the player has no prior matches
        "sets_last_7_days" : int — total sets played in the 7 days before match_date
                             (inclusive of the boundary 7 days ago)
    """
    match_dt = date.fromisoformat(match_date)
    window_start = (match_dt - timedelta(days=7)).isoformat()

    # Last match before match_date
    last_match_sql = """
        SELECT tourney_date
        FROM matches
        WHERE (winner_id = :pid OR loser_id = :pid)
          AND tourney_date < :match_date
        ORDER BY tourney_date DESC
        LIMIT 1
    """
    last_row = conn.execute(
        last_match_sql, {"pid": player_id, "match_date": match_date}
    ).fetchone()

    days_since_last: Optional[int] = None
    if last_row is not None:
        last_dt = date.fromisoformat(last_row[0])
        days_since_last = (match_dt - last_dt).days

    # Sets in last 7 days: matches in [match_date - 7 days, match_date)
    sets_sql = """
        SELECT score
        FROM matches
        WHERE (winner_id = :pid OR loser_id = :pid)
          AND tourney_date >= :window_start
          AND tourney_date < :match_date
    """
    rows = conn.execute(
        sets_sql, {"pid": player_id, "window_start": window_start, "match_date": match_date}
    ).fetchall()

    sets_last_7_days = sum(_count_sets_in_score(row[0]) for row in rows)

    return {
        "days_since_last": days_since_last,
        "sets_last_7_days": sets_last_7_days,
    }
