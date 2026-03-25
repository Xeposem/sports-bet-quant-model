"""
Tests for src/model/trainer.py, src/model/metrics.py, and src/model/predictor.py.
Uses in-memory SQLite with schema applied. Synthetic data only — no real DB.
"""
import sqlite3
import tempfile
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "db", "schema.sql")


def make_conn() -> sqlite3.Connection:
    """In-memory SQLite connection with full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH) as f:
        sql = f.read()
    # Remove PRAGMA journal_mode=WAL (not valid for :memory:)
    lines = [l for l in sql.splitlines() if "journal_mode" not in l]
    conn.executescript("\n".join(lines))
    return conn


def insert_match(conn, tourney_id="T001", match_num=1, tourney_date="2020-06-15",
                 winner_id=1, loser_id=2):
    """Insert a tournament, match, and optionally match_features rows."""
    conn.execute(
        "INSERT OR IGNORE INTO tournaments (tourney_id, tour, tourney_name, tourney_date) "
        "VALUES (?, 'ATP', 'Test Open', ?)",
        (tourney_id, tourney_date),
    )
    conn.execute(
        "INSERT OR IGNORE INTO matches "
        "(tourney_id, match_num, tour, winner_id, loser_id, tourney_date) "
        "VALUES (?, ?, 'ATP', ?, ?, ?)",
        (tourney_id, match_num, winner_id, loser_id, tourney_date),
    )
    conn.commit()


def insert_features(
    conn,
    tourney_id,
    match_num,
    role,
    elo_overall=1600.0,
    elo_hard=1550.0,
    elo_clay=1520.0,
    elo_grass=1510.0,
    ranking=50,
    ranking_delta=2,
    h2h_wins=3,
    h2h_losses=1,
    form_win_rate_10=0.7,
    form_win_rate_20=0.65,
    days_since_last=5,
):
    conn.execute(
        """INSERT OR REPLACE INTO match_features
           (tourney_id, match_num, tour, player_role,
            elo_overall, elo_hard, elo_clay, elo_grass,
            ranking, ranking_delta,
            h2h_wins, h2h_losses,
            form_win_rate_10, form_win_rate_20,
            days_since_last, sets_last_7_days)
           VALUES (?, ?, 'ATP', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (
            tourney_id,
            match_num,
            role,
            elo_overall,
            elo_hard,
            elo_clay,
            elo_grass,
            ranking,
            ranking_delta,
            h2h_wins,
            h2h_losses,
            form_win_rate_10,
            form_win_rate_20,
            days_since_last,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Task 1 tests: build_training_matrix
# ---------------------------------------------------------------------------


class TestBuildTrainingMatrix:
    def test_returns_tuple_of_three(self):
        from src.model.trainer import build_training_matrix

        conn = make_conn()
        insert_match(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)
        X, y, dates = build_training_matrix(conn)
        assert isinstance(X, np.ndarray)
        assert isinstance(y, np.ndarray)
        assert isinstance(dates, list)

    def test_y_all_ones(self):
        """Label is always 1 (winner-perspective differential)."""
        from src.model.trainer import build_training_matrix

        conn = make_conn()
        for i in range(3):
            d = f"2020-0{i+1}-15"
            insert_match(conn, tourney_id=f"T00{i}", match_num=i + 1, tourney_date=d)
            insert_features(conn, f"T00{i}", i + 1, "winner")
            insert_features(conn, f"T00{i}", i + 1, "loser", elo_overall=1450.0)
        X, y, dates = build_training_matrix(conn)
        assert np.all(y == 1)

    def test_feature_differential_correct(self):
        """X row = winner_features - loser_features for elo_diff."""
        from src.model.trainer import build_training_matrix, LOGISTIC_FEATURES

        conn = make_conn()
        insert_match(conn)
        # Winner has elo_overall=1700, loser=1500 => diff=200
        insert_features(conn, "T001", 1, "winner", elo_overall=1700.0)
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0)
        X, y, dates = build_training_matrix(conn)
        assert X.shape[0] == 1
        assert X.shape[1] == len(LOGISTIC_FEATURES)
        elo_idx = LOGISTIC_FEATURES.index("elo_diff")
        assert abs(X[0, elo_idx] - 200.0) < 1e-6

    def test_h2h_balance_winner_perspective(self):
        """h2h_balance = winner.h2h_wins - winner.h2h_losses."""
        from src.model.trainer import build_training_matrix, LOGISTIC_FEATURES

        conn = make_conn()
        insert_match(conn)
        # winner: 5 wins, 2 losses => balance=3
        insert_features(conn, "T001", 1, "winner", h2h_wins=5, h2h_losses=2)
        insert_features(conn, "T001", 1, "loser")
        X, y, dates = build_training_matrix(conn)
        h2h_idx = LOGISTIC_FEATURES.index("h2h_balance")
        assert abs(X[0, h2h_idx] - 3.0) < 1e-6

    def test_has_no_elo_w_flag_when_elo_1500(self):
        """has_no_elo_w=1 when winner elo_overall == 1500."""
        from src.model.trainer import build_training_matrix, LOGISTIC_FEATURES

        conn = make_conn()
        insert_match(conn)
        insert_features(conn, "T001", 1, "winner", elo_overall=1500.0)
        insert_features(conn, "T001", 1, "loser", elo_overall=1450.0)
        X, y, dates = build_training_matrix(conn)
        flag_idx = LOGISTIC_FEATURES.index("has_no_elo_w")
        assert X[0, flag_idx] == 1.0

    def test_has_no_elo_l_flag_when_elo_1500(self):
        """has_no_elo_l=1 when loser elo_overall == 1500."""
        from src.model.trainer import build_training_matrix, LOGISTIC_FEATURES

        conn = make_conn()
        insert_match(conn)
        insert_features(conn, "T001", 1, "winner", elo_overall=1700.0)
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0)
        X, y, dates = build_training_matrix(conn)
        flag_idx = LOGISTIC_FEATURES.index("has_no_elo_l")
        assert X[0, flag_idx] == 1.0

    def test_null_elo_imputed_as_1500(self):
        """NULL elo_overall should result in elo_diff=0 (both default to 1500)."""
        from src.model.trainer import build_training_matrix, LOGISTIC_FEATURES

        conn = make_conn()
        insert_match(conn)
        conn.execute(
            """INSERT OR REPLACE INTO match_features
               (tourney_id, match_num, tour, player_role,
                elo_overall, ranking, h2h_wins, h2h_losses,
                form_win_rate_10, form_win_rate_20, days_since_last)
               VALUES ('T001', 1, 'ATP', 'winner', NULL, 50, 0, 0, 0.5, 0.5, 5)"""
        )
        conn.execute(
            """INSERT OR REPLACE INTO match_features
               (tourney_id, match_num, tour, player_role,
                elo_overall, ranking, h2h_wins, h2h_losses,
                form_win_rate_10, form_win_rate_20, days_since_last)
               VALUES ('T001', 1, 'ATP', 'loser', NULL, 80, 0, 0, 0.5, 0.5, 5)"""
        )
        conn.commit()
        X, y, dates = build_training_matrix(conn)
        elo_idx = LOGISTIC_FEATURES.index("elo_diff")
        # Both NULL -> both become 1500 -> diff = 0
        assert abs(X[0, elo_idx]) < 1e-6

    def test_ordering_by_date(self):
        """Rows are ordered by tourney_date ascending."""
        from src.model.trainer import build_training_matrix

        conn = make_conn()
        dates_in = ["2021-06-01", "2019-03-10", "2020-11-20"]
        for i, d in enumerate(dates_in):
            insert_match(conn, tourney_id=f"T{i:03d}", match_num=i + 1, tourney_date=d)
            insert_features(conn, f"T{i:03d}", i + 1, "winner")
            insert_features(conn, f"T{i:03d}", i + 1, "loser", elo_overall=1450.0)
        X, y, dates = build_training_matrix(conn)
        assert dates == sorted(dates)

    def test_returns_correct_number_of_rows(self):
        from src.model.trainer import build_training_matrix

        conn = make_conn()
        for i in range(5):
            d = f"2020-0{i+1}-15"
            insert_match(conn, tourney_id=f"T{i:03d}", match_num=i + 1, tourney_date=d)
            insert_features(conn, f"T{i:03d}", i + 1, "winner")
            insert_features(conn, f"T{i:03d}", i + 1, "loser", elo_overall=1450.0)
        X, y, dates = build_training_matrix(conn)
        assert X.shape[0] == 5
        assert len(y) == 5
        assert len(dates) == 5


# ---------------------------------------------------------------------------
# Task 1 tests: compute_time_weights
# ---------------------------------------------------------------------------


class TestComputeTimeWeights:
    def test_weight_one_for_reference_date(self):
        """Match on the reference date should have weight=1.0."""
        from src.model.trainer import compute_time_weights

        today = "2023-06-01"
        w = compute_time_weights(["2023-06-01"], reference_date=today)
        assert abs(w[0] - 1.0) < 1e-9

    def test_half_life_decay(self):
        """Match exactly 730 days before reference has weight ~0.5."""
        from src.model.trainer import compute_time_weights

        reference = "2023-06-01"
        ref_d = date.fromisoformat(reference)
        old_d = ref_d - timedelta(days=730)
        w = compute_time_weights([old_d.isoformat()], reference_date=reference)
        assert abs(w[0] - 0.5) < 0.01

    def test_floor_at_1e6(self):
        """Very old matches never produce zero weight (floor=1e-6)."""
        from src.model.trainer import compute_time_weights

        w = compute_time_weights(["1900-01-01"], reference_date="2023-01-01")
        assert w[0] >= 1e-6

    def test_monotonic_decay(self):
        """More recent matches get higher weights."""
        from src.model.trainer import compute_time_weights

        dates = ["2010-01-01", "2015-06-15", "2021-12-31"]
        ref = "2023-01-01"
        w = compute_time_weights(dates, reference_date=ref)
        assert w[0] < w[1] < w[2]

    def test_default_reference_is_max_date(self):
        """Without explicit reference_date, weights reference the max date in list."""
        from src.model.trainer import compute_time_weights

        dates = ["2020-01-01", "2021-01-01", "2022-01-01"]
        w = compute_time_weights(dates)
        # Max date (2022-01-01) should have weight 1.0
        assert abs(w[-1] - 1.0) < 1e-9

    def test_returns_numpy_array(self):
        from src.model.trainer import compute_time_weights

        w = compute_time_weights(["2020-01-01"], reference_date="2021-01-01")
        assert isinstance(w, np.ndarray)


# ---------------------------------------------------------------------------
# Task 1 tests: temporal_split
# ---------------------------------------------------------------------------


class TestTemporalSplit:
    def _make_data(self, n=10):
        """Create n synthetic samples with sequential dates."""
        X = np.random.rand(n, 5)
        y = np.ones(n)
        weights = np.ones(n)
        dates = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return X, y, weights, dates

    def test_split_preserves_80_20_ratio(self):
        from src.model.trainer import temporal_split

        X, y, w, dates = self._make_data(10)
        split = temporal_split(X, y, w, dates, train_ratio=0.8)
        assert split["X_train"].shape[0] == 8
        assert split["X_val"].shape[0] == 2

    def test_train_dates_all_before_val_dates(self):
        """No temporal leakage: all train dates < all val dates."""
        from src.model.trainer import temporal_split

        X, y, w, dates = self._make_data(20)
        split = temporal_split(X, y, w, dates)
        max_train = max(split["dates_train"])
        min_val = min(split["dates_val"])
        assert max_train < min_val

    def test_split_keys_present(self):
        from src.model.trainer import temporal_split

        X, y, w, dates = self._make_data(10)
        split = temporal_split(X, y, w, dates)
        for key in ["X_train", "y_train", "w_train", "X_val", "y_val", "dates_train", "dates_val"]:
            assert key in split

    def test_no_shuffling(self):
        """First train index is 0, last val index is n-1 (strict sequential)."""
        from src.model.trainer import temporal_split

        X, y, w, dates = self._make_data(10)
        split = temporal_split(X, y, w, dates, train_ratio=0.8)
        assert split["dates_train"][0] == dates[0]
        assert split["dates_val"][-1] == dates[-1]


# ---------------------------------------------------------------------------
# Task 2 tests: train_and_calibrate
# ---------------------------------------------------------------------------


def make_synthetic_data(n=300, seed=42):
    """
    Generate synthetic binary classification data with known separability.
    Returns X, y as numpy arrays.
    Uses 16 columns to match current LOGISTIC_FEATURES length (14 original + 2 pinnacle).
    """
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 16))
    # Simple linear boundary: positive if first feature > 0
    y = (X[:, 0] > 0).astype(float)
    return X, y


class TestTrainAndCalibrate:
    def test_returns_tuple(self):
        from src.model.trainer import train_and_calibrate

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        X_train, y_train = X[:n_train], y[:n_train]
        X_val, y_val = X[n_train:], y[n_train:]
        w = np.ones(n_train)
        result = train_and_calibrate(X_train, y_train, X_val, y_val, w)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_predict_proba_in_0_1(self):
        """Calibrated model outputs probabilities in [0, 1]."""
        from src.model.trainer import train_and_calibrate

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        X_train, y_train = X[:n_train], y[:n_train]
        X_val, y_val = X[n_train:], y[n_train:]
        w = np.ones(n_train)
        model, metrics = train_and_calibrate(X_train, y_train, X_val, y_val, w)
        proba = model.predict_proba(X_val)[:, 1]
        assert np.all(proba >= 0.0)
        assert np.all(proba <= 1.0)

    def test_metrics_keys_present(self):
        """Metrics dict must include all required keys."""
        from src.model.trainer import train_and_calibrate

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        X_train, y_train = X[:n_train], y[:n_train]
        X_val, y_val = X[n_train:], y[n_train:]
        w = np.ones(n_train)
        _, metrics = train_and_calibrate(X_train, y_train, X_val, y_val, w)
        for key in ["calibration_method", "val_brier_score", "val_log_loss",
                    "brier_sigmoid", "brier_isotonic"]:
            assert key in metrics, f"Missing key: {key}"

    def test_calibration_method_is_string(self):
        from src.model.trainer import train_and_calibrate

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        _, metrics = train_and_calibrate(
            X[:n_train], y[:n_train], X[n_train:], y[n_train:], np.ones(n_train)
        )
        assert metrics["calibration_method"] in ("sigmoid", "isotonic")

    def test_auto_selects_lower_brier(self):
        """Selected calibration method must correspond to lower Brier score."""
        from src.model.trainer import train_and_calibrate

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        _, metrics = train_and_calibrate(
            X[:n_train], y[:n_train], X[n_train:], y[n_train:], np.ones(n_train)
        )
        if metrics["calibration_method"] == "sigmoid":
            assert metrics["brier_sigmoid"] <= metrics["brier_isotonic"]
        else:
            assert metrics["brier_isotonic"] <= metrics["brier_sigmoid"]


# ---------------------------------------------------------------------------
# Task 2 tests: save_model / load_model
# ---------------------------------------------------------------------------


class TestModelSerialization:
    def test_round_trip_identical_predictions(self):
        """Loaded model must produce same predictions as original."""
        from src.model.trainer import train_and_calibrate, save_model, load_model

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        model, _ = train_and_calibrate(
            X[:n_train], y[:n_train], X[n_train:], y[n_train:], np.ones(n_train)
        )
        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
            path = f.name
        try:
            save_model(model, path)
            loaded = load_model(path)
            original_proba = model.predict_proba(X[n_train:])[:, 1]
            loaded_proba = loaded.predict_proba(X[n_train:])[:, 1]
            np.testing.assert_array_equal(original_proba, loaded_proba)
        finally:
            os.unlink(path)

    def test_saved_file_exists(self):
        from src.model.trainer import train_and_calibrate, save_model

        X, y = make_synthetic_data()
        n_train = int(0.8 * len(X))
        model, _ = train_and_calibrate(
            X[:n_train], y[:n_train], X[n_train:], y[n_train:], np.ones(n_train)
        )
        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
            path = f.name
        try:
            save_model(model, path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Task 2 tests: metrics.py
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    def test_returns_required_keys(self):
        from src.model.metrics import compute_metrics

        y_true = np.array([1.0, 0.0, 1.0, 0.0])
        y_prob = np.array([0.8, 0.2, 0.7, 0.3])
        result = compute_metrics(y_true, y_prob)
        assert "brier_score" in result
        assert "log_loss" in result
        assert "n_samples" in result

    def test_n_samples_correct(self):
        from src.model.metrics import compute_metrics

        y_true = np.array([1.0, 0.0, 1.0])
        y_prob = np.array([0.8, 0.2, 0.9])
        result = compute_metrics(y_true, y_prob)
        assert result["n_samples"] == 3

    def test_brier_score_is_float(self):
        from src.model.metrics import compute_metrics

        y_true = np.array([1.0, 0.0])
        y_prob = np.array([0.6, 0.4])
        result = compute_metrics(y_true, y_prob)
        assert isinstance(result["brier_score"], float)

    def test_brier_score_range(self):
        """Brier score must be in [0, 1]."""
        from src.model.metrics import compute_metrics

        y_true = np.array([1.0, 0.0, 1.0, 0.0])
        y_prob = np.array([0.9, 0.1, 0.8, 0.2])
        result = compute_metrics(y_true, y_prob)
        assert 0.0 <= result["brier_score"] <= 1.0

    def test_perfect_predictions_low_brier(self):
        """Perfect calibration should yield Brier close to 0."""
        from src.model.metrics import compute_metrics

        y_true = np.array([1.0, 1.0, 0.0, 0.0])
        y_prob = np.array([0.99, 0.99, 0.01, 0.01])
        result = compute_metrics(y_true, y_prob)
        assert result["brier_score"] < 0.01


class TestCalibrationCurveData:
    def test_returns_required_keys(self):
        from src.model.metrics import calibration_curve_data

        y_true = np.array([1, 0, 1, 0, 1, 1, 0, 0, 1, 0] * 5, dtype=float)
        y_prob = np.linspace(0.1, 0.9, 50)
        result = calibration_curve_data(y_true, y_prob, n_bins=5)
        assert "bin_midpoints" in result
        assert "empirical_freq" in result

    def test_returns_lists(self):
        from src.model.metrics import calibration_curve_data

        y_true = np.array([1, 0, 1, 0] * 10, dtype=float)
        y_prob = np.linspace(0.1, 0.9, 40)
        result = calibration_curve_data(y_true, y_prob)
        assert isinstance(result["bin_midpoints"], list)
        assert isinstance(result["empirical_freq"], list)

    def test_same_length_outputs(self):
        from src.model.metrics import calibration_curve_data

        y_true = np.array([1, 0, 1, 0] * 10, dtype=float)
        y_prob = np.linspace(0.1, 0.9, 40)
        result = calibration_curve_data(y_true, y_prob)
        assert len(result["bin_midpoints"]) == len(result["empirical_freq"])

    def test_empirical_freq_in_0_1(self):
        from src.model.metrics import calibration_curve_data

        y_true = np.array([1, 0, 1, 0] * 10, dtype=float)
        y_prob = np.linspace(0.1, 0.9, 40)
        result = calibration_curve_data(y_true, y_prob)
        for val in result["empirical_freq"]:
            assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# Task 3 tests: predictor.py — compute_ev, predict_match, predict_all_matches
# ---------------------------------------------------------------------------


def make_mock_model(prob_a=0.6):
    """Create a mock sklearn model whose predict_proba returns fixed probability."""
    mock = MagicMock()
    # predict_proba returns shape (1, 2): [[p_lose, p_win]]
    mock.predict_proba.return_value = np.array([[1.0 - prob_a, prob_a]])
    return mock


def insert_match_with_players(conn, tourney_id="T001", match_num=1,
                               tourney_date="2023-06-15",
                               winner_id=101, loser_id=102):
    """Insert a tournament and match with specific player IDs."""
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name) "
        "VALUES (?, 'ATP', 'PlayerA', 'Winner')",
        (winner_id,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, tour, first_name, last_name) "
        "VALUES (?, 'ATP', 'PlayerB', 'Loser')",
        (loser_id,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO tournaments (tourney_id, tour, tourney_name, tourney_date) "
        "VALUES (?, 'ATP', 'Test Open', ?)",
        (tourney_id, tourney_date),
    )
    conn.execute(
        "INSERT OR IGNORE INTO matches "
        "(tourney_id, match_num, tour, winner_id, loser_id, tourney_date) "
        "VALUES (?, ?, 'ATP', ?, ?, ?)",
        (tourney_id, match_num, winner_id, loser_id, tourney_date),
    )
    conn.commit()


def insert_match_odds_row(conn, tourney_id="T001", match_num=1,
                           decimal_odds_a=1.60, decimal_odds_b=2.40):
    """Insert Pinnacle odds row into match_odds."""
    conn.execute(
        """INSERT OR REPLACE INTO match_odds
           (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b, source, imported_at)
           VALUES (?, ?, 'ATP', 'pinnacle', ?, ?, 'csv', '2023-06-10T00:00:00Z')""",
        (tourney_id, match_num, decimal_odds_a, decimal_odds_b),
    )
    conn.commit()


class TestComputeEv:
    """compute_ev(calibrated_prob, decimal_odds) -> float."""

    def test_positive_ev(self):
        """compute_ev(0.6, 2.10) = (0.6 * 2.10) - 1 = 0.26."""
        from src.model.predictor import compute_ev

        result = compute_ev(0.6, 2.10)
        assert abs(result - 0.26) < 1e-9

    def test_negative_ev(self):
        """compute_ev(0.4, 2.10) = (0.4 * 2.10) - 1 = -0.16."""
        from src.model.predictor import compute_ev

        result = compute_ev(0.4, 2.10)
        assert abs(result - (-0.16)) < 1e-9

    def test_zero_ev(self):
        """compute_ev(0.5, 2.0) = 0.0 exactly (fair odds)."""
        from src.model.predictor import compute_ev

        result = compute_ev(0.5, 2.0)
        assert abs(result - 0.0) < 1e-9

    def test_returns_float(self):
        from src.model.predictor import compute_ev

        result = compute_ev(0.6, 1.80)
        assert isinstance(result, float)


class TestPredictMatch:
    """predict_match returns list of two prediction dicts, one per player."""

    def test_returns_two_predictions(self):
        """predict_match returns exactly 2 prediction dicts (one per player)."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        preds = predict_match(model, conn, "T001", 1)
        assert len(preds) == 2

    def test_probabilities_sum_to_one(self):
        """P(A wins) + P(B wins) = 1.0."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.65)
        preds = predict_match(model, conn, "T001", 1)
        probs = [p["calibrated_prob"] for p in preds]
        assert abs(sum(probs) - 1.0) < 1e-9

    def test_ev_computed_when_odds_present(self):
        """When Pinnacle odds are present, ev_value and edge are not None."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)
        insert_match_odds_row(conn, decimal_odds_a=1.60, decimal_odds_b=2.40)

        model = make_mock_model(prob_a=0.6)
        preds = predict_match(model, conn, "T001", 1)
        for pred in preds:
            assert pred["ev_value"] is not None
            assert pred["edge"] is not None
            assert pred["pinnacle_prob"] is not None
            assert pred["decimal_odds"] is not None

    def test_ev_null_when_no_odds(self):
        """When no Pinnacle odds exist, ev_value, edge, pinnacle_prob are None."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)
        # No match_odds inserted

        model = make_mock_model(prob_a=0.6)
        preds = predict_match(model, conn, "T001", 1)
        for pred in preds:
            assert pred["ev_value"] is None
            assert pred["edge"] is None
            assert pred["pinnacle_prob"] is None

    def test_prediction_has_required_keys(self):
        """Each prediction dict has all required schema columns."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        preds = predict_match(model, conn, "T001", 1)
        required_keys = {
            "tourney_id", "match_num", "tour", "player_id",
            "model_prob", "calibrated_prob",
            "pinnacle_prob", "decimal_odds", "ev_value", "edge", "predicted_at",
        }
        for pred in preds:
            for key in required_keys:
                assert key in pred, f"Missing key: {key}"

    def test_ev_formula_correct_with_known_odds(self):
        """When model gives P(A)=0.6 and decimal_odds_a=2.10, EV for A = 0.26."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn, winner_id=101, loser_id=102)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)
        insert_match_odds_row(conn, decimal_odds_a=2.10, decimal_odds_b=1.80)

        model = make_mock_model(prob_a=0.6)
        preds = predict_match(model, conn, "T001", 1)
        # Winner player (player_id=101) gets P=0.6, odds=2.10
        winner_pred = next(p for p in preds if p["player_id"] == 101)
        assert abs(winner_pred["ev_value"] - 0.26) < 1e-6

    def test_brier_contribution_when_outcome_known(self):
        """brier_contribution = (calibrated_prob - outcome)^2 when outcome known."""
        from src.model.predictor import predict_match

        conn = make_conn()
        insert_match_with_players(conn, winner_id=101, loser_id=102)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        preds = predict_match(model, conn, "T001", 1)
        winner_pred = next(p for p in preds if p["player_id"] == 101)
        # Winner has outcome=1, prob=0.6 => brier = (0.6-1)^2 = 0.16
        assert winner_pred["brier_contribution"] is not None
        assert abs(winner_pred["brier_contribution"] - 0.16) < 1e-6


class TestStorePrediction:
    """store_prediction writes to predictions table idempotently."""

    def test_store_prediction_inserts_row(self):
        """store_prediction inserts prediction row into DB."""
        from src.model.predictor import store_prediction

        conn = make_conn()
        insert_match_with_players(conn)

        pred = {
            "tourney_id": "T001",
            "match_num": 1,
            "tour": "ATP",
            "player_id": 101,
            "model_version": "logistic_v1",
            "model_prob": 0.62,
            "calibrated_prob": 0.60,
            "brier_contribution": 0.16,
            "log_loss_contribution": 0.51,
            "pinnacle_prob": 0.58,
            "decimal_odds": 1.60,
            "ev_value": 0.04,
            "edge": 0.02,
            "predicted_at": "2023-06-15T10:00:00Z",
        }
        store_prediction(conn, pred)

        row = conn.execute(
            "SELECT * FROM predictions WHERE tourney_id=? AND match_num=? AND player_id=?",
            ("T001", 1, 101),
        ).fetchone()
        assert row is not None
        assert abs(row["calibrated_prob"] - 0.60) < 1e-9
        assert abs(row["ev_value"] - 0.04) < 1e-9

    def test_store_prediction_is_idempotent(self):
        """Calling store_prediction twice does not duplicate the row."""
        from src.model.predictor import store_prediction

        conn = make_conn()
        insert_match_with_players(conn)

        pred = {
            "tourney_id": "T001",
            "match_num": 1,
            "tour": "ATP",
            "player_id": 101,
            "model_version": "logistic_v1",
            "model_prob": 0.62,
            "calibrated_prob": 0.60,
            "brier_contribution": None,
            "log_loss_contribution": None,
            "pinnacle_prob": None,
            "decimal_odds": None,
            "ev_value": None,
            "edge": None,
            "predicted_at": "2023-06-15T10:00:00Z",
        }
        store_prediction(conn, pred)
        # Update and re-store to check idempotency
        pred["calibrated_prob"] = 0.65
        store_prediction(conn, pred)

        count = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE tourney_id='T001' AND match_num=1"
        ).fetchone()[0]
        assert count == 1


class TestPredictAllMatches:
    """predict_all_matches processes all matches with features and returns stats."""

    def test_returns_stats_dict(self):
        """predict_all_matches returns dict with matches_predicted, predictions_stored, with_ev."""
        from src.model.predictor import predict_all_matches

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        result = predict_all_matches(model, conn, model_version="logistic_v1")
        assert "matches_predicted" in result
        assert "predictions_stored" in result
        assert "with_ev" in result

    def test_predictions_stored_in_db(self):
        """predict_all_matches actually inserts rows into predictions table."""
        from src.model.predictor import predict_all_matches

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        predict_all_matches(model, conn, model_version="logistic_v1")

        count = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        assert count == 2  # one per player

    def test_with_ev_counts_matches_with_odds(self):
        """with_ev counts matches that had Pinnacle odds."""
        from src.model.predictor import predict_all_matches

        conn = make_conn()
        # Match 1: with odds
        insert_match_with_players(conn, tourney_id="T001", match_num=1, winner_id=101, loser_id=102)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)
        insert_match_odds_row(conn, tourney_id="T001", match_num=1)

        # Match 2: without odds
        insert_match_with_players(conn, tourney_id="T002", match_num=2, winner_id=201, loser_id=202)
        insert_features(conn, "T002", 2, "winner")
        insert_features(conn, "T002", 2, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        result = predict_all_matches(model, conn, model_version="logistic_v1")
        assert result["matches_predicted"] == 2
        assert result["with_ev"] == 1  # only 1 match had odds

    def test_idempotent_reruns(self):
        """Running predict_all_matches twice does not duplicate rows."""
        from src.model.predictor import predict_all_matches

        conn = make_conn()
        insert_match_with_players(conn)
        insert_features(conn, "T001", 1, "winner")
        insert_features(conn, "T001", 1, "loser", elo_overall=1500.0, ranking=100)

        model = make_mock_model(prob_a=0.6)
        predict_all_matches(model, conn, model_version="logistic_v1")
        predict_all_matches(model, conn, model_version="logistic_v1")

        count = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        assert count == 2  # still just 2 rows (idempotent)


# ---------------------------------------------------------------------------
# Pinnacle feature constant tests (Plan 12-02)
# ---------------------------------------------------------------------------


class TestPinnacleFeatureConstants:
    def test_logistic_features_includes_pinnacle(self):
        from src.model.base import LOGISTIC_FEATURES
        assert "pinnacle_prob_diff" in LOGISTIC_FEATURES
        assert "has_no_pinnacle" in LOGISTIC_FEATURES
        assert len(LOGISTIC_FEATURES) == 16

    def test_build_matrix_sql_has_pinnacle(self):
        from src.model.base import _BUILD_MATRIX_SQL
        assert "pinnacle_prob_diff" in _BUILD_MATRIX_SQL
        assert "has_no_pinnacle" in _BUILD_MATRIX_SQL

    def test_non_diff_cols_has_no_pinnacle(self):
        """augment_with_flipped preserves has_no_pinnacle as non-differential."""
        from src.model.base import augment_with_flipped, LOGISTIC_FEATURES
        # Create 1-row X where has_no_pinnacle=1
        n_feat = len(LOGISTIC_FEATURES)
        X = np.zeros((1, n_feat))
        pinnacle_idx = LOGISTIC_FEATURES.index("has_no_pinnacle")
        X[0, pinnacle_idx] = 1.0
        y = np.ones(1)
        w = np.ones(1)
        X_aug, y_aug, w_aug = augment_with_flipped(X, y, w, LOGISTIC_FEATURES)
        # Flipped row (index 1) should preserve has_no_pinnacle=1 (not negated to -1)
        assert X_aug[1, pinnacle_idx] == 1.0, (
            f"has_no_pinnacle was negated in flipped row: got {X_aug[1, pinnacle_idx]}"
        )
