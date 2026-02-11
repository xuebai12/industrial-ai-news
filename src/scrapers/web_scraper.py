"""Static web page scraper using BeautifulSoup4."""

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from src.models import Article

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
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def scrape_plattform_i40(max_items: int = 20) -> list[Article]:
    """Scrape Plattform Industrie 4.0 for use cases and news."""
    url = "https://www.plattform-i40.de/IP/Navigation/EN/Industrie40/UseCases/use-cases.html"
    logger.info(f"[WEB] Fetching Plattform Industrie 4.0: {url}")
    articles: list[Article] = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for article/card links on the page
        for item in soup.select("a.c-teaser, a.card, article a, .use-case a")[:max_items]:
            title_el = item.select_one("h2, h3, .title, .headline")
            title = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)
            link = item.get("href", "")

            if not title or not link:
                continue

            # Make absolute URL
            if link.startswith("/"):
                link = "https://www.plattform-i40.de" + link

            snippet_el = item.select_one("p, .description, .summary, .teaser-text")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            articles.append(Article(
                title=_clean_text(title),
                url=link,
                source="Plattform Industrie 4.0",
                content_snippet=_clean_text(snippet),
                language="de",
                category="policy",
            ))

        logger.info(f"[WEB] Got {len(articles)} articles from Plattform Industrie 4.0")

    except Exception as e:
        logger.error(f"[WEB] Failed to scrape Plattform Industrie 4.0: {e}")

    return articles


def scrape_fraunhofer_press(institute: str = "ipa", max_items: int = 20) -> list[Article]:
    """Scrape Fraunhofer institute press releases page."""
    urls = {
        "ipa": "https://www.ipa.fraunhofer.de/de/presse/presseinformationen.html",
        "iapt": "https://www.2.iapt.fraunhofer.de/en/press.html",
    }
    url = urls.get(institute, urls["ipa"])
    lang = "de" if institute == "ipa" else "en"
    name = f"Fraunhofer {institute.upper()}"

    logger.info(f"[WEB] Fetching {name}: {url}")
    articles: list[Article] = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select("a.teaser, .press-item a, article a, .news-item a")[:max_items]:
            title_el = item.select_one("h2, h3, .title, .headline")
            title = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)
            link = item.get("href", "")

            if not title or len(title) < 10 or not link:
                continue

            if link.startswith("/"):
                base = "https://www.ipa.fraunhofer.de" if institute == "ipa" else "https://www.2.iapt.fraunhofer.de"
                link = base + link

            snippet_el = item.select_one("p, .description, .teaser-text")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            articles.append(Article(
                title=_clean_text(title),
                url=link,
                source=name,
                content_snippet=_clean_text(snippet),
                language=lang,
                category="research",
            ))

        logger.info(f"[WEB] Got {len(articles)} articles from {name}")

    except Exception as e:
        logger.error(f"[WEB] Failed to scrape {name}: {e}")

    return articles


def scrape_web_sources(max_items: int = 20) -> list[Article]:
    """Run all static web scrapers and return combined results."""
    articles: list[Article] = []
    articles.extend(scrape_plattform_i40(max_items))
    articles.extend(scrape_fraunhofer_press("ipa", max_items))
    articles.extend(scrape_fraunhofer_press("iapt", max_items))
    return articles
