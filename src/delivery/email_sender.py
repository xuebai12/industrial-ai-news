"""Email delivery module using SMTP."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

from jinja2 import Template

from src.models import AnalyzedArticle
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO, EMAIL_FROM

logger = logging.getLogger(__name__)


# Jinja2 HTML email template
EMAIL_TEMPLATE = Template("""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
         max-width: 700px; margin: 0 auto; padding: 20px; color: #333; background: #f5f5f5; }
  .header { background: linear-gradient(135deg, #1a237e, #0d47a1); color: white; 
            padding: 24px; border-radius: 12px; margin-bottom: 20px; }
  .header h1 { margin: 0; font-size: 20px; }
  .header .date { opacity: 0.85; font-size: 14px; margin-top: 6px; }
  .article { background: white; border-radius: 10px; padding: 18px; 
             margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .category { display: inline-block; background: #e3f2fd; color: #1565c0; 
              padding: 3px 10px; border-radius: 12px; font-size: 12px; 
              font-weight: 600; margin-bottom: 8px; }
  .article h2 { margin: 6px 0 10px; font-size: 16px; color: #1a237e; }
  .summary { font-size: 14px; line-height: 1.6; color: #555; margin-bottom: 10px; }
  .tech-points { font-size: 13px; color: #666; border-left: 3px solid #2196f3; 
                 padding-left: 12px; margin: 10px 0; }
  .context { font-size: 12px; color: #888; }
  .source { font-size: 13px; margin-top: 10px; }
  .source a { color: #1976d2; text-decoration: none; }
  .footer { text-align: center; padding: 20px; font-size: 12px; color: #999; }
  .stats { background: #e8f5e9; border-radius: 8px; padding: 12px; 
           margin-bottom: 16px; font-size: 13px; color: #2e7d32; }
</style>
</head>
<body>
  <div class="header">
    <h1>📅 工业 AI 每日摘要</h1>
    <div class="date">{{ today }} | Industrial AI & Simulation Intelligence</div>
  </div>

  <div class="stats">
    📊 今日共筛选出 <strong>{{ articles|length }}</strong> 条相关情报
  </div>

  {% for article in articles %}
  <div class="article">
    <span class="category">{{ article.category_tag }}</span>
    <h2>{{ article.title_zh }}</h2>
    <div class="summary">摘要：{{ article.summary_zh }}</div>
    <div class="tech-points">🔬 {{ article.core_tech_points }}</div>
    {% if article.german_context %}
    <div class="context">🏭 {{ article.german_context }}</div>
    {% endif %}
    <div class="source">
      来源：{{ article.source_name }} | 
      <a href="{{ article.source_url }}">点击查看原文 →</a>
    </div>
  </div>
  {% endfor %}

  <div class="footer">
    Industrial AI Intelligence System · Powered by Ollama + Kimi Cloud
  </div>
</body>
</html>
""")


def render_digest(articles: list[AnalyzedArticle], today: str | None = None) -> str:
    """Render the daily digest as HTML."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")
    return EMAIL_TEMPLATE.render(today=today, articles=articles)


def render_digest_text(articles: list[AnalyzedArticle], today: str | None = None) -> str:
    """Render the daily digest as plain text (for --dry-run)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    lines = [
        f"📅 {today} 工业 AI 每日摘要",
        f"📊 今日共筛选出 {len(articles)} 条相关情报",
        "=" * 60,
        "",
    ]

    for article in articles:
        lines.append(f"[{article.category_tag}] {article.title_zh}")
        lines.append(f"  摘要：{article.summary_zh}")
        lines.append(f"  🔬 {article.core_tech_points}")
        if article.german_context:
            lines.append(f"  🏭 {article.german_context}")
        lines.append(f"  来源：{article.source_name} | {article.source_url}")
        lines.append("")

    return "\n".join(lines)


def send_email(articles: list[AnalyzedArticle], today: str | None = None) -> bool:
    """Send the daily digest email via SMTP."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO]):
        logger.warning("[EMAIL] SMTP not configured, skipping email delivery")
        return False

    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    html_content = render_digest(articles, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📅 {today} 工业 AI 每日摘要 ({len(articles)} 条)"
    msg["From"] = EMAIL_FROM or SMTP_USER
    msg["To"] = EMAIL_TO

    # Attach plain text and HTML versions
    text_content = render_digest_text(articles, today)
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        logger.info(f"[EMAIL] Sending digest to {EMAIL_TO}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(msg["From"], EMAIL_TO.split(","), msg.as_string())

        logger.info("[EMAIL] ✅ Digest sent successfully")
        return True

    except Exception as e:
        logger.error(f"[EMAIL] Failed to send: {e}")
        return False


def save_digest_markdown(articles: list[AnalyzedArticle],
                         output_dir: str = "output",
                         today: str | None = None) -> str:
    """Save digest as a Markdown file (alternative to email)."""
    import os
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"digest-{today}.md")

    lines = [
        f"# 📅 {today} 工业 AI 每日摘要\n",
        f"> 📊 今日共筛选出 **{len(articles)}** 条相关情报\n",
        "---\n",
    ]

    for article in articles:
        lines.append(f"### [{article.category_tag}] {article.title_zh}\n")
        lines.append(f"**摘要：** {article.summary_zh}\n")
        lines.append(f"🔬 **核心技术：** {article.core_tech_points}\n")
        if article.german_context:
            lines.append(f"🏭 **应用背景：** {article.german_context}\n")
        lines.append(f"📎 来源：{article.source_name} | [点击查看原文]({article.source_url})\n")
        lines.append("---\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[FILE] Digest saved to {filepath}")
    return filepath
