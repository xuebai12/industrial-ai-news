"""Dynamic web scraper using Playwright for JavaScript-rendered pages."""

import asyncio
import logging
import re

from src.models import Article

logger = logging.getLogger(__name__)


async def _scrape_handelsblatt(max_items: int = 20) -> list[Article]:
    """Scrape Handelsblatt tech/industry section (paywall-aware: title + teaser only)."""
    from playwright.async_api import async_playwright

    url = "https://www.handelsblatt.com/technik/"
    logger.info(f"[DYNAMIC] Fetching Handelsblatt: {url}")
    articles: list[Article] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Wait for content to load
            await page.wait_for_timeout(3000)

            # Extract article links and titles
            items = await page.query_selector_all(
                "article a, .vhb-teaser a, .vhb-article a, a[href*='/technik/']"
            )

            seen_urls = set()
            for item in items[:max_items * 2]:  # Over-fetch to filter dupes
                try:
                    title = await item.inner_text()
                    href = await item.get_attribute("href")

                    if not title or not href or len(title.strip()) < 15:
                        continue

                    title = re.sub(r"\s+", " ", title).strip()

                    if href.startswith("/"):
                        href = "https://www.handelsblatt.com" + href

                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    articles.append(Article(
                        title=title[:200],
                        url=href,
                        source="Handelsblatt",
                        content_snippet="",  # Paywall — no snippet
                        language="de",
                        category="industry",
                    ))

                    if len(articles) >= max_items:
                        break
                except Exception:
                    continue

            await browser.close()

        logger.info(f"[DYNAMIC] Got {len(articles)} articles from Handelsblatt")

    except Exception as e:
        logger.error(f"[DYNAMIC] Failed to scrape Handelsblatt: {e}")

    return articles


def scrape_dynamic_sources(max_items: int = 20) -> list[Article]:
    """Run all dynamic (Playwright) scrapers synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in an async context, create a new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                articles = pool.submit(
                    asyncio.run, _scrape_handelsblatt(max_items)
                ).result()
        else:
            articles = loop.run_until_complete(_scrape_handelsblatt(max_items))
    except RuntimeError:
        articles = asyncio.run(_scrape_handelsblatt(max_items))

    return articles
