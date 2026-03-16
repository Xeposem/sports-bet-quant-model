"""
Head-to-head record computation.

TEMPORAL SAFETY: Uses strict less-than on tourney_date to prevent look-ahead bias.
All matches on or after before_date are excluded from the H2H calculation.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


def get_h2h(
    conn: sqlite3.Connection,
    p1_id: int,
    p2_id: int,
    before_date: str,
    surface: Optional[str] = None,
) -> dict:
    """
    Compute the head-to-head record between two players strictly before before_date.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    p1_id : int
        Player 1 ID (perspective player — wins counted for p1).
    p2_id : int
        Player 2 ID (opponent).
    before_date : str
        ISO date string "YYYY-MM-DD". Only matches with tourney_date < before_date
        are included. Strict less-than prevents look-ahead bias.
    surface : str or None
        If provided, filter matches to this surface (e.g., "Hard", "Clay", "Grass").

    Returns
    -------
    dict with keys:
        "p1_wins"   : int — number of matches p1 won against p2
        "p1_losses" : int — number of matches p1 lost to p2
        "total"     : int — total matches between p1 and p2
    """
    if surface is not None:
        sql = """
            SELECT
                SUM(CASE WHEN m.winner_id = :p1 THEN 1 ELSE 0 END) AS p1_wins,
                SUM(CASE WHEN m.winner_id = :p2 THEN 1 ELSE 0 END) AS p1_losses,
                COUNT(*) AS total
            FROM matches m
            JOIN tournaments t USING (tourney_id, tour)
            WHERE m.tourney_date < :date
              AND t.surface = :surface
              AND (
                    (m.winner_id = :p1 AND m.loser_id = :p2)
                 OR (m.winner_id = :p2 AND m.loser_id = :p1)
              )
        """
        params = {"p1": p1_id, "p2": p2_id, "date": before_date, "surface": surface}
    else:
        sql = """
            SELECT
                SUM(CASE WHEN winner_id = :p1 THEN 1 ELSE 0 END) AS p1_wins,
                SUM(CASE WHEN winner_id = :p2 THEN 1 ELSE 0 END) AS p1_losses,
                COUNT(*) AS total
            FROM matches
            WHERE tourney_date < :date
              AND (
                    (winner_id = :p1 AND loser_id = :p2)
                 OR (winner_id = :p2 AND loser_id = :p1)
              )
        """
        params = {"p1": p1_id, "p2": p2_id, "date": before_date}

    row = conn.execute(sql, params).fetchone()
    if row is None or row[2] is None:
        return {"p1_wins": 0, "p1_losses": 0, "total": 0}

    return {
        "p1_wins": int(row[0] or 0),
        "p1_losses": int(row[1] or 0),
        "total": int(row[2] or 0),
    }
