#!/usr/bin/env python3
"""主流程控制器: 抓取 -> 过滤 -> 分析 -> 交付 (Scrape -> Filter -> Analyze -> Deliver)."""

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

from config import DATA_SOURCES, RECIPIENT_PROFILES, validate_config

logger = logging.getLogger(__name__)
YOUTUBE_MAX_ITEMS = int(os.getenv("YOUTUBE_MAX_ITEMS", "5"))


class JsonFormatter(logging.Formatter):
    """
    简单的 JSON 日志格式化器 (Simple JSON Log Formatter)
    用于生成机器可读的流水线日志，便于后续分析或监控。
    """

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
    """
    阶段失败记录 (Stage Failure Record)
    记录流水线特定阶段的错误信息。
    """
    stage: str          # 发生错误的阶段 (e.g. "scrape", "analyze")
    error_type: str     # 错误类型 (e.g. "TIMEOUT", "API_ERROR")
    message: str        # 错误详情
    source: str = ""    # 相关源名称 (optional)


@dataclass
class PipelineResult:
    """
    流水线执行结果数据类 (Pipeline Result Data Class)
    用于统计和报告整个流水线的执行情况。
    """
    run_id: str
    date: str
    strict: bool
    output: str
    success: bool = False
    exit_reason: str = ""
    duration_seconds: float = 0.0
    scraped_count: int = 0      # 抓取总数
    deduped_count: int = 0      # 去重后数量
    relevant_count: int = 0     # 相关性筛选后数量
    analyzed_count: int = 0     # 分析完成数量
    email_sent: bool = False    # 邮件是否发送成功
    markdown_path: str = ""     # Markdown 报告路径
    notion_pushed: int = 0      # 推送到 Notion 的数量
    failures: list[StageFailure] = field(default_factory=list)  # 失败列表


def configure_logging(log_format: str) -> None:
    """配置日志系统 (Configure Logging)"""
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
    """解析命令行参数 (Parse Command Line Arguments)"""
    parser = argparse.ArgumentParser(
        description="Industrial AI & Simulation Daily Intelligence System"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印结果到控制台，不发送邮件 (Print digest to stdout without sending email)",
    )
    parser.add_argument(
        "--output",
        choices=["email", "markdown", "both", "notion"],
        default="email",
        help="输出格式: email, markdown, both, 或 notion",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="产物输出目录 (default: output)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：遇到任何错误都返回非零退出码 (Fail run on any critical stage error)",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="日志格式 (text|json)",
    )
    parser.add_argument(
        "--skip-dynamic",
        action="store_true",
        help="跳过 Playwright 动态抓取 (Skip Playwright-based dynamic scrapers)",
    )
    parser.add_argument(
        "--skip-llm-filter",
        action="store_true",
        help="跳过 LLM 云端校验，仅使用关键词过滤 (Skip LLM Cloud validation)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=20,
        help="每个源最大抓取文章数 (Default: 20)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="按排序仅保留前 N 篇进入分析与投递 (Default: 20, <=0 表示不限制)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用模拟数据进行 LLM 分析 (Use mock data for LLM analysis)",
    )
    return parser.parse_args(argv)


def _normalize_url(url: str) -> str:
    """标准化 URL 以进行去重 (Normalize URL for deduplication)"""
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
    """基于 URL 或 (来源+标题) 对文章进行去重 (Deduplicate articles)"""
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


def _source_priority_map() -> dict[str, int]:
    """Build source priority lookup from configured sources."""
    return {source.name: source.priority for source in DATA_SOURCES}


def _rank_articles_for_delivery(articles: list, top_n: int) -> list:
    """
    Rank candidate articles and keep top N.
    排序规则: relevance_score desc -> source priority desc -> published_date desc
    """
    priorities = _source_priority_map()

    def _sort_key(article: object) -> tuple:
        relevance = int(getattr(article, "relevance_score", 0) or 0)
        source_name = getattr(article, "source", "") or getattr(article, "source_name", "")
        source_priority = int(priorities.get(source_name, 1))
        published_date = getattr(article, "published_date", None)
        published_ts = published_date.timestamp() if published_date else 0.0
        title = getattr(article, "title", "") or getattr(article, "title_en", "")
        return (relevance, source_priority, published_ts, str(title))

    ranked = sorted(articles, key=_sort_key, reverse=True)
    if top_n <= 0:
        return ranked
    return ranked[:top_n]


def _build_pending_articles_table(articles: list, start: int, limit: int = 20) -> list[dict]:
    """Build compact rows for the 'not analyzed yet' table in email."""
    rows: list[dict] = []
    if limit <= 0 or start >= len(articles):
        return rows
    for article in articles[start : start + limit]:
        rows.append(
            {
                "category": getattr(article, "category", ""),
                "title": getattr(article, "title", "")[:140],
                "url": getattr(article, "url", ""),
            }
        )
    return rows


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
    """输出运行摘要统计 (Emit Run Summary)"""
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
    """
    执行主流水线逻辑 (Execute Main Pipeline Logic)
    
    Steps:
    1. Validate Config (验证配置)
    2. Scrape (抓取)
    3. Dedupe (去重)
    4. Filter (过滤)
    5. Analyze (分析)
    6. Deliver (交付)
    """
    os.makedirs(args.output_dir, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    run_id = f"{today}-{int(time.time())}"
    started = time.perf_counter()

    result = PipelineResult(run_id=run_id, date=today, strict=args.strict, output=args.output)

    logger.info("=" * 60)
    logger.info("Industrial AI Intelligence Pipeline | date=%s run_id=%s", today, run_id)
    logger.info(
        "options dry_run=%s output=%s skip_dynamic=%s skip_llm_filter=%s mock=%s strict=%s top_n=%s",
        args.dry_run,
        args.output,
        args.skip_dynamic,
        args.skip_llm_filter,
        args.mock,
        args.strict,
        args.top_n,
    )

    # 1. 验证配置 (Validate Config)
    valid, config_errors = validate_config(mode=args.output, mock=args.mock)
    if not valid:
        for item in config_errors:
            _append_failure(result, "config", "CONFIG", item)
        result.exit_reason = "configuration validation failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    all_articles = []
    # 2. 开始抓取 (Start Scraping)
    try:
        from src.scrapers.rss_scraper import scrape_rss
        from src.scrapers.web_scraper import scrape_web_sources

        # 2.1 RSS 抓取
        rss_sources = [s for s in DATA_SOURCES if s.source_type == "rss"]
        for source in rss_sources:
            try:
                source_max_items = args.max_articles
                if source.name.lower().startswith("youtube rss:"):
                    source_max_items = min(source_max_items, YOUTUBE_MAX_ITEMS)
                articles = scrape_rss(
                    name=source.name,
                    url=source.url,
                    language=source.language,
                    category=source.category,
                    max_items=source_max_items,
                )
                all_articles.extend(articles)
            except Exception as exc:
                _append_failure(result, "scrape", "SCRAPE", str(exc), source=source.name)
                logger.error("[SCRAPE] RSS source failed: %s | %s", source.name, exc)
                if args.strict:
                    raise

        # 2.2 网页抓取 (BeautifulSoup)
        web_articles = scrape_web_sources(args.max_articles)
        all_articles.extend(web_articles)

        # 2.3 动态抓取 (Playwright)
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

    # 3. 去重 (Deduplication)
    deduped_articles = _dedupe_articles(all_articles)
    result.deduped_count = len(deduped_articles)
    logger.info(
        "[SCRAPE] total=%s deduped=%s",
        result.scraped_count,
        result.deduped_count,
    )

    # 4. 过滤 (Filtering - Ollama/Keyword)
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

    # 4.5 排序并截断 (Rank & cap before analysis to control volume and latency)
    sorted_relevant_articles = _rank_articles_for_delivery(relevant_articles, top_n=0)
    ranked_articles = (
        sorted_relevant_articles[: args.top_n] if args.top_n > 0 else sorted_relevant_articles
    )
    pending_articles = (
        _build_pending_articles_table(sorted_relevant_articles, start=max(args.top_n, 0), limit=20)
        if args.top_n > 0
        else []
    )
    if args.top_n > 0:
        logger.info(
            "[RANK] selected top %s/%s relevant articles for analysis",
            len(ranked_articles),
            len(relevant_articles),
        )
    else:
        logger.info("[RANK] top_n disabled, keeping all %s relevant articles", len(ranked_articles))

    # 5. 分析 (Analysis - LLM)
    try:
        from src.analyzers.llm_analyzer import analyze_articles

        analyzed = analyze_articles(ranked_articles, mock=args.mock)
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

    # 6. 交付 (Delivery - Email/Markdown/Notion)
    try:
        from src.delivery.email_sender import (
            render_digest_text,
            save_digest_markdown,
            send_email,
        )

        if args.dry_run:
            print("\n" + render_digest_text(analyzed, today, pending_articles=pending_articles))
            logger.info("[DELIVERY] Dry run output printed")
        else:
            if args.output in ("email", "both"):
                # Multi-channel delivery based on profiles
                for profile in RECIPIENT_PROFILES:
                    if profile.delivery_channel not in ("email", "both"):
                        continue

                    # Filter articles for this persona
                    # Logic: Include if article is explicitly tagged for this persona,
                    # OR if article has no tags and this is the default "student" persona.
                    profile_articles = [
                        a for a in analyzed
                        if profile.persona in (a.target_personas or [])
                        or (not a.target_personas and profile.persona == "student")
                    ]

                    if not profile_articles:
                        logger.info(f"[DELIVERY] No articles for profile '{profile.name}'")
                        continue

                    logger.info(f"[DELIVERY] Sending {len(profile_articles)} articles to '{profile.name}'")
                    success = send_email(
                        profile_articles,
                        today,
                        profile=profile,
                        pending_articles=pending_articles,
                    )

                    if args.strict and not success:
                         logger.error(f"[DELIVERY] Failed to send email to '{profile.name}'")
                         # In strict mode, maybe we should raise? But let's verify other profiles first or fail hard.
                         # User requested "fail run on any critical stage error"
                         raise RuntimeError(f"Email delivery failed for profile {profile.name}")

                result.email_sent = True # Mark as sent if we got here (individual failures raised if strict)

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
    """程序入口点：解析参数，运行流水线，处理异常。"""
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
