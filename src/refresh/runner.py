"""
Unified refresh orchestrator for the full tennis quantitative pipeline.

Executes all pipeline steps in order:
  1. Ingest: download and load new match data (src.ingestion.loader.ingest_all)
  2. Ratings: compute/update Glicko-2 ratings (src.ratings.glicko.compute_all_ratings)
  3. Sentiment: fetch articles and score them (src.sentiment.fetcher.fetch_all_articles)
  4. Features: rebuild feature matrix (src.features.builder.build_all_features)

Each step is wrapped in try/except so a failure in one step does NOT prevent
subsequent steps from running. Errors are logged and captured in the return value.

Callable from:
  a) CLI:       python -m src.refresh --db-path tennis.db
  b) APScheduler: scheduler.add_job(refresh_all, args=["tennis.db"])
  c) FastAPI (Phase 5): await run_in_executor(refresh_all, "tennis.db")

Exports:
  - refresh_all(db_path, raw_dir, fetch_articles) -> dict
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies and heavy load at module level
def _import_ingest_all():
    from src.ingestion.loader import ingest_all
    return ingest_all

def _import_compute_all_ratings():
    from src.ratings.glicko import compute_all_ratings
    return compute_all_ratings

def _import_build_all_features():
    from src.features.builder import build_all_features
    return build_all_features

def _import_fetch_all_articles():
    from src.sentiment.fetcher import fetch_all_articles
    return fetch_all_articles

# Module-level references used by tests (allow patching at module level)
from src.ingestion.loader import ingest_all
from src.ratings.glicko import compute_all_ratings
from src.features.builder import build_all_features
from src.sentiment.fetcher import fetch_all_articles


def refresh_all(
    db_path: str,
    raw_dir: str = "data/raw",
    fetch_articles: bool = True,
) -> dict:
    """
    Run the complete pipeline refresh: ingest -> ratings -> sentiment -> features.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.
    raw_dir : str
        Directory containing raw match CSV files. Defaults to "data/raw".
    fetch_articles : bool
        Whether to fetch and score new sentiment articles. Defaults to True.
        Set False for faster refreshes when article data is not needed.

    Returns
    -------
    dict
        {
            "steps": {
                "ingest": <result or error dict>,
                "ratings": <result or error dict>,
                "sentiment": <result or error dict>,
                "features": <result or error dict>,
            },
            "success": bool  -- True if no step raised an unhandled exception
        }
    """
    import sqlite3
    from src.db.connection import get_connection, init_db

    steps: dict = {
        "ingest": None,
        "ratings": None,
        "sentiment": None,
        "features": None,
    }
    any_error = False

    # -------------------------------------------------------------------
    # Step 1: Ingest new match data
    # -------------------------------------------------------------------
    try:
        result = ingest_all(db_path, raw_dir)
        steps["ingest"] = result
        logger.info("refresh_all: ingest completed — %s", result)
    except Exception as exc:
        logger.error("refresh_all: ingest step failed: %s", exc, exc_info=True)
        steps["ingest"] = {"error": str(exc)}
        any_error = True

    # -------------------------------------------------------------------
    # Step 2: Compute/update Glicko-2 ratings
    # -------------------------------------------------------------------
    try:
        conn = get_connection(db_path)
        try:
            result = compute_all_ratings(conn)
            steps["ratings"] = result
            logger.info("refresh_all: ratings completed — %s", result)
        finally:
            conn.close()
    except Exception as exc:
        logger.error("refresh_all: ratings step failed: %s", exc, exc_info=True)
        steps["ratings"] = {"error": str(exc)}
        any_error = True

    # -------------------------------------------------------------------
    # Step 3: Sentiment — fetch and score articles
    # -------------------------------------------------------------------
    if fetch_articles:
        try:
            from src.sentiment.store import store_article, store_sentiment_score
            from src.sentiment.scorer import score_text

            articles = fetch_all_articles()
            conn = get_connection(db_path)
            scored_count = 0
            try:
                for article in articles:
                    player_id = article.get("player_id")
                    if player_id is None:
                        continue
                    article_id = store_article(conn, player_id, article)
                    if article_id is not None:
                        text = article.get("content", "") or article.get("title", "")
                        sentiment = score_text(text)
                        store_sentiment_score(conn, article_id, player_id, sentiment, [])
                        scored_count += 1
                steps["sentiment"] = {"articles_fetched": len(articles), "articles_scored": scored_count}
                logger.info("refresh_all: sentiment completed — %s articles fetched", len(articles))
            finally:
                conn.close()
        except Exception as exc:
            logger.error("refresh_all: sentiment step failed: %s", exc, exc_info=True)
            steps["sentiment"] = {"error": str(exc)}
            any_error = True
    else:
        steps["sentiment"] = {"skipped": True}

    # -------------------------------------------------------------------
    # Step 4: Rebuild feature matrix
    # -------------------------------------------------------------------
    try:
        conn = get_connection(db_path)
        try:
            result = build_all_features(conn)
            steps["features"] = result
            logger.info("refresh_all: features completed — %s", result)
        finally:
            conn.close()
    except Exception as exc:
        logger.error("refresh_all: features step failed: %s", exc, exc_info=True)
        steps["features"] = {"error": str(exc)}
        any_error = True

    return {
        "steps": steps,
        "success": not any_error,
    }
