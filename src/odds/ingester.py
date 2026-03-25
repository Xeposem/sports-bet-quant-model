"""
Odds ingestion pipeline for tennis-data.co.uk CSV files and manual entry.

Provides:
- parse_tennis_data_csv: Parse odds CSV and extract Pinnacle PSW/PSL columns
- upsert_match_odds: Idempotent INSERT OR REPLACE into match_odds table
- import_csv_odds: Orchestrate parse -> link -> upsert pipeline
- manual_entry: Single-match odds entry with source='manual'

Column mapping: tennis-data.co.uk uses DD/MM/YYYY dates and PSW/PSL for
Pinnacle winner/loser odds respectively.
"""
import logging
import sqlite3
from datetime import datetime
from typing import Optional

import pandas as pd

from src.odds.linker import link_odds_to_matches


logger = logging.getLogger(__name__)


# Column mapping: tennis-data.co.uk column names -> internal schema names
TD_COLUMN_MAP = {
    "Date": "match_date",
    "Tournament": "tourney_name",
    "Winner": "winner_name",
    "Loser": "loser_name",
    "PSW": "decimal_odds_winner",   # Pinnacle odds for match winner
    "PSL": "decimal_odds_loser",    # Pinnacle odds for match loser
    "Surface": "surface",
}

# Required columns for a valid odds row
_REQUIRED_ODDS_COLS = {"PSW", "PSL"}


def parse_tennis_data_csv(filepath: str) -> list:
    """
    Parse a tennis-data.co.uk file and extract Pinnacle odds rows.

    Accepts CSV (.csv), Excel (.xlsx), and legacy Excel (.xls) formats.

    Handles:
    - DD/MM/YYYY date format (dayfirst=True) and converts to ISO YYYY-MM-DD
    - Missing Pinnacle odds (PSW/PSL NaN rows are dropped)
    - Column mapping via TD_COLUMN_MAP

    Args:
        filepath: Path to tennis-data.co.uk file (.csv, .xlsx, or .xls).

    Returns:
        List of dicts with keys: match_date, winner_name, loser_name,
        decimal_odds_winner, decimal_odds_loser, (optionally tourney_name, surface).
    """
    ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
    if ext in ("xlsx", "xls"):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    # Check for required Pinnacle odds columns
    missing_cols = _REQUIRED_ODDS_COLS - set(df.columns)
    if missing_cols:
        logger.warning(
            "CSV file %s missing Pinnacle odds columns: %s — skipping file",
            filepath, missing_cols,
        )
        return []

    # Apply column mapping — only map columns that exist
    rename_map = {k: v for k, v in TD_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Parse dates with dayfirst=True to handle DD/MM/YYYY format
    # errors='coerce' converts unparseable dates to NaT
    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], dayfirst=True, errors="coerce")
        # Log if any dates failed to parse
        null_dates = df["match_date"].isna().sum()
        if null_dates > 0:
            logger.warning(
                "%d rows in %s had unparseable dates and will be skipped",
                null_dates, filepath,
            )
        df = df.dropna(subset=["match_date"])
        # Convert to ISO format string
        df["match_date"] = df["match_date"].dt.strftime("%Y-%m-%d")

    # Drop rows where Pinnacle odds are missing
    odds_before = len(df)
    df = df.dropna(subset=["decimal_odds_winner", "decimal_odds_loser"])
    skipped = odds_before - len(df)
    if skipped > 0:
        logger.info(
            "Skipped %d rows in %s with missing Pinnacle odds (PSW/PSL NaN)",
            skipped, filepath,
        )

    # Convert odds columns to float (in case they came in as object dtype)
    df["decimal_odds_winner"] = df["decimal_odds_winner"].astype(float)
    df["decimal_odds_loser"] = df["decimal_odds_loser"].astype(float)

    # Return as list of dicts, keeping only mapped columns that exist
    keep_cols = [v for k, v in TD_COLUMN_MAP.items() if v in df.columns]
    return df[keep_cols].to_dict(orient="records")


def upsert_match_odds(conn: sqlite3.Connection, odds_row: dict) -> bool:
    """
    Insert or replace a row in the match_odds table.

    Idempotent — uses INSERT OR REPLACE (same as INSERT OR REPLACE used
    throughout the project for idempotent writes).

    Args:
        conn: SQLite connection with match_odds table.
        odds_row: Dict with keys: tourney_id, match_num, tour, bookmaker,
                  decimal_odds_a, decimal_odds_b, source.

    Returns:
        True if row was inserted/replaced.
    """
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    conn.execute(
        """
        INSERT OR REPLACE INTO match_odds
            (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b,
             source, imported_at)
        VALUES
            (:tourney_id, :match_num, :tour, :bookmaker, :decimal_odds_a, :decimal_odds_b,
             :source, :imported_at)
        """,
        {
            "tourney_id": odds_row["tourney_id"],
            "match_num": odds_row["match_num"],
            "tour": odds_row.get("tour", "ATP"),
            "bookmaker": odds_row.get("bookmaker", "pinnacle"),
            "decimal_odds_a": odds_row["decimal_odds_a"],
            "decimal_odds_b": odds_row["decimal_odds_b"],
            "source": odds_row.get("source", "csv"),
            "imported_at": now,
        },
    )
    return True


def import_csv_odds(conn: sqlite3.Connection, filepath: str) -> dict:
    """
    Orchestrate the full CSV import pipeline: parse -> link -> upsert.

    Args:
        conn: SQLite connection.
        filepath: Path to tennis-data.co.uk CSV file.

    Returns:
        Dict with keys: imported (int), unlinked (int), skipped_no_odds (int).
    """
    # Step 1: Parse CSV (drops rows with missing PSW/PSL)
    # Re-read raw to count skipped_no_odds accurately
    try:
        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        if ext in ("xlsx", "xls"):
            raw_df = pd.read_excel(filepath)
        else:
            raw_df = pd.read_csv(filepath)
        total_rows = len(raw_df)
    except Exception:
        total_rows = 0

    odds_rows = parse_tennis_data_csv(filepath)
    skipped_no_odds = total_rows - len(odds_rows)

    # Step 2: Link to match IDs
    linked_rows = link_odds_to_matches(conn, odds_rows)

    # Step 3: Upsert linked rows
    imported = 0
    unlinked = 0

    try:
        from tqdm import tqdm
        upsert_iter = tqdm(linked_rows, desc="Upserting odds", unit="row")
    except ImportError:
        upsert_iter = linked_rows

    for row in upsert_iter:
        if row.get("tourney_id") is None:
            unlinked += 1
            continue

        upsert_match_odds(conn, {
            "tourney_id": row["tourney_id"],
            "match_num": row["match_num"],
            "tour": row.get("tour", "ATP"),
            "bookmaker": "pinnacle",
            "decimal_odds_a": row["decimal_odds_winner"],
            "decimal_odds_b": row["decimal_odds_loser"],
            "source": "csv",
        })
        imported += 1

    conn.commit()

    logger.info(
        "CSV import complete: imported=%d, unlinked=%d, skipped_no_odds=%d",
        imported, unlinked, skipped_no_odds,
    )
    return {"imported": imported, "unlinked": unlinked, "skipped_no_odds": skipped_no_odds}


def manual_entry(
    conn: sqlite3.Connection,
    tourney_id: str,
    match_num: int,
    decimal_odds_a: float,
    decimal_odds_b: float,
    bookmaker: str = "pinnacle",
    tour: str = "ATP",
) -> None:
    """
    Insert a single match odds row with source='manual'.

    Used for entering odds on upcoming matches before they appear in CSV exports.
    The match must already exist in the matches table (FK enforced).

    Args:
        conn: SQLite connection.
        tourney_id: Tournament ID (must exist in matches table).
        match_num: Match number (must exist in matches table).
        decimal_odds_a: Decimal odds for player A (winner).
        decimal_odds_b: Decimal odds for player B (loser).
        bookmaker: Bookmaker name (default 'pinnacle').
        tour: Tour identifier (default 'ATP').
    """
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    conn.execute(
        """
        INSERT OR REPLACE INTO match_odds
            (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b,
             source, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, 'manual', ?)
        """,
        (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b, now),
    )
