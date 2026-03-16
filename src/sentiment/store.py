"""
Sentiment DB persistence layer.

Provides three operations:
- store_article: insert an article into the articles table (dedup by URL)
- store_sentiment_score: persist a sentiment score to article_sentiment
- get_player_articles: retrieve scored articles for a player before a given date
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def store_article(conn, player_id: int, article: dict):
    """
    Insert an article into the articles table.

    Uses INSERT OR IGNORE to handle duplicate URLs gracefully.

    Parameters
    ----------
    conn:
        SQLite connection with the articles table present.
    player_id:
        Integer player identifier.
    article:
        Dict with keys: title, content, published_date, url, source.

    Returns
    -------
    int or None
        The article_id (lastrowid) if inserted, or None if duplicate URL.
    """
    fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO articles
                (player_id, tour, source, url, title, content, published_date, fetched_at)
            VALUES
                (:player_id, :tour, :source, :url, :title, :content, :published_date, :fetched_at)
            """,
            {
                "player_id": player_id,
                "tour": article.get("tour", "ATP"),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "title": article.get("title", ""),
                "content": article.get("content", ""),
                "published_date": article.get("published_date", ""),
                "fetched_at": fetched_at,
            },
        )
        conn.commit()
        if cursor.lastrowid and cursor.rowcount > 0:
            return cursor.lastrowid
        return None
    except Exception as exc:
        logger.error("store_article error for url=%s: %s", article.get("url"), exc)
        return None


def store_sentiment_score(
    conn,
    article_id: int,
    player_id: int,
    score: float,
    keywords: list,
) -> None:
    """
    Persist a sentiment score for an article.

    Parameters
    ----------
    conn:
        SQLite connection with the article_sentiment table present.
    article_id:
        FK reference to articles.id.
    player_id:
        Integer player identifier.
    score:
        Sentiment score in [-1.0, 1.0].
    keywords:
        List of matched tennis keywords (stored as JSON string).
    """
    scored_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    keywords_json = json.dumps(keywords) if keywords else "[]"
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO article_sentiment
                (article_id, player_id, tour, sentiment_score, keywords_found, scored_at)
            VALUES
                (:article_id, :player_id, :tour, :sentiment_score, :keywords_found, :scored_at)
            """,
            {
                "article_id": article_id,
                "player_id": player_id,
                "tour": "ATP",
                "sentiment_score": score,
                "keywords_found": keywords_json,
                "scored_at": scored_at,
            },
        )
        conn.commit()
    except Exception as exc:
        logger.error("store_sentiment_score error for article_id=%s: %s", article_id, exc)


def get_player_articles(conn, player_id: int, before_date: str) -> list:
    """
    Retrieve sentiment-scored articles for a player published before a given date.

    Parameters
    ----------
    conn:
        SQLite connection.
    player_id:
        Integer player identifier.
    before_date:
        ISO date string (YYYY-MM-DD). Only articles strictly before this date are returned.

    Returns
    -------
    list[dict]
        Each dict has keys: 'date' (published_date) and 'score' (sentiment_score),
        sorted by date descending.
    """
    try:
        cursor = conn.execute(
            """
            SELECT a.published_date, s.sentiment_score
            FROM articles a
            JOIN article_sentiment s ON a.id = s.article_id
            WHERE a.player_id = :player_id
              AND a.published_date < :before_date
            ORDER BY a.published_date DESC
            """,
            {"player_id": player_id, "before_date": before_date},
        )
        rows = cursor.fetchall()
        return [{"date": row[0], "score": row[1]} for row in rows]
    except Exception as exc:
        logger.error("get_player_articles error for player_id=%s: %s", player_id, exc)
        return []
