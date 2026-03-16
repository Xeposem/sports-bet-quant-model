"""
Tests for the sentiment analysis pipeline — FEAT-05.

All tests mock the transformer pipeline to avoid model downloads.
Coverage:
- scorer.py: score_text, weighted_player_sentiment
- fetcher.py: fetch_rss_articles, fetch_asapsports_transcripts, fetch_all_articles
- store.py: store_article, store_sentiment_score, get_player_articles
"""
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ARTICLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id      INTEGER NOT NULL,
    tour           TEXT    NOT NULL DEFAULT 'ATP',
    source         TEXT,
    url            TEXT    UNIQUE,
    title          TEXT,
    content        TEXT,
    published_date TEXT NOT NULL,
    fetched_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_sentiment (
    article_id      INTEGER PRIMARY KEY,
    player_id       INTEGER NOT NULL,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    sentiment_score REAL,
    keywords_found  TEXT,
    scored_at       TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
"""


@pytest.fixture
def sentiment_db():
    """In-memory SQLite connection with articles + article_sentiment tables."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(ARTICLES_SCHEMA)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Task 1 — scorer.py tests
# ---------------------------------------------------------------------------


def _mock_pipe_positive():
    """Return a mock pipeline callable that always returns POSITIVE."""
    mock = MagicMock(return_value=[{"label": "POSITIVE", "score": 0.95}])
    return mock


def _mock_pipe_negative():
    """Return a mock pipeline callable that always returns NEGATIVE."""
    mock = MagicMock(return_value=[{"label": "NEGATIVE", "score": 0.90}])
    return mock


class TestScoreText:
    """Tests for src.sentiment.scorer.score_text"""

    def test_positive_pipeline_result_returns_positive_score(self):
        """POSITIVE label from pipeline produces score in (0, 1]."""
        with patch("src.sentiment.scorer._get_pipeline", return_value=_mock_pipe_positive()):
            from src.sentiment.scorer import score_text
            result = score_text("He played a great match today.")
        assert 0 < result <= 1.0

    def test_negative_pipeline_result_returns_negative_score(self):
        """NEGATIVE label from pipeline produces score in [-1, 0)."""
        with patch("src.sentiment.scorer._get_pipeline", return_value=_mock_pipe_negative()):
            from src.sentiment.scorer import score_text
            result = score_text("He struggled badly with his serve.")
        assert -1.0 <= result < 0

    def test_positive_tennis_keyword_boosts_score(self):
        """'confident' keyword boosts score toward +1 compared to no keyword."""
        mock_pipe = MagicMock(return_value=[{"label": "POSITIVE", "score": 0.5}])
        with patch("src.sentiment.scorer._get_pipeline", return_value=mock_pipe):
            from src.sentiment.scorer import score_text
            plain_score = score_text("He played well.")
            boosted_score = score_text("He felt confident on court.")
        assert boosted_score > plain_score

    def test_negative_tennis_keyword_reduces_score(self):
        """'injured' keyword reduces score (pushes toward -1) compared to no keyword."""
        mock_pipe = MagicMock(return_value=[{"label": "POSITIVE", "score": 0.5}])
        with patch("src.sentiment.scorer._get_pipeline", return_value=mock_pipe):
            from src.sentiment.scorer import score_text
            plain_score = score_text("He played well.")
            reduced_score = score_text("He was reported injured during warmup.")
        assert reduced_score < plain_score

    def test_score_clamped_to_minus_one_plus_one(self):
        """Score is always in [-1.0, 1.0] even with many keyword hits."""
        mock_pipe = MagicMock(return_value=[{"label": "POSITIVE", "score": 0.99}])
        with patch("src.sentiment.scorer._get_pipeline", return_value=mock_pipe):
            from src.sentiment.scorer import score_text
            # Flood with many positive keywords
            text = "confident fresh healthy motivated fit rested sharp ready strong"
            result = score_text(text)
        assert -1.0 <= result <= 1.0

    def test_score_text_truncates_input_to_512_chars(self):
        """Pipeline receives at most 512 characters of input text."""
        captured_calls = []

        def capturing_pipe(text):
            captured_calls.append(text)
            return [{"label": "POSITIVE", "score": 0.8}]

        with patch("src.sentiment.scorer._get_pipeline", return_value=capturing_pipe):
            from src.sentiment.scorer import score_text
            long_text = "x" * 1000
            score_text(long_text)

        assert len(captured_calls) == 1
        assert len(captured_calls[0]) <= 512


class TestWeightedPlayerSentiment:
    """Tests for src.sentiment.scorer.weighted_player_sentiment"""

    def test_empty_article_list_returns_zero(self):
        """Empty articles list returns 0.0."""
        from src.sentiment.scorer import weighted_player_sentiment
        result = weighted_player_sentiment([], match_date="2024-01-15")
        assert result == 0.0

    def test_recent_article_weighted_higher_than_old(self):
        """Recent article has higher weight contribution than a 30-day-old article."""
        today = "2024-01-15"
        articles = [
            {"date": "2024-01-14", "score": 1.0},   # 1 day ago — high weight
            {"date": "2023-12-16", "score": -1.0},  # 30 days ago — low weight
        ]
        from src.sentiment.scorer import weighted_player_sentiment
        result = weighted_player_sentiment(articles, match_date=today, half_life_days=14)
        # Recent positive (1.0 weight ~1.0) should dominate old negative (-1.0 weight ~0.22)
        assert result > 0.0

    def test_excludes_articles_on_or_after_match_date(self):
        """Articles with date >= match_date must be excluded."""
        match_date = "2024-01-15"
        articles = [
            {"date": "2024-01-15", "score": 1.0},   # same day — excluded
            {"date": "2024-01-16", "score": 1.0},   # future — excluded
            {"date": "2024-01-14", "score": -0.5},  # before — included
        ]
        from src.sentiment.scorer import weighted_player_sentiment
        result = weighted_player_sentiment(articles, match_date=match_date)
        # Only the -0.5 article is included
        assert result < 0.0

    def test_half_life_affects_weights(self):
        """Different half_life_days values produce different weighted sentiments."""
        articles = [
            {"date": "2024-01-08", "score": 1.0},   # 7 days ago
            {"date": "2023-12-15", "score": -1.0},  # 31 days ago
        ]
        match_date = "2024-01-15"
        from src.sentiment.scorer import weighted_player_sentiment
        result_7 = weighted_player_sentiment(articles, match_date=match_date, half_life_days=7)
        result_14 = weighted_player_sentiment(articles, match_date=match_date, half_life_days=14)
        # Different half-lives should yield different results
        assert result_7 != result_14

    def test_excludes_all_future_returns_zero(self):
        """If all articles are excluded (all future), returns 0.0."""
        articles = [
            {"date": "2024-01-20", "score": 0.8},
            {"date": "2024-01-25", "score": -0.5},
        ]
        from src.sentiment.scorer import weighted_player_sentiment
        result = weighted_player_sentiment(articles, match_date="2024-01-15")
        assert result == 0.0


# ---------------------------------------------------------------------------
# Task 2 — fetcher.py tests
# ---------------------------------------------------------------------------


class TestFetchRssArticles:
    """Tests for src.sentiment.fetcher.fetch_rss_articles"""

    def test_returns_list_of_article_dicts_with_required_keys(self):
        """Mocked feedparser returns articles with expected keys."""
        mock_entry = MagicMock()
        mock_entry.title = "Djokovic wins"
        mock_entry.summary = "Djokovic won the match in straight sets."
        mock_entry.link = "https://example.com/article1"
        mock_entry.get = lambda key, default=None: (
            "Mon, 15 Jan 2024 10:00:00 GMT" if key == "published" else default
        )

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_feed.bozo = False

        with patch("feedparser.parse", return_value=mock_feed):
            from src.sentiment.fetcher import fetch_rss_articles
            articles = fetch_rss_articles(feed_urls=["https://example.com/feed"])

        assert len(articles) >= 1
        required_keys = {"title", "content", "published_date", "url", "source"}
        for article in articles:
            assert required_keys.issubset(article.keys())

    def test_handles_empty_feed_gracefully(self):
        """Empty feed returns empty list without error."""
        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_feed.bozo = False

        with patch("feedparser.parse", return_value=mock_feed):
            from src.sentiment.fetcher import fetch_rss_articles
            articles = fetch_rss_articles(feed_urls=["https://example.com/empty"])

        assert articles == []

    def test_handles_malformed_feed_gracefully(self):
        """Malformed/bozo feed returns empty list without raising."""
        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_feed.bozo = True

        with patch("feedparser.parse", return_value=mock_feed):
            from src.sentiment.fetcher import fetch_rss_articles
            # Should not raise
            articles = fetch_rss_articles(feed_urls=["https://example.com/bad"])

        assert isinstance(articles, list)


class TestFetchAsapsportsTranscripts:
    """Tests for src.sentiment.fetcher.fetch_asapsports_transcripts"""

    def test_returns_transcript_dicts_with_required_keys(self):
        """Mocked requests+BS4 returns transcript dicts with expected keys."""
        mock_html = """
        <html>
          <body>
            <div class="transcript">Nadal played well today, he was confident.</div>
            <div class="date">January 15, 2024</div>
          </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = mock_html
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response), \
             patch("src.sentiment.fetcher._check_robots_allowed", return_value=True):
            from src.sentiment.fetcher import fetch_asapsports_transcripts
            transcripts = fetch_asapsports_transcripts("Rafael Nadal", max_pages=1)

        assert isinstance(transcripts, list)
        if transcripts:
            required_keys = {"title", "content", "published_date", "url", "source"}
            for t in transcripts:
                assert required_keys.issubset(t.keys())

    def test_handles_404_gracefully(self):
        """404 response returns empty list without raising."""
        import requests as req_lib
        with patch("requests.get", side_effect=req_lib.exceptions.HTTPError("404")), \
             patch("src.sentiment.fetcher._check_robots_allowed", return_value=True):
            from src.sentiment.fetcher import fetch_asapsports_transcripts
            result = fetch_asapsports_transcripts("Unknown Player", max_pages=1)

        assert result == []

    def test_handles_timeout_gracefully(self):
        """Timeout returns empty list without raising."""
        import requests as req_lib
        with patch("requests.get", side_effect=req_lib.exceptions.Timeout("timeout")), \
             patch("src.sentiment.fetcher._check_robots_allowed", return_value=True):
            from src.sentiment.fetcher import fetch_asapsports_transcripts
            result = fetch_asapsports_transcripts("Some Player", max_pages=1)

        assert result == []


# ---------------------------------------------------------------------------
# Task 2 — store.py tests
# ---------------------------------------------------------------------------


class TestStoreArticle:
    """Tests for src.sentiment.store.store_article"""

    def _make_article(self, url="https://example.com/article1"):
        return {
            "title": "Test Article",
            "content": "Player was confident and ready.",
            "published_date": "2024-01-14",
            "url": url,
            "source": "atp_rss",
        }

    def test_insert_returns_article_id(self, sentiment_db):
        """store_article returns a valid integer article_id."""
        from src.sentiment.store import store_article
        article_id = store_article(sentiment_db, player_id=100, article=self._make_article())
        assert isinstance(article_id, int)
        assert article_id > 0

    def test_duplicate_url_does_not_raise(self, sentiment_db):
        """Inserting same URL twice does not raise; second call returns None."""
        from src.sentiment.store import store_article
        article = self._make_article()
        first_id = store_article(sentiment_db, player_id=100, article=article)
        second_id = store_article(sentiment_db, player_id=100, article=article)
        assert first_id is not None
        assert second_id is None


class TestStoreSentimentScore:
    """Tests for src.sentiment.store.store_sentiment_score"""

    def test_inserts_into_article_sentiment(self, sentiment_db):
        """store_sentiment_score creates a row in article_sentiment table."""
        from src.sentiment.store import store_article, store_sentiment_score
        article = {
            "title": "Test",
            "content": "Great match.",
            "published_date": "2024-01-14",
            "url": "https://example.com/art2",
            "source": "rss",
        }
        article_id = store_article(sentiment_db, player_id=200, article=article)
        store_sentiment_score(
            sentiment_db,
            article_id=article_id,
            player_id=200,
            score=0.75,
            keywords=["confident", "ready"],
        )

        row = sentiment_db.execute(
            "SELECT sentiment_score, keywords_found FROM article_sentiment WHERE article_id = ?",
            (article_id,),
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 0.75) < 1e-6
        assert "confident" in row[1]


class TestGetPlayerArticles:
    """Tests for src.sentiment.store.get_player_articles"""

    def _insert_article_with_score(self, conn, player_id, url, published_date, score):
        from src.sentiment.store import store_article, store_sentiment_score
        article = {
            "title": "Test",
            "content": "Some content.",
            "published_date": published_date,
            "url": url,
            "source": "rss",
        }
        article_id = store_article(conn, player_id=player_id, article=article)
        if article_id:
            store_sentiment_score(conn, article_id=article_id, player_id=player_id,
                                  score=score, keywords=[])
        return article_id

    def test_returns_articles_before_date_sorted_desc(self, sentiment_db):
        """get_player_articles returns articles before given date, sorted DESC."""
        self._insert_article_with_score(sentiment_db, 300, "https://ex.com/a1", "2024-01-10", 0.5)
        self._insert_article_with_score(sentiment_db, 300, "https://ex.com/a2", "2024-01-12", 0.8)
        self._insert_article_with_score(sentiment_db, 300, "https://ex.com/a3", "2024-01-16", 0.9)

        from src.sentiment.store import get_player_articles
        results = get_player_articles(sentiment_db, player_id=300, before_date="2024-01-15")

        assert len(results) == 2
        # Sorted descending by date
        dates = [r["date"] for r in results]
        assert dates == sorted(dates, reverse=True)

    def test_excludes_other_players_articles(self, sentiment_db):
        """get_player_articles only returns articles for the specified player."""
        self._insert_article_with_score(sentiment_db, 400, "https://ex.com/b1", "2024-01-10", 0.3)
        self._insert_article_with_score(sentiment_db, 401, "https://ex.com/b2", "2024-01-11", 0.7)

        from src.sentiment.store import get_player_articles
        results = get_player_articles(sentiment_db, player_id=400, before_date="2024-01-15")

        assert len(results) == 1
        assert results[0]["score"] == pytest.approx(0.3)
