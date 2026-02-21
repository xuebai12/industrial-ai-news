#!/usr/bin/env python3
"""
调试脚本：只跑 抓取 → 去重 → 过滤，输出标题对比报告（MD格式）。
不执行 LLM 分析和投递，快速验证过滤规则效果。

用法:
    python debug_filter.py                  # 完整抓取（含动态）+ 关键词过滤
    python debug_filter.py --skip-dynamic   # 跳过 Playwright 动态抓取
    python debug_filter.py --skip-llm       # 只用关键词（不调 LLM Cloud）
    python debug_filter.py --max 10         # 每源最多抓 10 篇（加快速度）
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="Filter debug: scrape → dedupe → filter, output MD")
    p.add_argument("--skip-dynamic", action="store_true", help="跳过 Playwright 动态抓取")
    p.add_argument("--skip-llm", action="store_true", help="只用关键词过滤，不调 LLM Cloud")
    p.add_argument("--max", type=int, default=20, dest="max_articles", help="每源最多抓取条数（默认 20）")
    p.add_argument("--output-dir", default="output", help="MD 文件输出目录（默认 output）")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")

    # ── 1. 抓取 ────────────────────────────────────────────────────────────
    from config import DATA_SOURCES
    from src.scrapers.rss_scraper import scrape_rss
    from src.scrapers.web_scraper import scrape_web_sources

    YOUTUBE_MAX = int(os.getenv("YOUTUBE_MAX_ITEMS", "5"))
    all_articles = []

    logger.info("=== [SCRAPE] RSS sources ===")
    for source in [s for s in DATA_SOURCES if s.source_type == "rss"]:
        limit = min(args.max_articles, YOUTUBE_MAX) if source.name.lower().startswith("youtube rss:") else args.max_articles
        try:
            arts = scrape_rss(name=source.name, url=source.url,
                              language=source.language, category=source.category,
                              max_items=limit)
            all_articles.extend(arts)
            logger.info("  [RSS] %s  → %d articles", source.name, len(arts))
        except Exception as e:
            logger.warning("  [RSS] %s failed: %s", source.name, e)

    logger.info("=== [SCRAPE] Web sources ===")
    try:
        web = scrape_web_sources(args.max_articles)
        all_articles.extend(web)
        logger.info("  [WEB] %d articles", len(web))
    except Exception as e:
        logger.warning("  [WEB] failed: %s", e)

    if not args.skip_dynamic:
        logger.info("=== [SCRAPE] Dynamic sources (Playwright) ===")
        try:
            from src.scrapers.dynamic_scraper import scrape_dynamic_sources
            dyn = scrape_dynamic_sources(args.max_articles)
            all_articles.extend(dyn)
            logger.info("  [DYN] %d articles", len(dyn))
        except Exception as e:
            logger.warning("  [DYN] failed: %s", e)
    else:
        logger.info("[SCRAPE] Skipping dynamic scrapers (--skip-dynamic)")

    # ── 2. 去重 ────────────────────────────────────────────────────────────
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    def _norm_url(url: str) -> str:
        if not url:
            return ""
        p = urlparse(url.strip())
        netloc = p.netloc.lower().rstrip(":80").rstrip(":443")
        q = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), netloc, path, p.params, q, ""))

    seen: set[str] = set()
    deduped = []
    for a in all_articles:
        key = _norm_url(getattr(a, "url", "") or "")
        if not key:
            key = f"{getattr(a, 'source', '')}:{getattr(a, 'title', '')}"
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    logger.info("[DEDUPE] %d → %d", len(all_articles), len(deduped))

    # ── 3. 关键词评分（不调 LLM，先看关键词层） ─────────────────────────────
    from src.filters.ollama_filter import keyword_score, RELEVANCE_THRESHOLD

    scored_pass, scored_fail = [], []
    for a in deduped:
        score, _ = keyword_score(a)
        a.relevance_score = score
        (scored_pass if score >= RELEVANCE_THRESHOLD else scored_fail).append(a)

    logger.info("[KW-FILTER] pass=%d  fail=%d  threshold=%d",
                len(scored_pass), len(scored_fail), RELEVANCE_THRESHOLD)

    # ── 4. LLM Cloud 过滤（可选） ─────────────────────────────────────────
    if not args.skip_llm:
        from src.filters.ollama_filter import filter_articles
        final_pass = filter_articles(deduped, skip_llm=False)
        llm_note = "（关键词 + LLM 双重过滤）"
    else:
        final_pass = sorted(scored_pass, key=lambda a: a.relevance_score, reverse=True)
        llm_note = "（仅关键词过滤，已跳过 LLM）"

    # ── 5. 输出 MD ────────────────────────────────────────────────────────
    lines = [
        f"# 过滤调试报告 {today}",
        "",
        f"> 抓取 {len(all_articles)} → 去重后 {len(deduped)} → 关键词通过 {len(scored_pass)} → 最终通过 {len(final_pass)} {llm_note}",
        "",
        "---",
        "",
        f"## ✅ 通过过滤的新闻（{len(final_pass)} 条）",
        "",
    ]
    for i, a in enumerate(final_pass, 1):
        title = getattr(a, "title", "").strip() or "(无标题)"
        cat = getattr(a, "category", "")
        score = getattr(a, "relevance_score", "?")
        url = getattr(a, "url", "") or ""
        lines.append(f"{i:02d}. [{cat}] {title} _(score={score})_  \n    {url}")

    lines += [
        "",
        "---",
        "",
        f"## ❌ 被过滤掉的新闻（{len(scored_fail)} 条关键词=0）",
        "",
    ]
    for i, a in enumerate(sorted(scored_fail, key=lambda x: getattr(x, "title", "")), 1):
        title = getattr(a, "title", "").strip() or "(无标题)"
        cat = getattr(a, "category", "")
        url = getattr(a, "url", "") or ""
        lines.append(f"{i:02d}. [{cat}] {title}  \n    {url}")

    out_path = os.path.join(args.output_dir, f"debug-filter-{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info("[DONE] 报告已写入: %s", out_path)
    print(f"\n📄 报告路径: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
