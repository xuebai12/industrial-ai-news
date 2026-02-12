"""Controller layer for Notion delivery orchestration."""

import logging
from datetime import date

from notion_client import Client

from config import NOTION_API_KEY, NOTION_DATABASE_ID
from src.delivery.notion_service import NotionDeliveryError, NotionDeliveryService
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)


def push_to_notion_controller(
    articles: list[AnalyzedArticle], today: str | None = None
) -> int:
    """
    Controller entrypoint for Notion delivery.
    Checks configuration, prepares dependencies, and delegates to service.
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.warning("[NOTION] API key or Database ID not configured, skipping")
        return 0

    run_date = today or date.today().strftime("%Y-%m-%d")
    client = Client(auth=NOTION_API_KEY)
    service = NotionDeliveryService(client=client, database_id=NOTION_DATABASE_ID)
    try:
        return service.push_articles(articles=articles, today=run_date)
    except NotionDeliveryError as e:
        logger.error("[NOTION] Delivery failed: category=%s error=%s", e.category, e.message)
        raise
