"""Email delivery module using SMTP."""
"""
邮件交付模块 (Email Delivery Module)
使用 SMTP 协议发送 HTML 或纯文本格式的日报。
"""

import logging
import smtplib
import json
import os
import re
from datetime import date
from dataclasses import replace
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from jinja2 import Template
from openai import OpenAI

from config import (
    EMAIL_FROM,
    EMAIL_TO,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
)
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)
_translator_client: OpenAI | None = None
TECHNICIAN_LANGUAGE_GUARD_ENABLED = (
    os.getenv("TECHNICIAN_LANGUAGE_GUARD_ENABLED", "true").lower() == "true"
)
TECHNICIAN_GUARD_MAX_REWRITE = max(0, int(os.getenv("TECHNICIAN_GUARD_MAX_REWRITE", "8")))
TECHNICIAN_GUARD_TIMEOUT_SECONDS = float(os.getenv("TECHNICIAN_GUARD_TIMEOUT_SECONDS", "45"))
TECHNICIAN_GUARD_MAX_TOKENS = int(os.getenv("TECHNICIAN_GUARD_MAX_TOKENS", "700"))


I18N_LABELS = {
    "en": {
        "title": "Industrial AI Daily Digest",
        "stats": "Selected <strong>{{ count }}</strong> relevant updates today",
        "simple_explain_label": "Plain Explanation",
        "application_label": "Application Context",
        "source_label": "Source",
        "link_label": "Original Article",
        "overview_title": "Daily Overview",
        "top_title": "Top 3",
        "footer": "Industrial AI Intelligence System (EN)",
    },
    "de": {
        "title": "Tageszusammenfassung Industrielle KI",
        "stats": "Heute wurden <strong>{{ count }}</strong> relevante Berichte ausgewählt",
        "simple_explain_label": "Einfach Erklaert",
        "application_label": "Anwendungskontext",
        "source_label": "Quelle",
        "link_label": "Originalartikel",
        "overview_title": "Tagesueberblick",
        "top_title": "Top 3",
        "pending_title": "Weitere Relevante Artikel (nicht analysiert)",
        "pending_empty": "Keine unanalysierten Artikel in dieser Kategorie.",
        "footer": "System fuer Industrielle KI",
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
         max-width: 760px; margin: 0 auto; padding: 20px; color: #1f2937; background: #f3f5f9; }
  .header { background: linear-gradient(120deg, #0b3c7f, #0f5db8); color: #fff;
            padding: 22px; border-radius: 12px; margin-bottom: 14px; }
  .header h1 { margin: 0; font-size: 22px; letter-spacing: 0.2px; }
  .header .date { opacity: 0.9; font-size: 13px; margin-top: 6px; }
  .overview { background: #fff; border: 1px solid #dbe3ee; border-radius: 12px; padding: 16px; margin-bottom: 14px; }
  .overview h2 { margin: 0 0 10px; font-size: 16px; color: #0b3c7f; }
  .overview p { margin: 0 0 10px; font-size: 14px; line-height: 1.55; }
  .overview ul { margin: 6px 0 0 18px; padding: 0; }
  .overview li { margin: 5px 0; font-size: 13px; line-height: 1.45; }
  .article { background: #fff; border: 1px solid #dbe3ee; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
  .category { display: inline-block; background: #eaf2ff; color: #144a9e;
              padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .article h3 { margin: 8px 0 6px; font-size: 17px; color: #0f172a; }
  .subtle { font-size: 12px; color: #667085; margin-bottom: 10px; }
  .row { margin: 8px 0; }
  .label { display: block; font-size: 12px; color: #475467; font-weight: 700; text-transform: uppercase;
           letter-spacing: 0.2px; margin-bottom: 4px; }
  .value { font-size: 14px; line-height: 1.6; color: #1f2937; }
  .source { margin-top: 10px; font-size: 13px; color: #344054; }
  .source a { color: #175cd3; text-decoration: none; }
  .footer { text-align: center; padding: 16px 8px 8px; font-size: 12px; color: #98a2b3; }
  .extra { background: #fff; border: 1px solid #dbe3ee; border-radius: 12px; padding: 14px; margin: 12px 0; }
  .extra h2 { margin: 0 0 10px; font-size: 15px; color: #0b3c7f; }
  .extra h3 { margin: 12px 0 8px; font-size: 13px; color: #0f3d86; }
  .extra table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .extra th, .extra td { border-bottom: 1px solid #e6ebf2; padding: 6px 4px; text-align: left; vertical-align: top; }
  .extra th { color: #475467; font-weight: 700; }
  .extra a { color: #175cd3; text-decoration: none; }
</style>
</head>
<body>
  <div class="header">
    <h1>{{ labels.title }}</h1>
    <div class="date">{{ today }} | {% if persona == 'technician' %}Industrielle KI & Simulation{% else %}Industrial AI & Simulation{% endif %}</div>
  </div>

  <div class="overview">
    <h2>{{ labels.overview_title }}</h2>
    <p>{{ labels.stats | replace('{{ count }}', articles|length|string) }}</p>
  </div>

  {% for article in articles %}
  <div class="article">
    <span class="category">{{ article.category_tag }}</span>

    <h3>{{ article.display_title }}</h3>
    {% if article.title_en %}
    <div class="subtle">{{ article.title_en }}</div>
    {% endif %}

    <div class="row">
      <span class="label">{{ labels.application_label }}</span>
      <div class="value">{{ article.context_compact }}</div>
    </div>

    <div class="row">
      <span class="label">{{ labels.simple_explain_label }}</span>
      <div class="value">{{ article.simple_explanation }}</div>
    </div>

    <div class="source">
      {{ labels.source_label }}: {{ article.source_name }} |
      <a href="{{ article.source_url }}">{{ labels.link_label }}</a>
    </div>
  </div>
  {% endfor %}

  {% if pending_articles %}
  <div class="extra">
    <h2>{{ labels.pending_title if labels.pending_title else 'Weitere Relevante Artikel (nicht analysiert)' }}</h2>
    {% for group in pending_articles %}
    <h3>{{ group.domain_label }}</h3>
    {% if group.items_list %}
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Kategorie</th>
          <th>Titel</th>
          <th>Link</th>
        </tr>
      </thead>
      <tbody>
        {% for item in group.items_list %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ item.category }}</td>
          <td>{{ item.title }}</td>
          <td><a href="{{ item.url }}">{% if persona == 'technician' %}Oeffnen{% else %}Open{% endif %}</a></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="value">{{ labels.pending_empty if labels.pending_empty else 'Keine unanalysierten Artikel in dieser Kategorie.' }}</div>
    {% endif %}
    {% endfor %}
  </div>
  {% endif %}

  <div class="footer">
    {{ labels.footer }}
  </div>
</body>
</html>
"""
)


def _clip(text: str, limit: int) -> str:
    # Keep full content; clipping disabled by product rule.
    _ = limit
    return (text or "").strip()


def _pick_title(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.title_de or article.title_en
    return article.title_en or article.title_de


def _pick_primary_summary(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.summary_de or article.summary_en
    return article.summary_en or article.summary_de


def _pick_secondary_summary(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.summary_en if article.summary_en != article.summary_de else ""
    return article.summary_de if article.summary_de != article.summary_en else ""


def _get_translator_client() -> OpenAI | None:
    global _translator_client
    if _translator_client is None:
        if not LLM_API_KEY or not LLM_BASE_URL:
            return None
        _translator_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, max_retries=1)
    return _translator_client


def _extract_json_obj(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    md = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if md:
        try:
            parsed = json.loads(md.group(1))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _needs_german_rewrite(article: AnalyzedArticle) -> bool:
    text = " ".join(
        [
            article.title_de or "",
            article.german_context or "",
            article.technician_analysis_de or "",
        ]
    ).strip()
    if not text:
        return False

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+", text)
    if not words:
        return cjk_chars > 0

    english_stopwords = {
        "the", "and", "for", "with", "from", "this", "that", "are", "is", "to", "of", "in",
        "on", "as", "by", "an", "or", "be", "can", "will", "at", "it", "using", "model",
    }
    german_stopwords = {
        "und", "der", "die", "das", "mit", "fuer", "für", "ist", "im", "in", "auf", "eine",
        "einer", "den", "dem", "zu", "als", "wird", "durch", "bei", "aus", "vom", "zur",
        "an", "vom", "nach", "ohne",
    }
    english_hits = sum(1 for w in words if w.lower() in english_stopwords)
    german_hits = sum(1 for w in words if w.lower() in german_stopwords)
    latin_words = sum(1 for w in words if re.fullmatch(r"[A-Za-z]+", w) is not None)
    latin_ratio = latin_words / max(1, len(words))

    if cjk_chars >= 8:
        return True
    if english_hits >= 6 and english_hits >= german_hits * 2:
        return True
    if latin_ratio > 0.75 and german_hits <= 2 and len(words) >= 24:
        return True
    return False


def _rewrite_to_german(article: AnalyzedArticle) -> AnalyzedArticle:
    client = _get_translator_client()
    if client is None:
        return article

    prompt = (
        "Rewrite the provided fields into clear professional German for industrial technicians. "
        "Return JSON only with keys: title_de, german_context, technician_analysis_de. "
        "Do not output English or Chinese sentences except fixed product names/acronyms."
    )
    user = (
        f"title_de: {article.title_de or article.title_en}\n"
        f"german_context: {article.german_context}\n"
        f"technician_analysis_de: {article.technician_analysis_de or article.simple_explanation}\n"
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=TECHNICIAN_GUARD_MAX_TOKENS,
            timeout=TECHNICIAN_GUARD_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("[LANG_GUARD] rewrite request failed for '%s': %s", article.title_en[:60], exc)
        return article

    raw = getattr(response.choices[0].message, "content", "") or ""
    data = _extract_json_obj(raw)
    if not data:
        logger.warning("[LANG_GUARD] rewrite returned non-JSON for '%s'", article.title_en[:60])
        return article

    def _s(key: str, fallback: str) -> str:
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else fallback

    return replace(
        article,
        title_de=_s("title_de", article.title_de or article.title_en),
        german_context=_s("german_context", article.german_context),
        technician_analysis_de=_s("technician_analysis_de", article.technician_analysis_de),
    )


def _enforce_technician_language_guard(articles: list[AnalyzedArticle]) -> list[AnalyzedArticle]:
    if not TECHNICIAN_LANGUAGE_GUARD_ENABLED:
        return articles
    rewritten: list[AnalyzedArticle] = []
    rewrites = 0
    for article in articles:
        if rewrites < TECHNICIAN_GUARD_MAX_REWRITE and _needs_german_rewrite(article):
            logger.warning(
                "[LANG_GUARD] Non-German ratio high, rewriting article: %s",
                (article.title_en or article.title_de)[:80],
            )
            rewritten.append(_rewrite_to_german(article))
            rewrites += 1
        else:
            rewritten.append(article)
    if rewrites:
        logger.info("[LANG_GUARD] Rewritten %s technician article(s) to German", rewrites)
    return rewritten


def _to_german_category(tag: str) -> str:
    value = (tag or "").strip()
    lower = value.lower()
    mapping = [
        (("digital twin",), "Digitaler Zwilling"),
        (("industry 4.0", "industrie 4.0"), "Industrie 4.0"),
        (("simulation",), "Simulation"),
        (("ai", "künstliche intelligenz"), "Kuenstliche Intelligenz"),
        (("research",), "Forschung"),
        (("factory", "manufacturing"), "Fabrik"),
        (("robot", "humanoid"), "Robotik"),
        (("automotive", "vehicle"), "Automobil"),
        (("supply chain", "logistics"), "Lieferkette"),
        (("energy", "grid", "power"), "Energie"),
        (("cyber", "security", "ot security", "ics"), "Cybersicherheit"),
    ]
    for keys, translated in mapping:
        if any(k in lower for k in keys):
            return translated
    return value or "Sonstiges"


def _normalize_pending_articles(pending_articles: list[dict] | None) -> list[dict[str, Any]]:
    """Normalize pending rows to grouped structure expected by templates."""
    if not pending_articles:
        return []

    normalized: list[dict[str, Any]] = []
    first = pending_articles[0]
    grouped_mode = isinstance(first, dict) and "items" in first

    if grouped_mode:
        for group in pending_articles:
            if not isinstance(group, dict):
                continue
            raw_items = group.get("items", [])
            items_list: list[dict[str, str]] = []
            if isinstance(raw_items, list):
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    items_list.append(
                        {
                            "category": str(item.get("category", "") or ""),
                            "title": str(item.get("title", "") or ""),
                            "url": str(item.get("url", "") or ""),
                        }
                    )
            normalized.append(
                {
                    "domain_key": str(group.get("domain_key", "") or ""),
                    "domain_label": str(group.get("domain_label", "General") or "General"),
                    "items_list": items_list,
                }
            )
        return normalized

    # Backward-compatible flat mode: treat as one generic group.
    flat_items: list[dict[str, str]] = []
    for item in pending_articles:
        if not isinstance(item, dict):
            continue
        flat_items.append(
            {
                "category": str(item.get("category", "") or ""),
                "title": str(item.get("title", "") or ""),
                "url": str(item.get("url", "") or ""),
            }
        )
    return [{"domain_key": "general", "domain_label": "General", "items_list": flat_items}]


def _profile_name(profile: object | None) -> str:
    if profile is None:
        return "Default"
    name = getattr(profile, "name", "")
    if isinstance(name, str) and name.strip():
        return name
    persona = getattr(profile, "persona", "")
    if isinstance(persona, str) and persona.strip():
        return persona
    return "Default"


def render_digest(
    articles: list[AnalyzedArticle],
    today: str | None = None,
    profile: object | None = None,
    pending_articles: list[dict] | None = None,
) -> str:
    """Render the daily digest as HTML (渲染 HTML 摘要)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    lang = getattr(profile, "language", "en") if profile else "en"
    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    if persona == "student":
        # Student template is English-only by requirement.
        lang = "en"
    labels = I18N_LABELS.get(lang, I18N_LABELS["en"])

    rendered_articles = []
    for article in articles:
        if persona == "technician":
            context_compact = _clip(article.german_context or "N/A", 200)
            mechanism_text = article.technician_analysis_de or "N/A"
            explain_compact = _clip(mechanism_text, 220)
            title_en_compact = ""
            category_tag = _to_german_category(article.category_tag)
            display_title = _clip(article.title_de or article.title_en, 90)
        else:
            context_compact = (
                _clip(article.summary_en or "N/A", 140)
                if lang == "en"
                else _clip(article.summary_en or "N/A", 140)
            )
            explain_compact = (
                _clip(article.simple_explanation or article.summary_en or "N/A", 200)
                if lang == "en"
                else _clip(article.simple_explanation or "N/A", 200)
            )
            title_en_compact = _clip(article.title_en or "", 110)
            category_tag = article.category_tag
            display_title = _clip(_pick_title(article, lang), 90)

        rendered_articles.append(
            {
                "category_tag": category_tag,
                "display_title": display_title,
                "title_en": title_en_compact,
                "context_compact": context_compact,
                "simple_explanation": explain_compact,
                "source_name": article.source_name,
                "source_url": article.source_url,
            }
        )

    normalized_pending = _normalize_pending_articles(pending_articles)

    return EMAIL_TEMPLATE.render(
        today=today,
        articles=rendered_articles,
        pending_articles=normalized_pending,
        profile=profile,
        labels=labels,
        persona=persona,
    )


def render_digest_text(
    articles: list[AnalyzedArticle],
    today: str | None = None,
    pending_articles: list[dict] | None = None,
    profile: object | None = None,
) -> str:
    """Render the daily digest as plain text (渲染纯文本摘要 - 用于 dry-run 或邮件备选部分)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    if persona == "student":
        lang = "en"
    elif persona == "technician":
        lang = "de"
    else:
        lang = "en"

    if lang == "de":
        lines = [f"[Tagesuebersicht Industrielle KI] {today}", f"Artikel: {len(articles)}"]
    else:
        lines = [f"[Industrial AI Digest] {today}", f"Articles: {len(articles)}"]

    lines.append("\nDetails:\n")

    for article in articles:
        if lang == "de":
            display_title = _clip(article.title_de or article.title_en, 100)
            explain = _clip(article.technician_analysis_de or "N/A", 180)
            app = _clip(article.german_context or "N/A", 140)
            category = _to_german_category(article.category_tag)
        else:
            display_title = _clip(article.title_en or article.title_de, 100)
            explain = _clip(article.simple_explanation or article.summary_en or "N/A", 180)
            app = _clip(article.summary_en or "N/A", 140)
            category = article.category_tag
        lines.append(f"[{category}] {display_title}")
        if lang == "de":
            lines.append(f"- Anwendung: {app}")
            lines.append(f"- Erklaerung: {explain}")
            lines.append(f"- Quelle: {article.source_name} | {article.source_url}")
        else:
            lines.append(f"- Application: {app}")
            lines.append(f"- Explain: {explain}")
            lines.append(f"- Source: {article.source_name} | {article.source_url}")
        lines.append("")

    normalized_pending = _normalize_pending_articles(pending_articles)
    if normalized_pending:
        if lang == "de":
            lines.append("Weitere Relevante Artikel (nicht analysiert):")
        else:
            lines.append("More relevant articles (not analyzed):")
        for group in normalized_pending:
            lines.append(f"- {group.get('domain_label', '')}")
            items = group.get("items_list", [])
            if not items:
                if lang == "de":
                    lines.append("  Keine unanalysierten Artikel in dieser Kategorie.")
                else:
                    lines.append("  No unanalyzed articles in this category.")
                continue
            for idx, item in enumerate(items, start=1):
                lines.append(
                    f"  {idx}. [{item.get('category', 'N/A')}] {_clip(item.get('title', 'N/A'), 100)} "
                    f"| {item.get('url', '')}"
                )
        lines.append("")

    return "\n".join(lines)


def send_email(
    articles: list[AnalyzedArticle],
    today: str | None = None,
    profile: object | None = None,
    pending_articles: list[dict] | None = None,
) -> bool:
    """Send the daily digest email via SMTP (发送邮件)."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO]):
        logger.warning("[EMAIL] SMTP not configured, skipping email delivery")
        return False

    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    send_articles = articles
    if profile and hasattr(profile, "persona"):
        persona = str(getattr(profile, "persona", "")).strip().lower()
        if persona == "technician":
            send_articles = _enforce_technician_language_guard(articles)

    html_content = render_digest(send_articles, today, profile, pending_articles=pending_articles)

    msg = MIMEMultipart("alternative")
    if profile and hasattr(profile, "persona"):
        persona = str(getattr(profile, "persona", "")).strip().lower()
        if persona == "technician":
            subject_prefix = "[Technician] "
        elif persona == "student":
            subject_prefix = "[Student] "
        else:
            subject_prefix = ""
    else:
        subject_prefix = ""
    if profile and hasattr(profile, "persona") and str(getattr(profile, "persona", "")).strip().lower() == "technician":
        msg["Subject"] = f"{subject_prefix}📅 {today} Tageszusammenfassung Industrielle KI ({len(articles)})"
    else:
        msg["Subject"] = f"{subject_prefix}📅 {today} Industrial AI Digest ({len(send_articles)})"
    msg["From"] = EMAIL_FROM or SMTP_USER

    recipient = profile.email if profile and hasattr(profile, "email") else EMAIL_TO
    msg["To"] = recipient

    text_content = render_digest_text(send_articles, today, pending_articles=pending_articles, profile=profile)
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        logger.info(
            "[EMAIL] Sending digest to %s (Profile: %s)",
            recipient,
            _profile_name(profile),
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(msg["From"], recipient.split(","), msg.as_string())

        logger.info("[EMAIL] ✅ Digest sent successfully")
        return True

    except Exception as e:
        logger.error(f"[EMAIL] Failed to send: {e}")
        return False


def save_digest_markdown(
    articles: list[AnalyzedArticle], output_dir: str = "output", today: str | None = None
) -> str:
    """Save digest as a Markdown file (生成 Markdown 文件 - 邮件的替代方案)."""
    import os

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
