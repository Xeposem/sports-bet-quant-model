"""
Prop prediction resolver — updates actual_value for predictions where match data is available.

Resolves all 6 stat types:
  - aces: joins match_stats on player_id + match_date, reads ace column
  - double_faults: joins match_stats, reads df column
  - games_won: parses score from matches, winner/loser perspective
  - breaks_of_serve: joins match_stats, computes bp_faced - bp_saved
  - sets_won: parses score from matches via parse_sets(), winner/loser perspective
  - first_set_winner: parses score from matches via parse_first_set_winner(), flipped for loser

Exports:
  - resolve_props(conn) -> dict  {"resolved": int, "skipped": int}
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.props.score_parser import parse_score, parse_sets, parse_first_set_winner

logger = logging.getLogger(__name__)


def resolve_props(conn) -> dict:
    """
    Update actual_value for all unresolved prop_predictions where match data exists.

    For aces and double_faults: joins match_stats on player_id (via matches) + match_date.
    For games_won: parses score from matches table, uses winner/loser role to determine games.
    For breaks_of_serve: joins match_stats, computes bp_faced - bp_saved.
    For sets_won: parses score via parse_sets(), winner/loser perspective.
    For first_set_winner: parses score via parse_first_set_winner(), flipped for loser role.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection with prop_predictions, match_stats, and matches tables.

    Returns
    -------
    dict
        {"resolved": int, "skipped": int}
    """
    resolved = 0
    skipped = 0
    resolved_at = datetime.utcnow().isoformat()

    # Fetch all unresolved predictions
    unresolved = conn.execute("""
        SELECT id, player_id, stat_type, match_date
        FROM prop_predictions
        WHERE actual_value IS NULL
    """).fetchall()

    for pred in unresolved:
        pred_id = pred["id"]
        player_id = pred["player_id"]
        stat_type = pred["stat_type"]
        match_date = pred["match_date"]

        actual_value = None

        if stat_type in ("aces", "double_faults"):
            # Join match_stats on player_id + match_date
            # match_stats uses player_role not player_id; join through matches to get winner_id/loser_id
            stat_col = "ace" if stat_type == "aces" else "df"
            row = conn.execute(f"""
                SELECT ms.{stat_col} AS stat_value
                FROM match_stats ms
                JOIN matches m
                  ON ms.tourney_id = m.tourney_id
                  AND ms.match_num = m.match_num
                  AND ms.tour = m.tour
                WHERE m.tourney_date = ?
                  AND (
                    (ms.player_role = 'winner' AND m.winner_id = ?)
                    OR
                    (ms.player_role = 'loser' AND m.loser_id = ?)
                  )
                LIMIT 1
            """, (match_date, player_id, player_id)).fetchone()

            if row is not None and row["stat_value"] is not None:
                actual_value = int(row["stat_value"])

        elif stat_type == "games_won":
            # Parse score from matches, determine player's role, get correct game count
            row = conn.execute("""
                SELECT m.score, m.winner_id, m.loser_id
                FROM matches m
                WHERE m.tourney_date = ?
                  AND (m.winner_id = ? OR m.loser_id = ?)
                LIMIT 1
            """, (match_date, player_id, player_id)).fetchone()

            if row is not None and row["score"] is not None:
                parsed = parse_score(row["score"])
                if parsed is not None:
                    winner_games, loser_games = parsed
                    if row["winner_id"] == player_id:
                        actual_value = winner_games
                    else:
                        actual_value = loser_games

        elif stat_type == "breaks_of_serve":
            # Compute bp_faced - bp_saved from match_stats for the player
            row = conn.execute("""
                SELECT (ms.bp_faced - COALESCE(ms.bp_saved, 0)) AS stat_value
                FROM match_stats ms
                JOIN matches m
                  ON ms.tourney_id = m.tourney_id
                  AND ms.match_num = m.match_num
                  AND ms.tour = m.tour
                WHERE m.tourney_date = ?
                  AND (
                    (ms.player_role = 'winner' AND m.winner_id = ?)
                    OR
                    (ms.player_role = 'loser' AND m.loser_id = ?)
                  )
                LIMIT 1
            """, (match_date, player_id, player_id)).fetchone()

            if row is not None and row["stat_value"] is not None:
                actual_value = max(0, int(row["stat_value"]))

        elif stat_type == "sets_won":
            # Parse score from matches, determine sets won by player
            row = conn.execute("""
                SELECT m.score, m.winner_id
                FROM matches m
                WHERE m.tourney_date = ?
                  AND (m.winner_id = ? OR m.loser_id = ?)
                LIMIT 1
            """, (match_date, player_id, player_id)).fetchone()

            if row is not None and row["score"] is not None:
                parsed = parse_sets(row["score"])
                if parsed is not None:
                    winner_sets, loser_sets = parsed
                    if row["winner_id"] == player_id:
                        actual_value = winner_sets
                    else:
                        actual_value = loser_sets

        elif stat_type == "first_set_winner":
            # Parse score from matches; result=1 means match winner won set 1
            row = conn.execute("""
                SELECT m.score, m.winner_id
                FROM matches m
                WHERE m.tourney_date = ?
                  AND (m.winner_id = ? OR m.loser_id = ?)
                LIMIT 1
            """, (match_date, player_id, player_id)).fetchone()

            if row is not None and row["score"] is not None:
                parsed = parse_first_set_winner(row["score"])
                if parsed is not None:
                    # parsed=1 means match winner won set 1
                    if row["winner_id"] == player_id:
                        actual_value = parsed          # winner perspective: direct
                    else:
                        actual_value = 1 - parsed      # loser perspective: flip

        if actual_value is not None:
            conn.execute(
                "UPDATE prop_predictions SET actual_value = ?, resolved_at = ? WHERE id = ?",
                (actual_value, resolved_at, pred_id),
            )
            resolved += 1
            logger.debug("resolve_props: resolved prediction id=%d stat=%s value=%d", pred_id, stat_type, actual_value)
        else:
            skipped += 1
            logger.debug("resolve_props: skipped prediction id=%d stat=%s (no match data)", pred_id, stat_type)

    conn.commit()
    logger.info("resolve_props: resolved=%d skipped=%d", resolved, skipped)
    return {"resolved": resolved, "skipped": skipped}
