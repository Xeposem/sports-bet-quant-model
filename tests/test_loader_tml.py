"""
Integration tests for TML ingestion path in loader.py.

Tests cover:
- ingest_year_tml inserts matches with synthetic integer IDs
- Player IDs stored as integers in DB, not text
- Ingestion log records TML source file path
- ingest_all auto mode falls back to TML when Sackmann returns HTTPError
- ingest_all sackmann mode does not call TML functions
"""
import os
import sqlite3
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from src.db.connection import get_connection, init_db


# ---------------------------------------------------------------------------
# Minimal TML CSV content (1 row) for test fixtures
# ---------------------------------------------------------------------------
TML_MATCH_CSV = textwrap.dedent("""\
    tourney_id,tourney_name,surface,draw_size,tourney_level,indoor,tourney_date,match_num,winner_id,winner_seed,winner_entry,winner_name,winner_hand,winner_ht,winner_ioc,winner_age,winner_rank,winner_rank_points,loser_id,loser_seed,loser_entry,loser_name,loser_hand,loser_ht,loser_ioc,loser_age,loser_rank,loser_rank_points,score,best_of,round,minutes,w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,w_bpSaved,w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,l_SvGms,l_bpSaved,l_bpFaced
    2025-9900,United Cup,Hard,18,A,O,20241229,1,CD85,,,"Pablo Carreno Busta",R,188,ESP,33.467,196,292,S0H2,,,"Alexander Shevchenko",R,188,RUS,26.303,73,967,6-2 6-1,3,RR,64,3,0,40,25,20,8,8,3,3,1,2,35,18,12,5,7,1,4
""")

# Minimal ATP_Database.csv with our two test player IDs
TML_PLAYER_CSV = textwrap.dedent("""\
    id,atpname,player
    CD85,Pablo Carreno Busta,
    S0H2,Alexander Shevchenko,
""")


@pytest.fixture
def tml_db(tmp_path):
    """File-based SQLite DB with full schema applied via init_db."""
    db_path = str(tmp_path / "test_tml.db")
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


@pytest.fixture
def tml_files(tmp_path):
    """Write TML match CSV and player CSV to tmp_path, return paths."""
    match_csv = tmp_path / "tml_2025.csv"
    match_csv.write_text(TML_MATCH_CSV)
    player_csv = tmp_path / "ATP_Database.csv"
    player_csv.write_text(TML_PLAYER_CSV)
    return str(match_csv), str(player_csv)


# ---------------------------------------------------------------------------
# Task 1 tests
# ---------------------------------------------------------------------------

def test_ingest_year_tml_inserts_matches(tmp_path, tml_db, tml_files):
    """
    ingest_year_tml with mocked downloads should insert at least 1 match
    and those matches should have winner_id >= 900000 (synthetic TML range).
    """
    from src.ingestion.loader import ingest_year_tml

    conn, db_path = tml_db
    match_csv_path, player_csv_path = tml_files

    with (
        patch("src.ingestion.loader.download_tml_match_file", return_value=match_csv_path),
        patch("src.ingestion.loader.download_tml_player_file", return_value=player_csv_path),
    ):
        result = ingest_year_tml(conn, year=2025, raw_dir=str(tmp_path))

    assert result["inserted"] >= 1, f"Expected at least 1 inserted, got {result}"
    assert result["year"] == 2025

    rows = conn.execute("SELECT winner_id FROM matches").fetchall()
    assert rows, "No matches found in DB"
    for row in rows:
        assert row[0] >= 900000, f"winner_id {row[0]} is below 900000 (not synthetic TML range)"


def test_ingest_year_tml_player_ids_are_integers(tmp_path, tml_db, tml_files):
    """
    winner_id stored in the matches table should be of type integer, not text.
    Verifies the Int64 cast step in ingest_year_tml actually lands integer in DB.
    """
    from src.ingestion.loader import ingest_year_tml

    conn, db_path = tml_db
    match_csv_path, player_csv_path = tml_files

    with (
        patch("src.ingestion.loader.download_tml_match_file", return_value=match_csv_path),
        patch("src.ingestion.loader.download_tml_player_file", return_value=player_csv_path),
    ):
        ingest_year_tml(conn, year=2025, raw_dir=str(tmp_path))

    rows = conn.execute("SELECT typeof(winner_id) FROM matches").fetchall()
    assert rows, "No matches found"
    for row in rows:
        assert row[0] == "integer", (
            f"winner_id type should be 'integer', got '{row[0]}'"
        )


def test_ingest_year_tml_logs_tml_source(tmp_path, tml_db, tml_files):
    """
    ingestion_log.source_file should contain the TML CSV path (contains "tml_").
    Verifies the source_file is the TML file, not a Sackmann atp_matches_ path.
    """
    from src.ingestion.loader import ingest_year_tml

    conn, db_path = tml_db
    match_csv_path, player_csv_path = tml_files

    with (
        patch("src.ingestion.loader.download_tml_match_file", return_value=match_csv_path),
        patch("src.ingestion.loader.download_tml_player_file", return_value=player_csv_path),
    ):
        ingest_year_tml(conn, year=2025, raw_dir=str(tmp_path))

    rows = conn.execute(
        "SELECT source_file FROM ingestion_log WHERE year=2025"
    ).fetchall()
    assert rows, "No ingestion_log entry for year 2025"
    source_file = rows[0][0]
    assert "tml_" in source_file, (
        f"Expected source_file to contain 'tml_', got '{source_file}'"
    )


def test_ingest_all_auto_falls_back_to_tml(tmp_path, tml_files):
    """
    ingest_all with source='auto' should fall back to TML when Sackmann
    raises requests.exceptions.HTTPError (simulating a 404 for year 2025).
    """
    import requests
    from src.ingestion.loader import ingest_all

    match_csv_path, player_csv_path = tml_files
    db_path = str(tmp_path / "auto_test.db")

    with (
        patch("src.ingestion.loader.download_match_file",
              side_effect=requests.exceptions.HTTPError("404")),
        patch("src.ingestion.loader.download_tml_match_file",
              return_value=match_csv_path) as mock_tml_match,
        patch("src.ingestion.loader.download_tml_player_file",
              return_value=player_csv_path),
    ):
        results = ingest_all(
            db_path=db_path,
            raw_dir=str(tmp_path),
            start_year=2025,
            force=True,
            source="auto",
        )

    # At least one year should have been ingested via TML
    assert mock_tml_match.called, "TML fallback was not triggered in auto mode"
    # Result for 2025 should not have an error
    year_results = [r for r in results if r.get("year") == 2025]
    assert year_results, "No result for year 2025"
    assert "error" not in year_results[0], (
        f"Expected success for TML fallback, got error: {year_results[0].get('error')}"
    )


def test_ingest_all_sackmann_mode_unchanged(tmp_path):
    """
    ingest_all with source='sackmann' should never call TML functions.
    Verifies that the sackmann path is completely isolated from TML code.
    """
    from src.ingestion.loader import ingest_all

    db_path = str(tmp_path / "sackmann_test.db")

    # Stub Sackmann download to return a minimal CSV
    minimal_sackmann_csv = tmp_path / "atp_matches_2024.csv"
    # Write a valid minimal CSV that ingest_year can process
    from tests.conftest import MATCH_DTYPES
    import pandas as pd

    dummy_row = {col: (1 if dtype == "Int64" else 0.0 if dtype == float else "test")
                 for col, dtype in MATCH_DTYPES.items()}
    dummy_row.update({
        "tourney_id": "2024-9900",
        "tourney_name": "Test",
        "surface": "Hard",
        "draw_size": 32,
        "tourney_level": "A",
        "tourney_date": "20240101",
        "match_num": 1,
        "winner_id": 100001,
        "winner_name": "Player A",
        "winner_hand": "R",
        "winner_ioc": "USA",
        "winner_age": 25.0,
        "loser_id": 100002,
        "loser_name": "Player B",
        "loser_hand": "R",
        "loser_ioc": "ESP",
        "loser_age": 27.0,
        "score": "6-3 6-4",
        "best_of": 3,
        "round": "R32",
    })
    pd.DataFrame([dummy_row]).to_csv(str(minimal_sackmann_csv), index=False)

    with (
        patch("src.ingestion.loader.download_match_file",
              return_value=str(minimal_sackmann_csv)) as mock_sackmann,
        patch("src.ingestion.loader.download_tml_match_file") as mock_tml_match,
        patch("src.ingestion.loader.download_tml_player_file") as mock_tml_player,
    ):
        ingest_all(
            db_path=db_path,
            raw_dir=str(tmp_path),
            start_year=2024,
            force=True,
            source="sackmann",
        )

    assert mock_sackmann.called, "Sackmann download should have been called"
    assert not mock_tml_match.called, "TML match download should NOT be called in sackmann mode"
    assert not mock_tml_player.called, "TML player download should NOT be called in sackmann mode"
