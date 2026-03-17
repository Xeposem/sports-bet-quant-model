---
phase: 04-backtesting-engine
plan: "02"
subsystem: backtesting
tags: [reporting, calibration, roi, cli, matplotlib, sqlite]
dependency_graph:
  requires: ["04-01"]
  provides: ["backtesting-reports", "calibration-plots", "bankroll-curve", "backtest-cli"]
  affects: ["05-api-layer", "06-dashboard"]
tech_stack:
  added: [matplotlib]
  patterns: [sql-group-by-roi, calibration-curve-plots, argparse-cli, insert-or-replace]
key_files:
  created:
    - src/backtest/reporting.py
    - src/backtest/runner.py
    - tests/test_backtest_reporting.py
  modified:
    - .gitignore
decisions:
  - "kelly_bet > 0 filter for ROI: only bets actually placed count toward ROI denominator (zero-stake decisions excluded)"
  - "matplotlib.use('Agg') at module import: prevents display errors in headless environments before any pyplot import"
  - "Rank tier uses bet-on player's rank: outcome=1 maps to winner_rank, outcome=0 maps to loser_rank for correct tier assignment"
  - "EV buckets use >= thresholds (not >): >10% means ev >= 0.10, consistent with standard bet analytics"
  - "store_calibration_data uses INSERT OR REPLACE: re-running pipeline overwrites stale calibration rows idempotently"
metrics:
  duration_minutes: 25
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
  tests_added: 15
  tests_total: 320
---

# Phase 4 Plan 2: Backtesting Reporting, Calibration Plots, and CLI Runner Summary

**One-liner:** ROI breakdown reporting across 5 dimensions (surface, tourney_level, year, ev_bucket, rank_tier) with per-fold + aggregate calibration PNGs and a single idempotent CLI runner entry point.

## What Was Built

### src/backtest/reporting.py

Core reporting module with five public functions:

**`compute_roi_breakdowns(conn, model_version)`** — Queries `backtest_results` via SQL GROUP BY for six dimensions and returns structured dict:
- `by_surface`, `by_tourney_level`, `by_year`, `by_ev_bucket`, `by_rank_tier`, `overall`
- Each row includes: `label`, `n_bets`, `kelly_roi`, `flat_roi`, `total_pnl_kelly`, `total_pnl_flat`, `low_confidence`
- `low_confidence=True` when `n_bets < 30`
- Kelly ROI = `SUM(pnl_kelly) / SUM(kelly_bet)` for rows where `kelly_bet > 0`
- EV buckets: `>=10%`, `>=5%`, `>=2%`, else `>0%` using SQL CASE expression
- Rank tiers: `top10` (<=10), `top50` (11–50), `top100` (51–100), `outside100` using bet-on player's rank

**`store_calibration_data(conn, y_true, y_prob, fold_label, model_version)`** — Calls `calibration_curve_data` from `src/model/metrics.py`, stores JSON arrays as `bin_midpoints` and `empirical_freq` in `calibration_data` table via `INSERT OR REPLACE`.

**`generate_calibration_plots(conn, model_version, output_dir)`** — Iterates over fold years, generates per-fold calibration PNG with diagonal reference line, plus aggregate calibration PNG. Calls `plt.close(fig)` after each save to prevent memory leaks. Returns list of created file paths.

**`generate_bankroll_curve(conn, model_version, output_dir)`** — Queries bets ordered by `tourney_date, id`, plots `bankroll_after` as a line with initial bankroll reference line. Saves as `bankroll_curve.png`. Returns file path.

**`print_summary(summary, breakdowns)`** — Formatted stdout output with folds/bets/bankroll stats plus per-dimension ROI tables. Flags low-confidence buckets with `*` and `(n=XX)` annotation.

### src/backtest/runner.py

CLI entry point: `python -m src.backtest.runner` with argparse.

Configuration flags: `--db`, `--kelly-fraction`, `--max-fraction`, `--min-ev`, `--bankroll`, `--min-train`, `--output-dir`, `--model-version`.

Pipeline sequence:
1. `run_walk_forward(conn, config)` — generate backtest_results
2. `compute_roi_breakdowns(conn, model_version)` — analysis
3. `generate_calibration_plots(conn, model_version, output_dir)` — per-fold + aggregate PNGs
4. `store_calibration_data` — per-fold and aggregate to SQLite
5. `generate_bankroll_curve(conn, model_version, output_dir)` — bankroll PNG
6. `print_summary(summary, breakdowns)` — stdout display
7. Print generated plot paths

Fully idempotent: INSERT OR REPLACE for backtest_results (from walk_forward), INSERT OR REPLACE for calibration_data, plots overwrite on re-run.

### .gitignore

Added `output/backtest/` to exclude generated PNG artifacts from version control.

## Tests

15 tests in `tests/test_backtest_reporting.py`:

| Test | What it verifies |
|------|-----------------|
| `test_roi_by_surface` | Surface breakdown: correct kelly_roi, flat_roi, n_bets per surface |
| `test_roi_by_tourney_level` | Tourney level breakdown with correct groupings |
| `test_roi_by_ev_bucket` | EV threshold buckets >0%, >2%, >5%, >10% computed correctly |
| `test_roi_by_year` | Year-over-year trend breakdown |
| `test_roi_by_rank_tier` | Rank tiers: top10, top50, top100, outside100 |
| `test_thin_bucket_flag` | Buckets < 30 samples have `low_confidence=True` |
| `test_flat_vs_kelly_roi` | Both ROI types present in every dimension row |
| `test_calibration_store` | JSON bin_midpoints/empirical_freq written to calibration_data |
| `test_calibration_store_idempotent` | Second write with same fold_label overwrites (INSERT OR REPLACE) |
| `test_calibration_png_created` | Per-fold + aggregate PNGs created in output dir |
| `test_bankroll_curve_png` | bankroll_curve.png created from chronological bet sequence |
| `test_overall_roi` | Overall ROI dict includes correct aggregated values |
| `test_print_summary` | Print output contains bankroll/ROI info and flags low-confidence buckets |
| `test_runner_main_help` | `--help` exits cleanly with code 0 |
| `test_runner_calls_pipeline_in_sequence` | Mock-based: run_walk_forward, compute_roi_breakdowns, generate_calibration_plots all called |

## Decisions Made

1. **`kelly_bet > 0` filter for ROI:** Only bets actually placed count toward the ROI denominator. Zero-stake decisions (below min_ev threshold) are logged but excluded from ROI metrics — prevents artificially diluting ROI by counting non-bets as zero-return bets.

2. **`matplotlib.use("Agg")` at module import:** Called before any `pyplot` import to ensure the non-interactive backend is set in headless environments (CI, server). This is a module-level side effect per matplotlib documentation.

3. **Rank tier uses bet-on player's rank:** `outcome=1` maps to `winner_rank`, `outcome=0` maps to `loser_rank`. This correctly attributes the tier to the player the model decided to bet on, not always the match winner.

4. **EV bucket thresholds use `>=`:** `>10%` means `ev >= 0.10`. Using `>=` in the CASE expression matches standard analytics conventions and avoids edge-case off-by-one issues at exact threshold values.

5. **`INSERT OR REPLACE` for calibration_data idempotency:** Re-running the CLI overwrites stale calibration rows. Consistent with the `UNIQUE (fold_label, model_version)` constraint in schema.sql.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files Exist
- `src/backtest/reporting.py` — FOUND
- `src/backtest/runner.py` — FOUND
- `tests/test_backtest_reporting.py` — FOUND

### Commits Exist
- `97899e7` test(04-02): RED tests — FOUND
- `1c60d93` feat(04-02): reporting module — FOUND
- `7d9b33f` feat(04-02): CLI runner + gitignore + runner tests — FOUND

## Self-Check: PASSED
