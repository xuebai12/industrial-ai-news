import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import types

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

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
    def test_filter_logic_score_gate(self, mock_kw):
        # score >= 3 -> kept; score < 3 -> dropped
        def kw_side_effect(article):
            if article.title == "Keep Me":
                return (5, ['student'])
            if article.title == "Maybe Keep Me":
                return (3, ['student'])
            return (2, ['student'])

        mock_kw.side_effect = kw_side_effect

        result = ollama_filter.filter_articles(self.articles, skip_llm=False)

        # Verify
        # score gate -> kept; below threshold -> dropped
        titles = [a.title for a in result]
        self.assertIn("Keep Me", titles)
        self.assertIn("Maybe Keep Me", titles)
        self.assertNotIn("Drop Me", titles)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].domain_tags)

    @patch('src.filters.ollama_filter.keyword_score')
    def test_filter_high_score_is_kept(self, mock_kw):
        mock_kw.side_effect = lambda a: (10, ['student'])
        articles = [Article(title="Maybe Drop Me", url="u3", source="s", content_snippet="c", language="en", category="t")]
        result = ollama_filter.filter_articles(articles, skip_llm=False)
        self.assertEqual(len(result), 1)

    @patch('src.filters.ollama_filter.keyword_score')
    def test_skip_llm_flag_does_not_change_score_gate(self, mock_kw):
        def kw_side_effect(article):
            if article.title == "Drop Me":
                return (2, ['student'])
            return (10, ['student'])

        mock_kw.side_effect = kw_side_effect
        result = ollama_filter.filter_articles(self.articles, skip_llm=True)
        titles = [a.title for a in result]
        self.assertIn("Keep Me", titles)
        self.assertIn("Maybe Keep Me", titles)
        self.assertNotIn("Drop Me", titles)

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

    def test_universal_robots_promo_is_hard_filtered(self):
        article = Article(
            title="Celebrating 20 years of Universal Robots · Built by us. Driven by you.",
            url="https://www.youtube.com/watch?v=urpromo",
            source="YouTube RSS: Universal Robots",
            content_snippet="Brand campaign and celebration video.",
            language="en",
            category="industry",
        )
        score, personas = ollama_filter.keyword_score(article)
        self.assertEqual(score, 0)
        self.assertEqual(personas, [])

    def test_universal_robots_technical_content_not_blocked_by_brand_only(self):
        article = Article(
            title="Universal Robots introduces AI-based vision for bin picking",
            url="https://www.youtube.com/watch?v=urtech",
            source="YouTube RSS: Universal Robots",
            content_snippet="Industrial AI and machine vision in robotic cells.",
            language="en",
            category="industry",
        )
        score, _ = ollama_filter.keyword_score(article)
        self.assertGreater(score, 0)

    def test_infer_domain_tags_single_domain(self):
        article = Article(
            title="OT cybersecurity hardening in ICS environments",
            url="https://example.com/cyber",
            source="s",
            content_snippet="IEC 62443 controls and vulnerability management for OT security.",
            language="en",
            category="security",
        )
        tags = ollama_filter._infer_domain_tags(article)
        self.assertIn("cybersecurity", tags)
        self.assertLessEqual(len(tags), 3)

    def test_infer_domain_tags_multi_domain_and_cap(self):
        article = Article(
            title="AI robots in automotive factory improve supply chain and energy efficiency",
            url="https://example.com/multi",
            source="s",
            content_snippet=(
                "Robotics cells in vehicle production optimize logistics, grid demand, "
                "and manufacturing throughput with predictive maintenance."
            ),
            language="en",
            category="industry",
        )
        tags = ollama_filter._infer_domain_tags(article)
        self.assertGreaterEqual(len(tags), 2)
        self.assertLessEqual(len(tags), 3)

    def test_infer_domain_tags_default_factory_when_no_match(self):
        article = Article(
            title="General update",
            url="https://example.com/general",
            source="s",
            content_snippet="Miscellaneous announcement without clear domain keywords.",
            language="en",
            category="news",
        )
        tags = ollama_filter._infer_domain_tags(article)
        self.assertEqual(tags, ["factory"])

    @patch('src.filters.ollama_filter.keyword_score')
    @patch('src.filters.ollama_filter.llm_relevance_check')
    def test_filter_articles_assigns_domain_tags_for_yes(self, mock_llm, mock_kw):
        mock_kw.side_effect = lambda a: (3, ['student'])
        mock_llm.side_effect = lambda a: True
        articles = [
            Article(
                title="Humanoid robot cell in automotive assembly",
                url="https://example.com/robot-auto",
                source="s",
                content_snippet="Robotics integration in vehicle factory line.",
                language="en",
                category="industry",
            )
        ]
        result = ollama_filter.filter_articles(articles, skip_llm=False)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].domain_tags)

if __name__ == '__main__':
    unittest.main()
