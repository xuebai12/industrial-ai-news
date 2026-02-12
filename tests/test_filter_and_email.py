from __future__ import annotations

from pathlib import Path

from src.delivery.email_sender import render_digest_text, save_digest_markdown
from src.filters.ollama_filter import filter_articles, keyword_score
from src.models import Article, AnalyzedArticle


def _article(title: str, snippet: str) -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title}",
        source="source",
        content_snippet=snippet,
        language="en",
        category="industry",
    )


def _analyzed() -> AnalyzedArticle:
    raw = _article("t", "s")
    return AnalyzedArticle(
        category_tag="AI",
        title_zh="中文",
        title_en="English",
        core_tech_points="AAS",
        german_context="context",
        source_name="src",
        source_url="https://example.com/x",
        summary_zh="摘要",
        summary_en="summary",
        original=raw,
    )


def test_keyword_score_high_and_medium():
    article = _article(
        "Digital Twin rollout",
        "Uses Reinforcement Learning in smart factory",
    )
    score = keyword_score(article)
    assert score >= 3


def test_filter_articles_skip_llm_sorts_by_score():
    high = _article("Digital Twin", "Reinforcement Learning")
    low = _article("General update", "Nothing relevant")
    result = filter_articles([low, high], skip_llm=True)
    assert len(result) >= 1
    assert result[0].relevance_score >= result[-1].relevance_score


def test_render_digest_text_contains_sections():
    text = render_digest_text([_analyzed()], today="2026-02-12")
    assert "2026-02-12" in text
    assert "求职视角" in text


def test_save_digest_markdown_writes_file(tmp_path: Path):
    path = save_digest_markdown([_analyzed()], output_dir=str(tmp_path), today="2026-02-12")
    file_path = Path(path)
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "2026-02-12" in content
    assert "工业 AI 每日摘要" in content
