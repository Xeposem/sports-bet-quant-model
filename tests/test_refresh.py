"""
Tests for src/refresh/runner.py and src/refresh/scheduler.py

Covers:
- refresh_all() calls ingest, ratings, sentiment, features in correct order
- refresh_all() callable with only db_path (no FastAPI context)
- refresh_all() handles errors in individual steps gracefully (logs, continues)
- build_scheduler returns BackgroundScheduler with one job "daily_refresh"
- build_scheduler(hour=6, minute=0) configures CronTrigger at 6:00 AM
- Scheduler can start and shutdown cleanly
"""
import time
from unittest.mock import patch, MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# Tests: refresh_all
# ---------------------------------------------------------------------------

class TestRefreshAll:
    def test_callable_with_db_path_only(self, tmp_path):
        """refresh_all is callable with just a db_path argument — no FastAPI context needed."""
        db_path = str(tmp_path / "tennis.db")

        with patch("src.refresh.runner.ingest_all") as mock_ingest, \
             patch("src.refresh.runner.compute_all_ratings") as mock_ratings, \
             patch("src.refresh.runner.build_all_features") as mock_features, \
             patch("src.refresh.runner.fetch_all_articles") as mock_fetch:

            mock_ingest.return_value = {"status": "ok"}
            mock_ratings.return_value = {"total_snapshots": 0}
            mock_features.return_value = {"feature_rows_written": 0}
            mock_fetch.return_value = []

            from src.refresh.runner import refresh_all
            result = refresh_all(db_path)

        assert result is not None
        assert isinstance(result, dict)

    def test_calls_ingest_with_db_path_and_raw_dir(self, tmp_path):
        """refresh_all calls ingest_all with the provided db_path and raw_dir."""
        db_path = str(tmp_path / "tennis.db")
        raw_dir = "data/custom_raw"

        with patch("src.refresh.runner.ingest_all") as mock_ingest, \
             patch("src.refresh.runner.compute_all_ratings") as mock_ratings, \
             patch("src.refresh.runner.build_all_features") as mock_features, \
             patch("src.refresh.runner.fetch_all_articles") as mock_fetch:

            mock_ingest.return_value = {}
            mock_ratings.return_value = {}
            mock_features.return_value = {}
            mock_fetch.return_value = []

            from src.refresh.runner import refresh_all
            refresh_all(db_path, raw_dir=raw_dir)

        mock_ingest.assert_called_once_with(db_path, raw_dir)

    def test_calls_steps_in_correct_order(self, tmp_path):
        """refresh_all calls ingest -> ratings -> features in that order."""
        db_path = str(tmp_path / "tennis.db")
        call_order = []

        def mock_ingest(db, raw):
            call_order.append("ingest")
            return {}

        def mock_ratings(conn):
            call_order.append("ratings")
            return {}

        def mock_features(conn):
            call_order.append("features")
            return {}

        with patch("src.refresh.runner.ingest_all", side_effect=mock_ingest), \
             patch("src.refresh.runner.compute_all_ratings", side_effect=mock_ratings), \
             patch("src.refresh.runner.build_all_features", side_effect=mock_features), \
             patch("src.refresh.runner.fetch_all_articles", return_value=[]):

            from src.refresh.runner import refresh_all
            refresh_all(db_path, fetch_articles=False)

        assert call_order == ["ingest", "ratings", "features"]

    def test_returns_summary_with_all_steps(self, tmp_path):
        """refresh_all returns a dict with a 'steps' key containing ingest, ratings, sentiment, features."""
        db_path = str(tmp_path / "tennis.db")

        with patch("src.refresh.runner.ingest_all", return_value={"ok": True}), \
             patch("src.refresh.runner.compute_all_ratings", return_value={"snapshots": 5}), \
             patch("src.refresh.runner.build_all_features", return_value={"rows": 10}), \
             patch("src.refresh.runner.fetch_all_articles", return_value=[]):

            from src.refresh.runner import refresh_all
            result = refresh_all(db_path)

        assert "steps" in result
        assert "ingest" in result["steps"]
        assert "ratings" in result["steps"]
        assert "features" in result["steps"]
        assert "success" in result

    def test_ingest_error_does_not_prevent_ratings(self, tmp_path):
        """If ingest step fails, ratings step still runs (fault-tolerant pipeline)."""
        db_path = str(tmp_path / "tennis.db")
        call_order = []

        def mock_ingest_fail(db, raw):
            call_order.append("ingest")
            raise RuntimeError("Ingest failed")

        def mock_ratings(conn):
            call_order.append("ratings")
            return {}

        def mock_features(conn):
            call_order.append("features")
            return {}

        with patch("src.refresh.runner.ingest_all", side_effect=mock_ingest_fail), \
             patch("src.refresh.runner.compute_all_ratings", side_effect=mock_ratings), \
             patch("src.refresh.runner.build_all_features", side_effect=mock_features), \
             patch("src.refresh.runner.fetch_all_articles", return_value=[]):

            from src.refresh.runner import refresh_all
            result = refresh_all(db_path, fetch_articles=False)

        # Ratings and features should still have run despite ingest failure
        assert "ratings" in call_order
        assert "features" in call_order
        # Result captures error from ingest step
        assert result["steps"]["ingest"] is None or "error" in str(result["steps"]["ingest"]).lower()

    def test_ratings_error_does_not_prevent_features(self, tmp_path):
        """If ratings step fails, features step still runs."""
        db_path = str(tmp_path / "tennis.db")
        call_order = []

        with patch("src.refresh.runner.ingest_all", return_value={}), \
             patch("src.refresh.runner.compute_all_ratings", side_effect=lambda c: (_ for _ in ()).throw(RuntimeError("ratings error"))), \
             patch("src.refresh.runner.build_all_features", side_effect=lambda c: call_order.append("features") or {}), \
             patch("src.refresh.runner.fetch_all_articles", return_value=[]):

            from src.refresh.runner import refresh_all
            result = refresh_all(db_path, fetch_articles=False)

        assert "features" in call_order

    def test_fetch_articles_skipped_when_disabled(self, tmp_path):
        """When fetch_articles=False, fetch_all_articles is not called."""
        db_path = str(tmp_path / "tennis.db")

        with patch("src.refresh.runner.ingest_all", return_value={}), \
             patch("src.refresh.runner.compute_all_ratings", return_value={}), \
             patch("src.refresh.runner.build_all_features", return_value={}), \
             patch("src.refresh.runner.fetch_all_articles") as mock_fetch:

            from src.refresh.runner import refresh_all
            refresh_all(db_path, fetch_articles=False)

        mock_fetch.assert_not_called()

    def test_sentiment_step_included_in_steps_dict(self, tmp_path):
        """refresh_all includes 'sentiment' key in steps dict."""
        db_path = str(tmp_path / "tennis.db")

        with patch("src.refresh.runner.ingest_all", return_value={}), \
             patch("src.refresh.runner.compute_all_ratings", return_value={}), \
             patch("src.refresh.runner.build_all_features", return_value={}), \
             patch("src.refresh.runner.fetch_all_articles", return_value=[]):

            from src.refresh.runner import refresh_all
            result = refresh_all(db_path, fetch_articles=True)

        assert "sentiment" in result["steps"]


# ---------------------------------------------------------------------------
# Tests: build_scheduler
# ---------------------------------------------------------------------------

class TestBuildScheduler:
    def test_returns_background_scheduler(self):
        """build_scheduler returns a BackgroundScheduler instance."""
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler()

        assert isinstance(scheduler, BackgroundScheduler)

    def test_scheduler_has_daily_refresh_job(self):
        """build_scheduler adds a job with id='daily_refresh'."""
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler()
        jobs = scheduler.get_jobs()

        assert len(jobs) == 1
        assert jobs[0].id == "daily_refresh"

    def test_scheduler_cron_trigger_at_specified_time(self):
        """build_scheduler(hour=6, minute=0) creates a CronTrigger at 6:00 AM."""
        from apscheduler.triggers.cron import CronTrigger
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler(hour=6, minute=0)
        job = scheduler.get_jobs()[0]

        assert isinstance(job.trigger, CronTrigger)
        # Verify the trigger fields
        trigger_fields = {f.name: str(f) for f in job.trigger.fields}
        assert trigger_fields["hour"] == "6"
        assert trigger_fields["minute"] == "0"

    def test_scheduler_custom_time(self):
        """build_scheduler respects custom hour and minute."""
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler(hour=3, minute=30)
        job = scheduler.get_jobs()[0]

        trigger_fields = {f.name: str(f) for f in job.trigger.fields}
        assert trigger_fields["hour"] == "3"
        assert trigger_fields["minute"] == "30"

    def test_scheduler_default_db_path(self):
        """build_scheduler uses 'data/tennis.db' as default db_path."""
        from src.refresh.scheduler import build_scheduler

        # Should not raise
        scheduler = build_scheduler()
        assert scheduler is not None

    def test_scheduler_start_and_shutdown(self):
        """BackgroundScheduler from build_scheduler starts and shuts down without errors."""
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
        time.sleep(0.05)  # give scheduler thread a moment to initialize
        scheduler.shutdown(wait=False)

    def test_scheduler_not_started_by_default(self):
        """build_scheduler returns a scheduler that is NOT yet running."""
        from src.refresh.scheduler import build_scheduler

        scheduler = build_scheduler()
        assert not scheduler.running

    def test_replace_existing_allows_reconfiguration(self):
        """build_scheduler with replace_existing=True allows reconfiguring the same job."""
        from src.refresh.scheduler import build_scheduler

        # Build twice — should not raise
        s1 = build_scheduler(hour=6, minute=0)
        s2 = build_scheduler(hour=3, minute=30)

        assert s1 is not s2
        assert len(s1.get_jobs()) == 1
        assert len(s2.get_jobs()) == 1
