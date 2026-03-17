"""
Tests for odds module: power method devigging, CSV ingestion, fuzzy linking, manual entry,
and CLI commands (enter, import-csv, train, predict).
Phase 03-01/03-03: Odds ingestion pipeline + CLI.
"""
import json
import math
import os
import sqlite3
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Task 1: power_method_devig tests
# ---------------------------------------------------------------------------

class TestPowerMethodDevig:

    def test_devig_sum_near_even_market(self):
        """power_method_devig(1.95, 1.95) probs sum to 1.0 within 0.001 tolerance."""
        from src.odds.devig import power_method_devig
        p_a, p_b = power_method_devig(1.95, 1.95)
        assert abs(p_a + p_b - 1.0) < 0.001, f"Probs should sum to 1.0, got {p_a + p_b}"

    def test_devig_sum_heavy_favorite(self):
        """power_method_devig(1.05, 15.0) probs sum to 1.0."""
        from src.odds.devig import power_method_devig
        p_a, p_b = power_method_devig(1.05, 15.0)
        assert abs(p_a + p_b - 1.0) < 0.001, f"Probs should sum to 1.0, got {p_a + p_b}"

    def test_devig_underdog_lower_prob(self):
        """power_method_devig(2.10, 1.80) returns p_a < p_b (underdog has lower implied prob)."""
        from src.odds.devig import power_method_devig
        p_a, p_b = power_method_devig(2.10, 1.80)
        assert p_a < p_b, f"p_a ({p_a}) should be less than p_b ({p_b}) for underdog with higher odds"

    def test_devig_raises_invalid_odds_zero(self):
        """power_method_devig raises ValueError for odds = 0."""
        from src.odds.devig import power_method_devig
        with pytest.raises(ValueError):
            power_method_devig(0.0, 1.95)

    def test_devig_raises_invalid_odds_negative(self):
        """power_method_devig raises ValueError for negative odds."""
        from src.odds.devig import power_method_devig
        with pytest.raises(ValueError):
            power_method_devig(-1.5, 1.95)

    def test_devig_raises_invalid_odds_below_minimum(self):
        """power_method_devig raises ValueError for odds < 1.01."""
        from src.odds.devig import power_method_devig
        with pytest.raises(ValueError):
            power_method_devig(1.0, 1.95)

    def test_devig_vig_actually_removed(self):
        """power_method_devig(1.50, 2.60) devigged probs differ from naive 1/odds."""
        from src.odds.devig import power_method_devig
        p_a, p_b = power_method_devig(1.50, 2.60)
        naive_a = 1.0 / 1.50
        naive_b = 1.0 / 2.60
        # Naive probs sum to more than 1 (the overround/vig)
        naive_sum = naive_a + naive_b
        assert naive_sum > 1.0, "Naive probs should sum > 1 (bookmaker vig)"
        # Devigged probs sum to 1
        assert abs(p_a + p_b - 1.0) < 0.001
        # Devigged probs are different from naive (vig was removed)
        assert abs(p_a - naive_a) > 0.0001 or abs(p_b - naive_b) > 0.0001

    def test_devig_both_invalid(self):
        """power_method_devig raises ValueError when both odds are invalid."""
        from src.odds.devig import power_method_devig
        with pytest.raises(ValueError):
            power_method_devig(0.5, 0.5)

    def test_devig_probabilities_in_range(self):
        """Devigged probabilities should be between 0 and 1."""
        from src.odds.devig import power_method_devig
        p_a, p_b = power_method_devig(1.95, 1.95)
        assert 0.0 < p_a < 1.0
        assert 0.0 < p_b < 1.0


# ---------------------------------------------------------------------------
# Task 2: CSV parsing tests
# ---------------------------------------------------------------------------

class TestParseTennisDataCsv:

    def test_csv_parse_extracts_psw_psl(self, tmp_path):
        """parse_tennis_data_csv extracts Date, Winner, Loser, PSW, PSL columns."""
        from src.odds.ingester import parse_tennis_data_csv

        csv_content = (
            "Date,Tournament,Winner,Loser,PSW,PSL,Surface\n"
            "01/06/2023,Wimbledon,Djokovic N.,Federer R.,1.45,2.80,Grass\n"
            "02/06/2023,Wimbledon,Nadal R.,Murray A.,1.60,2.30,Grass\n"
        )
        csv_file = tmp_path / "test_odds.csv"
        csv_file.write_text(csv_content)

        rows = parse_tennis_data_csv(str(csv_file))
        assert len(rows) == 2
        assert rows[0]["decimal_odds_winner"] == 1.45
        assert rows[0]["decimal_odds_loser"] == 2.80

    def test_csv_parse_date_format_dayfirst(self, tmp_path):
        """parse_tennis_data_csv converts DD/MM/YYYY to ISO YYYY-MM-DD."""
        from src.odds.ingester import parse_tennis_data_csv

        csv_content = (
            "Date,Tournament,Winner,Loser,PSW,PSL\n"
            "15/03/2023,Roland Garros,Djokovic N.,Federer R.,1.45,2.80\n"
        )
        csv_file = tmp_path / "test_dates.csv"
        csv_file.write_text(csv_content)

        rows = parse_tennis_data_csv(str(csv_file))
        assert rows[0]["match_date"] == "2023-03-15"

    def test_csv_parse_skips_missing_pinnacle_odds(self, tmp_path):
        """parse_tennis_data_csv skips rows where PSW or PSL is NaN."""
        from src.odds.ingester import parse_tennis_data_csv

        csv_content = (
            "Date,Tournament,Winner,Loser,PSW,PSL\n"
            "01/06/2023,Wimbledon,Djokovic N.,Federer R.,1.45,2.80\n"
            "02/06/2023,Wimbledon,Nadal R.,Murray A.,,2.30\n"
            "03/06/2023,Wimbledon,Sinner J.,Alcaraz C.,1.70,\n"
        )
        csv_file = tmp_path / "test_missing.csv"
        csv_file.write_text(csv_content)

        rows = parse_tennis_data_csv(str(csv_file))
        assert len(rows) == 1
        assert rows[0]["winner_name"] == "Djokovic N."


# ---------------------------------------------------------------------------
# Task 2: Fuzzy linking tests
# ---------------------------------------------------------------------------

class TestFuzzyLinkPlayer:

    def test_fuzzy_link_matches_name_variant(self):
        """fuzzy_link_player matches 'Novak Djokovic' to 'Djokovic' with score >= 85 using token_set_ratio."""
        from src.odds.linker import fuzzy_link_player

        candidates = ["Djokovic", "Federer", "Nadal"]
        result = fuzzy_link_player("Novak Djokovic", candidates, threshold=85)
        assert result == "Djokovic"

    def test_fuzzy_link_returns_none_below_threshold(self):
        """fuzzy_link_player returns None when best match score < threshold."""
        from src.odds.linker import fuzzy_link_player

        candidates = ["Federer", "Nadal", "Murray"]
        result = fuzzy_link_player("Completely Different Name", candidates, threshold=85)
        assert result is None

    def test_fuzzy_link_exact_match(self):
        """fuzzy_link_player finds exact match."""
        from src.odds.linker import fuzzy_link_player

        candidates = ["Djokovic N.", "Federer R.", "Nadal R."]
        result = fuzzy_link_player("Djokovic N.", candidates, threshold=85)
        assert result == "Djokovic N."


# ---------------------------------------------------------------------------
# Task 2: link_odds_to_matches tests
# ---------------------------------------------------------------------------

def _make_test_db():
    """Create in-memory SQLite DB with schema for testing."""
    from src.db.connection import get_connection, _read_schema_sql
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema_sql = _read_schema_sql()
    conn.executescript(schema_sql)
    return conn


def _insert_test_match(conn, tourney_id="2023-001", match_num=1, tour="ATP",
                        winner_id=1001, loser_id=1002, tourney_date="2023-06-01"):
    """Insert test player and match records."""
    conn.execute(
        "INSERT OR REPLACE INTO players (player_id, tour, first_name, last_name) VALUES (?, ?, ?, ?)",
        (1001, tour, "Novak", "Djokovic")
    )
    conn.execute(
        "INSERT OR REPLACE INTO players (player_id, tour, first_name, last_name) VALUES (?, ?, ?, ?)",
        (1002, tour, "Roger", "Federer")
    )
    conn.execute(
        "INSERT OR REPLACE INTO tournaments (tourney_id, tour, tourney_name, tourney_date) VALUES (?, ?, ?, ?)",
        (tourney_id, tour, "Test Tournament", tourney_date)
    )
    conn.execute(
        """INSERT OR REPLACE INTO matches
           (tourney_id, match_num, tour, winner_id, loser_id, tourney_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tourney_id, match_num, tour, winner_id, loser_id, tourney_date)
    )
    conn.commit()
    return {"tourney_id": tourney_id, "match_num": match_num, "tour": tour}


class TestLinkOddsToMatches:

    def test_link_odds_finds_match(self):
        """link_odds_to_matches links CSV rows to match IDs via tourney_date + fuzzy player names."""
        from src.odds.linker import link_odds_to_matches

        conn = _make_test_db()
        _insert_test_match(conn)

        odds_rows = [{
            "match_date": "2023-06-01",
            "winner_name": "Djokovic N.",
            "loser_name": "Federer R.",
            "decimal_odds_winner": 1.45,
            "decimal_odds_loser": 2.80,
        }]

        linked = link_odds_to_matches(conn, odds_rows)
        assert len(linked) >= 1
        # Should have tourney_id and match_num populated
        matched = [r for r in linked if r.get("tourney_id") is not None]
        assert len(matched) >= 1

    def test_link_odds_unlinked_when_no_match(self):
        """link_odds_to_matches returns empty when no match found for date."""
        from src.odds.linker import link_odds_to_matches

        conn = _make_test_db()
        # No matches inserted

        odds_rows = [{
            "match_date": "2099-01-01",
            "winner_name": "Unknown Player",
            "loser_name": "Also Unknown",
            "decimal_odds_winner": 1.45,
            "decimal_odds_loser": 2.80,
        }]

        linked = link_odds_to_matches(conn, odds_rows)
        # Should return rows with no tourney_id (unlinked)
        unlinked = [r for r in linked if r.get("tourney_id") is None]
        assert len(unlinked) == 1


# ---------------------------------------------------------------------------
# Task 2: upsert_match_odds and manual_entry tests
# ---------------------------------------------------------------------------

class TestUpsertMatchOdds:

    def test_upsert_match_odds_inserts_row(self):
        """upsert_match_odds inserts a row into match_odds with source='csv' and is idempotent."""
        from src.odds.ingester import upsert_match_odds

        conn = _make_test_db()
        _insert_test_match(conn)

        odds_row = {
            "tourney_id": "2023-001",
            "match_num": 1,
            "tour": "ATP",
            "bookmaker": "pinnacle",
            "decimal_odds_a": 1.45,
            "decimal_odds_b": 2.80,
            "source": "csv",
        }
        result = upsert_match_odds(conn, odds_row)
        assert result is True

        # Verify it's in the DB
        row = conn.execute(
            "SELECT * FROM match_odds WHERE tourney_id=? AND match_num=?",
            ("2023-001", 1)
        ).fetchone()
        assert row is not None
        assert row["source"] == "csv"
        assert row["decimal_odds_a"] == 1.45

    def test_upsert_match_odds_is_idempotent(self):
        """upsert_match_odds can be called twice without error (INSERT OR REPLACE)."""
        from src.odds.ingester import upsert_match_odds

        conn = _make_test_db()
        _insert_test_match(conn)

        odds_row = {
            "tourney_id": "2023-001",
            "match_num": 1,
            "tour": "ATP",
            "bookmaker": "pinnacle",
            "decimal_odds_a": 1.45,
            "decimal_odds_b": 2.80,
            "source": "csv",
        }
        upsert_match_odds(conn, odds_row)
        upsert_match_odds(conn, odds_row)

        count = conn.execute("SELECT COUNT(*) FROM match_odds").fetchone()[0]
        assert count == 1


class TestManualEntry:

    def test_manual_entry_inserts_source_manual(self):
        """manual entry with valid match_id writes row with source='manual' to match_odds."""
        from src.odds.ingester import manual_entry

        conn = _make_test_db()
        _insert_test_match(conn)

        manual_entry(
            conn,
            tourney_id="2023-001",
            match_num=1,
            decimal_odds_a=1.50,
            decimal_odds_b=2.60,
            bookmaker="pinnacle",
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM match_odds WHERE tourney_id=? AND match_num=?",
            ("2023-001", 1)
        ).fetchone()
        assert row is not None
        assert row["source"] == "manual"
        assert row["decimal_odds_a"] == 1.50
        assert row["decimal_odds_b"] == 2.60

    def test_manual_entry_default_bookmaker_pinnacle(self):
        """manual_entry defaults to bookmaker='pinnacle'."""
        from src.odds.ingester import manual_entry

        conn = _make_test_db()
        _insert_test_match(conn)

        manual_entry(conn, tourney_id="2023-001", match_num=1,
                     decimal_odds_a=1.50, decimal_odds_b=2.60)
        conn.commit()

        row = conn.execute(
            "SELECT bookmaker FROM match_odds WHERE tourney_id=? AND match_num=?",
            ("2023-001", 1)
        ).fetchone()
        assert row["bookmaker"] == "pinnacle"


# ---------------------------------------------------------------------------
# Task 3 tests: CLI (src/odds/cli.py)
# ---------------------------------------------------------------------------

def _run_cli(args: list) -> int:
    """
    Helper to run the CLI main() with given sys.argv args.
    Returns 0 on success or catches SystemExit and returns its code.
    """
    from src.odds.cli import main

    with patch("sys.argv", ["cli"] + args):
        try:
            main()
            return 0
        except SystemExit as e:
            return int(e.code) if e.code is not None else 0


class TestCLIEnterCommand:
    """Tests for `cli enter` subcommand."""

    def test_enter_calls_manual_entry(self, tmp_path):
        """CLI `enter` calls manual_entry with provided args."""
        db_path = str(tmp_path / "test.db")

        with patch("src.odds.cli.manual_entry") as mock_entry, \
             patch("src.odds.cli.get_db_path", return_value=db_path), \
             patch("src.odds.cli.sqlite3") as mock_sqlite:

            mock_conn = MagicMock()
            mock_sqlite.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_sqlite.connect.return_value.__exit__ = MagicMock(return_value=False)

            with patch("sys.argv", [
                "cli", "enter",
                "--tourney-id", "2023-001",
                "--match-num", "1",
                "--odds-a", "1.60",
                "--odds-b", "2.40",
            ]):
                from src.odds.cli import main
                main()

            mock_entry.assert_called_once()
            call_kwargs = mock_entry.call_args
            assert call_kwargs is not None

    def test_enter_validates_odds_below_minimum(self, tmp_path, capsys):
        """CLI `enter` rejects odds < 1.01 with error exit."""
        with patch("sys.argv", [
            "cli", "enter",
            "--tourney-id", "2023-001",
            "--match-num", "1",
            "--odds-a", "0.90",   # invalid: < 1.01
            "--odds-b", "2.40",
        ]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_enter_validates_odds_b_below_minimum(self, tmp_path, capsys):
        """CLI `enter` rejects odds-b < 1.01 with error exit."""
        with patch("sys.argv", [
            "cli", "enter",
            "--tourney-id", "2023-001",
            "--match-num", "1",
            "--odds-a", "1.60",
            "--odds-b", "1.00",   # invalid: < 1.01
        ]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_enter_help_exits_cleanly(self):
        """CLI `enter --help` exits with code 0."""
        with patch("sys.argv", ["cli", "enter", "--help"]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestCLIImportCsvCommand:
    """Tests for `cli import-csv` subcommand."""

    def test_import_csv_calls_import_csv_odds(self, tmp_path):
        """CLI `import-csv` calls import_csv_odds with provided --file path."""
        csv_content = (
            "Date,Tournament,Winner,Loser,PSW,PSL,Surface\n"
            "01/06/2023,Wimbledon,Djokovic N.,Federer R.,1.45,2.80,Grass\n"
        )
        csv_file = tmp_path / "odds.csv"
        csv_file.write_text(csv_content)

        with patch("src.odds.cli.import_csv_odds") as mock_import, \
             patch("src.odds.cli.get_db_path", return_value=str(tmp_path / "test.db")), \
             patch("src.odds.cli.sqlite3") as mock_sqlite:

            mock_conn = MagicMock()
            mock_sqlite.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_sqlite.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_import.return_value = {"imported": 1, "unlinked": 0, "skipped_no_odds": 0}

            with patch("sys.argv", ["cli", "import-csv", "--file", str(csv_file)]):
                from src.odds.cli import main
                main()

            mock_import.assert_called_once()

    def test_import_csv_requires_file_arg(self):
        """CLI `import-csv` without --file arg exits non-zero."""
        with patch("sys.argv", ["cli", "import-csv"]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0


class TestCLITrainCommand:
    """Tests for `cli train` subcommand."""

    def test_train_requires_no_mandatory_args(self, tmp_path):
        """CLI `train` with defaults succeeds (uses mocked functions)."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.4, 0.6]])

        with patch("src.odds.cli.build_training_matrix") as mock_build, \
             patch("src.odds.cli.compute_time_weights") as mock_weights, \
             patch("src.odds.cli.temporal_split") as mock_split, \
             patch("src.odds.cli.train_and_calibrate") as mock_train, \
             patch("src.odds.cli.save_model") as mock_save, \
             patch("src.odds.cli.get_db_path", return_value=str(tmp_path / "test.db")), \
             patch("src.odds.cli.sqlite3") as mock_sqlite:

            import numpy as np
            mock_build.return_value = (
                np.array([[1.0] * 12]),
                np.array([1.0]),
                ["2023-06-01"],
            )
            mock_weights.return_value = np.array([1.0])
            mock_split.return_value = {
                "X_train": np.array([[1.0] * 12]),
                "y_train": np.array([1.0]),
                "w_train": np.array([1.0]),
                "X_val": np.array([[1.0] * 12]),
                "y_val": np.array([1.0]),
                "dates_train": ["2023-06-01"],
                "dates_val": ["2023-07-01"],
            }
            mock_train.return_value = (
                mock_model,
                {"val_brier_score": 0.25, "val_log_loss": 0.69,
                 "calibration_method": "sigmoid",
                 "brier_sigmoid": 0.25, "brier_isotonic": 0.26},
            )
            mock_conn = MagicMock()
            mock_sqlite.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_sqlite.connect.return_value.__exit__ = MagicMock(return_value=False)

            output_dir = str(tmp_path / "models")
            with patch("sys.argv", ["cli", "train", "--output-dir", output_dir]):
                from src.odds.cli import main
                main()

            mock_train.assert_called_once()
            mock_save.assert_called_once()

    def test_train_help_exits_cleanly(self):
        """CLI `train --help` exits with code 0."""
        with patch("sys.argv", ["cli", "train", "--help"]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestCLIPredictCommand:
    """Tests for `cli predict` subcommand."""

    def test_predict_requires_model_path(self):
        """CLI `predict` without --model-path exits non-zero."""
        with patch("sys.argv", ["cli", "predict"]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_predict_calls_predict_all_matches(self, tmp_path):
        """CLI `predict` loads model and calls predict_all_matches."""
        mock_model = MagicMock()
        model_path = str(tmp_path / "model.joblib")

        with patch("src.odds.cli.load_model", return_value=mock_model) as mock_load, \
             patch("src.odds.cli.predict_all_matches") as mock_predict, \
             patch("src.odds.cli.get_db_path", return_value=str(tmp_path / "test.db")), \
             patch("src.odds.cli.sqlite3") as mock_sqlite:

            mock_conn = MagicMock()
            mock_sqlite.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_sqlite.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_predict.return_value = {
                "matches_predicted": 5,
                "predictions_stored": 10,
                "with_ev": 3,
            }

            with patch("sys.argv", ["cli", "predict", "--model-path", model_path]):
                from src.odds.cli import main
                main()

            mock_load.assert_called_once_with(model_path)
            mock_predict.assert_called_once()

    def test_predict_help_exits_cleanly(self):
        """CLI `predict --help` exits with code 0."""
        with patch("sys.argv", ["cli", "predict", "--help"]):
            from src.odds.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
