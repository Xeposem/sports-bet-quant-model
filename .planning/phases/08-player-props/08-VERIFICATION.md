---
phase: 08-player-props
verified: 2026-03-19T00:00:00Z
status: human_needed
score: 3/3 must-haves verified
human_verification:
  - test: "Navigate to Props tab in running dashboard, submit a prop line, observe PMF chart"
    expected: "PMF bar chart renders with green/slate colored bars and amber dashed threshold line. Value badge shows correct color coding. KPI cards show hit rate metrics."
    why_human: "Visual appearance, chart rendering, and form interaction cannot be verified programmatically"
  - test: "Resize browser to mobile width while Props tab is active"
    expected: "Form fields stack vertically in single column. KPI cards wrap without overflow."
    why_human: "Responsive layout requires visual inspection in a browser"
  - test: "Enter an invalid player name and submit prop line"
    expected: "Toast error: 'Player not found. Try a more complete name...'"
    why_human: "Error toast behavior requires running backend + frontend interaction"
---

# Phase 8: Player Props Verification Report

**Phase Goal:** The system predicts player stat distributions for PrizePicks props, users can enter prop lines manually, and the system identifies value bets by comparing predictions to entered lines.
**Verified:** 2026-03-19
**Status:** human_needed (all automated checks passed; visual/interaction verification pending)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | System produces a predicted distribution (mean and CI) for aces, games won, and double faults per player per match | VERIFIED | `src/props/aces.py`, `double_faults.py`, `games_won.py` train Poisson/NegBin GLMs via statsmodels and return `{"pmf": [...], "mu": float, "model_version": str}`; `predict_and_store()` in `base.py` runs batch prediction and writes to `prop_predictions` table |
| 2 | User can enter a PrizePicks prop line and see whether the model prediction shows value | VERIFIED | POST /props stores line via `src/api/routers/props.py`; GET /props returns `PropPredictionRow` with `p_hit` computed from stored PMF; `PropsTab.tsx` renders inline entry form + value badges (Value/Marginal/No Value); `useSubmitPropLine` does POST then refetches GET /props to display PMF chart |
| 3 | Dashboard displays prop prediction accuracy tracked over time as directional validation | VERIFIED | GET /props/accuracy returns `overall_hit_rate`, `hit_rate_by_stat`, `rolling_30d`, `calibration_bins`; `PropsTab.tsx` renders 5 KPI cards, `RollingHitRateChart` component, and reuses `CalibrationChart` for prop calibration scatter |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/props/__init__.py` | PROP_REGISTRY with aces, games_won, double_faults | VERIFIED | Contains `PROP_REGISTRY = {"aces": ..., "double_faults": ..., "games_won": ...}` with train/predict callables; confirmed importable: prints `['aces', 'double_faults', 'games_won']` |
| `src/props/base.py` | compute_pmf, p_over, save/load, predict_and_store | VERIFIED | All 5 functions present and substantive; `compute_pmf` handles both Poisson and NegBin; `p_over` sums PMF strictly above threshold; `predict_and_store` executes full batch pipeline with INSERT OR REPLACE |
| `src/props/score_parser.py` | parse_score() | VERIFIED | Handles standard scores, tiebreaks (7-6(5)), RET, W/O, DEF, empty/None; uses regex `(\d+)-(\d+)(?:\(\d+\))?` |
| `src/props/aces.py` | Aces GLM model with train() and predict() | VERIFIED | Fits both Poisson and NegBin via `smf.glm()`; AIC selection; formula `ace_count ~ avg_ace_rate + opp_rtn_pct + surface_clay + surface_grass + level_G + level_M`; calls `compute_pmf` and `save_prop_model` |
| `src/props/double_faults.py` | Double faults GLM model | VERIFIED | Same pattern as aces; uses `avg_df_rate`; target column `df_count` |
| `src/props/games_won.py` | Games won GLM model | VERIFIED | Imports `parse_score`; builds two rows per match from parsed scores; prefers NegBin for higher variance |
| `src/props/__main__.py` | CLI with train and predict subcommands | VERIFIED | Both `train` and `predict` argparse subcommands present; calls `PROP_REGISTRY[st]["train"]` and `predict_and_store()`; note: plan specified `contains: "predict_props"` but actual identifier is `predict_cmd` (argparse subparser) — functionality is correct, name differs |
| `tests/test_props.py` | Unit tests for score parser, PMF, p_over, registry, predict_and_store | VERIFIED | File exists with 103+ lines; confirmed tests for `score_parser`, `compute_pmf`, `p_over`, `PROP_REGISTRY`, `predict_and_store`, CLI help |
| `src/db/schema.sql` | prop_predictions table with UNIQUE constraint and index | VERIFIED | `CREATE TABLE IF NOT EXISTS prop_predictions` at line 339; `idx_prop_predictions_date` index at line 357 |
| `src/api/routers/props.py` | GET /props with real predictions + GET /accuracy | VERIFIED | GET /accuracy registered before GET "" to prevent path param conflict; `response_model=PropsListResponse`; `from src.props.base import p_over`; `json.loads(r["pmf_json"])`; `p_hit = p_o if r["direction"] == "over" else (1.0 - p_o)`; no `status="not_available"` anywhere |
| `src/api/schemas.py` | PropPredictionRow, PropsListResponse, PropAccuracyBin, PropAccuracyResponse | VERIFIED | All 4 classes present at lines 221, 239, 247, 256 |
| `src/props/resolver.py` | resolve_props(conn) | VERIFIED | Imports `parse_score`; resolves aces/df via match_stats join; resolves games_won via score parse; UPDATE prop_predictions; returns `{"resolved": int, "skipped": int}` |
| `src/refresh/runner.py` | Steps 5 (predict_and_store) and 6 (resolve_props) | VERIFIED | Module-level imports at lines 49-50; `props_predict` and `props_resolution` in steps dict; both steps use try/except/conn pattern matching existing pipeline steps |
| `dashboard/src/api/types.ts` | PropPrediction, PropsListResponse, PropAccuracyResponse interfaces | VERIFIED | All interfaces present at lines 98, 130, 141; includes `p_hit`, `pmf`, `direction` fields |
| `dashboard/src/hooks/useProps.ts` | useProps, useSubmitPropLine, usePropAccuracy | VERIFIED | All 3 functions exported; useProps fetches GET /props; useSubmitPropLine posts to /props then invalidates query; usePropAccuracy fetches GET /props/accuracy |
| `dashboard/src/components/charts/PmfChart.tsx` | PMF bar chart with ThresholdLayer | VERIFIED | `makeThresholdLayer` creates SVG `<line>` with `stroke="#f59e0b"` and `strokeDasharray="4,4"`; `colors` callback returns `#22c55e` for bars above threshold; `ThresholdLayerComponent as any` in layers array |
| `dashboard/src/tabs/PropsTab.tsx` | Complete Props tab (435 lines, min 100) | VERIFIED | 435 lines; sections: KPI row (5 cards), inline entry form ("Enter Prop Line"), PMF chart section with value badges ("Value"/"Marginal"/"No Value"), rolling hit rate chart, calibration scatter; two-step POST/GET flow for prediction display |
| `dashboard/src/components/layout/TabNav.tsx` | 5th tab trigger for Props | VERIFIED | `import { PropsTab } from '@/tabs/PropsTab'`; `value="props"` TabsTrigger at line 38; `TabsContent value="props"` at line 57; 5 total TabsTrigger elements |
| `dashboard/src/__tests__/PropsTab.test.tsx` | Smoke tests for PropsTab | VERIFIED | 103 lines; tests for "Enter Prop Line", "Hit Rate", "No props tracked yet", loading skeletons |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/props/aces.py` | `src/props/base.py` | `from src.props.base import compute_pmf, save_prop_model` | WIRED | Line 23 in aces.py |
| `src/props/__init__.py` | `src/props/aces.py` | PROP_REGISTRY dict entry | WIRED | `"aces": {"train": aces_train, "predict": aces_predict}` at line 17 |
| `src/props/games_won.py` | `src/props/score_parser.py` | `from src.props.score_parser import parse_score` | WIRED | Line 25 in games_won.py |
| `src/props/__main__.py` | `src/props/base.py` | `from src.props.base import predict_and_store` | WIRED | Line 7 in __main__.py |
| `src/api/routers/props.py` | `src/props/base.py` | `from src.props.base import p_over` | WIRED | Line 34 in props.py; p_over used in both GET /props and GET /accuracy handlers |
| `src/refresh/runner.py` | `src/props/resolver.py` | `from src.props.resolver import resolve_props` | WIRED | Line 50 in runner.py; resolve_props called at line 196 |
| `src/refresh/runner.py` | `src/props/base.py` | `from src.props.base import predict_and_store` | WIRED | Line 49 in runner.py; predict_and_store called at line 180 |
| `dashboard/src/tabs/PropsTab.tsx` | `dashboard/src/hooks/useProps.ts` | `import { useProps, useSubmitPropLine, usePropAccuracy }` | WIRED | Line 19 in PropsTab.tsx; all 3 hooks used in component body |
| `dashboard/src/tabs/PropsTab.tsx` | `dashboard/src/components/charts/PmfChart.tsx` | `import { PmfChart }` | WIRED | Line 18 in PropsTab.tsx; PmfChart rendered at line 369 |
| `dashboard/src/components/layout/TabNav.tsx` | `dashboard/src/tabs/PropsTab.tsx` | `import { PropsTab }` | WIRED | Line 6 in TabNav.tsx; `<PropsTab />` rendered in TabsContent at line 57 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| PROP-01 | 08-01-PLAN.md | System predicts player stat distributions (aces, games won, double faults) for PrizePicks props | SATISFIED | PROP_REGISTRY with 3 Poisson/NegBin GLM models; predict_and_store writes PMF arrays to prop_predictions table |
| PROP-02 | 08-02-PLAN.md, 08-03-PLAN.md | System compares prop predictions against manually entered PrizePicks lines to identify value | SATISFIED | POST /props stores line; GET /props computes p_hit = p_over(pmf, line_value); PropsTab displays value badges by p_hit threshold; two-step form flow wires submission to PMF display |
| PROP-03 | 08-02-PLAN.md, 08-03-PLAN.md | System tracks prop prediction accuracy over time (directional validation) | SATISFIED | GET /props/accuracy returns overall_hit_rate, per-stat hit rates, rolling_30d series, calibration_bins; PropsTab renders all accuracy metrics with KPI cards and charts |

All 3 phase requirements satisfied. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/props/__main__.py` | — | Plan 01 specified `contains: "predict_props"` but actual identifier is `predict_cmd` (argparse subparser). No function named `predict_props` exists. | Info | No functional impact — CLI works correctly; this is a documentation naming discrepancy in the PLAN frontmatter artifact spec, not a code defect |

No stubs, TODO/FIXME markers, empty returns, or placeholder implementations found in any key file.

### Human Verification Required

#### 1. Props Tab Visual Rendering

**Test:** Start the FastAPI backend (`python -m uvicorn src.api.main:app --reload --port 8000`) and the dashboard (`cd dashboard && npm run dev`). Navigate to `http://localhost:5173`, click the "Props" tab (5th tab).
**Expected:** 5 KPI cards showing "--" values; "Enter Prop Line" form with all 5 fields; "No props tracked yet" empty state for PMF chart area; accuracy charts section visible.
**Why human:** Visual appearance, dark theme consistency, and layout correctness cannot be verified programmatically.

#### 2. Prop Line Submission and PMF Chart

**Test:** In the Props tab form, enter player name "Carlos Alcaraz", select "Aces", enter line value "5.5", select "Over", use today's date. Click "Check Prop".
**Expected:** If prop models are trained: PMF bar chart appears with green bars above the threshold, slate bars below, and an amber dashed vertical threshold line. Value badge appears with correct color (green "Value", amber "Marginal", or slate "No Value") based on P(hit). If no models trained: info toast "Prop line saved. No prediction available yet..."
**Why human:** Chart rendering with SVG ThresholdLayer, bar color transitions, and toast notification behavior require browser execution.

#### 3. Responsive Layout

**Test:** With the Props tab open, resize the browser to approximately 375px width (mobile).
**Expected:** Form fields stack vertically in a single column; KPI cards wrap to multiple rows without horizontal overflow.
**Why human:** Responsive CSS behavior requires visual inspection.

### Gaps Summary

No gaps found. All observable truths are verified, all artifacts pass all three levels (exists, substantive, wired), all key links are confirmed wired, and all 3 requirements (PROP-01, PROP-02, PROP-03) have implementation evidence.

The only open item is human visual verification of the Props tab UI — a blocking checkpoint (Task 3 of Plan 03) that was documented in the plan as requiring user approval. This is not a code defect; it is a standard human gate for visual and interactive behavior that cannot be verified programmatically.

---
_Verified: 2026-03-19_
_Verifier: Claude (gsd-verifier)_
