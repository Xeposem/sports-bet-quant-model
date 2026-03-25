"""
Command-line interface for odds management and model operations.

Subcommands:
  enter       — Manually enter match odds into the database
  import-csv  — Import odds from a tennis-data.co.uk CSV file
  train       — Train the logistic regression model from match_features
  predict     — Run model predictions and store EV values

Usage:
    python -m src.odds.cli enter --tourney-id 2023-001 --match-num 1 \\
        --odds-a 1.60 --odds-b 2.40

    python -m src.odds.cli import-csv --file data/odds/atp_2023.csv

    python -m src.odds.cli train --output-dir data/models

    python -m src.odds.cli predict --model-path data/models/logistic_v1.joblib
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.model.predictor import predict_all_matches
from src.model.trainer import (
    build_training_matrix,
    compute_time_weights,
    save_model,
    temporal_split,
    train_and_calibrate,
    load_model,
)
from src.odds.ingester import import_csv_odds, manual_entry


logger = logging.getLogger(__name__)

# Default DB path — override via environment variable for tests or deployment
_DEFAULT_DB_PATH = os.path.join("data", "tennis.db")
_MIN_ODDS = 1.01


def get_db_path() -> str:
    """Return the active database path (configurable via TENNIS_DB env var)."""
    return os.environ.get("TENNIS_DB", _DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Odds data download
# ---------------------------------------------------------------------------

_TD_BASE_URL = "http://www.tennis-data.co.uk"
_TD_FIRST_YEAR = 2000


def _td_url(year: int) -> str:
    """Return the tennis-data.co.uk download URL for an ATP season."""
    ext = "xls" if year <= 2012 else "xlsx"
    return f"{_TD_BASE_URL}/{year}/{year}.{ext}"


def download_odds(dest_dir: str, start_year: int = _TD_FIRST_YEAR, end_year: int | None = None) -> list:
    """Download ATP odds Excel files from tennis-data.co.uk.

    Returns list of dicts with year, path, and status.
    """
    import requests

    if end_year is None:
        end_year = datetime.now(timezone.utc).year

    os.makedirs(dest_dir, exist_ok=True)
    results = []

    for year in range(start_year, end_year + 1):
        url = _td_url(year)
        filename = url.rsplit("/", 1)[-1]
        dest_path = os.path.join(dest_dir, filename)

        if os.path.exists(dest_path):
            results.append({"year": year, "path": dest_path, "status": "exists"})
            continue

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            results.append({"year": year, "path": dest_path, "status": "downloaded"})
        except requests.exceptions.HTTPError as exc:
            results.append({"year": year, "path": None, "status": f"failed ({exc.response.status_code})"})
        except Exception as exc:
            results.append({"year": year, "path": None, "status": f"error ({exc})"})

    return results


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_download(args: argparse.Namespace) -> None:
    """Handle the `download` subcommand — fetch odds files from tennis-data.co.uk."""
    dest_dir = args.dest_dir
    results = download_odds(dest_dir, start_year=args.start_year, end_year=args.end_year)

    downloaded = sum(1 for r in results if r["status"] == "downloaded")
    existed = sum(1 for r in results if r["status"] == "exists")
    failed = sum(1 for r in results if r["status"] not in ("downloaded", "exists"))

    for r in results:
        symbol = "+" if r["status"] == "downloaded" else ("=" if r["status"] == "exists" else "!")
        print(f"  {symbol} {r['year']}: {r['status']}")

    print(f"\nDownload complete: {downloaded} new, {existed} already existed, {failed} failed")

    # Auto-import if requested
    if args.auto_import:
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Check which years already have odds data
            imported_years = set()
            for row in conn.execute(
                """SELECT DISTINCT CAST(SUBSTR(m.tourney_date, 1, 4) AS INTEGER) AS yr
                   FROM match_odds o
                   JOIN matches m ON o.tourney_id = m.tourney_id
                     AND o.match_num = m.match_num AND o.tour = m.tour
                   WHERE o.source = 'csv'"""
            ).fetchall():
                imported_years.add(row[0])

            total_imported = 0
            total_unlinked = 0
            skipped = 0
            for r in results:
                if r["path"] is None:
                    continue
                if r["year"] in imported_years and not args.force:
                    skipped += 1
                    print(f"  = {r['year']}: already imported, skipping")
                    continue
                stats = import_csv_odds(conn, r["path"])
                total_imported += stats["imported"]
                total_unlinked += stats["unlinked"]
                print(f"  {r['year']}: imported={stats['imported']}, unlinked={stats['unlinked']}")
        print(f"\nImport complete: {total_imported} imported, {total_unlinked} unlinked, {skipped} skipped")


def _cmd_enter(args: argparse.Namespace) -> None:
    """Handle the `enter` subcommand — insert manual odds."""
    # Validate odds
    if args.odds_a < _MIN_ODDS:
        print(
            f"Error: --odds-a must be >= {_MIN_ODDS}, got {args.odds_a}",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.odds_b < _MIN_ODDS:
        print(
            f"Error: --odds-b must be >= {_MIN_ODDS}, got {args.odds_b}",
            file=sys.stderr,
        )
        sys.exit(1)

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        manual_entry(
            conn,
            tourney_id=args.tourney_id,
            match_num=args.match_num,
            decimal_odds_a=args.odds_a,
            decimal_odds_b=args.odds_b,
            bookmaker=args.bookmaker,
        )
        conn.commit()

    print(
        f"Odds entered: {args.tourney_id}/match {args.match_num} — "
        f"A={args.odds_a}, B={args.odds_b} ({args.bookmaker})"
    )


def _cmd_import_csv(args: argparse.Namespace) -> None:
    """Handle the `import-csv` subcommand — bulk import from CSV."""
    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        stats = import_csv_odds(conn, args.file)

    print(
        f"CSV import complete: "
        f"imported={stats['imported']}, "
        f"unlinked={stats['unlinked']}, "
        f"skipped_no_odds={stats['skipped_no_odds']}"
    )


def _cmd_train(args: argparse.Namespace) -> None:
    """Handle the `train` subcommand — train and calibrate the model."""
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        X, y, match_dates = build_training_matrix(conn)

    if len(y) == 0:
        print("Error: no match features found in database — run feature engineering first.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(y)} training samples from database.")

    weights = compute_time_weights(match_dates, half_life_days=args.half_life)
    split = temporal_split(X, y, weights, match_dates, train_ratio=0.8)

    print(
        f"Split: {len(split['y_train'])} train / {len(split['y_val'])} val "
        f"({split['dates_train'][0]} to {split['dates_val'][-1]})"
    )

    model, metrics = train_and_calibrate(
        split["X_train"], split["y_train"],
        split["X_val"], split["y_val"],
        split["w_train"],
    )

    # Save model
    if args.save_path:
        model_path = args.save_path
        os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_path = os.path.join(output_dir, f"logistic_v1_{timestamp}.joblib")
    save_model(model, model_path)

    # Save metrics JSON alongside model
    metrics_path = model_path.replace(".joblib", "_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Model saved: {model_path}")
    print(
        f"Metrics — Brier: {metrics['val_brier_score']:.4f}, "
        f"LogLoss: {metrics['val_log_loss']:.4f}, "
        f"Calibration: {metrics['calibration_method']}"
    )


def _cmd_predict(args: argparse.Namespace) -> None:
    """Handle the `predict` subcommand — generate predictions with EV."""
    if not os.path.exists(args.model_path):
        print(f"Error: model file not found: {args.model_path}", file=sys.stderr)
        sys.exit(1)

    model = load_model(args.model_path)

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        stats = predict_all_matches(model, conn, model_version=args.model_version)

    print(
        f"Predictions complete: "
        f"matches_predicted={stats['matches_predicted']}, "
        f"predictions_stored={stats['predictions_stored']}, "
        f"with_ev={stats['with_ev']}"
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Tennis ATP betting model CLI — odds management and prediction.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # --- download ---
    dl_parser = subparsers.add_parser(
        "download",
        help="Download ATP odds files from tennis-data.co.uk.",
    )
    dl_parser.add_argument(
        "--dest-dir", default=os.path.join("data", "odds"),
        help="Directory to save downloaded files (default: data/odds).",
    )
    dl_parser.add_argument(
        "--start-year", type=int, default=_TD_FIRST_YEAR,
        help=f"First year to download (default: {_TD_FIRST_YEAR}).",
    )
    dl_parser.add_argument(
        "--end-year", type=int, default=None,
        help="Last year to download (default: current year).",
    )
    dl_parser.add_argument(
        "--auto-import", action="store_true",
        help="Automatically import downloaded files into the database.",
    )
    dl_parser.add_argument(
        "--force", action="store_true",
        help="Re-import years that already have odds data.",
    )

    # --- enter ---
    enter_parser = subparsers.add_parser(
        "enter",
        help="Manually enter match odds into the database.",
    )
    enter_parser.add_argument(
        "--tourney-id", required=True,
        help="Tournament ID (must exist in matches table).",
    )
    enter_parser.add_argument(
        "--match-num", required=True, type=int,
        help="Match number.",
    )
    enter_parser.add_argument(
        "--odds-a", required=True, type=float,
        help="Decimal odds for player A (winner). Must be >= 1.01.",
    )
    enter_parser.add_argument(
        "--odds-b", required=True, type=float,
        help="Decimal odds for player B (loser). Must be >= 1.01.",
    )
    enter_parser.add_argument(
        "--bookmaker", default="pinnacle",
        help="Bookmaker name (default: pinnacle).",
    )

    # --- import-csv ---
    import_parser = subparsers.add_parser(
        "import-csv",
        help="Import odds from a tennis-data.co.uk CSV file.",
    )
    import_parser.add_argument(
        "--file", required=True,
        help="Path to tennis-data.co.uk format CSV file.",
    )

    # --- train ---
    train_parser = subparsers.add_parser(
        "train",
        help="Train and calibrate the logistic regression model.",
    )
    train_parser.add_argument(
        "--output-dir", default="data/models",
        help="Directory for model artifact output (default: data/models).",
    )
    train_parser.add_argument(
        "--save-path",
        help="Exact file path for the saved model (overrides --output-dir).",
    )
    train_parser.add_argument(
        "--half-life", type=int, default=730,
        help="Time-decay half-life in days for sample weights (default: 730).",
    )

    # --- predict ---
    predict_parser = subparsers.add_parser(
        "predict",
        help="Run model predictions and store EV values for all matches.",
    )
    predict_parser.add_argument(
        "--model-path", required=True,
        help="Path to trained model .joblib file.",
    )
    predict_parser.add_argument(
        "--model-version", default="logistic_v1",
        help="Model version string for predictions table PK (default: logistic_v1).",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "download":
        _cmd_download(args)
    elif args.command == "enter":
        _cmd_enter(args)
    elif args.command == "import-csv":
        _cmd_import_csv(args)
    elif args.command == "train":
        _cmd_train(args)
    elif args.command == "predict":
        _cmd_predict(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
