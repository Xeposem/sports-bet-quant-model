"""
Unit tests for src/props package.

Task 1: score_parser, compute_pmf, p_over, PROP_REGISTRY (all pass)
Task 2: GLM model training/prediction, schema (unskipped in Task 2)
Task 3: predict_and_store, CLI (unskipped in Task 3)
Plan 02, Task 4: Resolver tests
Plan 02, Task 5: GET /props and GET /props/accuracy endpoint tests
"""

import json
import pytest
import sqlite3

# ---------------------------------------------------------------------------
# Task 1: Score parser tests
# ---------------------------------------------------------------------------

from src.props.score_parser import parse_score


def test_score_parser_standard():
    assert parse_score("6-3 7-5") == (13, 8)


def test_score_parser_tiebreak():
    # Tiebreak: 7-6(5) -- winner gets 7, loser gets 6
    assert parse_score("6-3 6-4 7-6(5)") == (19, 13)


def test_score_parser_three_sets():
    assert parse_score("6-4 3-6 6-3") == (15, 13)


def test_score_parser_retirement():
    assert parse_score("6-3 4-2 RET") is None


def test_score_parser_walkover():
    assert parse_score("W/O") is None


def test_score_parser_default():
    assert parse_score("DEF") is None


def test_score_parser_empty():
    assert parse_score("") is None
    assert parse_score(None) is None


# ---------------------------------------------------------------------------
# Task 1: compute_pmf tests
# ---------------------------------------------------------------------------

from src.props.base import compute_pmf, p_over


def test_compute_pmf_poisson():
    pmf = compute_pmf(mu=6.0, family="poisson")
    assert isinstance(pmf, list)
    assert all(v >= 0 for v in pmf)
    assert abs(sum(pmf) - 1.0) < 0.001


def test_compute_pmf_negbin():
    pmf = compute_pmf(mu=20.0, family="negative_binomial", alpha=0.5)
    assert isinstance(pmf, list)
    assert all(v >= 0 for v in pmf)
    assert abs(sum(pmf) - 1.0) < 0.001


def test_compute_pmf_truncation():
    pmf = compute_pmf(mu=6.0, family="poisson")
    assert len(pmf) >= 50


# ---------------------------------------------------------------------------
# Task 1: p_over tests
# ---------------------------------------------------------------------------


def test_p_over_exact():
    pmf = [0.1, 0.2, 0.3, 0.25, 0.15]
    # P(X > 2.5) = P(X >= 3) = pmf[3] + pmf[4] = 0.25 + 0.15 = 0.40
    result = p_over(pmf, 2.5)
    assert abs(result - 0.40) < 1e-9


def test_p_over_integer():
    pmf = [0.1, 0.2, 0.3, 0.25, 0.15]
    # P(X > 2.0) = P(X >= 3) = pmf[3] + pmf[4] = 0.25 + 0.15 = 0.40
    # strictly greater than 2 means k_min = int(2.0) + 1 = 3
    result = p_over(pmf, 2.0)
    assert abs(result - 0.40) < 1e-9


def test_p_over_beyond():
    pmf = [0.5, 0.5]
    # P(X > 5.0) = 0 since PMF only has indices 0 and 1
    result = p_over(pmf, 5.0)
    assert result == 0.0


# ---------------------------------------------------------------------------
# Task 1: PROP_REGISTRY tests
# ---------------------------------------------------------------------------

from src.props import PROP_REGISTRY


def test_prop_registry():
    assert "aces" in PROP_REGISTRY
    assert "games_won" in PROP_REGISTRY
    assert "double_faults" in PROP_REGISTRY
    for key in ("aces", "games_won", "double_faults"):
        entry = PROP_REGISTRY[key]
        assert "train" in entry
        assert "predict" in entry
        assert callable(entry["train"])
        assert callable(entry["predict"])


# ---------------------------------------------------------------------------
# Task 2: GLM model tests (implemented in Task 2)
# ---------------------------------------------------------------------------


def _make_test_db_with_data(n_matches: int = 25):
    """Create an in-memory DB with enough test data for GLM training."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    # Create tables (minimal schema for props training)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            first_name TEXT,
            last_name TEXT,
            PRIMARY KEY (player_id, tour)
        );

        CREATE TABLE IF NOT EXISTS matches (
            tourney_id TEXT NOT NULL,
            match_num INTEGER NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            winner_id INTEGER,
            loser_id INTEGER,
            score TEXT,
            tourney_date TEXT NOT NULL,
            surface TEXT,
            tourney_level TEXT,
            match_type TEXT NOT NULL DEFAULT 'completed',
            retirement_flag INTEGER NOT NULL DEFAULT 0,
            stats_normalized INTEGER NOT NULL DEFAULT 0,
            stats_missing INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tourney_id, match_num, tour)
        );

        CREATE TABLE IF NOT EXISTS match_stats (
            tourney_id TEXT NOT NULL,
            match_num INTEGER NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            player_role TEXT NOT NULL,
            ace INTEGER,
            df INTEGER,
            svpt INTEGER,
            first_in INTEGER,
            first_won INTEGER,
            second_won INTEGER,
            sv_gms INTEGER,
            bp_saved INTEGER,
            bp_faced INTEGER,
            PRIMARY KEY (tourney_id, match_num, tour, player_role)
        );

        CREATE TABLE IF NOT EXISTS match_features (
            tourney_id TEXT NOT NULL,
            match_num INTEGER NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            player_role TEXT NOT NULL,
            elo_hard REAL, elo_hard_rd REAL,
            elo_clay REAL, elo_clay_rd REAL,
            elo_grass REAL, elo_grass_rd REAL,
            elo_overall REAL, elo_overall_rd REAL,
            h2h_wins INTEGER, h2h_losses INTEGER,
            h2h_surface_wins INTEGER, h2h_surface_losses INTEGER,
            form_win_rate_10 REAL, form_win_rate_20 REAL,
            avg_ace_rate REAL,
            avg_df_rate REAL,
            avg_first_pct REAL,
            avg_first_won_pct REAL,
            ranking INTEGER, ranking_delta INTEGER,
            days_since_last INTEGER, sets_last_7_days INTEGER,
            tourney_level TEXT, surface TEXT,
            sentiment_score REAL,
            pinnacle_prob_winner REAL,
            pinnacle_prob_loser REAL,
            has_no_pinnacle INTEGER,
            PRIMARY KEY (tourney_id, match_num, tour, player_role)
        );

        CREATE TABLE IF NOT EXISTS tournaments (
            tourney_id TEXT NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            tourney_name TEXT,
            surface TEXT,
            tourney_level TEXT,
            tourney_date TEXT,
            PRIMARY KEY (tourney_id, tour)
        );

        CREATE TABLE IF NOT EXISTS prop_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour TEXT NOT NULL DEFAULT 'ATP',
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            stat_type TEXT NOT NULL,
            tourney_id TEXT,
            match_num INTEGER,
            match_date TEXT NOT NULL,
            mu REAL NOT NULL,
            pmf_json TEXT NOT NULL,
            model_version TEXT NOT NULL,
            predicted_at TEXT NOT NULL,
            actual_value INTEGER,
            resolved_at TEXT,
            UNIQUE (tour, player_id, stat_type, match_date)
        );

        CREATE TABLE IF NOT EXISTS court_speed_index (
            tourney_id   TEXT NOT NULL,
            tour         TEXT NOT NULL DEFAULT 'ATP',
            surface      TEXT,
            csi_value    REAL NOT NULL,
            n_matches    INTEGER NOT NULL,
            computed_at  TEXT NOT NULL,
            PRIMARY KEY (tourney_id, tour)
        );
    """)

    # Insert players
    conn.execute("INSERT OR IGNORE INTO players VALUES (1001, 'ATP', 'Roger', 'Federer')")
    conn.execute("INSERT OR IGNORE INTO players VALUES (1002, 'ATP', 'Rafael', 'Nadal')")

    import random
    random.seed(42)
    surfaces = ["Hard", "Clay", "Grass"]
    levels = ["A", "G", "M"]

    for i in range(n_matches):
        surface = surfaces[i % 3]
        level = levels[i % 3]
        tourney_id = f"2023-T{i:03d}"
        date_str = f"2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"

        conn.execute("""
            INSERT OR IGNORE INTO tournaments
            (tourney_id, tour, tourney_name, surface, tourney_level, tourney_date)
            VALUES (?, 'ATP', 'Test Open', ?, ?, ?)
        """, (tourney_id, surface, level, date_str))

        conn.execute("""
            INSERT OR IGNORE INTO matches
            (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, surface, tourney_level, match_type)
            VALUES (?, 1, 'ATP', 1001, 1002, '6-3 7-5', ?, ?, ?, 'completed')
        """, (tourney_id, date_str, surface, level))

        # Winner stats
        aces_w = random.randint(3, 15)
        df_w = random.randint(1, 6)
        svpt_w = random.randint(50, 90)
        first_won_w = random.randint(20, 40)
        second_won_w = random.randint(10, 20)

        conn.execute("""
            INSERT OR IGNORE INTO match_stats
            (tourney_id, match_num, tour, player_role, ace, df, svpt, first_in, first_won, second_won, sv_gms)
            VALUES (?, 1, 'ATP', 'winner', ?, ?, ?, ?, ?, ?, 8)
        """, (tourney_id, aces_w, df_w, svpt_w, svpt_w // 2, first_won_w, second_won_w))

        # Loser stats
        aces_l = random.randint(2, 10)
        df_l = random.randint(1, 8)
        svpt_l = random.randint(45, 85)
        first_won_l = random.randint(15, 35)
        second_won_l = random.randint(8, 18)

        conn.execute("""
            INSERT OR IGNORE INTO match_stats
            (tourney_id, match_num, tour, player_role, ace, df, svpt, first_in, first_won, second_won, sv_gms)
            VALUES (?, 1, 'ATP', 'loser', ?, ?, ?, ?, ?, ?, 8)
        """, (tourney_id, aces_l, df_l, svpt_l, svpt_l // 2, first_won_l, second_won_l))

        # Winner match_features
        conn.execute("""
            INSERT OR IGNORE INTO match_features
            (tourney_id, match_num, tour, player_role,
             avg_ace_rate, avg_df_rate, avg_first_pct, avg_first_won_pct,
             surface, tourney_level, elo_overall, ranking, form_win_rate_10)
            VALUES (?, 1, 'ATP', 'winner', ?, ?, 0.60, 0.72, ?, ?, 1600.0, 3, 0.65)
        """, (tourney_id, aces_w / svpt_w, df_w / svpt_w, surface, level))

        # Loser match_features
        conn.execute("""
            INSERT OR IGNORE INTO match_features
            (tourney_id, match_num, tour, player_role,
             avg_ace_rate, avg_df_rate, avg_first_pct, avg_first_won_pct,
             surface, tourney_level, elo_overall, ranking, form_win_rate_10)
            VALUES (?, 1, 'ATP', 'loser', ?, ?, 0.58, 0.68, ?, ?, 1550.0, 5, 0.45)
        """, (tourney_id, aces_l / svpt_l, df_l / svpt_l, surface, level))

    conn.commit()
    return conn


def test_aces_train_predict():
    """Test aces train() and predict() end-to-end with in-memory DB."""
    import src.props.aces as aces_mod
    conn = _make_test_db_with_data(25)
    trained = aces_mod.train(conn)
    assert "model" in trained
    assert "family" in trained
    assert "aic" in trained

    feature_row = {
        "avg_ace_rate": 0.10,
        "opp_rtn_pct": 0.35,
        "surface": "Hard",
        "tourney_level": "A",
    }
    result = aces_mod.predict(trained, feature_row)
    assert "pmf" in result
    assert "mu" in result
    pmf = result["pmf"]
    assert isinstance(pmf, list)
    assert result["mu"] > 0
    assert abs(sum(pmf) - 1.0) < 0.01


def test_games_won_uses_score_parser():
    """Verify games_won._build_training_df filters out RET matches."""
    import src.props.games_won as gw_mod
    conn = _make_test_db_with_data(25)
    # Add a retirement match
    conn.execute("""
        INSERT OR IGNORE INTO matches
        (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, surface, tourney_level, match_type)
        VALUES ('RET-T001', 1, 'ATP', 1001, 1002, '6-3 4-2 RET', '2023-06-15', 'Clay', 'A', 'retirement')
    """)
    conn.commit()
    df = gw_mod._build_training_df(conn)
    # Retirement match should not appear in training data
    assert len(df) > 0
    # All scores should be parseable (no RET) — games_won column must be non-null
    for _, row in df.iterrows():
        assert row["games_won"] is not None


def test_schema_has_prop_predictions():
    """Verify prop_predictions table is created by init_db."""
    import tempfile
    import os
    from src.db.connection import init_db, get_connection
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prop_predictions'"
        ).fetchone()
        assert row is not None, "prop_predictions table not found in schema"
        conn.close()
    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# Phase 15 Plan 01: Time-decay weights and updated predict_and_store tests
# ---------------------------------------------------------------------------


def test_time_decay_weights():
    """compute_time_weights returns valid weights for a list of date strings."""
    from src.model.base import compute_time_weights

    dates = ["2023-01-01", "2023-07-01", "2024-01-01"]
    weights = compute_time_weights(dates, half_life_days=365)
    assert len(weights) == 3
    # All weights should be positive
    assert all(w > 0 for w in weights)
    # Most recent date should have the highest weight
    assert weights[-1] >= weights[0]
    # Weights should be <= 1.0
    assert all(w <= 1.0 for w in weights)


def test_predict_and_store_includes_csi_features():
    """predict_and_store query compiles without SQL errors using DB with CSI table."""
    import src.props.aces as aces_mod
    from src.props.base import predict_and_store

    conn = _make_test_db_with_data(25)
    # Train aces model first
    trained = aces_mod.train(conn)
    # predict_and_store should execute without SQL errors (includes court_speed_index JOIN)
    result = predict_and_store(conn, stat_types=["aces"], date_from="2023-01-01", date_to="2025-12-31")
    # Should succeed and produce predictions
    assert result["predicted"] >= 0
    assert "aces" in result["stat_types"]


# ---------------------------------------------------------------------------
# Task 3: predict_and_store and CLI tests (implemented in Task 3)
# ---------------------------------------------------------------------------


def test_predict_and_store():
    """Test predict_and_store writes rows to prop_predictions."""
    import src.props.aces as aces_mod
    from src.props.base import predict_and_store

    conn = _make_test_db_with_data(25)
    # Train aces model first
    trained = aces_mod.train(conn)
    # predict_and_store for aces only
    result = predict_and_store(conn, stat_types=["aces"], date_from="2023-01-01", date_to="2025-12-31")
    assert result["predicted"] > 0
    rows = conn.execute("SELECT * FROM prop_predictions WHERE stat_type='aces'").fetchall()
    assert len(rows) > 0
    for row in rows:
        assert row["mu"] is not None
        pmf = json.loads(row["pmf_json"])
        assert isinstance(pmf, list)
        assert abs(sum(pmf) - 1.0) < 0.01
        assert row["predicted_at"] is not None


def test_predict_and_store_no_model(monkeypatch, tmp_path):
    """predict_and_store with no saved model should return predicted=0 gracefully."""
    import src.props.base as base_mod
    from src.props.base import predict_and_store

    # Point PROP_MODEL_DIR at a temp dir with no models
    monkeypatch.setattr(base_mod, "PROP_MODEL_DIR", str(tmp_path))
    conn = _make_test_db_with_data(5)
    result = predict_and_store(conn, stat_types=["aces"], date_from="2023-01-01", date_to="2023-12-31")
    # No saved model -> graceful skip -> predicted=0
    assert result["predicted"] == 0


def test_cli_predict_help():
    """CLI predict --help exits 0 and contains --date-from."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "src.props", "predict", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--date-from" in result.stdout


# ---------------------------------------------------------------------------
# Task 4 (Plan 02): Resolver tests
# ---------------------------------------------------------------------------


def _make_resolver_db():
    """Create minimal in-memory DB with prop_predictions + match data for resolver tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            tourney_id TEXT NOT NULL,
            match_num INTEGER NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            winner_id INTEGER,
            loser_id INTEGER,
            score TEXT,
            tourney_date TEXT NOT NULL,
            match_type TEXT NOT NULL DEFAULT 'completed',
            retirement_flag INTEGER NOT NULL DEFAULT 0,
            stats_normalized INTEGER NOT NULL DEFAULT 0,
            stats_missing INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tourney_id, match_num, tour)
        );

        CREATE TABLE IF NOT EXISTS match_stats (
            tourney_id TEXT NOT NULL,
            match_num INTEGER NOT NULL,
            tour TEXT NOT NULL DEFAULT 'ATP',
            player_role TEXT NOT NULL,
            ace INTEGER,
            df INTEGER,
            svpt INTEGER,
            first_in INTEGER,
            first_won INTEGER,
            second_won INTEGER,
            sv_gms INTEGER,
            bp_saved INTEGER,
            bp_faced INTEGER,
            PRIMARY KEY (tourney_id, match_num, tour, player_role)
        );

        CREATE TABLE IF NOT EXISTS prop_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour TEXT NOT NULL DEFAULT 'ATP',
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            stat_type TEXT NOT NULL,
            tourney_id TEXT,
            match_num INTEGER,
            match_date TEXT NOT NULL,
            mu REAL NOT NULL,
            pmf_json TEXT NOT NULL,
            model_version TEXT NOT NULL,
            predicted_at TEXT NOT NULL,
            actual_value INTEGER,
            resolved_at TEXT,
            UNIQUE (tour, player_id, stat_type, match_date)
        );
    """)
    conn.commit()
    return conn


def test_resolve_props():
    """resolve_props resolves aces prediction when match_stats data is available."""
    from src.props.resolver import resolve_props

    conn = _make_resolver_db()

    # Insert match with winner_id=1001
    conn.execute("""
        INSERT INTO matches (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, match_type)
        VALUES ('T001', 1, 'ATP', 1001, 1002, '6-3 7-5', '2024-01-15', 'completed')
    """)
    # Insert match_stats for the winner
    conn.execute("""
        INSERT INTO match_stats (tourney_id, match_num, tour, player_role, ace, df, svpt)
        VALUES ('T001', 1, 'ATP', 'winner', 7, 3, 60)
    """)
    # Insert unresolved prop prediction
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'aces', '2024-01-15', 6.5, '[0.1, 0.2, 0.3]', 'aces_v1', '2024-01-14T00:00:00')
    """)
    conn.commit()

    result = resolve_props(conn)

    assert result["resolved"] == 1
    assert result["skipped"] == 0

    row = conn.execute("SELECT actual_value, resolved_at FROM prop_predictions WHERE player_id=1001").fetchone()
    assert row["actual_value"] == 7
    assert row["resolved_at"] is not None


def test_resolve_props_games_won():
    """resolve_props resolves games_won by parsing match score for winner and loser."""
    from src.props.resolver import resolve_props

    conn = _make_resolver_db()

    # Insert match: winner_id=1001, loser_id=1002, score="6-3 7-5" -> (13, 8)
    conn.execute("""
        INSERT INTO matches (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, match_type)
        VALUES ('T002', 1, 'ATP', 1001, 1002, '6-3 7-5', '2024-02-10', 'completed')
    """)

    # Winner prediction (should get 13 games)
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'games_won', '2024-02-10', 12.0, '[0.1]', 'games_won_v1', '2024-02-09T00:00:00')
    """)
    # Loser prediction (should get 8 games)
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1002, 'Rafael Nadal', 'games_won', '2024-02-10', 8.0, '[0.1]', 'games_won_v1', '2024-02-09T00:00:00')
    """)
    conn.commit()

    result = resolve_props(conn)

    assert result["resolved"] == 2
    assert result["skipped"] == 0

    winner_row = conn.execute(
        "SELECT actual_value FROM prop_predictions WHERE player_id=1001 AND stat_type='games_won'"
    ).fetchone()
    loser_row = conn.execute(
        "SELECT actual_value FROM prop_predictions WHERE player_id=1002 AND stat_type='games_won'"
    ).fetchone()

    assert winner_row["actual_value"] == 13
    assert loser_row["actual_value"] == 8


def test_resolve_props_skips_unmatched():
    """resolve_props skips predictions where no matching match data exists."""
    from src.props.resolver import resolve_props

    conn = _make_resolver_db()

    # Insert prediction with no corresponding match data
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 9999, 'Unknown Player', 'aces', '2024-03-01', 5.0, '[0.1]', 'aces_v1', '2024-03-01T00:00:00')
    """)
    conn.commit()

    result = resolve_props(conn)

    assert result["resolved"] == 0
    assert result["skipped"] == 1

    row = conn.execute("SELECT actual_value FROM prop_predictions WHERE player_id=9999").fetchone()
    assert row["actual_value"] is None


# ---------------------------------------------------------------------------
# Plan 02, Task 5: GET /props and GET /props/accuracy endpoint tests
# ---------------------------------------------------------------------------


def _seed_props_in_db(db_path: str):
    """Seed prop_predictions and prop_lines into the test DB via raw sqlite3."""
    import sqlite3, json as _json
    from src.props.base import compute_pmf

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    # Insert a player
    conn.execute("INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name) VALUES (1001, 'ATP', 'Roger', 'Federer')")

    # Insert a prop_prediction for aces
    pmf = compute_pmf(6.5, "poisson")
    conn.execute("""
        INSERT OR IGNORE INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'aces', '2024-05-01', 6.5, ?, 'aces_v1', '2024-04-30T00:00:00')
    """, (_json.dumps(pmf),))

    # Insert a matching prop_line for that prediction
    conn.execute("""
        INSERT OR IGNORE INTO prop_lines
        (tour, player_id, player_name, stat_type, line_value, direction, match_date, bookmaker, entered_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'aces', 5.5, 'over', '2024-05-01', 'prizepicks', '2024-04-30T00:00:00')
    """)

    conn.commit()
    conn.close()


def _seed_resolved_props_in_db(db_path: str):
    """Seed resolved prop_predictions + prop_lines for accuracy tests."""
    import sqlite3, json as _json
    from src.props.base import compute_pmf

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute("INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name) VALUES (2001, 'ATP', 'Test', 'Player')")

    pmf = compute_pmf(6.0, "poisson")
    # Resolved prediction (actual_value=8 > line_value=5.5 over -> hit)
    conn.execute("""
        INSERT OR IGNORE INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version,
         predicted_at, actual_value, resolved_at)
        VALUES ('ATP', 2001, 'Test Player', 'aces', '2024-06-01', 6.0, ?, 'aces_v1',
                '2024-05-31T00:00:00', 8, '2024-06-02T00:00:00')
    """, (_json.dumps(pmf),))

    conn.execute("""
        INSERT OR IGNORE INTO prop_lines
        (tour, player_id, player_name, stat_type, line_value, direction, match_date, bookmaker, entered_at)
        VALUES ('ATP', 2001, 'Test Player', 'aces', 5.5, 'over', '2024-06-01', 'prizepicks', '2024-05-31T00:00:00')
    """)

    conn.commit()
    conn.close()


async def test_get_props_status(async_client, tmp_path):
    """GET /props returns status='ok' (not 'not_available') when predictions exist."""
    # Seed data into the test DB used by the fixture
    import inspect
    from httpx import AsyncClient
    # Get the db_path from the app state via the client transport
    app = async_client._transport.app
    db_path = app.state.db_path

    _seed_props_in_db(db_path)

    response = await async_client.get("/api/v1/props")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0
    # Verify p_hit is present (computed from PMF + line_value)
    row = data["data"][0]
    assert "p_hit" in row
    assert row["p_hit"] is not None
    assert 0.0 <= row["p_hit"] <= 1.0


async def test_get_props_empty_ok(async_client):
    """GET /props returns status='ok' with empty data when no predictions exist."""
    response = await async_client.get("/api/v1/props")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["data"] == []


async def test_accuracy_kpis(async_client):
    """GET /props/accuracy returns accuracy metrics when resolved data exists."""
    app = async_client._transport.app
    db_path = app.state.db_path

    _seed_resolved_props_in_db(db_path)

    response = await async_client.get("/api/v1/props/accuracy")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["total_tracked"] == 1
    assert data["overall_hit_rate"] is not None
    # actual_value=8 > line_value=5.5 -> hit -> 100% hit rate
    assert data["overall_hit_rate"] == 1.0
    assert "hit_rate_by_stat" in data
    assert "rolling_30d" in data
    assert len(data["rolling_30d"]) > 0
    assert "calibration_bins" in data


async def test_accuracy_empty_ok(async_client):
    """GET /props/accuracy returns ok with zero total_tracked when no resolved data."""
    response = await async_client.get("/api/v1/props/accuracy")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["total_tracked"] == 0
    assert data["overall_hit_rate"] is None


# ---------------------------------------------------------------------------
# Phase 15, Plan 02: New stat type parser tests
# ---------------------------------------------------------------------------

from src.props.score_parser import parse_sets, parse_first_set_winner


def test_parse_sets():
    """parse_sets extracts (winner_sets, loser_sets) from score strings."""
    assert parse_sets("6-3 7-5") == (2, 0)
    assert parse_sets("7-6(5) 3-6 6-4") == (2, 1)
    assert parse_sets("6-3 6-4 6-2") == (3, 0)
    assert parse_sets("RET") is None
    assert parse_sets("") is None
    assert parse_sets(None) is None
    assert parse_sets("W/O") is None


def test_parse_first_set_winner():
    """parse_first_set_winner identifies who won the first set."""
    # Match winner also won first set
    assert parse_first_set_winner("6-3 7-5") == 1
    # Match loser won first set (match went 3 sets)
    assert parse_first_set_winner("3-6 7-5 6-3") == 0
    # Tiebreak first set won by match winner
    assert parse_first_set_winner("7-6(5) 6-3") == 1
    # Invalid / retirement
    assert parse_first_set_winner("RET") is None
    assert parse_first_set_winner("") is None
    assert parse_first_set_winner(None) is None


# ---------------------------------------------------------------------------
# Phase 15, Plan 02: PROP_REGISTRY 6-type test
# ---------------------------------------------------------------------------


def test_prop_registry_has_6_types():
    """PROP_REGISTRY contains exactly 6 stat type entries."""
    from src.props import PROP_REGISTRY
    assert len(PROP_REGISTRY) == 6
    expected_keys = {"aces", "double_faults", "games_won", "breaks_of_serve", "sets_won", "first_set_winner"}
    assert set(PROP_REGISTRY.keys()) == expected_keys
    for key in expected_keys:
        entry = PROP_REGISTRY[key]
        assert callable(entry["train"]), f"train for {key} not callable"
        assert callable(entry["predict"]), f"predict for {key} not callable"


# ---------------------------------------------------------------------------
# Phase 15, Plan 02: New model train/predict tests
# ---------------------------------------------------------------------------


def _make_test_db_with_bos_data(n_matches: int = 25):
    """
    Create in-memory DB with bp_faced/bp_saved data for breaks_of_serve training.
    Extends _make_test_db_with_data with bp columns.
    """
    import random
    conn = _make_test_db_with_data(n_matches)
    random.seed(99)

    # Update match_stats to add bp_faced/bp_saved columns
    rows = conn.execute("SELECT tourney_id, match_num, tour, player_role FROM match_stats").fetchall()
    for row in rows:
        bp_faced = random.randint(2, 8)
        bp_saved = random.randint(0, bp_faced)
        conn.execute(
            "UPDATE match_stats SET bp_faced=?, bp_saved=? WHERE tourney_id=? AND match_num=? AND tour=? AND player_role=?",
            (bp_faced, bp_saved, row["tourney_id"], row["match_num"], row["tour"], row["player_role"]),
        )
    conn.commit()
    return conn


def test_breaks_of_serve_train_predict():
    """breaks_of_serve train() and predict() work end-to-end."""
    import src.props.breaks_of_serve as bos_mod
    conn = _make_test_db_with_bos_data(25)
    trained = bos_mod.train(conn)
    assert "model" in trained
    assert "family" in trained
    assert "alpha" in trained
    assert "aic" in trained

    feature_row = {
        "avg_df_rate": 0.05,
        "opp_rtn_pct": 0.40,
        "surface": "Clay",
        "tourney_level": "G",
    }
    result = bos_mod.predict(trained, feature_row)
    assert "pmf" in result
    assert "mu" in result
    assert isinstance(result["pmf"], list)
    assert result["mu"] > 0
    assert abs(sum(result["pmf"]) - 1.0) < 0.01


def test_sets_won_train_predict():
    """sets_won train() and predict() work end-to-end with max_k=6."""
    import src.props.sets_won as sw_mod
    conn = _make_test_db_with_data(25)
    trained = sw_mod.train(conn)
    assert "model" in trained
    assert "family" in trained

    feature_row = {
        "avg_ace_rate": 0.08,
        "opp_rtn_pct": 0.35,
        "surface": "Hard",
        "tourney_level": "A",
        "best_of": 3,
    }
    result = sw_mod.predict(trained, feature_row)
    assert "pmf" in result
    assert "mu" in result
    # max_k=6 means pmf has 7 entries (0..6)
    assert len(result["pmf"]) <= 7
    assert result["mu"] > 0
    assert abs(sum(result["pmf"]) - 1.0) < 0.01


def test_first_set_winner_train_predict():
    """first_set_winner train() and predict() work end-to-end."""
    import src.props.first_set_winner as fsw_mod
    conn = _make_test_db_with_data(25)
    trained = fsw_mod.train(conn)
    assert "model" in trained
    assert trained["family"] == "logistic"

    feature_row = {
        "avg_ace_rate": 0.10,
        "opp_rtn_pct": 0.35,
        "surface": "Grass",
        "tourney_level": "G",
    }
    result = fsw_mod.predict(trained, feature_row)
    assert "pmf" in result
    assert "mu" in result
    # Must be exactly 2-element PMF
    assert len(result["pmf"]) == 2
    # Probabilities must sum to 1
    assert abs(sum(result["pmf"]) - 1.0) < 1e-9
    # mu must be between 0 and 1
    assert 0.0 <= result["mu"] <= 1.0


# ---------------------------------------------------------------------------
# Phase 15, Plan 02: Resolver tests for new stat types
# ---------------------------------------------------------------------------


def test_resolve_props_breaks_of_serve():
    """resolve_props resolves breaks_of_serve: bp_faced=5, bp_saved=3 -> actual_value=2."""
    from src.props.resolver import resolve_props

    conn = _make_resolver_db()

    # Insert match with winner_id=1001
    conn.execute("""
        INSERT INTO matches (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, match_type)
        VALUES ('T010', 1, 'ATP', 1001, 1002, '6-3 7-5', '2024-05-01', 'completed')
    """)
    # Insert match_stats with bp data
    conn.execute("""
        INSERT INTO match_stats (tourney_id, match_num, tour, player_role, ace, df, svpt, bp_faced, bp_saved)
        VALUES ('T010', 1, 'ATP', 'winner', 5, 2, 60, 5, 3)
    """)
    # Insert unresolved prop prediction for breaks_of_serve
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'breaks_of_serve', '2024-05-01', 2.0, '[0.1, 0.3, 0.3, 0.2, 0.1]', 'poisson_v1', '2024-05-01T00:00:00')
    """)
    conn.commit()

    result = resolve_props(conn)
    assert result["resolved"] >= 1

    row = conn.execute(
        "SELECT actual_value FROM prop_predictions WHERE player_id=1001 AND stat_type='breaks_of_serve'"
    ).fetchone()
    assert row["actual_value"] == 2  # bp_faced(5) - bp_saved(3) = 2


def test_resolve_props_sets_won():
    """resolve_props resolves sets_won for winner (2) and loser (0) from '6-3 7-5'."""
    from src.props.resolver import resolve_props

    conn = _make_resolver_db()

    conn.execute("""
        INSERT INTO matches (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, match_type)
        VALUES ('T011', 1, 'ATP', 1001, 1002, '6-3 7-5', '2024-06-01', 'completed')
    """)
    # Winner prediction
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'sets_won', '2024-06-01', 1.8, '[0.05, 0.1, 0.6, 0.15, 0.05, 0.04, 0.01]', 'poisson_v1', '2024-06-01T00:00:00')
    """)
    # Loser prediction
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1002, 'Rafael Nadal', 'sets_won', '2024-06-01', 0.5, '[0.6, 0.3, 0.05, 0.03, 0.01, 0.01]', 'poisson_v1', '2024-06-01T00:00:00')
    """)
    conn.commit()

    result = resolve_props(conn)
    assert result["resolved"] == 2

    winner_row = conn.execute(
        "SELECT actual_value FROM prop_predictions WHERE player_id=1001 AND stat_type='sets_won'"
    ).fetchone()
    loser_row = conn.execute(
        "SELECT actual_value FROM prop_predictions WHERE player_id=1002 AND stat_type='sets_won'"
    ).fetchone()
    assert winner_row["actual_value"] == 2  # match winner won 2 sets
    assert loser_row["actual_value"] == 0   # loser won 0 sets in a 2-0 scoreline


def test_resolve_props_first_set_winner():
    """resolve_props resolves first_set_winner: match winner (1001) won first set -> 1."""
    from src.props.resolver import resolve_props

    conn = _make_resolver_db()

    # Score "6-3 7-5": match winner (1001) won both sets including first set
    conn.execute("""
        INSERT INTO matches (tourney_id, match_num, tour, winner_id, loser_id, score, tourney_date, match_type)
        VALUES ('T012', 1, 'ATP', 1001, 1002, '6-3 7-5', '2024-07-01', 'completed')
    """)
    # Winner prediction
    conn.execute("""
        INSERT INTO prop_predictions
        (tour, player_id, player_name, stat_type, match_date, mu, pmf_json, model_version, predicted_at)
        VALUES ('ATP', 1001, 'Roger Federer', 'first_set_winner', '2024-07-01', 0.65, '[0.35, 0.65]', 'logistic_v1', '2024-07-01T00:00:00')
    """)
    conn.commit()

    result = resolve_props(conn)
    assert result["resolved"] >= 1

    row = conn.execute(
        "SELECT actual_value FROM prop_predictions WHERE player_id=1001 AND stat_type='first_set_winner'"
    ).fetchone()
    assert row["actual_value"] == 1  # match winner won first set


# ---------------------------------------------------------------------------
# Phase 15, Plan 03: GET /props/backtest endpoint tests
# ---------------------------------------------------------------------------


def _seed_backtest_props_in_db(db_path: str):
    """Seed resolved prop_predictions (no prop_lines join needed) for backtest tests."""
    import sqlite3 as _sqlite3
    import json as _json
    from src.props.base import compute_pmf

    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name) VALUES (3001, 'ATP', 'Back', 'Test')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name) VALUES (3002, 'ATP', 'Back', 'Test2')"
    )

    pmf_aces = compute_pmf(6.0, "poisson")
    pmf_games = compute_pmf(12.0, "poisson")

    # Insert 3 resolved aces predictions (2023+) and 3 games_won predictions (2023+)
    aces_data = [
        (3001, "aces", "2023-03-01", 6.0, 8),   # actual > mu -> hit
        (3001, "aces", "2023-06-15", 6.0, 5),   # actual <= mu -> miss
        (3001, "aces", "2023-09-10", 6.0, 7),   # actual > mu -> hit
    ]
    games_data = [
        (3002, "games_won", "2023-04-01", 12.0, 14),  # hit
        (3002, "games_won", "2023-07-20", 12.0, 10),  # miss
        (3002, "games_won", "2023-10-05", 12.0, 13),  # hit
    ]

    for player_id, stat_type, match_date, mu, actual_value in aces_data:
        pmf_json = _json.dumps(pmf_aces)
        conn.execute("""
            INSERT OR IGNORE INTO prop_predictions
            (tour, player_id, player_name, stat_type, match_date, mu, pmf_json,
             model_version, predicted_at, actual_value, resolved_at)
            VALUES ('ATP', ?, 'Test Player', ?, ?, ?, ?, 'aces_v1',
                    '2023-01-01T00:00:00', ?, '2023-01-02T00:00:00')
        """, (player_id, stat_type, match_date, mu, pmf_json, actual_value))

    for player_id, stat_type, match_date, mu, actual_value in games_data:
        pmf_json = _json.dumps(pmf_games)
        conn.execute("""
            INSERT OR IGNORE INTO prop_predictions
            (tour, player_id, player_name, stat_type, match_date, mu, pmf_json,
             model_version, predicted_at, actual_value, resolved_at)
            VALUES ('ATP', ?, 'Test Player2', ?, ?, ?, ?, 'games_won_v1',
                    '2023-01-01T00:00:00', ?, '2023-01-02T00:00:00')
        """, (player_id, stat_type, match_date, mu, pmf_json, actual_value))

    conn.commit()
    conn.close()


async def test_get_props_backtest(async_client):
    """GET /props/backtest returns valid structure with 2023+ resolved predictions."""
    app = async_client._transport.app
    db_path = app.state.db_path

    _seed_backtest_props_in_db(db_path)

    response = await async_client.get("/api/v1/props/backtest")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["date_from"] == "2023-01-01"
    assert data["total_tracked"] >= 6

    # by_stat_type must be a list with required fields
    assert isinstance(data["by_stat_type"], list)
    assert len(data["by_stat_type"]) >= 2
    for row in data["by_stat_type"]:
        assert "stat_type" in row
        assert "hit_rate" in row
        assert "n" in row
        assert "avg_p_hit" in row
        assert "calibration_score" in row
        assert 0.0 <= row["hit_rate"] <= 1.0
        assert row["n"] > 0

    # calibration_bins must be a list with required fields
    assert isinstance(data["calibration_bins"], list)
    for bin_row in data["calibration_bins"]:
        assert "stat_type" in bin_row
        assert "predicted_p" in bin_row
        assert "actual_hit_rate" in bin_row
        assert "n" in bin_row

    # rolling_hit_rate list
    assert isinstance(data["rolling_hit_rate"], list)


async def test_get_props_backtest_empty(async_client):
    """GET /props/backtest returns ok with empty lists when no resolved predictions exist."""
    response = await async_client.get("/api/v1/props/backtest")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["total_tracked"] == 0
    assert data["by_stat_type"] == []
    assert data["calibration_bins"] == []
    assert data["rolling_hit_rate"] == []


def test_valid_stat_types_expanded():
    """_VALID_STAT_TYPES contains all 6 stat types."""
    from src.api.routers.props import _VALID_STAT_TYPES
    expected = {"aces", "games_won", "double_faults", "breaks_of_serve", "sets_won", "first_set_winner"}
    assert expected == _VALID_STAT_TYPES, f"_VALID_STAT_TYPES mismatch: {_VALID_STAT_TYPES}"
