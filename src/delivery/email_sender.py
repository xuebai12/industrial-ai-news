"""Email delivery module using SMTP."""
"""
邮件交付模块 (Email Delivery Module)
使用 SMTP 协议发送 HTML 或纯文本格式的日报。
"""

import logging
import smtplib
import re
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

from config import EMAIL_FROM, EMAIL_TO, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)


I18N_LABELS = {
    "en": {
        "title": "Industrial AI Daily Digest",
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
    },
    "zh": {
        "title": "工业 AI 每日摘要",
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
    },
    "de": {
        "title": "Industrial AI Tageszusammenfassung",
        "stats": "Heute wurden <strong>{{ count }}</strong> relevante Berichte ausgewählt",
        "simple_explain_label": "Einfach Erklaert",
        "tech_points_label": "Kerntechnologie",
        "application_label": "Anwendungskontext",
        "source_label": "Quelle",
        "link_label": "Originalartikel",
        "overview_title": "Tagesueberblick",
        "top_title": "Top 3",
        "no_articles": "Heute keine Artikel.",
        "date_suffix": "Industrial AI und Simulation",
        "subject_suffix": "Industrial AI Tageszusammenfassung",
        "footer": "Industrial AI Intelligence System (DE)",
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
</style>
</head>
<body>
  <div class="header">
    <h1>{{ labels.title }}</h1>
    <div class="date">{{ today }} | {{ labels.date_suffix }}</div>
  </div>

  <div class="overview">
    <h2>{{ labels.overview_title }}</h2>
    <p>{{ labels.stats | replace('{{ count }}', articles|length|string) }}</p>
    <div class="label">{{ labels.top_title }}</div>
    <ul>
      {% for item in top_articles %}
      <li>{{ item }}</li>
      {% endfor %}
    </ul>
  </div>

  {% for article in articles %}
  <div class="article">
    <span class="category">{{ article.category_tag }}</span>

    <h3>{{ article.display_title }}</h3>
    {% if article.subtitle %}
    <div class="subtle">{{ article.title_en }}</div>
    {% endif %}

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

    <div class="source">
      {{ labels.source_label }}: {{ article.source_name }} |
      <a href="{{ article.source_url }}">{{ labels.link_label }}</a>
    </div>
  </div>
  {% endfor %}

  <div class="footer">
    {{ labels.footer }}
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
        return article.title_en or article.title_zh or article.title_de
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
        return (article.summary_en or article.simple_explanation or "N/A").strip()
    return (article.simple_explanation or article.summary_en or "N/A").strip()


def _localize_context_for_technician(text: str) -> str:
    """Map common structured English labels to German for technician digest."""
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


def render_digest(
    articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None
) -> str:
    """Render the daily digest as HTML (渲染 HTML 摘要)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    base_lang = getattr(profile, "language", "zh") if profile else "zh"
    lang = "en" if persona == "student" else base_lang
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])
    no_truncate = True

    rendered_articles = []
    for article in articles:
        simple_explanation = _pick_explanation(article, persona)
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
        core_text = (article.core_tech_points or "").strip() or "N/A"
        if persona == "technician" and core_text == "N/A":
            core_text = "Keine technischen Kerndetails verfügbar."

        rendered_articles.append(
            {
                "category_tag": article.category_tag,
                "display_title": _clip(display_title_raw, 200),
                "title_en": subtitle,
                "subtitle": subtitle,
                "core_tech_compact": (
                    core_text
                    if no_truncate
                    else _clip(core_text, 500)
                ),
                "context_compact": (
                    context_text
                    if no_truncate
                    else _clip(context_text, 600)
                ),
                "simple_explanation": (
                    (simple_explanation or "N/A").strip()
                    if no_truncate
                    else _clip(simple_explanation or "N/A", 1000)
                ),
                "source_name": article.source_name,
                "source_url": article.source_url,
            }
        )

    top_articles = [f"{i + 1}. {item['display_title']}" for i, item in enumerate(rendered_articles[:3])]
    if not top_articles:
        top_articles = [labels.get("no_articles", "No articles today.")]

    return EMAIL_TEMPLATE.render(
        today=today,
        articles=rendered_articles,
        top_articles=top_articles,
        profile=profile,
        labels=labels,
    )


def render_digest_text(
    articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None
) -> str:
    """Render the daily digest as plain text (渲染纯文本摘要 - 用于 dry-run 或邮件备选部分)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")
    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""
    base_lang = getattr(profile, "language", "zh") if profile else "zh"
    lang = "en" if persona == "student" else base_lang
    if persona == "technician":
        header = "[Industrial AI Tageszusammenfassung]"
        count_label = "Artikel"
        top_label = "Top 3"
        details_label = "Details"
        tech_label = "Kerntechnologie"
        app_label = "Anwendung"
        explain_label = "Einfache Erklaerung"
        source_label = "Quelle"
    else:
        header = "[Industrial AI Digest]"
        count_label = "Articles"
        top_label = "Top 3"
        details_label = "Details"
        tech_label = "Tech"
        app_label = "Application"
        explain_label = "Explain"
        source_label = "Source"

    lines = [
        f"{header} {today}",
        f"{count_label}: {len(articles)}",
        f"{top_label}:",
    ]

    for idx, article in enumerate(articles[:3], start=1):
        if persona == "student":
            top_title = article.title_en or article.title_zh or "N/A"
        elif persona == "technician":
            top_title = article.title_de or "Deutscher Titel nicht verfügbar"
        elif lang == "de":
            top_title = article.title_de or article.title_zh or article.title_en or "N/A"
        else:
            top_title = article.title_zh or article.title_en or article.title_de or "N/A"
        lines.append(f"{idx}. {_clip(top_title, 200)}")

    lines.append(f"\n{details_label}:\n")

    for article in articles:
        if persona == "student":
            title = article.title_en or article.title_zh or "N/A"
        elif persona == "technician":
            title = article.title_de or "Deutscher Titel nicht verfügbar"
        else:
            title = article.title_zh or article.title_en or "N/A"
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


def send_email(articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None) -> bool:
    """Send the daily digest email via SMTP (发送邮件)."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO]):
        logger.warning("[EMAIL] SMTP not configured, skipping email delivery")
        return False

    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    html_content = render_digest(articles, today, profile)

    msg = MIMEMultipart("alternative")
    lang = getattr(profile, "language", "zh") if profile else "zh"
    if profile and hasattr(profile, "persona"):
        persona = str(getattr(profile, "persona", "")).strip().lower()
        if persona == "technician":
            subject_prefix = "[Techniker] "
            lang = "de"
        elif persona == "student":
            subject_prefix = "[Student] "
            lang = "en"
        else:
            subject_prefix = ""
    else:
        persona = ""
        subject_prefix = ""
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])
    msg["Subject"] = f"{subject_prefix}📅 {today} {labels['subject_suffix']} ({len(articles)})"
    msg["From"] = EMAIL_FROM or SMTP_USER

    recipient = profile.email if profile and hasattr(profile, "email") else EMAIL_TO
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
