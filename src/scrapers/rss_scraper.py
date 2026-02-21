"""RSS feed scraper for structured news sources."""
"""
RSS 订阅源抓取器 (RSS Feed Scraper)
用于抓取结构化的 RSS/Atom 新闻源。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import re

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
               max_items: int = 20, max_age_hours: int = 48) -> list[Article]:
    """
    抓取并解析 RSS 源 (Fetch and parse RSS feed).
    
    Args:
        name: 数据源名称 (Source Name)
        url: RSS 地址
        language: 语言代码 (de/en/zh)
        category: 类别标签
        max_items: 最大条目数
        max_age_hours: 文章最大时效（小时），超过则跳过；0 表示不限制

    Returns:
        list[Article]: 解析后的文章列表
    """
    cutoff: datetime | None = None
    if max_age_hours > 0:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
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
                video_views=_extract_youtube_views(entry, url),
            )

            # 时效过滤：跳过超过 max_age_hours 的文章（无发布日期的文章放行）
            if cutoff and article.published_date:
                pub_aware = article.published_date.replace(tzinfo=timezone.utc) \
                    if article.published_date.tzinfo is None \
                    else article.published_date
                if pub_aware < cutoff:
                    logger.debug(
                        "[RSS] Skipped stale article (>%sh): %s",
                        max_age_hours,
                        title[:70],
                    )
                    continue

            articles.append(article)

        logger.info(f"[RSS] Got {len(articles)} articles from {name}")

    except Exception as e:
        logger.error(f"[RSS] Failed to scrape {name}: {e}")

    return articles


def _extract_youtube_views(entry: dict, feed_url: str) -> int | None:
    """Try to parse YouTube view count from RSS entry metadata."""
    if "youtube.com/feeds/videos.xml" not in (feed_url or ""):
        return None

    candidates: list[object] = []
    # Common feedparser namespace mappings
    candidates.append(entry.get("yt_statistics"))
    candidates.append(entry.get("media_statistics"))
    # Fallback to direct keys sometimes flattened by parser
    for key in ("views", "viewcount", "yt_views"):
        if key in entry:
            candidates.append(entry.get(key))

    for item in candidates:
        if item is None:
            continue
        if isinstance(item, dict):
            for k in ("views", "viewCount", "viewcount"):
                raw = item.get(k)
                if raw is None:
                    continue
                try:
                    return int(str(raw).replace(",", "").strip())
                except Exception:
                    pass
        else:
            s = str(item)
            m = re.search(r"(\d[\d,]*)", s)
            if m:
                try:
                    return int(m.group(1).replace(",", ""))
                except Exception:
                    pass
    return None
