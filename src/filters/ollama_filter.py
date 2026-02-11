"""Relevance filtering with keyword scoring + cloud LLM validation."""

import logging
import re

from openai import OpenAI

from src.models import Article
from config import (
    HIGH_PRIORITY_KEYWORDS,
    MEDIUM_PRIORITY_KEYWORDS,
    MOONSHOT_API_KEY,
    MOONSHOT_BASE_URL,
    MOONSHOT_MODEL,
    RELEVANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def keyword_score(article: Article) -> int:
    """
    Score an article based on keyword matches in title + snippet.
    - High-priority keywords (DES, Ablaufsimulation): +2 each
    - Medium-priority keywords (Digital Twin, AI, ML): +1 each
    """
    text = f"{article.title} {article.content_snippet}".lower()
    score = 0

    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw.lower() in text:
            score += 2
            logger.debug(f"  +2 for keyword '{kw}' in: {article.title[:60]}")

    for kw in MEDIUM_PRIORITY_KEYWORDS:
        if kw.lower() in text:
            score += 1
            logger.debug(f"  +1 for keyword '{kw}' in: {article.title[:60]}")

    return score


def kimi_relevance_check(article: Article) -> bool:
    """
    Use Kimi Cloud to confirm article relevance.
    Returns True if the article is relevant.
    """
    if not MOONSHOT_API_KEY:
        logger.warning("  Kimi API key not set — accepting article by default")
        return True

    try:
        client = OpenAI(api_key=MOONSHOT_API_KEY, base_url=MOONSHOT_BASE_URL)

        prompt = (
            f"Title: {article.title}\n"
            f"Snippet: {article.content_snippet[:300]}\n\n"
            "Is this article about industrial AI, discrete event simulation, "
            "digital twin, or smart manufacturing? Reply with only YES or NO."
        )

        response = client.chat.completions.create(
            model=MOONSHOT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a relevance filter for industrial technology news. "
                        "Reply with only YES or NO."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=5,
        )

        answer = response.choices[0].message.content.strip().upper()
        is_relevant = answer.startswith("YES")
        logger.debug(f"  Kimi says {'YES' if is_relevant else 'NO'} for: {article.title[:60]}")
        return is_relevant

    except Exception as e:
        logger.warning(f"  Kimi check failed (accepting by default): {e}")
        return True  # Accept if API is unavailable


def filter_articles(articles: list[Article], skip_llm: bool = False) -> list[Article]:
    """
    Two-stage filtering pipeline:
    1. Keyword scoring — must meet threshold
    2. Kimi Cloud LLM validation (optional, skipped with --skip-llm-filter)

    Returns list of relevant articles sorted by score (descending).
    """
    logger.info(f"[FILTER] Starting filter on {len(articles)} articles")

    scored: list[Article] = []
    for article in articles:
        score = keyword_score(article)
        article.relevance_score = score

        if score >= RELEVANCE_THRESHOLD:
            scored.append(article)

    logger.info(f"[FILTER] {len(scored)}/{len(articles)} passed keyword threshold (>={RELEVANCE_THRESHOLD})")

    if skip_llm:
        logger.info("[FILTER] Skipping LLM validation (keyword-only mode)")
        result = scored
    else:
        result = []
        for article in scored:
            if kimi_relevance_check(article):
                result.append(article)
        logger.info(f"[FILTER] {len(result)}/{len(scored)} passed Kimi Cloud validation")

    # Sort by relevance score descending
    result.sort(key=lambda a: a.relevance_score, reverse=True)
    return result
