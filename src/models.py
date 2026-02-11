"""Article data models used across the pipeline."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """Raw article from scraping stage."""
    title: str
    url: str
    source: str
    content_snippet: str
    language: str  # "de", "en", "zh"
    category: str
    published_date: datetime | None = None
    relevance_score: int = 0


@dataclass
class AnalyzedArticle:
    """Article after Kimi deep analysis."""
    category_tag: str          # e.g. "Digital Twin", "Research", "Industry 4.0"
    title_zh: str              # Chinese translation of title
    core_tech_points: str      # Key technical insights
    german_context: str        # German company/application context
    source_name: str           # e.g. "Fraunhofer IPA"
    source_url: str            # Original URL
    summary_zh: str            # One-sentence Chinese summary
    original: Article | None = None
