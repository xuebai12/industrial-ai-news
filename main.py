#!/usr/bin/env python3
"""
Industrial AI & Simulation Daily Intelligence System
=====================================================
Main orchestrator: Scrape → Filter → Analyze → Deliver

Usage:
    python main.py                    # Full pipeline, send email
    python main.py --dry-run          # Print to stdout, no email
    python main.py --output markdown  # Save as Markdown file
    python main.py --skip-dynamic     # Skip Playwright scrapers
"""

import argparse
import logging
import sys
from datetime import date

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
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
        choices=["email", "markdown", "both"],
        default="email",
        help="Output format (default: email)",
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
    return parser.parse_args()


def main():
    import os
    import traceback
    
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    try:
        args = parse_args()
        today = date.today().strftime("%Y-%m-%d")

        logger.info("=" * 60)
        logger.info(f"📅 Industrial AI Intelligence Pipeline — {today}")
        logger.info("=" * 60)

        # =============================================
        # Stage 1: SCRAPE
        # =============================================
        logger.info("\n🔍 Stage 1: Scraping data sources...")
        from src.scrapers.rss_scraper import scrape_rss
        from src.scrapers.web_scraper import scrape_web_sources
        from config import DATA_SOURCES

        all_articles = []

        # RSS feeds
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
            except Exception as e:
                logger.error(f"[SCRAPE] Failed RSS {source.name}: {e}")

        # Static web scrapers
        try:
            web_articles = scrape_web_sources(args.max_articles)
            all_articles.extend(web_articles)
        except Exception as e:
            logger.error(f"[SCRAPE] Failed Web Scraping: {e}")

        # Dynamic scrapers (optional)
        if not args.skip_dynamic:
            try:
                from src.scrapers.dynamic_scraper import scrape_dynamic_sources
                dynamic_articles = scrape_dynamic_sources(args.max_articles)
                all_articles.extend(dynamic_articles)
            except Exception as e:
                logger.warning(f"Dynamic scraping failed (continuing without): {e}")
        else:
            logger.info("[SCRAPE] Skipping dynamic scrapers (--skip-dynamic)")

        logger.info(f"📊 Total scraped: {len(all_articles)} articles")

        if not all_articles:
            logger.warning("No articles scraped. Check data source configuration.")
            # Create a dummy file so artifact upload doesn't fail
            with open("output/no_articles.txt", "w") as f:
                f.write("No articles were scraped today.")
            sys.exit(0)

        # =============================================
        # Stage 2: FILTER
        # =============================================
        logger.info("\n🔎 Stage 2: Filtering for relevance...")
        from src.filters.ollama_filter import filter_articles

        relevant_articles = filter_articles(all_articles, skip_llm=args.skip_llm_filter)
        logger.info(f"📊 Relevant articles: {len(relevant_articles)}")

        if not relevant_articles:
            logger.info("No relevant articles found today. Exiting.")
            with open("output/no_relevant.txt", "w") as f:
                f.write("Articles were scraped but none matched relevance criteria.")
            sys.exit(0)

        # =============================================
        # Stage 3: ANALYZE
        # =============================================
        logger.info("\n📝 Stage 3: Deep analysis via Kimi Cloud...")
        from src.analyzers.kimi_analyzer import analyze_articles

        analyzed = analyze_articles(relevant_articles)
        logger.info(f"📊 Analyzed articles: {len(analyzed)}")

        if not analyzed:
            logger.warning("Analysis produced no results.")
            sys.exit(0)

        # =============================================
        # Stage 4: DELIVER
        # =============================================
        logger.info("\n📤 Stage 4: Delivering digest...")
        from src.delivery.email_sender import (
            render_digest_text,
            send_email,
            save_digest_markdown,
        )

        if args.dry_run:
            print("\n" + render_digest_text(analyzed, today))
            logger.info("✅ Dry run complete (output printed to stdout)")
        else:
            if args.output in ("email", "both"):
                send_email(analyzed, today)

            if args.output in ("markdown", "both") or True: # Always save markdown in CI
                filepath = save_digest_markdown(analyzed, today=today, output_dir="output")
                logger.info(f"📄 Markdown digest: {filepath}")

        logger.info("\n✅ Pipeline complete!")

    except Exception as e:
        logger.critical(f"🔥 Pipeline failed: {e}")
        traceback.print_exc()
        # Save error log
        with open("output/error.log", "w") as f:
            f.write(f"Pipeline failed: {e}\n\n")
            traceback.print_exc(file=f)
        sys.exit(1)


if __name__ == "__main__":
    main()
