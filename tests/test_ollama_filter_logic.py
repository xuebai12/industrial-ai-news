import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.models import Article
from src.filters import ollama_filter

class TestOllamaFilterLogic(unittest.TestCase):
    def setUp(self):
        # Create dummy articles
        self.articles = [
            Article(title="Keep Me", url="u1", source="s", content_snippet="c", language="en", category="t"),
            Article(title="Drop Me", url="u2", source="s", content_snippet="c", language="en", category="t"),
            Article(title="Maybe Keep Me", url="u3", source="s", content_snippet="c", language="en", category="t"),
        ]

    @patch('src.filters.ollama_filter.keyword_score')
    @patch('src.filters.ollama_filter.llm_relevance_check')
    def test_filter_logic(self, mock_llm, mock_kw):
        # Setup mocks
        mock_kw.side_effect = lambda a: (3, ['student']) # All pass keyword check

        def llm_side_effect(article):
            if "Keep" in article.title and "Maybe" not in article.title:
                return True
            if "Drop" in article.title:
                return False
            if "Maybe" in article.title:
                return None
            return False

        mock_llm.side_effect = llm_side_effect

        # Run filter
        # We need to ensure relevance score is set correctly.
        # keyword_score returns score, personas.
        # filter_articles sets article.relevance_score = score

        # However, for "Maybe Keep Me", we need score >= 2 for fallback logic.
        # keyword_score returns 3, so fallback logic applies (3 >= 2).

        # We need to mock MIN_RELEVANT_ARTICLES to 0 to avoid that logic interfering
        with patch('src.filters.ollama_filter.MIN_RELEVANT_ARTICLES', 0):
            result = ollama_filter.filter_articles(self.articles, skip_llm=False)

        # Verify
        # "Keep Me" -> True -> Kept
        # "Drop Me" -> False -> Dropped
        # "Maybe Keep Me" -> None, score 3 -> Kept (fallback)

        titles = [a.title for a in result]
        self.assertIn("Keep Me", titles)
        self.assertIn("Maybe Keep Me", titles)
        self.assertNotIn("Drop Me", titles)
        self.assertEqual(len(result), 2)

    @patch('src.filters.ollama_filter.keyword_score')
    @patch('src.filters.ollama_filter.llm_relevance_check')
    def test_filter_logic_fallback_fail(self, mock_llm, mock_kw):
        # Test case where Maybe article has low score

        def kw_side_effect(article):
            if "Maybe" in article.title:
                return 1, ['student'] # Low score < 2 but >= RELEVANCE_THRESHOLD (1)
            return 3, ['student']

        mock_kw.side_effect = kw_side_effect

        def llm_side_effect(article):
            if "Maybe" in article.title:
                return None
            return True # Others keep

        mock_llm.side_effect = llm_side_effect

        articles = [
            Article(title="Maybe Drop Me", url="u3", source="s", content_snippet="c", language="en", category="t"),
        ]

        with patch('src.filters.ollama_filter.MIN_RELEVANT_ARTICLES', 0):
            result = ollama_filter.filter_articles(articles, skip_llm=False)

        # "Maybe Drop Me" -> None, score 1 -> Dropped (fallback requires >= 2)
        self.assertEqual(len(result), 0)

    def test_negative_theory_without_industry_context_is_filtered(self):
        article = Article(
            title="Spatio-temporal dual-stage hypergraph theorem for reasoning benchmark",
            url="u4",
            source="s",
            content_snippet="Ablation study only on synthetic dataset and leaderboard.",
            language="en",
            category="research",
        )
        score, personas = ollama_filter.keyword_score(article)
        self.assertEqual(score, 0)
        self.assertEqual(personas, [])

    def test_negative_theory_with_industry_context_is_downweighted_not_blocked(self):
        article = Article(
            title="Hypergraph method for predictive maintenance in factory production line",
            url="u5",
            source="s",
            content_snippet="Industrial PLC and MES data are used for condition monitoring.",
            language="en",
            category="industry",
        )
        score, personas = ollama_filter.keyword_score(article)
        self.assertGreaterEqual(score, 1)

    def test_youtube_low_views_are_downweighted(self):
        high_view_article = Article(
            title="Industrial AI for factory quality inspection",
            url="https://www.youtube.com/watch?v=abc",
            source="YouTube RSS: Industrial AI",
            content_snippet="Machine vision for defect detection in production line.",
            language="en",
            category="industry",
            video_views=100,
        )
        low_view_article = Article(
            title="Industrial AI for factory quality inspection",
            url="https://www.youtube.com/watch?v=abc",
            source="YouTube RSS: Industrial AI",
            content_snippet="Machine vision for defect detection in production line.",
            language="en",
            category="industry",
            video_views=5,
        )
        high_score, _ = ollama_filter.keyword_score(high_view_article)
        low_score, _ = ollama_filter.keyword_score(low_view_article)
        self.assertLess(low_score, high_score)

    def test_hard_exclude_livestream_is_filtered(self):
        article = Article(
            title="Live stream Wuxi factory without subtitles | Schneider Electric",
            url="https://www.youtube.com/watch?v=live123",
            source="YouTube RSS: Schneider Electric",
            content_snippet="Livestream event recap from smart factory tour.",
            language="en",
            category="industry",
            video_views=1000,
        )
        score, personas = ollama_filter.keyword_score(article)
        self.assertEqual(score, 0)
        self.assertEqual(personas, [])

    def test_hard_exclude_mtp_news_is_filtered(self):
        article = Article(
            title="News about MTP",
            url="https://example.com/mtp",
            source="YouTube RSS: Beckhoff Automation",
            content_snippet="MTP update for modular process engineering.",
            language="en",
            category="industry",
        )
        score, personas = ollama_filter.keyword_score(article)
        self.assertEqual(score, 0)
        self.assertEqual(personas, [])

    def test_downweight_noise_keyword_reduces_score_not_hard_block(self):
        base_article = Article(
            title="Industrial AI sequence optimization for factory PLC line",
            url="https://example.com/base",
            source="s",
            content_snippet="Predictive maintenance and machine vision in production line.",
            language="en",
            category="industry",
        )
        noisy_article = Article(
            title="How to make a sequence in EAE v25.0 | Schneider Electric",
            url="https://example.com/noisy",
            source="s",
            content_snippet="Industrial AI sequence optimization for factory PLC line.",
            language="en",
            category="industry",
        )
        base_score, _ = ollama_filter.keyword_score(base_article)
        noisy_score, _ = ollama_filter.keyword_score(noisy_article)
        self.assertLess(noisy_score, base_score)
        self.assertGreaterEqual(noisy_score, 0)

    def test_press_contact_url_is_hard_filtered(self):
        article = Article(
            title="Industrial AI update",
            url="https://example.com/de/presse/pressekontakt",
            source="s",
            content_snippet="AI in manufacturing and predictive maintenance",
            language="de",
            category="industry",
        )
        score, personas = ollama_filter.keyword_score(article)
        self.assertEqual(score, 0)
        self.assertEqual(personas, [])

if __name__ == '__main__':
    unittest.main()
