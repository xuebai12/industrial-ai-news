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
    "title_en": "文章标题的英文原文（或英文翻译）",
    "core_tech_points": "核心技术要点（一到两句话）。如果涉及具体软件（如 AnyLogic, Siemens Tecnomatix, SAP DM），请明确指出。",
    "german_context": "德方应用背景：1. 涉及企业/机构 2. 对德国'中型企业 (Mittelstand)'的潜在价值",
    "summary_zh": "一句话中文总结",
    "summary_en": "One-sentence English summary"
}

要求：
1. 提供中英双语的标题和总结
2. 提取关键技术创新点，特别是“新(Neu)”或“原型(Prototype)”相关内容
3. 高亮具体的工业软件工具名称
4. 明确指出对德国制造业尤其是中小企业的应用价值
5. 保持简洁专业
"""


def analyze_article(article: Article, mock: bool = False) -> AnalyzedArticle | None:
    """
    Send a single article to Kimi for deep analysis.
    Returns an AnalyzedArticle or None if analysis fails.
    """
    if mock:
        return AnalyzedArticle(
            category_tag="Digital Twin",
            title_zh=f"[测试] {article.title} (CN)",
            title_en=f"[TEST] {article.title} (EN)",
            core_tech_points="This is a simulated technical point extracted by the mock analyzer.",
            german_context="Simulated German Industry Context (e.g. Siemens/BMW application).",
            source_name=article.source,
            source_url=article.url,
            summary_zh="这是一个测试摘要，用于验证系统流程是否通畅。",
            summary_en="This is a test summary to verify the pipeline flow.",
            original=article,
        )

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
            max_tokens=600,
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
            title_en=data.get("title_en", article.title),
            core_tech_points=data.get("core_tech_points", ""),
            german_context=data.get("german_context", ""),
            source_name=article.source,
            source_url=article.url,
            summary_zh=data.get("summary_zh", ""),
            summary_en=data.get("summary_en", ""),
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
            title_en=article.title,
            core_tech_points="(分析失败)",
            german_context=article.source,
            source_name=article.source,
            source_url=article.url,
            summary_zh=article.content_snippet[:100],
            summary_en="",
            original=article,
        )
    except Exception as e:
        logger.error(f"[KIMI] API error for '{article.title[:40]}': {e}")
        return None


def analyze_articles(articles: list[Article], mock: bool = False) -> list[AnalyzedArticle]:
    """
    Analyze a batch of articles through Kimi Cloud.
    Returns list of successfully analyzed articles.
    """
    logger.info(f"[KIMI] Starting analysis of {len(articles)} articles (Mock={mock})")
    results: list[AnalyzedArticle] = []

    for i, article in enumerate(articles, 1):
        logger.info(f"[KIMI] Processing {i}/{len(articles)}: {article.title[:50]}")
        analyzed = analyze_article(article, mock=mock)
        if analyzed:
            results.append(analyzed)

    logger.info(f"[KIMI] Successfully analyzed {len(results)}/{len(articles)} articles")
    return results
