"""
Article fetcher for the sentiment analysis pipeline.

Provides two sources:
- RSS feeds (via feedparser): generic tennis news
- ASAPSports transcripts (via requests + BeautifulSoup): press conference excerpts

All network calls use polite delays and graceful error handling so that
transient network failures never crash the ingestion pipeline.
"""
import logging
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import urlparse

import feedparser  # type: ignore
import requests
from bs4 import BeautifulSoup  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_RSS_FEEDS = [
    "https://www.atptour.com/en/media/rss-feeds/xml-feed.xml",
]

ASAPSPORTS_BASE = "https://www.asapsports.com/show_player.php"

_REQUEST_DELAY_SECS = 1.5  # polite delay between HTTP requests
_REQUEST_TIMEOUT_SECS = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_robots_allowed(url: str) -> bool:
    """
    Lightweight robots.txt check for the given URL's domain.

    Returns True (allow) if the robots.txt cannot be fetched or parsed,
    so that connectivity issues do not silently block all scraping.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=_REQUEST_TIMEOUT_SECS)
        if resp.status_code != 200:
            return True  # Cannot determine — allow
        # Very simple heuristic: if "Disallow: /" appears for User-agent: *, block
        lines = resp.text.splitlines()
        ua_star = False
        for line in lines:
            line = line.strip()
            if line.lower().startswith("user-agent"):
                ua_star = "*" in line
            elif ua_star and line.lower().startswith("disallow: /") and line.endswith("/"):
                return False
        return True
    except Exception:
        return True  # On any error, assume allowed


def _parse_date(raw_date: str) -> str:
    """
    Attempt to parse a date string and return ISO YYYY-MM-DD.

    Falls back to today's date if parsing fails.
    """
    if not raw_date:
        return datetime.utcnow().strftime("%Y-%m-%d")
    # Try RFC 2822 (standard RSS date)
    try:
        return parsedate_to_datetime(raw_date).strftime("%Y-%m-%d")
    except Exception:
        pass
    # Try ISO-ish formats
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_date[:19], fmt[:len(raw_date[:19])]).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.utcnow().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# RSS fetcher
# ---------------------------------------------------------------------------


def fetch_rss_articles(
    feed_urls: Optional[List[str]] = None,
    player_names: Optional[List[str]] = None,
) -> List[dict]:
    """
    Fetch and parse articles from RSS feeds.

    Parameters
    ----------
    feed_urls:
        List of RSS feed URLs to fetch. Defaults to DEFAULT_RSS_FEEDS.
    player_names:
        Optional list of player names to filter by (case-insensitive match
        against title and summary). If None, all entries are returned.

    Returns
    -------
    list[dict]
        Each dict has keys: title, content, published_date, url, source.
    """
    urls = feed_urls if feed_urls is not None else DEFAULT_RSS_FEEDS
    articles: list = []
    name_lower = [n.lower() for n in player_names] if player_names else None

    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(_REQUEST_DELAY_SECS)
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            logger.warning("feedparser error for %s: %s", url, exc)
            continue

        source = urlparse(url).netloc or url

        for entry in feed.entries:
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            link = getattr(entry, "link", "") or ""
            raw_date = entry.get("published", "") or ""

            if name_lower:
                combined = (title + " " + summary).lower()
                if not any(name in combined for name in name_lower):
                    continue

            articles.append(
                {
                    "title": title,
                    "content": summary,
                    "published_date": _parse_date(raw_date),
                    "url": link,
                    "source": source,
                }
            )

    return articles


# ---------------------------------------------------------------------------
# ASAPSports fetcher
# ---------------------------------------------------------------------------


def fetch_asapsports_transcripts(
    player_name: str,
    max_pages: int = 3,
) -> List[dict]:
    """
    Scrape press conference transcripts from ASAPSports.

    Parameters
    ----------
    player_name:
        Full name of the player (e.g. "Rafael Nadal").
    max_pages:
        Maximum number of result pages to scrape.

    Returns
    -------
    list[dict]
        Same format as fetch_rss_articles output.
    """
    if not _check_robots_allowed(ASAPSPORTS_BASE):
        logger.warning("robots.txt disallows scraping %s", ASAPSPORTS_BASE)
        return []

    articles: list = []

    for page in range(1, max_pages + 1):
        params = {"q": player_name, "page": page}
        try:
            resp = requests.get(
                ASAPSPORTS_BASE,
                params=params,
                timeout=_REQUEST_TIMEOUT_SECS,
                headers={"User-Agent": "SportsResearchBot/1.0"},
            )
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logger.warning("HTTP error fetching ASAPSports page %d: %s", page, exc)
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            logger.warning("Connection error fetching ASAPSports page %d: %s", page, exc)
            break
        except Exception as exc:
            logger.warning("Unexpected error fetching ASAPSports page %d: %s", page, exc)
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract transcript content — ASAPSports uses various div structures;
        # we collect all paragraph text as a fallback.
        entries = soup.find_all("div", class_="transcript") or soup.find_all("p")
        date_tags = soup.find_all("div", class_="date")

        if not entries:
            break  # No more content

        for idx, entry in enumerate(entries):
            text = entry.get_text(separator=" ", strip=True)
            if not text:
                continue

            raw_date = ""
            if idx < len(date_tags):
                raw_date = date_tags[idx].get_text(strip=True)

            page_url = resp.url if page == 1 else f"{resp.url}&page={page}"

            articles.append(
                {
                    "title": f"{player_name} transcript p{page}-{idx + 1}",
                    "content": text,
                    "published_date": _parse_date(raw_date),
                    "url": f"{page_url}#t{idx}",
                    "source": "asapsports",
                }
            )

        if page < max_pages:
            time.sleep(_REQUEST_DELAY_SECS)

    return articles


# ---------------------------------------------------------------------------
# Combined fetcher
# ---------------------------------------------------------------------------


def fetch_all_articles(
    player_names: Optional[List[str]] = None,
    feed_urls: Optional[List[str]] = None,
) -> List[dict]:
    """
    Fetch from all sources and deduplicate by URL.

    Parameters
    ----------
    player_names:
        Player names for RSS filtering and ASAPSports scraping.
    feed_urls:
        Custom RSS feed URLs. Defaults to DEFAULT_RSS_FEEDS.

    Returns
    -------
    list[dict]
        Deduplicated article dicts.
    """
    rss_articles = fetch_rss_articles(feed_urls=feed_urls, player_names=player_names)

    asap_articles: list = []
    if player_names:
        for name in player_names:
            asap_articles.extend(fetch_asapsports_transcripts(player_name=name))

    seen_urls: set = set()
    combined: list = []
    for article in rss_articles + asap_articles:
        url = article.get("url", "")
        if url and url in seen_urls:
            continue
        seen_urls.add(url)
        combined.append(article)

    return combined
