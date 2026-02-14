import pytest
from src.models import Article
from src.filters.ollama_filter import filter_articles, keyword_score, RELEVANCE_THRESHOLD
from unittest.mock import MagicMock, patch

def test_keyword_score_technician():
    # Test that technician keywords are detected
    article = Article(
        title="Predictive Maintenance for PLC S7-1500",
        url="http://example.com",
        source="Test",
        content_snippet="We use TIA Portal for diagnostics.",
        language="en",
        category="Tech"
    )
    score, personas = keyword_score(article)
    assert score >= 3
    assert "technician" in personas

def test_keyword_score_student():
    # Test that student/high priority keywords are detected
    article = Article(
        title="Digital Twin Simulation",
        url="http://example.com",
        source="Test",
        content_snippet="Using AnyLogic for simulation.",
        language="en",
        category="Research"
    )
    score, personas = keyword_score(article)
    assert score >= 2
    assert "student" in personas

def test_filter_articles_assigns_personas():
    # Test that filter_articles assigns target_personas to the Article object
    article = Article(
        title="Digital Twin Simulation",
        url="http://example.com",
        source="Test",
        content_snippet="Using AnyLogic for simulation.",
        language="en",
        category="Research"
    )

    # We mock llm_relevance_check to return True so we don't need actual LLM
    with patch("src.filters.ollama_filter.llm_relevance_check", return_value=True):
        filtered = filter_articles([article], skip_llm=True)

    assert len(filtered) == 1
    assert filtered[0].target_personas is not None
    assert "student" in filtered[0].target_personas
    assert filtered[0] is article # Verify it modifies the object in place

def test_setattr_issue_repro():
    # This test is to manually verify the current state and then will be kept to verify the fix
    article = Article(
        title="Industrial AI",
        url="http://example.com",
        source="Test",
        content_snippet="AI in manufacturing",
        language="en",
        category="Tech"
    )

    # Ensure target_personas is initially empty
    assert article.target_personas == []

    # Run filter (skip LLM to be fast)
    with patch("src.filters.ollama_filter.llm_relevance_check", return_value=True):
        filtered = filter_articles([article], skip_llm=True)

    # Verify target_personas is populated
    assert len(filtered) == 1
    assert "student" in filtered[0].target_personas or "technician" in filtered[0].target_personas
