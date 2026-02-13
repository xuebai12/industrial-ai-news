"""Email delivery module using SMTP."""
"""
邮件交付模块 (Email Delivery Module)
使用 SMTP 协议发送 HTML 或纯文本格式的日报。
"""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

from config import EMAIL_FROM, EMAIL_TO, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)


I18N_LABELS = {
    "zh": {
        "title": "工业 AI 每日摘要",
        "stats": "今日共筛选出 <strong>{{ count }}</strong> 条相关情报",
        "summary_label": "一句话结论",
        "tech_points_label": "核心技术",
        "context_label": "为什么重要",
        "source_label": "来源",
        "link_label": "查看原文",
        "simple_title": "你可以怎么用",
        "overview_title": "今日总览",
        "top_title": "最值得看",
        "action_title": "行动建议",
        "action_text": "优先阅读前 3 条，并记录可落地的工具链。",
        "footer": "Industrial AI Intelligence System",
    },
    "de": {
        "title": "Industrial AI Tageszusammenfassung",
        "stats": "Heute wurden <strong>{{ count }}</strong> relevante Berichte ausgewählt",
        "summary_label": "Kernaussage",
        "tech_points_label": "Kerntechnologie",
        "context_label": "Warum relevant",
        "source_label": "Quelle",
        "link_label": "Originalartikel",
        "simple_title": "Naechster Schritt",
        "overview_title": "Tagesueberblick",
        "top_title": "Top 3",
        "action_title": "Empfehlung",
        "action_text": "Zuerst die Top-3 lesen und ein umsetzbares Tool notieren.",
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
  .secondary { font-size: 12px; color: #667085; line-height: 1.45; margin-top: 6px; }
  .action { background: #f8fbff; border-left: 3px solid #2d7ff9; border-radius: 8px; padding: 10px 12px; margin-top: 10px; }
  .source { margin-top: 10px; font-size: 13px; color: #344054; }
  .source a { color: #175cd3; text-decoration: none; }
  .footer { text-align: center; padding: 16px 8px 8px; font-size: 12px; color: #98a2b3; }
</style>
</head>
<body>
  <div class="header">
    <h1>{{ labels.title }}</h1>
    <div class="date">{{ today }} | Industrial AI & Simulation</div>
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
    <div class="label" style="margin-top:10px;">{{ labels.action_title }}</div>
    <p>{{ labels.action_text }}</p>
  </div>

  {% for article in articles %}
  <div class="article">
    <span class="category">{{ article.category_tag }}</span>

    <h3>{{ article.display_title }}</h3>
    <div class="subtle">{{ article.title_en }}</div>

    <div class="row">
      <span class="label">{{ labels.summary_label }}</span>
      <div class="value">{{ article.primary_summary }}</div>
    </div>

    {% if article.secondary_summary %}
    <div class="secondary">{{ article.secondary_summary }}</div>
    {% endif %}

    <div class="row">
      <span class="label">{{ labels.tech_points_label }}</span>
      <div class="value">{{ article.core_tech_compact }}</div>
    </div>

    <div class="row">
      <span class="label">{{ labels.context_label }}</span>
      <div class="value">{{ article.context_compact }}</div>
    </div>

    <div class="action">
      <span class="label">{{ labels.simple_title }}</span>
      <div class="value">{{ article.action_text }}</div>
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
    if lang == "de":
        return article.title_de or article.title_en or article.title_zh
    return article.title_zh or article.title_en or article.title_de


def _pick_primary_summary(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.summary_de or article.summary_en or article.summary_zh
    return article.summary_zh or article.summary_en or article.summary_de


def _pick_secondary_summary(article: AnalyzedArticle, lang: str) -> str:
    if lang == "de":
        return article.summary_en if article.summary_en != article.summary_de else ""
    return article.summary_en if article.summary_en != article.summary_zh else ""


def render_digest(
    articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None
) -> str:
    """Render the daily digest as HTML (渲染 HTML 摘要)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    lang = getattr(profile, "language", "zh") if profile else "zh"
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])
    persona = str(getattr(profile, "persona", "")).strip().lower() if profile else ""

    rendered_articles = []
    for article in articles:
        action_text = article.technician_analysis_de if persona == "technician" else article.simple_explanation
        rendered_articles.append(
            {
                "category_tag": article.category_tag,
                "display_title": _clip(_pick_title(article, lang), 90),
                "title_en": _clip(article.title_en or "", 110),
                "primary_summary": _clip(_pick_primary_summary(article, lang), 190),
                "secondary_summary": _clip(_pick_secondary_summary(article, lang), 130),
                "core_tech_compact": _clip(article.core_tech_points or "N/A", 130),
                "context_compact": _clip(article.german_context or "N/A", 140),
                "action_text": _clip(action_text or "N/A", 150),
                "source_name": article.source_name,
                "source_url": article.source_url,
            }
        )

    top_articles = [f"{i + 1}. {item['display_title']}" for i, item in enumerate(rendered_articles[:3])]
    if not top_articles:
        top_articles = ["No articles today."]

    return EMAIL_TEMPLATE.render(
        today=today,
        articles=rendered_articles,
        top_articles=top_articles,
        profile=profile,
        labels=labels,
    )


def render_digest_text(articles: list[AnalyzedArticle], today: str | None = None) -> str:
    """Render the daily digest as plain text (渲染纯文本摘要 - 用于 dry-run 或邮件备选部分)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    lines = [
        f"[Industrial AI Digest] {today}",
        f"Articles: {len(articles)}",
        "Top 3:",
    ]

    for idx, article in enumerate(articles[:3], start=1):
        lines.append(f"{idx}. {_clip(article.title_zh or article.title_en, 100)}")

    lines.append("\nDetails:\n")

    for article in articles:
        lines.append(f"[{article.category_tag}] {_clip(article.title_zh or article.title_en, 100)}")
        lines.append(f"- Summary: {_clip(article.summary_zh or article.summary_en or article.summary_de, 180)}")
        lines.append(f"- Tech: {_clip(article.core_tech_points or 'N/A', 120)}")
        lines.append(f"- Source: {article.source_name} | {article.source_url}")
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
    msg["Subject"] = f"{subject_prefix}📅 {today} Industrial AI Digest ({len(articles)})"
    msg["From"] = EMAIL_FROM or SMTP_USER

    recipient = profile.email if profile and hasattr(profile, "email") else EMAIL_TO
    msg["To"] = recipient

    text_content = render_digest_text(articles, today)
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
        lines.append(f"**🇨🇳 摘要：** {article.summary_zh}\n\n")
        if article.summary_en:
            lines.append(f"**🇬🇧 Summary:** {article.summary_en}\n\n")
        lines.append(f"🔬 **核心技术：** {article.core_tech_points}\n")
        if article.german_context:
            lines.append(f"🏭 **应用背景：** {article.german_context}\n")

        lines.append(f"> 💡 **通俗解读:** {article.simple_explanation}\n")
        if article.tool_stack:
            lines.append(f"> - 🛠️ **涉及工具:** {article.tool_stack}\n")

        lines.append(f"\n📎 来源：{article.source_name} | [点击查看原文]({article.source_url})\n")
        lines.append("---\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[FILE] Digest saved to {filepath}")
    return filepath
