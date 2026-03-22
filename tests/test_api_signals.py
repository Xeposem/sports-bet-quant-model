"""
Integration tests for signals and CRUD delete endpoints.

Tests:
    GET   /api/v1/signals                — Returns signals from predictions with status field
    GET   /api/v1/signals?min_ev=X       — Filters low-EV signals
    PATCH /api/v1/signals/{id}/status    — Updates signal status
    GET   /api/v1/signals (idempotent)   — No duplicate signals on repeated calls
    DELETE /api/v1/props/lines/{id}      — Returns 204
    DELETE /api/v1/odds/{tid}/{mn}       — Returns 204
"""
import pytest
from sqlalchemy import text


async def _seed_predictions(app):
    """Seed predictions table with positive-EV rows for signal generation."""
    engine = app.state.engine
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        await conn.execute(text("""
            INSERT OR IGNORE INTO predictions
                (tourney_id, match_num, tour, player_id, model_version,
                 calibrated_prob, ev_value, edge, decimal_odds,
                 brier_contribution, log_loss_contribution, predicted_at)
            VALUES
                ('2024-0010', 1, 'ATP', 101, 'logistic_v1', 0.65, 0.12, 0.08, 1.75, 0.18, 0.50, '2024-06-01T10:00:00Z'),
                ('2024-0010', 2, 'ATP', 102, 'logistic_v1', 0.58, 0.08, 0.05, 1.65, 0.22, 0.55, '2024-06-01T10:00:00Z'),
                ('2024-0010', 3, 'ATP', 103, 'logistic_v1', 0.70, 0.25, 0.15, 1.80, 0.15, 0.45, '2024-06-02T10:00:00Z'),
                ('2024-0011', 1, 'ATP', 104, 'logistic_v1', 0.60, 0.03, 0.02, 1.55, 0.20, 0.52, '2024-06-03T10:00:00Z')
        """))


async def _seed_prop_lines(app):
    """Seed prop_lines table for DELETE endpoint tests."""
    engine = app.state.engine
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        await conn.execute(text("""
            INSERT INTO prop_lines
                (tour, player_name, stat_type, line_value, direction, match_date, bookmaker, entered_at)
            VALUES
                ('ATP', 'Test Player', 'aces', 5.5, 'over', '2024-06-01', 'prizepicks', '2024-06-01T10:00:00Z')
        """))


async def _seed_manual_odds(app):
    """Seed match_odds table with manual odds for DELETE endpoint tests."""
    engine = app.state.engine
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        await conn.execute(text("""
            INSERT OR REPLACE INTO match_odds
                (tourney_id, match_num, tour, bookmaker, decimal_odds_a, decimal_odds_b, source, imported_at)
            VALUES
                ('2024-test', 99, 'ATP', 'pinnacle', 1.75, 2.10, 'manual', '2024-06-01T10:00:00Z')
        """))


class TestGetSignals:
    async def test_get_signals_returns_200(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/signals")
        assert response.status_code == 200

    async def test_get_signals_returns_data_key(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/signals")
        data = response.json()
        assert "data" in data

    async def test_get_signals_has_status_field(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/signals")
        data = response.json()
        assert len(data["data"]) > 0
        for signal in data["data"]:
            assert "status" in signal
            assert signal["status"] == "new"

    async def test_get_signals_filters_by_min_ev(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Get all signals
            all_resp = await client.get("/api/v1/signals")
            all_data = all_resp.json()["data"]
            # Filter for high EV only (> 0.10)
            filtered_resp = await client.get("/api/v1/signals?min_ev=0.10")
            filtered_data = filtered_resp.json()["data"]

        # Filtered list should be smaller (we have 0.03 and 0.08 entries which should be excluded)
        assert len(filtered_data) < len(all_data)
        for signal in filtered_data:
            assert signal["ev_value"] >= 0.10

    async def test_get_signals_is_idempotent(self, async_app):
        """Multiple GET /signals calls should not duplicate signals."""
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.get("/api/v1/signals")
            resp2 = await client.get("/api/v1/signals")
        data1 = resp1.json()["data"]
        data2 = resp2.json()["data"]
        assert len(data1) == len(data2)

    async def test_get_signals_filters_by_status(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First get signals to populate the table
            await client.get("/api/v1/signals")
            # Filter by status=new
            resp = await client.get("/api/v1/signals?status=new")
        data = resp.json()["data"]
        for s in data:
            assert s["status"] == "new"


class TestPatchSignalStatus:
    async def test_patch_signal_status_returns_200(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Get signals first to create them
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            response = await client.patch(
                f"/api/v1/signals/{signal_id}/status",
                json={"status": "acted-on"},
            )
        assert response.status_code == 200

    async def test_patch_signal_status_updates_status(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            response = await client.patch(
                f"/api/v1/signals/{signal_id}/status",
                json={"status": "seen"},
            )
        data = response.json()
        assert data["status"] == "seen"

    async def test_patch_signal_status_nonexistent_returns_404(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/signals/99999/status",
                json={"status": "seen"},
            )
        assert response.status_code == 404

    async def test_patch_signal_invalid_status_returns_422(self, async_app):
        await _seed_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            response = await client.patch(
                f"/api/v1/signals/{signal_id}/status",
                json={"status": "invalid-status"},
            )
        assert response.status_code == 422


class TestDeletePropLine:
    async def test_delete_prop_line_returns_204(self, async_app):
        await _seed_prop_lines(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Get lines list first to find ID
            list_resp = await client.get("/api/v1/props/lines")
            line_id = list_resp.json()["data"][0]["id"]
            response = await client.delete(f"/api/v1/props/lines/{line_id}")
        assert response.status_code == 204

    async def test_delete_prop_line_nonexistent_returns_404(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/props/lines/99999")
        assert response.status_code == 404

    async def test_get_prop_lines_returns_list(self, async_app):
        await _seed_prop_lines(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/props/lines")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 1


class TestDeleteOdds:
    async def test_delete_odds_returns_204(self, async_app):
        await _seed_manual_odds(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/odds/2024-test/99")
        assert response.status_code == 204

    async def test_delete_odds_nonexistent_returns_404(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/odds/nonexistent-tourney/9999")
        assert response.status_code == 404

    async def test_get_odds_list_returns_manual_entries(self, async_app):
        await _seed_manual_odds(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/odds/list")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 1
