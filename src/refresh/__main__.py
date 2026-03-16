"""
CLI entry point for the refresh pipeline.

Usage:
  python -m src.refresh --db-path tennis.db
  python -m src.refresh --db-path tennis.db --raw-dir data/raw
  python -m src.refresh --schedule --db-path tennis.db --hour 6 --minute 0
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh tennis quantitative model pipeline"
    )
    parser.add_argument(
        "--db-path",
        default="data/tennis.db",
        help="Path to SQLite database file (default: data/tennis.db)",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw",
        help="Directory with raw match CSV files (default: data/raw)",
    )
    parser.add_argument(
        "--no-sentiment",
        action="store_true",
        help="Skip article fetching and sentiment scoring",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as scheduler (fires once per day at --hour:--minute)",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=6,
        help="Hour for scheduled run (24h format, default: 6)",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=0,
        help="Minute for scheduled run (default: 0)",
    )
    args = parser.parse_args()

    if args.schedule:
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler(
            db_path=args.db_path,
            hour=args.hour,
            minute=args.minute,
        )
        scheduler.start()
        logger.info(
            "Scheduler started — daily refresh at %02d:%02d. Press Ctrl+C to exit.",
            args.hour,
            args.minute,
        )

        def _shutdown(sig, frame):
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=False)
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        while True:
            time.sleep(60)
    else:
        from src.refresh.runner import refresh_all

        logger.info("Running one-shot refresh for db_path=%s", args.db_path)
        result = refresh_all(
            db_path=args.db_path,
            raw_dir=args.raw_dir,
            fetch_articles=not args.no_sentiment,
        )
        if result["success"]:
            logger.info("Refresh completed successfully: %s", result["steps"])
        else:
            logger.warning("Refresh completed with errors: %s", result["steps"])
            sys.exit(1)


if __name__ == "__main__":
    main()
