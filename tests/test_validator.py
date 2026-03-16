"""
Tests for src/ingestion/validator.py.

All tests use the db_conn fixture (in-memory SQLite with full schema).
Test data is inserted directly to verify each validation check.
"""
import sqlite3
from datetime import date

import pytest

from src.ingestion.validator import (
    check_date_ordering,
    check_duplicates,
    check_retirement_ratio,
    check_row_counts,
    check_stats_completeness,
    check_temporal_safety,
    validate_database,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_match(
    conn: sqlite3.Connection,
    tourney_id: str = "2023-0001",
    match_num: int = 1,
    tour: str = "ATP",
    tourney_date: str = "2023-01-15",
    match_type: str = "completed",
    retirement_flag: int = 0,
    stats_missing: int = 0,
) -> None:
    """Insert a minimal match row and a corresponding tournament row."""
    conn.execute(
        """
        INSERT OR IGNORE INTO tournaments (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
        VALUES (?, ?, 'Test Tournament', 'Hard', 64, 'A', ?)
        """,
        (tourney_id, tour, tourney_date),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO matches
            (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
             minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
        VALUES (?, ?, ?, 101, 102, '6-3 6-4', 'QF', 5, 90, ?, ?, ?, 0, ?)
        """,
        (tourney_id, match_num, tour, tourney_date, match_type, retirement_flag, stats_missing),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# check_duplicates
# ---------------------------------------------------------------------------

class TestCheckDuplicates:
    def test_no_duplicates_clean_data(self, db_conn):
        """Empty result when no duplicate (tourney_id, match_num, tour) tuples exist."""
        _insert_match(db_conn, tourney_id="2023-0001", match_num=1)
        _insert_match(db_conn, tourney_id="2023-0001", match_num=2)
        _insert_match(db_conn, tourney_id="2023-0002", match_num=1)

        result = check_duplicates(db_conn)
        assert result == [], f"Expected no duplicates, got: {result}"

    def test_detects_manually_inserted_duplicate(self):
        """
        Detect duplicates when the detection query runs against a DB that has
        duplicates (simulated via a shadow connection with a weaker schema).

        This tests the check_duplicates SQL logic itself. In production the
        PRIMARY KEY constraint prevents duplicates; here we use a no-PK schema
        to simulate what the query would find if duplicates somehow existed.
        """
        # Build a special in-memory DB with a matches table that has no PK constraint
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE matches (
                tourney_id TEXT,
                match_num  INTEGER,
                tour       TEXT,
                winner_id  INTEGER,
                loser_id   INTEGER
            )
            """
        )
        # Insert two rows with the same (tourney_id, match_num, tour)
        conn.execute(
            "INSERT INTO matches VALUES ('2023-0001', 1, 'ATP', 101, 102)"
        )
        conn.execute(
            "INSERT INTO matches VALUES ('2023-0001', 1, 'ATP', 103, 104)"
        )
        conn.commit()

        result = check_duplicates(conn)
        conn.close()

        assert len(result) == 1, f"Expected 1 duplicate group, got: {result}"
        dup = result[0]
        assert dup["tourney_id"] == "2023-0001"
        assert dup["match_num"] == 1
        assert dup["tour"] == "ATP"
        assert dup["count"] >= 2


# ---------------------------------------------------------------------------
# check_retirement_ratio
# ---------------------------------------------------------------------------

class TestCheckRetirementRatio:
    def _insert_n_matches(self, conn, n_completed: int, n_retirements: int):
        """Insert completed + retirement matches in a single tournament."""
        tourney_id = "2023-0010"
        conn.execute(
            """
            INSERT OR IGNORE INTO tournaments
                (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
            VALUES (?, 'ATP', 'Big Tour', 'Clay', 128, 'A', '2023-05-01')
            """,
            (tourney_id,),
        )
        match_num = 1
        for i in range(n_completed):
            conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 101, 102, '6-3 6-4', 'R32', 5, 90,
                        '2023-05-01', 'completed', 0, 0, 0)
                """,
                (tourney_id, match_num),
            )
            match_num += 1
        for i in range(n_retirements):
            conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 103, 104, '6-2 3-1 RET', 'R32', 5, 45,
                        '2023-05-01', 'retirement', 1, 0, 0)
                """,
                (tourney_id, match_num),
            )
            match_num += 1
        conn.commit()

    def test_retirement_ratio_in_range(self, db_conn):
        """96 completed + 4 retirements = 4% ratio — should be in_range=True."""
        self._insert_n_matches(db_conn, n_completed=96, n_retirements=4)
        result = check_retirement_ratio(db_conn)

        assert result["total"] == 100
        assert result["retirements"] == 4
        assert abs(result["ratio"] - 0.04) < 0.001
        assert result["in_range"] is True

    def test_retirement_ratio_out_of_range(self, db_conn):
        """85 completed + 15 retirements = 15% ratio — should be in_range=False."""
        self._insert_n_matches(db_conn, n_completed=85, n_retirements=15)
        result = check_retirement_ratio(db_conn)

        assert result["total"] == 100
        assert result["retirements"] == 15
        assert abs(result["ratio"] - 0.15) < 0.001
        assert result["in_range"] is False


# ---------------------------------------------------------------------------
# check_date_ordering
# ---------------------------------------------------------------------------

class TestCheckDateOrdering:
    def test_valid_iso_dates(self, db_conn):
        """Matches with ISO YYYY-MM-DD dates → valid_format=True."""
        _insert_match(db_conn, tourney_id="2023-0001", match_num=1, tourney_date="2023-01-15")
        _insert_match(db_conn, tourney_id="2023-0002", match_num=1, tourney_date="2023-06-05")
        _insert_match(db_conn, tourney_id="2023-0003", match_num=1, tourney_date="2023-09-10")

        result = check_date_ordering(db_conn)
        assert result["valid_format"] is True
        assert result["invalid_dates"] == []

    def test_invalid_date_format(self, db_conn):
        """Match with date '20240101' (no dashes) → valid_format=False."""
        # Insert tournament with the bad date first (bypassing FK to test the validator)
        db_conn.execute("PRAGMA foreign_keys = OFF")
        db_conn.execute(
            """
            INSERT INTO matches
                (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                 minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
            VALUES ('2024-0001', 1, 'ATP', 101, 102, '6-3 6-4', 'QF', 5, 90,
                    '20240101', 'completed', 0, 0, 0)
            """,
        )
        db_conn.execute("PRAGMA foreign_keys = ON")
        db_conn.commit()

        result = check_date_ordering(db_conn)
        assert result["valid_format"] is False
        assert "20240101" in result["invalid_dates"]


# ---------------------------------------------------------------------------
# check_stats_completeness
# ---------------------------------------------------------------------------

class TestCheckStatsCompleteness:
    def test_per_year_breakdown(self, db_conn):
        """Verify per-year missing stats breakdown is correct."""
        # 2022: 4 matches, 1 missing stats
        tourney_id_22 = "2022-0001"
        db_conn.execute(
            """
            INSERT OR IGNORE INTO tournaments
                (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
            VALUES (?, 'ATP', 'Tour 2022', 'Hard', 64, 'A', '2022-03-01')
            """,
            (tourney_id_22,),
        )
        for i in range(1, 5):
            missing = 1 if i == 4 else 0
            db_conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 101, 102, '6-3 6-4', 'QF', 5, 90,
                        '2022-03-01', 'completed', 0, 0, ?)
                """,
                (tourney_id_22, i, missing),
            )
        # 2023: 2 matches, both missing stats
        tourney_id_23 = "2023-0001"
        db_conn.execute(
            """
            INSERT OR IGNORE INTO tournaments
                (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
            VALUES (?, 'ATP', 'Tour 2023', 'Grass', 64, 'A', '2023-06-01')
            """,
            (tourney_id_23,),
        )
        for i in range(1, 3):
            db_conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 103, 104, '6-4 6-3', 'R16', 5, 85,
                        '2023-06-01', 'completed', 0, 0, 1)
                """,
                (tourney_id_23, i),
            )
        db_conn.commit()

        result = check_stats_completeness(db_conn)

        assert "by_year" in result
        assert 2022 in result["by_year"]
        assert 2023 in result["by_year"]

        yr22 = result["by_year"][2022]
        assert yr22["total"] == 4
        assert yr22["missing"] == 1
        assert abs(yr22["pct_missing"] - 0.25) < 0.01

        yr23 = result["by_year"][2023]
        assert yr23["total"] == 2
        assert yr23["missing"] == 2
        assert abs(yr23["pct_missing"] - 1.0) < 0.01

        # overall_missing_pct: 3 missing out of 6 total = 50%
        assert abs(result["overall_missing_pct"] - 0.5) < 0.01

    def test_identifies_high_missing_year(self, db_conn):
        """Year with >50% missing stats is identifiable in the by_year breakdown."""
        tourney_id = "2019-0001"
        db_conn.execute(
            """
            INSERT OR IGNORE INTO tournaments
                (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
            VALUES (?, 'ATP', 'Old Tour', 'Clay', 32, 'A', '2019-04-01')
            """,
            (tourney_id,),
        )
        for i in range(1, 11):
            missing = 1 if i <= 8 else 0  # 80% missing
            db_conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 101, 102, '6-3 6-4', 'QF', 5, 90,
                        '2019-04-01', 'completed', 0, 0, ?)
                """,
                (tourney_id, i, missing),
            )
        db_conn.commit()

        result = check_stats_completeness(db_conn)
        yr = result["by_year"][2019]
        assert yr["pct_missing"] > 0.50, "Expected >50% missing for 2019 test data"


# ---------------------------------------------------------------------------
# check_temporal_safety
# ---------------------------------------------------------------------------

class TestCheckTemporalSafety:
    def test_feature_tables_empty_safe(self, db_conn):
        """player_elo table should be empty in Phase 1 → safe=True."""
        result = check_temporal_safety(db_conn)
        assert result["feature_tables_empty"] is True
        assert result["safe"] is True

    def test_feature_tables_non_empty_unsafe(self, db_conn):
        """If player_elo has rows → feature_tables_empty=False, safe=False."""
        db_conn.execute(
            """
            INSERT INTO player_elo (player_id, tour, surface, as_of_date, elo_rating, matches_played)
            VALUES (101, 'ATP', 'Hard', '2023-01-01', 1520.0, 10)
            """
        )
        db_conn.commit()

        result = check_temporal_safety(db_conn)
        assert result["feature_tables_empty"] is False
        assert result["safe"] is False


# ---------------------------------------------------------------------------
# validate_database (combined)
# ---------------------------------------------------------------------------

class TestValidateDatabase:
    def test_overall_valid_clean_data(self, db_conn):
        """validate_database returns overall_valid=True for clean, well-formed data."""
        # Insert 100 matches: 96 completed + 4 retirements, all with ISO dates
        tourney_id = "2023-0099"
        db_conn.execute(
            """
            INSERT OR IGNORE INTO tournaments
                (tourney_id, tour, tourney_name, surface, draw_size, tourney_level, tourney_date)
            VALUES (?, 'ATP', 'Validation Test', 'Hard', 128, 'A', '2023-03-01')
            """,
            (tourney_id,),
        )
        match_num = 1
        for i in range(96):
            db_conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 101, 102, '6-3 6-4', 'R32', 5, 90,
                        '2023-03-01', 'completed', 0, 0, 0)
                """,
                (tourney_id, match_num),
            )
            match_num += 1
        for i in range(4):
            db_conn.execute(
                """
                INSERT INTO matches
                    (tourney_id, match_num, tour, winner_id, loser_id, score, round, best_of,
                     minutes, tourney_date, match_type, retirement_flag, stats_normalized, stats_missing)
                VALUES (?, ?, 'ATP', 103, 104, '6-2 3-1 RET', 'R32', 5, 45,
                        '2023-03-01', 'retirement', 1, 0, 0)
                """,
                (tourney_id, match_num),
            )
            match_num += 1
        db_conn.commit()

        result = validate_database(db_conn)

        assert "duplicates" in result
        assert "retirement_ratio" in result
        assert "date_ordering" in result
        assert "stats_completeness" in result
        assert "temporal_safety" in result
        assert "row_counts" in result
        assert "overall_valid" in result

        assert result["overall_valid"] is True
        assert result["duplicates"] == []
        assert result["retirement_ratio"]["in_range"] is True
        assert result["date_ordering"]["valid_format"] is True
        assert result["temporal_safety"]["safe"] is True
