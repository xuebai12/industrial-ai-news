from src.analyzers import llm_analyzer
from src.delivery.email_sender import render_digest
from src.models import AnalyzedArticle, Article


def _make_article() -> AnalyzedArticle:
    original = Article(
        title="Test",
        url="https://example.com",
        source="UnitTest",
        content_snippet="Snippet",
        language="de",
        category="Research",
    )
    return AnalyzedArticle(
        category_tag="Research",
        title_zh="测试",
        title_en="Test",
        title_de="Test",
        core_tech_points="SPS, OEE",
        german_context="Relevance: High",
        source_name="UnitTest",
        source_url="https://example.com",
        summary_zh="",
        summary_en="",
        summary_de="",
        tool_stack="Python",
        simple_explanation="",
        technician_analysis_de="",
        original=original,
    )


def test_split_german_compound_token():
    text = "Die Zuverlaessigkeitsmodellierung bleibt zentral."
    normalized = llm_analyzer._normalize_technician_text_de(text)
    assert "Zuverlaessigkeits-Modellierung" in normalized


def test_enforce_short_sentences_for_long_input():
    text = (
        "Das System sammelt kontinuierlich Sensordaten aus mehreren Linien und verknuepft diese "
        "mit Wartungsprotokollen, sodass Techniker Ausfaelle frueh erkennen und im TIA Portal "
        "schneller reagieren koennen."
    )
    normalized = llm_analyzer._normalize_technician_text_de(text)
    lines = [line.strip("- ").strip() for line in normalized.splitlines() if line.strip()]
    assert len(lines) >= 2
    assert all(len(line.split()) <= 20 for line in lines)


def test_empty_text_uses_safe_fallback():
    assert llm_analyzer._normalize_technician_text_de("") == "Kurzanalyse nicht verfuegbar. Bitte Lauf erneut starten."


def test_render_digest_technician_mode_styles():
    class Profile:
        persona = "technician"
        language = "de"

    article = _make_article()
    article.core_tech_points = "SPS und TIA Portal helfen."
    article.technician_analysis_de = "- Lernen schnell. Probleme bleiben."
    html = render_digest([article], "2026-02-19", Profile())
    assert 'body class="technician-mode"' in html
    assert "font-family: Arial, Helvetica, sans-serif;" in html
    assert "letter-spacing: 0.02em;" in html
    assert "background: #f5f5f5;" in html
    assert "white-space: pre-line;" in html
    assert "border-left: 8px solid #1d4ed8;" in html
    assert "border-left: 8px solid #16a34a;" in html
    assert "border-left: 8px solid #ea580c;" in html
    # tech-block now uses technician_analysis_de directly (not core_tech_points simplified)
    assert "<strong>Lernen</strong>" in html  # from technician_analysis_de: "- Lernen schnell."
    assert "<strong>Probleme</strong>" in html  # from technician_analysis_de: "Probleme bleiben."


def test_render_digest_non_technician_no_mode_class():
    class Profile:
        persona = "student"
        language = "en"

    article = _make_article()
    html = render_digest([article], "2026-02-19", Profile())
    assert 'body class=""' in html


def test_render_digest_uses_daily_keywords_in_header():
    class Profile:
        persona = "technician"
        language = "de"

    article = _make_article()
    article.title_de = "SPS TIA Portal Wartung OEE Sensor"
    article.core_tech_points = "SPS Sensor OEE TIA Portal"
    html = render_digest([article], "2026-02-19", Profile())
    assert "Industrial AI und Simulation" not in html
    assert "2026-02-19 |" in html
    assert "SPS" in html
    assert "Portal" in html
