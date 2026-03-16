---
phase: 02-elo-ratings-feature-engineering
plan: "03"
subsystem: sentiment
tags: [transformers, distilbert, feedparser, beautifulsoup4, nlp, sentiment-analysis, rss, sqlite]

# Dependency graph
requires:
  - phase: 01-data-ingestion-storage
    provides: SQLite connection helpers and schema.sql with ingestion infrastructure

provides:
  - DistilBERT-based sentiment scorer with tennis keyword boosting (score_text)
  - Exponential recency-weighted player sentiment aggregation (weighted_player_sentiment)
  - RSS feed article fetcher with player-name filtering (fetch_rss_articles)
  - ASAPSports press-conference transcript scraper (fetch_asapsports_transcripts)
  - Combined article fetcher with URL deduplication (fetch_all_articles)
  - SQLite persistence for articles and sentiment scores (store_article, store_sentiment_score, get_player_articles)

affects:
  - 03-baseline-model (sentiment features as model inputs)
  - 04-backtesting (historical sentiment signals)
  - 05-fastapi (sentiment endpoints for dashboard)

# Tech tracking
tech-stack:
  added:
    - transformers>=4.30.0 (HuggingFace DistilBERT pipeline for text-classification)
    - feedparser==6.0.12 (RSS feed parsing)
    - beautifulsoup4>=4.12.0 (HTML scraping)
    - lxml>=4.9.0 (fast HTML parser for BeautifulSoup)
    - torch (optional, CPU-only, in [ml] extras — not required for tests)
  patterns:
    - Lazy pipeline loading: module-level _sentiment_pipe = None, initialized on first call
    - Mock-friendly design: patch src.sentiment.scorer._get_pipeline to avoid 268MB download
    - Tennis keyword boosting: KEYWORD_BOOST=0.15 per net positive/negative keyword hit
    - Exponential recency decay: w = exp(-0.693 * days_ago / half_life_days)
    - INSERT OR IGNORE for URL-based deduplication in articles table
    - Python 3.9 compatibility: Optional[List[...]] instead of list | None syntax

key-files:
  created:
    - src/sentiment/__init__.py
    - src/sentiment/scorer.py
    - src/sentiment/fetcher.py
    - src/sentiment/store.py
    - tests/test_sentiment.py
  modified:
    - requirements.txt (added transformers, feedparser, beautifulsoup4, lxml)
    - pyproject.toml (added same + optional [ml] section for torch)

key-decisions:
  - "Lazy pipeline load: _sentiment_pipe=None at module level, initialized in _get_pipeline() — avoids 268MB DistilBERT download at every test/import"
  - "All tests mock _get_pipeline() return value — zero model downloads, suite runs in <1s"
  - "KEYWORD_BOOST=0.15 per keyword: enough to shift borderline scores but cannot flip a strongly polar base score"
  - "half_life_days=14 default for recency decay — two weeks balances recent signal vs. data availability"
  - "INSERT OR IGNORE for deduplication: cleaner than ON CONFLICT DO NOTHING and returns None on duplicate via rowcount check"
  - "Python 3.9 compatible type hints: project specifies requires-python>=3.12 but runtime is Python 3.9; used Optional[List[...]] to fix blocking TypeError"

patterns-established:
  - "Lazy ML model loading: never import-time, always first-call initialization with module cache"
  - "Test isolation via _get_pipeline mock: all sentiment tests run offline without side-effects"
  - "Exponential decay formula: exp(-ln(2) * days_ago / half_life) for half-life semantics"

requirements-completed: [FEAT-05]

# Metrics
duration: 4min
completed: 2026-03-16
---

# Phase 2 Plan 03: Sentiment Analysis Pipeline Summary

**DistilBERT sentiment scorer with tennis keyword boosting, exponential recency weighting, RSS+ASAPSports article fetcher, and SQLite persistence — all tests mocked for offline execution**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-16T18:32:18Z
- **Completed:** 2026-03-16T18:36:32Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Implemented score_text() using lazy-loaded DistilBERT pipeline with TENNIS_POSITIVE/NEGATIVE keyword boost (KEYWORD_BOOST=0.15) and [-1.0, 1.0] clamping
- Implemented weighted_player_sentiment() with configurable exponential decay half-life (default 14 days), strict before-match-date filtering to prevent temporal leakage
- Built fetch_rss_articles() and fetch_asapsports_transcripts() with graceful error handling (HTTP errors, timeouts, bozo feeds), polite delays, and robots.txt check
- DB persistence layer with URL-based deduplication (INSERT OR IGNORE), keyword JSON storage, and date-filtered temporal query for get_player_articles()
- 22 tests, all mocking external dependencies — suite completes in under 1 second, no network calls

## Task Commits

Each task was committed atomically:

1. **TDD RED — failing tests** - `47f343d` (test)
2. **Task 1: Sentiment scorer** - `e3b8e83` (feat)
3. **Task 2: Article fetcher and DB storage** - `47822ea` (feat)

_Note: TDD tasks have RED commit (failing tests) followed by GREEN commit (implementation)_

## Files Created/Modified

- `src/sentiment/__init__.py` - Package marker
- `src/sentiment/scorer.py` - score_text() and weighted_player_sentiment() with lazy DistilBERT pipeline
- `src/sentiment/fetcher.py` - fetch_rss_articles(), fetch_asapsports_transcripts(), fetch_all_articles()
- `src/sentiment/store.py` - store_article(), store_sentiment_score(), get_player_articles()
- `tests/test_sentiment.py` - 22 tests covering all scorer, fetcher, and store behaviors with mocked externals
- `requirements.txt` - Added transformers, feedparser, beautifulsoup4, lxml
- `pyproject.toml` - Added same + optional [ml] section for torch

## Decisions Made

- Lazy pipeline loading via `_get_pipeline()` function avoids importing transformers or downloading the 268MB DistilBERT model at import time — crucial for fast test runs
- All 22 tests mock `_get_pipeline` return value — test suite runs offline in <1s
- `KEYWORD_BOOST=0.15` calibrated so multiple keyword hits can shift borderline scores but cannot flip a strongly polar base score
- `half_life_days=14` chosen as default — two weeks balances recent signal vs. data availability for most players
- Python 3.9 `Optional[List[...]]` type hints used despite pyproject.toml specifying `>=3.12` because actual runtime environment is Python 3.9

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Python 3.9 incompatible union type syntax**
- **Found during:** Task 2 (fetcher.py import)
- **Issue:** `list | None` syntax (PEP 604) raises TypeError on Python 3.9; function signature caused `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`
- **Fix:** Replaced all `list | None` and `set | None` type hints with `Optional[List[...]]` from `typing` module in fetcher.py
- **Files modified:** src/sentiment/fetcher.py
- **Verification:** All 22 tests pass; `python -m pytest tests/test_sentiment.py -q` completes in 0.30s
- **Committed in:** 47822ea (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Fix required for correctness on the actual Python runtime. No scope creep.

## Issues Encountered

- feedparser and beautifulsoup4 were not yet installed — installed via pip before implementing fetcher.py. Added to requirements.txt and pyproject.toml as part of Task 1 action items.

## User Setup Required

None - no external service configuration required. The DistilBERT model downloads on first production use; tests run without it.

## Next Phase Readiness

- Sentiment features are ready to be consumed by Phase 3 (baseline model) as input signals
- articles and article_sentiment tables will be added to schema.sql via Phase 2 Plan 01 schema migration (already defined in plan interfaces)
- No blockers — all tests pass, pipeline is mock-friendly for future test suites

---
*Phase: 02-elo-ratings-feature-engineering*
*Completed: 2026-03-16*

## Self-Check: PASSED

- src/sentiment/__init__.py: FOUND
- src/sentiment/scorer.py: FOUND
- src/sentiment/fetcher.py: FOUND
- src/sentiment/store.py: FOUND
- tests/test_sentiment.py: FOUND
- Commit 47f343d: FOUND (test: failing tests)
- Commit e3b8e83: FOUND (feat: scorer)
- Commit 47822ea: FOUND (feat: fetcher + store)
- pytest tests/test_sentiment.py: 22 passed in 0.29s
