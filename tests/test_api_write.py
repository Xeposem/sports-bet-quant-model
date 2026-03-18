"""
Integration tests for write and action endpoints (Phase 5 Plan 03).

Tests:
    test_odds_entry_valid              — POST /api/v1/odds with linked result
    test_odds_entry_unlinked           — POST /api/v1/odds with unlinked result
    test_odds_upload_csv               — POST /api/v1/odds/upload with CSV file
    test_props_entry_valid             — POST /api/v1/props with valid prop line
    test_props_entry_valid_all_stats   — All valid stat_types return 200
    test_props_entry_invalid_stat      — POST /api/v1/props with invalid stat_type -> 422
    test_props_entry_invalid_direction — POST /api/v1/props with invalid direction -> 422
    test_refresh_trigger_returns_job   — POST /api/v1/refresh returns job_id
    test_refresh_trigger_and_poll      — POST /api/v1/refresh + GET /refresh/status
    test_refresh_status_not_found      — GET /refresh/status?job_id=unknown -> 404
    test_backtest_run_trigger          — POST /api/v1/backtest/run returns job_id
    test_backtest_run_default_params   — POST /api/v1/backtest/run with empty body
    test_backtest_run_status_not_found — GET /api/v1/backtest/run/status?job_id=unknown -> 404
    test_backtest_run_status_found     — GET /api/v1/backtest/run/status with valid job_id

All pipeline functions (refresh_all, run_walk_forward) are mocked to avoid heavy computation.
Schema is applied via init_db in the async_app fixture (conftest.py), using a temp file DB
so sync sqlite3 write calls share the same database as the async engine.
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Odds entry tests
# ---------------------------------------------------------------------------

class TestOddsEntry:
    """POST /api/v1/odds — manual odds entry with fuzzy matching."""

    async def test_odds_entry_valid(self, async_app, async_client):
        """POST /odds with mocked link_odds_to_matches returning linked row -> linked=True."""
        linked_row = {
            "match_date": "2024-01-15",
            "winner_name": "Novak Djokovic",
            "loser_name": "Andrey Rublev",
            "decimal_odds_winner": 1.35,
            "decimal_odds_loser": 3.10,
            "tourney_id": "2024-0021",
            "match_num": 1,
            "tour": "ATP",
        }

        with patch("src.api.routers.odds.link_odds_to_matches", return_value=[linked_row]), \
             patch("src.api.routers.odds.upsert_match_odds", return_value=True):
            response = await async_client.post(
                "/api/v1/odds",
                json={
                    "player_a": "Novak Djokovic",
                    "player_b": "Andrey Rublev",
                    "odds_a": 1.35,
                    "odds_b": 3.10,
                    "match_date": "2024-01-15",
                    "bookmaker": "pinnacle",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is True
        assert data["tourney_id"] == "2024-0021"
        assert data["match_num"] == 1
        assert "message" in data

    async def test_odds_entry_unlinked(self, async_app, async_client):
        """POST /odds with unlinked row -> linked=False with candidates list."""
        unlinked_row = {
            "match_date": "2024-01-15",
            "winner_name": "Unknown Player",
            "loser_name": "Another Unknown",
            "decimal_odds_winner": 1.50,
            "decimal_odds_loser": 2.50,
            "tourney_id": None,
            "match_num": None,
            "tour": None,
        }

        with patch("src.api.routers.odds.link_odds_to_matches", return_value=[unlinked_row]):
            response = await async_client.post(
                "/api/v1/odds",
                json={
                    "player_a": "Unknown Player",
                    "player_b": "Another Unknown",
                    "odds_a": 1.50,
                    "odds_b": 2.50,
                    "match_date": "2024-01-15",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is False
        assert "candidates" in data
        assert "message" in data


class TestOddsUpload:
    """POST /api/v1/odds/upload — CSV file upload."""

    async def test_odds_upload_csv(self, async_app, async_client):
        """POST /odds/upload with small CSV -> returns imported/skipped/total counts."""
        mock_result = {"imported": 3, "unlinked": 1, "skipped_no_odds": 0}

        csv_content = (
            "Date,Winner,Loser,PSW,PSL\n"
            "15/01/2024,Djokovic,Rublev,1.35,3.10\n"
            "15/01/2024,Alcaraz,Struff,1.20,5.00\n"
            "16/01/2024,Medvedev,Unknown,1.50,2.50\n"
            "16/01/2024,NoMatch,Player,2.00,1.80\n"
        )

        with patch("src.api.routers.odds.import_csv_odds", return_value=mock_result):
            response = await async_client.post(
                "/api/v1/odds/upload",
                files={"file": ("test_odds.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 3
        assert "skipped" in data
        assert "total" in data
        assert data["total"] == data["imported"] + data["skipped"]


# ---------------------------------------------------------------------------
# Props entry tests
# ---------------------------------------------------------------------------

class TestPropsEntry:
    """POST /api/v1/props — manual prop line entry."""

    async def test_props_entry_valid(self, async_app, async_client):
        """POST /props with valid body -> 200 with id, player_name, stat_type."""
        response = await async_client.post(
            "/api/v1/props",
            json={
                "player_name": "Novak Djokovic",
                "stat_type": "aces",
                "line_value": 5.5,
                "direction": "over",
                "match_date": "2024-01-15",
                "bookmaker": "prizepicks",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["player_name"] == "Novak Djokovic"
        assert data["stat_type"] == "aces"
        assert data["line_value"] == 5.5
        assert data["direction"] == "over"
        assert data["match_date"] == "2024-01-15"

    async def test_props_entry_valid_all_stat_types(self, async_app, async_client):
        """All valid stat_types should return 200."""
        for stat_type in ["aces", "games_won", "double_faults"]:
            response = await async_client.post(
                "/api/v1/props",
                json={
                    "player_name": "Test Player",
                    "stat_type": stat_type,
                    "line_value": 3.5,
                    "direction": "under",
                    "match_date": "2024-01-20",
                },
            )
            assert response.status_code == 200, f"Failed for stat_type={stat_type}"

    async def test_props_entry_invalid_stat(self, async_app, async_client):
        """POST /props with invalid stat_type -> 422."""
        response = await async_client.post(
            "/api/v1/props",
            json={
                "player_name": "Novak Djokovic",
                "stat_type": "invalid_stat",
                "line_value": 5.5,
                "direction": "over",
                "match_date": "2024-01-15",
            },
        )
        assert response.status_code == 422

    async def test_props_entry_invalid_direction(self, async_app, async_client):
        """POST /props with invalid direction -> 422."""
        response = await async_client.post(
            "/api/v1/props",
            json={
                "player_name": "Novak Djokovic",
                "stat_type": "aces",
                "line_value": 5.5,
                "direction": "sideways",
                "match_date": "2024-01-15",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Refresh trigger and poll tests
# ---------------------------------------------------------------------------

class TestRefreshJob:
    """POST /api/v1/refresh and GET /api/v1/refresh/status."""

    async def test_refresh_trigger_returns_job_id(self, async_app, async_client):
        """POST /refresh -> returns job_id and status=running."""
        with patch("src.api.routers.refresh.refresh_all", return_value={"success": True, "steps": {}}):
            response = await async_client.post("/api/v1/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "running"

    async def test_refresh_trigger_and_poll(self, async_app, async_client):
        """POST /refresh returns job_id; GET /refresh/status?job_id=... returns status."""
        with patch("src.api.routers.refresh.refresh_all", return_value={"success": True, "steps": {}}):
            trigger_response = await async_client.post("/api/v1/refresh")

        assert trigger_response.status_code == 200
        job_id = trigger_response.json()["job_id"]

        # Poll status using the job_id
        status_response = await async_client.get(f"/api/v1/refresh/status?job_id={job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        assert "status" in status_data

    async def test_refresh_status_not_found(self, async_app, async_client):
        """GET /refresh/status?job_id=nonexistent -> 404."""
        response = await async_client.get("/api/v1/refresh/status?job_id=nonexistent-job-id")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Backtest run trigger tests
# ---------------------------------------------------------------------------

class TestBacktestRunJob:
    """POST /api/v1/backtest/run and GET /api/v1/backtest/run/status."""

    async def test_backtest_run_trigger(self, async_app, async_client):
        """POST /backtest/run -> returns job_id with status=running."""
        with patch("src.api.routers.backtest.run_walk_forward", return_value={"folds": []}):
            response = await async_client.post(
                "/api/v1/backtest/run",
                json={
                    "kelly_fraction": 0.25,
                    "max_bet_pct": 0.03,
                    "ev_threshold": 0.0,
                    "initial_bankroll": 1000.0,
                    "model_version": "logistic_v1",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "running"

    async def test_backtest_run_default_params(self, async_app, async_client):
        """POST /backtest/run with empty body uses defaults."""
        with patch("src.api.routers.backtest.run_walk_forward", return_value={"folds": []}):
            response = await async_client.post("/api/v1/backtest/run", json={})

        assert response.status_code == 200
        assert "job_id" in response.json()

    async def test_backtest_run_status_not_found(self, async_app, async_client):
        """GET /backtest/run/status?job_id=nonexistent -> 404."""
        response = await async_client.get("/api/v1/backtest/run/status?job_id=nonexistent-job-id")
        assert response.status_code == 404

    async def test_backtest_run_status_found(self, async_app, async_client):
        """GET /backtest/run/status with valid job_id -> returns BacktestRunStatus."""
        with patch("src.api.routers.backtest.run_walk_forward", return_value={"folds": []}):
            trigger_response = await async_client.post("/api/v1/backtest/run", json={})

        job_id = trigger_response.json()["job_id"]
        status_response = await async_client.get(
            f"/api/v1/backtest/run/status?job_id={job_id}"
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        assert "status" in status_data
