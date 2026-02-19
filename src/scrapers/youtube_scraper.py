"""YouTube Scraper for accessing YouTube Data API v3."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


def scrape_youtube(
    name: str,
    url: str,
    language: str,
    category: str,
    max_items: int = 5,
) -> list[dict[str, Any]]:
    """
    Search YouTube for videos related to the given query (passed as url).
    
    Args:
        name: Name of the source (e.g., "YouTube Industrial AI").
        url: The search query string (e.g. "Industrial AI").
             Note: We misuse 'url' field in DataSource to pass the search query.
        language: Language code (e.g., "en", "de").
        category: Category string.
        max_items: Max videos to retrieve.

    Returns:
        List of dicts representing articles/videos.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("[SCRAPE] YOUTUBE_API_KEY not found. Skipping YouTube source.")
        return []

    try:
        youtube = build("youtube", "v3", developerKey=api_key)

        # Calculate publishedAfter date (e.g., last 24 hours)
        # For a daily digest, we might want videos from the last 24-48 hours.
        published_after = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat("T").replace("+00:00", "Z")

        request = youtube.search().list(
            part="snippet",
            q=url,  # using 'url' as the query
            type="video",
            order="date",
            publishedAfter=published_after,
            maxResults=max_items,
            relevanceLanguage=language,
        )
        response = request.execute()

        videos = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            video_id = item["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Map to our Article structure
            # Note: The main pipeline expects objects with attributes, or dicts?
            # Looking at main.py: getattr(article, "url", "") -> It expects objects.
            # But wait, scrape_rss returns objects? Let's check rss_scraper.py
            # If rss_scraper returns objects, we should too.
            # For now, let's return a SimpleNamespace or a dict and let the main pipeline handle it?
            # Let's check main.py again. It uses getattr. So objects are better.
            
            # Actually, let's define a simple class or use a dict and wrap it.
            # But wait, main.py uses getattr(article, "url", "") OR getattr(article, "source_url", "").
            # If I return a dict, getattr won't work on it unless I wrap it.
            # Let's see what scrape_rss returns.
            
            video_data = {
                "source": name,
                "source_name": name,
                "title": snippet["title"],
                "url": video_url,
                "source_url": video_url,
                "published_date": snippet["publishedAt"],
                "content": snippet["description"], # Description as content
                "description": snippet["description"],
                "language": language,
                "category": category,
                "source_type": "youtube",
                "is_video": True,
            }
            videos.append(DataWrapper(video_data))

        logger.info(f"[SCRAPE] YouTube '{name}' found {len(videos)} videos.")
        return videos

    except Exception as e:
        logger.error(f"[SCRAPE] YouTube search failed for '{name}': {e}")
        return []


class DataWrapper:
    """Simple wrapper to access dict keys as attributes."""
    def __init__(self, data):
        self._data = data
    
    def __getattr__(self, item):
        return self._data.get(item, "")
