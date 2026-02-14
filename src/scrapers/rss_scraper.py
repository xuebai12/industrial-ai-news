"""RSS feed scraper for structured news sources."""
"""
RSS 订阅源抓取器 (RSS Feed Scraper)
用于抓取结构化的 RSS/Atom 新闻源。
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import feedparser

from src.models import Article

logger = logging.getLogger(__name__)


def parse_date(entry: dict) -> Optional[datetime]:
    """
    从 RSS 条目中解析日期 (Parse date from RSS entry).
    尝试读取 'published_parsed' 或 'updated_parsed' 字段。
    """
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except Exception:
                continue
    return None


def get_content_snippet(entry: dict, max_len: int = 500) -> str:
    """
    获取内容摘要 (Extract content snippet).
    优先顺序: content > summary > description
    """
    # Try content field first (usually the fullest)
    if "content" in entry and entry["content"]:
        text = entry["content"][0].get("value", "")
    elif "summary" in entry:
        text = entry.get("summary", "")
    elif "description" in entry:
        text = entry.get("description", "")
    else:
        text = ""

    # Strip HTML tags simply (简单去除 HTML 标签)
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def scrape_rss(name: str, url: str, language: str, category: str,
               max_items: int = 20) -> list[Article]:
    """
    抓取并解析 RSS 源 (Fetch and parse RSS feed).
    
    Args:
        name: 数据源名称 (Source Name)
        url: RSS 地址
        language: 语言代码 (de/en/zh)
        category: 类别标签
        max_items: 最大条目数
        
    Returns:
        list[Article]: 解析后的文章列表
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


def scrape_rss_feeds(sources_data: list[dict], max_items: int = 20, max_workers: int = 5) -> tuple[list[Article], list[dict]]:
    """
    Fetch multiple RSS feeds in parallel.

    Args:
        sources_data: List of dicts with keys: name, url, language, category.
        max_items: Max items per feed.
        max_workers: Number of threads.

    Returns:
        tuple: (list of articles, list of failures [{'source': name, 'error': str}])
    """
    articles = []
    failures = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(
                scrape_rss,
                src['name'],
                src['url'],
                src['language'],
                src['category'],
                max_items
            ): src
            for src in sources_data
        }

        for future in as_completed(future_to_source):
            src = future_to_source[future]
            try:
                found = future.result()
                articles.extend(found)
            except Exception as e:
                logger.error(f"[RSS] Parallel execution error for {src['name']}: {e}")
                failures.append({'source': src['name'], 'error': str(e)})

    return articles, failures
