# Deferred Items — Phase 02

## Out-of-scope Pre-existing Issues Discovered During 02-02

### Pre-existing: schema.sql extended with extra tables, test_loader.py not updated

**Discovered during:** Task 1 (GREEN phase verification)

**Issue:** `src/db/schema.sql` has uncommitted changes from another plan that add three new tables:
- `match_features` (wide feature row per player per match)
- `articles` (tennis press/news articles for sentiment analysis)
- `article_sentiment` (scored sentiment per article)

The existing `tests/test_loader.py::test_schema_creates_all_tables` asserts exactly 7 tables,
but the modified schema now has 10. Additionally, `tests/test_glicko.py` and `tests/test_sentiment.py`
reference modules that do not yet fully pass their tests.

**Why deferred:** These changes were made outside this plan's scope (02-02 feature modules).
The failing tests are in files unrelated to h2h.py, form.py, ranking.py, fatigue.py, or tourney.py.

**Action needed:** Whoever commits the schema.sql changes should also update
`test_loader.py::test_schema_creates_all_tables` to include the 3 new tables.
