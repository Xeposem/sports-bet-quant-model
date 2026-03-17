"""
Backtesting reporting: ROI breakdowns, calibration plots, bankroll curve.

Transforms raw backtest_results rows into actionable analysis:
  - ROI breakdowns by surface, tourney_level, year, EV bucket, rank tier
  - Per-fold and aggregate calibration plots (PNG)
  - Bankroll evolution curve (PNG)
  - Calibration curve data stored in SQLite

Key exports:
  - compute_roi_breakdowns
  - generate_calibration_plots
  - generate_bankroll_curve
  - store_calibration_data
  - print_summary
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be before pyplot import
import matplotlib.pyplot as plt
import numpy as np

from src.model.metrics import calibration_curve_data


logger = logging.getLogger(__name__)

# Threshold below which a bucket is flagged as low-confidence
_LOW_CONFIDENCE_THRESHOLD = 30


# ---------------------------------------------------------------------------
# ROI helpers
# ---------------------------------------------------------------------------

def _compute_roi(pnl: float, stake: float) -> float:
    """Return ROI as pnl/stake, or 0.0 when no stake was placed."""
    if stake <= 0:
        return 0.0
    return pnl / stake


def _bucket_row(label, n_bets: int, pnl_kelly: float, stake_kelly: float,
                pnl_flat: float, stake_flat: float) -> dict:
    """Build a standard breakdown row dict."""
    return {
        "label": label,
        "n_bets": n_bets,
        "kelly_roi": _compute_roi(pnl_kelly, stake_kelly),
        "flat_roi": _compute_roi(pnl_flat, stake_flat),
        "total_pnl_kelly": pnl_kelly,
        "total_pnl_flat": pnl_flat,
        "low_confidence": n_bets < _LOW_CONFIDENCE_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# SQL query templates
# ---------------------------------------------------------------------------

# Group-by dimension queries
# We filter kelly_bet > 0 for ROI calculations to avoid zero-stake division.
# For flat staking we always stake flat_bet per decision row.

_ROI_BY_SURFACE_SQL = """
    SELECT
        surface                      AS label,
        COUNT(*)                     AS n_bets,
        SUM(pnl_kelly)               AS total_pnl_kelly,
        SUM(kelly_bet)               AS total_stake_kelly,
        SUM(pnl_flat)                AS total_pnl_flat,
        SUM(flat_bet)                AS total_stake_flat
    FROM backtest_results
    WHERE model_version = :model_version
      AND kelly_bet > 0
    GROUP BY surface
    ORDER BY surface
"""

_ROI_BY_TOURNEY_LEVEL_SQL = """
    SELECT
        tourney_level                AS label,
        COUNT(*)                     AS n_bets,
        SUM(pnl_kelly)               AS total_pnl_kelly,
        SUM(kelly_bet)               AS total_stake_kelly,
        SUM(pnl_flat)                AS total_pnl_flat,
        SUM(flat_bet)                AS total_stake_flat
    FROM backtest_results
    WHERE model_version = :model_version
      AND kelly_bet > 0
    GROUP BY tourney_level
    ORDER BY tourney_level
"""

_ROI_BY_YEAR_SQL = """
    SELECT
        fold_year                    AS label,
        COUNT(*)                     AS n_bets,
        SUM(pnl_kelly)               AS total_pnl_kelly,
        SUM(kelly_bet)               AS total_stake_kelly,
        SUM(pnl_flat)                AS total_pnl_flat,
        SUM(flat_bet)                AS total_stake_flat
    FROM backtest_results
    WHERE model_version = :model_version
      AND kelly_bet > 0
    GROUP BY fold_year
    ORDER BY fold_year
"""

_ROI_BY_EV_BUCKET_SQL = """
    SELECT
        CASE
            WHEN ev >= 0.10 THEN '>10%'
            WHEN ev >= 0.05 THEN '>5%'
            WHEN ev >= 0.02 THEN '>2%'
            ELSE '>0%'
        END                          AS label,
        COUNT(*)                     AS n_bets,
        SUM(pnl_kelly)               AS total_pnl_kelly,
        SUM(kelly_bet)               AS total_stake_kelly,
        SUM(pnl_flat)                AS total_pnl_flat,
        SUM(flat_bet)                AS total_stake_flat
    FROM backtest_results
    WHERE model_version = :model_version
      AND kelly_bet > 0
    GROUP BY label
    ORDER BY
        CASE label
            WHEN '>10%' THEN 4
            WHEN '>5%'  THEN 3
            WHEN '>2%'  THEN 2
            ELSE        1
        END DESC
"""

# Rank tier: use the bet-on player's rank.
# outcome=1 => we bet on winner side => use winner_rank
# outcome=0 => we bet on loser side  => use loser_rank
_ROI_BY_RANK_TIER_SQL = """
    SELECT
        CASE
            WHEN outcome = 1 THEN
                CASE
                    WHEN winner_rank IS NULL OR winner_rank > 100 THEN 'outside100'
                    WHEN winner_rank > 50  THEN 'top100'
                    WHEN winner_rank > 10  THEN 'top50'
                    ELSE 'top10'
                END
            ELSE
                CASE
                    WHEN loser_rank IS NULL OR loser_rank > 100 THEN 'outside100'
                    WHEN loser_rank > 50  THEN 'top100'
                    WHEN loser_rank > 10  THEN 'top50'
                    ELSE 'top10'
                END
        END                          AS label,
        COUNT(*)                     AS n_bets,
        SUM(pnl_kelly)               AS total_pnl_kelly,
        SUM(kelly_bet)               AS total_stake_kelly,
        SUM(pnl_flat)                AS total_pnl_flat,
        SUM(flat_bet)                AS total_stake_flat
    FROM backtest_results
    WHERE model_version = :model_version
      AND kelly_bet > 0
    GROUP BY label
    ORDER BY label
"""

_ROI_OVERALL_SQL = """
    SELECT
        COUNT(*)                     AS n_bets,
        SUM(pnl_kelly)               AS total_pnl_kelly,
        SUM(kelly_bet)               AS total_stake_kelly,
        SUM(pnl_flat)                AS total_pnl_flat,
        SUM(flat_bet)                AS total_stake_flat
    FROM backtest_results
    WHERE model_version = :model_version
      AND kelly_bet > 0
"""


def _rows_to_breakdowns(rows: list) -> list[dict]:
    """Convert SQL result rows to breakdown dict list."""
    result = []
    for row in rows:
        result.append(_bucket_row(
            label=row[0],
            n_bets=row[1],
            pnl_kelly=row[2] or 0.0,
            stake_kelly=row[3] or 0.0,
            pnl_flat=row[4] or 0.0,
            stake_flat=row[5] or 0.0,
        ))
    return result


# ---------------------------------------------------------------------------
# Public: compute_roi_breakdowns
# ---------------------------------------------------------------------------

def compute_roi_breakdowns(
    conn: sqlite3.Connection,
    model_version: str = "logistic_v1",
) -> dict:
    """
    Compute ROI breakdowns across six dimensions from backtest_results.

    Parameters
    ----------
    conn:
        Open SQLite connection with backtest_results populated.
    model_version:
        Model version string to filter results.

    Returns
    -------
    Dict with keys:
        by_surface, by_tourney_level, by_year, by_ev_bucket, by_rank_tier, overall.
    Each dimension value is a list of row dicts:
        {label, n_bets, kelly_roi, flat_roi, total_pnl_kelly, total_pnl_flat, low_confidence}
    overall is a single dict (no low_confidence).
    """
    params = {"model_version": model_version}

    by_surface = _rows_to_breakdowns(
        conn.execute(_ROI_BY_SURFACE_SQL, params).fetchall()
    )
    by_tourney_level = _rows_to_breakdowns(
        conn.execute(_ROI_BY_TOURNEY_LEVEL_SQL, params).fetchall()
    )
    by_year = _rows_to_breakdowns(
        conn.execute(_ROI_BY_YEAR_SQL, params).fetchall()
    )
    by_ev_bucket = _rows_to_breakdowns(
        conn.execute(_ROI_BY_EV_BUCKET_SQL, params).fetchall()
    )
    by_rank_tier = _rows_to_breakdowns(
        conn.execute(_ROI_BY_RANK_TIER_SQL, params).fetchall()
    )

    overall_row = conn.execute(_ROI_OVERALL_SQL, params).fetchone()
    n_bets = overall_row[0] or 0
    pnl_kelly = overall_row[1] or 0.0
    stake_kelly = overall_row[2] or 0.0
    pnl_flat = overall_row[3] or 0.0
    stake_flat = overall_row[4] or 0.0
    overall = {
        "n_bets": n_bets,
        "kelly_roi": _compute_roi(pnl_kelly, stake_kelly),
        "flat_roi": _compute_roi(pnl_flat, stake_flat),
        "total_pnl_kelly": pnl_kelly,
        "total_pnl_flat": pnl_flat,
    }

    return {
        "by_surface": by_surface,
        "by_tourney_level": by_tourney_level,
        "by_year": by_year,
        "by_ev_bucket": by_ev_bucket,
        "by_rank_tier": by_rank_tier,
        "overall": overall,
    }


# ---------------------------------------------------------------------------
# Public: store_calibration_data
# ---------------------------------------------------------------------------

def store_calibration_data(
    conn: sqlite3.Connection,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    fold_label: str,
    model_version: str,
) -> None:
    """
    Compute calibration curve and store as JSON in calibration_data table.

    Uses INSERT OR REPLACE for idempotency.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    y_true:
        Array of true binary labels.
    y_prob:
        Array of predicted probabilities.
    fold_label:
        Identifier for the fold (e.g., "2022" or "aggregate").
    model_version:
        Model version string.
    """
    curve = calibration_curve_data(y_true, y_prob, n_bins=10)
    n_samples = int(len(y_true))
    computed_at = datetime.now(tz=timezone.utc).isoformat()

    conn.execute(
        """
        INSERT OR REPLACE INTO calibration_data
            (fold_label, model_version, bin_midpoints, empirical_freq,
             n_samples, computed_at)
        VALUES
            (:fold_label, :model_version, :bin_midpoints, :empirical_freq,
             :n_samples, :computed_at)
        """,
        {
            "fold_label": fold_label,
            "model_version": model_version,
            "bin_midpoints": json.dumps(curve["bin_midpoints"]),
            "empirical_freq": json.dumps(curve["empirical_freq"]),
            "n_samples": n_samples,
            "computed_at": computed_at,
        },
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Public: generate_calibration_plots
# ---------------------------------------------------------------------------

def generate_calibration_plots(
    conn: sqlite3.Connection,
    model_version: str,
    output_dir: str,
) -> list[str]:
    """
    Generate per-fold and aggregate calibration plots and save as PNG files.

    For each fold year in backtest_results, computes calibration curve and saves
    a PNG. Also computes aggregate calibration over all folds.

    Parameters
    ----------
    conn:
        Open SQLite connection with backtest_results populated.
    model_version:
        Model version string to filter results.
    output_dir:
        Directory to save PNG files. Created if it does not exist.

    Returns
    -------
    List of created file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    created_paths = []

    # Fetch per-fold data
    fold_years = [
        row[0] for row in conn.execute(
            "SELECT DISTINCT fold_year FROM backtest_results "
            "WHERE model_version = ? ORDER BY fold_year",
            (model_version,),
        ).fetchall()
    ]

    all_y_true: list[float] = []
    all_y_prob: list[float] = []

    for fold_year in fold_years:
        rows = conn.execute(
            """
            SELECT outcome, calibrated_prob
            FROM backtest_results
            WHERE model_version = ? AND fold_year = ?
            ORDER BY tourney_date, id
            """,
            (model_version, fold_year),
        ).fetchall()

        if not rows:
            continue

        y_true = np.array([r[0] for r in rows], dtype=float)
        y_prob = np.array([r[1] for r in rows], dtype=float)

        all_y_true.extend(y_true.tolist())
        all_y_prob.extend(y_prob.tolist())

        # Skip fold if not enough unique probability values for calibration curve
        if len(y_true) < 5:
            continue

        try:
            curve = calibration_curve_data(y_true, y_prob, n_bins=10)
        except Exception as exc:
            logger.warning("Fold %s calibration curve failed: %s", fold_year, exc)
            continue

        fig, ax = plt.subplots(figsize=(6, 6))
        ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
        ax.plot(curve["bin_midpoints"], curve["empirical_freq"],
                "o-", color="steelblue", label="Model")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Fraction of positives")
        ax.set_title(f"Calibration — Fold {fold_year}")
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        path = os.path.join(output_dir, f"calibration_{fold_year}.png")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        created_paths.append(path)

    # Aggregate calibration plot
    if len(all_y_true) >= 5:
        agg_y_true = np.array(all_y_true, dtype=float)
        agg_y_prob = np.array(all_y_prob, dtype=float)

        try:
            agg_curve = calibration_curve_data(agg_y_true, agg_y_prob, n_bins=10)
            fig, ax = plt.subplots(figsize=(6, 6))
            ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
            ax.plot(agg_curve["bin_midpoints"], agg_curve["empirical_freq"],
                    "o-", color="tomato", label="Model (aggregate)")
            ax.set_xlabel("Mean predicted probability")
            ax.set_ylabel("Fraction of positives")
            ax.set_title("Calibration — Aggregate (all folds)")
            ax.legend()
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)

            agg_path = os.path.join(output_dir, "calibration_aggregate.png")
            fig.savefig(agg_path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            created_paths.append(agg_path)
        except Exception as exc:
            logger.warning("Aggregate calibration curve failed: %s", exc)

    return created_paths


# ---------------------------------------------------------------------------
# Public: generate_bankroll_curve
# ---------------------------------------------------------------------------

def generate_bankroll_curve(
    conn: sqlite3.Connection,
    model_version: str,
    output_dir: str,
) -> str:
    """
    Generate a bankroll evolution curve and save as bankroll_curve.png.

    Queries backtest_results ordered by tourney_date, id (chronological bet order).
    Plots bankroll_after over time with a reference line at the initial bankroll.

    Parameters
    ----------
    conn:
        Open SQLite connection with backtest_results populated.
    model_version:
        Model version string to filter results.
    output_dir:
        Directory to save the PNG. Created if it does not exist.

    Returns
    -------
    File path to the created bankroll_curve.png.
    """
    os.makedirs(output_dir, exist_ok=True)

    rows = conn.execute(
        """
        SELECT tourney_date, bankroll_after, bankroll_before
        FROM backtest_results
        WHERE model_version = ? AND kelly_bet > 0
        ORDER BY tourney_date, id
        """,
        (model_version,),
    ).fetchall()

    if not rows:
        # No bets placed — create an empty/placeholder chart
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set_title("Bankroll Evolution (no bets placed)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Bankroll ($)")
        path = os.path.join(output_dir, "bankroll_curve.png")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path

    dates = [r[0] for r in rows]
    bankrolls = [r[1] for r in rows]
    initial_bankroll = rows[0][2]  # bankroll_before of first bet

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(range(len(bankrolls)), bankrolls, color="steelblue",
            linewidth=1.5, label="Bankroll after each bet")
    ax.axhline(y=initial_bankroll, color="gray", linestyle="--",
               linewidth=1.0, label=f"Initial bankroll (${initial_bankroll:,.0f})")
    ax.set_xlabel("Bet sequence")
    ax.set_ylabel("Bankroll ($)")
    ax.set_title("Bankroll Evolution — Walk-Forward Backtest")
    ax.legend()
    ax.grid(True, alpha=0.3)

    path = os.path.join(output_dir, "bankroll_curve.png")
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)

    return path


# ---------------------------------------------------------------------------
# Public: print_summary
# ---------------------------------------------------------------------------

def print_summary(summary: dict, breakdowns: dict) -> None:
    """
    Print walk-forward summary stats and ROI breakdowns to stdout.

    Parameters
    ----------
    summary:
        Walk-forward summary dict from run_walk_forward.
    breakdowns:
        ROI breakdowns dict from compute_roi_breakdowns.
    """
    sep = "-" * 60
    print(sep)
    print("BACKTEST SUMMARY")
    print(sep)
    print(f"  Folds run:        {summary.get('folds_run', 0)}")
    print(f"  Total bets:       {summary.get('total_bets', 0)}")
    print(f"  Bets placed:      {summary.get('bets_placed', 0)}")
    print(f"  Bets skipped:     {summary.get('bets_skipped', 0)}")
    print(f"  Start bankroll:   ${summary.get('start_bankroll', 0):,.2f}")
    print(f"  Final bankroll:   ${summary.get('final_bankroll', 0):,.2f}")
    print(f"  Total P&L Kelly:  ${summary.get('total_pnl_kelly', 0):+,.2f}")
    print(f"  Total P&L Flat:   ${summary.get('total_pnl_flat', 0):+,.2f}")

    overall = breakdowns.get("overall", {})
    if overall:
        kelly_roi = overall.get("kelly_roi", 0.0)
        flat_roi = overall.get("flat_roi", 0.0)
        n_bets = overall.get("n_bets", 0)
        print(f"\nOVERALL ROI (n={n_bets} bets with kelly_bet > 0)")
        print(f"  Kelly ROI:  {kelly_roi:+.2%}")
        print(f"  Flat ROI:   {flat_roi:+.2%}")

    _print_dimension("BY SURFACE", breakdowns.get("by_surface", []))
    _print_dimension("BY TOURNEY LEVEL", breakdowns.get("by_tourney_level", []))
    _print_dimension("BY YEAR", breakdowns.get("by_year", []))
    _print_dimension("BY EV BUCKET", breakdowns.get("by_ev_bucket", []))
    _print_dimension("BY RANK TIER", breakdowns.get("by_rank_tier", []))


def _print_dimension(title: str, rows: list[dict]) -> None:
    """Print a single ROI breakdown dimension as a formatted table."""
    if not rows:
        return
    print(f"\n{title}")
    print(f"  {'Label':<16} {'N':>6}  {'Kelly ROI':>10}  {'Flat ROI':>10}  {'Flags'}")
    print(f"  {'-'*16} {'-'*6}  {'-'*10}  {'-'*10}  {'-'*12}")
    for row in rows:
        label = str(row.get("label", ""))
        n = row.get("n_bets", 0)
        k_roi = row.get("kelly_roi", 0.0)
        f_roi = row.get("flat_roi", 0.0)
        low_conf = row.get("low_confidence", False)
        flag = f"* (n={n})" if low_conf else ""
        print(f"  {label:<16} {n:>6}  {k_roi:>+10.2%}  {f_roi:>+10.2%}  {flag}")
