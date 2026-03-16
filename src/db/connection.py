"""
SQLite connection factory for the sports-bet-quant-model project.

Provides:
- get_connection(db_path): configured connection with WAL, foreign keys, and
  performance pragmas
- init_db(db_path): create/upgrade the database schema from schema.sql
- _read_schema_sql(): internal helper to load schema.sql content

All connections use:
  - autocommit=False  (explicit transaction control, PEP 249 / Python 3.12)
  - row_factory=sqlite3.Row  (dictionary-style column access)
  - PRAGMA journal_mode = WAL  (concurrent reads + single writer)
  - PRAGMA synchronous = NORMAL  (safe for analytics workload)
  - PRAGMA foreign_keys = ON  (enforce referential integrity)
  - PRAGMA cache_size = -64000  (64 MB page cache)

Usage:
    from src.db.connection import get_connection, init_db

    init_db("data/tennis.db")          # idempotent — safe to call multiple times
    conn = get_connection("data/tennis.db")
    rows = conn.execute("SELECT * FROM matches LIMIT 10").fetchall()
    conn.close()
"""

import sqlite3
from pathlib import Path


def _read_schema_sql() -> str:
    """
    Read and return the contents of schema.sql located in the same directory
    as this module.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    Open a SQLite connection to db_path with standard pragmas applied.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file, or ":memory:" for an in-memory DB.

    Returns
    -------
    sqlite3.Connection
        Configured connection (WAL mode, foreign keys ON, 64 MB cache).

    Notes
    -----
    - autocommit=False is explicit for Python 3.12+ best practice.
    - row_factory=sqlite3.Row enables column access by name.
    - Pragma results are read back and discarded — the pragmas are applied
      regardless of the return value for :memory: databases.
    """
    # isolation_level="" (default) enables deferred transactions (non-autocommit).
    # autocommit=False was added in Python 3.12; omitting it here is equivalent
    # for Python 3.9+ compatibility — the default sqlite3.connect() behaviour
    # is already non-autocommit (PEP 249 compliant).
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA cache_size = -64000")
    return conn


def init_db(db_path: str) -> None:
    """
    Initialize (or upgrade) the database at db_path by executing schema.sql.

    Idempotent — all DDL statements use CREATE TABLE IF NOT EXISTS and
    CREATE INDEX IF NOT EXISTS, so running this multiple times is safe.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.
    """
    schema_sql = _read_schema_sql()
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
    finally:
        conn.close()
