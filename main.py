#!/usr/bin/env python3
"""Main orchestrator: Scrape -> Filter -> Analyze -> Deliver."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config import DATA_SOURCES, validate_config

logger = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    """Simple JSON log formatter for machine-readable pipeline logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event"):
            payload["event"] = getattr(record, "event")
        if hasattr(record, "stage"):
            payload["stage"] = getattr(record, "stage")
        return json.dumps(payload, ensure_ascii=False)


@dataclass
class StageFailure:
    stage: str
    error_type: str
    message: str
    source: str = ""


@dataclass
class PipelineResult:
    run_id: str
    date: str
    strict: bool
    output: str
    success: bool = False
    exit_reason: str = ""
    duration_seconds: float = 0.0
    scraped_count: int = 0
    deduped_count: int = 0
    relevant_count: int = 0
    analyzed_count: int = 0
    email_sent: bool = False
    markdown_path: str = ""
    notion_pushed: int = 0
    failures: list[StageFailure] = field(default_factory=list)


def configure_logging(log_format: str) -> None:
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Industrial AI & Simulation Daily Intelligence System"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print digest to stdout without sending email",
    )
    parser.add_argument(
        "--output",
        choices=["email", "markdown", "both", "notion"],
        default="email",
        help="Output format: email, markdown, both, or notion",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for artifacts and diagnostics (default: output)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail run (non-zero exit) on any critical stage error",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Logging format (text|json)",
    )
    parser.add_argument(
        "--skip-dynamic",
        action="store_true",
        help="Skip Playwright-based dynamic scrapers",
    )
    parser.add_argument(
        "--skip-llm-filter",
        action="store_true",
        help="Skip Kimi Cloud LLM validation (keyword-only filtering)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=20,
        help="Max articles per source (default: 20)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data for Kimi analysis (simulated response)",
    )
    return parser.parse_args(argv)


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    if netloc.endswith(":443"):
        netloc = netloc[:-4]
    clean_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    clean_path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            clean_path,
            parsed.params,
            clean_query,
            "",
        )
    )


def _dedupe_articles(articles: list) -> list:
    seen: set[str] = set()
    deduped: list = []
    for article in articles:
        key = _normalize_url(getattr(article, "url", "") or getattr(article, "source_url", ""))
        if not key:
            key = f"{getattr(article, 'source', '')}:{getattr(article, 'title', '')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def _append_failure(
    result: PipelineResult, stage: str, error_type: str, message: str, source: str = ""
) -> None:
    result.failures.append(
        StageFailure(stage=stage, error_type=error_type, message=message, source=source)
    )


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _emit_summary(result: PipelineResult, output_dir: str) -> None:
    summary_path = os.path.join(output_dir, f"run-summary-{result.date}.json")
    _write_json(summary_path, asdict(result))
    logger.info("[SUMMARY] Wrote run summary: %s", summary_path)

    if not result.success:
        error_path = os.path.join(output_dir, f"error-{result.date}.json")
        _write_json(
            error_path,
            {
                "run_id": result.run_id,
                "date": result.date,
                "exit_reason": result.exit_reason,
                "failures": [asdict(item) for item in result.failures],
            },
        )
        logger.info("[SUMMARY] Wrote error report: %s", error_path)


def run_pipeline(args: argparse.Namespace) -> PipelineResult:
    os.makedirs(args.output_dir, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    run_id = f"{today}-{int(time.time())}"
    started = time.perf_counter()

    result = PipelineResult(run_id=run_id, date=today, strict=args.strict, output=args.output)

    logger.info("=" * 60)
    logger.info("Industrial AI Intelligence Pipeline | date=%s run_id=%s", today, run_id)
    logger.info(
        "options dry_run=%s output=%s skip_dynamic=%s skip_llm_filter=%s mock=%s strict=%s",
        args.dry_run,
        args.output,
        args.skip_dynamic,
        args.skip_llm_filter,
        args.mock,
        args.strict,
    )

    valid, config_errors = validate_config(mode=args.output, mock=args.mock)
    if not valid:
        for item in config_errors:
            _append_failure(result, "config", "CONFIG", item)
        result.exit_reason = "configuration validation failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    all_articles = []
    try:
        from src.scrapers.rss_scraper import scrape_rss
        from src.scrapers.web_scraper import scrape_web_sources

        rss_sources = [s for s in DATA_SOURCES if s.source_type == "rss"]
        for source in rss_sources:
            try:
                articles = scrape_rss(
                    name=source.name,
                    url=source.url,
                    language=source.language,
                    category=source.category,
                    max_items=args.max_articles,
                )
                all_articles.extend(articles)
            except Exception as exc:
                _append_failure(result, "scrape", "SCRAPE", str(exc), source=source.name)
                logger.error("[SCRAPE] RSS source failed: %s | %s", source.name, exc)
                if args.strict:
                    raise

        web_articles = scrape_web_sources(args.max_articles)
        all_articles.extend(web_articles)

        if not args.skip_dynamic:
            from src.scrapers.dynamic_scraper import scrape_dynamic_sources

            dynamic_articles = scrape_dynamic_sources(args.max_articles)
            all_articles.extend(dynamic_articles)
        else:
            logger.info("[SCRAPE] Skipping dynamic scrapers (--skip-dynamic)")

    except Exception as exc:
        _append_failure(result, "scrape", "SCRAPE", str(exc))
        result.exit_reason = "scraping stage failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    result.scraped_count = len(all_articles)
    if not all_articles:
        result.success = not args.strict
        result.exit_reason = "no articles scraped"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    deduped_articles = _dedupe_articles(all_articles)
    result.deduped_count = len(deduped_articles)
    logger.info(
        "[SCRAPE] total=%s deduped=%s",
        result.scraped_count,
        result.deduped_count,
    )

    try:
        from src.filters.ollama_filter import filter_articles

        relevant_articles = filter_articles(
            deduped_articles, skip_llm=args.skip_llm_filter
        )
    except Exception as exc:
        _append_failure(result, "filter", "FILTER", str(exc))
        result.exit_reason = "filter stage failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    result.relevant_count = len(relevant_articles)
    if not relevant_articles:
        result.success = not args.strict
        result.exit_reason = "no relevant articles"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    try:
        from src.analyzers.kimi_analyzer import analyze_articles

        analyzed = analyze_articles(relevant_articles, mock=args.mock)
    except Exception as exc:
        _append_failure(result, "analyze", "LLM", str(exc))
        result.exit_reason = "analysis stage failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    result.analyzed_count = len(analyzed)
    if not analyzed:
        result.success = not args.strict
        result.exit_reason = "analysis produced no results"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    try:
        from src.delivery.email_sender import (
            render_digest_text,
            save_digest_markdown,
            send_email,
        )

        if args.dry_run:
            print("\n" + render_digest_text(analyzed, today))
            logger.info("[DELIVERY] Dry run output printed")
        else:
            if args.output in ("email", "both"):
                result.email_sent = send_email(analyzed, today)
                if args.strict and not result.email_sent:
                    raise RuntimeError("Email delivery failed in strict mode")

            if args.output in ("markdown", "both"):
                result.markdown_path = save_digest_markdown(
                    analyzed, today=today, output_dir=args.output_dir
                )
                logger.info("[DELIVERY] Markdown digest saved: %s", result.markdown_path)

            if args.output in ("notion", "both"):
                from src.delivery.notion_sender import push_to_notion

                result.notion_pushed = push_to_notion(analyzed, today)
                logger.info("[DELIVERY] Notion pushed: %s", result.notion_pushed)
    except Exception as exc:
        _append_failure(result, "delivery", "DELIVERY", str(exc))
        result.exit_reason = "delivery stage failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    result.success = True
    result.exit_reason = "completed"
    result.duration_seconds = round(time.perf_counter() - started, 3)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_format)

    try:
        result = run_pipeline(args)
    except Exception as exc:
        logger.critical("Pipeline failed unexpectedly: %s", exc)
        traceback.print_exc()
        os.makedirs(args.output_dir, exist_ok=True)
        today = date.today().strftime("%Y-%m-%d")
        crash_result = PipelineResult(
            run_id=f"{today}-{int(time.time())}",
            date=today,
            strict=args.strict,
            output=args.output,
            success=False,
            exit_reason="unhandled exception",
        )
        _append_failure(crash_result, "runtime", "RUNTIME", str(exc))
        _emit_summary(crash_result, args.output_dir)
        return 1

    _emit_summary(result, args.output_dir)
    if result.success:
        logger.info(
            "Pipeline complete | scraped=%s deduped=%s relevant=%s analyzed=%s duration=%.2fs",
            result.scraped_count,
            result.deduped_count,
            result.relevant_count,
            result.analyzed_count,
            result.duration_seconds,
        )
        return 0

    logger.error(
        "Pipeline ended with issues | reason=%s strict=%s failures=%s",
        result.exit_reason,
        result.strict,
        len(result.failures),
    )
    return 1 if result.strict or result.exit_reason.startswith("configuration") else 0


if __name__ == "__main__":
    sys.exit(main())
