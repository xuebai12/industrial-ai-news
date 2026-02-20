"""Email delivery module using SMTP."""
"""
邮件交付模块 (Email Delivery Module)
使用 SMTP 协议发送 HTML 或纯文本格式的日报。
"""

import logging
import os
import smtplib
import re
import html
from collections import Counter
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

from config import EMAIL_FROM, EMAIL_TO, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)

# --- Pre-compiled regexes (module-level for performance) ---
_RE_WHITESPACE = re.compile(r"\s+")
_RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_RE_KEYWORD_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{2,}")

STOPWORDS_DE = {
    "und", "oder", "aber", "mit", "ohne", "fuer", "dass", "eine", "einer", "eines", "einem",
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "ist", "sind", "war", "waren",
    "wird", "werden", "von", "zu", "im", "in", "auf", "am", "an", "bei", "als", "auch",
    "nicht", "mehr", "noch", "ueber", "unter", "nach", "vor", "aus", "durch", "pro", "nur",
    "heute", "artikel", "quelle", "details", "top", "relevanz", "hoch",
}

STOPWORDS_EN = {
    "the", "and", "or", "with", "without", "for", "from", "this", "that", "these", "those",
    "are", "is", "was", "were", "be", "been", "to", "in", "on", "at", "as", "of", "by",
    "an", "a", "it", "its", "into", "about", "over", "under", "more", "less", "today",
}


I18N_LABELS = {
    "en": {
        "title": "Industrial AI Daily Digest",
        "tagline": "Signal first: key updates for industrial decision-making and implementation.",
        "stats": "Today we selected <strong>{{ count }}</strong> relevant updates",
        "simple_explain_label": "Plain-English Takeaway",
        "tech_points_label": "Core Technology",
        "application_label": "Application Context",
        "source_label": "Source",
        "link_label": "Read Original",
        "overview_title": "Today's Overview",
        "top_title": "Top Picks",
        "no_articles": "No articles today.",
        "date_suffix": "Industrial AI & Simulation",
        "subject_suffix": "Industrial AI Digest",
        "footer": "Industrial AI Intelligence System",
        "tech_highlight_label": "Technical Highlights",
        "app_value_label": "Application Value",
        "core_mechanism_label": "Core Mechanism",
        "combined_focus_label": "Key Focus",
    },
    "zh": {
        "title": "工业 AI 每日摘要",
        "tagline": "聚焦可执行信号：面向工业决策与落地的关键更新。",
        "stats": "今日共筛选出 <strong>{{ count }}</strong> 条相关情报",
        "simple_explain_label": "通俗解读",
        "tech_points_label": "核心技术",
        "application_label": "应用背景",
        "source_label": "来源",
        "link_label": "查看原文",
        "overview_title": "今日总览",
        "top_title": "最值得看",
        "no_articles": "今日无文章。",
        "date_suffix": "工业 AI 与仿真",
        "subject_suffix": "工业 AI 每日摘要",
        "footer": "Industrial AI Intelligence System",
        "tech_highlight_label": "技术亮点",
        "app_value_label": "应用价值",
        "core_mechanism_label": "核心机制",
        "combined_focus_label": "重点信息",
    },
    "de": {
        "title": "Industrial AI Tageszusammenfassung",
        "tagline": "Klare Signale: Relevante Updates fuer industrielle Entscheidungen und Umsetzung.",
        "stats": "Heute wurden <strong>{{ count }}</strong> relevante Berichte ausgewählt",
        "simple_explain_label": "Worauf achten?",
        "tech_points_label": "Was passiert technisch?",
        "application_label": "Welcher Nutzen entsteht?",
        "source_label": "Quelle",
        "link_label": "Originalartikel",
        "overview_title": "Tagesueberblick",
        "top_title": "Top 3",
        "no_articles": "Heute keine Artikel.",
        "date_suffix": "Industrial AI und Simulation",
        "subject_suffix": "Industrial AI Tageszusammenfassung",
        "footer": "Industrial AI Intelligence System (DE)",
        "tech_highlight_label": "Technische Highlights",
        "app_value_label": "Anwendungswert",
        "core_mechanism_label": "Kernmechanismus",
        "combined_focus_label": "Kernfokus",
    },
}


EMAIL_TEMPLATE = Template(
    """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 920px; margin: 0 auto; padding: 20px; color: #1f2937; background: #f3f5f9; }
  body.technician-mode, .technician-mode { font-family: Arial, Helvetica, sans-serif; line-height: 1.6; letter-spacing: 0.02em; background: #f5f5f5; }
  .header { background: linear-gradient(120deg, #0b3c7f, #0f5db8); color: #fff;
            padding: 22px; border-radius: 12px; margin-bottom: 14px; }
  .header h1 { margin: 0; font-size: 22px; letter-spacing: 0.2px; }
  .header .date { opacity: 0.9; font-size: 13px; margin-top: 6px; }
  .header .tagline { margin-top: 10px; font-size: 14px; opacity: 0.95; line-height: 1.5; }
  .section { margin: 0 0 16px; }
  .section-title { margin: 0 0 10px; font-size: 17px; color: #0b3c7f; font-weight: 700; }
  .article { background: #fff; border: 1px solid #dbe3ee; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
  .category { display: inline-block; background: #eaf2ff; color: #144a9e;
              padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .article h3 { margin: 8px 0 6px; font-size: 17px; color: #0f172a; }
  .subtle { font-size: 12px; color: #667085; margin-bottom: 10px; }
  .quick-grid-title { font-size: 12px; font-weight: 700; color: #0b3c7f; text-transform: uppercase; letter-spacing: 0.2px; margin: 4px 0 2px; }
  .stack-cards { margin: 6px 0 10px; }
  .quick-card { border-radius: 10px; padding: 12px; min-height: 0; }
  .quick-card + .quick-card { margin-top: 10px; }
  .quick-card.blue { background: #eff6ff; border-left: 8px solid #1d4ed8; color: #1e3a8a; }
  .quick-card.orange { background: #fff7ed; border-left: 8px solid #ea580c; color: #9a3412; }
  .quick-card .label { margin-bottom: 8px; color: #111827; display: block; }
  .quick-card .value { font-size: 15px; line-height: 1.75; white-space: pre-line; margin: 0; }
  .focus-list { margin: 0; padding-left: 18px; white-space: normal; font-size: 15px; line-height: 1.5; letter-spacing: 0; }
  .focus-list li { margin: 0 0 6px; }
  .focus-list li:last-child { margin-bottom: 0; }
  .mechanism-list { margin: 0; padding-left: 20px; font-size: 15px; line-height: 1.5; letter-spacing: 0; }
  .mechanism-list li { margin: 0 0 6px; }
  .mechanism-list li:last-child { margin-bottom: 0; }
  .focus-panel { margin: 10px 0 14px; background: #f8fafc; border: 1px solid #dbe3ee; border-radius: 10px; padding: 10px; }
  .focus-title { font-size: 12px; font-weight: 700; color: #0b3c7f; text-transform: uppercase; letter-spacing: 0.2px; margin-bottom: 8px; }
  .focus-cell { width: 50%; vertical-align: top; padding: 4px; }
  .focus-item { background: #ffffff; border: 1px solid #dbe3ee; border-radius: 8px; padding: 10px; font-size: 13px; line-height: 1.55; color: #0f172a; min-height: 56px; }
  .row { margin: 8px 0; }
  .label { display: block; font-size: 12px; color: #475467; font-weight: 700; text-transform: uppercase;
           letter-spacing: 0.2px; margin-bottom: 4px; }
  .value { font-size: 14px; line-height: 1.6; color: #1f2937; }
  body.technician-mode .article, .technician-mode .article { border: 2px solid #d1d5db; background: #ffffff; }
  body.technician-mode .row, .technician-mode .row { margin: 0 0 34px; padding: 8px; border-radius: 8px; }
  body.technician-mode .value, .technician-mode .value { line-height: 1.8; letter-spacing: 0.02em; white-space: pre-line; padding: 12px 14px; border-radius: 6px; font-size: 16px; }
  body.technician-mode .row.tech-block, .technician-mode .row.tech-block { background: #dbeafe; }
  body.technician-mode .row.tech-block .value, .technician-mode .row.tech-block .value { border-left: 8px solid #1d4ed8; background: #eff6ff; color: #1e3a8a; }
  body.technician-mode .row.benefit-block, .technician-mode .row.benefit-block { background: #dcfce7; }
  body.technician-mode .row.benefit-block .value, .technician-mode .row.benefit-block .value { border-left: 8px solid #16a34a; background: #f0fdf4; color: #14532d; }
  body.technician-mode .row.issue-block, .technician-mode .row.issue-block { background: #ffedd5; }
  body.technician-mode .row.issue-block .value, .technician-mode .row.issue-block .value { border-left: 8px solid #ea580c; background: #fff7ed; color: #9a3412; }
  body.technician-mode .row .label, .technician-mode .row .label { margin-bottom: 10px; font-size: 13px; color: #111827; letter-spacing: 0.3px; }
  body.technician-mode strong, .technician-mode strong { font-size: 17px; }
  @media (max-width: 640px) {
    body { padding: 12px; }
    .stack-cards { margin: 6px 0 8px; }
    .quick-card { min-height: auto; }
    body.technician-mode .header, .technician-mode .header { padding: 16px; }
    body.technician-mode .article, .technician-mode .article { padding: 12px; border-width: 2px; }
    body.technician-mode .row, .technician-mode .row { margin: 0 0 30px; padding: 6px; }
    body.technician-mode .value, .technician-mode .value { font-size: 17px; line-height: 1.85; padding: 12px; }
    body.technician-mode .row.tech-block .value, .technician-mode .row.tech-block .value { border-left-width: 9px; }
    body.technician-mode .row.benefit-block .value, .technician-mode .row.benefit-block .value { border-left-width: 9px; }
    body.technician-mode .row.issue-block .value, .technician-mode .row.issue-block .value { border-left-width: 9px; }
    body.technician-mode .source, .technician-mode .source { font-size: 14px; }
  }
  .source { margin-top: 10px; font-size: 13px; color: #344054; }
  .source a { color: #175cd3; text-decoration: none; }
  .footer { text-align: center; padding: 16px 8px 8px; font-size: 12px; color: #98a2b3; }
</style>
</head>
<body class="{{ 'technician-mode' if technician_mode else '' }}">
  <div class="{{ 'technician-mode' if technician_mode else '' }}">
  <div class="header">
    <h1>{{ labels.title }}</h1>
    <div class="date">{{ today }} | {{ date_suffix }}</div>
    <div class="tagline">{{ labels.tagline }}</div>
  </div>

  {% for group in grouped_articles %}
  <div class="section">
    <div class="section-title">{{ group["name"] }}</div>
    {% if not group["items"] %}
    <div class="article">{{ labels.no_articles }}</div>
    {% endif %}
    {% for article in group["items"] %}
  <div class="article">
    {% if not technician_mode %}
    <span class="category">{{ article.category_tag }}</span>
    {% endif %}

    <h3>{{ article.display_title }}</h3>
    {% if article.subtitle %}
    <div class="subtle">{{ article.title_en }}</div>
    {% endif %}

    {% if technician_mode %}
    <div class="quick-grid-title">{{ labels.combined_focus_label }}</div>
    <div class="stack-cards">
      <div class="quick-card blue">
        <span class="label">{{ labels.combined_focus_label }}</span>
        <ul class="focus-list">
          {% for point in article.tech_focus_list %}
          <li>{{ point }}</li>
          {% endfor %}
        </ul>
      </div>
      <div class="quick-card orange">
        <span class="label">{{ labels.core_mechanism_label }}</span>
        <ol class="mechanism-list">
          {% for point in article.mechanism_steps %}
          <li>{{ point }}</li>
          {% endfor %}
        </ol>
      </div>
    </div>
    {% else %}
    <div class="row">
      <span class="label">{{ labels.tech_points_label }}</span>
      <div class="value">{{ article.core_tech_compact }}</div>
    </div>

    <div class="row">
      <span class="label">{{ labels.application_label }}</span>
      <div class="value">{{ article.context_compact }}</div>
    </div>

    <div class="row">
      <span class="label">{{ labels.simple_explain_label }}</span>
      <div class="value">{{ article.simple_explanation }}</div>
    </div>
    {% endif %}

    {% if not technician_mode %}
    <div class="source">
      {{ labels.source_label }}: {{ article.source_name }} |
      <a href="{{ article.source_url }}">{{ labels.link_label }}</a>
    </div>
    {% endif %}
  </div>
    {% endfor %}
  </div>
  {% endfor %}

  <div class="footer">
    {{ labels.footer }}
  </div>
  </div>
</body>
</html>
"""
)


def _clip(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _pick_title(article: AnalyzedArticle, lang: str) -> str:
    if lang == "en":
        return article.title_en or "English title unavailable"
    if lang == "de":
        return article.title_de or "Deutscher Titel nicht verfügbar"
    return article.title_zh or article.title_en or article.title_de


def _pick_primary_summary(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.summary_de or article.summary_en or article.summary_zh
    return article.summary_zh or article.summary_en or article.summary_de


def _pick_secondary_summary(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.summary_en if article.summary_en != article.summary_de else ""
    return article.summary_en if article.summary_en != article.summary_zh else ""


def _pick_title_for_persona(article: AnalyzedArticle, persona: str) -> str:
    """Return the appropriate article title for a given persona.

    Args:
        article: The analyzed article containing multi-language titles.
        persona: Recipient persona ("student", "technician", or "").

    Returns:
        Title string in the most appropriate language for the persona.
    """
    if persona == "student":
        return article.title_en or "English title unavailable"
    if persona == "technician":
        return article.title_de or "Deutscher Titel nicht verfügbar"
    return article.title_zh or article.title_en or "N/A"


def _pick_explanation(article: AnalyzedArticle, persona: str) -> str:
    """Select persona-specific explanation text with stable language preference."""
    if persona == "technician":
        return (
            article.technician_analysis_de
            or article.summary_de
            or "Keine deutschsprachige Analyse verfügbar."
        ).strip()
    if persona == "student":
        # Student digest should stay in English regardless of profile language.
        return (article.summary_en or "English summary unavailable.").strip()
    return (article.simple_explanation or article.summary_en or "N/A").strip()


def _pick_technician_focus_note(article: AnalyzedArticle) -> str:
    """Return a short German-only add-on note for technician digest."""
    value = (article.summary_de or "").strip()
    if value:
        return value
    return "Keine kurze deutsche Zusatznotiz verfuegbar."


def _pick_technician_application_value(article: AnalyzedArticle) -> str:
    """Return German-only application value text for technician digest."""
    value = (article.summary_de or "").strip()
    if value:
        return value
    return "Kein deutscher Anwendungshinweis verfuegbar."


def _extract_technician_highlights(text: str, limit: int = 4) -> list[str]:
    """Extract up to 4 concise German key points from technician text."""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [
        p.strip(" -•\t,;:[]{}\"'")
        for p in re.split(r"\n+|(?<=[.!?])\s+", raw)
        if p.strip(" -•\t,;:[]{}\"'")
    ]
    highlights: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = re.sub(r"^(?:\d+[\.\)]\s*)", "", part).strip(" []{}\"'")
        if not cleaned:
            continue
        words = cleaned.split()
        if len(words) > 14:
            cleaned = " ".join(words[:14]).rstrip(" ,;:.") + "."
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        highlights.append(html.escape(cleaned))
        if len(highlights) >= limit:
            break
    return highlights


def _extract_compact_points(text: str, limit: int = 3, max_words: int = 10) -> list[str]:
    """Extract compact German bullet points for technician focus cards."""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [
        p.strip(" -•\t,;:[]{}\"'")
        for p in re.split(r"\n+|(?<=[.!?])\s+", raw)
        if p.strip(" -•\t,;:[]{}\"'")
    ]
    points: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = re.sub(r"^(?:\d+[\.\)]\s*)", "", part).strip(" []{}\"'")
        if not cleaned:
            continue
        words = cleaned.split()
        if len(words) > max_words:
            cleaned = " ".join(words[:max_words]).rstrip(" ,;:.") + "."
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        points.append(html.escape(cleaned))
        if len(points) >= limit:
            break
    return points


def _pair_highlights(items: list[str]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for idx in range(0, len(items), 2):
        left = items[idx]
        right = items[idx + 1] if idx + 1 < len(items) else ""
        rows.append((left, right))
    return rows


def _extract_mechanism_steps(text: str, limit: int = 3) -> list[str]:
    """Extract short, beginner-friendly mechanism steps for technician cards."""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [
        p.strip(" -•\t,;:[]{}\"'")
        for p in re.split(r"\n+|(?<=[.!?])\s+", raw)
        if p.strip(" -•\t,;:[]{}\"'")
    ]
    steps: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = re.sub(r"^(?:\d+[\.\)]\s*)", "", part).strip(" []{}\"'")
        if not cleaned:
            continue
        words = cleaned.split()
        if len(words) > 18:
            cleaned = " ".join(words[:18]).rstrip(" ,;:.") + "."
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        steps.append(html.escape(cleaned))
        if len(steps) >= limit:
            break
    return steps


def _build_vivid_mechanism_steps(text: str) -> list[str]:
    """Explain the mechanism with concrete analogies for non-technical readers."""
    steps = _extract_mechanism_steps(text, limit=3)
    if not steps:
        return [
            "Wie ein Fruehwarnsystem am Auto: Die Maschine meldet kleinste Warnzeichen sofort.",
            "Wie ein persoenlicher Maschinenarzt: Das System lernt den gesunden Normalzustand.",
            "Wie ein Wartungs-Kalender mit Vorwarnung: Eingriffe kommen geplant vor dem Ausfall.",
        ]
    metaphors = [
        "Wie ein Fitness-Tracker fuer Maschinen",
        "Wie ein persoenlicher Arzt fuer den Anlagenzustand",
        "Wie ein Rauchmelder mit Vorwarnung fuer Ausfaelle",
    ]
    vivid: list[str] = []
    for idx, step in enumerate(steps):
        prefix = metaphors[idx] if idx < len(metaphors) else "Wie ein klares Leitsystem im Betrieb"
        vivid.append(f"{prefix}: {step}")
    return vivid


def _localize_context_for_technician(text: str) -> str:
    """Map common structured English field labels to German for the technician digest.

    Args:
        text: Raw context string, potentially containing English label prefixes.

    Returns:
        Context string with English labels replaced by German equivalents.
        Falls back to a German placeholder when the input is empty.
    """
    value = (text or "").strip()
    if not value:
        return "Kein Anwendungskontext verfügbar."
    replacements = {
        r"\bRelevance:\s*": "Relevanz: ",
        r"\bIndustry Sectors:\s*": "Industriebereiche: ",
        r"\bRegulatory Aspects:\s*": "Regulatorische Aspekte: ",
        r"\bResearch Institutions:\s*": "Forschungseinrichtungen: ",
    }
    for pattern, target in replacements.items():
        value = re.sub(pattern, target, value)
    return value


def _simplify_for_beginner_de(text: str) -> str:
    """Replace hard technical abbreviations with plain-German wording for beginners.

    Args:
        text: German text potentially containing technical abbreviations.

    Returns:
        Text with known abbreviations replaced by beginner-friendly terms.
        Returns empty string when the input is empty.
    """
    value = (text or "").strip()
    if not value:
        return ""
    simple_map = {
        r"\bSPS\b": "Steuerungsrechner",
        r"\bPLC\b": "Steuerungsrechner",
        r"\bTIA Portal\b": "Siemens-Programmieroberflaeche",
        r"\bOEE\b": "Anlagen-Leistung",
        r"\bModell\b": "Rechenmodell",
        r"\bInstandhaltung\b": "Wartung",
        r"\bPredictive Maintenance\b": "vorausschauende Wartung",
    }
    for pattern, target in simple_map.items():
        value = re.sub(pattern, target, value, flags=re.IGNORECASE)
    return value


def _emphasize_sentence_leads_html(text: str) -> str:
    """Bold the leading keyword of each sentence to improve scanability.

    Each sentence or line is split and its first token is wrapped in
    ``<strong>`` tags. Purely punctuation-only fragments are emitted as-is.

    Args:
        text: Plain text to transform.

    Returns:
        HTML string with sentence leads bolded and sentences joined by ``<br>``.
    """
    value = (text or "").strip()
    if not value:
        return ""
    value = _RE_WHITESPACE.sub(" ", value)
    parts = [seg.strip(" -•\t") for seg in _RE_SENTENCE_SPLIT.split(value) if seg.strip(" -•\t")]
    rendered: list[str] = []
    for part in parts:
        tokens = part.split(maxsplit=1)
        lead = html.escape(tokens[0].strip(" ,;:"))
        rest = html.escape(tokens[1]) if len(tokens) > 1 else ""
        if not lead:
            # Part was purely punctuation — emit as-is without bolding
            rendered.append(html.escape(part))
            continue
        if rest:
            rendered.append(f"<strong>{lead}</strong> {rest}")
        else:
            rendered.append(f"<strong>{lead}</strong>")
    return "<br>".join(rendered)


def _extract_daily_keywords(
    articles: list[AnalyzedArticle], lang: str, limit: int = 5
) -> list[str]:
    """Extract top keywords from daily articles for header subtitle."""
    if not articles:
        return []

    stopwords = STOPWORDS_DE if lang == "de" else STOPWORDS_EN
    counts: Counter[str] = Counter()
    display_map: dict[str, str] = {}
    pattern = _RE_KEYWORD_TOKEN

    def _ingest(text: str, weight: int = 1) -> None:
        for raw in pattern.findall(text or ""):
            token = raw.strip("-")
            if any(ch.isdigit() for ch in token):
                continue
            key = token.casefold()
            if key in stopwords or len(key) < 3:
                continue
            counts[key] += weight
            display_map.setdefault(key, token)

    for article in articles:
        if lang == "de":
            _ingest(article.title_de, weight=3)
            _ingest(article.core_tech_points, weight=2)
            _ingest(article.german_context, weight=2)
            _ingest(article.technician_analysis_de, weight=1)
        elif lang == "en":
            _ingest(article.title_en, weight=3)
            _ingest(article.summary_en, weight=2)
            _ingest(article.core_tech_points, weight=2)
        else:
            _ingest(article.title_zh, weight=3)
            _ingest(article.title_en, weight=2)
            _ingest(article.core_tech_points, weight=2)

    ranked = [key for key, _ in counts.most_common(limit * 3)]
    keywords: list[str] = []
    for key in ranked:
        token = display_map.get(key, key)
        if token.isupper() and len(token) <= 8:
            display = token
        else:
            display = token[:1].upper() + token[1:]
        if display not in keywords:
            keywords.append(display)
        if len(keywords) >= limit:
            break
    return keywords


def _normalize_theme(category_tag: str) -> str:
    """Map a free-form category tag to one of the canonical theme buckets.

    Args:
        category_tag: Raw category string from the analyzed article.

    Returns:
        One of the canonical theme names used by ``_group_articles_by_theme``.
    """
    value = (category_tag or "").strip().casefold()
    if (
        "policy" in value
        or "regulat" in value
        or "standard" in value
        or "compliance" in value
    ):
        return "Standards & Regulation"
    if "cyber" in value or "security" in value or "ot " in value or "ics" in value:
        return "OT Cybersecurity"
    if (
        "semiconductor" in value
        or "chip" in value
        or "sensor" in value
        or "edge" in value
        or "hardware" in value
    ):
        return "Semiconductors & Hardware"
    if (
        "industry 4.0" in value
        or "digital twin" in value
        or "simulation" in value
        or "automation" in value
        or "robot" in value
        or "manufacturing" in value
    ):
        return "Industry 4.0 & Automation"
    if (
        "supply chain" in value
        or "logistics" in value
        or "procurement" in value
        or "warehouse" in value
    ):
        return "Supply Chain & Logistics"
    if (
        "energy" in value
        or "sustainability" in value
        or "carbon" in value
        or "esg" in value
    ):
        return "Energy & Sustainability"
    if "ai" in value or "ml" in value or "llm" in value or "research" in value:
        return "AI"
    return "Industry 4.0 & Automation"


def _localize_theme_name(theme: str, lang: str, persona: str) -> str:
    if persona != "technician" or lang != "de":
        return theme
    mapping = {
        "AI": "KI",
        "Industry 4.0 & Automation": "Industrie 4.0 & Automatisierung",
        "OT Cybersecurity": "OT-Sicherheit",
        "Semiconductors & Hardware": "Halbleiter & Hardware",
        "Energy & Sustainability": "Energie & Nachhaltigkeit",
        "Supply Chain & Logistics": "Lieferkette & Logistik",
        "Standards & Regulation": "Normen & Regulierung",
    }
    return mapping.get(theme, theme)


def _group_articles_by_theme(rendered_articles: list[dict[str, str]], max_per_group: int = 5) -> list[dict[str, object]]:
    order = [
        "AI",
        "Industry 4.0 & Automation",
        "OT Cybersecurity",
        "Semiconductors & Hardware",
        "Energy & Sustainability",
        "Supply Chain & Logistics",
        "Standards & Regulation",
    ]
    bucket: dict[str, list[dict[str, str]]] = {name: [] for name in order}
    for item in rendered_articles:
        theme = _normalize_theme(item.get("category_tag", ""))
        if theme not in bucket:
            theme = "Industry 4.0 & Automation"
        if len(bucket[theme]) < max_per_group:
            bucket[theme].append(item)
    return [{"name": theme, "items": bucket[theme]} for theme in order if bucket[theme]]


def render_digest(
    articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None
) -> str:
    """Render the daily digest as an HTML email body.

    Args:
        articles: LLM-analyzed articles to include in the digest.
        today: Date string in ``YYYY-MM-DD`` format. Defaults to today.
        profile: ``RecipientProfile`` instance controlling language and persona.
            When ``None`` the Chinese / default persona is used.

    Returns:
        Fully rendered HTML string ready to attach to a MIME message.
    """
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    technician_mode = persona == "technician"
    base_lang = getattr(profile, "language", "zh") if profile else "zh"
    lang = "en" if persona == "student" else base_lang
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])
    # Truncation is disabled; fields are rendered in full.
    daily_keywords = _extract_daily_keywords(articles, lang, limit=5)
    date_suffix = ", ".join(daily_keywords) if len(daily_keywords) >= 3 else labels.get("date_suffix", "")

    rendered_articles = []
    for article in articles:
        display_title_raw = (_pick_title(article, lang) or "").strip()
        title_en_raw = (article.title_en or "").strip()
        subtitle = ""
        if (
            persona != "technician"
            and title_en_raw
            and title_en_raw.casefold() != display_title_raw.casefold()
        ):
            subtitle = _clip(title_en_raw, 200)
        context_text = (article.german_context or "").strip() or "N/A"
        if persona == "technician":
            context_text = _localize_context_for_technician(context_text)
        # For technician mode: blue block uses technician_analysis_de;
        # for other personas: use core_tech_points as before.
        if persona == "technician":
            core_text = (
                article.technician_analysis_de
                or "Keine technischen Kerndetails verfügbar."
            ).strip()
        else:
            core_text = (article.core_tech_points or "").strip() or "N/A"
        # Orange issue-block:
        # - technician: always short German note to avoid mixed-language artifacts
        # - others: simple explanation as before
        simple_explanation = (article.simple_explanation or "").strip() or "N/A"
        if persona == "student":
            # Student digest should stay in English regardless of profile language.
            simple_explanation = (article.summary_en or "English summary unavailable.").strip()
        if technician_mode:
            simple_explanation = _pick_technician_focus_note(article)
            core_text = _simplify_for_beginner_de(core_text)
            context_text = _simplify_for_beginner_de(_pick_technician_application_value(article))
            simple_explanation = _simplify_for_beginner_de(simple_explanation)
            scenario_text = " ".join(
                seg for seg in [
                    context_text,
                    (article.german_context or "").strip(),
                    (article.summary_de or "").strip(),
                ]
                if seg
            ).strip()
            tech_focus_list = _extract_compact_points(scenario_text, limit=3, max_words=10)
            if len(tech_focus_list) < 2:
                tech_focus_list.append("Einsatz im Betrieb: klare Anwendung an Linie, Anlage und Wartungsfenster.")
            tech_focus_list = tech_focus_list[:3]
            # Keep plain text for better readability and stable Gmail rendering.
            core_text = html.escape(core_text)
            context_text = html.escape(context_text)
            simple_explanation = html.escape(simple_explanation)
            core_mechanism_raw = (
                article.technician_analysis_de
                or article.summary_de
                or "Keine Kernmechanik verfuegbar."
            )
            core_mechanism = html.escape(_simplify_for_beginner_de(core_mechanism_raw))
            mechanism_steps = _build_vivid_mechanism_steps(core_mechanism_raw)
            if not mechanism_steps:
                mechanism_steps = [core_mechanism]
            highlight_rows = []
            tech_highlights = ""
            app_value = ""
        else:
            highlight_rows = []
            tech_highlights = ""
            app_value = ""
            core_mechanism = ""
            mechanism_steps = []
            tech_focus_list = []

        rendered_articles.append(
            {
                "category_tag": article.category_tag,
                "display_title": _clip(display_title_raw, 200),
                "title_en": subtitle,
                "subtitle": subtitle,
                "core_tech_compact": core_text,
                "context_compact": context_text,
                "simple_explanation": (simple_explanation or "N/A").strip(),
                "highlight_rows": highlight_rows,
                "tech_highlights": tech_highlights,
                "app_value": app_value,
                "tech_focus_list": tech_focus_list,
                "core_mechanism": core_mechanism,
                "mechanism_steps": mechanism_steps,
                "source_name": article.source_name,
                "source_url": article.source_url,
            }
        )

    grouped_articles = _group_articles_by_theme(rendered_articles, max_per_group=5)
    if not grouped_articles:
        grouped_articles = [{"name": labels.get("overview_title", "Overview"), "items": []}]
    else:
        for group in grouped_articles:
            group["name"] = _localize_theme_name(str(group.get("name", "")), lang=lang, persona=persona)

    # Pre-compute the stats string to avoid the Jinja2 "replace {{ count }}" anti-pattern.
    stats_text = labels["stats"].replace("{{ count }}", str(len(articles)))

    return EMAIL_TEMPLATE.render(
        today=today,
        date_suffix=date_suffix,
        articles=rendered_articles,
        grouped_articles=grouped_articles,
        stats_text=stats_text,
        profile=profile,
        labels=labels,
        technician_mode=technician_mode,
    )


def render_digest_text(
    articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None
) -> str:
    """Render the daily digest as plain text (for dry-runs or MIME plain-text part).

    Args:
        articles: LLM-analyzed articles to include in the digest.
        today: Date string in ``YYYY-MM-DD`` format. Defaults to today.
        profile: ``RecipientProfile`` instance controlling language and persona.

    Returns:
        Plain-text digest string.
    """
    if today is None:
        today = date.today().strftime("%Y-%m-%d")
    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    base_lang = getattr(profile, "language", "zh") if profile else "zh"
    lang = "en" if persona == "student" else base_lang
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])
    if persona == "technician":
        header = "[Industrial AI Tageszusammenfassung]"
        count_label = "Artikel"
        details_label = "Details"
        tech_label = "Kerntechnologie"
        app_label = "Anwendung"
        explain_label = "Einfache Erklaerung"
        source_label = "Quelle"
    else:
        header = "[Industrial AI Digest]"
        count_label = "Articles"
        details_label = "Details"
        tech_label = "Tech"
        app_label = "Application"
        explain_label = "Explain"
        source_label = "Source"

    lines = [
        f"{header} {today}",
        f"{count_label}: {len(articles)}",
        f"{labels.get('tagline', '')}",
        "",
    ]

    grouped_source: list[dict[str, str]] = []
    for article in articles:
        title = _pick_title_for_persona(article, persona)
        grouped_source.append({"category_tag": article.category_tag, "title": title})
    grouped = _group_articles_by_theme(grouped_source, max_per_group=5)

    lines.append(f"{details_label}:\n")
    for group in grouped:
        lines.append(f"[{group['name']}]")
        for item in group["items"]:
            lines.append(f"- {_clip(item.get('title', 'N/A'), 200)}")
        lines.append("")

    for article in articles:
        title = _pick_title_for_persona(article, persona)
        application = article.german_context or "N/A"
        if persona == "technician":
            application = _localize_context_for_technician(application)
        lines.append(f"[{article.category_tag}] {_clip(title, 200)}")
        lines.append(f"- {tech_label}: {_clip(article.core_tech_points or 'N/A', 500)}")
        lines.append(f"- {app_label}: {_clip(application, 600)}")
        lines.append(f"- {explain_label}: {_clip(_pick_explanation(article, persona), 1000)}")
        lines.append(f"- {source_label}: {article.source_name} | {article.source_url}")
        lines.append("")

    return "\n".join(lines)


def send_email(
    articles: list[AnalyzedArticle],
    today: str | None = None,
    profile: object | None = None,
    recipient_override: str | None = None,
    subject_prefix_override: str | None = None,
) -> bool:
    """Send the daily digest email via SMTP.

    Args:
        articles: LLM-analyzed articles to include in the digest.
        today: Date string in ``YYYY-MM-DD`` format. Defaults to today.
        profile: ``RecipientProfile`` instance containing email address,
            language preference, and persona.
        recipient_override: Optional explicit recipient list (comma-separated).
        subject_prefix_override: Optional extra subject prefix, e.g. "[Review] ".

    Returns:
        ``True`` if the email was delivered successfully, ``False`` otherwise.
    """
    default_recipient = (
        recipient_override
        if recipient_override
        else (profile.email if profile and hasattr(profile, "email") else EMAIL_TO)
    )
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, default_recipient]):
        logger.warning("[EMAIL] SMTP not configured, skipping email delivery")
        return False

    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    html_content = render_digest(articles, today, profile)

    msg = MIMEMultipart("alternative")
    # Resolve language the same way render_digest does — honour profile.language,
    # with student always defaulting to English.
    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    base_lang = getattr(profile, "language", "zh") if profile else "zh"
    lang = "en" if persona == "student" else base_lang
    if persona == "technician":
        subject_prefix = "[Techniker] "
    elif persona == "student":
        subject_prefix = "[Student] "
    else:
        subject_prefix = ""
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])
    if subject_prefix_override:
        subject_prefix = f"{subject_prefix_override}{subject_prefix}"
    msg["Subject"] = f"{subject_prefix}📅 {today} {labels['subject_suffix']} ({len(articles)})"
    msg["From"] = EMAIL_FROM or SMTP_USER

    recipient = default_recipient
    msg["To"] = recipient

    text_content = render_digest_text(articles, today, profile)
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        logger.info(
            f"[EMAIL] Sending digest to {recipient} (Profile: {profile.name if profile else 'Default'})"
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            recipients = [r.strip() for r in recipient.split(",") if r.strip()]
            server.sendmail(msg["From"], recipients, msg.as_string())

        logger.info("[EMAIL] ✅ Digest sent successfully")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error("[EMAIL] SMTP 认证失败，请检查用户名和密码: %s", e)
        return False
    except smtplib.SMTPException as e:
        logger.error("[EMAIL] SMTP 发送失败: %s", e)
        return False
    except OSError as e:
        logger.error("[EMAIL] 网络连接错误: %s", e)
        return False


def save_digest_markdown(
    articles: list[AnalyzedArticle], output_dir: str = "output", today: str | None = None
) -> str:
    """Save the digest as a Markdown file.

    Args:
        articles: LLM-analyzed articles to include.
        output_dir: Directory to write the file into. Created if absent.
        today: Date string in ``YYYY-MM-DD`` format. Defaults to today.

    Returns:
        Absolute path to the saved Markdown file.
    """
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"digest-{today}.md")

    lines = [
        f"# 📅 {today} 工业 AI 每日摘要 (Industrial AI Daily)\n",
        f"> 📊 今日共筛选出 **{len(articles)}** 条相关情报\n",
        "---\n",
    ]

    for article in articles:
        lines.append(f"### [{article.category_tag}] {article.title_zh}\n")
        lines.append(f"*{article.title_en}*\n\n")
        lines.append(f"📎 来源：{article.source_name} | [点击查看原文]({article.source_url})\n")
        lines.append("---\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[FILE] Digest saved to {filepath}")
    return filepath
