"""
Tests for src/backtest/reporting.py

Uses in-memory SQLite with manually inserted backtest_results rows
to test the reporting layer independently of the walk-forward engine.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BACKTEST_DDL = """
CREATE TABLE IF NOT EXISTS backtest_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fold_year        INTEGER NOT NULL,
    tourney_id       TEXT    NOT NULL,
    match_num        INTEGER NOT NULL,
    tour             TEXT    NOT NULL DEFAULT 'ATP',
    model_version    TEXT    NOT NULL,
    player_id        INTEGER NOT NULL,
    outcome          INTEGER NOT NULL,
    calibrated_prob  REAL    NOT NULL,
    decimal_odds     REAL    NOT NULL,
    ev               REAL    NOT NULL,
    kelly_full       REAL    NOT NULL,
    kelly_bet        REAL    NOT NULL,
    flat_bet         REAL    NOT NULL DEFAULT 1.0,
    pnl_kelly        REAL    NOT NULL,
    pnl_flat         REAL    NOT NULL,
    bankroll_before  REAL    NOT NULL,
    bankroll_after   REAL    NOT NULL,
    surface          TEXT,
    tourney_level    TEXT,
    winner_rank      INTEGER,
    loser_rank       INTEGER,
    tourney_date     TEXT    NOT NULL,
    UNIQUE (tourney_id, match_num, tour, player_id, model_version)
);

CREATE TABLE IF NOT EXISTS calibration_data (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fold_label     TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    bin_midpoints  TEXT NOT NULL,
    empirical_freq TEXT NOT NULL,
    n_samples      INTEGER NOT NULL,
    computed_at    TEXT NOT NULL,
    UNIQUE (fold_label, model_version)
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_BACKTEST_DDL)
    return conn


def _insert_rows(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Insert backtest_results rows (subset of columns OK — rest use defaults/NULL)."""
    for row in rows:
        conn.execute(
            """
            INSERT INTO backtest_results
                (fold_year, tourney_id, match_num, tour, model_version,
                 player_id, outcome, calibrated_prob, decimal_odds, ev,
                 kelly_full, kelly_bet, flat_bet,
                 pnl_kelly, pnl_flat, bankroll_before, bankroll_after,
                 surface, tourney_level, winner_rank, loser_rank, tourney_date)
            VALUES
                (:fold_year, :tourney_id, :match_num, :tour, :model_version,
                 :player_id, :outcome, :calibrated_prob, :decimal_odds, :ev,
                 :kelly_full, :kelly_bet, :flat_bet,
                 :pnl_kelly, :pnl_flat, :bankroll_before, :bankroll_after,
                 :surface, :tourney_level, :winner_rank, :loser_rank, :tourney_date)
            """,
            row,
        )
    conn.commit()


def _base_row(**kwargs) -> dict:
    """Return a minimal valid backtest row with sensible defaults."""
    defaults = dict(
        fold_year=2022,
        tourney_id="2022-001",
        match_num=1,
        tour="ATP",
        model_version="logistic_v1",
        player_id=100,
        outcome=1,
        calibrated_prob=0.65,
        decimal_odds=1.8,
        ev=0.03,
        kelly_full=0.1,
        kelly_bet=5.0,
        flat_bet=1.0,
        pnl_kelly=4.0,
        pnl_flat=0.8,
        bankroll_before=1000.0,
        bankroll_after=1004.0,
        surface="Hard",
        tourney_level="A",
        winner_rank=10,
        loser_rank=25,
        tourney_date="2022-03-15",
    )
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Test: ROI by surface
# ---------------------------------------------------------------------------

class TestRoiBySurface:
    def test_roi_by_surface(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        rows = [
            _base_row(
                tourney_id="2022-001", match_num=1, player_id=100,
                surface="Hard", kelly_bet=10.0, flat_bet=1.0,
                pnl_kelly=8.0, pnl_flat=0.8,
            ),
            _base_row(
                tourney_id="2022-001", match_num=2, player_id=101,
                surface="Hard", kelly_bet=5.0, flat_bet=1.0,
                pnl_kelly=4.0, pnl_flat=0.8,
            ),
            _base_row(
                tourney_id="2022-002", match_num=1, player_id=102,
                surface="Clay", kelly_bet=8.0, flat_bet=1.0,
                pnl_kelly=-8.0, pnl_flat=-1.0,
            ),
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn, model_version="logistic_v1")

        assert "by_surface" in result
        surfaces = {r["label"]: r for r in result["by_surface"]}

        # Hard: 2 bets, pnl_kelly=12, kelly_bet=15 => roi = 12/15 = 0.8
        assert "Hard" in surfaces
        hard = surfaces["Hard"]
        assert hard["n_bets"] == 2
        assert abs(hard["kelly_roi"] - 12.0 / 15.0) < 1e-6
        assert abs(hard["flat_roi"] - 1.6 / 2.0) < 1e-6
        assert "low_confidence" in hard

        # Clay: 1 bet
        assert "Clay" in surfaces
        clay = surfaces["Clay"]
        assert clay["n_bets"] == 1


# ---------------------------------------------------------------------------
# Test: ROI by tournament level
# ---------------------------------------------------------------------------

class TestRoiByTourneyLevel:
    def test_roi_by_tourney_level(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        rows = [
            _base_row(tourney_id="t1", match_num=1, player_id=100,
                      tourney_level="G", kelly_bet=10.0, pnl_kelly=5.0,
                      flat_bet=1.0, pnl_flat=0.5),
            _base_row(tourney_id="t1", match_num=2, player_id=101,
                      tourney_level="M", kelly_bet=8.0, pnl_kelly=-8.0,
                      flat_bet=1.0, pnl_flat=-1.0),
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)

        assert "by_tourney_level" in result
        levels = {r["label"]: r for r in result["by_tourney_level"]}

        assert "G" in levels
        assert "M" in levels
        assert levels["G"]["n_bets"] == 1
        assert abs(levels["G"]["kelly_roi"] - 5.0 / 10.0) < 1e-6


# ---------------------------------------------------------------------------
# Test: ROI by EV bucket
# ---------------------------------------------------------------------------

class TestRoiByEvBucket:
    def test_roi_by_ev_bucket(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        rows = [
            _base_row(tourney_id="t1", match_num=1, player_id=100,
                      ev=0.12, kelly_bet=10.0, pnl_kelly=5.0,
                      flat_bet=1.0, pnl_flat=0.5),   # >10%
            _base_row(tourney_id="t1", match_num=2, player_id=101,
                      ev=0.07, kelly_bet=8.0, pnl_kelly=3.0,
                      flat_bet=1.0, pnl_flat=0.3),   # >5%
            _base_row(tourney_id="t1", match_num=3, player_id=102,
                      ev=0.03, kelly_bet=6.0, pnl_kelly=2.0,
                      flat_bet=1.0, pnl_flat=0.2),   # >2%
            _base_row(tourney_id="t1", match_num=4, player_id=103,
                      ev=0.01, kelly_bet=5.0, pnl_kelly=1.0,
                      flat_bet=1.0, pnl_flat=0.1),   # >0%
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)

        assert "by_ev_bucket" in result
        buckets = {r["label"]: r for r in result["by_ev_bucket"]}

        # Should have >0%, >2%, >5%, >10% buckets
        assert ">10%" in buckets
        assert ">5%" in buckets
        assert ">2%" in buckets
        assert ">0%" in buckets

        # >10% bucket: 1 row with ev=0.12
        assert buckets[">10%"]["n_bets"] == 1


# ---------------------------------------------------------------------------
# Test: ROI by year
# ---------------------------------------------------------------------------

class TestRoiByYear:
    def test_roi_by_year(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        rows = [
            _base_row(tourney_id="t1", match_num=1, player_id=100,
                      fold_year=2021, tourney_date="2021-05-10",
                      kelly_bet=10.0, pnl_kelly=5.0,
                      flat_bet=1.0, pnl_flat=0.5),
            _base_row(tourney_id="t1", match_num=2, player_id=101,
                      fold_year=2022, tourney_date="2022-05-10",
                      kelly_bet=8.0, pnl_kelly=3.0,
                      flat_bet=1.0, pnl_flat=0.3),
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)

        assert "by_year" in result
        years = {r["label"]: r for r in result["by_year"]}

        assert 2021 in years or "2021" in years
        year_key = 2021 if 2021 in years else "2021"
        assert years[year_key]["n_bets"] == 1


# ---------------------------------------------------------------------------
# Test: ROI by rank tier
# ---------------------------------------------------------------------------

class TestRoiByRankTier:
    def test_roi_by_rank_tier(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        # Betting on winner (outcome=1), use winner_rank
        rows = [
            # top10 (winner_rank=5)
            _base_row(tourney_id="t1", match_num=1, player_id=100,
                      outcome=1, winner_rank=5, loser_rank=30,
                      kelly_bet=10.0, pnl_kelly=5.0,
                      flat_bet=1.0, pnl_flat=0.5),
            # top50 (winner_rank=20)
            _base_row(tourney_id="t1", match_num=2, player_id=101,
                      outcome=1, winner_rank=20, loser_rank=80,
                      kelly_bet=8.0, pnl_kelly=3.0,
                      flat_bet=1.0, pnl_flat=0.3),
            # top100 (loser_rank=60 — betting on loser side)
            _base_row(tourney_id="t1", match_num=3, player_id=102,
                      outcome=0, winner_rank=5, loser_rank=60,
                      kelly_bet=6.0, pnl_kelly=-6.0,
                      flat_bet=1.0, pnl_flat=-1.0),
            # outside100 (loser_rank=150)
            _base_row(tourney_id="t1", match_num=4, player_id=103,
                      outcome=0, winner_rank=5, loser_rank=150,
                      kelly_bet=5.0, pnl_kelly=-5.0,
                      flat_bet=1.0, pnl_flat=-1.0),
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)

        assert "by_rank_tier" in result
        tiers = {r["label"]: r for r in result["by_rank_tier"]}

        assert "top10" in tiers
        assert "top50" in tiers
        assert "top100" in tiers
        assert "outside100" in tiers


# ---------------------------------------------------------------------------
# Test: thin bucket flagging
# ---------------------------------------------------------------------------

class TestThinBucketFlag:
    def test_thin_bucket_flag(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        # Insert only 5 Clay rows (< 30 threshold)
        rows = [
            _base_row(tourney_id="t1", match_num=i, player_id=200 + i,
                      surface="Clay", kelly_bet=5.0, pnl_kelly=2.0,
                      flat_bet=1.0, pnl_flat=0.4)
            for i in range(1, 6)
        ]
        # Insert 35 Hard rows (>= 30 threshold)
        rows += [
            _base_row(tourney_id="t2", match_num=i, player_id=300 + i,
                      surface="Hard", kelly_bet=5.0, pnl_kelly=2.0,
                      flat_bet=1.0, pnl_flat=0.4)
            for i in range(1, 36)
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)
        surfaces = {r["label"]: r for r in result["by_surface"]}

        # Clay has 5 bets < 30, should be flagged
        assert surfaces["Clay"]["low_confidence"] is True
        assert surfaces["Clay"]["n_bets"] == 5

        # Hard has 35 bets >= 30, should NOT be flagged
        assert surfaces["Hard"]["low_confidence"] is False
        assert surfaces["Hard"]["n_bets"] == 35


# ---------------------------------------------------------------------------
# Test: flat vs Kelly ROI both present
# ---------------------------------------------------------------------------

class TestFlatVsKellyRoi:
    def test_flat_vs_kelly_roi(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        rows = [
            _base_row(tourney_id="t1", match_num=i, player_id=400 + i,
                      surface="Hard", kelly_bet=10.0, pnl_kelly=5.0,
                      flat_bet=1.0, pnl_flat=0.5)
            for i in range(1, 5)
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)

        # Every breakdown row must have both kelly_roi and flat_roi
        for dimension_key in ["by_surface", "by_tourney_level", "by_year",
                               "by_ev_bucket", "by_rank_tier"]:
            for row in result[dimension_key]:
                assert "kelly_roi" in row, f"Missing kelly_roi in {dimension_key}"
                assert "flat_roi" in row, f"Missing flat_roi in {dimension_key}"
                assert "total_pnl_kelly" in row
                assert "total_pnl_flat" in row

        # Overall must also have both
        assert "kelly_roi" in result["overall"]
        assert "flat_roi" in result["overall"]


# ---------------------------------------------------------------------------
# Test: calibration storage
# ---------------------------------------------------------------------------

class TestCalibrationStore:
    def test_calibration_store(self):
        from src.backtest.reporting import store_calibration_data

        conn = _make_conn()
        y_true = np.array([1, 1, 0, 1, 0, 0, 1, 0, 1, 1,
                           1, 0, 1, 0, 1, 1, 0, 1, 0, 0])
        y_prob = np.array([0.8, 0.7, 0.3, 0.9, 0.2, 0.1, 0.6, 0.4, 0.75, 0.65,
                           0.85, 0.35, 0.55, 0.45, 0.7, 0.6, 0.25, 0.8, 0.15, 0.3])

        store_calibration_data(
            conn, y_true, y_prob,
            fold_label="2022", model_version="logistic_v1",
        )

        row = conn.execute(
            "SELECT * FROM calibration_data WHERE fold_label='2022'"
        ).fetchone()
        assert row is not None

        bin_midpoints = json.loads(row["bin_midpoints"])
        empirical_freq = json.loads(row["empirical_freq"])
        n_samples = row["n_samples"]

        assert isinstance(bin_midpoints, list)
        assert isinstance(empirical_freq, list)
        assert len(bin_midpoints) > 0
        assert len(empirical_freq) == len(bin_midpoints)
        assert n_samples == 20

    def test_calibration_store_idempotent(self):
        """Second call with same fold_label should overwrite (INSERT OR REPLACE)."""
        from src.backtest.reporting import store_calibration_data

        conn = _make_conn()
        y_true = np.array([1, 0, 1, 0, 1])
        y_prob = np.array([0.8, 0.3, 0.7, 0.2, 0.9])

        store_calibration_data(conn, y_true, y_prob, "2022", "logistic_v1")
        store_calibration_data(conn, y_true, y_prob, "2022", "logistic_v1")

        count = conn.execute("SELECT COUNT(*) FROM calibration_data").fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# Test: calibration PNG created
# ---------------------------------------------------------------------------

class TestCalibrationPngCreated:
    def test_calibration_png_created(self):
        from src.backtest.reporting import generate_calibration_plots

        conn = _make_conn()
        # Insert 3 folds of data with sufficient samples for calibration
        for fold_year in [2020, 2021, 2022]:
            rows = [
                _base_row(
                    tourney_id=f"{fold_year}-t",
                    match_num=i,
                    player_id=1000 + i + fold_year,
                    fold_year=fold_year,
                    outcome=1 if i % 2 == 0 else 0,
                    calibrated_prob=0.4 + 0.01 * i,
                    kelly_bet=5.0,
                    pnl_kelly=2.0 if i % 2 == 0 else -5.0,
                    flat_bet=1.0,
                    pnl_flat=0.8 if i % 2 == 0 else -1.0,
                )
                for i in range(1, 21)
            ]
            _insert_rows(conn, rows)

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_calibration_plots(conn, "logistic_v1", tmpdir)

            # Should return list of paths
            assert isinstance(paths, list)
            assert len(paths) > 0

            # Per-fold PNGs
            for fold_year in [2020, 2021, 2022]:
                fold_png = os.path.join(tmpdir, f"calibration_{fold_year}.png")
                assert os.path.exists(fold_png), f"Missing {fold_png}"

            # Aggregate PNG
            agg_png = os.path.join(tmpdir, "calibration_aggregate.png")
            assert os.path.exists(agg_png), f"Missing {agg_png}"


# ---------------------------------------------------------------------------
# Test: bankroll curve PNG
# ---------------------------------------------------------------------------

class TestBankrollCurvePng:
    def test_bankroll_curve_png(self):
        from src.backtest.reporting import generate_bankroll_curve

        conn = _make_conn()
        # Insert bets ordered chronologically
        rows = [
            _base_row(
                tourney_id="t1",
                match_num=i,
                player_id=2000 + i,
                tourney_date=f"2022-0{(i // 10) + 1}-{(i % 10) + 10}",
                bankroll_before=1000.0 + i * 10,
                bankroll_after=1000.0 + (i + 1) * 10,
                kelly_bet=5.0,
                pnl_kelly=10.0,
            )
            for i in range(1, 11)
        ]
        _insert_rows(conn, rows)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_bankroll_curve(conn, "logistic_v1", tmpdir)

            assert path is not None
            assert os.path.exists(path)
            assert path.endswith("bankroll_curve.png")


# ---------------------------------------------------------------------------
# Test: overall ROI in compute_roi_breakdowns
# ---------------------------------------------------------------------------

class TestOverallRoi:
    def test_overall_roi(self):
        from src.backtest.reporting import compute_roi_breakdowns

        conn = _make_conn()
        rows = [
            _base_row(tourney_id="t1", match_num=1, player_id=100,
                      kelly_bet=10.0, pnl_kelly=5.0, flat_bet=1.0, pnl_flat=0.5),
            _base_row(tourney_id="t1", match_num=2, player_id=101,
                      kelly_bet=8.0, pnl_kelly=-2.0, flat_bet=1.0, pnl_flat=-1.0),
        ]
        _insert_rows(conn, rows)

        result = compute_roi_breakdowns(conn)

        assert "overall" in result
        overall = result["overall"]
        assert "n_bets" in overall
        assert "kelly_roi" in overall
        assert "flat_roi" in overall
        assert overall["n_bets"] == 2
        # kelly_roi = (5 + -2) / (10 + 8) = 3/18
        assert abs(overall["kelly_roi"] - 3.0 / 18.0) < 1e-6


# ---------------------------------------------------------------------------
# Test: print_summary runs without error
# ---------------------------------------------------------------------------

class TestPrintSummary:
    def test_print_summary(self, capsys):
        from src.backtest.reporting import print_summary

        summary = {
            "folds_run": 3,
            "total_bets": 150,
            "bets_placed": 45,
            "bets_skipped": 105,
            "total_pnl_kelly": 23.5,
            "total_pnl_flat": 8.1,
            "final_bankroll": 1023.5,
            "start_bankroll": 1000.0,
        }
        breakdowns = {
            "overall": {"n_bets": 45, "kelly_roi": 0.05, "flat_roi": 0.02,
                        "total_pnl_kelly": 23.5, "total_pnl_flat": 8.1},
            "by_surface": [
                {"label": "Hard", "n_bets": 30, "kelly_roi": 0.06,
                 "flat_roi": 0.03, "total_pnl_kelly": 18.0,
                 "total_pnl_flat": 6.0, "low_confidence": False},
                {"label": "Clay", "n_bets": 5, "kelly_roi": -0.1,
                 "flat_roi": -0.05, "total_pnl_kelly": -2.0,
                 "total_pnl_flat": -1.0, "low_confidence": True},
            ],
            "by_tourney_level": [],
            "by_year": [],
            "by_ev_bucket": [],
            "by_rank_tier": [],
        }

        print_summary(summary, breakdowns)

        out = capsys.readouterr().out
        # Should print something substantial
        assert "bankroll" in out.lower() or "roi" in out.lower()
        # Low-confidence bucket should be flagged
        assert "Clay" in out
        assert "*" in out or "low" in out.lower() or "n=" in out
