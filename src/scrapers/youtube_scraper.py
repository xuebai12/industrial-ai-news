"""YouTube Scraper for accessing YouTube Data API v3."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


def _build_search_request_kwargs(
    *,
    query: str,
    language: str,
    max_items: int,
    region_code: str,
    video_duration: str,
    safe_search: str,
    published_after: str,
    channel_id: str = "",
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after,
        "maxResults": max_items,
        "relevanceLanguage": language,
        "videoDuration": video_duration,
        "safeSearch": safe_search,
    }
    if region_code:
        kwargs["regionCode"] = region_code
    if channel_id:
        kwargs["channelId"] = channel_id
    return kwargs


def _extract_videos(items: list[dict[str, Any]], *, name: str, language: str, category: str) -> list["DataWrapper"]:
    videos: list[DataWrapper] = []
    for item in items:
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        if not video_id:
            continue
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_data = {
            "source": name,
            "source_name": name,
            "title": snippet.get("title", ""),
            "url": video_url,
            "source_url": video_url,
            "published_date": snippet.get("publishedAt", ""),
            "content": snippet.get("description", ""),
            "description": snippet.get("description", ""),
            "language": language,
            "category": category,
            "source_type": "youtube",
            "is_video": True,
        }
        videos.append(DataWrapper(video_data))
    return videos


def _dedupe_videos(videos: list["DataWrapper"]) -> list["DataWrapper"]:
    seen: set[str] = set()
    result: list[DataWrapper] = []
    for item in videos:
        key = getattr(item, "url", "") or getattr(item, "source_url", "")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def scrape_youtube_focus_channels(
    *,
    name: str,
    query: str,
    language: str,
    category: str,
    channel_ids: list[str],
    max_items: int = 5,
    region_code: str = "",
    video_duration: str = "medium",
    safe_search: str = "moderate",
) -> list[dict[str, Any]]:
    """Search recent videos from focus channels first, then merge and dedupe."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("[SCRAPE] YOUTUBE_API_KEY not found. Skipping YouTube source.")
        return []
    if not channel_ids:
        return []

    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        published_after = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat("T").replace("+00:00", "Z")
        per_channel = max(1, min(5, max_items))
        merged: list[DataWrapper] = []
        for channel_id in channel_ids:
            kwargs = _build_search_request_kwargs(
                query=query,
                language=language,
                max_items=per_channel,
                region_code=region_code,
                video_duration=video_duration,
                safe_search=safe_search,
                published_after=published_after,
                channel_id=channel_id,
            )
            response = youtube.search().list(**kwargs).execute()
            merged.extend(_extract_videos(response.get("items", []), name=name, language=language, category=category))

        deduped = _dedupe_videos(merged)[:max_items]
        logger.info(
            "[SCRAPE] YouTube '%s' focus channels found %s videos (channels=%s, region=%s).",
            name,
            len(deduped),
            len(channel_ids),
            region_code or "global",
        )
        return deduped
    except Exception as e:
        logger.error(f"[SCRAPE] YouTube focus-channel search failed for '{name}': {e}")
        return []


def scrape_youtube(
    name: str,
    url: str,
    language: str,
    category: str,
    max_items: int = 5,
    region_code: str = "",
    video_duration: str = "medium",
    safe_search: str = "moderate",
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
        region_code: YouTube regionCode (e.g. "US", "DE"), optional.
        video_duration: "any" | "short" | "medium" | "long".
        safe_search: "none" | "moderate" | "strict".

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

        request_kwargs = _build_search_request_kwargs(
            query=url,
            language=language,
            max_items=max_items,
            region_code=region_code,
            video_duration=video_duration,
            safe_search=safe_search,
            published_after=published_after,
        )

        request = youtube.search().list(**request_kwargs)
        response = request.execute()

        videos = _extract_videos(
            response.get("items", []),
            name=name,
            language=language,
            category=category,
        )

        logger.info(
            "[SCRAPE] YouTube '%s' found %s videos (region=%s, duration=%s, safeSearch=%s).",
            name,
            len(videos),
            region_code or "global",
            video_duration,
            safe_search,
        )
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
