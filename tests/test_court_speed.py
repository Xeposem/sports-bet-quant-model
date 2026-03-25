"""
Tests for src/features/court_speed.py

Covers:
- compute_court_speed_index stores one CSI row per qualifying tournament
- Tournaments with fewer than min_matches are skipped (has_no_csi fallback)
- _get_csi returns fallback with has_no_csi=1 for missing tournaments
- compute_player_speed_affinity returns fast_wr - slow_wr differential
- migrate_csi_columns is idempotent (no error on second run, columns exist)
"""
import sqlite3

import pytest

from src.features.court_speed import (
    compute_court_speed_index,
    _get_csi,
    compute_player_speed_affinity,
    migrate_csi_columns,
)


# ---------------------------------------------------------------------------
# Helpers to build a minimal in-memory DB with required schema
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    """Create an in-memory DB and apply the project schema."""
    from src.db.connection import get_connection, _read_schema_sql
    conn = get_connection(":memory:")
    conn.executescript(_read_schema_sql())
    return conn


def _insert_tournament(conn, tourney_id="T001", tour="ATP", surface="Hard", date="2023-01-15"):
    conn.execute(
        "INSERT OR IGNORE INTO tournaments (tourney_id, tour, tourney_name, surface, tourney_level, tourney_date)"
        " VALUES (?, ?, 'Test Open', ?, 'G', ?)",
        (tourney_id, tour, surface, date),
    )
    conn.commit()


def _insert_match(conn, tourney_id="T001", match_num=1, tour="ATP",
                  winner_id=1, loser_id=2, date="2023-01-15"):
    conn.execute(
        "INSERT OR IGNORE INTO matches (tourney_id, match_num, tour, winner_id, loser_id,"
        " score, round, best_of, tourney_date)"
        " VALUES (?, ?, ?, ?, ?, '6-3 6-4', 'QF', 3, ?)",
        (tourney_id, match_num, tour, winner_id, loser_id, date),
    )
    conn.commit()


def _insert_match_stats(conn, tourney_id="T001", match_num=1, tour="ATP",
                         player_role="winner", ace=10, svpt=80, first_in=50, first_won=35):
    conn.execute(
        "INSERT OR IGNORE INTO match_stats "
        "(tourney_id, match_num, tour, player_role, ace, df, svpt, first_in, first_won)"
        " VALUES (?, ?, ?, ?, ?, 2, ?, ?, ?)",
        (tourney_id, match_num, tour, player_role, ace, svpt, first_in, first_won),
    )
    conn.commit()


def _seed_tournament_matches(conn, tourney_id="T001", tour="ATP", surface="Hard",
                               date="2023-01-15", n_matches=15,
                               winner_id_start=1, loser_id_start=100):
    """Insert n_matches matches with match_stats for a tournament."""
    _insert_tournament(conn, tourney_id=tourney_id, tour=tour, surface=surface, date=date)
    for i in range(1, n_matches + 1):
        _insert_match(conn, tourney_id=tourney_id, match_num=i, tour=tour,
                      winner_id=winner_id_start + i, loser_id=loser_id_start + i, date=date)
        # Insert stats for both roles
        _insert_match_stats(conn, tourney_id=tourney_id, match_num=i, tour=tour,
                             player_role="winner", ace=8, svpt=80, first_in=50, first_won=36)
        _insert_match_stats(conn, tourney_id=tourney_id, match_num=i, tour=tour,
                             player_role="loser", ace=4, svpt=75, first_in=45, first_won=28)


# ---------------------------------------------------------------------------
# Test: compute_court_speed_index
# ---------------------------------------------------------------------------

class TestComputeCourtSpeedIndex:
    def test_compute_csi(self):
        """One qualifying tournament (>=10 matches) gets a CSI row with value in [0, 1]."""
        conn = _make_db()
        _seed_tournament_matches(conn, tourney_id="T001", n_matches=15)

        result = compute_court_speed_index(conn)

        assert result["tournaments_computed"] == 1
        row = conn.execute(
            "SELECT csi_value, n_matches FROM court_speed_index WHERE tourney_id='T001'"
        ).fetchone()
        assert row is not None
        csi_value, n_matches = row
        assert 0.0 <= csi_value <= 1.0
        # Distinct match count
        assert n_matches == 15

    def test_csi_min_matches_threshold(self):
        """Tournament with fewer than 10 matches is skipped."""
        conn = _make_db()
        _seed_tournament_matches(conn, tourney_id="T002", n_matches=5)

        result = compute_court_speed_index(conn, min_matches=10)

        assert result["tournaments_computed"] == 0
        assert result["tournaments_skipped"] >= 1
        row = conn.execute(
            "SELECT csi_value FROM court_speed_index WHERE tourney_id='T002'"
        ).fetchone()
        assert row is None

    def test_csi_value_between_zero_and_one(self):
        """CSI normalization keeps all values in [0, 1] for multiple tournaments."""
        conn = _make_db()
        # Fast court: many aces
        _insert_tournament(conn, tourney_id="FAST", surface="Grass", date="2022-06-01")
        for i in range(1, 16):
            _insert_match(conn, tourney_id="FAST", match_num=i, winner_id=i, loser_id=100 + i, date="2022-06-01")
            _insert_match_stats(conn, tourney_id="FAST", match_num=i, player_role="winner",
                                 ace=20, svpt=80, first_in=50, first_won=45)
            _insert_match_stats(conn, tourney_id="FAST", match_num=i, player_role="loser",
                                 ace=15, svpt=75, first_in=45, first_won=40)

        # Slow court: few aces
        _insert_tournament(conn, tourney_id="SLOW", surface="Clay", date="2022-05-01")
        for i in range(1, 16):
            _insert_match(conn, tourney_id="SLOW", match_num=i, winner_id=200 + i,
                          loser_id=300 + i, date="2022-05-01")
            _insert_match_stats(conn, tourney_id="SLOW", match_num=i, player_role="winner",
                                 ace=2, svpt=80, first_in=45, first_won=26)
            _insert_match_stats(conn, tourney_id="SLOW", match_num=i, player_role="loser",
                                 ace=1, svpt=75, first_in=40, first_won=22)

        result = compute_court_speed_index(conn, min_matches=10)
        assert result["tournaments_computed"] == 2

        rows = conn.execute("SELECT csi_value FROM court_speed_index").fetchall()
        for (v,) in rows:
            assert 0.0 <= v <= 1.0

    def test_compute_csi_idempotent(self):
        """Running compute_court_speed_index twice does not create duplicate rows."""
        conn = _make_db()
        _seed_tournament_matches(conn, n_matches=15)

        compute_court_speed_index(conn)
        compute_court_speed_index(conn)

        count = conn.execute("SELECT COUNT(*) FROM court_speed_index").fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# Test: _get_csi fallback logic
# ---------------------------------------------------------------------------

class TestGetCsi:
    def test_get_csi_exact_match(self):
        """_get_csi returns exact row with has_no_csi=0 when tournament is found."""
        conn = _make_db()
        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('T001', 'ATP', 'Hard', 0.72, 30, '2023-01-15T00:00:00')"
        )
        conn.commit()

        result = _get_csi(conn, "T001", "Hard", "ATP")

        assert result["has_no_csi"] == 0
        assert abs(result["court_speed_index"] - 0.72) < 1e-9

    def test_csi_fallback(self):
        """_get_csi returns surface average with has_no_csi=1 for missing tournament."""
        conn = _make_db()
        # Only "T001" (Hard) is in the table — "T999" is not
        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('T001', 'ATP', 'Hard', 0.60, 20, '2023-01-15T00:00:00')"
        )
        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('T002', 'ATP', 'Hard', 0.80, 25, '2023-01-15T00:00:00')"
        )
        conn.commit()

        result = _get_csi(conn, "T999", "Hard", "ATP")

        assert result["has_no_csi"] == 1
        # Should be average of Hard courts: (0.60 + 0.80) / 2 = 0.70
        assert abs(result["court_speed_index"] - 0.70) < 1e-6

    def test_csi_global_fallback_when_no_surface_match(self):
        """_get_csi falls back to global average when surface has no rows."""
        conn = _make_db()
        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('T001', 'ATP', 'Grass', 0.90, 20, '2023-01-15T00:00:00')"
        )
        conn.commit()

        # Requesting a Clay tournament not in table
        result = _get_csi(conn, "T999", "Clay", "ATP")
        assert result["has_no_csi"] == 1
        # Falls back to global average (only Grass row = 0.90)
        assert abs(result["court_speed_index"] - 0.90) < 1e-6

    def test_csi_default_when_empty_table(self):
        """_get_csi returns 0.5 with has_no_csi=1 when court_speed_index table is empty."""
        conn = _make_db()

        result = _get_csi(conn, "T999", "Hard", "ATP")

        assert result["has_no_csi"] == 1
        assert result["court_speed_index"] == 0.5


# ---------------------------------------------------------------------------
# Test: compute_player_speed_affinity
# ---------------------------------------------------------------------------

class TestComputePlayerSpeedAffinity:
    def test_compute_player_speed_affinity(self):
        """Player with many wins on fast courts gets positive affinity."""
        conn = _make_db()

        # Two tournaments: one fast (CSI=0.9), one slow (CSI=0.1)
        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('FAST', 'ATP', 'Grass', 0.9, 20, '2023-01-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('SLOW', 'ATP', 'Clay', 0.1, 20, '2023-01-01T00:00:00')"
        )
        conn.commit()

        # Insert tournaments
        _insert_tournament(conn, tourney_id="FAST", surface="Grass", date="2022-01-01")
        _insert_tournament(conn, tourney_id="SLOW", surface="Clay", date="2022-03-01")

        player_id = 1
        # Player wins 5 matches on fast court
        for i in range(1, 6):
            _insert_match(conn, tourney_id="FAST", match_num=i, winner_id=player_id,
                          loser_id=100 + i, date="2022-01-10")
        # Player loses 5 matches on slow court
        for i in range(1, 6):
            _insert_match(conn, tourney_id="SLOW", match_num=i, winner_id=200 + i,
                          loser_id=player_id, date="2022-03-10")

        affinity = compute_player_speed_affinity(
            conn, player_id=player_id, match_date="2023-06-01", min_matches_per_tier=5
        )

        # fast_wr = 5/5 = 1.0, slow_wr = 0/5 = 0.0 → affinity = 1.0
        assert affinity == pytest.approx(1.0)

    def test_player_affinity_neutral_when_below_min_matches(self):
        """Player affinity defaults to 0.0 when below min_matches_per_tier threshold."""
        conn = _make_db()

        conn.execute(
            "INSERT INTO court_speed_index (tourney_id, tour, surface, csi_value, n_matches, computed_at)"
            " VALUES ('FAST', 'ATP', 'Grass', 0.9, 20, '2023-01-01T00:00:00')"
        )
        conn.commit()

        _insert_tournament(conn, tourney_id="FAST", surface="Grass", date="2022-01-01")

        player_id = 5
        # Only 2 matches on fast court — below min_matches_per_tier=5
        for i in range(1, 3):
            _insert_match(conn, tourney_id="FAST", match_num=i, winner_id=player_id,
                          loser_id=100 + i, date="2022-01-10")

        affinity = compute_player_speed_affinity(
            conn, player_id=player_id, match_date="2023-06-01", min_matches_per_tier=5
        )

        # Both tiers below threshold → 0.5 - 0.5 = 0.0
        assert affinity == pytest.approx(0.0)

    def test_player_affinity_zero_when_no_history(self):
        """Player with no match history returns affinity=0.0."""
        conn = _make_db()

        affinity = compute_player_speed_affinity(
            conn, player_id=9999, match_date="2023-06-01"
        )

        assert affinity == pytest.approx(0.0)

    def test_player_affinity_zero_when_no_csi_data(self):
        """Player affinity is 0.0 when court_speed_index table is empty."""
        conn = _make_db()

        affinity = compute_player_speed_affinity(conn, player_id=1, match_date="2023-06-01")

        assert affinity == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test: migrate_csi_columns
# ---------------------------------------------------------------------------

class TestMigrateCsiColumns:
    def test_migrate_csi_columns_adds_columns(self):
        """migrate_csi_columns adds court_speed_index, has_no_csi, speed_affinity to match_features."""
        conn = _make_db()
        migrate_csi_columns(conn)

        cols = [row[1] for row in conn.execute("PRAGMA table_info(match_features)").fetchall()]
        assert "court_speed_index" in cols
        assert "has_no_csi" in cols
        assert "speed_affinity" in cols

    def test_migrate_csi_columns_idempotent(self):
        """Running migrate_csi_columns twice raises no error and columns still exist."""
        conn = _make_db()
        migrate_csi_columns(conn)
        migrate_csi_columns(conn)  # second call must not raise

        cols = [row[1] for row in conn.execute("PRAGMA table_info(match_features)").fetchall()]
        assert "court_speed_index" in cols
        assert "has_no_csi" in cols
        assert "speed_affinity" in cols
