"""RSS feed scraper for structured news sources."""

import logging
from datetime import datetime
from typing import Optional

import feedparser

from src.models import Article

logger = logging.getLogger(__name__)


def parse_date(entry: dict) -> Optional[datetime]:
    """Parse date from RSS entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except Exception:
                continue
    return None


def get_content_snippet(entry: dict, max_len: int = 500) -> str:
    """Extract the best available content snippet from an RSS entry."""
    # Try content field first (usually the fullest)
    if "content" in entry and entry["content"]:
        text = entry["content"][0].get("value", "")
    elif "summary" in entry:
        text = entry.get("summary", "")
    elif "description" in entry:
        text = entry.get("description", "")
    else:
        text = ""

    # Strip HTML tags simply
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def scrape_rss(name: str, url: str, language: str, category: str,
               max_items: int = 20) -> list[Article]:
    """
    Fetch and parse an RSS feed, returning a list of Article objects.

    Args:
        name: Human-readable source name
        url: RSS feed URL
        language: Source language code (de/en/zh)
        category: Article category tag
        max_items: Maximum number of items to return
    """
    logger.info(f"[RSS] Fetching: {name} ({url})")
    articles: list[Article] = []

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"[RSS] Feed error for {name}: {feed.bozo_exception}")
            return articles

        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            article = Article(
                title=title,
                url=link,
                source=name,
                content_snippet=get_content_snippet(entry),
                language=language,
                category=category,
                published_date=parse_date(entry),
            )
            articles.append(article)

        logger.info(f"[RSS] Got {len(articles)} articles from {name}")

    except Exception as e:
        logger.error(f"[RSS] Failed to scrape {name}: {e}")

    return articles
