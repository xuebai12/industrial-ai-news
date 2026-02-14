import unittest
from unittest.mock import MagicMock

from src.delivery.notion_service import AnalyzedArticle, NotionDeliveryService


class TestNotionDedupe(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.service = NotionDeliveryService(self.mock_client, "fake_db_id")
        # Mock database schema discovery
        self.service._database_properties = {
            "URL": {"type": "url"},
            "Title": {"type": "title"}
        }
        self.service._parent_key = "database_id"
        self.service._parent_id = "fake_db_id"

        # Mock finding properties
        self.service.find_url_property_name = MagicMock(return_value="URL")
        self.service.find_title_property_name = MagicMock(return_value="Title")

    def create_mock_article(self, url, title_zh):
        return AnalyzedArticle(
            category_tag="test",
            title_zh=title_zh,
            title_en="Test Title EN",
            title_de="Test Title DE",
            core_tech_points="tech",
            german_context="context",
            source_name="source",
            source_url=url,
            summary_zh="summary",
            summary_en="summary",
            summary_de="summary",
            original=MagicMock()
        )

    def test_check_is_duplicate_false(self):
        """Test that check_is_duplicate returns False when no entries found."""
        # Mock query_entries to return empty results
        self.service.query_entries = MagicMock(return_value={"results": []})

        article = self.create_mock_article("http://example.com", "Test Title")

        is_dup = self.service.check_is_duplicate(article)

        self.assertFalse(is_dup)

        # Verify call arguments
        self.service.query_entries.assert_called_once()
        _, kwargs = self.service.query_entries.call_args

        expected_filter = {
            "or": [
                {"property": "URL", "url": {"equals": "http://example.com"}},
                {"property": "Title", "title": {"equals": "Test Title"}},
                {"property": "Title", "title": {"equals": "Test Title EN"}}
            ]
        }
        # Note: order of OR list might vary but list equality checks order in Python.
        # Let's check filter structure more robustly if needed.
        self.assertEqual(kwargs['body']['filter'], expected_filter)
        self.assertEqual(kwargs['body']['page_size'], 1)

    def test_check_is_duplicate_true(self):
        """Test that check_is_duplicate returns True when entry found."""
        # Mock query_entries to return one result
        self.service.query_entries = MagicMock(return_value={"results": [{"id": "page_id"}]})

        article = self.create_mock_article("http://example.com", "Test Title")

        is_dup = self.service.check_is_duplicate(article)

        self.assertTrue(is_dup)

    def test_check_is_duplicate_no_url(self):
        """Test check_is_duplicate with no URL."""
        self.service.query_entries = MagicMock(return_value={"results": []})

        article = self.create_mock_article("", "Test Title")

        self.service.check_is_duplicate(article)

        _, kwargs = self.service.query_entries.call_args
        # Should only filter by title (ZH and EN)
        expected_filter = {
            "or": [
                {"property": "Title", "title": {"equals": "Test Title"}},
                {"property": "Title", "title": {"equals": "Test Title EN"}}
            ]
        }
        self.assertEqual(kwargs['body']['filter'], expected_filter)

    def test_push_articles_calls_check(self):
        """Test that push_articles calls check_is_duplicate."""
        # Mock check_is_duplicate
        self.service.check_is_duplicate = MagicMock(side_effect=[False, True])
        self.service.create_page = MagicMock()

        articles = [
            self.create_mock_article("u1", "t1"),
            self.create_mock_article("u2", "t2")
        ]

        pushed_count = self.service.push_articles(articles, "2023-10-27")

        # 1st article not duplicate -> pushed
        # 2nd article duplicate -> skipped
        self.assertEqual(pushed_count, 1)
        self.assertEqual(self.service.check_is_duplicate.call_count, 2)
        self.service.create_page.assert_called_once()

if __name__ == '__main__':
    unittest.main()
