"""Static web page scraper using BeautifulSoup4."""
"""
静态网页抓取器 (Static Web Scraper)
使用 BeautifulSoup4 和 Requests 抓取普通网页新闻列表。
"""

import logging
import json
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from src.models import Article
from config import DATA_SOURCES

logger = logging.getLogger(__name__)
OBSERVED_SOURCES = {"ABB Robotics News", "Rockwell Automation Blog"}
OBSERVATION_STATE_PATH = os.path.join("output", "source_observation.json")
ZERO_DISABLE_THRESHOLD = 3

# User-Agent to avoid being blocked (设置 UA 防止被反爬)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de,en;q=0.9",
}


def _build_session() -> requests.Session:
    """创建带有重试机制的 HTTP 会话 (Build Request Session with automatic retries)"""
    session = requests.Session()
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _load_observation_state() -> dict:
    if not os.path.exists(OBSERVATION_STATE_PATH):
        return {}
    try:
        with open(OBSERVATION_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_observation_state(state: dict) -> None:
    os.makedirs(os.path.dirname(OBSERVATION_STATE_PATH), exist_ok=True)
    with open(OBSERVATION_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _is_observation_disabled(state: dict, source_name: str) -> bool:
    info = state.get(source_name, {})
    return bool(info.get("disabled", False))


def _update_observation_status(state: dict, source_name: str, fetched_count: int) -> None:
    if source_name not in OBSERVED_SOURCES:
        return
    info = state.get(source_name, {"zero_streak": 0, "disabled": False})
    if fetched_count > 0:
        info["zero_streak"] = 0
        info["disabled"] = False
    else:
        info["zero_streak"] = int(info.get("zero_streak", 0)) + 1
        if info["zero_streak"] >= ZERO_DISABLE_THRESHOLD:
            info["disabled"] = True
    state[source_name] = info


def _clean_text(text: str, max_len: int = 500) -> str:
    """清洗并截断文本 (Clean and truncate text)."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _make_absolute(url: str, base_url: str) -> str:
    """确保 URL 是绝对路径 (Ensure URL is absolute)."""
    if url.startswith("http"):
        return url
    return urljoin(base_url, url)


def scrape_generic_web(source_name: str, url: str, selector: str,
                       lang: str, category: str, max_items: int = 20,
                       session: requests.Session | None = None) -> list[Article]:
    """
    通用网页列表抓取器 (Generic Web Scraper).
    根据 CSS 选择器抓取新闻列表页面。
    
    Args:
        selector: CSS 选择器，用于定位每篇新闻的容器或链接。
    """
    logger.info(f"[WEB] Fetching {source_name}: {url}")
    articles: list[Article] = []

    try:
        req = session or requests
        resp = req.get(url, headers=HEADERS, timeout=15)
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

            # 2. Try to find link (查找链接)
            link_el = item if item.name == "a" else item.select_one("a")
            link = link_el.get("href", "") if link_el else ""

            if not title or len(title) < 5 or not link:
                continue

            # 3. Try to find snippet (查找摘要)
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
    """
    抓取所有配置为 'web' 类型的源 (Scrape all web sources).
    根据 config.DATA_SOURCES 中的定义，自动匹配抓取规则。
    """
    articles: list[Article] = []
    
    # Map sources to specific selectors or generic logic
    # (Source Name -> CSS Selector mapping)
    # 针对不同网站的 CSS 选择器配置
    selectors = {
        "Plattform Industrie 4.0": ".c-teaser, .card, article a, .use-case a",
        "Fraunhofer IPA Press": ".press-item, .news-item, article",
        "DFKI News": ".news-item, article, .portlet-body a",
        "TUM fml (Logistics)": ".news-item, article, .ce-textpic",
        "SimPlan Blog/News": "article, .post, .entry",
        "VDI Nachrichten Tech": "article, .vdi-card",
        "de:hub Smart Systems": ".news-item, .card",
        "ABB Robotics News": "article a, .news-item a, .teaser a, a[href*='/news/']",
        "Rockwell Automation Blog": "article a, .cmp-teaser a, .card a, a[href*='/blogs/']",
        "Bosch Stories (Manufacturing/AI)": "article a, .story-teaser a, .teaser a, a[href*='/stories/']",
    }
    
    # Generic fallback selector (通用回退选择器)
    default_selector = "article, .news-item, .card, .entry, .post"

    web_sources = [s for s in DATA_SOURCES if s.source_type == "web"]
    observation_state = _load_observation_state()

    session = _build_session()
    try:
        for source in web_sources:
            if source.name in OBSERVED_SOURCES and _is_observation_disabled(observation_state, source.name):
                logger.warning(
                    "[WEB] Skipping observed source '%s' (disabled after %s consecutive zero-result runs)",
                    source.name,
                    ZERO_DISABLE_THRESHOLD,
                )
                continue
            selector = selectors.get(source.name, default_selector)

            found = scrape_generic_web(
                source_name=source.name,
                url=source.url,
                selector=selector,
                lang=source.language,
                category=source.category,
                max_items=max_items,
                session=session,
            )
            _update_observation_status(observation_state, source.name, len(found))
            articles.extend(found)
    finally:
        session.close()
        _save_observation_state(observation_state)

    return articles
