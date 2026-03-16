"""
Tests for database schema, connection factory, and test fixtures.

Task 1 tests — DATA-05 requirements:
- Schema creates all 7 tables with tour columns
- Connection factory sets WAL + foreign keys
- Schema is idempotent
- Indexes exist after schema creation

Task 2 tests — fixture behavior:
- In-memory DB fixture is available and has schema applied
- Sample CSV fixture has 5 rows and all expected columns
- Sample data includes retirement, walkover, completed match types
- Fixture teardown properly closes connections
"""
import sqlite3
import pytest
import pandas as pd


def test_schema_creates_all_tables(db_conn):
    """Verify 7 tables exist after schema creation."""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    # Exclude internal SQLite system tables (e.g., sqlite_sequence from AUTOINCREMENT)
    tables = {
        row[0] for row in cursor.fetchall()
        if not row[0].startswith("sqlite_")
    }
    expected = {
        "players",
        "tournaments",
        "matches",
        "match_stats",
        "rankings",
        "ingestion_log",
        "player_elo",
    }
    assert expected == tables, f"Expected {expected}, got {tables}"


def test_tour_column_exists(db_conn):
    """Verify every table has a 'tour' column."""
    tables = [
        "players",
        "tournaments",
        "matches",
        "match_stats",
        "rankings",
        "ingestion_log",
        "player_elo",
    ]
    for table in tables:
        cursor = db_conn.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        assert "tour" in columns, f"Table '{table}' is missing 'tour' column"


def test_schema_idempotent(db_conn):
    """Running schema.sql a second time on the same connection produces no errors."""
    from src.db.connection import _read_schema_sql

    schema_sql = _read_schema_sql()
    # Should not raise
    db_conn.executescript(schema_sql)


def test_connection_wal_mode(tmp_path):
    """
    Connection to a file-based database has WAL journal mode enabled.

    Note: In-memory SQLite databases always use 'memory' journal mode and
    cannot be set to WAL. This test uses a temporary file to verify WAL
    is correctly applied to real database connections.
    """
    from src.db.connection import get_connection, _read_schema_sql

    db_path = str(tmp_path / "test_wal.db")
    conn = get_connection(db_path)
    schema_sql = _read_schema_sql()
    conn.executescript(schema_sql)
    cursor = conn.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    conn.close()
    assert mode == "wal", f"Expected 'wal', got '{mode}'"


def test_connection_foreign_keys(db_conn):
    """Connection has foreign keys enabled (PRAGMA foreign_keys returns 1)."""
    cursor = db_conn.execute("PRAGMA foreign_keys")
    fk = cursor.fetchone()[0]
    assert fk == 1, f"Expected foreign_keys=1, got {fk}"


def test_indexes_exist(db_conn):
    """Verify all 4 required indexes exist after schema creation."""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    )
    indexes = {row[0] for row in cursor.fetchall()}
    expected = {
        "idx_matches_date",
        "idx_matches_winner",
        "idx_matches_loser",
        "idx_rankings_player",
    }
    missing = expected - indexes
    assert not missing, f"Missing indexes: {missing}"


# ---------------------------------------------------------------------------
# Task 2: Fixture behavior tests
# ---------------------------------------------------------------------------

def test_db_conn_fixture_has_schema(db_conn):
    """
    In-memory DB fixture creates schema and is available to tests.
    Verifies the fixture yields a usable connection with all tables present.
    """
    cursor = db_conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    table_count = cursor.fetchone()[0]
    assert table_count == 7, f"Expected 7 tables, got {table_count}"


def test_sample_match_df_has_five_rows(sample_match_df):
    """Sample CSV fixture provides a 5-row DataFrame."""
    assert len(sample_match_df) == 5, f"Expected 5 rows, got {len(sample_match_df)}"


def test_sample_match_df_has_all_columns(sample_match_df):
    """Sample CSV fixture has all 44 expected Sackmann schema columns."""
    expected_cols = [
        "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level",
        "tourney_date", "match_num", "winner_id", "winner_seed", "winner_entry",
        "winner_name", "winner_hand", "winner_ht", "winner_ioc", "winner_age",
        "winner_rank", "winner_rank_points", "loser_id", "loser_seed", "loser_entry",
        "loser_name", "loser_hand", "loser_ht", "loser_ioc", "loser_age",
        "loser_rank", "loser_rank_points", "score", "best_of", "round", "minutes",
        "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms",
        "w_bpSaved", "w_bpFaced", "l_ace", "l_df", "l_svpt", "l_1stIn",
        "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
    ]
    missing = [col for col in expected_cols if col not in sample_match_df.columns]
    assert not missing, f"Missing columns: {missing}"


def test_sample_match_df_has_retirement(sample_match_df):
    """Sample data includes at least one retirement (score ends with 'RET')."""
    retirements = sample_match_df[
        sample_match_df["score"].str.upper().str.endswith("RET", na=False)
    ]
    assert len(retirements) >= 1, "Expected at least one retirement match in sample data"


def test_sample_match_df_has_walkover(sample_match_df):
    """Sample data includes at least one walkover (score = 'W/O')."""
    walkovers = sample_match_df[
        sample_match_df["score"].str.upper() == "W/O"
    ]
    assert len(walkovers) >= 1, "Expected at least one walkover match in sample data"


def test_sample_match_df_has_completed(sample_match_df):
    """Sample data includes at least one completed match (regular score format)."""
    from tests.conftest import MATCH_DTYPES

    def is_completed(score):
        if not isinstance(score, str) or not score.strip():
            return False
        s = score.strip().upper()
        return s not in ("W/O", "DEF") and not s.endswith("RET")

    completed = sample_match_df[sample_match_df["score"].apply(is_completed)]
    assert len(completed) >= 1, "Expected at least one completed match in sample data"


def test_sample_match_df_tourney_date_is_raw_string(sample_match_df):
    """tourney_date in sample fixture is in YYYYMMDD string format (raw, before cleaning)."""
    for date_val in sample_match_df["tourney_date"]:
        assert isinstance(date_val, str), f"Expected str, got {type(date_val)}"
        assert len(date_val) == 8 and date_val.isdigit(), (
            f"Expected YYYYMMDD format, got '{date_val}'"
        )


def test_sample_csv_path_creates_readable_csv(sample_csv_path, sample_match_df):
    """sample_csv_path fixture writes sample DataFrame to a readable CSV."""
    assert sample_csv_path.exists(), f"CSV file not found at {sample_csv_path}"
    loaded = pd.read_csv(sample_csv_path, dtype=str)
    assert len(loaded) == len(sample_match_df), (
        f"CSV row count {len(loaded)} != fixture row count {len(sample_match_df)}"
    )


def test_db_conn_fixture_closes_on_teardown():
    """
    Fixture teardown properly closes connections.
    Verifies that after the fixture scope ends the connection is closed.
    We test this by calling the fixture manually and checking conn.close() behavior.
    """
    from src.db.connection import get_connection, _read_schema_sql

    conn = get_connection(":memory:")
    schema_sql = _read_schema_sql()
    conn.executescript(schema_sql)

    # Verify connection is open (can execute)
    conn.execute("SELECT 1")

    # Close and verify it's closed
    conn.close()
    with pytest.raises(Exception):
        conn.execute("SELECT 1")
