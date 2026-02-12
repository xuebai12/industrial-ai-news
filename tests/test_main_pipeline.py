from __future__ import annotations

from argparse import Namespace
from datetime import datetime

import main
from src.models import Article, AnalyzedArticle


def _article() -> Article:
    return Article(
        title="Digital Twin News",
        url="https://example.com/a",
        source="src",
        content_snippet="Digital Twin in industry",
        language="en",
        category="industry",
        published_date=datetime.utcnow(),
    )


def _analyzed(article: Article | None = None) -> AnalyzedArticle:
    article = article or _article()
    return AnalyzedArticle(
        category_tag="Digital Twin",
        title_zh="标题",
        title_en="Title",
        core_tech_points="AAS",
        german_context="Germany",
        source_name=article.source,
        source_url=article.url,
        summary_zh="摘要",
        summary_en="Summary",
        original=article,
    )


def _patch_pipeline_deps(monkeypatch, tmp_path, output: str):
    monkeypatch.setattr(main, "validate_config", lambda mode, mock=False: (True, []))
    monkeypatch.setattr(main, "DATA_SOURCES", [])

    import src.scrapers.web_scraper as web_scraper
    import src.filters.ollama_filter as ollama_filter
    import src.analyzers.kimi_analyzer as kimi_analyzer
    import src.delivery.email_sender as email_sender
    import src.delivery.notion_sender as notion_sender

    article = _article()
    analyzed = _analyzed(article)

    monkeypatch.setattr(web_scraper, "scrape_web_sources", lambda max_items: [article])
    monkeypatch.setattr(ollama_filter, "filter_articles", lambda articles, skip_llm: articles)
    monkeypatch.setattr(kimi_analyzer, "analyze_articles", lambda articles, mock=False: [analyzed])

    calls = {"email": 0, "markdown": 0, "notion": 0}

    def fake_send_email(articles, today):
        calls["email"] += 1
        return True

    def fake_save_digest_markdown(articles, output_dir, today):
        calls["markdown"] += 1
        return str(tmp_path / f"digest-{today}.md")

    def fake_push_to_notion(articles, today):
        calls["notion"] += 1
        return 1

    monkeypatch.setattr(email_sender, "send_email", fake_send_email)
    monkeypatch.setattr(email_sender, "save_digest_markdown", fake_save_digest_markdown)
    monkeypatch.setattr(notion_sender, "push_to_notion", fake_push_to_notion)

    args = Namespace(
        dry_run=False,
        output=output,
        output_dir=str(tmp_path),
        strict=False,
        log_format="text",
        skip_dynamic=True,
        skip_llm_filter=True,
        max_articles=5,
        mock=True,
    )
    return args, calls


def test_parse_args_accepts_new_flags():
    args = main.parse_args(
        ["--output-dir", "tmp-out", "--strict", "--log-format", "json", "--output", "markdown"]
    )
    assert args.output_dir == "tmp-out"
    assert args.strict is True
    assert args.log_format == "json"
    assert args.output == "markdown"


def test_run_pipeline_output_markdown_only(monkeypatch, tmp_path):
    args, calls = _patch_pipeline_deps(monkeypatch, tmp_path, "markdown")
    result = main.run_pipeline(args)
    assert result.success is True
    assert calls["markdown"] == 1
    assert calls["email"] == 0
    assert calls["notion"] == 0


def test_run_pipeline_output_both(monkeypatch, tmp_path):
    args, calls = _patch_pipeline_deps(monkeypatch, tmp_path, "both")
    result = main.run_pipeline(args)
    assert result.success is True
    assert calls["markdown"] == 1
    assert calls["email"] == 1
    assert calls["notion"] == 1


def test_run_pipeline_output_notion_only(monkeypatch, tmp_path):
    args, calls = _patch_pipeline_deps(monkeypatch, tmp_path, "notion")
    result = main.run_pipeline(args)
    assert result.success is True
    assert calls["markdown"] == 0
    assert calls["email"] == 0
    assert calls["notion"] == 1


def test_strict_email_failure_returns_error(monkeypatch, tmp_path):
    args, calls = _patch_pipeline_deps(monkeypatch, tmp_path, "email")
    args.strict = True

    import src.delivery.email_sender as email_sender

    monkeypatch.setattr(email_sender, "send_email", lambda articles, today: False)
    result = main.run_pipeline(args)

    assert result.success is False
    assert result.exit_reason == "delivery stage failed"


def test_config_validation_failure_is_fatal(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "validate_config", lambda mode, mock=False: (False, ["bad config"]))
    args = Namespace(
        dry_run=False,
        output="email",
        output_dir=str(tmp_path),
        strict=False,
        log_format="text",
        skip_dynamic=True,
        skip_llm_filter=True,
        max_articles=5,
        mock=False,
    )
    result = main.run_pipeline(args)
    assert result.success is False
    assert result.exit_reason == "configuration validation failed"
    assert len(result.failures) == 1
