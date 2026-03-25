"""
Tests for src/features/builder.py

Covers:
- build_feature_row returns dict with all match_features schema columns
- build_feature_row populates Glicko-2 ELO fields from player_elo table
- build_feature_row calls all feature modules (h2h, form, ranking, fatigue, tourney)
- build_feature_row with no sentiment data returns sentiment_score=None
- build_all_features inserts 2 rows per match into match_features
- End-to-end look-ahead bias test: features for match M unchanged after adding future match
- Pinnacle devigged probability extraction and schema columns
"""
import sqlite3
from unittest.mock import patch

import pytest

from src.features.builder import build_feature_row, build_all_features

# ---------------------------------------------------------------------------
# Expected columns in match_features table
# ---------------------------------------------------------------------------
EXPECTED_FEATURE_KEYS = {
    "tourney_id", "match_num", "tour", "player_role",
    "elo_hard", "elo_hard_rd",
    "elo_clay", "elo_clay_rd",
    "elo_grass", "elo_grass_rd",
    "elo_overall", "elo_overall_rd",
    "h2h_wins", "h2h_losses",
    "h2h_surface_wins", "h2h_surface_losses",
    "form_win_rate_10", "form_win_rate_20",
    "avg_ace_rate", "avg_df_rate", "avg_first_pct", "avg_first_won_pct",
    "ranking", "ranking_delta",
    "days_since_last", "sets_last_7_days",
    "tourney_level", "surface",
    "sentiment_score",
    "pinnacle_prob_winner", "pinnacle_prob_loser", "has_no_pinnacle",
}


# ---------------------------------------------------------------------------
# Helpers to insert synthetic data
# ---------------------------------------------------------------------------

def _insert_tournament(conn, tourney_id="T001", surface="Hard", level="G", date="2024-01-15"):
    conn.execute(
        "INSERT OR IGNORE INTO tournaments (tourney_id, tour, tourney_name, surface, tourney_level, tourney_date)"
        " VALUES (?, 'ATP', 'Test Open', ?, ?, ?)",
        (tourney_id, surface, level, date),
    )
    conn.commit()


def _insert_match(conn, tourney_id="T001", match_num=1, winner_id=1, loser_id=2,
                  date="2024-01-15", score="6-3 6-4", round_="QF"):
    conn.execute(
        "INSERT OR IGNORE INTO matches (tourney_id, match_num, tour, winner_id, loser_id,"
        " score, round, best_of, tourney_date)"
        " VALUES (?, ?, 'ATP', ?, ?, ?, ?, 3, ?)",
        (tourney_id, match_num, winner_id, loser_id, score, round_, date),
    )
    conn.commit()


def _insert_player_elo(conn, player_id=1, surface="Hard", as_of_date="2024-01-01",
                        elo=1600.0, rd=80.0):
    conn.execute(
        "INSERT OR IGNORE INTO player_elo (player_id, tour, surface, as_of_date, elo_rating, rd)"
        " VALUES (?, 'ATP', ?, ?, ?, ?)",
        (player_id, surface, as_of_date, elo, rd),
    )
    conn.commit()


def _insert_ranking(conn, player_id=1, ranking=10, date="2024-01-08"):
    conn.execute(
        "INSERT OR IGNORE INTO rankings (ranking_date, tour, player_id, ranking)"
        " VALUES (?, 'ATP', ?, ?)",
        (date, player_id, ranking),
    )
    conn.commit()


def _make_match_dict(tourney_id="T001", match_num=1, date="2024-01-15",
                     surface="Hard", level="G"):
    return {
        "tourney_id": tourney_id,
        "match_num": match_num,
        "tour": "ATP",
        "tourney_date": date,
        "surface": surface,
        "tourney_level": level,
    }


# ---------------------------------------------------------------------------
# Tests: build_feature_row
# ---------------------------------------------------------------------------

class TestBuildFeatureRow:
    def test_all_expected_keys_present(self, db_conn):
        """build_feature_row returns dict containing all expected match_features keys."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)
        match = _make_match_dict()

        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert set(row.keys()) == EXPECTED_FEATURE_KEYS

    def test_correct_tourney_and_match_ids(self, db_conn):
        """build_feature_row sets tourney_id, match_num, tour, player_role correctly."""
        _insert_tournament(db_conn, tourney_id="T002")
        _insert_match(db_conn, tourney_id="T002", match_num=5)
        match = _make_match_dict(tourney_id="T002", match_num=5)

        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="loser")

        assert row["tourney_id"] == "T002"
        assert row["match_num"] == 5
        assert row["tour"] == "ATP"
        assert row["player_role"] == "loser"

    def test_elo_populated_from_player_elo_table(self, db_conn):
        """build_feature_row reads Glicko-2 ratings from player_elo for the correct player."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)
        # Insert Elo snapshots before match date
        for surface, rating in [("Hard", 1650.0), ("Clay", 1580.0), ("Grass", 1520.0), ("Overall", 1620.0)]:
            _insert_player_elo(db_conn, player_id=1, surface=surface, as_of_date="2024-01-08", elo=rating, rd=75.0)

        match = _make_match_dict(date="2024-01-15", surface="Hard")
        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert row["elo_hard"] == pytest.approx(1650.0)
        assert row["elo_hard_rd"] == pytest.approx(75.0)
        assert row["elo_clay"] == pytest.approx(1580.0)
        assert row["elo_grass"] == pytest.approx(1520.0)
        assert row["elo_overall"] == pytest.approx(1620.0)

    def test_elo_defaults_when_no_ratings(self, db_conn):
        """build_feature_row returns default Elo values (1500, 350) when no player_elo row exists."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)
        match = _make_match_dict()

        row = build_feature_row(db_conn, match, player_id=999, opponent_id=2, player_role="winner")

        assert row["elo_hard"] == pytest.approx(1500.0)
        assert row["elo_hard_rd"] == pytest.approx(350.0)
        assert row["elo_clay"] == pytest.approx(1500.0)
        assert row["elo_overall"] == pytest.approx(1500.0)

    def test_h2h_features_populated(self, db_conn):
        """build_feature_row includes H2H wins/losses from get_h2h calls."""
        _insert_tournament(db_conn)
        # Past match: player 1 beat player 2 on hard
        _insert_match(db_conn, tourney_id="T001", match_num=10, winner_id=1, loser_id=2,
                      date="2023-06-15", score="6-3 6-4")
        # The match we're building features for
        _insert_match(db_conn, tourney_id="T001", match_num=20, winner_id=1, loser_id=2,
                      date="2024-01-15")
        match = _make_match_dict(match_num=20, date="2024-01-15")

        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        # Player 1 won 1 H2H match before this date
        assert row["h2h_wins"] == 1
        assert row["h2h_losses"] == 0

    def test_ranking_features_populated(self, db_conn):
        """build_feature_row includes ranking data from get_ranking_features."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)
        _insert_ranking(db_conn, player_id=1, ranking=15, date="2024-01-08")

        match = _make_match_dict()
        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert row["ranking"] == 15

    def test_tourney_level_and_surface_set(self, db_conn):
        """build_feature_row includes tourney_level (raw string) and surface."""
        _insert_tournament(db_conn, surface="Clay", level="M")
        _insert_match(db_conn)
        match = _make_match_dict(surface="Clay", level="M")

        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert row["surface"] == "Clay"
        assert row["tourney_level"] == "M"

    def test_sentiment_score_none_when_no_articles(self, db_conn):
        """build_feature_row returns sentiment_score=None when no articles exist."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)
        match = _make_match_dict()

        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert row["sentiment_score"] is None

    def test_sentiment_score_populated_when_articles_exist(self, db_conn):
        """build_feature_row populates sentiment_score from weighted_player_sentiment."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)

        # Insert an article and its sentiment score
        conn = db_conn
        cursor = conn.execute(
            "INSERT INTO articles (player_id, tour, source, url, title, content, published_date)"
            " VALUES (1, 'ATP', 'rss', 'http://test.com/1', 'title', 'content', '2024-01-10')"
        )
        article_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO article_sentiment (article_id, player_id, tour, sentiment_score)"
            " VALUES (?, 1, 'ATP', 0.75)",
            (article_id,),
        )
        conn.commit()

        match = _make_match_dict()
        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert row["sentiment_score"] is not None
        # Weighted average with recency decay; article 5 days before match → close to 0.75
        assert -1.0 <= row["sentiment_score"] <= 1.0

    def test_elo_uses_latest_snapshot_before_match_date(self, db_conn):
        """build_feature_row uses the most recent player_elo snapshot strictly before match date."""
        _insert_tournament(db_conn)
        _insert_match(db_conn, date="2024-01-15")
        # Insert two snapshots: one old, one more recent but still before match
        _insert_player_elo(db_conn, player_id=1, surface="Hard", as_of_date="2023-12-01", elo=1550.0)
        _insert_player_elo(db_conn, player_id=1, surface="Hard", as_of_date="2024-01-08", elo=1700.0)
        # This snapshot is on match date — should NOT be used
        _insert_player_elo(db_conn, player_id=1, surface="Hard", as_of_date="2024-01-15", elo=9999.0)

        match = _make_match_dict(date="2024-01-15")
        row = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert row["elo_hard"] == pytest.approx(1700.0)


# ---------------------------------------------------------------------------
# Tests: build_all_features
# ---------------------------------------------------------------------------

class TestBuildAllFeatures:
    def test_returns_summary_dict(self, db_conn):
        """build_all_features returns dict with matches_processed and feature_rows_written."""
        result = build_all_features(db_conn)

        assert "matches_processed" in result
        assert "feature_rows_written" in result
        assert result["matches_processed"] == 0
        assert result["feature_rows_written"] == 0

    def test_two_rows_per_match(self, db_conn):
        """build_all_features inserts 2 rows (winner + loser) per match."""
        _insert_tournament(db_conn)
        _insert_match(db_conn, match_num=1, winner_id=1, loser_id=2)
        _insert_match(db_conn, match_num=2, winner_id=3, loser_id=4)

        result = build_all_features(db_conn)

        assert result["matches_processed"] == 2
        assert result["feature_rows_written"] == 4  # 2 matches * 2 roles

        count = db_conn.execute("SELECT COUNT(*) FROM match_features").fetchone()[0]
        assert count == 4

    def test_player_roles_winner_and_loser(self, db_conn):
        """build_all_features writes one row with player_role='winner' and one with 'loser'."""
        _insert_tournament(db_conn)
        _insert_match(db_conn, match_num=1, winner_id=1, loser_id=2)

        build_all_features(db_conn)

        roles = {
            row[0]
            for row in db_conn.execute(
                "SELECT player_role FROM match_features WHERE tourney_id='T001' AND match_num=1"
            ).fetchall()
        }
        assert roles == {"winner", "loser"}

    def test_idempotent_rerun(self, db_conn):
        """build_all_features is idempotent: re-running does not duplicate rows."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)

        build_all_features(db_conn)
        build_all_features(db_conn)  # run again

        count = db_conn.execute("SELECT COUNT(*) FROM match_features").fetchone()[0]
        assert count == 2  # still 2, not 4

    def test_multiple_tournaments(self, db_conn):
        """build_all_features processes matches across multiple tournaments."""
        _insert_tournament(db_conn, tourney_id="T001", surface="Hard", date="2024-01-15")
        _insert_tournament(db_conn, tourney_id="T002", surface="Clay", date="2024-04-01")
        _insert_match(db_conn, tourney_id="T001", match_num=1)
        _insert_match(db_conn, tourney_id="T002", match_num=1)

        result = build_all_features(db_conn)

        assert result["matches_processed"] == 2
        assert result["feature_rows_written"] == 4


# ---------------------------------------------------------------------------
# Test: End-to-end look-ahead bias
# ---------------------------------------------------------------------------

class TestLookAheadBias:
    def test_future_match_does_not_change_features_for_earlier_match(self, db_conn):
        """
        End-to-end look-ahead test.

        Build features for match M1. Insert a later match M4. Rebuild. Verify
        that H2H, form, ranking, and fatigue features for M1 are unchanged.
        """
        # Set up three sequential matches between players 1 and 2
        _insert_tournament(db_conn, tourney_id="T001", surface="Hard", date="2024-01-01")
        _insert_tournament(db_conn, tourney_id="T001B", surface="Hard", date="2024-02-01")
        _insert_tournament(db_conn, tourney_id="T001C", surface="Hard", date="2024-03-01")

        # M1: player 1 beats player 2 on Jan 15
        _insert_match(db_conn, tourney_id="T001", match_num=1,
                      winner_id=1, loser_id=2, date="2024-01-15")
        # M2: player 2 beats player 1 on Feb 1
        _insert_match(db_conn, tourney_id="T001B", match_num=1,
                      winner_id=2, loser_id=1, date="2024-02-01")
        # M3: player 1 beats player 2 on Mar 1
        _insert_match(db_conn, tourney_id="T001C", match_num=1,
                      winner_id=1, loser_id=2, date="2024-03-01")

        # Insert rankings so ranking features are stable
        _insert_ranking(db_conn, player_id=1, ranking=20, date="2024-01-08")
        _insert_ranking(db_conn, player_id=2, ranking=30, date="2024-01-08")

        # Build features for M1 only (before M2, M3 exist)
        match_m1 = {
            "tourney_id": "T001", "match_num": 1, "tour": "ATP",
            "tourney_date": "2024-01-15", "surface": "Hard", "tourney_level": "G",
        }
        row_before = build_feature_row(db_conn, match_m1, player_id=1, opponent_id=2, player_role="winner")

        # Now add a future match M4 after M1
        _insert_tournament(db_conn, tourney_id="T001D", surface="Hard", date="2024-04-01")
        _insert_match(db_conn, tourney_id="T001D", match_num=1,
                      winner_id=1, loser_id=2, date="2024-04-01")

        # Rebuild features for M1
        row_after = build_feature_row(db_conn, match_m1, player_id=1, opponent_id=2, player_role="winner")

        # Features for M1 must be identical — future matches must not affect them
        assert row_before["h2h_wins"] == row_after["h2h_wins"]
        assert row_before["h2h_losses"] == row_after["h2h_losses"]
        assert row_before["form_win_rate_10"] == row_after["form_win_rate_10"]
        assert row_before["days_since_last"] == row_after["days_since_last"]
        assert row_before["sets_last_7_days"] == row_after["sets_last_7_days"]
        assert row_before["ranking"] == row_after["ranking"]


# ---------------------------------------------------------------------------
# Helpers for Pinnacle tests
# ---------------------------------------------------------------------------

def _insert_match_odds(conn, tourney_id="T001", match_num=1, tour="ATP",
                        bookmaker="pinnacle", decimal_odds_a=1.90, decimal_odds_b=2.05):
    conn.execute(
        "INSERT OR IGNORE INTO match_odds "
        "(tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b, source, imported_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'manual', '2024-01-14T00:00:00Z')",
        (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests: _get_pinnacle_prob
# ---------------------------------------------------------------------------

class TestGetPinnacleProb:
    def test_get_pinnacle_prob_with_odds(self, db_conn):
        """_get_pinnacle_prob returns devigged probabilities when match_odds row exists."""
        from src.features.builder import _get_pinnacle_prob
        from src.odds.devig import power_method_devig

        _insert_tournament(db_conn)
        _insert_match(db_conn)
        _insert_match_odds(db_conn, decimal_odds_a=1.90, decimal_odds_b=2.05)

        result = _get_pinnacle_prob(db_conn, "T001", 1)

        expected_p_a, expected_p_b = power_method_devig(1.90, 2.05)
        assert result["pinnacle_prob_winner"] == pytest.approx(expected_p_a, abs=0.05)
        assert result["pinnacle_prob_loser"] == pytest.approx(expected_p_b, abs=0.05)
        assert result["has_no_pinnacle"] == 0

    def test_get_pinnacle_prob_no_odds(self, db_conn):
        """_get_pinnacle_prob returns None/None/1 when no match_odds row exists."""
        from src.features.builder import _get_pinnacle_prob

        result = _get_pinnacle_prob(db_conn, "T999", 99)

        assert result == {"pinnacle_prob_winner": None, "pinnacle_prob_loser": None, "has_no_pinnacle": 1}

    def test_get_pinnacle_prob_invalid_odds(self, db_conn):
        """_get_pinnacle_prob returns None/None/1 fallback when odds are invalid (< 1.01)."""
        from src.features.builder import _get_pinnacle_prob

        _insert_tournament(db_conn)
        _insert_match(db_conn)
        _insert_match_odds(db_conn, decimal_odds_a=0.5, decimal_odds_b=2.05)

        result = _get_pinnacle_prob(db_conn, "T001", 1)

        assert result["pinnacle_prob_winner"] is None
        assert result["pinnacle_prob_loser"] is None
        assert result["has_no_pinnacle"] == 1

    def test_match_features_schema_pinnacle_columns(self, db_conn):
        """After init_db, match_features table has pinnacle_prob_winner, pinnacle_prob_loser, has_no_pinnacle columns."""
        cols = [
            row[1]
            for row in db_conn.execute("PRAGMA table_info(match_features)").fetchall()
        ]
        assert "pinnacle_prob_winner" in cols
        assert "pinnacle_prob_loser" in cols
        assert "has_no_pinnacle" in cols

    def test_feature_row_has_pinnacle_keys(self, db_conn):
        """build_feature_row includes pinnacle keys; with odds returns floats; without odds returns None/None/1."""
        _insert_tournament(db_conn)
        _insert_match(db_conn)

        # Case 1: Pinnacle odds row exists — expect non-None float probs
        _insert_match_odds(db_conn, decimal_odds_a=1.90, decimal_odds_b=2.05)
        match = _make_match_dict()
        row_with_odds = build_feature_row(db_conn, match, player_id=1, opponent_id=2, player_role="winner")

        assert "pinnacle_prob_winner" in row_with_odds
        assert "pinnacle_prob_loser" in row_with_odds
        assert "has_no_pinnacle" in row_with_odds
        assert row_with_odds["pinnacle_prob_winner"] is not None
        assert row_with_odds["pinnacle_prob_loser"] is not None
        assert row_with_odds["has_no_pinnacle"] == 0

        # Case 2: No Pinnacle odds for a different match — expect None/None/1
        _insert_match(db_conn, tourney_id="T001", match_num=99, winner_id=3, loser_id=4, date="2024-01-15")
        match_no_odds = {**_make_match_dict(), "match_num": 99}
        row_no_odds = build_feature_row(db_conn, match_no_odds, player_id=3, opponent_id=4, player_role="winner")

        assert row_no_odds["pinnacle_prob_winner"] is None
        assert row_no_odds["pinnacle_prob_loser"] is None
        assert row_no_odds["has_no_pinnacle"] == 1
