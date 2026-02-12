"""Service layer for Notion delivery business logic."""

import hashlib
import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from notion_client import Client
from notion_client.errors import APIResponseError

from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)


class NotionDeliveryError(Exception):
    """Structured Notion delivery error with category metadata."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


class NotionDeliveryService:
    """Encapsulates Notion database interactions for analyzed articles."""

    def __init__(self, client: Client, database_id: str):
        self.client = client
        self.database_id = database_id

    def push_articles(self, articles: list[AnalyzedArticle], today: str) -> int:
        """
        Push analyzed articles to Notion database.
        Returns number of newly created entries.
        """
        existing_urls = self.get_existing_urls()
        logger.info(f"[NOTION] Found {len(existing_urls)} existing entries in database")

        pushed = 0
        seen_hashes: set[str] = set()
        for article in articles:
            normalized = self.normalize_url(article.source_url or "")
            if normalized and normalized in existing_urls:
                logger.info(f"[NOTION] Skip (duplicate url): {article.title_zh[:40]}")
                continue

            dedupe_key = self.article_dedupe_hash(article)
            if dedupe_key in seen_hashes:
                logger.info(f"[NOTION] Skip (duplicate hash): {article.title_zh[:40]}")
                continue
            seen_hashes.add(dedupe_key)

            try:
                self.create_page(article, today)
                pushed += 1
                logger.info(f"[NOTION] ✅ Pushed {pushed}: {article.title_zh[:50]}")
            except NotionDeliveryError as e:
                logger.error(
                    "[NOTION] ❌ Failed to push '%s': category=%s error=%s",
                    article.title_zh[:40],
                    e.category,
                    e.message,
                )
                # Fail-fast on auth/schema issues (retry won't help)
                if e.category in {"AUTH", "SCHEMA"}:
                    raise
            except Exception as e:
                category = self.classify_error(e)
                logger.error(
                    "[NOTION] ❌ Failed to push '%s': category=%s error=%s",
                    article.title_zh[:40],
                    category,
                    e,
                )

        logger.info(
            f"[NOTION] Done: {pushed} new entries pushed ({len(articles) - pushed} skipped)"
        )
        return pushed

    @staticmethod
    def normalize_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        clean_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
        clean_path = parsed.path.rstrip("/") or "/"
        return urlunparse(
            (parsed.scheme.lower(), netloc, clean_path, parsed.params, clean_query, "")
        )

    @classmethod
    def article_dedupe_hash(cls, article: AnalyzedArticle) -> str:
        normalized = cls.normalize_url(article.source_url or "")
        raw = "|".join(
            [
                normalized,
                (article.source_name or "").strip().lower(),
                (article.title_zh or article.title_en or "").strip().lower(),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def classify_error(error: Exception) -> str:
        if isinstance(error, APIResponseError):
            status = int(getattr(error, "status", 0) or 0)
            code = str(getattr(error, "code", "")).lower()
            message = str(error).lower()
            if status in (401, 403) or "unauthorized" in message or "forbidden" in message:
                return "AUTH"
            if status == 429 or "rate" in code or "rate" in message:
                return "RATE_LIMIT"
            if status == 400 and ("validation" in message or "property" in message):
                return "SCHEMA"
            return "API"
        return "UNKNOWN"

    def get_existing_urls(self) -> set[str]:
        """Query database for all existing source URLs (for dedup)."""
        urls: set[str] = set()
        try:
            has_more = True
            start_cursor = None
            seen_cursors: set[str | None] = set()
            while has_more:
                if start_cursor in seen_cursors:
                    logger.warning("[NOTION] Cursor loop detected, stopping pagination")
                    break
                seen_cursors.add(start_cursor)

                body = {"page_size": 100, "filter_properties": ["原文链接"]}
                if start_cursor:
                    body["start_cursor"] = start_cursor

                resp = self.client.request(
                    path=f"databases/{self.database_id}/query",
                    method="POST",
                    body=body,
                )
                for page in resp.get("results", []):
                    props = page.get("properties", {})
                    url_prop = props.get("原文链接", {})
                    url = url_prop.get("url")
                    if url:
                        urls.add(self.normalize_url(url))

                has_more = bool(resp.get("has_more", False))
                start_cursor = resp.get("next_cursor")
        except Exception as e:
            logger.warning(f"[NOTION] Could not fetch existing URLs: {e}")
        return urls

    def create_page(self, article: AnalyzedArticle, today: str) -> None:
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
                "multi_select": self.parse_multi_select_tags(article.core_tech_points)
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
                "select": {"name": self.career_relevance(article)}
            },
        }

        children = self.build_page_body(article)

        try:
            self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=children,
            )
        except Exception as e:
            raise NotionDeliveryError(self.classify_error(e), str(e)) from e

    def parse_multi_select_tags(self, text: str) -> list[dict]:
        """Parse comma/semicolon separated text into Notion multi-select tags."""
        if not text:
            return []

        parts = re.split(r"[,;，；、/]", text)
        tags = []
        for part in parts:
            tag = part.strip()
            if tag and len(tag) < 100:
                tags.append({"name": tag})
        return tags[:10]

    def career_relevance(self, article: AnalyzedArticle) -> str:
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
        if signals >= 1:
            return "Medium"
        return "Low"

    def build_page_body(self, article: AnalyzedArticle) -> list[dict]:
        """Build Notion page content blocks for the article."""
        blocks = []

        blocks.append(self._heading2(article.title_en or article.title_zh))

        blocks.append(self._heading3("📝 摘要 / Summary"))
        if article.summary_zh:
            blocks.append(self._paragraph(f"🇨🇳 {article.summary_zh}"))
        if article.summary_en:
            blocks.append(self._paragraph(f"🇬🇧 {article.summary_en}"))

        if article.core_tech_points:
            blocks.append(self._heading3("🔬 核心技术"))
            blocks.append(self._paragraph(article.core_tech_points))

        if article.german_context:
            blocks.append(self._heading3("🏭 德国市场背景"))
            blocks.append(self._paragraph(article.german_context))

        if article.tool_stack:
            blocks.append(self._heading3("🛠️ 工具链"))
            blocks.append(self._paragraph(article.tool_stack))

        if article.hiring_signals:
            blocks.append(self._heading3("💼 招聘信号"))
            blocks.append(self._paragraph(article.hiring_signals))

        if article.interview_flip:
            blocks.append(self._heading3("💡 面试谈资"))
            blocks.append(self._paragraph(article.interview_flip))

        if article.theory_gap:
            blocks.append(self._heading3("📖 学术 vs 工业"))
            blocks.append(self._paragraph(article.theory_gap))

        blocks.append(self._divider())
        if article.source_url:
            blocks.append(self._paragraph(f"🔗 原文: {article.source_url}"))
        blocks.append(self._paragraph(f"📡 来源: {article.source_name}"))
        return blocks

    @staticmethod
    def _heading2(text: str) -> dict:
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    @staticmethod
    def _heading3(text: str) -> dict:
        return {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    @staticmethod
    def _paragraph(text: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    @staticmethod
    def _divider() -> dict:
        return {"object": "block", "type": "divider", "divider": {}}
