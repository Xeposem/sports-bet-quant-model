"""
Pytest fixtures for sports-bet-quant-model test suite.

Includes both sync fixtures (db_conn, sample_match_df, sample_csv_path)
and async API fixtures (async_app, async_client) for httpx-based endpoint tests.

Provides:
- db_conn: in-memory SQLite connection with schema applied
- sample_match_df: 5-row synthetic ATP match DataFrame
- sample_csv_path: CSV file containing sample_match_df written to tmp_path
"""
import sqlite3
import pytest
import pandas as pd

from src.db.connection import get_connection, init_db


@pytest.fixture
def db_conn():
    """
    In-memory SQLite connection with full schema applied.
    Uses get_connection(":memory:") and applies schema.sql via init_db logic.
    Yields the connection, closes on teardown.
    """
    conn = get_connection(":memory:")
    from src.db.connection import _read_schema_sql
    schema_sql = _read_schema_sql()
    conn.executescript(schema_sql)
    yield conn
    conn.close()


# Sackmann 44-column dtype map — matches RESEARCH.md MATCH_DTYPES
MATCH_DTYPES = {
    "tourney_id": str,
    "tourney_name": str,
    "surface": str,
    "draw_size": "Int64",
    "tourney_level": str,
    "tourney_date": str,
    "match_num": "Int64",
    "winner_id": "Int64",
    "winner_seed": "Int64",
    "winner_entry": str,
    "winner_name": str,
    "winner_hand": str,
    "winner_ht": "Int64",
    "winner_ioc": str,
    "winner_age": float,
    "winner_rank": "Int64",
    "winner_rank_points": "Int64",
    "loser_id": "Int64",
    "loser_seed": "Int64",
    "loser_entry": str,
    "loser_name": str,
    "loser_hand": str,
    "loser_ht": "Int64",
    "loser_ioc": str,
    "loser_age": float,
    "loser_rank": "Int64",
    "loser_rank_points": "Int64",
    "score": str,
    "best_of": "Int64",
    "round": str,
    "minutes": "Int64",
    "w_ace": "Int64",
    "w_df": "Int64",
    "w_svpt": "Int64",
    "w_1stIn": "Int64",
    "w_1stWon": "Int64",
    "w_2ndWon": "Int64",
    "w_SvGms": "Int64",
    "w_bpSaved": "Int64",
    "w_bpFaced": "Int64",
    "l_ace": "Int64",
    "l_df": "Int64",
    "l_svpt": "Int64",
    "l_1stIn": "Int64",
    "l_1stWon": "Int64",
    "l_2ndWon": "Int64",
    "l_SvGms": "Int64",
    "l_bpSaved": "Int64",
    "l_bpFaced": "Int64",
}


@pytest.fixture
def sample_match_df():
    """
    5-row synthetic ATP match DataFrame covering:
    - 1 completed match
    - 1 retirement (score ends with "RET")
    - 1 walkover (score="W/O")
    - 1 default (score="DEF")
    - 1 match with missing stats (all stat columns NaN)

    tourney_date is YYYYMMDD string (raw format before cleaning).
    Includes all 44 columns from the Sackmann schema (MATCH_DTYPES).
    """
    rows = [
        # Row 0: Completed match — full stats
        {
            "tourney_id": "2024-0021",
            "tourney_name": "Australian Open",
            "surface": "Hard",
            "draw_size": 128,
            "tourney_level": "G",
            "tourney_date": "20240115",
            "match_num": 1,
            "winner_id": 104925,
            "winner_seed": 1,
            "winner_entry": None,
            "winner_name": "Novak Djokovic",
            "winner_hand": "R",
            "winner_ht": 188,
            "winner_ioc": "SRB",
            "winner_age": 36.5,
            "winner_rank": 1,
            "winner_rank_points": 11245,
            "loser_id": 207989,
            "loser_seed": 5,
            "loser_entry": None,
            "loser_name": "Andrey Rublev",
            "loser_hand": "R",
            "loser_ht": 188,
            "loser_ioc": "RUS",
            "loser_age": 26.2,
            "loser_rank": 5,
            "loser_rank_points": 4200,
            "score": "6-3 6-4 6-3",
            "best_of": 5,
            "round": "QF",
            "minutes": 112,
            "w_ace": 12,
            "w_df": 2,
            "w_svpt": 85,
            "w_1stIn": 52,
            "w_1stWon": 42,
            "w_2ndWon": 22,
            "w_SvGms": 9,
            "w_bpSaved": 2,
            "w_bpFaced": 3,
            "l_ace": 4,
            "l_df": 3,
            "l_svpt": 70,
            "l_1stIn": 43,
            "l_1stWon": 30,
            "l_2ndWon": 18,
            "l_SvGms": 9,
            "l_bpSaved": 0,
            "l_bpFaced": 5,
        },
        # Row 1: Retirement match
        {
            "tourney_id": "2024-0021",
            "tourney_name": "Australian Open",
            "surface": "Hard",
            "draw_size": 128,
            "tourney_level": "G",
            "tourney_date": "20240113",
            "match_num": 2,
            "winner_id": 106421,
            "winner_seed": 2,
            "winner_entry": None,
            "winner_name": "Carlos Alcaraz",
            "winner_hand": "R",
            "winner_ht": 185,
            "winner_ioc": "ESP",
            "winner_age": 20.8,
            "winner_rank": 2,
            "winner_rank_points": 9520,
            "loser_id": 200765,
            "loser_seed": None,
            "loser_entry": None,
            "loser_name": "Jan-Lennard Struff",
            "loser_hand": "R",
            "loser_ht": 196,
            "loser_ioc": "GER",
            "loser_age": 33.4,
            "loser_rank": 42,
            "loser_rank_points": 910,
            "score": "6-2 3-1 RET",
            "best_of": 5,
            "round": "R32",
            "minutes": 45,
            "w_ace": 5,
            "w_df": 1,
            "w_svpt": 40,
            "w_1stIn": 28,
            "w_1stWon": 22,
            "w_2ndWon": 9,
            "w_SvGms": 5,
            "w_bpSaved": 1,
            "w_bpFaced": 2,
            "l_ace": 1,
            "l_df": 2,
            "l_svpt": 30,
            "l_1stIn": 18,
            "l_1stWon": 12,
            "l_2ndWon": 7,
            "l_SvGms": 4,
            "l_bpSaved": 0,
            "l_bpFaced": 3,
        },
        # Row 2: Walkover
        {
            "tourney_id": "2024-0021",
            "tourney_name": "Australian Open",
            "surface": "Hard",
            "draw_size": 128,
            "tourney_level": "G",
            "tourney_date": "20240113",
            "match_num": 3,
            "winner_id": 105777,
            "winner_seed": 3,
            "winner_entry": None,
            "winner_name": "Daniil Medvedev",
            "winner_hand": "R",
            "winner_ht": 198,
            "winner_ioc": "RUS",
            "winner_age": 28.1,
            "winner_rank": 3,
            "winner_rank_points": 7160,
            "loser_id": 200456,
            "loser_seed": None,
            "loser_entry": None,
            "loser_name": "Some Player",
            "loser_hand": "R",
            "loser_ht": 180,
            "loser_ioc": "FRA",
            "loser_age": 25.0,
            "loser_rank": 88,
            "loser_rank_points": 410,
            "score": "W/O",
            "best_of": 5,
            "round": "R64",
            "minutes": None,
            "w_ace": None,
            "w_df": None,
            "w_svpt": None,
            "w_1stIn": None,
            "w_1stWon": None,
            "w_2ndWon": None,
            "w_SvGms": None,
            "w_bpSaved": None,
            "w_bpFaced": None,
            "l_ace": None,
            "l_df": None,
            "l_svpt": None,
            "l_1stIn": None,
            "l_1stWon": None,
            "l_2ndWon": None,
            "l_SvGms": None,
            "l_bpSaved": None,
            "l_bpFaced": None,
        },
        # Row 3: Default
        {
            "tourney_id": "2024-0021",
            "tourney_name": "Australian Open",
            "surface": "Hard",
            "draw_size": 128,
            "tourney_level": "G",
            "tourney_date": "20240113",
            "match_num": 4,
            "winner_id": 105777,
            "winner_seed": 3,
            "winner_entry": None,
            "winner_name": "Daniil Medvedev",
            "winner_hand": "R",
            "winner_ht": 198,
            "winner_ioc": "RUS",
            "winner_age": 28.1,
            "winner_rank": 3,
            "winner_rank_points": 7160,
            "loser_id": 200999,
            "loser_seed": None,
            "loser_entry": None,
            "loser_name": "Another Player",
            "loser_hand": "L",
            "loser_ht": 183,
            "loser_ioc": "ITA",
            "loser_age": 22.3,
            "loser_rank": 120,
            "loser_rank_points": 230,
            "score": "DEF",
            "best_of": 5,
            "round": "R64",
            "minutes": None,
            "w_ace": None,
            "w_df": None,
            "w_svpt": None,
            "w_1stIn": None,
            "w_1stWon": None,
            "w_2ndWon": None,
            "w_SvGms": None,
            "w_bpSaved": None,
            "w_bpFaced": None,
            "l_ace": None,
            "l_df": None,
            "l_svpt": None,
            "l_1stIn": None,
            "l_1stWon": None,
            "l_2ndWon": None,
            "l_SvGms": None,
            "l_bpSaved": None,
            "l_bpFaced": None,
        },
        # Row 4: Completed match with all stat columns missing
        {
            "tourney_id": "2024-0021",
            "tourney_name": "Australian Open",
            "surface": "Hard",
            "draw_size": 128,
            "tourney_level": "G",
            "tourney_date": "20240112",
            "match_num": 5,
            "winner_id": 105434,
            "winner_seed": None,
            "winner_entry": "Q",
            "winner_name": "Lucky Qualifier",
            "winner_hand": "R",
            "winner_ht": 182,
            "winner_ioc": "AUS",
            "winner_age": 24.7,
            "winner_rank": 200,
            "winner_rank_points": 95,
            "loser_id": 201111,
            "loser_seed": None,
            "loser_entry": None,
            "loser_name": "Opponent Player",
            "loser_hand": "R",
            "loser_ht": 178,
            "loser_ioc": "ARG",
            "loser_age": 27.9,
            "loser_rank": 180,
            "loser_rank_points": 130,
            "score": "6-4 3-6 7-5",
            "best_of": 3,
            "round": "R128",
            "minutes": 95,
            "w_ace": None,
            "w_df": None,
            "w_svpt": None,
            "w_1stIn": None,
            "w_1stWon": None,
            "w_2ndWon": None,
            "w_SvGms": None,
            "w_bpSaved": None,
            "w_bpFaced": None,
            "l_ace": None,
            "l_df": None,
            "l_svpt": None,
            "l_1stIn": None,
            "l_1stWon": None,
            "l_2ndWon": None,
            "l_SvGms": None,
            "l_bpSaved": None,
            "l_bpFaced": None,
        },
    ]

    # Build DataFrame with proper dtypes
    df = pd.DataFrame(rows)

    # Apply nullable integer types
    int64_cols = [
        "draw_size", "match_num", "winner_id", "winner_seed", "winner_ht",
        "winner_rank", "winner_rank_points", "loser_id", "loser_seed",
        "loser_ht", "loser_rank", "loser_rank_points", "best_of", "minutes",
        "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
        "w_SvGms", "w_bpSaved", "w_bpFaced", "l_ace", "l_df", "l_svpt",
        "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
    ]
    for col in int64_cols:
        df[col] = df[col].astype("Int64")

    return df


@pytest.fixture
def sample_csv_path(tmp_path, sample_match_df):
    """Write sample_match_df to a CSV in tmp_path and return the path."""
    csv_path = tmp_path / "atp_matches_test.csv"
    sample_match_df.to_csv(csv_path, index=False)
    return csv_path


# ---------------------------------------------------------------------------
# Async API fixtures (Phase 5 — FastAPI)
# ---------------------------------------------------------------------------

@pytest.fixture
async def async_app(tmp_path):
    """Create FastAPI app with a temporary file-based test DB.

    Uses a temp file so both the async SQLAlchemy engine and sync sqlite3 calls
    (in write endpoints) can share the same database with the schema applied.

    Bypasses the lifespan context manager by directly setting app.state so tests
    do not require a real model artifact on disk.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from src.api.main import app
    from src.db.connection import init_db

    # Use a temp file so all sqlite3 connections (async + sync) share the same DB
    db_file = tmp_path / "test.db"
    db_path = str(db_file)
    init_db(db_path)

    # Create async engine pointing to the same temp file
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.async_session_factory = session_factory
    app.state.engine = engine
    app.state.model = None
    app.state.db_path = db_path

    yield app

    await engine.dispose()


@pytest.fixture
async def async_client(async_app):
    """httpx AsyncClient configured to call the FastAPI test app."""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=async_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
