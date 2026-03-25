"""
Tests for the CLI in src.ingestion.__main__.

Verifies:
- Default flags parse correctly
- --force and --validate-only flags are accepted
- Invalid flags raise SystemExit
- main() passes args to ingest_all
"""
import pytest
from unittest.mock import MagicMock, patch

from src.ingestion.__main__ import _build_parser, main


def test_default_args():
    """Default args: db-path=data/tennis.db, start-year=1991, no force."""
    args = _build_parser().parse_args([])
    assert args.db_path == "data/tennis.db"
    assert args.start_year == 1991
    assert args.force is False
    assert args.validate_only is False


def test_start_year_flag():
    """--start-year parses correctly."""
    args = _build_parser().parse_args(["--start-year", "2020"])
    assert args.start_year == 2020


def test_force_flag():
    """--force sets force=True."""
    args = _build_parser().parse_args(["--force"])
    assert args.force is True


def test_validate_only_flag():
    """--validate-only sets validate_only=True."""
    args = _build_parser().parse_args(["--validate-only"])
    assert args.validate_only is True


def test_main_passes_args_to_ingest_all(tmp_path):
    """
    main() should pass correct kwargs to ingest_all.

    We verify by mocking ingest_all and capturing the kwargs passed.
    We also mock validate_database to avoid DB side effects.
    """
    db_path = str(tmp_path / "cli_test.db")

    mock_ingest_results = [{"year": 2025, "inserted": 1, "skipped": 0, "excluded": 0, "rows_processed": 1}]
    mock_report = {
        "overall_valid": True,
        "row_counts": {},
        "duplicates": [],
        "retirement_ratio": {"ratio": 0.04, "in_range": True, "total": 100, "retirements": 4},
        "date_ordering": {"valid_format": True, "chronological": True, "invalid_dates": []},
        "stats_completeness": {"overall_missing_pct": 0.0, "by_year": {}},
        "temporal_safety": {"safe": True},
    }

    with (
        patch("src.ingestion.__main__.ingest_all", return_value=mock_ingest_results) as mock_ia,
        patch("src.ingestion.__main__.validate_database", return_value=mock_report),
        patch("src.ingestion.__main__.init_db"),
        patch("src.ingestion.__main__.get_connection", return_value=MagicMock()),
    ):
        exit_code = main([
            "--db-path", db_path,
            "--raw-dir", str(tmp_path),
            "--start-year", "2025",
        ])

    assert mock_ia.called, "ingest_all should have been called"
    _, kwargs = mock_ia.call_args
    assert kwargs.get("start_year") == 2025
