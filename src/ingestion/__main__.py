"""
CLI entry point for the ATP tennis data ingestion pipeline.

Data is sourced from TennisMyLife (stats.tennismylife.org).

Usage:
    python -m src.ingestion [--db-path DB_PATH] [--raw-dir RAW_DIR]
                            [--start-year YEAR] [--force] [--validate-only]
                            [--verbose]

Examples:
    # Ingest all unprocessed years (1991-present) into the default database
    python -m src.ingestion --db-path data/tennis.db

    # Ingest only recent years
    python -m src.ingestion --db-path data/tennis.db --start-year 2020

    # Run validation only (no download/ingest)
    python -m src.ingestion --db-path data/tennis.db --validate-only

    # Force re-ingest all years (ignores existing log entries)
    python -m src.ingestion --db-path data/tennis.db --force
"""
import argparse
import logging
import os
import sys

from src.db.connection import get_connection, init_db
from src.ingestion.loader import ingest_all
from src.ingestion.validator import validate_database


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingestion",
        description="ATP tennis data ingestion pipeline",
    )
    parser.add_argument(
        "--db-path",
        default="data/tennis.db",
        help="Path to the SQLite database file (default: data/tennis.db)",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw",
        help="Directory for downloaded CSV files (default: data/raw)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1991,
        help="First year to ingest (default: 1991)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest years already present in the ingestion log",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run validation report only — skip download and ingestion",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging output",
    )
    return parser


def _print_ingestion_summary(results: list) -> None:
    """Print per-year ingestion summary to stdout."""
    if not results:
        print("  (no years ingested)")
        return

    print(f"  {'Year':<6} {'Inserted':>8} {'Skipped':>8} {'Excluded':>8} {'Error'}")
    print(f"  {'-'*5} {'-'*8} {'-'*8} {'-'*8} {'-'*20}")
    for r in results:
        year = r.get("year", "?")
        if "error" in r:
            print(f"  {year:<6} {'':>8} {'':>8} {'':>8} {r['error']}")
        else:
            inserted = r.get("inserted", 0)
            skipped = r.get("skipped", 0)
            excluded = r.get("excluded", 0)
            print(f"  {year:<6} {inserted:>8} {skipped:>8} {excluded:>8}")


def _print_validation_summary(report: dict) -> None:
    """Print a human-readable validation summary to stdout."""
    print()
    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)

    # Row counts
    rc = report.get("row_counts", {})
    print("\nRow Counts:")
    print(f"  Matches:      {rc.get('matches', 0):>8,}")
    print(f"  Players:      {rc.get('players', 0):>8,}")
    print(f"  Tournaments:  {rc.get('tournaments', 0):>8,}")
    print(f"  Match stats:  {rc.get('match_stats', 0):>8,}")
    print(f"  Rankings:     {rc.get('rankings', 0):>8,}")

    # Per-year match counts
    by_year = rc.get("by_year", {})
    if by_year:
        print("\n  Matches by year:")
        for year, cnt in sorted(by_year.items()):
            print(f"    {year}: {cnt:,}")

    # Duplicates
    dups = report.get("duplicates", [])
    dup_status = "PASS" if not dups else f"FAIL ({len(dups)} duplicates)"
    print(f"\nDuplicates:         {dup_status}")
    if dups:
        for d in dups[:5]:
            print(f"  {d['tourney_id']} match {d['match_num']} ({d['tour']}) x{d['count']}")

    # Retirement ratio
    rr = report.get("retirement_ratio", {})
    ratio_pct = rr.get("ratio", 0.0) * 100
    in_range = rr.get("in_range", False)
    ratio_status = "PASS" if in_range else "WARN (outside 3-5% range)"
    print(f"\nRetirement ratio:   {ratio_pct:.1f}%  [{ratio_status}]")
    print(f"  Total: {rr.get('total', 0):,}  Retirements: {rr.get('retirements', 0):,}")

    # Date format
    do = report.get("date_ordering", {})
    date_status = "PASS" if do.get("valid_format") else "FAIL"
    print(f"\nDate format:        {date_status}")
    invalid = do.get("invalid_dates", [])
    if invalid:
        print(f"  Invalid dates: {invalid[:5]}")
    chron = do.get("chronological", True)
    print(f"  Chronological:  {'yes' if chron else 'NO (ordering issue)'}")

    # Stats completeness
    sc = report.get("stats_completeness", {})
    overall_missing = sc.get("overall_missing_pct", 0.0) * 100
    print(f"\nStats missing:      {overall_missing:.1f}% overall")
    yr_data = sc.get("by_year", {})
    high_missing = {yr: d for yr, d in yr_data.items() if d["pct_missing"] > 0.5}
    if high_missing:
        print(f"  Years with >50% missing:")
        for yr, d in sorted(high_missing.items()):
            print(f"    {yr}: {d['pct_missing']*100:.0f}% ({d['missing']}/{d['total']})")

    # Temporal safety
    ts = report.get("temporal_safety", {})
    ts_status = "PASS" if ts.get("safe") else "FAIL (feature tables have data)"
    print(f"\nTemporal safety:    {ts_status}")

    # Overall
    overall = report.get("overall_valid", False)
    print()
    print("=" * 60)
    print(f"OVERALL STATUS: {'PASS' if overall else 'FAIL'}")
    print("=" * 60)


def main(argv=None) -> int:
    """
    Main entry point.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("src.ingestion")

    db_path = args.db_path
    raw_dir = args.raw_dir

    # Ensure raw directory exists
    os.makedirs(raw_dir, exist_ok=True)

    # Run ingestion if not validate-only
    if not args.validate_only:
        print(f"Starting ingestion: db={db_path}, raw_dir={raw_dir}, start_year={args.start_year}, force={args.force}")
        logger.info("Initialising database at %s", db_path)
        results = ingest_all(
            db_path=db_path,
            raw_dir=raw_dir,
            start_year=args.start_year,
            force=args.force,
        )
        print()
        print("Ingestion Summary:")
        _print_ingestion_summary(results)
    else:
        logger.info("Validate-only mode — skipping ingestion")
        # Ensure DB exists and schema is applied before validating
        init_db(db_path)

    # Run validation
    logger.info("Running validation checks on %s", db_path)
    conn = get_connection(db_path)
    try:
        report = validate_database(conn)
    finally:
        conn.close()

    _print_validation_summary(report)

    return 0 if report.get("overall_valid", False) else 1


if __name__ == "__main__":
    sys.exit(main())
