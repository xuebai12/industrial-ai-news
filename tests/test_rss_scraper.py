from datetime import datetime
from src.scrapers.rss_scraper import get_content_snippet, parse_date

def test_get_content_snippet_html_stripping():
    """Test that HTML tags are stripped from the content."""
    entry = {"content": [{"value": "<p>Hello <b>World</b></p>"}]}
    snippet = get_content_snippet(entry)
    assert snippet == "Hello World"

def test_get_content_snippet_whitespace():
    """Test that whitespace is normalized."""
    entry = {"content": [{"value": "  Hello   \n World  "}]}
    snippet = get_content_snippet(entry)
    assert snippet == "Hello World"

def test_get_content_snippet_priority():
    """Test the priority: content > summary > description."""
    # content has priority
    entry1 = {
        "content": [{"value": "Content"}],
        "summary": "Summary",
        "description": "Description"
    }
    assert get_content_snippet(entry1) == "Content"

    # summary fallback
    entry2 = {
        "summary": "Summary",
        "description": "Description"
    }
    assert get_content_snippet(entry2) == "Summary"

    # description fallback
    entry3 = {
        "description": "Description"
    }
    assert get_content_snippet(entry3) == "Description"

    # empty
    entry4 = {}
    assert get_content_snippet(entry4) == ""

def test_get_content_snippet_max_len():
    """Test that the snippet is truncated to max_len."""
    entry = {"content": [{"value": "A" * 100}]}
    snippet = get_content_snippet(entry, max_len=10)
    assert len(snippet) == 10
    assert snippet == "A" * 10

def test_parse_date():
    """Test date parsing from different fields."""
    # Test published_parsed
    entry1 = {"published_parsed": (2023, 10, 27, 12, 0, 0, 0, 0, 0)}
    assert parse_date(entry1) == datetime(2023, 10, 27, 12, 0, 0)

    # Test updated_parsed
    entry2 = {"updated_parsed": (2023, 10, 28, 12, 0, 0, 0, 0, 0)}
    assert parse_date(entry2) == datetime(2023, 10, 28, 12, 0, 0)

    # Test priority (published > updated)
    entry3 = {
        "published_parsed": (2023, 10, 27, 12, 0, 0, 0, 0, 0),
        "updated_parsed": (2023, 10, 28, 12, 0, 0, 0, 0, 0)
    }
    assert parse_date(entry3) == datetime(2023, 10, 27, 12, 0, 0)

    # Test None
    entry4 = {}
    assert parse_date(entry4) is None
