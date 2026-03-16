"""
Tests for feature computation modules.

Covers:
- FEAT-01: H2H record (h2h.py)
- FEAT-02: Rolling form and service stats (form.py)
- FEAT-03: Ranking and ranking delta (ranking.py)
- FEAT-04: Fatigue/scheduling features (fatigue.py)
- FEAT-06: Tournament level encoding (tourney.py)
- Temporal safety: look-ahead bias prevention tests
"""
import pytest
from tests.conftest import db_conn  # noqa: F401  imported for pytest fixture discovery


# ---------------------------------------------------------------------------
# Helpers: insert synthetic data into in-memory DB
# ---------------------------------------------------------------------------

def _insert_tournament(conn, tourney_id, surface="Hard", tourney_level="G", tourney_date="2024-01-01"):
    conn.execute(
        "INSERT OR IGNORE INTO tournaments(tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date) "
        "VALUES (?, 'ATP', 'Test Tournament', ?, 128, ?, ?)",
        (tourney_id, surface, tourney_level, tourney_date),
    )


def _insert_match(conn, tourney_id, match_num, winner_id, loser_id, score="6-3 6-4",
                  tourney_date="2024-01-10", match_type="completed", best_of=3):
    conn.execute(
        "INSERT OR IGNORE INTO matches(tourney_id, match_num, tour, winner_id, loser_id, score, round, "
        "best_of, minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing) "
        "VALUES (?, ?, 'ATP', ?, ?, ?, 'R32', ?, 90, ?, ?, 0, 0, 0)",
        (tourney_id, match_num, winner_id, loser_id, score, best_of, tourney_date, match_type),
    )


def _insert_match_stats(conn, tourney_id, match_num, player_role,
                        ace=5, df=2, svpt=60, first_in=36, first_won=28, second_won=14):
    conn.execute(
        "INSERT OR IGNORE INTO match_stats(tourney_id, match_num, tour, player_role, "
        "ace, df, svpt, first_in, first_won, second_won, sv_gms, bp_saved, bp_faced) "
        "VALUES (?, ?, 'ATP', ?, ?, ?, ?, ?, ?, ?, 8, 2, 3)",
        (tourney_id, match_num, player_role, ace, df, svpt, first_in, first_won, second_won),
    )


def _insert_ranking(conn, player_id, ranking_date, ranking, ranking_points=1000):
    conn.execute(
        "INSERT OR IGNORE INTO rankings(ranking_date, tour, player_id, ranking, ranking_points) "
        "VALUES (?, 'ATP', ?, ?, ?)",
        (ranking_date, player_id, ranking, ranking_points),
    )


# ---------------------------------------------------------------------------
# H2H Tests (FEAT-01)
# ---------------------------------------------------------------------------

class TestGetH2H:
    def test_no_prior_matches_returns_zeros(self, db_conn):
        """get_h2h returns (0, 0) when no prior matches exist between players."""
        from src.features.h2h import get_h2h
        result = get_h2h(db_conn, p1_id=1, p2_id=2, before_date="2024-01-01")
        assert result["p1_wins"] == 0
        assert result["p1_losses"] == 0
        assert result["total"] == 0

    def test_correct_wins_losses_from_history(self, db_conn):
        """get_h2h returns correct wins/losses from 3 historical matches."""
        from src.features.h2h import get_h2h
        _insert_tournament(db_conn, "T1", tourney_date="2023-06-01")
        _insert_tournament(db_conn, "T2", tourney_date="2023-08-01")
        _insert_tournament(db_conn, "T3", tourney_date="2023-10-01")
        # p1 wins twice, loses once
        _insert_match(db_conn, "T1", 1, winner_id=10, loser_id=20, tourney_date="2023-06-15")
        _insert_match(db_conn, "T2", 1, winner_id=10, loser_id=20, tourney_date="2023-08-15")
        _insert_match(db_conn, "T3", 1, winner_id=20, loser_id=10, tourney_date="2023-10-15")

        result = get_h2h(db_conn, p1_id=10, p2_id=20, before_date="2024-01-01")
        assert result["p1_wins"] == 2
        assert result["p1_losses"] == 1
        assert result["total"] == 3

    def test_surface_filter_returns_only_surface_records(self, db_conn):
        """get_h2h with surface filter returns only surface-specific records."""
        from src.features.h2h import get_h2h
        _insert_tournament(db_conn, "TH", surface="Hard", tourney_date="2023-06-01")
        _insert_tournament(db_conn, "TC", surface="Clay", tourney_date="2023-08-01")
        _insert_match(db_conn, "TH", 1, winner_id=10, loser_id=20, tourney_date="2023-06-15")
        _insert_match(db_conn, "TC", 1, winner_id=20, loser_id=10, tourney_date="2023-08-15")

        hard_result = get_h2h(db_conn, p1_id=10, p2_id=20, before_date="2024-01-01", surface="Hard")
        assert hard_result["p1_wins"] == 1
        assert hard_result["p1_losses"] == 0

        clay_result = get_h2h(db_conn, p1_id=10, p2_id=20, before_date="2024-01-01", surface="Clay")
        assert clay_result["p1_wins"] == 0
        assert clay_result["p1_losses"] == 1

    def test_strict_less_than_excludes_same_date(self, db_conn):
        """get_h2h does NOT count matches on the same date as the query date (strict less-than)."""
        from src.features.h2h import get_h2h
        _insert_tournament(db_conn, "T1", tourney_date="2024-01-10")
        _insert_match(db_conn, "T1", 1, winner_id=10, loser_id=20, tourney_date="2024-01-10")

        # Query with exactly the match date — must NOT see this match
        result = get_h2h(db_conn, p1_id=10, p2_id=20, before_date="2024-01-10")
        assert result["total"] == 0

        # Query with day after — must see it
        result = get_h2h(db_conn, p1_id=10, p2_id=20, before_date="2024-01-11")
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# Ranking Tests (FEAT-03)
# ---------------------------------------------------------------------------

class TestGetRankingFeatures:
    def test_ranking_and_delta_returned(self, db_conn):
        """get_ranking_features returns (ranking, delta) where delta = prev - current."""
        from src.features.ranking import get_ranking_features
        _insert_ranking(db_conn, player_id=100, ranking_date="2024-01-01", ranking=10)
        _insert_ranking(db_conn, player_id=100, ranking_date="2024-01-08", ranking=8)

        result = get_ranking_features(db_conn, player_id=100, before_date="2024-01-15")
        assert result["ranking"] == 8
        # delta = previous - current = 10 - 8 = 2 (improved)
        assert result["ranking_delta"] == 2

    def test_no_ranking_data_returns_none(self, db_conn):
        """get_ranking_features returns (None, None) for player with no ranking data."""
        from src.features.ranking import get_ranking_features
        result = get_ranking_features(db_conn, player_id=999, before_date="2024-01-15")
        assert result["ranking"] is None
        assert result["ranking_delta"] is None

    def test_no_future_rankings_used(self, db_conn):
        """get_ranking_features uses ranking_date <= match_date, not future rankings."""
        from src.features.ranking import get_ranking_features
        _insert_ranking(db_conn, player_id=100, ranking_date="2024-01-01", ranking=15)
        # Future ranking that should be excluded
        _insert_ranking(db_conn, player_id=100, ranking_date="2024-01-20", ranking=5)

        # Query for match on 2024-01-10 — only Jan 1 ranking should be used
        result = get_ranking_features(db_conn, player_id=100, before_date="2024-01-10")
        assert result["ranking"] == 15

    def test_single_ranking_no_delta(self, db_conn):
        """With only one prior ranking, delta is None (no previous to compare)."""
        from src.features.ranking import get_ranking_features
        _insert_ranking(db_conn, player_id=100, ranking_date="2024-01-01", ranking=20)

        result = get_ranking_features(db_conn, player_id=100, before_date="2024-01-15")
        assert result["ranking"] == 20
        assert result["ranking_delta"] is None


# ---------------------------------------------------------------------------
# Fatigue Tests (FEAT-04)
# ---------------------------------------------------------------------------

class TestGetFatigueFeatures:
    def test_first_match_returns_none_days_and_zero_sets(self, db_conn):
        """First match ever returns days_since_last=None and sets_last_7=0."""
        from src.features.fatigue import get_fatigue_features
        result = get_fatigue_features(db_conn, player_id=50, match_date="2024-01-15")
        assert result["days_since_last"] is None
        assert result["sets_last_7_days"] == 0

    def test_sets_counted_in_7_day_window(self, db_conn):
        """Correctly counts sets from score parsing in last 7 days."""
        from src.features.fatigue import get_fatigue_features
        _insert_tournament(db_conn, "T1", tourney_date="2024-01-01")
        # Match 3 days before: score "6-3 6-4" = 2 sets
        _insert_match(db_conn, "T1", 1, winner_id=50, loser_id=99, score="6-3 6-4",
                      tourney_date="2024-01-08")
        # Match 5 days before: score "6-4 3-6 6-2" = 3 sets
        _insert_match(db_conn, "T1", 2, winner_id=99, loser_id=50, score="6-4 3-6 6-2",
                      tourney_date="2024-01-06")

        result = get_fatigue_features(db_conn, player_id=50, match_date="2024-01-11")
        # Both matches within 7 days: 2 + 3 = 5 sets
        assert result["sets_last_7_days"] == 5
        assert result["days_since_last"] == 3

    def test_exactly_7_days_ago_included(self, db_conn):
        """Match exactly 7 days ago is included in sets_last_7_days."""
        from src.features.fatigue import get_fatigue_features
        _insert_tournament(db_conn, "T1", tourney_date="2024-01-01")
        # Exactly 7 days before match_date 2024-01-15
        _insert_match(db_conn, "T1", 1, winner_id=50, loser_id=99, score="6-3 6-4",
                      tourney_date="2024-01-08")

        result = get_fatigue_features(db_conn, player_id=50, match_date="2024-01-15")
        assert result["sets_last_7_days"] == 2

    def test_8_days_ago_excluded(self, db_conn):
        """Match 8 days ago is excluded from sets_last_7_days."""
        from src.features.fatigue import get_fatigue_features
        _insert_tournament(db_conn, "T1", tourney_date="2024-01-01")
        # 8 days before 2024-01-15
        _insert_match(db_conn, "T1", 1, winner_id=50, loser_id=99, score="6-3 6-4",
                      tourney_date="2024-01-07")

        result = get_fatigue_features(db_conn, player_id=50, match_date="2024-01-15")
        assert result["sets_last_7_days"] == 0


# ---------------------------------------------------------------------------
# Tournament Level Tests (FEAT-06)
# ---------------------------------------------------------------------------

class TestEncodeTourneyLevel:
    def test_grand_slam_encoding(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("G") == 4

    def test_masters_encoding(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("M") == 3

    def test_atp_500_encoding(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("A") == 2

    def test_tour_finals_encoding(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("F") == 2

    def test_davis_cup_encoding(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("D") == 1

    def test_challenger_encoding(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("C") == 1

    def test_unknown_level_returns_zero(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level("X") == 0
        assert encode_tourney_level("") == 0

    def test_none_returns_zero(self):
        from src.features.tourney import encode_tourney_level
        assert encode_tourney_level(None) == 0


# ---------------------------------------------------------------------------
# Rolling Form Tests (FEAT-02) — added in Task 2
# ---------------------------------------------------------------------------

class TestComputeRollingForm:
    def test_rolling_form_window_3_correct(self, db_conn):
        """compute_rolling_form with window=3 on a player with 5 prior matches returns correct rolling win rate."""
        from src.features.form import compute_rolling_form
        _insert_tournament(db_conn, "T1", tourney_date="2023-01-01")
        pid = 200
        opp = 999
        # 5 matches: pid wins 3 of last 3, loses 2 before that
        dates = ["2023-01-10", "2023-02-10", "2023-03-10", "2023-04-10", "2023-05-10"]
        results = [(opp, pid), (opp, pid), (pid, opp), (pid, opp), (pid, opp)]  # W=winner, L=loser
        for i, (wid, lid) in enumerate(results):
            _insert_match(db_conn, "T1", i + 1, winner_id=wid, loser_id=lid,
                          tourney_date=dates[i])
            _insert_match_stats(db_conn, "T1", i + 1, "winner")
            _insert_match_stats(db_conn, "T1", i + 1, "loser")

        # Query on 2023-06-01 — all 5 matches are prior
        # With window=3, only last 3 are considered (Apr, May x2 = 2 wins in last 3 = 2/3)
        result = compute_rolling_form(db_conn, player_id=pid, before_date="2023-06-01", windows=[3])
        assert result["form_win_rate_3"] == pytest.approx(3 / 3, abs=0.01)

    def test_rolling_form_excludes_current_match(self, db_conn):
        """Rolling form excludes the current match (strict before_date filter)."""
        from src.features.form import compute_rolling_form
        _insert_tournament(db_conn, "T1", tourney_date="2023-01-01")
        pid = 300
        # One match on the query date itself — must be excluded
        _insert_match(db_conn, "T1", 1, winner_id=pid, loser_id=999, tourney_date="2024-01-15")

        result = compute_rolling_form(db_conn, player_id=pid, before_date="2024-01-15", windows=[10])
        # No prior matches — win rate is None
        assert result["form_win_rate_10"] is None

    def test_service_stats_averaged_over_window(self, db_conn):
        """Service stats (ace_rate, df_rate, first_pct, first_won_pct) are averaged over the rolling window."""
        from src.features.form import compute_rolling_form
        _insert_tournament(db_conn, "T1", tourney_date="2023-01-01")
        pid = 400
        # Two prior matches: same stats each time — ace=10, df=2, svpt=100, first_in=60, first_won=45
        for i, date in enumerate(["2024-01-05", "2024-01-08"]):
            _insert_match(db_conn, "T1", i + 1, winner_id=pid, loser_id=999, tourney_date=date)
            _insert_match_stats(db_conn, "T1", i + 1, "winner",
                                ace=10, df=2, svpt=100, first_in=60, first_won=45)
            _insert_match_stats(db_conn, "T1", i + 1, "loser")

        result = compute_rolling_form(db_conn, player_id=pid, before_date="2024-01-15", windows=[10])
        # ace_rate = 20/200 = 0.1, df_rate = 4/200 = 0.02
        # first_pct = 120/200 = 0.6, first_won_pct = 90/120 = 0.75
        assert result["avg_ace_rate"] == pytest.approx(0.1, abs=0.001)
        assert result["avg_df_rate"] == pytest.approx(0.02, abs=0.001)
        assert result["avg_first_pct"] == pytest.approx(0.6, abs=0.001)
        assert result["avg_first_won_pct"] == pytest.approx(0.75, abs=0.001)

    def test_fewer_matches_than_window_uses_min_periods(self, db_conn):
        """Player with fewer matches than window uses min_periods=1 (no None)."""
        from src.features.form import compute_rolling_form
        _insert_tournament(db_conn, "T1", tourney_date="2023-01-01")
        pid = 500
        # Only 2 matches, window=10
        _insert_match(db_conn, "T1", 1, winner_id=pid, loser_id=999, tourney_date="2024-01-05")
        _insert_match_stats(db_conn, "T1", 1, "winner")
        _insert_match_stats(db_conn, "T1", 1, "loser")

        result = compute_rolling_form(db_conn, player_id=pid, before_date="2024-01-15", windows=[10])
        # Should return a value, not None, since min_periods=1
        assert result["form_win_rate_10"] is not None

    def test_zero_prior_matches_returns_none(self, db_conn):
        """Player with 0 prior matches returns None win rate values."""
        from src.features.form import compute_rolling_form
        result = compute_rolling_form(db_conn, player_id=600, before_date="2024-01-15", windows=[10])
        assert result["form_win_rate_10"] is None

    def test_no_lookahead_bias_future_match_does_not_change_result(self, db_conn):
        """LOOK-AHEAD BIAS TEST: Adding a future match does not change computed features for earlier match."""
        from src.features.form import compute_rolling_form
        _insert_tournament(db_conn, "T1", tourney_date="2023-01-01")
        pid = 700
        # Insert prior matches
        for i, date in enumerate(["2024-01-05", "2024-01-08"]):
            _insert_match(db_conn, "T1", i + 1, winner_id=pid, loser_id=999, tourney_date=date)
            _insert_match_stats(db_conn, "T1", i + 1, "winner")
            _insert_match_stats(db_conn, "T1", i + 1, "loser")

        # Compute features for match on 2024-01-15
        result_before = compute_rolling_form(db_conn, player_id=pid, before_date="2024-01-15", windows=[10])

        # Add a future match (2024-01-20) and recompute for 2024-01-15
        _insert_match(db_conn, "T1", 3, winner_id=pid, loser_id=999, tourney_date="2024-01-20")
        _insert_match_stats(db_conn, "T1", 3, "winner", ace=99, df=99, svpt=200, first_in=100, first_won=80)
        _insert_match_stats(db_conn, "T1", 3, "loser")

        result_after = compute_rolling_form(db_conn, player_id=pid, before_date="2024-01-15", windows=[10])

        assert result_before["form_win_rate_10"] == result_after["form_win_rate_10"]
        assert result_before["avg_ace_rate"] == result_after["avg_ace_rate"]

    def test_no_lookahead_bias_current_match_excluded(self, db_conn):
        """LOOK-AHEAD BIAS TEST: Features for match M do not include match M itself."""
        from src.features.form import compute_rolling_form
        _insert_tournament(db_conn, "T1", tourney_date="2023-01-01")
        pid = 800
        # Prior match
        _insert_match(db_conn, "T1", 1, winner_id=pid, loser_id=999, tourney_date="2024-01-10")
        _insert_match_stats(db_conn, "T1", 1, "winner")
        _insert_match_stats(db_conn, "T1", 1, "loser")

        # Current match (same date as query) — should NOT be included
        _insert_match(db_conn, "T1", 2, winner_id=999, loser_id=pid, tourney_date="2024-01-15")
        _insert_match_stats(db_conn, "T1", 2, "winner")
        _insert_match_stats(db_conn, "T1", 2, "loser")

        result = compute_rolling_form(db_conn, player_id=pid, before_date="2024-01-15", windows=[10])
        # win_rate should be 1.0 (one match prior, which was a win)
        assert result["form_win_rate_10"] == pytest.approx(1.0)
