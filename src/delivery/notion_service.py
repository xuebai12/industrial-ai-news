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
        self._database_properties: dict[str, dict] | None = None

    def push_articles(self, articles: list[AnalyzedArticle], today: str) -> int:
        """
        Push analyzed articles to Notion database.
        Returns number of newly created entries.
        """
        existing_urls, existing_titles = self.get_existing_entries()
        logger.info(
            "[NOTION] Found existing entries in database: urls=%s titles=%s",
            len(existing_urls),
            len(existing_titles),
        )

        pushed = 0
        seen_hashes: set[str] = set()
        for article in articles:
            normalized = self.normalize_url(article.source_url or "")
            if normalized and normalized in existing_urls:
                logger.info(f"[NOTION] Skip (duplicate url): {article.title_zh[:40]}")
                continue
            normalized_title = (article.title_zh or article.title_en or "").strip().lower()
            if normalized_title and normalized_title in existing_titles:
                logger.info(f"[NOTION] Skip (duplicate title): {article.title_zh[:40]}")
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

    def get_existing_entries(self) -> tuple[set[str], set[str]]:
        """Query database for existing URLs and titles (for cross-run dedupe)."""
        urls: set[str] = set()
        titles: set[str] = set()
        try:
            schema = self.get_database_properties()
            url_property = self.find_url_property_name(schema)
            title_property = self.find_title_property_name(schema)
            if not url_property:
                logger.warning("[NOTION] No URL property found in database schema, skip URL dedupe")
            if not title_property:
                logger.warning("[NOTION] No title property found in database schema, skip title dedupe")

            has_more = True
            start_cursor = None
            seen_cursors: set[str | None] = set()
            while has_more:
                if start_cursor in seen_cursors:
                    logger.warning("[NOTION] Cursor loop detected, stopping pagination")
                    break
                seen_cursors.add(start_cursor)

                body = {"page_size": 100}
                if start_cursor:
                    body["start_cursor"] = start_cursor

                resp = self.client.request(
                    path=f"databases/{self.database_id}/query",
                    method="POST",
                    body=body,
                )
                for page in resp.get("results", []):
                    props = page.get("properties", {})
                    if url_property:
                        url_prop = props.get(url_property, {})
                        url = url_prop.get("url")
                        if url:
                            urls.add(self.normalize_url(url))
                    if title_property:
                        title_prop = props.get(title_property, {})
                        title_items = title_prop.get("title", [])
                        title_text = "".join(
                            item.get("plain_text", "") for item in title_items if isinstance(item, dict)
                        ).strip()
                        if title_text:
                            titles.add(title_text.lower())

                has_more = bool(resp.get("has_more", False))
                start_cursor = resp.get("next_cursor")
        except Exception as e:
            logger.warning(f"[NOTION] Could not fetch existing URLs: {e}")
        return urls, titles

    def create_page(self, article: AnalyzedArticle, today: str) -> None:
        """Create a single Notion database entry with properties and page body."""
        schema = self.get_database_properties()
        title_property = self.find_title_property_name(schema) or "标题"
        url_property = self.find_url_property_name(schema) or "原文链接"

        all_properties = {
            title_property: {
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
            url_property: {
                "url": article.source_url or None
            },
            "日期": {
                "date": {"start": today}
            },
            "工具链": {
                "rich_text": [{"text": {"content": (article.tool_stack or "")[:2000]}}]
            },
        }
        properties = self.filter_existing_properties(all_properties, schema)

        children = self.build_page_body(article)

        try:
            self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=children,
            )
        except Exception as e:
            raise NotionDeliveryError(self.classify_error(e), str(e)) from e

    def get_database_properties(self) -> dict[str, dict]:
        """Retrieve and cache database schema properties."""
        if self._database_properties is not None:
            return self._database_properties

        db = self.client.databases.retrieve(database_id=self.database_id)
        self._database_properties = db.get("properties", {}) or {}
        return self._database_properties

    @staticmethod
    def find_title_property_name(schema: dict[str, dict]) -> str | None:
        """Find title property name from schema."""
        if "标题" in schema and schema.get("标题", {}).get("type") == "title":
            return "标题"
        for name, meta in schema.items():
            if meta.get("type") == "title":
                return name
        return None

    @staticmethod
    def find_url_property_name(schema: dict[str, dict]) -> str | None:
        """Find source URL property name from schema."""
        preferred = ("原文链接", "Source URL", "source_url", "URL", "url")
        for name in preferred:
            if schema.get(name, {}).get("type") == "url":
                return name
        for name, meta in schema.items():
            if meta.get("type") == "url":
                return name
        return None

    @staticmethod
    def filter_existing_properties(
        all_properties: dict[str, dict], schema: dict[str, dict]
    ) -> dict[str, dict]:
        """Keep only properties that exist in database schema."""
        if not schema:
            return all_properties

        known = {k: v for k, v in all_properties.items() if k in schema}
        missing = [k for k in all_properties if k not in schema]
        if missing:
            logger.warning("[NOTION] Missing properties in DB schema, skipped: %s", ", ".join(missing))
        return known

    def parse_multi_select_tags(self, text: str | list[str] | None) -> list[dict]:
        """Parse text/list input into Notion multi-select tags."""
        if not text:
            return []

        if isinstance(text, list):
            parts = [str(item).strip() for item in text if str(item).strip()]
        else:
            parts = re.split(r"[,;，；、/]", text)
        tags = []
        for part in parts:
            tag = part.strip()
            if tag and len(tag) < 100:
                tags.append({"name": tag})
        return tags[:10]

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

        if article.simple_explanation:
            blocks.append(self._heading3("💡 通俗解读 (Student View)"))
            blocks.append(self._paragraph(article.simple_explanation))

        if article.technician_analysis_de:
            blocks.append(self._heading3("🔧 Technician Analysis (DE)"))
            blocks.append(self._paragraph(article.technician_analysis_de))

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
