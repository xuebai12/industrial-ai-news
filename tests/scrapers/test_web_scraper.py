import pytest
from src.scrapers.web_scraper import _make_absolute

class TestMakeAbsolute:

    def test_absolute_http(self):
        """Test URL that is already absolute with http."""
        url = "http://example.com/page"
        base = "http://example.com"
        assert _make_absolute(url, base) == url

    def test_absolute_https(self):
        """Test URL that is already absolute with https."""
        url = "https://example.com/page"
        base = "http://example.com"
        assert _make_absolute(url, base) == url

    def test_relative_root(self):
        """Test relative URL starting with /."""
        url = "/page"
        base = "http://example.com"
        assert _make_absolute(url, base) == "http://example.com/page"

    def test_relative_no_root(self):
        """Test relative URL without /."""
        url = "page"
        base = "http://example.com/"
        assert _make_absolute(url, base) == "http://example.com/page"

    def test_relative_no_root_base_no_slash(self):
        """Test relative URL without / and base without trailing slash."""
        # urljoin replaces the last path component if base doesn't end with /
        url = "page"
        base = "http://example.com/subdir"
        # 'http://example.com/subdir' + 'page' -> 'http://example.com/page'
        # This is standard urljoin behavior, we just verify it persists.
        assert _make_absolute(url, base) == "http://example.com/page"

    def test_relative_dot_dots(self):
        """Test relative URL with .."""
        url = "../page"
        base = "http://example.com/subdir/"
        assert _make_absolute(url, base) == "http://example.com/page"

    def test_protocol_relative(self):
        """Test protocol relative URL //."""
        url = "//cdn.example.com/lib.js"
        base = "https://example.com"
        # urljoin uses the scheme from base if url starts with //
        assert _make_absolute(url, base) == "https://cdn.example.com/lib.js"

    def test_empty_url(self):
        """Test empty URL."""
        url = ""
        base = "http://example.com/page"
        assert _make_absolute(url, base) == base

    def test_fragment_only(self):
        """Test fragment only URL."""
        url = "#section"
        base = "http://example.com/page"
        assert _make_absolute(url, base) == "http://example.com/page#section"

    def test_query_only(self):
        """Test query only URL."""
        url = "?q=test"
        base = "http://example.com/page"
        assert _make_absolute(url, base) == "http://example.com/page?q=test"
