"""
Backtesting CLI entry point.

Usage: python -m src.backtest.runner [OPTIONS]

Options:
  --db PATH            Database path (default: data/tennis.db)
  --kelly-fraction F   Kelly fraction (default: 0.25)
  --max-fraction F     Max bet as fraction of bankroll (default: 0.03)
  --min-ev F           Minimum EV threshold to place bet (default: 0.0)
  --bankroll F         Starting bankroll (default: 1000.0)
  --min-train N        Minimum training matches per fold (default: 500)
  --output-dir PATH    Output directory for plots (default: output/backtest)
  --model-version STR  Model version string (default: logistic_v1)

The runner is idempotent — re-running overwrites backtest_results via
INSERT OR REPLACE and regenerates plots.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from src.db.connection import get_connection
from src.backtest.walk_forward import run_walk_forward
from src.backtest.reporting import (
    compute_roi_breakdowns,
    generate_calibration_plots,
    generate_bankroll_curve,
    store_calibration_data,
    print_summary,
)


logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the backtesting CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m src.backtest.runner",
        description="Run the walk-forward backtesting pipeline and generate reports.",
    )
    parser.add_argument(
        "--db",
        default="data/tennis.db",
        metavar="PATH",
        help="Database path (default: data/tennis.db)",
    )
    parser.add_argument(
        "--kelly-fraction",
        type=float,
        default=0.25,
        metavar="F",
        help="Kelly fraction for bet sizing (default: 0.25)",
    )
    parser.add_argument(
        "--max-fraction",
        type=float,
        default=0.03,
        metavar="F",
        help="Maximum bet as fraction of bankroll (default: 0.03)",
    )
    parser.add_argument(
        "--min-ev",
        type=float,
        default=0.0,
        metavar="F",
        help="Minimum EV threshold to place a bet (default: 0.0)",
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=1000.0,
        metavar="F",
        help="Starting bankroll (default: 1000.0)",
    )
    parser.add_argument(
        "--min-train",
        type=int,
        default=500,
        metavar="N",
        help="Minimum training matches per fold (default: 500)",
    )
    parser.add_argument(
        "--output-dir",
        default="output/backtest",
        metavar="PATH",
        help="Output directory for plots (default: output/backtest)",
    )
    parser.add_argument(
        "--model-version",
        default="logistic_v1",
        metavar="STR",
        help="Model version string (default: logistic_v1)",
    )
    parser.add_argument(
        "--clv-threshold",
        type=float,
        default=0.03,
        metavar="F",
        help="CLV threshold: minimum model_prob - pinnacle_prob to place bet (default: 0.03, per D-04)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        default=False,
        help="Run CLV threshold sweep across [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    """
    CLI entry point: run the full backtesting pipeline.

    Parameters
    ----------
    argv:
        Optional argument list. Uses sys.argv[1:] when None.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Open database connection
    conn = get_connection(args.db)

    try:
        config = {
            "kelly_fraction": args.kelly_fraction,
            "max_fraction": args.max_fraction,
            "min_ev": args.min_ev,
            "initial_bankroll": args.bankroll,
            "min_train_matches": args.min_train,
            "model_version": args.model_version,
            "clv_threshold": args.clv_threshold,
        }

        # Optional CLV sweep: run at multiple thresholds then fall through to regular backtest
        if args.sweep:
            from src.backtest.walk_forward import run_clv_sweep
            logger.info("Running CLV threshold sweep")
            sweep_results = run_clv_sweep(conn, config)
            print("\nCLV Threshold Sweep Results:")
            print(f"{'Threshold':>10} | {'Bets':>6} | {'ROI':>8} | {'Sharpe':>8} | {'Max DD':>8}")
            print("-" * 50)
            for r in sweep_results:
                print(
                    f"{r['clv_threshold']:>10.2f} | {r['bets_placed']:>6d} | "
                    f"{r['roi']:>7.2%} | {r['sharpe']:>8.4f} | {r['max_drawdown']:>7.2%}"
                )
            logger.info(
                "Sweep complete. Running regular backtest at clv_threshold=%.2f",
                args.clv_threshold,
            )

        # Step 1: Run walk-forward backtesting (at configured clv_threshold, overwrites DB results)
        logger.info("Starting walk-forward backtest (db=%s)", args.db)
        summary = run_walk_forward(conn, config)

        # Step 2: Compute ROI breakdowns
        logger.info("Computing ROI breakdowns")
        breakdowns = compute_roi_breakdowns(conn, model_version=args.model_version)

        # Step 3: Generate per-fold and aggregate calibration plots
        logger.info("Generating calibration plots -> %s", args.output_dir)
        calibration_paths = generate_calibration_plots(
            conn, args.model_version, args.output_dir
        )

        # Step 4: Store calibration data in SQLite for each fold + aggregate
        import numpy as np

        fold_years = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT fold_year FROM backtest_results "
                "WHERE model_version = ? ORDER BY fold_year",
                (args.model_version,),
            ).fetchall()
        ]
        for fold_year in fold_years:
            rows = conn.execute(
                "SELECT outcome, calibrated_prob FROM backtest_results "
                "WHERE model_version = ? AND fold_year = ?",
                (args.model_version, fold_year),
            ).fetchall()
            if len(rows) >= 2:
                y_true = np.array([r[0] for r in rows], dtype=float)
                y_prob = np.array([r[1] for r in rows], dtype=float)
                try:
                    store_calibration_data(
                        conn, y_true, y_prob,
                        fold_label=str(fold_year),
                        model_version=args.model_version,
                    )
                except Exception as exc:
                    logger.warning("Fold %s calibration store failed: %s", fold_year, exc)

        # Aggregate calibration
        all_rows = conn.execute(
            "SELECT outcome, calibrated_prob FROM backtest_results "
            "WHERE model_version = ?",
            (args.model_version,),
        ).fetchall()
        if len(all_rows) >= 2:
            y_true_all = np.array([r[0] for r in all_rows], dtype=float)
            y_prob_all = np.array([r[1] for r in all_rows], dtype=float)
            try:
                store_calibration_data(
                    conn, y_true_all, y_prob_all,
                    fold_label="aggregate",
                    model_version=args.model_version,
                )
            except Exception as exc:
                logger.warning("Aggregate calibration store failed: %s", exc)

        # Step 5: Generate bankroll curve
        logger.info("Generating bankroll curve -> %s", args.output_dir)
        bankroll_path = generate_bankroll_curve(
            conn, args.model_version, args.output_dir
        )

        # Step 6: Print summary to stdout
        print_summary(summary, breakdowns)

        # Step 7: Print plot paths
        if calibration_paths:
            print("\nGenerated calibration plots:")
            for p in calibration_paths:
                print(f"  {p}")
        if bankroll_path:
            print(f"\nBankroll curve: {bankroll_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
