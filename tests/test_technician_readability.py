import unittest
from types import SimpleNamespace

from src.delivery.email_sender import render_digest
from src.models import AnalyzedArticle


def _article() -> AnalyzedArticle:
    return AnalyzedArticle(
        category_tag="AI",
        title_zh="中文标题",
        title_en="English Title",
        title_de="Deutscher Titel",
        core_tech_points="Kernel details for mechanism fallback.",
        german_context="In der Montagelinie wird KI fuer visuelle Qualitaetspruefung eingesetzt.",
        source_name="Source",
        source_url="https://example.com",
        summary_zh="zh summary",
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

    def test_student_keeps_simple_explanation_path(self) -> None:
        article = _article()
        profile = SimpleNamespace(language="zh", persona="student")

        html = render_digest([article], today="2026-02-20", profile=profile)

        self.assertIn("Student-only simple explanation text.", html)
        self.assertNotIn("Wie ein Fruehwarnsystem", html)

    def test_non_technician_mode_behavior_unchanged(self) -> None:
        article = _article()
        profile = SimpleNamespace(language="de", persona="student")

        html = render_digest([article], today="2026-02-20", profile=profile)

        self.assertIn("Student-only simple explanation text.", html)


if __name__ == "__main__":
    unittest.main()
