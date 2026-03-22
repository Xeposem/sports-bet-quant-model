"""
Integration tests for Monte Carlo simulation API endpoints.

Tests:
    POST /api/v1/simulation/run   — runs simulation from backtest_results, returns MonteCarloResult
    GET  /api/v1/simulation/result — returns last stored simulation result
    GET  /api/v1/simulation/result with no prior run — returns 404
"""
import pytest
from sqlalchemy import text


async def _seed_backtest_results(app, n_rows: int = 25):
    """Seed backtest_results with realistic rows for simulation resampling."""
    engine = app.state.engine
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        # Insert enough rows that simulation has meaningful input
        values = []
        for i in range(n_rows):
            fold_year = 2022 if i < 12 else 2023
            pnl = 0.06 if i % 2 == 0 else -0.04
            bankroll_before = 1000.0 + i * 5
            bankroll_after = bankroll_before + pnl
            values.append(
                f"({fold_year}, '2022-0001', {i + 1}, 'ATP', 'logistic_v1', {100 + i}, "
                f"1, 0.65, 1.75, 0.14, 0.08, 0.08, 1.0, {pnl}, 0.75, "
                f"{bankroll_before}, {bankroll_after}, 'Hard', 'G', 5, 20, '2022-06-{(i%28)+1:02d}')"
            )
        await conn.execute(
            text(
                "INSERT OR IGNORE INTO backtest_results "
                "(fold_year, tourney_id, match_num, tour, model_version, player_id, outcome, "
                "calibrated_prob, decimal_odds, ev, kelly_full, kelly_bet, flat_bet, pnl_kelly, "
                "pnl_flat, bankroll_before, bankroll_after, surface, tourney_level, "
                "winner_rank, loser_rank, tourney_date) VALUES "
                + ", ".join(values)
            )
        )


class TestSimulationRun:
    async def test_run_returns_200(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/simulation/run",
                json={"n_seasons": 100},
            )
        assert response.status_code == 200

    async def test_run_returns_required_fields(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/simulation/run",
                json={"n_seasons": 100},
            )
        data = response.json()
        assert "p_ruin" in data
        assert "expected_terminal" in data
        assert "sharpe_ratio" in data
        assert "paths" in data
        assert "terminal_distribution" in data
        assert "n_seasons" in data
        assert "initial_bankroll" in data

    async def test_run_paths_have_20_checkpoints(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/simulation/run",
                json={"n_seasons": 100},
            )
        data = response.json()
        assert len(data["paths"]) == 20

    async def test_run_respects_n_seasons(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/simulation/run",
                json={"n_seasons": 50},
            )
        data = response.json()
        assert data["n_seasons"] == 50
        assert len(data["terminal_distribution"]) == 50

    async def test_run_respects_initial_bankroll(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/simulation/run",
                json={"n_seasons": 50, "initial_bankroll": 5000.0},
            )
        data = response.json()
        assert data["initial_bankroll"] == 5000.0

    async def test_run_p_ruin_is_between_0_and_1(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/simulation/run",
                json={"n_seasons": 100},
            )
        data = response.json()
        assert 0.0 <= data["p_ruin"] <= 1.0


class TestSimulationResult:
    async def test_result_returns_404_when_no_simulation_run(self, async_app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/simulation/result")
        assert response.status_code == 404

    async def test_result_returns_200_after_run(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/simulation/run", json={"n_seasons": 50})
            response = await client.get("/api/v1/simulation/result")
        assert response.status_code == 200

    async def test_result_matches_run_output(self, async_app):
        await _seed_backtest_results(async_app)
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=async_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            run_resp = await client.post("/api/v1/simulation/run", json={"n_seasons": 50})
            get_resp = await client.get("/api/v1/simulation/result")
        run_data = run_resp.json()
        get_data = get_resp.json()
        assert run_data["p_ruin"] == get_data["p_ruin"]
        assert run_data["expected_terminal"] == get_data["expected_terminal"]
        assert run_data["n_seasons"] == get_data["n_seasons"]
