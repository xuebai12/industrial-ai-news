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
    title_en: str              # English title
    core_tech_points: str      # Key technical insights
    german_context: str        # German company/application context
    source_name: str           # e.g. "Fraunhofer IPA"
    source_url: str            # Original URL
    summary_zh: str            # One-sentence Chinese summary
    summary_en: str            # One-sentence English summary
    
    # New Dimensions (2026-02-11)
    tool_stack: str = ""       # Identifying software tools (e.g. Siemens, AnyLogic)
    hiring_signals: str = ""   # Hiring/Investment signals
    interview_flip: str = ""   # "Pain Point & Solution" for interviews
    theory_gap: str = ""       # Academic theory (DES) vs Industry practice
    
    original: Article | None = None
