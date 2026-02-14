import unittest
from unittest.mock import MagicMock
from src.delivery.notion_service import NotionDeliveryService, NotionDeliveryError
from src.models import AnalyzedArticle

class TestNotionDeliveryService(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.service = NotionDeliveryService(self.mock_client, "db_id")

        # Mock initial db setup (bypass property fetching)
        self.service._database_properties = {"Title": {"type": "title"}, "URL": {"type": "url"}}
        self.service._parent_key = "database_id"
        self.service._parent_id = "db_id"

    def test_push_articles_success(self):
        # Mock get_existing_entries to return empty
        self.service.get_existing_entries = MagicMock(return_value=(set(), set()))

        articles = [
            AnalyzedArticle(
                category_tag="Test",
                title_zh=f"Title {i}",
                title_en=f"Title {i}",
                title_de=f"Title {i}",
                core_tech_points="",
                german_context="",
                source_name="",
                source_url=f"http://example.com/{i}",
                summary_zh="",
                summary_en="",
                summary_de="",
                original=None
            ) for i in range(5)
        ]

        pushed = self.service.push_articles(articles, "2023-01-01")
        self.assertEqual(pushed, 5)
        self.assertEqual(self.mock_client.pages.create.call_count, 5)

    def test_push_articles_skip_duplicate(self):
        # Mock existing URL
        self.service.get_existing_entries = MagicMock(
            return_value=({"http://example.com/0"}, set())
        )

        articles = [
            AnalyzedArticle(
                category_tag="Test",
                title_zh="Title 0",
                title_en="Title 0",
                title_de="Title 0",
                core_tech_points="",
                german_context="",
                source_name="",
                source_url="http://example.com/0", # Duplicate
                summary_zh="",
                summary_en="",
                summary_de="",
                original=None
            ),
            AnalyzedArticle(
                category_tag="Test",
                title_zh="Title 1",
                title_en="Title 1",
                title_de="Title 1",
                core_tech_points="",
                german_context="",
                source_name="",
                source_url="http://example.com/1",
                summary_zh="",
                summary_en="",
                summary_de="",
                original=None
            )
        ]

        pushed = self.service.push_articles(articles, "2023-01-01")
        self.assertEqual(pushed, 1)
        self.mock_client.pages.create.assert_called_once()
        # Verify it created the second one
        args, kwargs = self.mock_client.pages.create.call_args
        self.assertIn("Title 1", str(kwargs['properties']))

    def test_push_articles_fail_fast_auth(self):
        self.service.get_existing_entries = MagicMock(return_value=(set(), set()))

        articles = [
            AnalyzedArticle(
                category_tag="Test",
                title_zh=f"Title {i}",
                title_en=f"Title {i}",
                title_de=f"Title {i}",
                core_tech_points="",
                german_context="",
                source_name="",
                source_url=f"http://example.com/{i}",
                summary_zh="",
                summary_en="",
                summary_de="",
                original=None
            ) for i in range(3)
        ]

        # Simulate AUTH error on create_page
        # We mock create_page directly to avoid dealing with APIResponseError structure
        # ensuring we test the fail-fast logic in push_articles, not classify_error
        self.service.create_page = MagicMock(
            side_effect=NotionDeliveryError("AUTH", "Unauthorized")
        )

        with self.assertRaises(NotionDeliveryError) as cm:
            self.service.push_articles(articles, "2023-01-01")

        self.assertEqual(cm.exception.category, "AUTH")

    def test_push_articles_log_error_but_continue(self):
        self.service.get_existing_entries = MagicMock(return_value=(set(), set()))

        articles = [
            AnalyzedArticle(
                category_tag="Test",
                title_zh=f"Title {i}",
                title_en=f"Title {i}",
                title_de=f"Title {i}",
                core_tech_points="",
                german_context="",
                source_name="",
                source_url=f"http://example.com/{i}",
                summary_zh="",
                summary_en="",
                summary_de="",
                original=None
            ) for i in range(3)
        ]

        # Simulate a generic error for the second article
        def side_effect(*args, **kwargs):
            # args[0] is not passed (keyword args used in create_page)
            # parent, properties, children
            props = kwargs.get('properties', {})
            # Look for title in props
            # The structure is {title_property: {"title": ...}}
            # Let's check article title in text
            title_content = str(props)
            if "Title 1" in title_content:
                raise Exception("Random failure")
            return {}

        self.mock_client.pages.create.side_effect = side_effect

        pushed = self.service.push_articles(articles, "2023-01-01")
        # Should push 0 and 2. 1 fails. Total 2.
        self.assertEqual(pushed, 2)
        self.assertEqual(self.mock_client.pages.create.call_count, 3)

if __name__ == '__main__':
    unittest.main()
