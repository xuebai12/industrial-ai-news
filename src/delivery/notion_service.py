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
        self._parent_key: str | None = None
        self._parent_id: str | None = None

    def push_articles(self, articles: list[AnalyzedArticle], today: str) -> int:
        """
        Push analyzed articles to Notion database.
        Returns number of newly created entries.
        """
        existing_urls, existing_titles = self.get_existing_entries(articles)
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

    def get_existing_entries(
        self, candidates: list[AnalyzedArticle] | None = None
    ) -> tuple[set[str], set[str]]:
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
                logger.warning(
                    "[NOTION] No title property found in database schema, skip title dedupe"
                )

            # Strategy 1: Full Scan (Legacy)
            if candidates is None:
                self._fetch_and_process(
                    {"page_size": 100}, url_property, title_property, urls, titles
                )
                return urls, titles

            # Strategy 2: Recent + Targeted
            # 2a. Fetch Recent (past month)
            self._fetch_and_process(
                {
                    "page_size": 100,
                    "filter": {"timestamp": "created_time", "created_time": {"past_month": {}}},
                },
                url_property,
                title_property,
                urls,
                titles,
            )

            # 2b. Identify Missing
            missing_candidates = []
            for c in candidates:
                is_covered = False
                if c.source_url:
                    norm_url = self.normalize_url(c.source_url)
                    if norm_url in urls:
                        is_covered = True

                if not is_covered:
                    title_text = c.title_zh or c.title_en or ""
                    norm_title = title_text.strip().lower()
                    if norm_title and norm_title in titles:
                        is_covered = True

                if not is_covered:
                    missing_candidates.append(c)

            # 2c. Fetch Specific (for missing)
            if missing_candidates:
                batch_size = 10
                for i in range(0, len(missing_candidates), batch_size):
                    batch = missing_candidates[i : i + batch_size]
                    or_filters = []
                    for item in batch:
                        if url_property and item.source_url:
                            or_filters.append(
                                {"property": url_property, "url": {"equals": item.source_url}}
                            )
                        if title_property:
                            title_text = item.title_zh or item.title_en or ""
                            if title_text:
                                or_filters.append(
                                    {"property": title_property, "title": {"equals": title_text}}
                                )

                    if or_filters:
                        self._fetch_and_process(
                            {"page_size": 100, "filter": {"or": or_filters}},
                            url_property,
                            title_property,
                            urls,
                            titles,
                        )

        except Exception as e:
            logger.warning(f"[NOTION] Could not fetch existing URLs: {e}")
        return urls, titles

    def _process_page_results(
        self,
        page: dict,
        url_property: str | None,
        title_property: str | None,
        urls: set[str],
        titles: set[str],
    ) -> None:
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

    def _fetch_and_process(
        self,
        body: dict,
        url_property: str | None,
        title_property: str | None,
        urls: set[str],
        titles: set[str],
    ) -> None:
        has_more = True
        start_cursor = None
        seen_cursors: set[str | None] = set()

        query_body = body.copy()

        while has_more:
            if start_cursor in seen_cursors:
                logger.warning("[NOTION] Cursor loop detected, stopping pagination")
                break
            seen_cursors.add(start_cursor)

            if start_cursor:
                query_body["start_cursor"] = start_cursor
            elif "start_cursor" in query_body:
                del query_body["start_cursor"]

            parent_key, parent_id = self.get_parent_target()
            resp = self.query_entries(parent_key=parent_key, parent_id=parent_id, body=query_body)
            for page in resp.get("results", []):
                self._process_page_results(page, url_property, title_property, urls, titles)

            has_more = bool(resp.get("has_more", False))
            start_cursor = resp.get("next_cursor")

    def create_page(self, article: AnalyzedArticle, today: str) -> None:
        """Create a single Notion database entry with properties and page body."""
        schema = self.get_database_properties()
        properties = self.build_properties_from_schema(article=article, today=today, schema=schema)
        parent_key, parent_id = self.get_parent_target()

        children = self.build_page_body(article)

        try:
            self.client.pages.create(
                parent={parent_key: parent_id},
                properties=properties,
                children=children,
            )
        except Exception as e:
            raise NotionDeliveryError(self.classify_error(e), str(e)) from e

    def get_database_properties(self) -> dict[str, dict]:
        """Retrieve and cache database schema properties."""
        if self._database_properties is not None:
            return self._database_properties

        parent_key, parent_id, schema = self._resolve_target()
        self._parent_key = parent_key
        self._parent_id = parent_id
        self._database_properties = schema
        return self._database_properties

    def get_parent_target(self) -> tuple[str, str]:
        if self._parent_key and self._parent_id:
            return self._parent_key, self._parent_id
        self.get_database_properties()
        if not self._parent_key or not self._parent_id:
            return "database_id", self.database_id
        return self._parent_key, self._parent_id

    def _resolve_target(self) -> tuple[str, str, dict[str, dict]]:
        # Prefer modern Data Source API if the supplied ID is a data_source id.
        if hasattr(self.client, "data_sources"):
            try:
                ds = self.client.data_sources.retrieve(data_source_id=self.database_id)
                ds_props = ds.get("properties", {}) or {}
                if ds_props:
                    return "data_source_id", self.database_id, ds_props
            except Exception:
                pass

        # Fallback to legacy database API.
        db = self.client.databases.retrieve(database_id=self.database_id)
        db_props = db.get("properties", {}) or {}
        if db_props:
            return "database_id", self.database_id, db_props

        # New Notion API may return data_sources under a database object.
        for ds in db.get("data_sources", []) or []:
            ds_id = str(ds.get("id", "")).strip()
            if not ds_id:
                continue
            try:
                ds_detail = self.client.data_sources.retrieve(data_source_id=ds_id)
                ds_props = ds_detail.get("properties", {}) or {}
                if ds_props:
                    return "data_source_id", ds_id, ds_props
            except Exception:
                continue

        return "database_id", self.database_id, {}

    def query_entries(self, parent_key: str, parent_id: str, body: dict) -> dict:
        if parent_key == "data_source_id" and hasattr(self.client, "data_sources"):
            return self.client.data_sources.query(data_source_id=parent_id, **body)
        return self.client.request(
            path=f"databases/{parent_id}/query",
            method="POST",
            body=body,
        )

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
    def find_property_name(
        schema: dict[str, dict], candidates: tuple[str, ...], expected_types: tuple[str, ...]
    ) -> str | None:
        for name in candidates:
            meta = schema.get(name, {})
            if meta.get("type") in expected_types:
                return name
        for name, meta in schema.items():
            if meta.get("type") in expected_types:
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

    def build_properties_from_schema(
        self, article: AnalyzedArticle, today: str, schema: dict[str, dict]
    ) -> dict[str, dict]:
        title_property = self.find_title_property_name(schema)
        if not title_property:
            raise NotionDeliveryError("SCHEMA", "No title property found in Notion schema")

        title_text = article.title_zh or article.title_en or "Untitled"
        properties: dict[str, dict] = {
            title_property: {"title": [{"text": {"content": title_text[:2000]}}]}
        }

        category_name = self.find_property_name(
            schema,
            candidates=("类别", "Category", "category"),
            expected_types=("select", "multi_select", "rich_text"),
        )
        if category_name:
            kind = schema.get(category_name, {}).get("type")
            if kind == "select":
                properties[category_name] = {"select": {"name": article.category_tag or "Other"}}
            elif kind == "multi_select":
                properties[category_name] = {
                    "multi_select": self.parse_multi_select_tags(article.category_tag)
                }
            elif kind == "rich_text":
                properties[category_name] = {
                    "rich_text": [{"text": {"content": (article.category_tag or "Other")[:2000]}}]
                }

        summary_name = self.find_property_name(
            schema,
            candidates=("AI 摘要", "摘要", "Summary", "summary"),
            expected_types=("rich_text",),
        )
        if summary_name and (article.summary_zh or article.summary_en):
            properties[summary_name] = {
                "rich_text": [
                    {"text": {"content": ((article.summary_zh or article.summary_en)[:2000])}}
                ]
            }

        core_tech_name = self.find_property_name(
            schema,
            candidates=("核心技术", "Core Tech", "core_tech_points"),
            expected_types=("multi_select", "rich_text"),
        )
        if core_tech_name and article.core_tech_points:
            kind = schema.get(core_tech_name, {}).get("type")
            if kind == "multi_select":
                properties[core_tech_name] = {
                    "multi_select": self.parse_multi_select_tags(article.core_tech_points)
                }
            elif kind == "rich_text":
                properties[core_tech_name] = {
                    "rich_text": [{"text": {"content": article.core_tech_points[:2000]}}]
                }

        source_name = self.find_property_name(
            schema,
            candidates=("来源/机构", "来源", "Source", "source_name"),
            expected_types=("select", "rich_text"),
        )
        if source_name:
            kind = schema.get(source_name, {}).get("type")
            source_value = article.source_name or "Unknown"
            if kind == "select":
                properties[source_name] = {"select": {"name": source_value}}
            elif kind == "rich_text":
                properties[source_name] = {"rich_text": [{"text": {"content": source_value[:2000]}}]}

        url_property = self.find_url_property_name(schema)
        if url_property and article.source_url:
            properties[url_property] = {"url": article.source_url}

        date_name = self.find_property_name(
            schema,
            candidates=("日期", "Date", "Published Date", "publish_date"),
            expected_types=("date",),
        )
        if date_name:
            properties[date_name] = {"date": {"start": today}}

        tool_stack_name = self.find_property_name(
            schema,
            candidates=("工具链", "Tool Stack", "tool_stack"),
            expected_types=("rich_text",),
        )
        if tool_stack_name and article.tool_stack:
            properties[tool_stack_name] = {
                "rich_text": [{"text": {"content": article.tool_stack[:2000]}}]
            }

        return properties

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
