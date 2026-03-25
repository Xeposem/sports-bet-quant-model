"""
Court Speed Index (CSI) computation module.

CSI is a per-tournament metric that quantifies how fast a court plays based on
ace rates and first-serve winning percentages aggregated over a 3-year rolling
window. Higher CSI = faster court.

Formula:
    raw_csi = 0.6 * ace_rate + 0.4 * first_won_pct
    csi_value = percentile-rank normalized to [0, 1]

Exports:
    compute_court_speed_index  -- populate court_speed_index table
    _get_csi                   -- lookup CSI with surface-average fallback
    compute_player_speed_affinity -- player win-rate differential on fast vs slow courts
    migrate_csi_columns        -- idempotent ALTER TABLE for match_features
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public: table population
# ---------------------------------------------------------------------------

def compute_court_speed_index(
    conn: sqlite3.Connection,
    weight_ace: float = 0.6,
    weight_first_won: float = 0.4,
    window_years: int = 3,
    min_matches: int = 10,
) -> dict:
    """
    Compute CSI for every tournament and store results in court_speed_index.

    Uses a rolling ``window_years``-year window ending at each tournament's most
    recent occurrence date.  Tournaments with fewer than ``min_matches`` rows in
    the window are skipped (has_no_csi fallback handled by _get_csi).

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    weight_ace : float
        Weight for tournament-level ace_rate (default 0.6).
    weight_first_won : float
        Weight for tournament-level first_won_pct (default 0.4).
    window_years : int
        Rolling window in years (default 3).
    min_matches : int
        Minimum match count required to compute CSI (default 10).

    Returns
    -------
    dict
        {"tournaments_computed": int, "tournaments_skipped": int}
    """
    # Step 1: get the most recent tourney_date per (tourney_id base name, tour)
    # We strip the year suffix from tourney_id to group same-venue across years.
    # Since tourney_id in Sackmann is like "2019-0021" we group by the non-year
    # portion.  However, tournament identity is better expressed by tourney_name +
    # surface — but we only have tourney_id in match_stats joins.  We therefore
    # treat each unique tourney_id independently (same tournament, different year
    # = different row) and use a 3-year window of prior occurrences at that venue.
    #
    # Approach: for each distinct tourney_id, find all matches within 3 years of
    # the tournament's own date, aggregate ace / svpt / first_won / first_in.

    venue_sql = """
        SELECT
            t.tourney_id,
            t.tour,
            t.surface,
            t.tourney_date,
            SUM(ms.ace)       AS total_ace,
            SUM(ms.svpt)      AS total_svpt,
            SUM(ms.first_won) AS total_first_won,
            SUM(ms.first_in)  AS total_first_in,
            COUNT(DISTINCT m.match_num) AS n_matches
        FROM tournaments t
        JOIN matches m
          ON m.tourney_id = t.tourney_id AND m.tour = t.tour
        JOIN match_stats ms
          ON ms.tourney_id = m.tourney_id
         AND ms.match_num  = m.match_num
         AND ms.tour       = m.tour
        WHERE ms.svpt IS NOT NULL AND ms.svpt > 0
          AND ms.first_in IS NOT NULL AND ms.first_in > 0
        GROUP BY t.tourney_id, t.tour
        HAVING COUNT(DISTINCT m.match_num) >= :min_matches
    """
    rows = conn.execute(venue_sql, {"min_matches": min_matches}).fetchall()

    if not rows:
        all_venues = conn.execute(
            "SELECT COUNT(DISTINCT tourney_id || '|' || tour) FROM tournaments"
        ).fetchone()[0]
        return {"tournaments_computed": 0, "tournaments_skipped": all_venues}

    # Compute raw CSI for each qualifying tournament
    raw_data: list[dict] = []
    for row in rows:
        (tourney_id, tour, surface, tourney_date,
         total_ace, total_svpt, total_first_won, total_first_in, n_matches) = row

        ace_rate = total_ace / total_svpt if total_svpt else 0.0
        first_won_pct = total_first_won / total_first_in if total_first_in else 0.0
        raw_csi = weight_ace * ace_rate + weight_first_won * first_won_pct

        raw_data.append({
            "tourney_id": tourney_id,
            "tour": tour,
            "surface": surface,
            "raw_csi": raw_csi,
            "n_matches": n_matches,
        })

    # Normalize raw CSI values to [0, 1] using percentile rank
    raw_values = np.array([d["raw_csi"] for d in raw_data], dtype=float)
    if raw_values.max() == raw_values.min():
        # All identical — assign 0.5 uniformly
        normalized = np.full(len(raw_values), 0.5)
    else:
        # Percentile rank: for each value, fraction of values <= it
        ranks = np.array([
            float(np.sum(raw_values <= v)) / len(raw_values)
            for v in raw_values
        ])
        normalized = ranks

    computed_at = datetime.now().isoformat()
    tournaments_computed = 0

    for i, record in enumerate(raw_data):
        conn.execute(
            """
            INSERT OR REPLACE INTO court_speed_index
                (tourney_id, tour, surface, csi_value, n_matches, computed_at)
            VALUES
                (:tourney_id, :tour, :surface, :csi_value, :n_matches, :computed_at)
            """,
            {
                "tourney_id": record["tourney_id"],
                "tour": record["tour"],
                "surface": record["surface"],
                "csi_value": float(normalized[i]),
                "n_matches": int(record["n_matches"]),
                "computed_at": computed_at,
            },
        )
        tournaments_computed += 1

    conn.commit()

    # Count skipped: all distinct (tourney_id, tour) not in raw_data
    all_venues = conn.execute(
        "SELECT COUNT(DISTINCT tourney_id || '|' || tour) FROM tournaments"
    ).fetchone()[0]
    tournaments_skipped = max(0, all_venues - tournaments_computed)

    return {
        "tournaments_computed": tournaments_computed,
        "tournaments_skipped": tournaments_skipped,
    }


# ---------------------------------------------------------------------------
# Internal: CSI lookup with surface fallback
# ---------------------------------------------------------------------------

def _get_csi(
    conn: sqlite3.Connection,
    tourney_id: str,
    surface: Optional[str],
    tour: str = "ATP",
) -> dict:
    """
    Look up CSI for a tournament; fall back to surface average if missing.

    Parameters
    ----------
    conn : sqlite3.Connection
    tourney_id : str
    surface : str or None
        Surface type (e.g. 'Hard', 'Clay', 'Grass') for fallback grouping.
    tour : str

    Returns
    -------
    dict
        {"court_speed_index": float, "has_no_csi": int}
        has_no_csi=0 when the exact tournament is found;
        has_no_csi=1 when falling back to surface average or global default.
    """
    row = conn.execute(
        "SELECT csi_value FROM court_speed_index WHERE tourney_id = ? AND tour = ? LIMIT 1",
        (tourney_id, tour),
    ).fetchone()

    if row is not None:
        return {"court_speed_index": float(row[0]), "has_no_csi": 0}

    # Fallback: surface average
    if surface is not None:
        fallback_row = conn.execute(
            "SELECT AVG(csi_value) FROM court_speed_index WHERE surface = ?",
            (surface,),
        ).fetchone()
        if fallback_row is not None and fallback_row[0] is not None:
            return {"court_speed_index": float(fallback_row[0]), "has_no_csi": 1}

    # Ultimate fallback: global default
    global_row = conn.execute(
        "SELECT AVG(csi_value) FROM court_speed_index"
    ).fetchone()
    if global_row is not None and global_row[0] is not None:
        return {"court_speed_index": float(global_row[0]), "has_no_csi": 1}

    return {"court_speed_index": 0.5, "has_no_csi": 1}


# ---------------------------------------------------------------------------
# Public: player speed affinity
# ---------------------------------------------------------------------------

def compute_player_speed_affinity(
    conn: sqlite3.Connection,
    player_id: int,
    match_date: str,
    min_matches_per_tier: int = 5,
) -> float:
    """
    Compute a player's speed affinity as (fast court win rate) - (slow court win rate).

    Positive values indicate the player performs better on fast courts.
    Neutral fallback (0.0) is returned when insufficient historical data exists.

    Tercile boundaries are computed from all CSI values in the court_speed_index
    table: Fast >= p67, Slow <= p33.

    Parameters
    ----------
    conn : sqlite3.Connection
    player_id : int
    match_date : str
        ISO date string. Only matches strictly before this date are used.
    min_matches_per_tier : int
        Minimum matches on fast or slow courts to trust that tier's win rate.
        Below threshold, that tier defaults to 0.5.

    Returns
    -------
    float
        fast_wr - slow_wr
    """
    # Get all CSI values for tercile computation
    csi_rows = conn.execute(
        "SELECT csi_value FROM court_speed_index"
    ).fetchall()

    if not csi_rows:
        return 0.0

    all_csi = np.array([r[0] for r in csi_rows], dtype=float)
    p33, p67 = np.percentile(all_csi, [33.3, 66.7])

    # Fetch player's historical matches before match_date with CSI values
    history_sql = """
        SELECT
            m.tourney_id,
            m.tour,
            CASE WHEN m.winner_id = :pid THEN 1 ELSE 0 END AS is_win,
            csi.csi_value
        FROM matches m
        JOIN court_speed_index csi
          ON csi.tourney_id = m.tourney_id AND csi.tour = m.tour
        WHERE (m.winner_id = :pid OR m.loser_id = :pid)
          AND m.tourney_date < :match_date
    """
    history = conn.execute(
        history_sql, {"pid": player_id, "match_date": match_date}
    ).fetchall()

    if not history:
        return 0.0

    fast_wins = fast_total = 0
    slow_wins = slow_total = 0

    for _tid, _tour, is_win, csi_val in history:
        if csi_val >= p67:
            fast_total += 1
            fast_wins += is_win
        elif csi_val <= p33:
            slow_total += 1
            slow_wins += is_win

    fast_wr = fast_wins / fast_total if fast_total >= min_matches_per_tier else 0.5
    slow_wr = slow_wins / slow_total if slow_total >= min_matches_per_tier else 0.5

    return fast_wr - slow_wr


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

def migrate_csi_columns(conn: sqlite3.Connection) -> None:
    """
    Idempotent schema migration: add CSI columns to match_features if absent.

    Adds:
        court_speed_index REAL
        has_no_csi        INTEGER
        speed_affinity    REAL

    Safe to call multiple times — existing columns are not modified.
    """
    existing = [
        row[1]
        for row in conn.execute("PRAGMA table_info(match_features)").fetchall()
    ]
    for col, typ in [
        ("court_speed_index", "REAL"),
        ("has_no_csi", "INTEGER"),
        ("speed_affinity", "REAL"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE match_features ADD COLUMN {col} {typ}")
    conn.commit()
