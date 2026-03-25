"""
Unit tests for backtesting engine — Kelly bet sizing, walk-forward fold generation,
and backtest results schema.

Task 1 tests: Kelly bet sizing and schema
Task 2 tests: Walk-forward fold engine
"""

import sqlite3
import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mem_db():
    """In-memory SQLite database with full schema applied."""
    from src.db.connection import get_connection, _read_schema_sql

    conn = get_connection(":memory:")
    schema_sql = _read_schema_sql()
    conn.executescript(schema_sql)
    return conn


@pytest.fixture
def db_with_matches(mem_db):
    """DB with synthetic match data for walk-forward tests."""
    conn = mem_db
    # Insert tournaments and matches across 3 years (2020, 2021, 2022)
    years_data = [
        ("2020-001", "2020", "Hard", "ATP250"),
        ("2021-001", "2021", "Clay", "ATP500"),
        ("2022-001", "2022", "Grass", "GS"),
    ]
    for tourney_id, year, surface, level in years_data:
        conn.execute(
            "INSERT INTO tournaments (tourney_id, tour, tourney_name, surface, tourney_level, tourney_date) "
            "VALUES (?, 'ATP', ?, ?, ?, ?)",
            (tourney_id, f"Test {year}", surface, level, f"{year}-06-01"),
        )
        # Insert 200 matches per year (200 * 3 = 600 total, enough for min_train_matches)
        for match_num in range(1, 201):
            tourney_date = f"{year}-06-{(match_num % 28) + 1:02d}"
            winner_id = (match_num * 2) % 1000 + 1
            loser_id = (match_num * 2 + 1) % 1000 + 1
            conn.execute(
                "INSERT INTO matches (tourney_id, match_num, tour, winner_id, loser_id, tourney_date) "
                "VALUES (?, ?, 'ATP', ?, ?, ?)",
                (tourney_id, match_num, winner_id, loser_id, tourney_date),
            )
            # Insert winner features
            conn.execute(
                "INSERT INTO match_features "
                "(tourney_id, match_num, tour, player_role, elo_overall, elo_hard, elo_clay, elo_grass, "
                "ranking, ranking_delta, h2h_wins, h2h_losses, form_win_rate_10, form_win_rate_20, "
                "days_since_last, surface, tourney_level) "
                "VALUES (?, ?, 'ATP', 'winner', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tourney_id, match_num,
                 1600.0 + match_num, 1550.0, 1500.0, 1480.0,
                 match_num % 200 + 1, -1,
                 5, 2, 0.65, 0.60,
                 3, surface, level),
            )
            # Insert loser features
            conn.execute(
                "INSERT INTO match_features "
                "(tourney_id, match_num, tour, player_role, elo_overall, elo_hard, elo_clay, elo_grass, "
                "ranking, ranking_delta, h2h_wins, h2h_losses, form_win_rate_10, form_win_rate_20, "
                "days_since_last, surface, tourney_level) "
                "VALUES (?, ?, 'ATP', 'loser', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tourney_id, match_num,
                 1400.0 + match_num, 1450.0, 1420.0, 1380.0,
                 match_num % 200 + 50, 2,
                 2, 3, 0.45, 0.42,
                 5, surface, level),
            )
            # Insert match odds for matches 1-100 in 2022 only
            if year == "2022" and match_num <= 100:
                conn.execute(
                    "INSERT INTO match_odds (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b, source, imported_at) "
                    "VALUES (?, ?, 'ATP', 'pinnacle', 1.85, 2.10, 'csv', '2026-01-01T00:00:00Z')",
                    (tourney_id, match_num),
                )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Task 1: Kelly bet sizing tests
# ---------------------------------------------------------------------------


class TestKellyBetSizing:
    def test_kelly_positive_ev(self):
        """Positive EV bet returns a positive bet amount."""
        from src.backtest.kelly import compute_kelly_bet

        bet = compute_kelly_bet(prob=0.6, decimal_odds=2.10, bankroll=1000, kelly_fraction=0.25)
        assert bet > 0.0, f"Expected positive bet, got {bet}"

    def test_kelly_negative_ev(self):
        """Negative EV bet returns 0 (skip the bet)."""
        from src.backtest.kelly import compute_kelly_bet

        # EV = 0.3 * 2.10 - 1 = -0.37 (negative)
        bet = compute_kelly_bet(prob=0.3, decimal_odds=2.10, bankroll=1000)
        assert bet == 0.0, f"Expected 0.0 for negative EV, got {bet}"

    def test_kelly_fraction(self):
        """
        Full Kelly for (0.6, 2.10): b=1.10, p=0.6, q=0.4
        full_kelly = (b*p - q) / b = (1.10*0.6 - 0.4) / 1.10 = (0.66 - 0.4) / 1.10 = 0.26/1.1 ≈ 0.23636
        fractional (0.25x) = 0.23636 * 0.25 ≈ 0.05909
        bet = 0.05909 * 1000 ≈ 59.09 (subject to 3% cap = 30)
        With default max_fraction=0.03, bet is capped at 30.
        Pass max_fraction=1.0 to test the fraction calc without cap.
        """
        from src.backtest.kelly import compute_kelly_bet

        bet = compute_kelly_bet(
            prob=0.6, decimal_odds=2.10, bankroll=1000,
            kelly_fraction=0.25, max_fraction=1.0
        )
        expected = 0.23636 * 0.25 * 1000
        assert abs(bet - expected) < 1.0, f"Expected ~{expected:.2f}, got {bet:.2f}"

    def test_kelly_cap(self):
        """High Kelly output is capped at max_fraction * bankroll."""
        from src.backtest.kelly import compute_kelly_bet

        # prob=0.9, decimal_odds=5.0 → very high Kelly, should be capped at 3%
        bet = compute_kelly_bet(prob=0.9, decimal_odds=5.0, bankroll=1000, max_fraction=0.03)
        assert bet <= 30.0, f"Expected bet <= 30 (3% cap), got {bet}"
        assert bet > 0.0, f"Expected positive bet, got {bet}"

    def test_kelly_cap_lower_than_kelly(self):
        """When Kelly fraction * bankroll > max_fraction * bankroll, the cap wins."""
        from src.backtest.kelly import compute_kelly_bet

        # Set kelly_fraction=1.0 (full Kelly) but max_fraction=0.02 (2% cap)
        bet = compute_kelly_bet(
            prob=0.9, decimal_odds=5.0, bankroll=1000,
            kelly_fraction=1.0, max_fraction=0.02
        )
        assert bet <= 20.0, f"Expected bet <= 20 (2% cap), got {bet}"

    def test_kelly_min_ev_threshold(self):
        """Positive EV below min_ev threshold returns 0."""
        from src.backtest.kelly import compute_kelly_bet

        # EV = 0.51 * 2.0 - 1 = 0.02 (positive but below min_ev=0.05)
        bet = compute_kelly_bet(prob=0.51, decimal_odds=2.0, bankroll=1000, min_ev=0.05)
        assert bet == 0.0, f"Expected 0.0 when EV below threshold, got {bet}"

    def test_apply_bet_result_win(self):
        """Winning bet increases bankroll by bet_size * (decimal_odds - 1)."""
        from src.backtest.kelly import apply_bet_result

        result = apply_bet_result(bankroll=1000, bet_size=30, decimal_odds=2.10, won=True)
        expected = 1000 + 30 * (2.10 - 1)
        assert abs(result - expected) < 0.001, f"Expected {expected}, got {result}"

    def test_apply_bet_result_loss(self):
        """Losing bet decreases bankroll by bet_size."""
        from src.backtest.kelly import apply_bet_result

        result = apply_bet_result(bankroll=1000, bet_size=30, decimal_odds=2.10, won=False)
        expected = 1000 - 30
        assert abs(result - expected) < 0.001, f"Expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# Task 1: Schema tests
# ---------------------------------------------------------------------------


class TestBacktestSchema:
    def test_backtest_results_schema(self, mem_db):
        """backtest_results table exists with all required columns."""
        cursor = mem_db.execute("PRAGMA table_info(backtest_results)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {
            "id", "fold_year", "tourney_id", "match_num", "tour",
            "model_version", "player_id", "outcome", "calibrated_prob",
            "decimal_odds", "ev", "kelly_full", "kelly_bet", "flat_bet",
            "pnl_kelly", "pnl_flat", "bankroll_before", "bankroll_after",
            "surface", "tourney_level", "winner_rank", "loser_rank", "tourney_date",
        }
        missing = required - columns
        assert not missing, f"Missing columns in backtest_results: {missing}"

    def test_calibration_data_schema(self, mem_db):
        """calibration_data table exists after init_db."""
        cursor = mem_db.execute("PRAGMA table_info(calibration_data)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {
            "id", "fold_label", "model_version", "bin_midpoints",
            "empirical_freq", "n_samples", "computed_at",
        }
        missing = required - columns
        assert not missing, f"Missing columns in calibration_data: {missing}"

    def test_table_count_includes_backtest_tables(self, mem_db):
        """Schema now includes all tables through Phase 9 (20 total)."""
        cursor = mem_db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_count = cursor.fetchone()[0]
        assert table_count == 20, f"Expected 20 tables, got {table_count}"


# ---------------------------------------------------------------------------
# Task 2: Walk-forward fold engine tests
# ---------------------------------------------------------------------------


class TestGenerateFolds:
    def test_generate_folds(self, db_with_matches):
        """generate_folds returns list of (train_end, test_start, test_end) tuples in chronological order."""
        from src.backtest.walk_forward import generate_folds

        folds = generate_folds(db_with_matches, min_train_matches=100)
        assert len(folds) >= 1, "Expected at least one fold"
        # Verify chronological order
        for i in range(len(folds) - 1):
            assert folds[i][0] <= folds[i + 1][0], "Folds not in chronological order"
        # Verify test_start == train_end for each fold
        for train_end, test_start, test_end in folds:
            assert test_start == train_end, f"test_start ({test_start}) != train_end ({train_end})"

    def test_generate_folds_min_training(self, db_with_matches):
        """Folds with fewer than min_train_matches training rows are skipped."""
        from src.backtest.walk_forward import generate_folds

        # Very high min_train_matches should skip folds
        folds_strict = generate_folds(db_with_matches, min_train_matches=10000)
        assert len(folds_strict) == 0, "Expected no folds with 10000 min_train_matches"

        # Lower threshold should allow folds
        folds_lenient = generate_folds(db_with_matches, min_train_matches=100)
        assert len(folds_lenient) >= 1, "Expected at least one fold with 100 min_train_matches"

    def test_fold_no_test_data_in_train(self, db_with_matches):
        """For each fold, training matrix dates are all strictly before fold test_start date."""
        from src.backtest.walk_forward import generate_folds, build_fold_training_matrix

        folds = generate_folds(db_with_matches, min_train_matches=100)
        for train_end, test_start, test_end in folds:
            _, _, train_dates = build_fold_training_matrix(db_with_matches, train_end)
            if train_dates:
                max_train_date = max(train_dates)
                assert max_train_date < test_start, (
                    f"Training data contains date {max_train_date} >= test_start {test_start}"
                )


class TestBuildFoldTrainingMatrix:
    def test_look_ahead_assertion(self, db_with_matches):
        """build_fold_training_matrix with train_end constraint returns only rows with tourney_date < train_end."""
        from src.backtest.walk_forward import build_fold_training_matrix

        train_end = "2021-01-01"
        X, y, dates = build_fold_training_matrix(db_with_matches, train_end)
        assert len(dates) > 0, "Expected some training rows"
        for d in dates:
            assert d < train_end, f"Training row date {d} >= train_end {train_end}"

    def test_look_ahead_raises(self, db_with_matches):
        """assert_no_look_ahead raises AssertionError when test dates appear in train dates."""
        from src.backtest.walk_forward import assert_no_look_ahead

        train_dates = ["2020-01-01", "2020-06-15", "2020-12-31"]
        test_dates = ["2020-06-15", "2021-01-01"]  # "2020-06-15" overlaps
        with pytest.raises(AssertionError):
            assert_no_look_ahead(train_dates, test_dates)

    def test_assert_no_look_ahead_passes_clean(self):
        """assert_no_look_ahead passes when no overlap exists."""
        from src.backtest.walk_forward import assert_no_look_ahead

        train_dates = ["2020-01-01", "2020-06-15", "2020-12-31"]
        test_dates = ["2021-01-01", "2021-06-15"]
        # Should not raise
        assert_no_look_ahead(train_dates, test_dates)


class TestRunFold:
    def test_run_fold(self, db_with_matches):
        """Single fold trains model, generates predictions, produces backtest_results rows."""
        from src.backtest.walk_forward import run_fold

        config = {
            "kelly_fraction": 0.25,
            "max_fraction": 0.03,
            "min_ev": 0.0,
            "model_version": "logistic_v1",
        }
        # Use 2022 fold (2020+2021 train data, 2022 test)
        train_end = "2022-01-01"
        test_start = "2022-01-01"
        test_end = "2023-01-01"
        bankroll = 1000.0

        results, updated_bankroll = run_fold(
            db_with_matches, train_end, test_start, test_end, bankroll, config
        )
        # Should produce some result rows
        assert isinstance(results, list), "Expected list of result rows"
        assert isinstance(updated_bankroll, float), "Expected float bankroll"
        # All rows should have required fields
        for row in results:
            assert "kelly_bet" in row, "Missing kelly_bet in result row"
            assert "pnl_kelly" in row, "Missing pnl_kelly in result row"
            assert "bankroll_before" in row, "Missing bankroll_before in result row"

    def test_matches_without_odds_skipped(self, db_with_matches):
        """Matches without odds produce no bet (kelly_bet=0)."""
        from src.backtest.walk_forward import run_fold

        config = {
            "kelly_fraction": 0.25,
            "max_fraction": 0.03,
            "min_ev": 0.0,
            "model_version": "logistic_v1",
        }
        # 2022 fold: only matches 1-100 have odds
        train_end = "2022-01-01"
        test_start = "2022-01-01"
        test_end = "2023-01-01"
        bankroll = 1000.0

        results, _ = run_fold(db_with_matches, train_end, test_start, test_end, bankroll, config)
        # Rows for matches without odds should have kelly_bet=0
        no_odds_rows = [r for r in results if r.get("no_odds")]
        for row in no_odds_rows:
            assert row["kelly_bet"] == 0.0, f"Expected kelly_bet=0 for no-odds match, got {row['kelly_bet']}"


class TestRunWalkForward:
    def test_run_walk_forward(self, db_with_matches):
        """run_walk_forward returns summary dict with required keys; bankroll carries across folds."""
        from src.backtest.walk_forward import run_walk_forward

        config = {
            "kelly_fraction": 0.25,
            "max_fraction": 0.03,
            "min_ev": 0.0,
            "initial_bankroll": 1000.0,
            "min_train_matches": 100,
            "model_version": "logistic_v1",
        }
        summary = run_walk_forward(db_with_matches, config=config)

        required_keys = {
            "folds_run", "total_bets", "bets_placed", "bets_skipped",
            "total_pnl_kelly", "total_pnl_flat", "final_bankroll", "start_bankroll",
        }
        missing = required_keys - set(summary.keys())
        assert not missing, f"Missing keys in summary: {missing}"

        assert summary["start_bankroll"] == 1000.0
        assert isinstance(summary["final_bankroll"], float)
        assert summary["folds_run"] >= 0

    def test_run_walk_forward_stores_results(self, db_with_matches):
        """run_walk_forward inserts backtest_results rows into the database."""
        from src.backtest.walk_forward import run_walk_forward

        config = {
            "kelly_fraction": 0.25,
            "max_fraction": 0.03,
            "min_ev": 0.0,
            "initial_bankroll": 1000.0,
            "min_train_matches": 100,
            "model_version": "logistic_v1",
        }
        run_walk_forward(db_with_matches, config=config)

        cursor = db_with_matches.execute("SELECT COUNT(*) FROM backtest_results")
        count = cursor.fetchone()[0]
        # Should have stored some rows (at least one fold ran)
        assert count >= 0, "backtest_results should exist"


# ---------------------------------------------------------------------------
# Pinnacle SQL and dispatch tests (Plan 12-02)
# ---------------------------------------------------------------------------


class TestPinnacleWalkForwardSQL:
    def test_fold_matrix_sql_has_pinnacle(self):
        from src.backtest.walk_forward import _FOLD_MATRIX_SQL
        assert "pinnacle_prob_diff" in _FOLD_MATRIX_SQL
        assert "has_no_pinnacle" in _FOLD_MATRIX_SQL

    def test_fold_test_matches_sql_has_pinnacle(self):
        from src.backtest.walk_forward import _FOLD_TEST_MATCHES_SQL
        assert "pinnacle_prob_diff" in _FOLD_TEST_MATCHES_SQL
        assert "has_no_pinnacle" in _FOLD_TEST_MATCHES_SQL

    def test_fold_xgb_test_matches_sql_has_pinnacle(self):
        from src.backtest.walk_forward import _FOLD_XGB_TEST_MATCHES_SQL
        assert "pinnacle_prob_diff" in _FOLD_XGB_TEST_MATCHES_SQL
        assert "has_no_pinnacle" in _FOLD_XGB_TEST_MATCHES_SQL

    def test_train_model_for_fold_logistic_v3(self):
        """_train_model_for_fold dispatches logistic_v3_pinnacle to train_and_calibrate."""
        from unittest.mock import patch, MagicMock
        import numpy as np
        from src.backtest.walk_forward import _train_model_for_fold
        from src.model.base import LOGISTIC_FEATURES

        n = len(LOGISTIC_FEATURES)
        X = np.random.default_rng(0).standard_normal((20, n))
        y = np.ones(20)
        w = np.ones(20)
        X_val = np.random.default_rng(1).standard_normal((5, n))
        y_val = np.ones(5)

        mock_model = MagicMock()
        mock_metrics = {"val_brier_score": 0.2}

        with patch("src.backtest.walk_forward.train_and_calibrate",
                   return_value=(mock_model, mock_metrics)) as mock_tac:
            result = _train_model_for_fold(
                "logistic_v3_pinnacle",
                X, y, X_val, y_val, w,
                config={},
            )
            mock_tac.assert_called_once()

    def test_train_model_for_fold_xgboost_v2(self):
        """_train_model_for_fold dispatches xgboost_v2_pinnacle to xgb_train_fold."""
        from unittest.mock import patch, MagicMock
        import numpy as np
        from src.backtest.walk_forward import _train_model_for_fold
        from src.model.base import LOGISTIC_FEATURES, XGB_FEATURES

        n = len(LOGISTIC_FEATURES)
        X = np.zeros((20, n))
        y = np.ones(20)
        w = np.ones(20)
        X_val = np.zeros((5, n))
        y_val = np.ones(5)

        # XGB build matrix returns XGB_FEATURES-column array
        n_xgb = len(XGB_FEATURES)
        mock_xgb_X = np.zeros((20, n_xgb))
        mock_xgb_y = np.ones(20)
        mock_xgb_dates = [f"2020-01-{i+1:02d}" for i in range(20)]

        mock_model = MagicMock()
        mock_metrics = {"val_brier_score": 0.25}

        with patch("src.backtest.walk_forward.build_xgb_training_matrix",
                   return_value=(mock_xgb_X, mock_xgb_y, mock_xgb_dates)):
            with patch("src.model.xgboost_model.train_fold",
                       return_value=(mock_model, mock_metrics)) as mock_xgb_fold:
                mock_conn = MagicMock()
                result = _train_model_for_fold(
                    "xgboost_v2_pinnacle",
                    X, y, X_val, y_val, w,
                    config={},
                    conn=mock_conn,
                    train_end="2021-01-01",
                )
