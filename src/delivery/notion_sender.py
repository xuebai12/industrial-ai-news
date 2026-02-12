"""Compatibility facade for Notion delivery public API."""

from src.delivery.notion_controller import push_to_notion_controller
from src.delivery.notion_service import NotionDeliveryError
from src.models import AnalyzedArticle


def push_to_notion(articles: list[AnalyzedArticle], today: str | None = None) -> int:
    """Public entrypoint kept stable for backward compatibility."""
    try:
        return push_to_notion_controller(articles=articles, today=today)
    except NotionDeliveryError:
        raise
