"""CLI for prop models: python -m src.props train|predict --db-path tennis.db"""

import argparse

from src.db.connection import get_connection, init_db
from src.props import PROP_REGISTRY
from src.props.base import predict_and_store


def main():
    parser = argparse.ArgumentParser(description="Prop model CLI")
    sub = parser.add_subparsers(dest="command")

    # Train subcommand
    train_cmd = sub.add_parser("train", help="Train prop models")
    train_cmd.add_argument(
        "--stat-type",
        choices=["aces", "double_faults", "games_won", "all"],
        default="all",
    )
    train_cmd.add_argument("--db-path", default="tennis.db")

    # Predict subcommand
    predict_cmd = sub.add_parser(
        "predict",
        help="Batch-predict and populate prop_predictions table",
    )
    predict_cmd.add_argument(
        "--stat-type",
        choices=["aces", "double_faults", "games_won", "all"],
        default="all",
    )
    predict_cmd.add_argument("--db-path", default="tennis.db")
    predict_cmd.add_argument(
        "--date-from",
        default=None,
        help="Start date (YYYY-MM-DD). Defaults to 30 days ago.",
    )
    predict_cmd.add_argument(
        "--date-to",
        default=None,
        help="End date (YYYY-MM-DD). Defaults to today.",
    )

    args = parser.parse_args()

    if args.command == "train":
        init_db(args.db_path)
        conn = get_connection(args.db_path)
        try:
            types = list(PROP_REGISTRY.keys()) if args.stat_type == "all" else [args.stat_type]
            for st in types:
                print(f"Training {st}...")
                result = PROP_REGISTRY[st]["train"](conn)
                print(f"  family={result['family']}, aic={result['aic']:.1f}")
        finally:
            conn.close()

    elif args.command == "predict":
        from datetime import date, timedelta

        init_db(args.db_path)
        conn = get_connection(args.db_path)
        try:
            date_from = args.date_from or (date.today() - timedelta(days=30)).isoformat()
            date_to = args.date_to or date.today().isoformat()
            stat_types = None if args.stat_type == "all" else [args.stat_type]
            print(f"Predicting props for {date_from} to {date_to}...")
            result = predict_and_store(
                conn,
                stat_types=stat_types,
                date_from=date_from,
                date_to=date_to,
            )
            print(f"  predicted={result['predicted']} rows for {result['stat_types']}")
        finally:
            conn.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
