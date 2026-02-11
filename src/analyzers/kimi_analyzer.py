"""Kimi Cloud (Moonshot AI) deep analysis module."""

import json
import logging
from openai import OpenAI

from src.models import Article, AnalyzedArticle
from config import MOONSHOT_API_KEY, MOONSHOT_BASE_URL, MOONSHOT_MODEL

logger = logging.getLogger(__name__)

# Initialize Moonshot client (OpenAI-compatible)
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazy-init Moonshot client."""
    global _client
    if _client is None:
        if not MOONSHOT_API_KEY:
            raise ValueError(
                "MOONSHOT_API_KEY is not set. "
                "Get one at https://platform.moonshot.cn"
            )
        _client = OpenAI(
            api_key=MOONSHOT_API_KEY,
            base_url=MOONSHOT_BASE_URL,
        )
    return _client


SYSTEM_PROMPT = """\
你是一个工业技术情报分析师，专注于工业 AI、离散事件仿真 (DES) 和数字孪生 (Digital Twin) 领域。

你的任务是分析给定的文章信息，并输出结构化的 JSON 格式摘要。

输出格式 (严格 JSON):
{
    "category_tag": "类别标签，如 Digital Twin / Research / Industry 4.0 / Simulation / AI",
    "title_zh": "文章标题的中文翻译",
    "core_tech_points": "核心技术要点（一到两句话）",
    "german_context": "德方应用背景或相关企业（如适用，否则填写该技术的应用场景）",
    "summary_zh": "一句话中文总结"
}

要求：
1. 如果原文是德语或英语，请翻译为中文
2. 提取关键技术创新点
3. 特别关注德国工业背景（Fraunhofer、西门子、宝马等）
4. 保持简洁专业
"""


def analyze_article(article: Article) -> AnalyzedArticle | None:
    """
    Send a single article to Kimi for deep analysis.
    Returns an AnalyzedArticle or None if analysis fails.
    """
    client = _get_client()

    user_content = (
        f"标题: {article.title}\n"
        f"来源: {article.source}\n"
        f"语言: {article.language}\n"
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:800]}\n"
    )

    try:
        response = client.chat.completions.create(
            model=MOONSHOT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON from response (handle markdown code blocks)
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        data = json.loads(raw)

        analyzed = AnalyzedArticle(
            category_tag=data.get("category_tag", "Other"),
            title_zh=data.get("title_zh", article.title),
            core_tech_points=data.get("core_tech_points", ""),
            german_context=data.get("german_context", ""),
            source_name=article.source,
            source_url=article.url,
            summary_zh=data.get("summary_zh", ""),
            original=article,
        )

        logger.info(f"[KIMI] Analyzed: [{analyzed.category_tag}] {analyzed.title_zh[:50]}")
        return analyzed

    except json.JSONDecodeError as e:
        logger.error(f"[KIMI] JSON parse error for '{article.title[:40]}': {e}")
        # Fallback: create minimal AnalyzedArticle
        return AnalyzedArticle(
            category_tag=article.category,
            title_zh=article.title,
            core_tech_points="(分析失败)",
            german_context=article.source,
            source_name=article.source,
            source_url=article.url,
            summary_zh=article.content_snippet[:100],
            original=article,
        )
    except Exception as e:
        logger.error(f"[KIMI] API error for '{article.title[:40]}': {e}")
        return None


def analyze_articles(articles: list[Article]) -> list[AnalyzedArticle]:
    """
    Analyze a batch of articles through Kimi Cloud.
    Returns list of successfully analyzed articles.
    """
    logger.info(f"[KIMI] Starting analysis of {len(articles)} articles")
    results: list[AnalyzedArticle] = []

    for i, article in enumerate(articles, 1):
        logger.info(f"[KIMI] Processing {i}/{len(articles)}: {article.title[:50]}")
        analyzed = analyze_article(article)
        if analyzed:
            results.append(analyzed)

    logger.info(f"[KIMI] Successfully analyzed {len(results)}/{len(articles)} articles")
    return results
