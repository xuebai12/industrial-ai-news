from unittest.mock import MagicMock, patch
import pytest
import os
from src.scrapers.youtube_scraper import scrape_youtube, scrape_youtube_focus_channels

@patch("src.scrapers.youtube_scraper.build")
@patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake_key"})
def test_scrape_youtube_success(mock_build):
    # Mock the API response
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube
    
    mock_search = mock_youtube.search.return_value
    mock_list = mock_search.list.return_value
    
    mock_response = {
        "items": [
            {
                "id": {"videoId": "12345"},
                "snippet": {
                    "title": "Industrial AI Video",
                    "description": "A video about AI in factories.",
                    "publishedAt": "2023-10-27T10:00:00Z"
                }
            }
        ]
    }
    mock_list.execute.return_value = mock_response
    
    # Run scraper
    results = scrape_youtube("Test Source", "test query", "en", "industry", 5)
    
    assert len(results) == 1
    video = results[0]
    assert video.title == "Industrial AI Video"
    assert video.url == "https://www.youtube.com/watch?v=12345"
    assert video.source == "Test Source"
    assert video.is_video is True

@patch("src.scrapers.youtube_scraper.build")
def test_scrape_youtube_no_key(mock_build):
    # Ensure no key in env
    with patch.dict(os.environ, {}, clear=True):
        results = scrape_youtube("Test Source", "query", "en", "industry")
        assert len(results) == 0
        mock_build.assert_not_called()

@patch("src.scrapers.youtube_scraper.build")
@patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake_key"})
def test_scrape_youtube_api_error(mock_build):
    # Mock API error
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube
    mock_youtube.search.return_value.list.return_value.execute.side_effect = Exception("API Error")
    
    results = scrape_youtube("Test Source", "query", "en", "industry")
    assert len(results) == 0


@patch("src.scrapers.youtube_scraper.build")
@patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake_key"})
def test_scrape_youtube_focus_channels_success(mock_build):
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube
    mock_list = mock_youtube.search.return_value.list

    # Return one video for first channel, duplicate + one new for second channel.
    resp1 = {
        "items": [
            {
                "id": {"videoId": "dup123"},
                "snippet": {
                    "title": "Focus Video A",
                    "description": "A",
                    "publishedAt": "2026-02-20T10:00:00Z",
                },
            }
        ]
    }
    resp2 = {
        "items": [
            {
                "id": {"videoId": "dup123"},
                "snippet": {
                    "title": "Focus Video A",
                    "description": "A",
                    "publishedAt": "2026-02-20T10:00:00Z",
                },
            },
            {
                "id": {"videoId": "new456"},
                "snippet": {
                    "title": "Focus Video B",
                    "description": "B",
                    "publishedAt": "2026-02-20T11:00:00Z",
                },
            },
        ]
    }
    mock_list.return_value.execute.side_effect = [resp1, resp2]

    results = scrape_youtube_focus_channels(
        name="Focus",
        query="industrial ai",
        language="en",
        category="industry",
        channel_ids=["ch1", "ch2"],
        max_items=5,
        region_code="US",
        video_duration="medium",
        safe_search="moderate",
    )

    assert len(results) == 2
    assert results[0].url == "https://www.youtube.com/watch?v=dup123"
    assert results[1].url == "https://www.youtube.com/watch?v=new456"
