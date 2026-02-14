
import time
import unittest
from unittest.mock import MagicMock

from src.delivery.notion_service import AnalyzedArticle, NotionDeliveryService


class TestNotionPerformance(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.service = NotionDeliveryService(self.mock_client, "fake_db_id")
        # Mock database properties schema
        self.service.get_database_properties = MagicMock(return_value={
            "原文链接": {"type": "url"},
            "标题": {"type": "title"}
        })
        self.service.get_parent_target = MagicMock(return_value=("database_id", "fake_db_id"))

    def test_get_existing_entries_full_scan(self):
        """Benchmark full scan performance by simulating pages."""
        # Simulate 10 pages of results (1000 items)

        pages = []
        for i in range(10):
            results = []
            for j in range(100):
                results.append({
                    "properties": {
                        "原文链接": {"url": f"http://example.com/page_{i}_{j}"},
                        "标题": {"title": [{"plain_text": f"Title {i} {j}"}]}
                    }
                })
            pages.append({
                "results": results,
                "has_more": i < 9,
                "next_cursor": f"cursor_{i}" if i < 9 else None
            })

        self.mock_client.request.side_effect = pages

        start_time = time.time()
        urls, titles = self.service.get_existing_entries(None) # None explicitly for legacy mode
        duration = time.time() - start_time

        print(f"\n[Baseline] Full scan of 10 pages took {duration:.4f}s")
        print(f"[Baseline] API calls: {self.mock_client.request.call_count}")

        self.assertEqual(self.mock_client.request.call_count, 10)
        self.assertEqual(len(urls), 1000)

    def test_get_existing_entries_recent_found(self):
        """Verify that if candidate is in recent entries, no specific query is made."""
        candidate = AnalyzedArticle(
            category_tag="Tag", title_zh="Zh", title_en="Recent Title", title_de="De",
            summary_zh="SumZh", summary_en="SumEn", summary_de="SumDe",
            core_tech_points="Core", german_context="Context", source_name="Source",
            source_url="http://example.com/recent", tool_stack="Tool",
            simple_explanation="Simple", technician_analysis_de="Tech"
        )

        # Mock recent query response
        recent_page = {
            "results": [{
                "properties": {
                    "原文链接": {"url": "http://example.com/recent"},
                    "标题": {"title": [{"plain_text": "Recent Title"}]}
                }
            }],
            "has_more": False
        }

        self.mock_client.request.return_value = recent_page

        urls, titles = self.service.get_existing_entries([candidate])

        # 1 call to query entries (recent)
        self.assertEqual(self.mock_client.request.call_count, 1)
        args, kwargs = self.mock_client.request.call_args
        self.assertIn("filter", kwargs["body"])
        self.assertIn("timestamp", kwargs["body"]["filter"]) # Check it is the recent query

        self.assertIn("http://example.com/recent", urls)

    def test_get_existing_entries_missing_fetched(self):
        """Verify that if candidate is missing from recent, specific query is made."""
        candidate = AnalyzedArticle(
            category_tag="Tag", title_zh="Zh", title_en="Old Title", title_de="De",
            summary_zh="SumZh", summary_en="SumEn", summary_de="SumDe",
            core_tech_points="Core", german_context="Context", source_name="Source",
            source_url="http://example.com/old", tool_stack="Tool",
            simple_explanation="Simple", technician_analysis_de="Tech"
        )

        # Mock recent query response (empty)
        recent_page = {"results": [], "has_more": False}

        # Mock specific query response (found)
        specific_page = {
            "results": [{
                "properties": {
                    "原文链接": {"url": "http://example.com/old"},
                    "标题": {"title": [{"plain_text": "Old Title"}]}
                }
            }],
            "has_more": False
        }

        self.mock_client.request.side_effect = [recent_page, specific_page]

        urls, titles = self.service.get_existing_entries([candidate])

        self.assertEqual(self.mock_client.request.call_count, 2)
        # First call: recent
        args1, kwargs1 = self.mock_client.request.call_args_list[0]
        self.assertIn("timestamp", kwargs1["body"]["filter"])

        # Second call: specific
        args2, kwargs2 = self.mock_client.request.call_args_list[1]
        self.assertIn("or", kwargs2["body"]["filter"]) # Check it is specific OR query

        self.assertIn("http://example.com/old", urls)

if __name__ == "__main__":
    unittest.main()
