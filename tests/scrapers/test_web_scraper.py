
import pytest
import sys
import os

# Ensure src is in path if running from test file directly (though pytest usually handles this)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.scrapers.web_scraper import _clean_text

class TestCleanText:
    def test_basic_stripping(self):
        assert _clean_text("<p>Hello</p>") == "Hello"
        assert _clean_text("<div><p>Hello</p></div>") == "Hello"

    def test_malformed_tags(self):
        # Current regex fails this: <div title='>'>Hello</div> -> '>Hello'
        # BeautifulSoup should handle it: -> Hello
        # Note: This test is expected to fail with the vulnerable implementation
        assert _clean_text("<div title='>'>Hello</div>") == "Hello"

    def test_script_stripping(self):
        # Current regex: <script>alert(1)</script> -> alert(1)
        # BeautifulSoup (html.parser) should strip script content.
        # Note: This test might fail with the vulnerable implementation if it returns "alert(1)"
        result = _clean_text("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "alert(1)" not in result

    def test_style_stripping(self):
        # BeautifulSoup should strip style content.
        result = _clean_text("<style>body { color: red; }</style>")
        assert "body {" not in result
        assert "color: red" not in result

    def test_whitespace_normalization(self):
        text = "  Hello   \n  World  "
        assert _clean_text(text) == "Hello World"

    def test_truncation(self):
        text = "A" * 600
        assert len(_clean_text(text, max_len=500)) == 500

    def test_none_input(self):
        # Although type hint says str, handling None gracefully is good practice if implemented
        # The current implementation handles "if not text: return ''" which covers None
        assert _clean_text(None) == "" # type: ignore
        assert _clean_text("") == ""
