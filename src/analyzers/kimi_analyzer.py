"""Kimi Cloud (Moonshot AI) deep analysis module."""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from src.models import Article, AnalyzedArticle
from config import KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL, API_PROVIDER

logger = logging.getLogger(__name__)

# Initialize client (OpenAI-compatible)
_client: OpenAI | None = None

# Local models need more tokens (they're verbose) and higher temp tolerance
IS_LOCAL = API_PROVIDER == "Local_Ollama"
MAX_TOKENS = 1500 if IS_LOCAL else 800
REQUEST_TIMEOUT_SECONDS = float(os.getenv("KIMI_TIMEOUT_SECONDS", "45"))
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "4")))


def _get_client() -> OpenAI:
    """Lazy-init API client."""
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


def _extract_json(text: str) -> dict | None:
    """
    Robustly extract a JSON object from model output.
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


SYSTEM_PROMPT = """\
你是工业技术情报分析师。分析给定文章，输出**纯 JSON**（无其他文字）。

JSON 格式:
{"category_tag":"类别","title_zh":"中文标题","title_en":"English Title","summary_zh":"一句话中文总结","summary_en":"One-sentence English summary","core_tech_points":"核心技术要点","german_context":"德方应用背景","tool_stack":"使用的软件工具","hiring_signals":"招聘/扩建信号","interview_flip":"面试谈资: 痛点与方案","theory_gap":"学术vs工业差异"}

类别选项: Digital Twin / Industry 4.0 / Simulation / AI / Research
重点关注: VDI标准, AAS(Verwaltungsschale), 工业软件工具名称
只输出JSON，不要任何解释文字。
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
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:800]}\n\n"
        f"请只输出JSON。"
    )

    # --- Attempt 1: Full analysis ---
    data = _call_and_parse(client, SYSTEM_PROMPT, user_content)

    # --- Attempt 2: Retry with ultra-simple prompt (local models) ---
    if data is None and IS_LOCAL:
        logger.warning(f"[{API_PROVIDER}] Retry with simplified prompt for '{article.title[:40]}'")
        simple_prompt = (
            'You are a JSON generator. Output ONLY a JSON object with these keys: '
            '"category_tag", "title_zh", "title_en", "summary_zh", "summary_en", '
            '"core_tech_points", "german_context", "tool_stack", "hiring_signals", '
            '"interview_flip", "theory_gap". '
            'No explanation, no markdown, ONLY JSON.'
        )
        data = _call_and_parse(client, simple_prompt, user_content)

    if data is None:
        logger.error(f"[{API_PROVIDER}] All parse attempts failed for '{article.title[:40]}'")
        return AnalyzedArticle(
            category_tag=article.category or "Other",
            title_zh=article.title,
            title_en=article.title,
            core_tech_points="(本地模型分析失败，建议使用云端模型)",
            german_context=article.source,
            source_name=article.source,
            source_url=article.url,
            summary_zh=article.content_snippet[:100],
            summary_en="",
            original=article,
        )

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

    logger.info(f"[{API_PROVIDER}] ✅ Analyzed: [{analyzed.category_tag}] {analyzed.title_zh[:50]}")
    return analyzed


def _call_and_parse(client: OpenAI, system_prompt: str, user_content: str) -> dict | None:
    """Call the model and attempt to parse JSON from the response."""
    try:
        response = client.chat.completions.create(
            model=KIMI_MODEL,
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
    Analyze a batch of articles through Kimi Cloud.
    Returns list of successfully analyzed articles.
    """
    logger.info(f"[{API_PROVIDER}] Starting analysis of {len(articles)} articles (Mock={mock})")
    results: list[AnalyzedArticle] = []
    if not articles:
        return results

    # Keep deterministic order while still using concurrent requests.
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
