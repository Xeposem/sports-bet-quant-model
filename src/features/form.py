"""
Rolling form and service stats feature computation.

TEMPORAL SAFETY: Uses strict less-than on tourney_date (tourney_date < before_date)
to prevent look-ahead bias. The current match date is always excluded.

The function queries only matches before before_date, ensuring no future data
contaminates the rolling window — equivalent to applying shift(1) in a pandas
rolling context.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


def compute_rolling_form(
    conn: sqlite3.Connection,
    player_id: int,
    before_date: str,
    windows: list[int] | None = None,
) -> dict:
    """
    Compute rolling form and service statistics for a player strictly before before_date.

    TEMPORAL SAFETY: only matches with tourney_date < before_date are included.
    This is equivalent to shift(1) — the current match is never in its own window.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    player_id : int
        The player whose form to compute.
    before_date : str
        ISO date string "YYYY-MM-DD". Only matches strictly before this date are used.
    windows : list[int] or None
        Rolling window sizes. Defaults to [10, 20] if None.
        Each window N limits computation to the N most recent prior matches.
        For service stats, all prior matches up to max(windows) are used
        (the same result regardless of window, since we aggregate rather than roll).

    Returns
    -------
    dict with keys:
        "form_win_rate_{N}"  : float or None for each window N (e.g., "form_win_rate_10")
        "avg_ace_rate"       : float or None
        "avg_df_rate"        : float or None
        "avg_first_pct"      : float or None
        "avg_first_won_pct"  : float or None

    None is returned for any metric when no prior matches exist or when
    required denominators are zero.
    """
    if windows is None:
        windows = [10, 20]

    max_window = max(windows)

    # Fetch the most recent max_window matches for this player before before_date
    matches_sql = """
        SELECT
            m.tourney_id, m.match_num, m.tour,
            CASE WHEN m.winner_id = :pid THEN 1 ELSE 0 END AS is_win,
            CASE WHEN m.winner_id = :pid THEN 'winner' ELSE 'loser' END AS player_role
        FROM matches m
        WHERE (m.winner_id = :pid OR m.loser_id = :pid)
          AND m.tourney_date < :before_date
        ORDER BY m.tourney_date DESC
        LIMIT :max_window
    """
    match_rows = conn.execute(
        matches_sql,
        {"pid": player_id, "before_date": before_date, "max_window": max_window},
    ).fetchall()

    result: dict[str, Optional[float]] = {}

    # Win rate for each window
    for w in windows:
        window_rows = match_rows[:w]
        if not window_rows:
            result[f"form_win_rate_{w}"] = None
        else:
            wins = sum(row[3] for row in window_rows)
            result[f"form_win_rate_{w}"] = wins / len(window_rows)

    # Service stats across all fetched matches (up to max_window)
    if not match_rows:
        result["avg_ace_rate"] = None
        result["avg_df_rate"] = None
        result["avg_first_pct"] = None
        result["avg_first_won_pct"] = None
        return result

    # Build a lookup of (tourney_id, match_num, tour) -> player_role
    match_keys = [
        {"tid": row[0], "mnum": row[1], "tour": row[2], "role": row[4]}
        for row in match_rows
    ]

    # Aggregate service stats using a single query per role (winner vs loser)
    # We use CASE expressions to handle winner/loser roles
    # Build an IN-clause for the specific matches
    if not match_keys:
        result["avg_ace_rate"] = None
        result["avg_df_rate"] = None
        result["avg_first_pct"] = None
        result["avg_first_won_pct"] = None
        return result

    # Separate winner and loser keys
    winner_keys = [(r["tid"], r["mnum"], r["tour"]) for r in match_keys if r["role"] == "winner"]
    loser_keys  = [(r["tid"], r["mnum"], r["tour"]) for r in match_keys if r["role"] == "loser"]

    total_ace = 0
    total_df = 0
    total_svpt = 0
    total_first_in = 0
    total_first_won = 0
    has_any_stats = False

    def _fetch_stats(keys: list, role: str) -> None:
        nonlocal total_ace, total_df, total_svpt, total_first_in, total_first_won, has_any_stats
        if not keys:
            return
        # Build parameterized query using UNION ALL
        placeholders = " UNION ALL ".join(
            f"SELECT ace, df, svpt, first_in, first_won "
            f"FROM match_stats "
            f"WHERE tourney_id = ? AND match_num = ? AND tour = ? AND player_role = ?"
            for _ in keys
        )
        params: list = []
        for tid, mnum, tour in keys:
            params.extend([tid, mnum, tour, role])

        rows = conn.execute(placeholders, params).fetchall()
        for row in rows:
            ace, df, svpt, first_in, first_won = row
            if svpt is not None:
                has_any_stats = True
                total_ace += ace or 0
                total_df += df or 0
                total_svpt += svpt or 0
                total_first_in += first_in or 0
                total_first_won += first_won or 0

    _fetch_stats(winner_keys, "winner")
    _fetch_stats(loser_keys, "loser")

    if not has_any_stats or total_svpt == 0:
        result["avg_ace_rate"] = None
        result["avg_df_rate"] = None
        result["avg_first_pct"] = None
        result["avg_first_won_pct"] = None
    else:
        result["avg_ace_rate"] = total_ace / total_svpt
        result["avg_df_rate"] = total_df / total_svpt
        result["avg_first_pct"] = total_first_in / total_svpt
        result["avg_first_won_pct"] = (
            total_first_won / total_first_in if total_first_in > 0 else None
        )

    return result
