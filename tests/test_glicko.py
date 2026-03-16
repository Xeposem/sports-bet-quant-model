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
