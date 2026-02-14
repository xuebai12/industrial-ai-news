import pytest
from src.scrapers.web_scraper import _make_absolute

def test_make_absolute_absolute_url():
    """Test that absolute URLs are returned as is."""
    assert _make_absolute("https://example.com/page", "https://example.com") == "https://example.com/page"
    assert _make_absolute("http://example.com/page", "https://example.com") == "http://example.com/page"

def test_make_absolute_relative_url():
    """Test that relative URLs are joined with the base URL."""
    # Simple relative path
    assert _make_absolute("/page", "https://example.com") == "https://example.com/page"

    # Relative path without leading slash
    assert _make_absolute("page", "https://example.com/") == "https://example.com/page"

    # Base URL without trailing slash
    assert _make_absolute("page", "https://example.com") == "https://example.com/page"
