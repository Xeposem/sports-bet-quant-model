"""
Tests for src/ingestion/loader.py

Covers:
- upsert_matches inserts records
- upsert_matches with duplicate primary key skips duplicate (ON CONFLICT DO NOTHING)
- Re-running upsert_matches is idempotent
- upsert_tournaments inserts tournament records
- upsert_players extracts unique player records from match data
- upsert_match_stats splits winner/loser stats into separate rows
- log_ingestion creates an ingestion_log entry
- ingest_year orchestrates download->clean->load (mock download)
- No duplicate (tourney_id, match_num, tour) rows after ingestion
- tourney_date values match ISO format YYYY-MM-DD
- get_unprocessed_years excludes already-ingested years
- Chronological ordering of tourney_date
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.ingestion.loader import (
    upsert_matches,
    upsert_players,
    upsert_tournaments,
    upsert_match_stats,
    log_ingestion,
    ingest_year,
    get_unprocessed_years,
)
from src.ingestion.cleaner import clean_match_dataframe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cleaned_df(sample_match_df):
    """Return cleaned, non-excluded rows from the sample fixture."""
    cleaned, _ = clean_match_dataframe(sample_match_df)
    return cleaned


# ---------------------------------------------------------------------------
# upsert_matches
# ---------------------------------------------------------------------------

class TestUpsertMatches:
    def test_inserts_records(self, db_conn, sample_match_df):
        """upsert_matches inserts records into the matches table."""
        cleaned = _get_cleaned_df(sample_match_df)
        # Must upsert tournaments first (foreign key dependency)
        upsert_tournaments(db_conn, cleaned)
        records = cleaned.to_dict(orient="records")
        inserted, skipped = upsert_matches(db_conn, records)
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        assert count == len(records)
        assert inserted == len(records)
        assert skipped == 0

    def test_duplicate_primary_key_skipped(self, db_conn, sample_match_df):
        """Inserting the same records twice keeps only the original (ON CONFLICT DO NOTHING)."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        records = cleaned.to_dict(orient="records")

        # First insert
        upsert_matches(db_conn, records)
        db_conn.commit()

        # Second insert — all should be skipped
        inserted, skipped = upsert_matches(db_conn, records)
        db_conn.commit()

        assert inserted == 0
        assert skipped == len(records)

    def test_idempotent_reingest(self, db_conn, sample_match_df):
        """Row count is unchanged after reinserting the same data."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        records = cleaned.to_dict(orient="records")

        upsert_matches(db_conn, records)
        db_conn.commit()
        count_before = db_conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

        upsert_matches(db_conn, records)
        db_conn.commit()
        count_after = db_conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

        assert count_before == count_after


# ---------------------------------------------------------------------------
# upsert_tournaments
# ---------------------------------------------------------------------------

class TestUpsertTournaments:
    def test_inserts_tournament_records(self, db_conn, sample_match_df):
        """upsert_tournaments inserts unique tournament rows with correct primary key."""
        cleaned = _get_cleaned_df(sample_match_df)
        count = upsert_tournaments(db_conn, cleaned)
        db_conn.commit()

        # All rows in sample have same tourney_id — should be 1 unique tournament
        db_count = db_conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
        assert db_count >= 1

    def test_tournament_columns_stored(self, db_conn, sample_match_df):
        """Inserted tournament has tourney_id, tour, tourney_name, surface columns."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        db_conn.commit()

        row = db_conn.execute(
            "SELECT tourney_id, tour, tourney_name, surface FROM tournaments LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "2024-0021"
        assert row[1] == "ATP"


# ---------------------------------------------------------------------------
# upsert_players
# ---------------------------------------------------------------------------

class TestUpsertPlayers:
    def test_inserts_unique_players(self, db_conn, sample_match_df):
        """upsert_players extracts unique player IDs from winner/loser columns."""
        cleaned = _get_cleaned_df(sample_match_df)
        count = upsert_players(db_conn, cleaned)
        db_conn.commit()

        db_count = db_conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        assert db_count >= 1

    def test_idempotent_player_insert(self, db_conn, sample_match_df):
        """Inserting players twice yields same count (ON CONFLICT DO NOTHING)."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_players(db_conn, cleaned)
        db_conn.commit()
        count1 = db_conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]

        upsert_players(db_conn, cleaned)
        db_conn.commit()
        count2 = db_conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]

        assert count1 == count2


# ---------------------------------------------------------------------------
# upsert_match_stats
# ---------------------------------------------------------------------------

class TestUpsertMatchStats:
    def test_creates_two_rows_per_match(self, db_conn, sample_match_df):
        """upsert_match_stats creates winner and loser rows for each match with stats."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        upsert_matches(db_conn, cleaned.to_dict(orient="records"))
        db_conn.commit()

        count = upsert_match_stats(db_conn, cleaned)
        db_conn.commit()

        rows = db_conn.execute("SELECT * FROM match_stats").fetchall()
        # At least 2 rows for the match with stats
        assert len(rows) >= 2

    def test_player_role_winner_and_loser(self, db_conn, sample_match_df):
        """match_stats rows include both 'winner' and 'loser' player_role values."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        upsert_matches(db_conn, cleaned.to_dict(orient="records"))
        upsert_match_stats(db_conn, cleaned)
        db_conn.commit()

        roles = {
            row[0] for row in
            db_conn.execute("SELECT DISTINCT player_role FROM match_stats").fetchall()
        }
        assert "winner" in roles
        assert "loser" in roles

    def test_skips_rows_with_all_null_stats(self, db_conn, sample_match_df):
        """Rows where all stat columns are NaN produce no match_stats rows."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        upsert_matches(db_conn, cleaned.to_dict(orient="records"))
        upsert_match_stats(db_conn, cleaned)
        db_conn.commit()

        # The missing-stats match (match_num=5) should have no stats rows
        rows = db_conn.execute(
            "SELECT COUNT(*) FROM match_stats WHERE tourney_id='2024-0021' AND match_num=5"
        ).fetchone()[0]
        assert rows == 0


# ---------------------------------------------------------------------------
# log_ingestion
# ---------------------------------------------------------------------------

class TestLogIngestion:
    def test_creates_ingestion_log_entry(self, db_conn):
        """log_ingestion inserts a row into the ingestion_log table."""
        log_ingestion(
            db_conn,
            year=2024,
            source_file="data/raw/atp_matches_2024.csv",
            rows_processed=100,
            rows_inserted=98,
            rows_skipped=2,
            status="success",
        )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM ingestion_log").fetchone()[0]
        assert count == 1

    def test_log_entry_has_correct_values(self, db_conn):
        """Ingestion log row stores the correct year, status, and counts."""
        log_ingestion(
            db_conn,
            year=2023,
            source_file="atp_matches_2023.csv",
            rows_processed=200,
            rows_inserted=195,
            rows_skipped=5,
            status="success",
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT year, status, rows_processed, rows_inserted, rows_skipped "
            "FROM ingestion_log LIMIT 1"
        ).fetchone()
        assert row[0] == 2023
        assert row[1] == "success"
        assert row[2] == 200
        assert row[3] == 195
        assert row[4] == 5


# ---------------------------------------------------------------------------
# get_unprocessed_years
# ---------------------------------------------------------------------------

class TestGetUnprocessedYears:
    def test_excludes_already_processed_year(self, db_conn):
        """Years logged as 'success' are excluded from unprocessed list."""
        log_ingestion(
            db_conn, year=2020, source_file="atp_matches_2020.csv",
            rows_processed=100, rows_inserted=100, rows_skipped=0, status="success",
        )
        db_conn.commit()

        unprocessed = get_unprocessed_years(db_conn, start_year=2020, end_year=2022)
        assert 2020 not in unprocessed
        assert 2021 in unprocessed
        assert 2022 in unprocessed

    def test_includes_failed_years(self, db_conn):
        """Years with 'failed' status are still considered unprocessed."""
        log_ingestion(
            db_conn, year=2019, source_file="atp_matches_2019.csv",
            rows_processed=0, rows_inserted=0, rows_skipped=0, status="failed",
        )
        db_conn.commit()

        unprocessed = get_unprocessed_years(db_conn, start_year=2019, end_year=2019)
        assert 2019 in unprocessed

    def test_returns_all_years_when_nothing_processed(self, db_conn):
        """All years returned when ingestion_log is empty."""
        unprocessed = get_unprocessed_years(db_conn, start_year=2020, end_year=2022)
        assert unprocessed == [2020, 2021, 2022]


# ---------------------------------------------------------------------------
# Data integrity assertions
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_no_duplicate_matches(self, db_conn, sample_match_df):
        """No duplicate (tourney_id, match_num, tour) rows exist after ingestion."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        records = cleaned.to_dict(orient="records")
        upsert_matches(db_conn, records)
        upsert_matches(db_conn, records)  # attempt duplicate insert
        db_conn.commit()

        dupes = db_conn.execute(
            "SELECT tourney_id, match_num, tour, COUNT(*) AS cnt "
            "FROM matches GROUP BY tourney_id, match_num, tour HAVING cnt > 1"
        ).fetchall()
        assert len(dupes) == 0, f"Found duplicate matches: {dupes}"

    def test_tourney_date_iso_format(self, db_conn, sample_match_df):
        """All tourney_date values in the matches table match ISO YYYY-MM-DD format."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        upsert_matches(db_conn, cleaned.to_dict(orient="records"))
        db_conn.commit()

        rows = db_conn.execute("SELECT tourney_date FROM matches").fetchall()
        for row in rows:
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", row[0]), (
                f"tourney_date '{row[0]}' does not match YYYY-MM-DD"
            )

    def test_chronological_ordering(self, db_conn, sample_match_df):
        """ORDER BY tourney_date ASC returns dates in chronological order."""
        cleaned = _get_cleaned_df(sample_match_df)
        upsert_tournaments(db_conn, cleaned)
        upsert_matches(db_conn, cleaned.to_dict(orient="records"))
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT tourney_date FROM matches ORDER BY tourney_date ASC"
        ).fetchall()
        dates = [row[0] for row in rows]
        assert dates == sorted(dates), f"Dates not in order: {dates}"


# ---------------------------------------------------------------------------
# ingest_year integration test
# ---------------------------------------------------------------------------

class TestIngestYear:
    def test_ingest_year_orchestrates_pipeline(self, db_conn, sample_csv_path, tmp_path):
        """ingest_year calls download->clean->load and returns a summary dict."""
        # Mock download_match_file to return our pre-written CSV
        with patch("src.ingestion.loader.download_match_file", return_value=str(sample_csv_path)):
            result = ingest_year(db_conn, year=2024, raw_dir=str(tmp_path))

        assert "year" in result
        assert "inserted" in result
        assert "skipped" in result
        assert result["year"] == 2024

        # Check data made it into the DB
        count = db_conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        assert count > 0

    def test_ingest_year_logs_to_ingestion_log(self, db_conn, sample_csv_path, tmp_path):
        """After ingest_year, an ingestion_log entry exists."""
        with patch("src.ingestion.loader.download_match_file", return_value=str(sample_csv_path)):
            ingest_year(db_conn, year=2024, raw_dir=str(tmp_path))

        count = db_conn.execute("SELECT COUNT(*) FROM ingestion_log").fetchone()[0]
        assert count == 1
