import unittest
from types import SimpleNamespace

from src.delivery.email_sender import render_digest
from src.models import AnalyzedArticle


def _article() -> AnalyzedArticle:
    return AnalyzedArticle(
        category_tag="AI",
        title_en="English Title",
        title_de="Deutscher Titel",
        german_context="In der Montagelinie wird KI fuer visuelle Qualitaetspruefung eingesetzt.",
        source_name="Source",
        source_url="https://example.com",
        summary_en="en summary",
        summary_de="de summary",
        tool_stack="Python",
        simple_explanation="Student-only simple explanation text.",
        technician_analysis_de="Wie ein Fruehwarnsystem: Das Modell erkennt Anomalien und loest Wartungsaktionen aus.",
    )


class TestTechnicianReadability(unittest.TestCase):
    def test_technician_uses_german_context_and_technician_analysis(self) -> None:
        article = _article()
        profile = SimpleNamespace(language="de", persona="technician")

        html = render_digest([article], today="2026-02-20", profile=profile)

        self.assertIn("In der Montagelinie wird KI", html)
        self.assertIn("Wie ein Fruehwarnsystem", html)
        self.assertNotIn("Student-only simple explanation text.", html)

    def test_student_uses_english_only_fields(self) -> None:
        article = _article()
        profile = SimpleNamespace(language="en", persona="student")

        html = render_digest([article], today="2026-02-20", profile=profile)

        self.assertIn("en summary", html)
        self.assertNotIn("中文标题", html)
        self.assertNotIn("Wie ein Fruehwarnsystem", html)
        self.assertNotIn("In der Montagelinie wird KI", html)
        self.assertNotIn("Student-only simple explanation text.", html)

    def test_student_persona_forces_english_even_with_de_language(self) -> None:
        article = _article()
        profile = SimpleNamespace(language="de", persona="student")

        html = render_digest([article], today="2026-02-20", profile=profile)

        self.assertIn("en summary", html)
        self.assertNotIn("Deutscher Titel", html)
        self.assertNotIn("Student-only simple explanation text.", html)

    def test_pending_articles_table_is_rendered(self) -> None:
        article = _article()
        profile = SimpleNamespace(language="de", persona="technician")
        pending = [
            {
                "category": "industry",
                "title": "Nicht analysierter Artikel 1",
                "url": "https://example.com/pending-1",
            }
        ]

        html = render_digest([article], today="2026-02-20", profile=profile, pending_articles=pending)

        self.assertIn("Weitere Relevante Artikel (nicht analysiert)", html)
        self.assertIn("Nicht analysierter Artikel 1", html)
        self.assertIn("industry", html)
        self.assertNotIn("score", html.lower())


if __name__ == "__main__":
    unittest.main()
