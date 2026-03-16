"""
Sentiment scorer for tennis player articles.

Uses DistilBERT (distilbert-base-uncased-finetuned-sst-2-english) to produce
base sentiment scores, enhanced by tennis-domain keyword boosting and
exponential recency weighting.

Pipeline is lazy-loaded to avoid the 268MB model download at import time.
All tests mock _get_pipeline() to keep the test suite fast and offline.
"""
import math
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tennis-domain keyword sets
# ---------------------------------------------------------------------------
TENNIS_POSITIVE = {
    "confident", "fresh", "healthy", "motivated", "fit",
    "rested", "sharp", "ready", "strong",
}

TENNIS_NEGATIVE = {
    "injured", "tired", "fatigued", "struggling", "sick",
    "ill", "pain", "sore", "cramping", "withdrawn",
}

KEYWORD_BOOST = 0.15

# Module-level cache — None until first call to _get_pipeline()
_sentiment_pipe = None


def _get_pipeline():
    """
    Lazy-load and cache the HuggingFace text-classification pipeline.

    Returns the cached pipeline on subsequent calls.
    Safe to mock in tests: patch 'src.sentiment.scorer._get_pipeline'.
    """
    global _sentiment_pipe
    if _sentiment_pipe is None:
        from transformers import pipeline  # type: ignore
        _sentiment_pipe = pipeline(
            "text-classification",
            model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
            device=-1,
        )
        logger.info("DistilBERT sentiment pipeline loaded.")
    return _sentiment_pipe


def score_text(text: str) -> float:
    """
    Score a piece of text on the range [-1.0, 1.0].

    Steps:
    1. Truncate input to 512 characters (DistilBERT token limit proxy).
    2. Run through the HuggingFace pipeline.
    3. Convert label/score to base: POSITIVE -> +score, NEGATIVE -> -score.
    4. Count tennis keyword hits and apply boost.
    5. Clamp to [-1.0, 1.0].

    Parameters
    ----------
    text:
        Raw article text or press-conference excerpt.

    Returns
    -------
    float
        Sentiment score in [-1.0, 1.0].
    """
    truncated = text[:512]
    pipe = _get_pipeline()
    result = pipe(truncated)
    label = result[0]["label"]
    score = result[0]["score"]

    # Convert to signed base score
    base = score if label == "POSITIVE" else -score

    # Tennis keyword boosting
    words = set(truncated.lower().split())
    pos_hits = len(words & TENNIS_POSITIVE)
    neg_hits = len(words & TENNIS_NEGATIVE)
    boosted = base + (pos_hits - neg_hits) * KEYWORD_BOOST

    # Clamp
    return max(-1.0, min(1.0, boosted))


def weighted_player_sentiment(
    articles: list,
    match_date: str,
    half_life_days: int = 14,
) -> float:
    """
    Compute a recency-weighted average sentiment score for a player before a match.

    Articles published on or after match_date are excluded (temporal leakage prevention).
    Weights are computed using exponential decay: w = exp(-0.693 * days_ago / half_life_days).

    Parameters
    ----------
    articles:
        List of dicts with keys 'date' (ISO YYYY-MM-DD) and 'score' (float in [-1, 1]).
    match_date:
        ISO date string (YYYY-MM-DD). Articles must be strictly before this date.
    half_life_days:
        Number of days for the exponential decay half-life. Default 14.

    Returns
    -------
    float
        Weighted average sentiment, or 0.0 if no valid articles.
    """
    match_dt = datetime.strptime(match_date, "%Y-%m-%d")

    weighted_sum = 0.0
    weight_total = 0.0

    for article in articles:
        article_dt = datetime.strptime(article["date"], "%Y-%m-%d")
        if article_dt >= match_dt:
            continue  # Exclude articles on/after match_date

        days_ago = (match_dt - article_dt).days
        weight = math.exp(-0.693 * days_ago / half_life_days)
        weighted_sum += weight * article["score"]
        weight_total += weight

    if weight_total == 0.0:
        return 0.0

    return weighted_sum / weight_total
