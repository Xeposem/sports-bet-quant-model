"""
Integration tests for paper trading endpoints.

Tests:
    POST /api/v1/paper/session            — Creates session with initial bankroll
    GET  /api/v1/paper/session            — Returns active session with stats
    POST /api/v1/paper/bets               — Places bet with kelly_stake > 0
    GET  /api/v1/paper/bets               — Returns bets for active session
    PATCH /api/v1/paper/bets/{id}/resolve — Resolves bet with P&L
    DELETE /api/v1/paper/session          — Deactivates session
    GET  /api/v1/paper/equity             — Returns equity curve
"""
import pytest
from sqlalchemy import text


async def _seed_signals_and_predictions(app):
    """Seed predictions and signals for paper bet tests."""
    engine = app.state.engine
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        await conn.execute(text("""
            INSERT OR IGNORE INTO predictions
                (tourney_id, match_num, tour, player_id, model_version,
                 calibrated_prob, ev_value, edge, decimal_odds,
                 brier_contribution, log_loss_contribution, predicted_at)
            VALUES
                ('2024-0050', 1, 'ATP', 201, 'logistic_v1', 0.65, 0.15, 0.10, 1.75, 0.18, 0.50, '2024-06-01T10:00:00Z'),
                ('2024-0050', 2, 'ATP', 202, 'logistic_v1', 0.70, 0.25, 0.18, 1.80, 0.15, 0.45, '2024-06-01T10:00:00Z')
        """))
        # Create signals manually (bypass the API upsert for isolation)
        await conn.execute(text("""
            INSERT OR IGNORE INTO signals
                (tourney_id, match_num, tour, player_id, model_version,
                 status, created_at, updated_at)
            VALUES
                ('2024-0050', 1, 'ATP', 201, 'logistic_v1', 'new', datetime('now'), datetime('now')),
                ('2024-0050', 2, 'ATP', 202, 'logistic_v1', 'new', datetime('now'), datetime('now'))
        """))


class TestPaperSession:
    async def test_post_session_returns_201(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/paper/session",
                json={"initial_bankroll": 5000.0},
            )
        assert response.status_code == 201

    async def test_post_session_returns_correct_bankroll(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/paper/session",
                json={"initial_bankroll": 5000.0},
            )
        data = response.json()
        assert data["initial_bankroll"] == 5000.0
        assert data["current_bankroll"] == 5000.0
        assert "id" in data
        assert data["active"] == 1

    async def test_get_session_returns_active_session(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 2000.0})
            response = await client.get("/api/v1/paper/session")
        assert response.status_code == 200
        data = response.json()
        assert data["initial_bankroll"] == 2000.0
        assert data["active"] == 1

    async def test_get_session_returns_404_when_no_session(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/paper/session")
        assert response.status_code == 404

    async def test_post_session_deactivates_existing(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            second = await client.post("/api/v1/paper/session", json={"initial_bankroll": 2000.0})
            get_resp = await client.get("/api/v1/paper/session")
        # Active session should be the second one
        assert get_resp.json()["initial_bankroll"] == 2000.0
        # Second session has a new ID
        assert first.json()["id"] != second.json()["id"]

    async def test_delete_session_returns_204(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            response = await client.delete("/api/v1/paper/session")
        assert response.status_code == 204

    async def test_delete_session_deactivates(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            await client.delete("/api/v1/paper/session")
            get_resp = await client.get("/api/v1/paper/session")
        assert get_resp.status_code == 404

    async def test_delete_session_returns_404_when_no_session(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/paper/session")
        assert response.status_code == 404


class TestPaperBets:
    async def test_post_bet_returns_201(self, async_app):
        await _seed_signals_and_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            # Get signal ID
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            response = await client.post(
                "/api/v1/paper/bets",
                json={"signal_id": signal_id},
            )
        assert response.status_code == 201

    async def test_post_bet_has_kelly_stake(self, async_app):
        await _seed_signals_and_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            response = await client.post(
                "/api/v1/paper/bets",
                json={"signal_id": signal_id},
            )
        data = response.json()
        assert "kelly_stake" in data
        assert data["kelly_stake"] > 0

    async def test_post_bet_no_session_returns_404(self, async_app):
        await _seed_signals_and_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            response = await client.post(
                "/api/v1/paper/bets",
                json={"signal_id": signal_id},
            )
        assert response.status_code == 404

    async def test_get_bets_returns_bet_list(self, async_app):
        await _seed_signals_and_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            await client.post("/api/v1/paper/bets", json={"signal_id": signal_id})
            response = await client.get("/api/v1/paper/bets")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1

    async def test_get_bets_returns_empty_when_no_session(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/paper/bets")
        assert response.status_code == 200
        assert response.json()["data"] == []


async def _setup_session_and_bet(async_app):
    """Helper: seed data, create session, place a bet; return bet_id."""
    await _seed_signals_and_predictions(async_app)
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=async_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
        sigs = await client.get("/api/v1/signals")
        signal_id = sigs.json()["data"][0]["id"]
        bet_resp = await client.post("/api/v1/paper/bets", json={"signal_id": signal_id})
        return bet_resp.json()["id"]


class TestPaperBetResolve:
    async def test_resolve_win_returns_200(self, async_app):
        bet_id = await _setup_session_and_bet(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/paper/bets/{bet_id}/resolve",
                json={"outcome": 1},
            )
        assert response.status_code == 200

    async def test_resolve_win_sets_positive_pnl(self, async_app):
        bet_id = await _setup_session_and_bet(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/paper/bets/{bet_id}/resolve",
                json={"outcome": 1},
            )
        data = response.json()
        assert data["outcome"] == 1
        assert data["pnl"] is not None
        assert data["pnl"] > 0
        assert data["bankroll_after"] is not None

    async def test_resolve_loss_sets_negative_pnl(self, async_app):
        bet_id = await _setup_session_and_bet(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/paper/bets/{bet_id}/resolve",
                json={"outcome": 0},
            )
        data = response.json()
        assert data["outcome"] == 0
        assert data["pnl"] is not None
        assert data["pnl"] < 0

    async def test_resolve_updates_session_bankroll(self, async_app):
        bet_id = await _setup_session_and_bet(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            before = await client.get("/api/v1/paper/session")
            initial_bankroll = before.json()["current_bankroll"]
            resolve_resp = await client.patch(
                f"/api/v1/paper/bets/{bet_id}/resolve",
                json={"outcome": 1},
            )
            pnl = resolve_resp.json()["pnl"]
            after = await client.get("/api/v1/paper/session")
            new_bankroll = after.json()["current_bankroll"]
        assert abs(new_bankroll - (initial_bankroll + pnl)) < 0.01

    async def test_resolve_nonexistent_bet_returns_404(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/paper/bets/99999/resolve",
                json={"outcome": 1},
            )
        assert response.status_code == 404

    async def test_resolve_invalid_outcome_returns_422(self, async_app):
        bet_id = await _setup_session_and_bet(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/paper/bets/{bet_id}/resolve",
                json={"outcome": 2},  # invalid: only 0 or 1 valid
            )
        assert response.status_code == 422


class TestPaperEquity:
    async def test_get_equity_returns_200(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            response = await client.get("/api/v1/paper/equity")
        assert response.status_code == 200

    async def test_get_equity_has_required_fields(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            response = await client.get("/api/v1/paper/equity")
        data = response.json()
        assert "initial" in data
        assert "current" in data
        assert "total_pnl" in data
        assert "curve" in data

    async def test_get_equity_curve_populated_after_resolution(self, async_app):
        await _seed_signals_and_predictions(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/paper/session", json={"initial_bankroll": 1000.0})
            sigs = await client.get("/api/v1/signals")
            signal_id = sigs.json()["data"][0]["id"]
            bet_resp = await client.post("/api/v1/paper/bets", json={"signal_id": signal_id})
            bet_id = bet_resp.json()["id"]
            await client.patch(f"/api/v1/paper/bets/{bet_id}/resolve", json={"outcome": 1})
            equity_resp = await client.get("/api/v1/paper/equity")
        data = equity_resp.json()
        assert len(data["curve"]) == 1
        assert data["curve"][0]["bankroll"] > 0

    async def test_get_equity_returns_200_no_session(self, async_app):
        """GET /paper/equity returns 200 with empty curve when no session exists."""
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/paper/equity")
        assert response.status_code == 200
        data = response.json()
        assert data["curve"] == []
