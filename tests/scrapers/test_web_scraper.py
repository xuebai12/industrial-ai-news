import pytest
from src.scrapers.web_scraper import _clean_text

class TestCleanText:
    """Test suite for the _clean_text helper function."""

    def test_basic_cleaning(self):
        """Test removal of HTML tags and whitespace normalization."""
        raw_text = "  <p>Hello   World!</p>  <br/> "
        expected = "Hello World!"
        assert _clean_text(raw_text) == expected

    def test_truncation(self):
        """Test text truncation to max_len."""
        text = "Hello World"
        assert _clean_text(text, max_len=5) == "Hello"
        assert _clean_text(text, max_len=100) == "Hello World"

    def test_empty_input(self):
        """Test handling of empty strings and None."""
        assert _clean_text("") == ""
        # The type hint says str, but passing None is a common edge case to handle safely
        assert _clean_text(None) == "" # type: ignore

    def test_whitespace_only(self):
        """Test handling of whitespace-only strings."""
        assert _clean_text("   \n\t   ") == ""

    def test_no_changes_needed(self):
        """Test handling of already clean text."""
        text = "Clean text"
        assert _clean_text(text) == text

    def test_unicode_handling(self):
        """Test handling of unicode characters."""
        text = "你好  World 🌍"
        expected = "你好 World 🌍"
        assert _clean_text(text) == expected

    def test_mixed_content(self):
        """Test handling of mixed content with multiple issues."""
        raw = "<div>  Title:  <b>Important</b>  </div>"
        expected = "Title: Important"
        assert _clean_text(raw) == expected
