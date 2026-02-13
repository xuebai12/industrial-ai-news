"""Email delivery module using SMTP."""
"""
邮件交付模块 (Email Delivery Module)
使用 SMTP 协议发送 HTML 或纯文本格式的日报。
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

from jinja2 import Template

from src.models import AnalyzedArticle
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO, EMAIL_FROM

logger = logging.getLogger(__name__)


# i18n Labels
I18N_LABELS = {
    "zh": {
        "title": "📅 工业 AI 每日摘要 (Industrial AI Daily)",
        "stats": "📊 今日共筛选出 <strong>{{ count }}</strong> 条相关情报",
        "summary_label": "摘要：",
        "tech_points_label": "🔬 核心技术：",
        "context_label": "🏭 背景：",
        "source_label": "来源 / Source:",
        "link_label": "Link / 原文 →",
        "simple_title": "💡 通俗解读 (Student View)",
        "footer": "Industrial AI Intelligence System",
    },
    "de": {
        "title": "📅 Industrial AI Tageszusammenfassung",
        "stats": "📊 Heute wurden <strong>{{ count }}</strong> relevante Berichte ausgewählt",
        "summary_label": "Zusammenfassung:",
        "tech_points_label": "🔬 Kerntechnologie:",
        "context_label": "🏭 Hintergrund:",
        "source_label": "Quelle / Source:",
        "link_label": "Originalartikel →",
        "simple_title": "💡 Einfache Erklärung",
        "footer": "Industrial AI Intelligence System (DE)",
    }
}

# Jinja2 HTML email template
# 定义邮件 HTML 模板
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
  .english-title { font-size: 14px; color: #555; margin-bottom: 8px; font-style: italic; }
  .summary { font-size: 14px; line-height: 1.6; color: #333; margin-bottom: 6px; }
  .english-summary { font-size: 13px; line-height: 1.5; color: #666; margin-bottom: 10px; border-left: 2px solid #ddd; padding-left: 10px; }
  .tech-points { font-size: 13px; color: #666; border-left: 3px solid #2196f3; 
                 padding-left: 12px; margin: 10px 0; }
  .context { font-size: 12px; color: #888; }
  .simple-box { background: #e8f5e9; border: 1px solid #c8e6c9; border-radius: 8px; 
                padding: 12px; margin-top: 12px; font-size: 13px; color: #2e7d32; }
  .simple-title { font-weight: bold; margin-bottom: 5px; display: block; color: #1b5e20; }
  .tool-item { margin-top: 8px; font-size: 12px; color: #666; display: flex; align-items: center; }
  .icon { margin-right: 6px; }
  .source { font-size: 13px; margin-top: 10px; }
  .source a { color: #1976d2; text-decoration: none; }
  .footer { text-align: center; padding: 20px; font-size: 12px; color: #999; }
  .stats { background: #e8f5e9; border-radius: 8px; padding: 12px; 
           margin-bottom: 16px; font-size: 13px; color: #2e7d32; }
</style>
</head>
<body>
  <div class="header">
    <h1>{{ labels.title }}</h1>
    <div class="date">{{ today }} | Industrial AI & Simulation Intelligence</div>
  </div>

  <div class="stats">
    {{ labels.stats | replace('{{ count }}', articles|length|string) }}
  </div>

  {% for article in articles %}
  <div class="article">
    <span class="category">{{ article.category_tag }}</span>
    
    <!-- Title: German for DE profile, Chinese for ZH profile -->
    {% if profile.language == 'de' %}
        <h2>{{ article.title_de or article.title_en }}</h2>
        <div class="english-title">{{ article.title_en }}</div>
    {% else %}
        <h2>{{ article.title_zh }}</h2>
        <div class="english-title">{{ article.title_en }}</div>
    {% endif %}

    <div class="summary"><strong>{{ labels.summary_label }}</strong>
        {% if profile.language == 'de' %}
            {{ article.summary_de or article.summary_en }}
        {% else %}
            {{ article.summary_zh }}
        {% endif %}
    </div>
    
    {% if article.summary_en and profile.language != 'en' %}
    <div class="english-summary">{{ article.summary_en }}</div>
    {% endif %}
    
    <div class="tech-points">{{ labels.tech_points_label }} {{ article.core_tech_points }}</div>
    
    {% if article.german_context %}
    <div class="context">{{ labels.context_label }} {{ article.german_context }}</div>
    {% endif %}
    
    <!-- New Dimensions Block -->
    <div class="simple-box">
        {% if profile.persona == 'technician' %}
            <span class="simple-title">🔧 Technician Analysis (DE)</span>
            {{ article.technician_analysis_de }}
        {% else %}
            <span class="simple-title">{{ labels.simple_title }}</span>
            {{ article.simple_explanation }}
        {% endif %}
        
        {% if article.tool_stack %}
        <div class="tool-item">
            <span class="icon">🛠️</span> <strong>Tool Stack:</strong>&nbsp;{{ article.tool_stack }}
        </div>
        {% endif %}
    </div>

    <div class="source">
      {{ labels.source_label }} {{ article.source_name }} | 
      <a href="{{ article.source_url }}">{{ labels.link_label }}</a>
    </div>
  </div>
  {% endfor %}

  <div class="footer">
    {{ labels.footer }}
  </div>
</body>
</html>
""")


def render_digest(articles: list[AnalyzedArticle], today: str | None = None, profile: object | None = None) -> str:
    """Render the daily digest as HTML (渲染 HTML 摘要)."""
    if today is None:
        today = date.today().strftime("%Y-%m-%d")
    
    # Default to ZH if no profile
    lang = getattr(profile, "language", "zh") if profile else "zh"
    labels = I18N_LABELS.get(lang, I18N_LABELS["zh"])

    return EMAIL_TEMPLATE.render(today=today, articles=articles, profile=profile, labels=labels)


def render_digest_text(articles: list[AnalyzedArticle], today: str | None = None) -> str:
    """Render the daily digest as plain text (渲染纯文本摘要 - 用于 dry-run 或邮件备选部分)."""
    # NOTE: Keep text version generic/simple for now, or update if user requests text-only format too.
    if today is None:
        today = date.today().strftime("%Y-%m-%d")

    lines = [
        f"📅 {today} 工业 AI 每日摘要 (Industrial AI Daily)",
        f"📊 今日共筛选出 {len(articles)} 条相关情报",
        "=" * 60,
        "",
    ]

    for article in articles:
        lines.append(f"[{article.category_tag}] {article.title_zh}")
        lines.append(f"  {article.title_en}")
        lines.append(f"  🇨🇳 摘要：{article.summary_zh}")
        if article.summary_en:
            lines.append(f"  🇬🇧 Summary: {article.summary_en}")
        lines.append(f"  🔬 核心点：{article.core_tech_points}")
        if article.german_context:
            lines.append(f"  🏭 背景：{article.german_context}")
        
        # New Dimensions
        lines.append(f"  💡 通俗解读: {article.simple_explanation}")
        if article.technician_analysis_de:
            lines.append(f"  🔧 Techniker: {article.technician_analysis_de}")
        if article.tool_stack:
            lines.append(f"  🛠️ 涉及工具: {article.tool_stack}")

        lines.append(f"  📎 来源：{article.source_name} | {article.source_url}")
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
    subject_prefix = f"[{profile.name}] " if profile else ""
    msg["Subject"] = f"{subject_prefix}📅 {today} Industrial AI Digest ({len(articles)})"
    msg["From"] = EMAIL_FROM or SMTP_USER
    
    # Use profile email if available, else default EMAIL_TO
    recipient = profile.email if profile and hasattr(profile, 'email') else EMAIL_TO
    msg["To"] = recipient

    # Attach plain text and HTML versions
    text_content = render_digest_text(articles, today) # Text version remains generic for now
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        logger.info(f"[EMAIL] Sending digest to {recipient} (Profile: {profile.name if profile else 'Default'})")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(msg["From"], recipient.split(","), msg.as_string())

        logger.info("[EMAIL] ✅ Digest sent successfully")
        return True

    except Exception as e:
        logger.error(f"[EMAIL] Failed to send: {e}")
        return False


def save_digest_markdown(articles: list[AnalyzedArticle],
                         output_dir: str = "output",
                         today: str | None = None) -> str:
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
