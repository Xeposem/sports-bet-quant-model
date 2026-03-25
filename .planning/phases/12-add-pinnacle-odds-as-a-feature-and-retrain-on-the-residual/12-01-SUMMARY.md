---
phase: 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual
plan: "01"
subsystem: features/schema
tags: [pinnacle, devig, match-features, schema-migration, tdd]
dependency_graph:
  requires:
    - src/odds/devig.py (power_method_devig)
    - src/db/schema.sql (match_features table)
    - src/features/builder.py (build_feature_row)
  provides:
    - pinnacle_prob_winner, pinnacle_prob_loser, has_no_pinnacle in match_features
    - _get_pinnacle_prob helper in builder.py
  affects:
    - Any downstream consumer of match_features (model training, feature matrix)
tech_stack:
  added: []
  patterns:
    - Power method devigging via scipy.optimize.brentq
    - Graceful fallback (None/None/1) for missing or invalid odds
    - INSERT OR REPLACE idempotent feature row persistence
key_files:
  created: []
  modified:
    - src/db/schema.sql
    - src/features/builder.py
    - tests/test_builder.py
decisions:
  - "_get_pinnacle_prob uses function-level import of power_method_devig to match existing lazy import pattern in builder.py"
  - "Graceful fallback (None, None, 1) for both missing odds and invalid odds (ValueError) — consistent with has_no_elo pattern"
  - "EXPECTED_FEATURE_KEYS in test_builder.py updated to include three new pinnacle keys — test_all_expected_keys_present now asserts full schema coverage"
metrics:
  duration: "~8 minutes"
  completed: "2026-03-25"
  tasks_completed: 1
  files_modified: 3
---

# Phase 12 Plan 01: Pinnacle Prob Schema + Feature Builder Summary

**One-liner:** Pinnacle devigged win probabilities (via power method) added to match_features schema and populated by _get_pinnacle_prob helper in builder.py, with None/None/1 fallback for missing or invalid odds.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Schema migration and _get_pinnacle_prob helper with tests | 137907e | src/db/schema.sql, src/features/builder.py, tests/test_builder.py |

## What Was Built

### Schema Changes (src/db/schema.sql)
Three new nullable columns added to `match_features` after `sentiment_score`:
- `pinnacle_prob_winner REAL` — devigged Pinnacle win probability for the winner
- `pinnacle_prob_loser REAL` — devigged Pinnacle win probability for the loser
- `has_no_pinnacle INTEGER` — 1 when no Pinnacle odds exist, 0 when they do

### New Helper (src/features/builder.py)
`_get_pinnacle_prob(conn, tourney_id, match_num, tour="ATP") -> dict`:
- Queries `match_odds` for `bookmaker='pinnacle'`
- Calls `power_method_devig(decimal_odds_a, decimal_odds_b)` to devig odds
- Returns `{"pinnacle_prob_winner": p_a, "pinnacle_prob_loser": p_b, "has_no_pinnacle": 0}` when odds exist
- Returns `{"pinnacle_prob_winner": None, "pinnacle_prob_loser": None, "has_no_pinnacle": 1}` when no odds or invalid odds (ValueError caught)

### Extended build_feature_row
Calls `_get_pinnacle_prob` after sentiment and includes all three keys in the returned dict.

### Extended _insert_feature_row
INSERT OR REPLACE now persists `pinnacle_prob_winner`, `pinnacle_prob_loser`, `has_no_pinnacle`.

### Tests (tests/test_builder.py)
Five new tests in `TestGetPinnacleProb` class:
1. `test_get_pinnacle_prob_with_odds` — devigged probs correct for (1.90, 2.05) input
2. `test_get_pinnacle_prob_no_odds` — returns `None/None/1` when no match_odds row
3. `test_get_pinnacle_prob_invalid_odds` — ValueError from invalid odds (0.5) caught, returns fallback
4. `test_match_features_schema_pinnacle_columns` — PRAGMA confirms all 3 new columns exist
5. `test_feature_row_has_pinnacle_keys` — `build_feature_row` returns correct pinnacle keys for both with-odds and without-odds cases

EXPECTED_FEATURE_KEYS set updated to include the three new pinnacle keys.

## Verification

```
pytest tests/test_builder.py -k pinnacle -x -q  → 5 passed
pytest tests/test_builder.py -x -q             → 21 passed (all existing + new)
Schema OK (confirmed via PRAGMA table_info)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all three pinnacle columns are fully wired from match_odds through _get_pinnacle_prob to match_features INSERT OR REPLACE.

## Self-Check: PASSED

- src/db/schema.sql contains "pinnacle_prob_winner": CONFIRMED
- src/db/schema.sql contains "pinnacle_prob_loser": CONFIRMED
- src/db/schema.sql contains "has_no_pinnacle": CONFIRMED
- src/features/builder.py contains "_get_pinnacle_prob": CONFIRMED
- src/features/builder.py contains "power_method_devig": CONFIRMED
- src/features/builder.py _insert_feature_row contains all 3 new columns: CONFIRMED
- tests/test_builder.py contains all 5 new test functions: CONFIRMED
- Commits exist: cbbafbb (RED tests), 137907e (GREEN implementation)
