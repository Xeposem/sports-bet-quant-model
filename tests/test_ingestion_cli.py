"""
Tests for the --source CLI flag in src.ingestion.__main__.

Verifies:
- Default source is 'auto'
- --source tml is accepted
- --source sackmann is accepted
- --source invalid raises SystemExit
- main() passes source kwarg to ingest_all
"""
import pytest
from unittest.mock import MagicMock, patch

from src.ingestion.__main__ import _build_parser, main


def test_source_flag_default_is_auto():
    """Default --source value is 'auto' when not specified."""
    args = _build_parser().parse_args([])
    assert args.source == "auto"


def test_source_flag_accepts_tml():
    """--source tml parses to 'tml'."""
    args = _build_parser().parse_args(["--source", "tml"])
    assert args.source == "tml"


def test_source_flag_accepts_sackmann():
    """--source sackmann parses to 'sackmann'."""
    args = _build_parser().parse_args(["--source", "sackmann"])
    assert args.source == "sackmann"


def test_source_flag_accepts_auto():
    """--source auto parses to 'auto' explicitly."""
    args = _build_parser().parse_args(["--source", "auto"])
    assert args.source == "auto"


def test_source_flag_rejects_invalid():
    """An unrecognised --source value should raise SystemExit (argparse error)."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--source", "invalid"])


def test_main_passes_source_to_ingest_all(tmp_path):
    """
    main() should pass source=args.source to ingest_all.

    We verify by mocking ingest_all and capturing the kwargs passed.
    The --validate-only flag is NOT used here so that the ingest_all call fires.
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
            "--source", "tml",
        ])

    assert mock_ia.called, "ingest_all should have been called"
    _, kwargs = mock_ia.call_args
    assert kwargs.get("source") == "tml", (
        f"Expected source='tml', got '{kwargs.get('source')}'"
    )
