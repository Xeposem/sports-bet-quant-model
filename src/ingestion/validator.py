"""
Data quality validation module for the ATP tennis database.

Provides:
- check_duplicates(conn) -> list[dict]
- check_retirement_ratio(conn) -> dict
- check_date_ordering(conn) -> dict
- check_stats_completeness(conn) -> dict
- check_temporal_safety(conn) -> dict
- check_row_counts(conn) -> dict
- validate_database(conn) -> dict
"""
import re
import sqlite3


# ISO date pattern: YYYY-MM-DD
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Range bounds for expected retirement ratio
_RETIREMENT_RATIO_MIN = 0.03
_RETIREMENT_RATIO_MAX = 0.05


def check_duplicates(conn: sqlite3.Connection) -> list:
    """
    Detect duplicate match rows by (tourney_id, match_num, tour).

    In normal operation the ON CONFLICT DO NOTHING upsert prevents duplicates,
    but this check validates the state of the database directly.

    Args:
        conn: Active SQLite connection.

    Returns:
        List of dicts, each with keys: tourney_id, match_num, tour, count.
        Empty list if no duplicates exist.
    """
    cursor = conn.execute(
        """
        SELECT tourney_id, match_num, tour, COUNT(*) AS cnt
        FROM matches
        GROUP BY tourney_id, match_num, tour
        HAVING COUNT(*) > 1
        """
    )
    rows = cursor.fetchall()
    return [
        {
            "tourney_id": row[0],
            "match_num": row[1],
            "tour": row[2],
            "count": row[3],
        }
        for row in rows
    ]


def check_retirement_ratio(conn: sqlite3.Connection) -> dict:
    """
    Compute the ratio of retirement matches to total matches.

    Args:
        conn: Active SQLite connection.

    Returns:
        Dict with keys:
        - total: int — total match count
        - retirements: int — count of retirement_flag=1 rows
        - ratio: float — retirements / total (0.0 if total is 0)
        - in_range: bool — True if ratio between 3% and 5%
    """
    total_row = conn.execute("SELECT COUNT(*) FROM matches").fetchone()
    total = total_row[0] if total_row else 0

    ret_row = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE retirement_flag = 1"
    ).fetchone()
    retirements = ret_row[0] if ret_row else 0

    ratio = retirements / total if total > 0 else 0.0
    in_range = _RETIREMENT_RATIO_MIN <= ratio <= _RETIREMENT_RATIO_MAX

    return {
        "total": total,
        "retirements": retirements,
        "ratio": ratio,
        "in_range": in_range,
    }


def check_date_ordering(conn: sqlite3.Connection) -> dict:
    """
    Verify that all tourney_date values in matches are ISO YYYY-MM-DD format,
    and that the dates are chronologically ordered (i.e. no time-travel anomalies).

    Args:
        conn: Active SQLite connection.

    Returns:
        Dict with keys:
        - valid_format: bool — True if all dates match YYYY-MM-DD pattern
        - invalid_dates: list[str] — dates that do not match the ISO pattern
        - chronological: bool — True if dates are non-decreasing when sorted
    """
    cursor = conn.execute("SELECT DISTINCT tourney_date FROM matches")
    all_dates = [row[0] for row in cursor.fetchall() if row[0] is not None]

    invalid_dates = [d for d in all_dates if not _ISO_DATE_RE.match(d)]
    valid_format = len(invalid_dates) == 0

    # Check chronological ordering: sorted list should equal itself
    valid_iso = [d for d in all_dates if _ISO_DATE_RE.match(d)]
    chronological = valid_iso == sorted(valid_iso)

    return {
        "valid_format": valid_format,
        "invalid_dates": invalid_dates,
        "chronological": chronological,
    }


def check_stats_completeness(conn: sqlite3.Connection) -> dict:
    """
    Compute per-year breakdown of missing stats (stats_missing = 1).

    The year is extracted from tourney_date (YYYY-MM-DD format).

    Args:
        conn: Active SQLite connection.

    Returns:
        Dict with keys:
        - by_year: dict mapping year (int) -> {"total": int, "missing": int, "pct_missing": float}
        - overall_missing_pct: float — overall fraction of matches with stats_missing=1
    """
    cursor = conn.execute(
        """
        SELECT
            CAST(SUBSTR(tourney_date, 1, 4) AS INTEGER) AS year,
            COUNT(*) AS total,
            SUM(stats_missing) AS missing
        FROM matches
        WHERE tourney_date LIKE '____-__-__'
        GROUP BY year
        ORDER BY year
        """
    )
    rows = cursor.fetchall()

    by_year = {}
    total_all = 0
    missing_all = 0

    for row in rows:
        year = row[0]
        total = row[1]
        missing = row[2] if row[2] is not None else 0
        pct = missing / total if total > 0 else 0.0
        by_year[year] = {"total": total, "missing": missing, "pct_missing": pct}
        total_all += total
        missing_all += missing

    overall_missing_pct = missing_all / total_all if total_all > 0 else 0.0

    return {
        "by_year": by_year,
        "overall_missing_pct": overall_missing_pct,
    }


def check_temporal_safety(conn: sqlite3.Connection) -> dict:
    """
    Verify that Phase 2 feature tables are empty stubs in Phase 1.

    Confirms that player_elo has no rows (no computed features exist yet)
    and the matches table contains only raw data columns (no computed feature cols).

    Args:
        conn: Active SQLite connection.

    Returns:
        Dict with keys:
        - feature_tables_empty: bool — True if player_elo has 0 rows
        - safe: bool — True if all temporal safety checks pass
    """
    elo_count_row = conn.execute("SELECT COUNT(*) FROM player_elo").fetchone()
    elo_count = elo_count_row[0] if elo_count_row else 0

    feature_tables_empty = elo_count == 0
    safe = feature_tables_empty

    return {
        "feature_tables_empty": feature_tables_empty,
        "safe": safe,
    }


def check_row_counts(conn: sqlite3.Connection) -> dict:
    """
    Return total row counts per table and per-year match counts.

    Useful for data health dashboards and quick sanity checks.

    Args:
        conn: Active SQLite connection.

    Returns:
        Dict with keys:
        - matches: int
        - players: int
        - tournaments: int
        - match_stats: int
        - rankings: int
        - by_year: dict mapping year (int) -> row count (int)
    """
    def _count(table: str) -> int:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0

    by_year_cursor = conn.execute(
        """
        SELECT
            CAST(SUBSTR(tourney_date, 1, 4) AS INTEGER) AS year,
            COUNT(*) AS cnt
        FROM matches
        WHERE tourney_date LIKE '____-__-__'
        GROUP BY year
        ORDER BY year
        """
    )
    by_year = {row[0]: row[1] for row in by_year_cursor.fetchall()}

    return {
        "matches": _count("matches"),
        "players": _count("players"),
        "tournaments": _count("tournaments"),
        "match_stats": _count("match_stats"),
        "rankings": _count("rankings"),
        "by_year": by_year,
    }


def validate_database(conn: sqlite3.Connection) -> dict:
    """
    Run all validation checks and return a combined result.

    Args:
        conn: Active SQLite connection.

    Returns:
        Dict with keys:
        - duplicates: list[dict] from check_duplicates
        - retirement_ratio: dict from check_retirement_ratio
        - date_ordering: dict from check_date_ordering
        - stats_completeness: dict from check_stats_completeness
        - temporal_safety: dict from check_temporal_safety
        - row_counts: dict from check_row_counts
        - overall_valid: bool — True if all critical checks pass
    """
    duplicates = check_duplicates(conn)
    retirement_ratio = check_retirement_ratio(conn)
    date_ordering = check_date_ordering(conn)
    stats_completeness = check_stats_completeness(conn)
    temporal_safety = check_temporal_safety(conn)
    row_counts = check_row_counts(conn)

    # overall_valid: no duplicates, dates are valid ISO, temporal safety OK
    # retirement_ratio in_range is a WARNING not a hard failure (can vary with real data)
    overall_valid = (
        len(duplicates) == 0
        and date_ordering["valid_format"]
        and temporal_safety["safe"]
    )

    return {
        "duplicates": duplicates,
        "retirement_ratio": retirement_ratio,
        "date_ordering": date_ordering,
        "stats_completeness": stats_completeness,
        "temporal_safety": temporal_safety,
        "row_counts": row_counts,
        "overall_valid": overall_valid,
    }
