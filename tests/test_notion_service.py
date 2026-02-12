from __future__ import annotations

from src.delivery.notion_service import NotionDeliveryService
from src.models import AnalyzedArticle, Article


class _Pages:
    def __init__(self):
        self.created = []

    def create(self, parent, properties, children):
        self.created.append({"parent": parent, "properties": properties, "children": children})


class _Client:
    def __init__(self, responses):
        self.responses = responses
        self.request_calls = 0
        self.pages = _Pages()

    def request(self, path, method, body):
        idx = self.request_calls
        self.request_calls += 1
        if idx < len(self.responses):
            return self.responses[idx]
        return {"results": [], "has_more": False, "next_cursor": None}


def _analyzed(url: str, title: str) -> AnalyzedArticle:
    raw = Article(
        title=title,
        url=url,
        source="src",
        content_snippet="snippet",
        language="en",
        category="industry",
    )
    return AnalyzedArticle(
        category_tag="AI",
        title_zh=title,
        title_en=title,
        core_tech_points="AAS",
        german_context="ctx",
        source_name="src",
        source_url=url,
        summary_zh="摘要",
        summary_en="summary",
        original=raw,
    )


def test_normalize_url_sorts_query_and_removes_fragment():
    normalized = NotionDeliveryService.normalize_url("https://x.com/a/?b=2&a=1#frag")
    assert normalized == "https://x.com/a?a=1&b=2"


def test_get_existing_urls_paginates_and_normalizes():
    client = _Client(
        [
            {
                "results": [
                    {"properties": {"原文链接": {"url": "https://x.com/a?b=2&a=1"}}},
                ],
                "has_more": True,
                "next_cursor": "c1",
            },
            {
                "results": [
                    {"properties": {"原文链接": {"url": "https://x.com/b"}}},
                ],
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )
    svc = NotionDeliveryService(client=client, database_id="db")
    urls = svc.get_existing_urls()
    assert "https://x.com/a?a=1&b=2" in urls
    assert "https://x.com/b" in urls


def test_push_articles_skips_existing_and_duplicate_hash():
    client = _Client(
        [
            {
                "results": [
                    {"properties": {"原文链接": {"url": "https://x.com/already"}}},
                ],
                "has_more": False,
                "next_cursor": None,
            }
        ]
    )
    svc = NotionDeliveryService(client=client, database_id="db")

    one = _analyzed("https://x.com/already", "old")
    two = _analyzed("https://x.com/new", "new")
    three = _analyzed("https://x.com/new/", "new")

    pushed = svc.push_articles([one, two, three], today="2026-02-12")
    assert pushed == 1
    assert len(client.pages.created) == 1
