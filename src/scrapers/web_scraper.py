"""Static web page scraper using BeautifulSoup4."""

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.models import Article
from config import DATA_SOURCES

logger = logging.getLogger(__name__)

# User-Agent to avoid being blocked
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de,en;q=0.9",
}


def _clean_text(text: str, max_len: int = 500) -> str:
    """Clean and truncate text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _make_absolute(url: str, base_url: str) -> str:
    """Ensure URL is absolute."""
    if url.startswith("http"):
        return url
    from urllib.parse import urljoin
    return urljoin(base_url, url)


def scrape_generic_web(source_name: str, url: str, selector: str,
                       lang: str, category: str, max_items: int = 20) -> list[Article]:
    """Generic scraper for list-based news pages."""
    logger.info(f"[WEB] Fetching {source_name}: {url}")
    articles: list[Article] = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Select items based on provided CSS selector
        items = soup.select(selector)[:max_items]

        for item in items:
            # 1. Try to find title
            title_el = item.select_one("h2, h3, h4, .title, .headline, span.text, strong")
            # Fallback: links usually contain the text if no title element
            if not title_el and item.name == "a":
                title_el = item
            
            title = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)

            # 2. Try to find link
            link_el = item if item.name == "a" else item.select_one("a")
            link = link_el.get("href", "") if link_el else ""

            if not title or len(title) < 5 or not link:
                continue

            # 3. Try to find snippet
            snippet_el = item.select_one("p, .description, .summary, .teaser, .text")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            articles.append(Article(
                title=_clean_text(title),
                url=_make_absolute(link, url),
                source=source_name,
                content_snippet=_clean_text(snippet),
                language=lang,
                category=category,
            ))

        logger.info(f"[WEB] Got {len(articles)} articles from {source_name}")

    except Exception as e:
        logger.error(f"[WEB] Failed to scrape {source_name}: {e}")

    return articles


def scrape_web_sources(max_items: int = 20) -> list[Article]:
    """Run scrapers for all web-type data sources defined in config."""
    articles: list[Article] = []
    
    # Map sources to specific selectors or generic logic
    # (Source Name -> CSS Selector for the valid item container or link)
    selectors = {
        "Plattform Industrie 4.0": ".c-teaser, .card, article a, .use-case a",
        "Fraunhofer IPA Press": ".press-item, .news-item, article",
        "DFKI News": ".news-item, article, .portlet-body a",
        "TUM fml (Logistics)": ".news-item, article, .ce-textpic",
        "SimPlan Blog/News": "article, .post, .entry",
        "Siemens Digital Industries": "a.card, .card__link",
        "VDI Nachrichten Tech": "article, .vdi-card",
        "de:hub Smart Systems": ".news-item, .card",
    }
    
    # Generic fallback selector
    default_selector = "article, .news-item, .card, .entry, .post"

    web_sources = [s for s in DATA_SOURCES if s.source_type == "web"]

    for source in web_sources:
        selector = selectors.get(source.name, default_selector)
        
        # Special case handling if needed, otherwise generic
        found = scrape_generic_web(
            source_name=source.name,
            url=source.url,
            selector=selector,
            lang=source.language,
            category=source.category,
            max_items=max_items
        )
        articles.extend(found)

    return articles
