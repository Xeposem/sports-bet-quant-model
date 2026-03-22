"""
Monte Carlo simulation endpoints.

Routes:
    POST /api/v1/simulation/run    — Run Monte Carlo simulation from backtest results.
    GET  /api/v1/simulation/result — Return last stored simulation result.

Simulation uses backtest_results rows (kelly_bet > 0) to derive pnl_ratios.
Results are stored in simulation_results table (single-row, overwritten each run).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import MonteCarloRequest, MonteCarloResult, PercentilePath
from src.backtest.monte_carlo import run_monte_carlo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["simulation"])


# ---------------------------------------------------------------------------
# POST /simulation/run
# ---------------------------------------------------------------------------

@router.post("/run", response_model=MonteCarloResult)
async def run_simulation(body: MonteCarloRequest, request: Request) -> MonteCarloResult:
    """Run Monte Carlo simulation from historical backtest returns."""
    import numpy as np

    db_path: str = request.app.state.db_path

    def _sync_run() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # 1. Read backtest_results rows where kelly_bet > 0
            rows = conn.execute(
                "SELECT pnl_kelly, bankroll_before, fold_year FROM backtest_results WHERE kelly_bet > 0"
            ).fetchall()

            if not rows:
                raise HTTPException(
                    status_code=422,
                    detail="No backtest results found. Run a backtest first.",
                )

            pnl_list = [r["pnl_kelly"] for r in rows]
            bankroll_list = [r["bankroll_before"] for r in rows]
            years = [r["fold_year"] for r in rows]

            # 2. Compute pnl_ratios = pnl_kelly / bankroll_before
            pnl_ratios = np.array(pnl_list) / np.array(bankroll_list)

            # 3. Derive n_bets_per_season from actual annual bet count
            if years:
                distinct_years = len(set(years))
                n_bets_per_season = max(1, len(rows) // distinct_years)
            else:
                n_bets_per_season = 200

            # 4. Run Monte Carlo
            result = run_monte_carlo(
                pnl_ratios=pnl_ratios,
                n_seasons=body.n_seasons,
                n_bets_per_season=n_bets_per_season,
                initial_bankroll=body.initial_bankroll,
                seed=42,
            )

            # 5. Store in simulation_results (overwrite — single-row table)
            computed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute("DELETE FROM simulation_results")
            conn.execute(
                """
                INSERT INTO simulation_results
                    (n_seasons, initial_bankroll, kelly_fraction, ev_threshold,
                     p_ruin, expected_terminal, sharpe_ratio, paths_json, terminal_json, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.n_seasons,
                    body.initial_bankroll,
                    body.kelly_fraction,
                    body.ev_threshold,
                    result["p_ruin"],
                    result["expected_terminal"],
                    result["sharpe_ratio"],
                    json.dumps(result["paths"]),
                    json.dumps(result["terminal_distribution"]),
                    computed_at,
                ),
            )
            conn.commit()

            result["n_seasons"] = body.n_seasons
            result["initial_bankroll"] = body.initial_bankroll
            return result

        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_run)

    return MonteCarloResult(
        p_ruin=data["p_ruin"],
        expected_terminal=data["expected_terminal"],
        sharpe_ratio=data["sharpe_ratio"],
        paths=[PercentilePath(**p) for p in data["paths"]],
        terminal_distribution=data["terminal_distribution"],
        n_seasons=data["n_seasons"],
        initial_bankroll=data["initial_bankroll"],
    )


# ---------------------------------------------------------------------------
# GET /simulation/result
# ---------------------------------------------------------------------------

@router.get("/result", response_model=MonteCarloResult)
async def get_simulation_result(request: Request) -> MonteCarloResult:
    """Return the last stored Monte Carlo simulation result."""
    db_path: str = request.app.state.db_path

    def _sync_fetch() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM simulation_results ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return {
                "p_ruin": row["p_ruin"],
                "expected_terminal": row["expected_terminal"],
                "sharpe_ratio": row["sharpe_ratio"],
                "paths": json.loads(row["paths_json"]),
                "terminal_distribution": json.loads(row["terminal_json"]),
                "n_seasons": row["n_seasons"],
                "initial_bankroll": row["initial_bankroll"],
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_fetch)

    if data is None:
        raise HTTPException(status_code=404, detail="No simulation results found. Run POST /simulation/run first.")

    return MonteCarloResult(
        p_ruin=data["p_ruin"],
        expected_terminal=data["expected_terminal"],
        sharpe_ratio=data["sharpe_ratio"],
        paths=[PercentilePath(**p) for p in data["paths"]],
        terminal_distribution=data["terminal_distribution"],
        n_seasons=data["n_seasons"],
        initial_bankroll=data["initial_bankroll"],
    )
