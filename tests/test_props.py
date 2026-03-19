"""
Unit tests for src/props package.

Task 1: score_parser, compute_pmf, p_over, PROP_REGISTRY (all pass)
Task 2: GLM model training/prediction, schema (unskipped in Task 2)
Task 3: predict_and_store, CLI (unskipped in Task 3)
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
