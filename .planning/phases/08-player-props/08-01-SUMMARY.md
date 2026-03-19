---
phase: 08-player-props
plan: 01
subsystem: props
tags: [glm, poisson, negative-binomial, statsmodels, prop-predictions, score-parser]
dependency_graph:
  requires:
    - src/db/schema.sql (prop_lines table already present)
    - src/db/connection.py (get_connection, init_db)
    - src/model/base.py (persistence pattern reference)
  provides:
    - src/props/PROP_REGISTRY (aces, double_faults, games_won train/predict callables)
    - src/props/base.py (compute_pmf, p_over, save_prop_model, load_prop_model, predict_and_store)
    - src/props/score_parser.py (parse_score)
    - src/db/schema.sql (prop_predictions table + index)
    - CLI: python -m src.props train|predict
  affects:
    - Phase 08 Plan 02 (FastAPI props endpoints — will consume PROP_REGISTRY and prop_predictions table)
    - Phase 09 (paper trading signals — will use predict_and_store pipeline)
tech_stack:
  added:
    - statsmodels>=0.14 (Poisson GLM, NegBin GLM via smf.glm and sm.families)
    - scipy.stats.poisson / scipy.stats.nbinom (PMF computation)
  patterns:
    - Registry pattern: PROP_REGISTRY mirrors MODEL_REGISTRY from src/model/__init__.py
    - Joblib serialization for trained model dicts (mirrors src/model/base.py save_model)
    - Poisson/NegBin AIC selection: choose NegBin if nb_aic < poisson_aic - 2
key_files:
  created:
    - src/props/__init__.py
    - src/props/base.py
    - src/props/score_parser.py
    - src/props/aces.py
    - src/props/double_faults.py
    - src/props/games_won.py
    - src/props/__main__.py
    - tests/test_props.py
  modified:
    - src/db/schema.sql (prop_predictions table added)
    - requirements.txt (statsmodels>=0.14 added)
decisions:
  - "statsmodels GLM NegBin: scale attribute holds the alpha dispersion parameter for compute_pmf"
  - "max_k = max(50, int(mu * 6)) for NegBin tail coverage — mu*4 was insufficient for mu=20 alpha=0.5"
  - "match_stats uses player_role not player_id — training queries join through matches to get winner_id/loser_id"
  - "predict_and_store imports PROP_REGISTRY at function level to avoid circular import"
  - "games_won._build_training_df filters retirements via parse_score() returning None"
  - "Python 3.9 compatible Optional[Tuple] type hints — tuple|None PEP 604 syntax not supported on 3.9"
metrics:
  duration_seconds: 572
  completed_date: "2026-03-19"
  tasks_completed: 3
  files_created: 8
  files_modified: 2
---

# Phase 08 Plan 01: Prop Prediction Model Layer Summary

**One-liner:** Poisson/NegBin GLM prop prediction models for aces, double faults, and games won with PROP_REGISTRY, score parser, PMF utilities, and CLI train/predict pipeline.

## What Was Built

The complete `src/props/` package providing:

1. **Score parser** (`score_parser.py`): Handles all Sackmann score formats including tiebreaks (7-6(5)), retirements (RET), walkovers (W/O), defaults (DEF), and empty inputs.

2. **Base utilities** (`base.py`): `compute_pmf()` generates Poisson or NegBin PMF arrays; `p_over()` computes P(X > threshold); `save_prop_model`/`load_prop_model` use joblib for serialization; `predict_and_store()` is the batch prediction pipeline.

3. **Three GLM models** (aces, double_faults, games_won): Each fits Poisson and NegBin GLMs via statsmodels, selects by AIC, and returns `{model, family, alpha, aic}`. Feature formula: `count ~ avg_rate + opp_rtn_pct + surface_clay + surface_grass + level_G + level_M`.

4. **PROP_REGISTRY** (`__init__.py`): Maps stat_type strings to `{train, predict}` dicts, mirroring MODEL_REGISTRY pattern.

5. **CLI** (`__main__.py`): `python -m src.props train [--stat-type] [--db-path]` and `python -m src.props predict [--stat-type] [--db-path] [--date-from] [--date-to]`.

6. **Schema** (`schema.sql`): `prop_predictions` table with UNIQUE constraint on (tour, player_id, stat_type, match_date) and date index.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 incompatible type hint syntax**
- **Found during:** Task 1 test run
- **Issue:** `def parse_score(score: str) -> tuple | None:` uses PEP 604 union syntax which fails on Python 3.9
- **Fix:** Added `from __future__ import annotations` and `from typing import Optional, Tuple`; changed to `Optional[Tuple[int, int]]`
- **Files modified:** `src/props/score_parser.py`, `src/props/base.py`
- **Commit:** 9ec6049

**2. [Rule 1 - Bug] NegBin PMF sum test tolerance too tight**
- **Found during:** Task 1 test run
- **Issue:** `compute_pmf(mu=20.0, family="negative_binomial", alpha=0.5)` had sum = 0.9963 because `max_k = max(50, int(20*4)) = 80` is insufficient for the heavy NegBin tail
- **Fix:** Increased multiplier from 4 to 6: `max_k = max(50, int(mu * 6))`
- **Files modified:** `src/props/base.py`
- **Commit:** 9ec6049

**3. [Rule 1 - Bug] Test accessed wrong column name**
- **Found during:** Task 2 test run
- **Issue:** `test_games_won_uses_score_parser` accessed `row["games"]` but the DataFrame column is named `games_won`
- **Fix:** Updated test to use `row["games_won"]`
- **Files modified:** `tests/test_props.py`
- **Commit:** d4f6a1e

**4. [Rule 2 - Missing Critical Functionality] predict_and_store test isolation**
- **Found during:** Task 3 test design
- **Issue:** `test_predict_and_store_no_model` would spuriously pass if a model was already saved by a previous test run (the original logic `result["predicted"] == 0 or isinstance(result, dict)` always passes)
- **Fix:** Used `monkeypatch` and `tmp_path` to point PROP_MODEL_DIR at an empty temp directory for proper isolation
- **Files modified:** `tests/test_props.py`
- **Commit:** 1f13d0f

## Test Coverage

20 tests, all passing:
- 7 score_parser tests (standard, tiebreak, 3-set, RET, W/O, DEF, empty/None)
- 3 compute_pmf tests (Poisson sum, NegBin sum, length >= 50)
- 3 p_over tests (fractional threshold, integer threshold, beyond PMF range)
- 1 PROP_REGISTRY test (keys + callable check)
- 3 Task 2 model tests (aces train/predict, games_won score filtering, schema)
- 3 Task 3 pipeline tests (predict_and_store, no-model graceful, CLI help)

## Self-Check: PASSED

All 8 created files confirmed on disk. All 3 task commits confirmed in git log (9ec6049, d4f6a1e, 1f13d0f). All 20 tests pass.
