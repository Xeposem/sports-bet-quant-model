---
phase: 03-baseline-model-ev-framework
plan: "03"
subsystem: model-prediction
tags: [prediction, ev, expected-value, cli, logistic-regression, calibration]
dependency_graph:
  requires:
    - 03-01  # odds ingestion pipeline (devig, ingester, match_odds table)
    - 03-02  # logistic regression training (trainer, metrics, calibrated model)
  provides:
    - predictor.py: EV calculation and batch prediction storage
    - cli.py: CLI for manual odds entry, CSV import, train, predict
  affects:
    - predictions table: populated with model_prob, calibrated_prob, ev_value, edge
tech_stack:
  added:
    - argparse: CLI argument parsing
  patterns:
    - TDD red-green: failing tests first, then implementation
    - compute_ev formula: (calibrated_prob * decimal_odds) - 1.0
    - INSERT OR REPLACE: idempotent prediction storage
    - patchable get_db_path: TENNIS_DB env var override for testing
key_files:
  created:
    - src/model/predictor.py
    - src/odds/cli.py
  modified:
    - tests/test_model.py
    - tests/test_odds.py
decisions:
  - "predict_match returns both players in [winner_pred, loser_pred] order — winner gets outcome=1 for brier/log-loss, loser gets outcome=0"
  - "get_db_path() in cli.py is patchable (not inlined) to support test isolation without real DB"
  - "CLI predict subcommand checks os.path.exists before calling load_model to provide clear error messages"
  - "Model path includes UTC timestamp in filename (logistic_v1_YYYYMMDD_HHMMSS.joblib) to avoid overwriting previous artifacts"
  - "Per-sample log-loss: -log(p) for outcome=1, -log(1-p) for outcome=0, with 1e-15 epsilon clip"
metrics:
  duration: ~20 minutes
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
  tests_added: 28
  tests_total: 284
---

# Phase 03 Plan 03: Prediction Engine and EV Framework Summary

**One-liner:** EV calculation engine `(calibrated_prob * decimal_odds) - 1` with batch prediction storage and argparse CLI for manual odds entry, CSV import, model training, and prediction.

## What Was Built

### Task 1: Predictor Module (`src/model/predictor.py`)

The prediction engine combines calibrated model output with bookmaker odds:

- `compute_ev(calibrated_prob, decimal_odds)` — formula: `(calibrated_prob * decimal_odds) - 1.0`
- `predict_match(model, conn, tourney_id, match_num)` — generates predictions for both players:
  - Joins `match_features` (winner/loser) to compute the same differential feature vector used in training
  - Calls `model.predict_proba` to get P(winner wins); P(loser wins) = 1 - P(winner wins)
  - Queries `match_odds` for Pinnacle odds; if present, calls `power_method_devig` for market probs, then computes EV and edge for both sides
  - Computes brier_contribution and log_loss_contribution (outcome is always known for stored matches)
  - Returns two dicts matching the `predictions` table schema
- `store_prediction(conn, pred)` — `INSERT OR REPLACE` for idempotent re-runs
- `predict_all_matches(model, conn, model_version)` — batch: queries all matches with feature rows, runs `predict_match`, stores results, returns `{matches_predicted, predictions_stored, with_ev}`

### Task 2: CLI (`src/odds/cli.py`)

Four subcommands via argparse:

| Command | What it does |
|---------|-------------|
| `enter` | Validates odds >= 1.01, calls `manual_entry()`, prints confirmation |
| `import-csv` | Calls `import_csv_odds()`, prints imported/unlinked/skipped stats |
| `train` | Runs full training pipeline, saves timestamped .joblib + _metrics.json |
| `predict` | Loads model, calls `predict_all_matches()`, prints stats |

The `get_db_path()` function reads from `TENNIS_DB` env var (default: `data/tennis.db`) and is designed for test isolation via patching.

## Test Coverage

| File | Tests Added | Total |
|------|-------------|-------|
| tests/test_model.py | 17 (predictor) | 52 |
| tests/test_odds.py | 11 (CLI) | 32 |

Full suite: **284 tests, 0 failures**.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `19fdbaa` | test | RED: failing predictor tests (compute_ev, predict_match, store/predict_all) |
| `35e9252` | feat | GREEN: predictor module implementation |
| `a79c816` | test | RED: failing CLI tests (enter, import-csv, train, predict) |
| `a3a3e26` | feat | GREEN: CLI module implementation |

## Deviations from Plan

None — plan executed exactly as written. One minor test fix applied inline (Rule 1): the `test_predict_calls_predict_all_matches` test needed to create a placeholder `.joblib` file so the CLI's path-exists check would pass before the mocked `load_model` was called. No behavior change to production code.

## Self-Check

Files created:
- `src/model/predictor.py` — FOUND
- `src/odds/cli.py` — FOUND
- `tests/test_model.py` (modified) — FOUND
- `tests/test_odds.py` (modified) — FOUND

Commits:
- `19fdbaa` — FOUND
- `35e9252` — FOUND
- `a79c816` — FOUND
- `a3a3e26` — FOUND

Test suite: 284 passed, 0 failed.

## Self-Check: PASSED
