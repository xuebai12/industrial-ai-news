"""
LLM Analyzer Module
负责调用 LLM (Local Ollama / NVIDIA NIM) 对文章进行深度分析，提取结构化信息。
"""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from src.models import Article, AnalyzedArticle
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, API_PROVIDER

logger = logging.getLogger(__name__)

# Initialize client (OpenAI-compatible)
_client: OpenAI | None = None

# Local models need more tokens (they're verbose) and higher temp tolerance
# 本地模型通常更啰嗦，需要更多 token 和更高的容错率
IS_LOCAL = API_PROVIDER == "Local_Ollama"
MAX_TOKENS = 1500 if IS_LOCAL else 800
REQUEST_TIMEOUT_SECONDS = float(os.getenv("KIMI_TIMEOUT_SECONDS", "45")) # Kept env var name for compatibility or should query user? Let's use generic default
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "4"))) 

def _get_client() -> OpenAI:
    """Lazy-init API client (延迟初始化 API 客户端)."""
    global _client
    if _client is None:
        if not LLM_API_KEY:
             # This should be caught by validate_config, but safety check
            raise ValueError(f"{API_PROVIDER} API Key is not set.")
        
        _client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )
    return _client


def _extract_json(text: str) -> dict | None:
    """
    Robustly extract a JSON object from model output.
    从模型输出中鲁棒地提取 JSON 对象。
    Handles: pure JSON, markdown code blocks, JSON embedded in free text.
    """
    if not text or not text.strip():
        return None

    raw = text.strip()

    # Strategy 1: Try direct parse (ideal case)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown ```json ... ``` blocks
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if md_match:
        try:
            return json.loads(md_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find the first { ... } block using brace matching
    brace_start = raw.find('{')
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(raw)):
            if raw[i] == '{':
                depth += 1
            elif raw[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = raw[brace_start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # Try fixing common issues: trailing commas, single quotes
                        fixed = candidate.replace("'", '"')
                        fixed = re.sub(r',\s*}', '}', fixed)
                        fixed = re.sub(r',\s*]', ']', fixed)
                        try:
                            return json.loads(fixed)
                        except json.JSONDecodeError:
                            pass
                    break

    return None


# 系统提示词 (System Prompt)
# 指导 LLM 以特定 JSON 格式输出分析结果
SYSTEM_PROMPT = """\
Role: 你是一位深耕德国工业 4.0 领域的资深技术专家，擅长连接自动化工程（OT）与数据科学（IT）。

Task: 请针对以下抓取到的技术动态，进行“一文两看”的多视角深度分析，分别面向“专业学生”和“现场技术员”。

Constraint (核心限制):
1. 场景化链接：必须将内容关联到 Siemens TIA Portal（如 PLC 编程、HMI 组态）和 Jupyter Notebook（如数据清洗、模型训练）。
2. 拒绝陈词滥调：
   - 学生视角：解释数据流向（传感器 -> PLC -> Jupyter -> 仿真模型）。
   - 技术员视角：关注维护（Instandhaltung）、设备可用性（Anlagenverfügbarkeit）和 OEE。
3. 双语对齐：关键术语保留德语和英文原词并附带中文注释。

这是背景设定。现在，作为分析师，请分析给定文章，并输出**纯 JSON**（无其他文字）。

JSON 格式:
{
    "category_tag": "类别",
    "title_zh": "中文标题",
    "title_en": "English Title",
    "title_de": "Deutscher Titel (Professional German)",
    "summary_zh": "一句话中文总结",
    "summary_en": "One-sentence English summary",
    "summary_de": "Deutsche Zusammenfassung (One-sentence German summary)",
    "core_tech_points": "核心技术要点",
    "german_context": "德方应用背景",
    "tool_stack": "使用的软件工具",
    "simple_explanation": "深度通俗解读(学生视角/中文): 关联TIA/Jupyter/痛点",
    "technician_analysis_de": "Technician Analysis (German): Focus on Maintenance, PLC/SPS, OEE, TIA Portal integration. Professional tone (VDI standard)."
}

类别选项: Digital Twin / Industry 4.0 / Simulation / AI / Research
重点关注: VDI标准, AAS(Verwaltungsschale), 工业软件工具名称
只输出JSON，不要任何解释文字。
"""


def analyze_article(article: Article, mock: bool = False) -> AnalyzedArticle | None:
    """
    Send a single article to LLM for deep analysis.
    发送单篇文章给 LLM 进行深度分析。
    Returns an AnalyzedArticle or None if analysis fails.
    """
    if mock:
        # Mock Response (模拟响应，用于测试)
        return AnalyzedArticle(
            category_tag="Digital Twin",
            title_zh=f"[测试] {article.title} (CN)",
            title_en=f"[TEST] {article.title} (EN)",
            title_de=f"[TEST] {article.title} (DE)",
            core_tech_points="Mock core tech points.",
            german_context="Mock context.",
            source_name=article.source,
            source_url=article.url,
            summary_zh="这是一个测试摘要。",
            summary_en="This is a test summary.",
            summary_de="Dies ist eine Test-Zusammenfassung.",
            tool_stack="AnyLogic, Python",
            simple_explanation="这是一个通俗易懂的解释，专门给非技术人员看的。",
            technician_analysis_de="Dies ist eine technische Analyse für Techniker (Mock).",
            target_personas=article.target_personas,
            original=article,
        )

    client = _get_client()

    user_content = (
        f"标题: {article.title}\n"
        f"来源: {article.source}\n"
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:800]}\n\n"
        f"请只输出JSON。"
    )

    # --- Attempt 1: Full analysis (尝试 1: 完整分析) ---
    data = _call_and_parse(client, SYSTEM_PROMPT, user_content)

    # --- Attempt 2: Retry with ultra-simple prompt (local models) (尝试 2: 简化提示词重试 - 针对本地模型) ---
    if data is None and IS_LOCAL:
        logger.warning(f"[{API_PROVIDER}] Retry with simplified prompt for '{article.title[:40]}'")
        simple_prompt = (
            'You are a JSON generator. Output ONLY a JSON object with these keys: '
            '"category_tag", "title_zh", "title_en", "title_de", "summary_zh", "summary_en", "summary_de", '
            '"core_tech_points", "german_context", "tool_stack", "simple_explanation", "technician_analysis_de". '
            'No explanation, no markdown, ONLY JSON.'
        )
        data = _call_and_parse(client, simple_prompt, user_content)

    if data is None:
        logger.error(f"[{API_PROVIDER}] All parse attempts failed for '{article.title[:40]}'")
        # Return fallback object (返回兜底对象，避免流程中断)
        return AnalyzedArticle(
            category_tag=article.category or "Other",
            title_zh=article.title,
            title_en=article.title,
            title_de=article.title,
            core_tech_points="N/A (analysis fallback)",
            german_context=article.source,
            source_name=article.source,
            source_url=article.url,
            summary_zh="本地模型分析失败，建议切换云端模型后重试。",
            summary_en="Local model analysis failed. Please switch to a cloud model and retry.",
            summary_de="Lokale Modellanalyse fehlgeschlagen. Bitte auf ein Cloud-Modell wechseln und erneut versuchen.",
            tool_stack="N/A",
            simple_explanation="模型未返回可解析的结构化结果。",
            technician_analysis_de="Kein auswertbares Modell-Ergebnis verfügbar.",
            original=article,
            target_personas=article.target_personas, # Pass through
        )

    # Construct AnalyzedArticle from JSON data
    analyzed = AnalyzedArticle(
        category_tag=data.get("category_tag", "Other"),
        title_zh=data.get("title_zh", article.title),
        title_en=data.get("title_en", article.title),
        title_de=data.get("title_de", article.title),
        core_tech_points=data.get("core_tech_points", ""),
        german_context=data.get("german_context", ""),
        source_name=article.source,
        source_url=article.url,
        summary_zh=data.get("summary_zh", ""),
        summary_en=data.get("summary_en", ""),
        summary_de=data.get("summary_de", ""),
        tool_stack=data.get("tool_stack", ""),
        simple_explanation=data.get("simple_explanation", ""),
        technician_analysis_de=data.get("technician_analysis_de", ""),
        target_personas=article.target_personas, # Pass through
        original=article,
    )

    logger.info(f"[{API_PROVIDER}] ✅ Analyzed: [{analyzed.category_tag}] {analyzed.title_zh[:50]}")
    return analyzed


def _call_and_parse(client: OpenAI, system_prompt: str, user_content: str) -> dict | None:
    """Call the model and attempt to parse JSON from the response."""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=MAX_TOKENS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        raw = response.choices[0].message.content
        if not raw:
            logger.warning(f"[{API_PROVIDER}] Empty response from model")
            return None

        raw = raw.strip()
        logger.info(f"[{API_PROVIDER}] Raw response ({len(raw)} chars): {raw[:300]}...")

        data = _extract_json(raw)
        if data is None:
            logger.warning(f"[{API_PROVIDER}] Could not extract JSON from response")
            return None

        return data

    except Exception as e:
        logger.error(f"[{API_PROVIDER}] API call error: {e}")
        return None


def analyze_articles(articles: list[Article], mock: bool = False) -> list[AnalyzedArticle]:
    """
    Analyze a batch of articles through LLM.
    批量分析文章。
    Returns list of successfully analyzed articles.
    """
    logger.info(f"[{API_PROVIDER}] Starting analysis of {len(articles)} articles (Mock={mock})")
    results: list[AnalyzedArticle] = []
    if not articles:
        return results

    # Keep deterministic order while still using concurrent requests.
    # 保持结果顺序确定，同时使用并发请求
    indexed: dict[int, AnalyzedArticle] = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        future_map = {
            executor.submit(analyze_article, article, mock): (idx, article)
            for idx, article in enumerate(articles)
        }
        for future in as_completed(future_map):
            idx, article = future_map[future]
            logger.info(
                f"[{API_PROVIDER}] Processing {idx + 1}/{len(articles)}: {article.title[:50]}"
            )
            try:
                analyzed = future.result(timeout=REQUEST_TIMEOUT_SECONDS + 5)
            except Exception as e:
                logger.error(f"[{API_PROVIDER}] Analysis worker failed: {e}")
                analyzed = None
            if analyzed:
                indexed[idx] = analyzed

    for idx in sorted(indexed):
        results.append(indexed[idx])

    logger.info(f"[{API_PROVIDER}] Successfully analyzed {len(results)}/{len(articles)} articles")
    return results
