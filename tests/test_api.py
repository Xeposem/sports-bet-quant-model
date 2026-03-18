"""
Tests for the Tennis Betting API (Phase 5).

Phase 5 Plan 01 smoke tests:
    test_openapi_schema   — /docs returns 200 with valid HTML (OpenAPI UI)
    test_health_endpoint  — /api/v1/health returns 200 with status=ok
    test_error_format     — 404 on nonexistent route returns structured JSON

Phase 5 Plan 02 integration tests:
    test_predict_endpoint          — GET /api/v1/predict returns 200 with data key
    test_predict_filter_min_ev     — min_ev filter excludes low-EV rows
    test_backtest_summary          — GET /api/v1/backtest returns aggregate stats
    test_backtest_bets_pagination  — GET /api/v1/backtest/bets pagination works
    test_bankroll_endpoint         — GET /api/v1/bankroll returns curve + stats
    test_models_endpoint           — GET /api/v1/models returns model list
    test_calibration_endpoint      — GET /api/v1/calibration returns bins
    test_props_stub                — GET /api/v1/props returns not_available
    test_pagination_schema         — /backtest/bets response has total/offset/limit/data
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Phase 5 Plan 01 — smoke tests
# ---------------------------------------------------------------------------

class TestOpenAPISchema:
    """GET /docs should serve the OpenAPI interactive documentation."""

    async def test_openapi_schema(self, async_client):
        response = await async_client.get("/docs")
        assert response.status_code == 200
        # FastAPI /docs returns HTML with the swagger UI
        assert "text/html" in response.headers.get("content-type", "")


class TestHealthEndpoint:
    """GET /api/v1/health should return {status: ok, model_loaded: false}."""

    async def test_health_returns_200(self, async_client):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_status_ok(self, async_client):
        response = await async_client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "ok"

    async def test_health_model_loaded_false(self, async_client):
        """Model is None in tests (no joblib file on disk)."""
        response = await async_client.get("/api/v1/health")
        data = response.json()
        assert data["model_loaded"] is False


class TestErrorFormat:
    """404 responses should use structured JSON, not HTML error pages."""

    async def test_nonexistent_route_returns_structured_json(self, async_client):
        response = await async_client.get("/api/v1/nonexistent-route")
        assert response.status_code == 404
        # Must be JSON — not an HTML page
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    async def test_error_response_has_required_keys(self, async_client):
        response = await async_client.get("/api/v1/nonexistent-route")
        data = response.json()
        assert "error" in data
        assert "message" in data


# ---------------------------------------------------------------------------
# Seed helper — creates tables and inserts test data into the async in-memory DB
# ---------------------------------------------------------------------------

async def _seed_test_data(app):
    """Seed in-memory async DB with schema and realistic test rows.

    SQLite's PRAGMA foreign_keys defaults to OFF, so we can INSERT into leaf
    tables (predictions, backtest_results) without the parent match rows.
    The schema DDL is executed statement-by-statement; errors are silently
    ignored (duplicate CREATE IF NOT EXISTS, PRAGMA lines, etc.).
    """
    from sqlalchemy import text
    from src.db.connection import _read_schema_sql

    schema_sql = _read_schema_sql()

    engine = app.state.engine

    # Create tables — foreign_keys defaults to OFF in aiosqlite in-memory DB
    async with engine.begin() as conn:
        for stmt in schema_sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await conn.execute(text(stmt))
                except Exception:
                    pass  # PRAGMA / index stmts that error are fine

    midpoints = json.dumps([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    emp_freqs = json.dumps([0.09, 0.19, 0.31, 0.39, 0.51, 0.61, 0.69, 0.81, 0.90])

    async with engine.begin() as conn:
        # Disable FK enforcement for this connection before inserting leaf tables
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        await conn.execute(
            text(
                """
                INSERT OR IGNORE INTO predictions
                    (tourney_id, match_num, tour, player_id, model_version,
                     calibrated_prob, ev_value, edge, decimal_odds,
                     brier_contribution, log_loss_contribution, predicted_at)
                VALUES
                    ('2023-0001', 1, 'ATP', 101, 'logistic_v1', 0.65, 0.12, 0.08, 1.75, 0.18, 0.50, '2023-06-01T10:00:00Z'),
                    ('2023-0001', 2, 'ATP', 102, 'logistic_v1', 0.58, 0.06, 0.04, 1.65, 0.22, 0.55, '2023-06-01T10:00:00Z'),
                    ('2023-0001', 3, 'ATP', 103, 'logistic_v1', 0.52, 0.02, 0.01, 1.55, 0.25, 0.60, '2023-06-02T10:00:00Z'),
                    ('2023-0002', 1, 'ATP', 104, 'logistic_v1', 0.70, 0.20, 0.15, 1.80, 0.15, 0.45, '2023-06-03T10:00:00Z'),
                    ('2023-0002', 2, 'ATP', 105, 'logistic_v1', 0.55, 0.03, 0.02, 1.58, 0.23, 0.58, '2023-06-04T10:00:00Z')
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT OR IGNORE INTO backtest_results
                    (fold_year, tourney_id, match_num, tour, model_version,
                     player_id, outcome, calibrated_prob, decimal_odds, ev,
                     kelly_full, kelly_bet, flat_bet, pnl_kelly, pnl_flat,
                     bankroll_before, bankroll_after, surface, tourney_level,
                     winner_rank, loser_rank, tourney_date)
                VALUES
                    (2022, '2022-0001', 1, 'ATP', 'logistic_v1', 101, 1, 0.65, 1.75, 0.14, 0.08, 0.08, 1.0,  0.06, 0.75, 1000.0, 1006.0, 'Hard', 'G', 5,  20,  '2022-01-15'),
                    (2022, '2022-0001', 2, 'ATP', 'logistic_v1', 102, 0, 0.58, 1.65, 0.06, 0.04, 0.04, 1.0, -0.04, -1.00, 1006.0, 1001.76, 'Clay', 'M', 15, 40, '2022-02-10'),
                    (2022, '2022-0002', 1, 'ATP', 'logistic_v1', 103, 1, 0.70, 1.80, 0.26, 0.14, 0.14, 1.0,  0.11, 0.80, 1001.76, 1013.28, 'Grass', 'G', 3,  12, '2022-06-20'),
                    (2023, '2023-0001', 1, 'ATP', 'logistic_v1', 104, 1, 0.62, 1.70, 0.08, 0.05, 0.05, 1.0,  0.04, 0.70, 1013.28, 1017.60, 'Hard', 'A', 8,  25, '2023-01-20'),
                    (2023, '2023-0002', 1, 'ATP', 'logistic_v1', 105, 0, 0.55, 1.58, 0.02, 0.02, 0.02, 1.0, -0.02, -1.00, 1017.60, 1017.18, 'Clay', 'M', 30, 60, '2023-04-05')
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT OR IGNORE INTO calibration_data
                    (fold_label, model_version, bin_midpoints, empirical_freq, n_samples, computed_at)
                VALUES
                    ('overall', 'logistic_v1', :midpoints, :emp_freqs, 450, '2023-06-01T00:00:00Z'),
                    ('2022',    'logistic_v1', :midpoints, :emp_freqs, 200, '2022-12-31T00:00:00Z')
                """
            ),
            {"midpoints": midpoints, "emp_freqs": emp_freqs},
        )


# ---------------------------------------------------------------------------
# Fixture: seeded async_client
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_client(async_app):
    """async_client with test data seeded into the in-memory DB."""
    await _seed_test_data(async_app)

    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=async_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Phase 5 Plan 02 — GET endpoint integration tests
# ---------------------------------------------------------------------------

class TestPredictEndpoint:
    """GET /api/v1/predict — prediction rows with positive EV."""

    async def test_predict_endpoint(self, seeded_client):
        response = await seeded_client.get("/api/v1/predict")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        # All seeded predictions have ev_value > 0
        assert len(data["data"]) > 0

    async def test_predict_response_fields(self, seeded_client):
        response = await seeded_client.get("/api/v1/predict")
        rows = response.json()["data"]
        for row in rows:
            assert "tourney_id" in row
            assert "match_num" in row
            assert "tour" in row
            assert "player_id" in row
            assert "model_version" in row
            assert "predicted_at" in row

    async def test_predict_filter_min_ev(self, seeded_client):
        """min_ev=0.10 should only return rows with ev_value >= 0.10."""
        response = await seeded_client.get("/api/v1/predict?min_ev=0.10")
        assert response.status_code == 200
        rows = response.json()["data"]
        for row in rows:
            assert row["ev_value"] >= 0.10

    async def test_predict_high_min_ev_returns_fewer_rows(self, seeded_client):
        """Higher min_ev threshold returns fewer rows."""
        all_resp = await seeded_client.get("/api/v1/predict")
        filtered_resp = await seeded_client.get("/api/v1/predict?min_ev=0.15")
        assert len(filtered_resp.json()["data"]) <= len(all_resp.json()["data"])

    async def test_predict_empty_when_no_data(self, async_client):
        """Without seeding, returns empty list (not 404)."""
        response = await async_client.get("/api/v1/predict")
        assert response.status_code == 200
        assert response.json()["data"] == []


class TestBacktestSummary:
    """GET /api/v1/backtest — aggregate stats and ROI breakdowns."""

    async def test_backtest_summary(self, seeded_client):
        response = await seeded_client.get("/api/v1/backtest")
        assert response.status_code == 200
        data = response.json()
        assert "n_bets" in data
        assert "kelly_roi" in data
        assert "flat_roi" in data
        assert "total_pnl_kelly" in data
        assert "total_pnl_flat" in data

    async def test_backtest_has_breakdowns(self, seeded_client):
        data = (await seeded_client.get("/api/v1/backtest")).json()
        assert "by_surface" in data
        assert "by_tourney_level" in data
        assert "by_year" in data
        assert "by_ev_bucket" in data
        assert "by_rank_tier" in data

    async def test_backtest_n_bets_positive(self, seeded_client):
        data = (await seeded_client.get("/api/v1/backtest")).json()
        assert data["n_bets"] == 5

    async def test_backtest_by_surface_has_labels(self, seeded_client):
        data = (await seeded_client.get("/api/v1/backtest")).json()
        for bucket in data["by_surface"]:
            assert "label" in bucket
            assert "n_bets" in bucket
            assert "kelly_roi" in bucket


class TestBacktestBets:
    """GET /api/v1/backtest/bets — paginated individual bet rows."""

    async def test_backtest_bets_pagination(self, seeded_client):
        response = await seeded_client.get("/api/v1/backtest/bets?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["data"]) == 2

    async def test_pagination_schema(self, seeded_client):
        """Response must have total, offset, limit, data keys."""
        data = (await seeded_client.get("/api/v1/backtest/bets")).json()
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert "data" in data

    async def test_backtest_bets_offset(self, seeded_client):
        resp_all = await seeded_client.get("/api/v1/backtest/bets")
        resp_offset = await seeded_client.get("/api/v1/backtest/bets?offset=3")
        assert len(resp_offset.json()["data"]) == len(resp_all.json()["data"]) - 3

    async def test_backtest_bets_year_filter(self, seeded_client):
        data = (await seeded_client.get("/api/v1/backtest/bets?year=2022")).json()
        assert data["total"] == 3
        for row in data["data"]:
            assert row["tourney_date"].startswith("2022")


class TestBankrollEndpoint:
    """GET /api/v1/bankroll — equity curve and summary stats."""

    async def test_bankroll_endpoint(self, seeded_client):
        response = await seeded_client.get("/api/v1/bankroll")
        assert response.status_code == 200
        data = response.json()
        assert "initial" in data
        assert "current" in data
        assert "peak" in data
        assert "max_drawdown" in data
        assert "curve" in data

    async def test_bankroll_curve_is_list(self, seeded_client):
        data = (await seeded_client.get("/api/v1/bankroll")).json()
        assert isinstance(data["curve"], list)
        assert len(data["curve"]) > 0

    async def test_bankroll_curve_has_date_and_bankroll(self, seeded_client):
        curve = (await seeded_client.get("/api/v1/bankroll")).json()["curve"]
        for point in curve:
            assert "date" in point
            assert "bankroll" in point

    async def test_bankroll_initial_matches_first_bankroll_before(self, seeded_client):
        data = (await seeded_client.get("/api/v1/bankroll")).json()
        assert data["initial"] == pytest.approx(1000.0)

    async def test_bankroll_empty_without_data(self, async_client):
        """Without seeding, returns zero values and empty curve."""
        data = (await async_client.get("/api/v1/bankroll")).json()
        assert data["initial"] == 0.0
        assert data["curve"] == []


class TestModelsEndpoint:
    """GET /api/v1/models — per-model metrics table."""

    async def test_models_endpoint(self, seeded_client):
        response = await seeded_client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0

    async def test_models_has_model_version(self, seeded_client):
        rows = (await seeded_client.get("/api/v1/models")).json()["data"]
        for row in rows:
            assert "model_version" in row
            assert "total_bets" in row

    async def test_models_logistic_v1_present(self, seeded_client):
        rows = (await seeded_client.get("/api/v1/models")).json()["data"]
        versions = [r["model_version"] for r in rows]
        assert "logistic_v1" in versions


class TestCalibrationEndpoint:
    """GET /api/v1/calibration — reliability diagram data."""

    async def test_calibration_endpoint(self, seeded_client):
        response = await seeded_client.get("/api/v1/calibration")
        assert response.status_code == 200
        data = response.json()
        assert "model_version" in data
        assert "bins" in data
        assert isinstance(data["bins"], list)
        assert len(data["bins"]) > 0

    async def test_calibration_bins_have_required_fields(self, seeded_client):
        bins = (await seeded_client.get("/api/v1/calibration")).json()["bins"]
        for b in bins:
            assert "midpoint" in b
            assert "empirical_freq" in b
            assert "n_samples" in b

    async def test_calibration_fold_filter(self, seeded_client):
        data = (await seeded_client.get("/api/v1/calibration?fold=2022")).json()
        assert data["fold"] == "2022"

    async def test_calibration_prefers_overall_fold(self, seeded_client):
        data = (await seeded_client.get("/api/v1/calibration")).json()
        # 'overall' fold exists in seed data — should be selected
        assert data["fold"] == "overall"

    async def test_calibration_empty_without_data(self, async_client):
        """Without seeding, returns empty bins list."""
        data = (await async_client.get("/api/v1/calibration")).json()
        assert data["bins"] == []


class TestPropsStub:
    """GET /api/v1/props — stub response (Phase 8 not implemented)."""

    async def test_props_stub(self, async_client):
        response = await async_client.get("/api/v1/props")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_available"
        assert data["data"] == []
