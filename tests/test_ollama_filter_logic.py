from unittest.mock import patch

from src.filters import ollama_filter
from src.models import Article


def _article(title: str, snippet: str = "", source: str = "UnitTest") -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{abs(hash(title))}",
        source=source,
        content_snippet=snippet,
        language="en",
        category="research",
    )


def test_theory_only_without_industry_is_downranked():
    article = _article(
        "Spatio-temporal dual-stage hypergraph MARL theorem proof for traffic signal control",
    )
    score, personas = ollama_filter.keyword_score(article)
    assert score <= 1
    assert "technician" not in personas


def test_theory_with_industry_context_passes():
    article = _article(
        "Deep reinforcement learning AI for factory scheduling",
        "Industrial manufacturing production line with MES and PLC closed-loop control.",
    )
    score, personas = ollama_filter.keyword_score(article)
    assert score >= 2
    assert "student" in personas or "technician" in personas


def test_industrial_practical_terms_mark_technician():
    article = _article(
        "AI predictive maintenance with PLC and MES improves OEE on shopfloor line",
    )
    score, personas = ollama_filter.keyword_score(article)
    assert score >= 3
    assert "technician" in personas


@patch("src.filters.ollama_filter.keyword_score", return_value=(4, ["student"]))
@patch("src.filters.ollama_filter.llm_relevance_check", return_value=None)
def test_llm_none_high_score_without_industry_is_blocked(mock_llm, mock_kw):
    article = _article(
        "Formal logic theorem for hypergraph reasoning benchmark",
        source="Generic Research Feed",
    )
    with patch("src.filters.ollama_filter.MIN_RELEVANT_ARTICLES", 0):
        result = ollama_filter.filter_articles([article], skip_llm=False)
    assert len(result) == 0


@patch("src.filters.ollama_filter.keyword_score", return_value=(3, ["student"]))
@patch("src.filters.ollama_filter.llm_relevance_check", return_value=False)
def test_min_volume_fallback_does_not_add_non_industry(mock_llm, mock_kw):
    article = _article(
        "Formal logic theorem for hypergraph reasoning benchmark",
        source="Generic Research Feed",
    )
    with patch("src.filters.ollama_filter.MIN_RELEVANT_ARTICLES", 1):
        result = ollama_filter.filter_articles([article], skip_llm=False)
    assert len(result) == 0


@patch("src.filters.ollama_filter.keyword_score", return_value=(3, ["student"]))
@patch("src.filters.ollama_filter.llm_relevance_check", return_value=False)
def test_min_volume_fallback_adds_industry_context_article(mock_llm, mock_kw):
    article = _article(
        "Industrial AI manufacturing planning with PLC and MES",
        source="Generic Research Feed",
    )
    with patch("src.filters.ollama_filter.MIN_RELEVANT_ARTICLES", 1):
        result = ollama_filter.filter_articles([article], skip_llm=False)
    assert len(result) == 1
    assert result[0].title == article.title


@patch("src.filters.ollama_filter.keyword_score")
@patch("src.filters.ollama_filter.llm_relevance_check")
def test_llm_none_fallback_keeps_industry_high_score(mock_llm, mock_kw):
    article = _article("AI adaptive control for factory line scheduling with MES")
    mock_kw.return_value = (3, ["student"])
    mock_llm.return_value = None
    with patch("src.filters.ollama_filter.MIN_RELEVANT_ARTICLES", 0):
        result = ollama_filter.filter_articles([article], skip_llm=False)
    assert len(result) == 1


def test_pure_automotive_news_without_ai_is_blocked():
    article = _article(
        "Automotive production update: new EV model launched in Europe",
        "Vehicle sales and factory expansion plans with no software intelligence details.",
    )
    score, _ = ollama_filter.keyword_score(article)
    assert score == 0


def test_automotive_ai_news_passes_keyword_gate():
    article = _article(
        "Automotive AI quality inspection improves EV battery pack line",
        "Computer vision model detects defects in battery module assembly.",
    )
    score, personas = ollama_filter.keyword_score(article)
    assert score >= 2
    assert "student" in personas or "technician" in personas
