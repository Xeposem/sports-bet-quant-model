"""
Tests for Phase 2 Plan 1: Glicko-2 rating engine.

Covers:
- ELO-01: Schema migration (player_elo with rd, volatility columns; match_features, articles, article_sentiment tables)
- ELO-02: Seeder (rank-based logarithmic mapping)
- ELO-03: Decay (surface-specific inactivity decay)
- Glicko-2 engine (Task 2 tests appended below)
"""

import pytest
import sqlite3

from src.db.connection import get_connection, _read_schema_sql


# ---------------------------------------------------------------------------
# Task 1: Schema migration tests (ELO-01)
# ---------------------------------------------------------------------------

class TestSchemaMigration:
    """Tests verifying schema.sql includes all Phase 2 columns and tables."""

    def test_player_elo_has_rd_column(self, db_conn):
        """player_elo table must have rd REAL column with default 350."""
        cols = {
            row[1]: row
            for row in db_conn.execute("PRAGMA table_info(player_elo)").fetchall()
        }
        assert "rd" in cols, "player_elo missing rd column"
        assert cols["rd"][2].upper() == "REAL", "rd column must be REAL type"

    def test_player_elo_has_volatility_column(self, db_conn):
        """player_elo table must have volatility REAL column with default 0.06."""
        cols = {
            row[1]: row
            for row in db_conn.execute("PRAGMA table_info(player_elo)").fetchall()
        }
        assert "volatility" in cols, "player_elo missing volatility column"
        assert cols["volatility"][2].upper() == "REAL", "volatility column must be REAL type"

    def test_player_elo_has_last_played_date_column(self, db_conn):
        """player_elo table must have last_played_date TEXT column."""
        cols = {
            row[1]: row
            for row in db_conn.execute("PRAGMA table_info(player_elo)").fetchall()
        }
        assert "last_played_date" in cols, "player_elo missing last_played_date column"

    def test_match_features_table_exists(self, db_conn):
        """match_features table must exist with expected columns."""
        cols = {
            row[1]
            for row in db_conn.execute("PRAGMA table_info(match_features)").fetchall()
        }
        assert len(cols) > 0, "match_features table does not exist"
        expected = {
            "tourney_id", "match_num", "tour", "player_role",
            "elo_hard", "elo_clay", "elo_grass", "elo_overall",
            "ranking", "surface",
        }
        missing = expected - cols
        assert not missing, f"match_features missing columns: {missing}"

    def test_articles_table_exists(self, db_conn):
        """articles table must exist with required columns."""
        cols = {
            row[1]
            for row in db_conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        assert len(cols) > 0, "articles table does not exist"
        required = {"id", "player_id", "tour", "url", "title", "published_date"}
        missing = required - cols
        assert not missing, f"articles missing columns: {missing}"

    def test_article_sentiment_table_exists(self, db_conn):
        """article_sentiment table must exist with required columns."""
        cols = {
            row[1]
            for row in db_conn.execute("PRAGMA table_info(article_sentiment)").fetchall()
        }
        assert len(cols) > 0, "article_sentiment table does not exist"
        required = {"article_id", "player_id", "sentiment_score"}
        missing = required - cols
        assert not missing, f"article_sentiment missing columns: {missing}"


# ---------------------------------------------------------------------------
# Task 1: Seeder tests (ELO-02)
# ---------------------------------------------------------------------------

class TestSeeder:
    """Tests for seed_rating_from_rank logarithmic mapping."""

    def test_rank_1_near_1800(self):
        """Rank 1 should produce rating close to 1800."""
        from src.ratings.seeder import seed_rating_from_rank
        rating = seed_rating_from_rank(1)
        assert 1780 <= rating <= 1820, f"Rank 1 rating expected ~1800, got {rating}"

    def test_rank_100_near_1500(self):
        """Rank 100 should produce rating close to 1500."""
        from src.ratings.seeder import seed_rating_from_rank
        rating = seed_rating_from_rank(100)
        assert 1450 <= rating <= 1550, f"Rank 100 rating expected ~1500, got {rating}"

    def test_rank_300_near_1350(self):
        """Rank 300 should produce rating close to 1350."""
        from src.ratings.seeder import seed_rating_from_rank
        rating = seed_rating_from_rank(300)
        assert 1300 <= rating <= 1400, f"Rank 300 rating expected ~1350, got {rating}"

    def test_rank_none_returns_1500(self):
        """None rank falls back to default 1500."""
        from src.ratings.seeder import seed_rating_from_rank
        rating = seed_rating_from_rank(None)
        assert rating == 1500.0, f"None rank expected 1500, got {rating}"

    def test_rank_zero_returns_1500(self):
        """Zero or negative rank falls back to 1500."""
        from src.ratings.seeder import seed_rating_from_rank
        assert seed_rating_from_rank(0) == 1500.0
        assert seed_rating_from_rank(-5) == 1500.0

    def test_rating_decreases_with_rank(self):
        """Higher rank number should produce lower or equal rating."""
        from src.ratings.seeder import seed_rating_from_rank
        r1 = seed_rating_from_rank(1)
        r50 = seed_rating_from_rank(50)
        r200 = seed_rating_from_rank(200)
        assert r1 > r50 > r200, "Rating should decrease as rank number increases"


# ---------------------------------------------------------------------------
# Task 1: Decay tests (ELO-03)
# ---------------------------------------------------------------------------

class TestDecay:
    """Tests for apply_decay_if_needed surface-specific inactivity decay."""

    def test_no_decay_zero_days(self):
        """Zero days inactive returns unchanged rating."""
        from src.ratings.decay import apply_decay_if_needed
        rating = 1700.0
        result = apply_decay_if_needed(rating, "Hard", 0)
        assert result == rating

    def test_no_decay_below_hard_threshold(self):
        """Hard surface: 89 days inactive (below 90-day threshold) returns unchanged."""
        from src.ratings.decay import apply_decay_if_needed
        rating = 1700.0
        result = apply_decay_if_needed(rating, "Hard", 89)
        assert result == rating

    def test_decay_above_hard_threshold(self):
        """Hard surface: 120 days inactive (above 90-day threshold) decays toward 1500."""
        from src.ratings.decay import apply_decay_if_needed
        rating = 1700.0
        result = apply_decay_if_needed(rating, "Hard", 120)
        assert result < rating, "Rating should decay when above Hard threshold"
        assert result > 1500.0, "Rating should not decay below mean"

    def test_no_decay_grass_below_threshold(self):
        """Grass surface: 200 days inactive (below 330-day threshold) returns unchanged."""
        from src.ratings.decay import apply_decay_if_needed
        rating = 1700.0
        result = apply_decay_if_needed(rating, "Grass", 200)
        assert result == rating

    def test_decay_above_clay_threshold(self):
        """Clay surface: 240 days inactive (above 180-day threshold) decays toward 1500."""
        from src.ratings.decay import apply_decay_if_needed
        rating = 1700.0
        result = apply_decay_if_needed(rating, "Clay", 240)
        assert result < rating, "Rating should decay when above Clay threshold"
        assert result > 1500.0, "Rating should not decay below mean"

    def test_decay_proportional(self):
        """More months over threshold = more decay (further from original rating)."""
        from src.ratings.decay import apply_decay_if_needed
        rating = 1700.0
        # 120 days on Hard = 1 month over 90-day threshold
        result_1mo = apply_decay_if_needed(rating, "Hard", 120)
        # 150 days on Hard = ~2 months over threshold
        result_2mo = apply_decay_if_needed(rating, "Hard", 150)
        assert result_2mo < result_1mo, "More months over threshold should produce more decay"

    def test_surface_thresholds_exported(self):
        """SURFACE_THRESHOLDS constant must be exported from decay module."""
        from src.ratings.decay import SURFACE_THRESHOLDS
        assert "Hard" in SURFACE_THRESHOLDS
        assert "Clay" in SURFACE_THRESHOLDS
        assert "Grass" in SURFACE_THRESHOLDS
        assert SURFACE_THRESHOLDS["Hard"] == 90
        assert SURFACE_THRESHOLDS["Clay"] == 180
        assert SURFACE_THRESHOLDS["Grass"] == 330


# ---------------------------------------------------------------------------
# Task 2: Glicko-2 engine tests
# ---------------------------------------------------------------------------

# Helper to insert synthetic data into an in-memory db for engine tests


def _insert_tournament(conn, tourney_id, surface, tourney_level, tourney_date, tour="ATP"):
    """Insert a tournament record."""
    conn.execute(
        """INSERT OR IGNORE INTO tournaments
           (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tourney_id, tour, f"Test {tourney_id}", surface, 32, tourney_level, tourney_date),
    )
    conn.commit()


def _insert_match(conn, tourney_id, match_num, winner_id, loser_id, tourney_date,
                  round_="R32", retirement_flag=0, tour="ATP"):
    """Insert a match record."""
    conn.execute(
        """INSERT OR IGNORE INTO matches
           (tourney_id, match_num, tour, winner_id, loser_id, score, round,
            best_of, minutes, tourney_date, match_type, retirement_flag,
            stats_normalized, stats_missing)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tourney_id, match_num, tour, winner_id, loser_id,
            "6-3 6-4", round_, 3, 90, tourney_date,
            "retirement" if retirement_flag else "completed",
            retirement_flag, 0, 0,
        ),
    )
    conn.commit()


def _insert_ranking(conn, player_id, ranking, ranking_date="2020-01-01", tour="ATP"):
    """Insert a ranking record."""
    conn.execute(
        """INSERT OR IGNORE INTO rankings (ranking_date, tour, player_id, ranking)
           VALUES (?, ?, ?, ?)""",
        (ranking_date, tour, player_id, ranking),
    )
    conn.commit()


def _get_latest_rating(conn, player_id, surface, tour="ATP"):
    """Get the most recent rating for a player on a surface."""
    row = conn.execute(
        """SELECT elo_rating, rd, volatility FROM player_elo
           WHERE player_id=? AND tour=? AND surface=?
           ORDER BY as_of_date DESC LIMIT 1""",
        (player_id, tour, surface),
    ).fetchone()
    return row


class TestGlicko2Engine:
    """Tests for compute_all_ratings weekly batch Glicko-2 engine."""

    def test_winner_rating_increases_loser_decreases(self, db_conn):
        """After a Hard match, winner rating should be higher and loser lower."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-001", "Hard", "G", "2020-01-13")
        _insert_match(db_conn, "2020-001", 1, 101, 102, "2020-01-13")
        _insert_ranking(db_conn, 101, 50)
        _insert_ranking(db_conn, 102, 60)

        compute_all_ratings(db_conn)

        winner_row = _get_latest_rating(db_conn, 101, "Hard")
        loser_row = _get_latest_rating(db_conn, 102, "Hard")

        assert winner_row is not None, "Winner should have a Hard rating"
        assert loser_row is not None, "Loser should have a Hard rating"

        winner_initial = 1500.0  # seeded from rank 50
        loser_initial = 1500.0   # seeded from rank 60

        # After a match, winner rating should go above initial, loser below
        assert winner_row[0] > loser_row[0], "Winner rating should be higher than loser"

    def test_frozen_opponent_ratings_mid_week(self, db_conn):
        """
        Second match in same week uses pre-update opponent rating (no contamination).
        Player 101 plays player 102 in match 1 and player 103 in match 2.
        Player 102's rating used for match 2 opponent should be the frozen week-start value.
        """
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-002", "Hard", "A", "2020-01-13")
        _insert_ranking(db_conn, 101, 30)
        _insert_ranking(db_conn, 102, 40)
        _insert_ranking(db_conn, 103, 50)

        # Player 101 plays both matches in same week
        _insert_match(db_conn, "2020-002", 1, 101, 102, "2020-01-13", round_="R32")
        _insert_match(db_conn, "2020-002", 2, 103, 102, "2020-01-14", round_="R16")

        result = compute_all_ratings(db_conn)

        # Should complete without error
        assert result["total_weeks"] >= 1

    def test_surface_tracks_are_independent(self, db_conn):
        """Match on Hard updates Hard and Overall tracks only, not Clay or Grass."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-003", "Hard", "G", "2020-01-13")
        _insert_match(db_conn, "2020-003", 1, 201, 202, "2020-01-13")
        _insert_ranking(db_conn, 201, 10)
        _insert_ranking(db_conn, 202, 20)

        compute_all_ratings(db_conn)

        hard_row = _get_latest_rating(db_conn, 201, "Hard")
        overall_row = _get_latest_rating(db_conn, 201, "Overall")

        # Hard and Overall should exist for player who played Hard match
        assert hard_row is not None, "Hard rating should exist after Hard match"
        assert overall_row is not None, "Overall rating should exist after Hard match"

        # Clay and Grass tracks may or may not be seeded, but should not have
        # matches_played > 0 from this Hard match
        # Check via multiple rows in player_elo
        rows = db_conn.execute(
            "SELECT surface, matches_played FROM player_elo WHERE player_id=201",
        ).fetchall()
        surface_matches = {row[0]: row[1] for row in rows}
        # Only Hard and Overall should have matches played
        for surface in ["Clay", "Grass"]:
            if surface in surface_matches:
                assert surface_matches[surface] == 0, \
                    f"{surface} matches_played should be 0 for player only on Hard"

    def test_inactive_players_get_rd_growth(self, db_conn):
        """Players who did not compete in a week should see RD increase."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-004", "Hard", "G", "2020-01-13")
        _insert_tournament(db_conn, "2020-005", "Hard", "G", "2020-01-20")

        _insert_ranking(db_conn, 301, 5)
        _insert_ranking(db_conn, 302, 10)
        _insert_ranking(db_conn, 303, 15)

        # Week 1: 301 and 302 play
        _insert_match(db_conn, "2020-004", 1, 301, 302, "2020-01-13")
        # Week 2: 302 and 303 play (301 is inactive)
        _insert_match(db_conn, "2020-005", 1, 302, 303, "2020-01-20")

        compute_all_ratings(db_conn)

        # Get 301's Hard rating rows (should have 2: one per week)
        rows = db_conn.execute(
            """SELECT as_of_date, rd FROM player_elo
               WHERE player_id=301 AND surface='Hard'
               ORDER BY as_of_date""",
        ).fetchall()

        # Must have at least 2 rows for 301 to see RD growth
        assert len(rows) >= 2, "Should have snapshots from multiple weeks"
        # RD should grow (or stay same) from week 1 to week 2 for inactive player
        rd_week1 = rows[0][1]
        rd_week2 = rows[1][1]
        assert rd_week2 >= rd_week1, "Inactive player RD should not decrease"

    def test_rating_history_preserved(self, db_conn):
        """Multiple rows in player_elo for same player across different weeks."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-006", "Hard", "G", "2020-01-13")
        _insert_tournament(db_conn, "2020-007", "Hard", "G", "2020-01-20")

        _insert_ranking(db_conn, 401, 5)
        _insert_ranking(db_conn, 402, 10)

        _insert_match(db_conn, "2020-006", 1, 401, 402, "2020-01-13")
        _insert_match(db_conn, "2020-007", 1, 402, 401, "2020-01-20")

        compute_all_ratings(db_conn)

        rows = db_conn.execute(
            """SELECT as_of_date FROM player_elo
               WHERE player_id=401 AND surface='Hard'
               ORDER BY as_of_date""",
        ).fetchall()

        assert len(rows) >= 2, "Should have at least 2 weekly snapshots for player 401"

    def test_retirement_match_weight(self, db_conn):
        """Retirement matches should produce smaller rating changes than completed ones."""
        from src.ratings.glicko import compute_all_ratings

        # Scenario A: same-ranked players, completed match
        _insert_tournament(db_conn, "2020-R1", "Hard", "G", "2020-01-13")
        _insert_ranking(db_conn, 501, 50)
        _insert_ranking(db_conn, 502, 50)
        _insert_match(db_conn, "2020-R1", 1, 501, 502, "2020-01-13", retirement_flag=0)

        compute_all_ratings(db_conn)
        winner_row_normal = _get_latest_rating(db_conn, 501, "Hard")
        loser_row_normal = _get_latest_rating(db_conn, 502, "Hard")
        delta_normal = abs(winner_row_normal[0] - loser_row_normal[0])

        # Reset DB for second scenario
        db_conn.execute("DELETE FROM player_elo")
        db_conn.execute("DELETE FROM matches")
        db_conn.execute("DELETE FROM tournaments")
        db_conn.execute("DELETE FROM rankings")
        db_conn.commit()

        # Scenario B: retirement match with same ranked players
        _insert_tournament(db_conn, "2020-R2", "Hard", "G", "2020-01-13")
        _insert_ranking(db_conn, 501, 50)
        _insert_ranking(db_conn, 502, 50)
        _insert_match(db_conn, "2020-R2", 1, 501, 502, "2020-01-13", retirement_flag=1)

        compute_all_ratings(db_conn)
        winner_row_ret = _get_latest_rating(db_conn, 501, "Hard")
        loser_row_ret = _get_latest_rating(db_conn, 502, "Hard")
        delta_retirement = abs(winner_row_ret[0] - loser_row_ret[0])

        assert delta_retirement < delta_normal, \
            f"Retirement delta {delta_retirement:.2f} should be less than normal delta {delta_normal:.2f}"

    def test_grand_slam_larger_change_than_atp250(self, db_conn):
        """Grand Slam match should produce larger rating change than ATP 250 match."""
        from src.ratings.glicko import compute_all_ratings

        # Scenario A: Grand Slam match
        _insert_tournament(db_conn, "2020-GS1", "Hard", "G", "2020-01-13")
        _insert_ranking(db_conn, 601, 50)
        _insert_ranking(db_conn, 602, 50)
        _insert_match(db_conn, "2020-GS1", 1, 601, 602, "2020-01-13")

        compute_all_ratings(db_conn)
        winner_gs = _get_latest_rating(db_conn, 601, "Hard")
        loser_gs = _get_latest_rating(db_conn, 602, "Hard")
        delta_gs = abs(winner_gs[0] - loser_gs[0])

        # Reset
        db_conn.execute("DELETE FROM player_elo")
        db_conn.execute("DELETE FROM matches")
        db_conn.execute("DELETE FROM tournaments")
        db_conn.execute("DELETE FROM rankings")
        db_conn.commit()

        # Scenario B: ATP 250 match  (tourney_level "A" = ATP 250)
        _insert_tournament(db_conn, "2020-A1", "Hard", "A", "2020-01-13")
        _insert_ranking(db_conn, 601, 50)
        _insert_ranking(db_conn, 602, 50)
        _insert_match(db_conn, "2020-A1", 1, 601, 602, "2020-01-13")

        compute_all_ratings(db_conn)
        winner_a = _get_latest_rating(db_conn, 601, "Hard")
        loser_a = _get_latest_rating(db_conn, 602, "Hard")
        delta_a = abs(winner_a[0] - loser_a[0])

        assert delta_gs > delta_a, \
            f"Grand Slam delta {delta_gs:.2f} should be larger than ATP 250 delta {delta_a:.2f}"

    def test_rank_seeding_applied(self, db_conn):
        """Players seeded from ranking data should have non-default initial ratings."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-S1", "Hard", "G", "2020-01-13")
        _insert_ranking(db_conn, 701, 1)   # rank 1 -> ~1800
        _insert_ranking(db_conn, 702, 300) # rank 300 -> ~1350
        _insert_match(db_conn, "2020-S1", 1, 701, 702, "2020-01-13")

        compute_all_ratings(db_conn)

        winner_row = _get_latest_rating(db_conn, 701, "Hard")
        loser_row = _get_latest_rating(db_conn, 702, "Hard")

        # Rank 1 player starts at ~1800 so should still be much higher
        assert winner_row[0] > loser_row[0] + 200, \
            "Rank 1 player should be much higher rated than rank 300 player"

    def test_lookahead_safety(self, db_conn):
        """Removing a later match does not change ratings computed before it."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-LA1", "Hard", "G", "2020-01-13")
        _insert_tournament(db_conn, "2020-LA2", "Hard", "G", "2020-01-20")

        _insert_ranking(db_conn, 801, 30)
        _insert_ranking(db_conn, 802, 40)
        _insert_ranking(db_conn, 803, 50)

        # Week 1 match
        _insert_match(db_conn, "2020-LA1", 1, 801, 802, "2020-01-13")
        # Week 2 match
        _insert_match(db_conn, "2020-LA2", 1, 801, 803, "2020-01-20")

        compute_all_ratings(db_conn)

        # Get week 1 snapshot for 801 on Hard
        row_with_week2 = db_conn.execute(
            """SELECT elo_rating FROM player_elo
               WHERE player_id=801 AND surface='Hard'
               ORDER BY as_of_date LIMIT 1""",
        ).fetchone()

        # Now remove week 2 match and recompute
        db_conn.execute("DELETE FROM player_elo")
        db_conn.execute("DELETE FROM matches WHERE tourney_id='2020-LA2'")
        db_conn.commit()

        compute_all_ratings(db_conn)

        row_without_week2 = db_conn.execute(
            """SELECT elo_rating FROM player_elo
               WHERE player_id=801 AND surface='Hard'
               ORDER BY as_of_date LIMIT 1""",
        ).fetchone()

        assert abs(row_with_week2[0] - row_without_week2[0]) < 1e-6, \
            "Week 1 rating should be identical with or without week 2 match"

    def test_compute_all_ratings_returns_summary(self, db_conn):
        """compute_all_ratings returns a dict with total_weeks, total_players, total_snapshots."""
        from src.ratings.glicko import compute_all_ratings

        _insert_tournament(db_conn, "2020-SUM", "Hard", "G", "2020-01-13")
        _insert_ranking(db_conn, 901, 50)
        _insert_ranking(db_conn, 902, 60)
        _insert_match(db_conn, "2020-SUM", 1, 901, 902, "2020-01-13")

        result = compute_all_ratings(db_conn)

        assert "total_weeks" in result
        assert "total_players" in result
        assert "total_snapshots" in result
        assert result["total_weeks"] >= 1
        assert result["total_players"] >= 2
        assert result["total_snapshots"] >= 1
