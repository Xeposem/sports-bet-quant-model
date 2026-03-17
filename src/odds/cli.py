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
from datetime import datetime
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
# Subcommand handlers
# ---------------------------------------------------------------------------


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
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
        help="Decimal odds for player A (winner in Sackmann convention). Must be >= 1.01.",
    )
    enter_parser.add_argument(
        "--odds-b", required=True, type=float,
        help="Decimal odds for player B (loser in Sackmann convention). Must be >= 1.01.",
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

    if args.command == "enter":
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
