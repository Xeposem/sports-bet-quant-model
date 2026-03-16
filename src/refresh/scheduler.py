"""
APScheduler-based daily refresh scheduler.

Creates a BackgroundScheduler that fires refresh_all once per day at a
configurable time. Designed to be imported and started inside a FastAPI
lifespan (Phase 5) or run standalone for testing.

The scheduler is NOT started by build_scheduler() — the caller starts it:

    scheduler = build_scheduler(db_path="data/tennis.db", hour=6, minute=0)
    scheduler.start()

    # On shutdown:
    scheduler.shutdown()

Exports:
  - build_scheduler(db_path, hour, minute) -> BackgroundScheduler
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.refresh.runner import refresh_all

logger = logging.getLogger(__name__)


def build_scheduler(
    db_path: str = "data/tennis.db",
    hour: int = 6,
    minute: int = 0,
) -> BackgroundScheduler:
    """
    Build and configure a BackgroundScheduler with a daily CronTrigger.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file passed to refresh_all.
        Defaults to "data/tennis.db".
    hour : int
        Hour of the day to run the refresh (24-hour format). Default 6 (6 AM).
    minute : int
        Minute of the hour. Default 0.

    Returns
    -------
    BackgroundScheduler
        Configured but NOT yet started. Call scheduler.start() to begin.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_all,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_refresh",
        args=[db_path],
        replace_existing=True,
    )
    logger.info(
        "Scheduler configured: daily_refresh at %02d:%02d, db_path=%s",
        hour, minute, db_path,
    )
    return scheduler
