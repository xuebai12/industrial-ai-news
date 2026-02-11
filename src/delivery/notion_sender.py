"""Notion delivery module — push analyzed articles to a Notion database."""

import logging
import re
from datetime import date

from notion_client import Client

from src.models import AnalyzedArticle
from config import NOTION_API_KEY, NOTION_DATABASE_ID

logger = logging.getLogger(__name__)


def push_to_notion(articles: list[AnalyzedArticle], today: str | None = None) -> int:
    """
    Push analyzed articles to Notion database.
    Returns the number of articles successfully pushed.
    - Incremental: skips articles whose URL already exists in the database.
    - Writes structured properties + Markdown page body.
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.warning("[NOTION] API key or Database ID not configured, skipping")
        return 0

    today = today or date.today().strftime("%Y-%m-%d")
    client = Client(auth=NOTION_API_KEY)

    # Fetch existing URLs for dedup
    existing_urls = _get_existing_urls(client)
    logger.info(f"[NOTION] Found {len(existing_urls)} existing entries in database")

    pushed = 0
    for i, article in enumerate(articles):
        url = article.source_url or ""
        if url in existing_urls:
            logger.info(f"[NOTION] Skip (duplicate): {article.title_zh[:40]}")
            continue

        try:
            _create_page(client, article, today)
            pushed += 1
            logger.info(f"[NOTION] ✅ Pushed {pushed}: {article.title_zh[:50]}")
        except Exception as e:
            logger.error(f"[NOTION] ❌ Failed to push '{article.title_zh[:40]}': {e}")

    logger.info(f"[NOTION] Done: {pushed} new entries pushed ({len(articles) - pushed} skipped)")
    return pushed


def _get_existing_urls(client: Client) -> set[str]:
    """Query database for all existing source URLs (for dedup)."""
    urls = set()
    try:
        has_more = True
        start_cursor = None
        while has_more:
            resp = client.databases.query(
                database_id=NOTION_DATABASE_ID,
                start_cursor=start_cursor,
                page_size=100,
                filter_properties=["原文链接"],
            )
            for page in resp.get("results", []):
                props = page.get("properties", {})
                url_prop = props.get("原文链接", {})
                if url_prop.get("url"):
                    urls.add(url_prop["url"])
            has_more = resp.get("has_more", False)
            start_cursor = resp.get("next_cursor")
    except Exception as e:
        logger.warning(f"[NOTION] Could not fetch existing URLs: {e}")
    return urls


def _parse_multi_select_tags(text: str) -> list[dict]:
    """Parse comma/semicolon separated text into Notion multi-select tags."""
    if not text:
        return []
    # Split by common delimiters
    parts = re.split(r"[,;，；、/]", text)
    tags = []
    for part in parts:
        tag = part.strip()
        if tag and len(tag) < 100:  # Notion limit
            tags.append({"name": tag})
    return tags[:10]  # Notion limit: max tags


def _career_relevance(article: AnalyzedArticle) -> str:
    """Estimate career relevance based on content richness."""
    signals = 0
    if article.hiring_signals and len(article.hiring_signals) > 10:
        signals += 2
    if article.interview_flip and len(article.interview_flip) > 10:
        signals += 2
    if article.tool_stack and len(article.tool_stack) > 5:
        signals += 1
    if signals >= 3:
        return "High"
    elif signals >= 1:
        return "Medium"
    return "Low"


def _create_page(client: Client, article: AnalyzedArticle, today: str):
    """Create a single Notion database entry with properties and page body."""
    properties = {
        "标题": {
            "title": [{"text": {"content": article.title_zh or article.title_en or "Untitled"}}]
        },
        "类别": {
            "select": {"name": article.category_tag or "Other"}
        },
        "AI 摘要": {
            "rich_text": [{"text": {"content": (article.summary_zh or "")[:2000]}}]
        },
        "核心技术": {
            "multi_select": _parse_multi_select_tags(article.core_tech_points)
        },
        "来源/机构": {
            "select": {"name": article.source_name or "Unknown"}
        },
        "原文链接": {
            "url": article.source_url or None
        },
        "日期": {
            "date": {"start": today}
        },
        "工具链": {
            "rich_text": [{"text": {"content": (article.tool_stack or "")[:2000]}}]
        },
        "招聘信号": {
            "rich_text": [{"text": {"content": (article.hiring_signals or "")[:2000]}}]
        },
        "面试谈资": {
            "rich_text": [{"text": {"content": (article.interview_flip or "")[:2000]}}]
        },
        "学术差异": {
            "rich_text": [{"text": {"content": (article.theory_gap or "")[:2000]}}]
        },
        "职业关联度": {
            "select": {"name": _career_relevance(article)}
        },
    }

    # Build page body as Notion blocks (Markdown-style)
    children = _build_page_body(article)

    client.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=properties,
        children=children,
    )


def _build_page_body(article: AnalyzedArticle) -> list[dict]:
    """Build Notion page content blocks for the article."""
    blocks = []

    # English title
    blocks.append(_heading2(article.title_en or article.title_zh))

    # Summaries
    blocks.append(_heading3("📝 摘要 / Summary"))
    if article.summary_zh:
        blocks.append(_paragraph(f"🇨🇳 {article.summary_zh}"))
    if article.summary_en:
        blocks.append(_paragraph(f"🇬🇧 {article.summary_en}"))

    # Core tech
    if article.core_tech_points:
        blocks.append(_heading3("🔬 核心技术"))
        blocks.append(_paragraph(article.core_tech_points))

    # German context
    if article.german_context:
        blocks.append(_heading3("🏭 德国市场背景"))
        blocks.append(_paragraph(article.german_context))

    # Tool stack
    if article.tool_stack:
        blocks.append(_heading3("🛠️ 工具链"))
        blocks.append(_paragraph(article.tool_stack))

    # Hiring signals
    if article.hiring_signals:
        blocks.append(_heading3("💼 招聘信号"))
        blocks.append(_paragraph(article.hiring_signals))

    # Interview insights
    if article.interview_flip:
        blocks.append(_heading3("💡 面试谈资"))
        blocks.append(_paragraph(article.interview_flip))

    # Theory vs practice
    if article.theory_gap:
        blocks.append(_heading3("📖 学术 vs 工业"))
        blocks.append(_paragraph(article.theory_gap))

    # Source link
    blocks.append(_divider())
    if article.source_url:
        blocks.append(_paragraph(f"🔗 原文: {article.source_url}"))
    blocks.append(_paragraph(f"📡 来源: {article.source_name}"))

    return blocks


# --- Notion Block Helpers ---

def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}
