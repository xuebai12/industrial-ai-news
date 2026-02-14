import unittest
from unittest.mock import MagicMock, patch
import requests
from src.scrapers.web_scraper import (
    _clean_text,
    _make_absolute,
    scrape_generic_web,
    _is_observation_disabled,
    _update_observation_status,
)
from src.models import Article

class TestWebScraper(unittest.TestCase):

    # --- Tests for Helper Functions ---

    def test_clean_text_removes_html_tags(self):
        """Test that HTML tags are removed from text."""
        raw_text = "<p>This is <b>bold</b> text.</p>"
        cleaned = _clean_text(raw_text)
        self.assertEqual(cleaned, "This is bold text.")

    def test_clean_text_truncates_long_text(self):
        """Test that text is truncated to the specified maximum length."""
        long_text = "a" * 100
        cleaned = _clean_text(long_text, max_len=50)
        self.assertEqual(len(cleaned), 50)
        self.assertEqual(cleaned, "a" * 50)

    def test_clean_text_handles_empty_input(self):
        """Test that empty or None input returns an empty string."""
        self.assertEqual(_clean_text(""), "")
        self.assertEqual(_clean_text(None), "")

    def test_clean_text_normalizes_whitespace(self):
        """Test that extra whitespace is removed."""
        text = "  Hello   World  \n New Line "
        cleaned = _clean_text(text)
        self.assertEqual(cleaned, "Hello World New Line")

    def test_make_absolute_returns_absolute_url_as_is(self):
        """Test that an absolute URL is returned unchanged."""
        url = "https://example.com/page"
        base_url = "https://example.com"
        self.assertEqual(_make_absolute(url, base_url), url)

    def test_make_absolute_joins_relative_url(self):
        """Test that a relative URL is correctly joined with the base URL."""
        url = "/page"
        base_url = "https://example.com"
        self.assertEqual(_make_absolute(url, base_url), "https://example.com/page")

        url_no_slash = "page"
        base_url_slash = "https://example.com/"
        self.assertEqual(_make_absolute(url_no_slash, base_url_slash), "https://example.com/page")

    # --- Tests for Observation Logic ---

    def test_is_observation_disabled(self):
        """Test logic for checking if a source is disabled."""
        state = {
            "source1": {"disabled": True},
            "source2": {"disabled": False}
        }
        self.assertTrue(_is_observation_disabled(state, "source1"))
        self.assertFalse(_is_observation_disabled(state, "source2"))
        self.assertFalse(_is_observation_disabled(state, "source3"))  # Not in state

    def test_update_observation_status_success_reset(self):
        """Test that a successful fetch resets the zero streak and enables the source."""
        # Mock OBSERVED_SOURCES to include 'test_source'
        with patch("src.scrapers.web_scraper.OBSERVED_SOURCES", {"test_source"}):
            state = {"test_source": {"zero_streak": 5, "disabled": True}}
            _update_observation_status(state, "test_source", fetched_count=10)

            self.assertEqual(state["test_source"]["zero_streak"], 0)
            self.assertFalse(state["test_source"]["disabled"])

    def test_update_observation_status_failure_increment(self):
        """Test that a failed fetch (0 items) increments the zero streak."""
        with patch("src.scrapers.web_scraper.OBSERVED_SOURCES", {"test_source"}):
            with patch("src.scrapers.web_scraper.ZERO_DISABLE_THRESHOLD", 3):
                state = {}

                # 1st failure
                _update_observation_status(state, "test_source", fetched_count=0)
                self.assertEqual(state["test_source"]["zero_streak"], 1)
                self.assertFalse(state.get("test_source", {}).get("disabled", False))

                # 2nd failure
                _update_observation_status(state, "test_source", fetched_count=0)
                self.assertEqual(state["test_source"]["zero_streak"], 2)

                # 3rd failure -> should disable
                _update_observation_status(state, "test_source", fetched_count=0)
                self.assertEqual(state["test_source"]["zero_streak"], 3)
                self.assertTrue(state["test_source"]["disabled"])

    def test_update_observation_status_ignored_source(self):
        """Test that sources not in OBSERVED_SOURCES are ignored."""
        with patch("src.scrapers.web_scraper.OBSERVED_SOURCES", {"other_source"}):
            state = {}
            _update_observation_status(state, "ignored_source", fetched_count=0)
            self.assertNotIn("ignored_source", state)

    # --- Tests for Scraping Logic ---

    @patch("src.scrapers.web_scraper.requests.get")
    def test_scrape_generic_web_success(self, mock_get):
        """Test successful scraping of articles."""
        html_content = """
        <html>
            <body>
                <div class="news-item">
                    <h2>Article One Title</h2>
                    <a href="/article/1">Read More</a>
                    <p class="summary">Summary of article one.</p>
                </div>
                <div class="news-item">
                    <h3>Article Two Title</h3>
                    <a href="https://other.com/article/2">Link</a>
                </div>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        articles = scrape_generic_web(
            source_name="Test Source",
            url="https://example.com",
            selector=".news-item",
            lang="en",
            category="TestCat"
        )

        self.assertEqual(len(articles), 2)

        # Check first article
        self.assertEqual(articles[0].title, "Article One Title")
        self.assertEqual(articles[0].url, "https://example.com/article/1")
        self.assertEqual(articles[0].content_snippet, "Summary of article one.")
        self.assertEqual(articles[0].source, "Test Source")
        self.assertEqual(articles[0].language, "en")
        self.assertEqual(articles[0].category, "TestCat")

        # Check second article
        self.assertEqual(articles[1].title, "Article Two Title")
        self.assertEqual(articles[1].url, "https://other.com/article/2")

    @patch("src.scrapers.web_scraper.requests.get")
    def test_scrape_generic_web_filtering(self, mock_get):
        """Test that articles with short titles or missing links are filtered out."""
        html_content = """
        <html>
            <body>
                <!-- Short title (< 5 chars) -->
                <div class="news-item">
                    <h2>Tiny</h2>
                    <a href="/valid">Link</a>
                </div>
                <!-- Missing link -->
                <div class="news-item">
                    <h2>Valid Title But No Link</h2>
                    <span>No link here</span>
                </div>
                <!-- Valid article -->
                <div class="news-item">
                    <h2>Valid Title</h2>
                    <a href="/valid">Link</a>
                </div>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        articles = scrape_generic_web("Test", "http://ex.com", ".news-item", "en", "Test")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Valid Title")

    @patch("src.scrapers.web_scraper.requests.get")
    def test_scrape_generic_web_network_error(self, mock_get):
        """Test that network errors are handled gracefully (log error, return empty list)."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.RequestException("Network Error")
        mock_get.return_value = mock_response

        # We expect the error to be logged (which we could assert with assertLogs)
        # and an empty list returned.
        with self.assertLogs(level='ERROR') as cm:
            articles = scrape_generic_web("Test", "http://ex.com", ".news-item", "en", "Test")
            self.assertEqual(articles, [])
            self.assertTrue(any("Failed to scrape Test" in log for log in cm.output))

    @patch("src.scrapers.web_scraper.requests.get")
    def test_scrape_generic_web_selector_fallback(self, mock_get):
        """Test scraping when title is not in standard tags but item is an anchor or has text."""
        # Case where the item itself is an anchor tag
        html_content = """
        <html>
            <body>
                <a class="card" href="/article">
                    Valid Title Here
                </a>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        articles = scrape_generic_web("Test", "http://ex.com", ".card", "en", "Test")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Valid Title Here")
        self.assertEqual(articles[0].url, "http://ex.com/article")

if __name__ == "__main__":
    unittest.main()
