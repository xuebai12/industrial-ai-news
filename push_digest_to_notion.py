#!/usr/bin/env python3
"""Push a generated digest markdown file to Notion database."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from notion_client import Client

from src.delivery.notion_service import NotionDeliveryService
from src.models import AnalyzedArticle, Article


@dataclass
class DigestEntry:
    category: str
    title_zh: str
    title_en: str
    summary_zh: str
    summary_en: str
    core_tech: str
    german_context: str
    source_name: str
    source_url: str


def _extract(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return ""
    return match.group(1).strip()


def parse_digest(content: str) -> list[DigestEntry]:
    parts = re.split(r"\n---\n\n### ", content)
    entries: list[DigestEntry] = []
    for part in parts[1:]:
        block = "### " + part
        heading = _extract(r"^### \[(.*?)\]\s*(.+)$", block)
        if not heading:
            continue
        heading_match = re.search(r"^### \[(.*?)\]\s*(.+)$", block, flags=re.M)
        if not heading_match:
            continue
        category = heading_match.group(1).strip()
        title_zh = heading_match.group(2).strip()

        title_en = _extract(r"^\*(.*?)\*$", block)
        summary_zh = _extract(r"\*\*🇨🇳 摘要：\*\*\s*(.+?)(?:\n\n|\n🔬)", block)
        summary_en = _extract(r"\*\*🇬🇧 Summary:\*\*\s*(.+?)(?:\n\n|\n🔬)", block)
        core_tech = _extract(r"🔬 \*\*核心技术：\*\*\s*(.+?)(?:\n\n|\n🏭)", block)
        german_context = _extract(r"🏭 \*\*应用背景：\*\*\s*(.+?)(?:\n\n|\n>)", block)

        source_match = re.search(
            r"📎 来源：\s*(.+?)\s*\|\s*\[点击查看原文\]\((https?://[^)]+)\)",
            block,
            flags=re.S,
        )
        source_name = source_match.group(1).strip() if source_match else "Unknown"
        source_url = source_match.group(2).strip() if source_match else ""

        entries.append(
            DigestEntry(
                category=category or "Other",
                title_zh=title_zh or "Untitled",
                title_en=title_en or title_zh or "Untitled",
                summary_zh=summary_zh,
                summary_en=summary_en,
                core_tech=core_tech,
                german_context=german_context,
                source_name=source_name,
                source_url=source_url,
            )
        )
    return entries


def to_analyzed(entry: DigestEntry) -> AnalyzedArticle:
    original = Article(
        title=entry.title_en or entry.title_zh,
        url=entry.source_url,
        source=entry.source_name,
        content_snippet=entry.summary_en or entry.summary_zh,
        language="en",
        category=entry.category,
    )
    return AnalyzedArticle(
        category_tag=entry.category,
        title_zh=entry.title_zh,
        title_en=entry.title_en,
        title_de=entry.title_en,
        core_tech_points=entry.core_tech,
        german_context=entry.german_context,
        source_name=entry.source_name,
        source_url=entry.source_url,
        summary_zh=entry.summary_zh,
        summary_en=entry.summary_en,
        summary_de=entry.summary_en,
        tool_stack="",
        simple_explanation="",
        technician_analysis_de="",
        target_personas=[],
        original=original,
    )


def infer_date(path: Path) -> str:
    match = re.search(r"digest-(\d{4}-\d{2}-\d{2})", path.name)
    if match:
        return match.group(1)
    return "1970-01-01"


def main() -> int:
    parser = argparse.ArgumentParser(description="Push digest markdown to Notion")
    parser.add_argument("digest_path", help="Path to digest markdown file")
    parser.add_argument("--date", dest="digest_date", default="", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

    load_dotenv()
    notion_api_key = os.getenv("NOTION_API_KEY", "")
    notion_database_id = os.getenv("NOTION_DATABASE_ID", "")
    if not notion_api_key or not notion_database_id:
        raise SystemExit("Missing NOTION_API_KEY or NOTION_DATABASE_ID")

    digest_path = Path(args.digest_path)
    content = digest_path.read_text(encoding="utf-8")
    entries = parse_digest(content)
    if not entries:
        raise SystemExit(f"No entries parsed from {digest_path}")

    articles = [to_analyzed(item) for item in entries]
    digest_date = args.digest_date or infer_date(digest_path)

    client = Client(auth=notion_api_key)
    service = NotionDeliveryService(client=client, database_id=notion_database_id)
    pushed = service.push_articles(articles, digest_date)
    print(f"Parsed: {len(entries)} | Pushed: {pushed} | Date: {digest_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
