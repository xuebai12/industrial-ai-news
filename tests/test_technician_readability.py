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
    article.technician_analysis_de = (
        "- Sensoren messen Vibration und Temperatur in Echtzeit. "
        "Das Modell lernt den Normalzustand der Maschine. "
        "Bei Abweichung wird frueh ein Wartungsfenster empfohlen. "
        "Techniker planen den Eingriff ohne ungeplanten Stopp."
    )
    article.summary_de = "Weniger Stillstand und bessere Planbarkeit in der Wartung."
    html = render_digest([article], "2026-02-19", Profile())
    assert 'body class="technician-mode"' in html
    assert "font-family: Arial, Helvetica, sans-serif;" in html
    assert "letter-spacing: 0.02em;" in html
    assert "background: #f5f5f5;" in html
    assert "white-space: pre-line;" in html
    assert "Kernfokus" in html
    assert "Kernmechanismus" in html
    assert "class=\"focus-list\"" in html
    assert "class=\"mechanism-list\"" in html
    assert "border-left: 8px solid #1d4ed8;" in html
    assert "border-left: 8px solid #ea580c;" in html
    assert "class=\"quick-card green\"" not in html
    assert "Weniger Stillstand und bessere Planbarkeit in der Wartung." in html
    assert "Wie ein Fitness-Tracker fuer Maschinen:" in html
    assert "Quelle:" not in html


def test_render_digest_technician_focus_lists_are_compact_and_bounded():
    class Profile:
        persona = "technician"
        language = "de"

    article = _make_article()
    article.technician_analysis_de = (
        "Sensoren erfassen Vibration und Temperatur. "
        "Modell lernt den Normalzustand je Maschine. "
        "Abweichung erzeugt Wartungsfenster. "
        "Instandhaltung plant Eingriff im Schichtfenster."
    )
    article.summary_de = (
        "Weniger Ausfallzeit in der Linie. "
        "Bessere Terminplanung fuer Wartungsteams. "
        "Hoehere Anlagenverfuegbarkeit im Tagesbetrieb."
    )
    html = render_digest([article], "2026-02-19", Profile())
    assert html.count("<ul class=\"focus-list\">") == 1
    assert html.count("<ol class=\"mechanism-list\">") == 1
    assert "Kernmechanismus" in html


def test_render_digest_technician_focus_lists_use_german_fallback_when_too_short():
    class Profile:
        persona = "technician"
        language = "de"

    article = _make_article()
    article.technician_analysis_de = "Nur ein Punkt."
    article.summary_de = ""
    article.german_context = ""
    html = render_digest([article], "2026-02-19", Profile())
    assert "Einsatz im Betrieb: klare Anwendung an Linie, Anlage und Wartungsfenster." in html


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
