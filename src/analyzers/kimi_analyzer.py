"""Kimi Cloud (Moonshot AI) deep analysis module."""

import json
import logging
from openai import OpenAI

from src.models import Article, AnalyzedArticle
from config import KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL, API_PROVIDER

logger = logging.getLogger(__name__)

# Initialize Moonshot client (OpenAI-compatible)
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazy-init Moonshot client."""
    global _client
    if _client is None:
        if not KIMI_API_KEY:
            raise ValueError(
                f"{API_PROVIDER} API Key is not set. "
                "Check .env (MOONSHOT_API_KEY or NVIDIA_API_KEY)."
            )
        _client = OpenAI(
            api_key=KIMI_API_KEY,
            base_url=KIMI_BASE_URL,
        )
    return _client


SYSTEM_PROMPT = """\
你是一个工业技术情报分析师，专注于工业 AI、离散事件仿真 (DES) 和数字孪生 (Digital Twin) 领域。
你的目标读者是：正在寻找德国工业 AI 领域工作的学生/求职者。

你的任务是分析给定的文章信息，并输出结构化的 JSON 格式摘要。

输出格式 (严格 JSON):
{
    "category_tag": "类别标签 (Digital Twin / Industry 4.0 / Simulation / AI / Research)",
    "title_zh": "中文标题",
    "title_en": "English Title",
    "summary_zh": "一句话中文总结",
    "summary_en": "One-sentence English summary",
    "core_tech_points": "核心技术要点",
    "german_context": "德方应用背景 (涉及企业/机构)",
    
    "tool_stack": "工具链追踪: 识别文中提到的具体仿真/AI软件 (如 AnyLogic, Siemens Plant Simulation, NVIDIA Isaac Sim, Python, TensorFlow)。若无明确提及则留空。",
    "hiring_signals": "企业信号: 如果内容涉及公司扩建研发中心、新项目启动或明确提到招聘/人才需求，请标注为'潜在雇主'并简述。否则留空。",
    "interview_flip": "面试谈资: 从技术中总结 1-2 个可以在面试中讨论的'痛点与解决方案' (Pain Point & Solution)。例如: '痛点: 传统仿真建模慢; 方案: 利用 AI 自动生成模型'。",
    "theory_gap": "学术/工业界差异: 对比该案例与教科书上的基础理论 (如 DES, Queueing Theory) 的差异。例如: '理论假设无限缓冲区，但实际案例中必须考虑物理空间限制'。"
}

要求：
1. 提取关键技术创新点，特别是“新(Neu)”或“原型(Prototype)”相关内容。
2. **工具链追踪**：必须高亮具体的工业软件工具名称。
3. **面试谈资**：将技术点转化为面试中可以展示的见解。
4. **学术/工业桥梁**：如果文章偏应用，请指出它如何落地了理论。
5. **德国市场特别关注**：
   - **VDI 标准**：如果提到 VDI 3633 或其他仿真标准，请务必详细解读其更新点。
   - **AAS (Asset Administration Shell)**：这是德国工业 4.0 的核心。如果文中出现 AAS / Verwaltungsschale，请重点分析其在互操作性方面的应用，并将其作为面试谈资的核心。
6. 保持 JSON 格式合法。
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
            core_tech_points="Mock core tech points.",
            german_context="Mock context.",
            source_name=article.source,
            source_url=article.url,
            summary_zh="这是一个测试摘要。",
            summary_en="This is a test summary.",
            
            tool_stack="AnyLogic, Python",
            hiring_signals="Siemens is expanding AI R&D in Munich.",
            interview_flip="Pain: Data silos; Solution: AAS (Asset Administration Shell).",
            theory_gap="Real-world data is noisy vs textbook perfect data.",
            
            original=article,
        )

    client = _get_client()

    user_content = (
        f"标题: {article.title}\n"
        f"来源: {article.source}\n"
        f"语言: {article.language}\n"
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:1000]}\n"
    )

    try:
        response = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()
        logger.info(f"[{API_PROVIDER}] Raw response: {raw[:500]}...")  # Show first 500 chars

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
            
            tool_stack=data.get("tool_stack", ""),
            hiring_signals=data.get("hiring_signals", ""),
            interview_flip=data.get("interview_flip", ""),
            theory_gap=data.get("theory_gap", ""),
            
            original=article,
        )

        logger.info(f"[{API_PROVIDER}] Analyzed: [{analyzed.category_tag}] {analyzed.title_zh[:50]}")
        return analyzed

    except json.JSONDecodeError as e:
        logger.error(f"[{API_PROVIDER}] JSON parse error for '{article.title[:40]}': {e}")
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
        logger.error(f"[{API_PROVIDER}] API error for '{article.title[:40]}': {e}")
        return None


def analyze_articles(articles: list[Article], mock: bool = False) -> list[AnalyzedArticle]:
    """
    Analyze a batch of articles through Kimi Cloud.
    Returns list of successfully analyzed articles.
    """
    logger.info(f"[{API_PROVIDER}] Starting analysis of {len(articles)} articles (Mock={mock})")
    results: list[AnalyzedArticle] = []

    for i, article in enumerate(articles, 1):
        logger.info(f"[{API_PROVIDER}] Processing {i}/{len(articles)}: {article.title[:50]}")
        analyzed = analyze_article(article, mock=mock)
        if analyzed:
            results.append(analyzed)

    logger.info(f"[{API_PROVIDER}] Successfully analyzed {len(results)}/{len(articles)} articles")
    return results
