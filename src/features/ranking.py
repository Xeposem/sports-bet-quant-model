"""
Ranking and ranking delta feature computation.

TEMPORAL SAFETY: Uses ranking_date <= before_date (not strictly less-than) so that
the ranking published on the match date is available, consistent with real-world
ATP practice where weekly rankings are published before matches are played.
Delta = previous_ranking - current_ranking (positive = improved = rank number decreased).
"""
from __future__ import annotations

import sqlite3
from typing import Optional


def get_ranking_features(
    conn: sqlite3.Connection,
    player_id: int,
    before_date: str,
) -> dict:
    """
    Retrieve the most recent pre-match ranking and compute the ranking delta.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    player_id : int
        The player whose ranking to look up.
    before_date : str
        ISO date string "YYYY-MM-DD". Only rankings with ranking_date <= before_date
        are considered (weekly rankings published before the match).

    Returns
    -------
    dict with keys:
        "ranking"       : int or None — most recent ranking, None if no data
        "ranking_delta" : int or None — previous_ranking - current_ranking (positive = improved),
                          None if fewer than two prior ranking snapshots exist
    """
    sql = """
        SELECT ranking
        FROM rankings
        WHERE player_id = :pid
          AND ranking_date <= :date
          AND tour = 'ATP'
        ORDER BY ranking_date DESC
        LIMIT 2
    """
    rows = conn.execute(sql, {"pid": player_id, "date": before_date}).fetchall()

    if not rows:
        return {"ranking": None, "ranking_delta": None}

    current_ranking: int = rows[0][0]
    ranking_delta: Optional[int] = None

    if len(rows) >= 2:
        previous_ranking: int = rows[1][0]
        ranking_delta = previous_ranking - current_ranking  # positive = improved

    return {"ranking": current_ranking, "ranking_delta": ranking_delta}
