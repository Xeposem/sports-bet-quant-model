"""
SQLite upsert for matches, players, tournaments, match_stats, and ingestion_log.

Exports:
- upsert_tournaments(conn, df) -> int
- upsert_players(conn, df) -> int
- upsert_matches(conn, records) -> tuple[int, int]
- upsert_match_stats(conn, df) -> int
- upsert_rankings(conn, df) -> int
- log_ingestion(conn, year, source_file, rows_processed, rows_inserted, rows_skipped, status) -> None
- get_unprocessed_years(conn, start_year, end_year) -> list[int]
- ingest_year(conn, year, raw_dir, force) -> dict
- ingest_all(db_path, raw_dir, start_year, force) -> list[dict]
"""
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from src.db.connection import get_connection, init_db
from src.ingestion.cleaner import MATCH_DTYPES, clean_match_dataframe
from src.ingestion.tml_downloader import download_tml_match_file, download_tml_player_file
from src.ingestion.tml_id_mapper import build_id_map, normalise_tml_dataframe


# Mapping from winner/loser stat columns to match_stats schema columns
_WINNER_STAT_MAP = {
    "w_ace": "ace",
    "w_df": "df",
    "w_svpt": "svpt",
    "w_1stIn": "first_in",
    "w_1stWon": "first_won",
    "w_2ndWon": "second_won",
    "w_SvGms": "sv_gms",
    "w_bpSaved": "bp_saved",
    "w_bpFaced": "bp_faced",
}

_LOSER_STAT_MAP = {
    "l_ace": "ace",
    "l_df": "df",
    "l_svpt": "svpt",
    "l_1stIn": "first_in",
    "l_1stWon": "first_won",
    "l_2ndWon": "second_won",
    "l_SvGms": "sv_gms",
    "l_bpSaved": "bp_saved",
    "l_bpFaced": "bp_faced",
}


def _to_python(val):
    """Convert pandas NA / nullable integer types to Python-native types for sqlite3."""
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    # Unwrap pandas nullable integer (Int64)
    if hasattr(val, "item"):
        return val.item()
    return val


def upsert_tournaments(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    Extract unique tournament records from a match DataFrame and INSERT OR IGNORE
    into the tournaments table.

    Args:
        conn: Active SQLite connection.
        df: Cleaned match DataFrame (output of clean_match_dataframe).

    Returns:
        Number of rows inserted.
    """
    cols = ["tourney_id", "tour", "tourney_name", "surface", "draw_size", "tourney_level", "tourney_date"]
    present = [c for c in cols if c in df.columns]

    # Deduplicate by (tourney_id, tour)
    tourney_df = df[present].drop_duplicates(subset=["tourney_id", "tour"] if "tour" in present else ["tourney_id"])

    sql = """
        INSERT OR IGNORE INTO tournaments
            (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    inserted = 0
    for _, row in tourney_df.iterrows():
        conn.execute(sql, (
            _to_python(row.get("tourney_id")),
            _to_python(row.get("tour", "ATP")),
            _to_python(row.get("tourney_name")),
            _to_python(row.get("surface")),
            _to_python(row.get("draw_size")),
            _to_python(row.get("tourney_level")),
            _to_python(row.get("tourney_date")),
        ))
        if conn.execute("SELECT changes()").fetchone()[0] > 0:
            inserted += 1
    return inserted


def upsert_players(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    Extract unique player records from winner_* and loser_* columns and
    INSERT OR IGNORE into the players table.

    Note: TML CSVs provide only the full name in winner_name/loser_name.
    The full name is stored in last_name; a proper split can occur later.

    Args:
        conn: Active SQLite connection.
        df: Cleaned match DataFrame.

    Returns:
        Number of rows inserted.
    """
    sql = """
        INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name, hand, country_code)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    seen = set()
    inserted = 0
    tour = "ATP"

    for _, row in df.iterrows():
        for side in ("winner", "loser"):
            pid = _to_python(row.get(f"{side}_id"))
            if pid is None or pid in seen:
                continue
            seen.add(pid)
            name = _to_python(row.get(f"{side}_name"))
            hand = _to_python(row.get(f"{side}_hand"))
            ioc = _to_python(row.get(f"{side}_ioc"))
            conn.execute(sql, (pid, tour, None, name, hand, ioc))
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1

    return inserted


def upsert_matches(conn: sqlite3.Connection, records: list) -> tuple:
    """
    Insert match records into the matches table, skipping duplicates.

    Uses ON CONFLICT(tourney_id, match_num, tour) DO NOTHING so that
    re-running ingestion on the same year is idempotent.

    Args:
        conn: Active SQLite connection.
        records: List of dicts mapping cleaned DataFrame columns to values.

    Returns:
        (inserted, skipped) counts.
    """
    sql = """
        INSERT INTO matches (
            tourney_id, match_num, tour, winner_id, loser_id,
            score, round, best_of, minutes, tourney_date,
            match_type, retirement_flag, stats_normalized, stats_missing
        )
        VALUES (
            :tourney_id, :match_num, :tour, :winner_id, :loser_id,
            :score, :round, :best_of, :minutes, :tourney_date,
            :match_type, :retirement_flag, :stats_normalized, :stats_missing
        )
        ON CONFLICT(tourney_id, match_num, tour) DO NOTHING
    """
    inserted = 0
    skipped = 0

    for record in records:
        # Coerce all values to Python-native types
        clean = {k: _to_python(v) for k, v in record.items()}
        # Ensure required fields have defaults
        clean.setdefault("tour", "ATP")
        clean.setdefault("match_type", "completed")
        clean.setdefault("retirement_flag", 0)
        clean.setdefault("stats_normalized", 0)
        clean.setdefault("stats_missing", 0)
        conn.execute(sql, clean)
        changed = conn.execute("SELECT changes()").fetchone()[0]
        if changed > 0:
            inserted += 1
        else:
            skipped += 1

    return inserted, skipped


def upsert_rankings(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    Extract per-match ranking snapshots from a match DataFrame and INSERT OR IGNORE
    into the rankings table.

    Each match row yields up to two ranking entries (winner and loser).
    Rows where ranking is NaN/None are skipped (unranked players).
    Keyed by (ranking_date=tourney_date, tour, player_id) — duplicates are ignored.

    Args:
        conn: Active SQLite connection.
        df: Cleaned match DataFrame with winner_rank, loser_rank, etc.

    Returns:
        Number of rows inserted.
    """
    sql = """
        INSERT OR IGNORE INTO rankings
            (ranking_date, tour, player_id, ranking, ranking_points)
        VALUES (?, ?, ?, ?, ?)
    """
    inserted = 0

    for _, row in df.iterrows():
        tour = _to_python(row.get("tour", "ATP"))
        ranking_date = _to_python(row.get("tourney_date"))
        if ranking_date is None:
            continue

        for id_col, rank_col, pts_col in [
            ("winner_id", "winner_rank", "winner_rank_points"),
            ("loser_id", "loser_rank", "loser_rank_points"),
        ]:
            player_id = _to_python(row.get(id_col))
            ranking = _to_python(row.get(rank_col))
            if player_id is None or ranking is None:
                continue
            ranking_points = _to_python(row.get(pts_col))
            conn.execute(sql, (ranking_date, tour, player_id, ranking, ranking_points))
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1

    return inserted


def upsert_match_stats(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    For each match row, insert two match_stats rows: one for winner and one for loser.

    Rows where all stat columns for a player are NaN are skipped.

    Args:
        conn: Active SQLite connection.
        df: Cleaned match DataFrame.

    Returns:
        Total number of rows inserted.
    """
    sql = """
        INSERT OR IGNORE INTO match_stats
            (tourney_id, match_num, tour, player_role,
             ace, df, svpt, first_in, first_won, second_won, sv_gms, bp_saved, bp_faced)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    inserted = 0

    for _, row in df.iterrows():
        tid = _to_python(row.get("tourney_id"))
        mnum = _to_python(row.get("match_num"))
        tour = _to_python(row.get("tour", "ATP"))

        for role, stat_map in (("winner", _WINNER_STAT_MAP), ("loser", _LOSER_STAT_MAP)):
            stats = {dest: _to_python(row.get(src)) for src, dest in stat_map.items()}
            # Skip rows where all stats are None
            if all(v is None for v in stats.values()):
                continue
            conn.execute(sql, (
                tid, mnum, tour, role,
                stats.get("ace"), stats.get("df"), stats.get("svpt"),
                stats.get("first_in"), stats.get("first_won"), stats.get("second_won"),
                stats.get("sv_gms"), stats.get("bp_saved"), stats.get("bp_faced"),
            ))
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1

    return inserted


def log_ingestion(
    conn: sqlite3.Connection,
    year: int,
    source_file: str,
    rows_processed: int,
    rows_inserted: int,
    rows_skipped: int,
    status: str = "success",
) -> None:
    """
    Insert a row into ingestion_log recording the result of one ingestion run.

    Args:
        conn: Active SQLite connection.
        year: The season year ingested.
        source_file: Path or name of the CSV file processed.
        rows_processed: Total rows loaded from CSV (after exclusions).
        rows_inserted: Rows written to the DB.
        rows_skipped: Rows that were duplicates (ON CONFLICT DO NOTHING).
        status: 'success', 'partial', or 'failed'.
    """
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        """
        INSERT INTO ingestion_log
            (ingested_at, source_file, tour, year, rows_processed, rows_inserted, rows_skipped, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ingested_at, source_file, "ATP", year, rows_processed, rows_inserted, rows_skipped, status),
    )


def get_unprocessed_years(
    conn: sqlite3.Connection,
    start_year: int = 1991,
    end_year: int | None = None,
) -> list:
    """
    Return years in [start_year, end_year] that have not yet been successfully ingested.

    Args:
        conn: Active SQLite connection.
        start_year: First year to check (inclusive).
        end_year: Last year to check (inclusive). Defaults to the current year.

    Returns:
        List of integer years not present in ingestion_log with status='success'.
    """
    if end_year is None:
        end_year = datetime.now(timezone.utc).year
    cursor = conn.execute(
        "SELECT year FROM ingestion_log WHERE status='success' AND tour='ATP'"
    )
    processed = {row[0] for row in cursor.fetchall()}
    return [y for y in range(start_year, end_year + 1) if y not in processed]


def ingest_year(
    conn: sqlite3.Connection,
    year: int,
    raw_dir: str,
    force: bool = False,
) -> dict:
    """
    Orchestrate the full pipeline for one season year using TennisMyLife data.

    Steps: Download TML CSV -> Download ATP_Database.csv (if missing) -> Build ID map
    -> Read CSV with str player IDs -> Normalise IDs to integers -> Clean -> Upsert -> Log.

    Args:
        conn: Active SQLite connection (caller manages commit/rollback).
        year: The season year to ingest.
        raw_dir: Directory for downloading raw CSV files.
        force: If True, skip the already-processed check (default False).

    Returns:
        Summary dict with keys: year, inserted, skipped, excluded, rows_processed.
    """
    # 1. Download TML match CSV
    csv_path = download_tml_match_file(year, raw_dir)

    # 2. Ensure ATP_Database.csv exists for ID mapping
    player_csv = os.path.join(raw_dir, "ATP_Database.csv")
    if not os.path.exists(player_csv):
        download_tml_player_file(raw_dir)

    # 3. Build/update ID map
    build_id_map(player_csv, conn)

    # 4. Read CSV — TML uses alphanumeric winner_id/loser_id, so override those dtypes to str
    tml_dtypes = {k: v for k, v in MATCH_DTYPES.items()}
    tml_dtypes["winner_id"] = str
    tml_dtypes["loser_id"] = str
    df = pd.read_csv(
        csv_path,
        dtype=tml_dtypes,
        na_values=["", "nan", "NA"],
        keep_default_na=True,
        encoding="latin-1",
    )

    # 4b. Back-fill missing match_num with sequential integers per tournament
    if df["match_num"].isna().any():
        for tid, grp in df[df["match_num"].isna()].groupby("tourney_id"):
            df.loc[grp.index, "match_num"] = range(1, len(grp) + 1)
        df["match_num"] = df["match_num"].astype("Int64")

    # 5. Translate TML alphanumeric IDs to synthetic integers
    df = normalise_tml_dataframe(df, conn)
    df["winner_id"] = df["winner_id"].astype("Int64")
    df["loser_id"] = df["loser_id"].astype("Int64")

    # 6. Clean (reindex drops 'indoor' column, classify_match works unchanged)
    cleaned_df, excluded_df = clean_match_dataframe(df)

    # 7. Upsert in dependency order (same as ingest_year)
    upsert_tournaments(conn, cleaned_df)
    upsert_players(conn, cleaned_df)
    records = cleaned_df.to_dict(orient="records")
    inserted, skipped = upsert_matches(conn, records)
    upsert_match_stats(conn, cleaned_df)
    upsert_rankings(conn, cleaned_df)

    # 8. Log with TML source file path
    log_ingestion(
        conn,
        year=year,
        source_file=csv_path,
        rows_processed=len(cleaned_df),
        rows_inserted=inserted,
        rows_skipped=skipped,
        status="success",
    )
    conn.commit()

    return {
        "year": year,
        "inserted": inserted,
        "skipped": skipped,
        "excluded": len(excluded_df),
        "rows_processed": len(cleaned_df),
    }


def ingest_all(
    db_path: str,
    raw_dir: str,
    start_year: int = 1991,
    force: bool = False,
) -> list:
    """
    Initialize the database and ingest all unprocessed years from TennisMyLife.

    Args:
        db_path: Path to the SQLite database file.
        raw_dir: Directory for downloaded CSV files.
        start_year: First year to consider (default 1991).
        force: If True, re-ingest all years regardless of existing log entries.

    Returns:
        List of per-year summary dicts from ingest_year.
    """
    try:
        from tqdm import tqdm
        _tqdm = tqdm
    except ImportError:
        _tqdm = list  # fallback: no progress bar

    init_db(db_path)
    conn = get_connection(db_path)

    try:
        if force:
            current_year = datetime.now(timezone.utc).year
            years = list(range(start_year, current_year + 1))
        else:
            years = get_unprocessed_years(conn, start_year=start_year)

        results = []
        for year in _tqdm(years):
            try:
                result = ingest_year(conn, year=year, raw_dir=raw_dir, force=force)
                results.append(result)
            except Exception as exc:
                log_ingestion(
                    conn,
                    year=year,
                    source_file=f"tml_{year}.csv",
                    rows_processed=0,
                    rows_inserted=0,
                    rows_skipped=0,
                    status="failed",
                )
                conn.commit()
                results.append({"year": year, "error": str(exc)})

        return results
    finally:
        conn.close()
