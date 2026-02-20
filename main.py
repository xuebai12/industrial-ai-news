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
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config import (
    DATA_SOURCES,
    RECIPIENT_PROFILES,
    YOUTUBE_FOCUS_CHANNELS_BY_REGION,
    RSS_WEB_PRIORITY_SOURCES,
    RSS_WEB_PRIORITY_ONLY,
    validate_config,
)

logger = logging.getLogger(__name__)


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


SENT_HISTORY_FILE = "sent_history.json"
PROFILE_ARTICLE_TARGET = max(1, int(os.getenv("PROFILE_ARTICLE_TARGET", "5")))
PROFILE_REPEAT_COOLDOWN_DAYS = max(0, int(os.getenv("PROFILE_REPEAT_COOLDOWN_DAYS", "7")))
EMAIL_REVIEWER = os.getenv("EMAIL_REVIEWER", "baixue243@gmail.com").strip()
ANALYSIS_FALLBACK_MARKERS = (
    "analysis fallback",
    "kein auswertbares modell-ergebnis verfügbar",
    "模型未返回可解析的结构化结果",
    "local model analysis failed",
    "model analysis temporarily unavailable",
    "auto fallback summary from source snippet",
    "__analysis_fallback__",
)


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
        "--mock",
        action="store_true",
        help="使用模拟数据进行 LLM 分析 (Use mock data for LLM analysis)",
    )
    parser.add_argument(
        "--approve-send",
        action="store_true",
        help=(
            "邮件审核通过后执行正式发送。默认先发送审核邮件到 EMAIL_REVIEWER "
            f"(default: {EMAIL_REVIEWER})"
        ),
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


def _is_fallback_analysis(article) -> bool:
    fields = (
        getattr(article, "core_tech_points", "") or "",
        getattr(article, "simple_explanation", "") or "",
        getattr(article, "technician_analysis_de", "") or "",
        getattr(article, "summary_en", "") or "",
        getattr(article, "tool_stack", "") or "",
    )
    blob = " ".join(fields).strip().lower()
    if not blob:
        return True
    return any(marker in blob for marker in ANALYSIS_FALLBACK_MARKERS)


def _drop_fallback_analysis(articles: list) -> tuple[list, int]:
    kept = []
    dropped = 0
    for item in articles:
        if _is_fallback_analysis(item):
            dropped += 1
            continue
        kept.append(item)
    return kept, dropped


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


def _article_key(article: object) -> str:
    """构建文章唯一键，用于去重和历史记录。"""
    url = _normalize_url(getattr(article, "source_url", "") or getattr(article, "url", ""))
    if url:
        return f"url:{url}"
    source = str(getattr(article, "source_name", "") or getattr(article, "source", "")).strip().lower()
    title = str(getattr(article, "title_zh", "") or getattr(article, "title", "")).strip().lower()
    return f"title:{source}:{title}"


def _article_score(article: object) -> int:
    original = getattr(article, "original", None)
    if original is not None:
        return int(getattr(original, "relevance_score", 0) or 0)
    return int(getattr(article, "relevance_score", 0) or 0)


def _prioritize_sources(sources: list, priority_names: list[str], priority_only: bool = False) -> list:
    """Prioritize sources by name with optional whitelist-only mode."""
    priority_set = {name.strip().casefold() for name in priority_names if name.strip()}
    if not priority_set:
        return list(sources)
    prioritized = [s for s in sources if str(getattr(s, "name", "")).strip().casefold() in priority_set]
    if priority_only:
        return prioritized
    remaining = [s for s in sources if str(getattr(s, "name", "")).strip().casefold() not in priority_set]
    return prioritized + remaining


def _load_sent_history(path: str) -> dict[str, dict[str, str]]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        profiles = raw.get("profiles", {}) if isinstance(raw, dict) else {}
        if not isinstance(profiles, dict):
            return {}
        return {
            str(persona): {str(k): str(v) for k, v in entries.items()}
            for persona, entries in profiles.items()
            if isinstance(entries, dict)
        }
    except Exception:
        return {}


def _save_sent_history(path: str, history: dict[str, dict[str, str]]) -> None:
    _write_json(path, {"profiles": history})


def _is_recent(
    history: dict[str, dict[str, str]], persona: str, key: str, today: date, cooldown_days: int
) -> bool:
    persona_history = history.get(persona, {})
    sent_on = persona_history.get(key, "")
    if not sent_on:
        return False
    try:
        sent_date = date.fromisoformat(sent_on)
    except ValueError:
        return False
    return sent_date >= (today - timedelta(days=cooldown_days))


def _select_articles_for_profile(
    analyzed: list,
    persona: str,
    history: dict[str, dict[str, str]],
    today: date,
    target_count: int,
    cooldown_days: int,
    globally_used: set[str],
) -> list:
    def primary_match(item: object) -> bool:
        personas = list(getattr(item, "target_personas", []) or [])
        return persona in personas or (not personas and persona == "student")

    primary = [a for a in analyzed if primary_match(a)]
    secondary = [a for a in analyzed if not primary_match(a)]
    primary.sort(key=_article_score, reverse=True)
    secondary.sort(key=_article_score, reverse=True)

    selected: list = []
    selected_keys: set[str] = set()

    def append_from(pool: list, *, allow_recent: bool, allow_global_dup: bool) -> None:
        for item in pool:
            if len(selected) >= target_count:
                return
            key = _article_key(item)
            if key in selected_keys:
                continue
            if (not allow_global_dup) and key in globally_used:
                continue
            if (not allow_recent) and _is_recent(history, persona, key, today, cooldown_days):
                continue
            selected.append(item)
            selected_keys.add(key)

    # 优先级: 主画像且非近期重复 -> 主画像允许近期重复 -> 次画像非近期 -> 次画像允许近期
    append_from(primary, allow_recent=False, allow_global_dup=False)
    append_from(primary, allow_recent=True, allow_global_dup=False)
    append_from(secondary, allow_recent=False, allow_global_dup=False)
    append_from(secondary, allow_recent=True, allow_global_dup=False)
    append_from(primary, allow_recent=True, allow_global_dup=True)
    append_from(secondary, allow_recent=True, allow_global_dup=True)

    for key in selected_keys:
        globally_used.add(key)
    return selected


def _record_sent(
    history: dict[str, dict[str, str]], persona: str, articles: list, today_iso: str
) -> None:
    persona_history = history.setdefault(persona, {})
    for item in articles:
        persona_history[_article_key(item)] = today_iso


def _split_recipients(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _unique_recipients(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


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
    today_obj = date.today()
    today = today_obj.strftime("%Y-%m-%d")
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
        rss_sources = _prioritize_sources(
            rss_sources,
            priority_names=RSS_WEB_PRIORITY_SOURCES,
            priority_only=RSS_WEB_PRIORITY_ONLY,
        )
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

        # 2.2 网页抓取 (BeautifulSoup)
        web_sources = [s for s in DATA_SOURCES if s.source_type == "web"]
        web_sources = _prioritize_sources(
            web_sources,
            priority_names=RSS_WEB_PRIORITY_SOURCES,
            priority_only=RSS_WEB_PRIORITY_ONLY,
        )
        web_articles = scrape_web_sources(args.max_articles, sources=web_sources)
        all_articles.extend(web_articles)

        # 2.3 动态抓取 (Playwright)
        if not args.skip_dynamic:
            from src.scrapers.dynamic_scraper import scrape_dynamic_sources

            dynamic_articles = scrape_dynamic_sources(args.max_articles)
            all_articles.extend(dynamic_articles)
        else:
            logger.info("[SCRAPE] Skipping dynamic scrapers (--skip-dynamic)")

        # 2.4 YouTube 抓取
        youtube_sources = [s for s in DATA_SOURCES if s.source_type == "youtube"]
        if youtube_sources:
            try:
                from src.scrapers.youtube_scraper import scrape_youtube, scrape_youtube_focus_channels
                for source in youtube_sources:
                    try:
                        region = getattr(source, "region_code", "")
                        focus_channels = YOUTUBE_FOCUS_CHANNELS_BY_REGION.get(region, [])
                        focus_videos = scrape_youtube_focus_channels(
                            name=source.name,
                            query=source.url,
                            language=source.language,
                            category=source.category,
                            channel_ids=focus_channels,
                            max_items=args.max_articles,
                            region_code=region,
                            video_duration="medium",
                            safe_search="moderate",
                        )
                        all_articles.extend(focus_videos)

                        remaining = max(0, args.max_articles - len(focus_videos))
                        if remaining == 0:
                            continue
                        yt_videos = scrape_youtube(
                            name=source.name,
                            url=source.url, # passed as query
                            language=source.language,
                            category=source.category,
                            max_items=remaining,
                            region_code=region,
                            video_duration="medium",
                            safe_search="moderate",
                        )
                        all_articles.extend(yt_videos)
                    except Exception as exc:
                         _append_failure(result, "scrape", "YOUTUBE", str(exc), source=source.name)
                         logger.error("[SCRAPE] YouTube source failed: %s | %s", source.name, exc)
            except ImportError:
                 logger.warning("[SCRAPE] google-api-python-client not installed. Skipping YouTube.")
            except Exception as exc:
                 _append_failure(result, "scrape", "YOUTUBE_INIT", str(exc))
                 logger.error("[SCRAPE] Failed to initialize YouTube scraper: %s", exc)

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

    # 5. 分析 (Analysis - LLM)
    try:
        from src.analyzers.llm_analyzer import analyze_articles

        analyzed = analyze_articles(relevant_articles, mock=args.mock)
    except Exception as exc:
        _append_failure(result, "analyze", "LLM", str(exc))
        result.exit_reason = "analysis stage failed"
        result.duration_seconds = round(time.perf_counter() - started, 3)
        return result

    cleaned_analyzed, dropped_fallback = _drop_fallback_analysis(analyzed)
    if dropped_fallback:
        logger.warning(
            "[ANALYZE] Dropped %s fallback articles due to invalid LLM output",
            dropped_fallback,
        )

    # Graceful degradation: if all items are fallback analyses, keep them so
    # downstream delivery can still produce a useful digest instead of hard stop.
    if not cleaned_analyzed and analyzed:
        cleaned_analyzed = analyzed
        logger.warning(
            "[ANALYZE] All %s analyses were fallback; continuing with fallback content",
            len(analyzed),
        )

    result.analyzed_count = len(cleaned_analyzed)
    if not cleaned_analyzed:
        result.success = not args.strict
        result.exit_reason = "analysis produced no usable results"
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
            print("\n" + render_digest_text(cleaned_analyzed, today))
            logger.info("[DELIVERY] Dry run output printed")
        else:
            if args.output in ("email", "both"):
                history_path = os.path.join(args.output_dir, SENT_HISTORY_FILE)
                sent_history = _load_sent_history(history_path)
                used_today_keys: set[str] = set()
                review_mode = not args.approve_send
                reviewer = EMAIL_REVIEWER
                logger.info(
                    "[DELIVERY] Email mode: %s (reviewer=%s)",
                    "review-only" if review_mode else "approved-send",
                    reviewer,
                )

                # Multi-channel delivery based on profiles
                for profile in RECIPIENT_PROFILES:
                    if profile.delivery_channel not in ("email", "both"):
                        continue

                    profile_articles = _select_articles_for_profile(
                        analyzed=cleaned_analyzed,
                        persona=profile.persona,
                        history=sent_history,
                        today=today_obj,
                        target_count=PROFILE_ARTICLE_TARGET,
                        cooldown_days=PROFILE_REPEAT_COOLDOWN_DAYS,
                        globally_used=used_today_keys,
                    )

                    if not profile_articles:
                        logger.info(f"[DELIVERY] No articles for profile '{profile.name}'")
                        continue

                    if len(profile_articles) < PROFILE_ARTICLE_TARGET:
                        logger.warning(
                            "[DELIVERY] Profile '%s' has %s/%s articles after de-dup & cooldown",
                            profile.name,
                            len(profile_articles),
                            PROFILE_ARTICLE_TARGET,
                        )
                    logger.info(
                        "[DELIVERY] Sending %s articles to '%s' (target=%s, cooldown=%s days)",
                        len(profile_articles),
                        profile.name,
                        PROFILE_ARTICLE_TARGET,
                        PROFILE_REPEAT_COOLDOWN_DAYS,
                    )
                    if review_mode:
                        recipient_override = reviewer
                        subject_prefix_override = "[Review] "
                    else:
                        original_recipients = _split_recipients(getattr(profile, "email", ""))
                        filtered_recipients = [
                            item
                            for item in original_recipients
                            if item.casefold() != reviewer.casefold()
                        ]
                        recipient_override = ",".join(_unique_recipients(filtered_recipients))
                        subject_prefix_override = ""
                        if not recipient_override:
                            logger.info(
                                "[DELIVERY] Skip profile '%s': no non-review recipients in approved mode",
                                profile.name,
                            )
                            continue

                    success = send_email(
                        profile_articles,
                        today,
                        profile=profile,
                        recipient_override=recipient_override,
                        subject_prefix_override=subject_prefix_override,
                    )

                    if success and not review_mode:
                        _record_sent(sent_history, profile.persona, profile_articles, today)
                    if args.strict and not success:
                         logger.error(f"[DELIVERY] Failed to send email to '{profile.name}'")
                         # In strict mode, maybe we should raise? But let's verify other profiles first or fail hard.
                         # User requested "fail run on any critical stage error"
                         raise RuntimeError(f"Email delivery failed for profile {profile.name}")

                if not review_mode:
                    _save_sent_history(history_path, sent_history)
                result.email_sent = True # Mark as sent if we got here (individual failures raised if strict)

            if args.output in ("markdown", "both"):
                result.markdown_path = save_digest_markdown(
                    cleaned_analyzed, today=today, output_dir=args.output_dir
                )
                logger.info("[DELIVERY] Markdown digest saved: %s", result.markdown_path)

            if args.output in ("notion", "both"):
                from src.delivery.notion_sender import push_to_notion

                result.notion_pushed = push_to_notion(cleaned_analyzed, today)
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
