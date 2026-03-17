---
phase: 04-backtesting-engine
plan: 01
subsystem: backtesting
tags: [kelly, walk-forward, backtesting, schema, tdd]
dependency_graph:
  requires:
    - src/model/trainer.py
    - src/model/predictor.py
    - src/db/schema.sql
  provides:
    - src/backtest/kelly.py
    - src/backtest/walk_forward.py
    - backtest_results table
    - calibration_data table
  affects:
    - tests/test_loader.py (table count updated 12 -> 14)
tech_stack:
  added: []
  patterns:
    - fractional Kelly with cap enforcement and min_ev threshold
    - expanding-window walk-forward fold generation by calendar year
    - look-ahead bias prevention via tourney_date < train_end boundary
    - pairwise differential feature vectors (same convention as trainer.py)
    - per-fold train_and_calibrate with time-decay weights
key_files:
  created:
    - src/backtest/__init__.py
    - src/backtest/kelly.py
    - src/backtest/walk_forward.py
    - tests/test_backtest.py
  modified:
    - src/db/schema.sql (added backtest_results and calibration_data tables)
    - tests/test_loader.py (table count assertion updated to 14)
decisions:
  - "Year-based folds (train_end=Jan 1 of test year) — simple, interpretable boundaries for annual performance analysis"
  - "Both winner and loser sides processed per match — model bets on whichever side has positive EV, log all decisions for audit"
  - "No-odds matches logged with kelly_bet=0 for full match coverage in backtest_results"
  - "Flat bet always $1 for parallel ROI comparison against Kelly strategy"
  - "assert_no_look_ahead enforced in run_fold as runtime safety guard"
metrics:
  duration: "5 minutes"
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
  tests_added: 21
---

# Phase 4 Plan 1: Walk-Forward Backtesting Core Summary

**One-liner:** Fractional Kelly bet sizing with cap enforcement plus year-based expanding-window walk-forward fold engine with look-ahead bias prevention, writing results to backtest_results table.

## What Was Built

### Schema Additions (src/db/schema.sql)

Added two new tables after the `predictions` table:

- **backtest_results**: Per-match, per-fold backtesting output with Kelly sizing. Columns: fold_year, calibrated_prob, ev, kelly_full, kelly_bet, pnl_kelly, pnl_flat, bankroll_before/after. Unique constraint on (tourney_id, match_num, tour, player_id, model_version). Two indexes added for dashboard queries.
- **calibration_data**: Per-fold calibration curve storage for Phase 4 Plan 2 reporting.

### Kelly Bet Sizing (src/backtest/kelly.py)

`compute_kelly_bet(prob, decimal_odds, bankroll, kelly_fraction=0.25, max_fraction=0.03, min_ev=0.0)`:
1. EV check: skip if EV < min_ev
2. Full Kelly = (b*p - q) / b
3. Fractional Kelly = full_kelly * kelly_fraction
4. Cap = min(fractional * bankroll, max_fraction * bankroll)

`apply_bet_result(bankroll, bet_size, decimal_odds, won)`: Won: +profit, Lost: -stake.

### Walk-Forward Engine (src/backtest/walk_forward.py)

- `generate_folds`: Queries distinct years from match_features, generates (train_end, test_start, test_end) tuples. test_start == train_end for each fold. Skips folds below min_train_matches threshold.
- `build_fold_training_matrix`: Exact copy of trainer._BUILD_MATRIX_SQL with `AND m.tourney_date < :train_end` added before ORDER BY.
- `build_fold_test_matches`: LEFT JOIN with match_odds to detect odds availability; returns feature vectors and odds per match.
- `assert_no_look_ahead`: Raises AssertionError on any date overlap between train and test sets.
- `run_fold`: Full fold loop — build matrix, time weights, temporal split, train_and_calibrate, predict, Kelly size, bankroll update.
- `run_walk_forward`: Orchestrates all folds, carries bankroll forward, stores results via INSERT OR REPLACE.

## Test Coverage (tests/test_backtest.py — 21 tests)

| Group | Tests |
|-------|-------|
| Kelly bet sizing | 6 tests: positive/negative EV, fraction calc, cap, min_ev threshold |
| apply_bet_result | 2 tests: win/loss pnl |
| Schema | 3 tests: backtest_results columns, calibration_data columns, table count |
| generate_folds | 2 tests: chronological order + test_start==train_end, min_train_matches skip |
| build_fold_training_matrix | 3 tests: date boundary, look-ahead raises, clean passes |
| run_fold | 2 tests: results structure, no-odds matches get kelly_bet=0 |
| run_walk_forward | 2 tests: summary keys, results stored in DB |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All files exist:
- src/backtest/kelly.py: FOUND
- src/backtest/walk_forward.py: FOUND
- src/backtest/__init__.py: FOUND
- tests/test_backtest.py: FOUND

All commits exist:
- 6b30d5e: test(04-01): add failing tests for Kelly bet sizing and backtest schema
- 949cc56: feat(04-01): schema migrations + Kelly module
- 7d623e5: feat(04-01): walk-forward engine implementation
