"""
Tests for database schema and connection factory.
These tests cover DATA-05 requirements:
- Schema creates all 7 tables with tour columns
- Connection factory sets WAL + foreign keys
- Schema is idempotent
- Indexes exist after schema creation
"""
import sqlite3
import pytest


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
