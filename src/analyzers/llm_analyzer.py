"""
LLM Analyzer Module
负责调用 LLM (Local Ollama / NVIDIA NIM) 对文章进行深度分析，提取结构化信息。
"""

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from src.models import Article, AnalyzedArticle
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, API_PROVIDER

logger = logging.getLogger(__name__)

# Initialize client (OpenAI-compatible)
_client: OpenAI | None = None

# Local models need stable JSON and lower per-request load to avoid timeout storms.
IS_LOCAL = API_PROVIDER == "Local_Ollama"
MAX_TOKENS = int(os.getenv("KIMI_MAX_TOKENS", "1400" if IS_LOCAL else "800"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("KIMI_TIMEOUT_SECONDS", "60"))
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "1" if IS_LOCAL else "4")))
CLIENT_MAX_RETRIES = int(os.getenv("KIMI_CLIENT_MAX_RETRIES", "1" if IS_LOCAL else "0"))
MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("KIMI_MIN_REQUEST_INTERVAL_SECONDS", "2.0" if not IS_LOCAL else "0.2"))
RATE_LIMIT_BACKOFF_SECONDS = float(os.getenv("KIMI_RATE_LIMIT_BACKOFF_SECONDS", "10"))
MAX_RATE_LIMIT_RETRIES = int(os.getenv("KIMI_RATE_LIMIT_MAX_RETRIES", "2"))
# For local inference, keep retries conservative to avoid long backlogs.
LOCAL_ENABLE_FINAL_RETRY = os.getenv("LOCAL_ENABLE_FINAL_RETRY", "false").lower() == "true"
_rate_lock = threading.Lock()
_last_request_ts = 0.0

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
            max_retries=CLIENT_MAX_RETRIES,
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

    def _try_parse(candidate: str) -> dict | None:
        s = (candidate or "").strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # Common repairs for local model outputs
            repaired = s.replace("“", '"').replace("”", '"').replace("’", "'")
            repaired = repaired.replace("\ufeff", "")
            repaired = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', "", repaired)
            repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                return None

    # Strategy 1: Try direct parse (ideal case)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    # Strategy 2: Extract from markdown ```json ... ``` blocks
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if md_match:
        parsed = _try_parse(md_match.group(1).strip())
        if parsed is not None:
            return parsed

    # Strategy 2b: Unclosed markdown fence (common in truncated local outputs)
    md_unclosed = re.search(r'```(?:json)?\s*\n?(.*)$', raw, re.DOTALL)
    if md_unclosed:
        candidate = md_unclosed.group(1).replace("```", "").strip()
        parsed = _try_parse(candidate)
        if parsed is not None:
            return parsed

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
                    parsed = _try_parse(candidate)
                    if parsed is not None:
                        return parsed
                    break

        # Strategy 3b: If text is truncated and only missing closing braces, try autoclose
        tail = raw[brace_start:]
        depth = 0
        for ch in tail:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        if depth > 0:
            repaired = tail + ("}" * depth)
            parsed = _try_parse(repaired)
            if parsed is not None:
                return parsed

    return None


# 系统提示词 (System Prompt)
# 指导 LLM 以特定 JSON 格式输出分析结果
SYSTEM_PROMPT = """\
Role: 你是一位工业 AI 研究与落地分析师，面向制造业决策与实施团队输出可执行解读。

Task: 请针对抓取到的技术动态，进行“一文两看”分析，分别面向“学生（英文模板）”和“行业技术员（德文模板）”。

Constraint (核心限制):
1. 删除固定工具绑定：不要强制关联 Siemens TIA Portal 或 Jupyter Notebook。
2. 领域对齐：优先贴合 6 大领域（工厂、机器人、汽车、供应链、能源、网络安全），并可映射工厂 4 子类（设计研发、工艺优化、质量缺陷、运维预测）。
3. 语言一致性：
   - student 输出依赖英文字段；
   - technician 输出依赖德文字段；
   - 中文来源也必须给出可用的英文/德文翻译字段。
4. 模板字段约束（必须严格遵守）：
   - german_context（对应 Kernfokus）：
     - 德语 2-4 条短句；
     - 每条必须同时包含“工业场景（在哪个流程/车间/系统）+ AI 应用方式（AI如何被用）”；
     - 禁止空泛表述，禁止只写政策或口号。
   - technician_analysis_de（对应 Kernmechanismus）：
     - 德语 2-4 条短句；
     - 每条包含“通俗比喻 + 运作步骤 + 1个落地动作”；
     - 写给没有编程经验的一线人员，语言直白可执行。
   - simple_explanation：
     - 仅给 student 使用；
     - 固定 2 句中文结论，直接说明 AI 做了什么和带来什么变化。
5. 按“每个点做 AI 解读”输出：每条内容都要回答这 3 个问题：
   - AI 在这里做了什么（感知/预测/优化/决策）？
   - 对业务流程带来什么变化（效率/质量/风险/成本）？
   - 落地需要哪些条件（数据、系统、组织、合规）？

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
    "simple_explanation": "中文简短解读：AI做了什么、带来什么变化、落地要点",
    "technician_analysis_de": "Deutsch, 2-4 kurze Punkte: Urteil + Business-Impact + naechster Umsetzungsschritt."
}

类别选项: Digital Twin / Industry 4.0 / Simulation / AI / Research
只输出JSON，不要任何解释文字。
"""

SIMPLE_JSON_PROMPT = (
    'You are a JSON generator. Output ONLY a JSON object with these keys: '
    '"category_tag", "title_zh", "title_en", "title_de", "summary_zh", "summary_en", "summary_de", '
    '"core_tech_points", "german_context", "tool_stack", "simple_explanation", "technician_analysis_de". '
    "No explanation, no markdown, ONLY JSON. "
    "Do not force Siemens TIA Portal or Jupyter references. "
    "Align to 6 domains: factory, robotics, automotive, supply chain, energy, cybersecurity. "
    "german_context is Kernfokus: provide 2-4 German short points, each must include industrial scene + how AI is applied. "
    "technician_analysis_de is Kernmechanismus: 2-4 German short points with metaphor + mechanism steps + concrete next action. "
    "simple_explanation is student-only and must be exactly 2 Chinese sentences. "
    "For each key point, reflect AI function, business impact, and implementation requirement."
)


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

    snippet_limit = 450 if IS_LOCAL else 800
    user_content = (
        f"标题: {article.title}\n"
        f"来源: {article.source}\n"
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:snippet_limit]}\n\n"
        f"请只输出JSON。"
    )

    # Attempt strategy:
    # - Local: start with simplified JSON prompt for stability
    # - Remote/cloud: full prompt first, then simplified fallback
    if IS_LOCAL:
        data = _call_and_parse(client, SIMPLE_JSON_PROMPT, user_content)
    else:
        data = _call_and_parse(client, SYSTEM_PROMPT, user_content)

    # Cloud fallback: simplified schema + shorter input can recover empty/non-JSON responses.
    if data is None and not IS_LOCAL:
        logger.warning(f"[{API_PROVIDER}] Retry with simplified JSON prompt for '{article.title[:40]}'")
        short_user_content = (
            f"title: {article.title[:180]}\n"
            f"source: {article.source}\n"
            f"url: {article.url}\n"
            f"snippet: {article.content_snippet[:350]}\n"
            f"reply with JSON only."
        )
        data = _call_and_parse(client, SIMPLE_JSON_PROMPT, short_user_content)

    # --- Attempt 3: Retry with strict minimal schema + shorter input (尝试 3: 最小化输入重试) ---
    if data is None and IS_LOCAL:
        logger.warning(f"[{API_PROVIDER}] Retry with minimal strict schema for '{article.title[:40]}'")
        minimal_user_content = (
            f"title: {article.title[:180]}\n"
            f"source: {article.source}\n"
            f"url: {article.url}\n"
            f"snippet: {article.content_snippet[:350]}\n"
        )
        minimal_prompt = (
            'Return ONLY valid JSON. No markdown. No explanation. '
            'Required keys: category_tag,title_zh,title_en,title_de,summary_zh,summary_en,summary_de,'
            'core_tech_points,german_context,tool_stack,simple_explanation,technician_analysis_de. '
            'Use empty string if unknown.'
        )
        data = _call_and_parse(client, minimal_prompt, minimal_user_content)

    # Optional final retry for local model. Disabled by default to prevent timeout storms.
    if data is None and IS_LOCAL and LOCAL_ENABLE_FINAL_RETRY:
        logger.warning(f"[{API_PROVIDER}] Final retry with full prompt for '{article.title[:40]}'")
        data = _call_and_parse(client, SYSTEM_PROMPT, user_content)

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

    # Helper to force string type
    def _ensure_str(value: any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            # Join list items with space or comma
            return " ".join(str(v) for v in value)
        if isinstance(value, dict):
            # Fallback for dict (should stay rare): dump as string
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    # Construct AnalyzedArticle from JSON data
    # creating AnalyzedArticle with sanitized inputs
    analyzed = AnalyzedArticle(
        category_tag=_ensure_str(data.get("category_tag", "Other")),
        title_zh=_ensure_str(data.get("title_zh", article.title)),
        title_en=_ensure_str(data.get("title_en", article.title)),
        title_de=_ensure_str(data.get("title_de", article.title)),
        core_tech_points=_ensure_str(data.get("core_tech_points", "")),
        german_context=_ensure_str(data.get("german_context", "")),
        source_name=_ensure_str(article.source),
        source_url=_ensure_str(article.url),
        summary_zh=_ensure_str(data.get("summary_zh", "")),
        summary_en=_ensure_str(data.get("summary_en", "")),
        summary_de=_ensure_str(data.get("summary_de", "")),
        tool_stack=_ensure_str(data.get("tool_stack", "")),
        simple_explanation=_ensure_str(data.get("simple_explanation", "")),
        technician_analysis_de=_ensure_str(data.get("technician_analysis_de", "")),
        target_personas=article.target_personas, # List type is expected here
        original=article,
    )

    logger.info(f"[{API_PROVIDER}] ✅ Analyzed: [{analyzed.category_tag}] {analyzed.title_zh[:50]}")
    return analyzed


def _call_and_parse(client: OpenAI, system_prompt: str, user_content: str) -> dict | None:
    """Call the model and attempt to parse JSON from the response."""
    def _message_to_text(message: object) -> str:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join([p for p in parts if p]).strip()

        # Some providers put text in non-standard fields.
        for attr in ("reasoning_content", "refusal"):
            value = getattr(message, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            global _last_request_ts
            # Global throttle to reduce provider-side 429 for cloud endpoints.
            with _rate_lock:
                now = time.monotonic()
                wait_s = MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_ts)
                if wait_s > 0:
                    time.sleep(wait_s)
                _last_request_ts = time.monotonic()

            request_kwargs = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.0 if IS_LOCAL else 0.2,
                "max_tokens": MAX_TOKENS,
                "timeout": REQUEST_TIMEOUT_SECONDS,
            }
            if IS_LOCAL:
                request_kwargs["extra_body"] = {"format": "json"}

            response = client.chat.completions.create(
                **request_kwargs
            )

            raw = _message_to_text(response.choices[0].message)
            if not raw:
                finish_reason = getattr(response.choices[0], "finish_reason", "unknown")
                logger.warning(f"[{API_PROVIDER}] Empty response from model (finish_reason={finish_reason})")
                return None

            raw = raw.strip()
            logger.info(f"[{API_PROVIDER}] Raw response ({len(raw)} chars): {raw[:300]}...")

            data = _extract_json(raw)
            if data is None:
                logger.warning(f"[{API_PROVIDER}] Could not extract JSON from response")
                return None

            return data

        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "too many requests" in msg:
                if attempt < MAX_RATE_LIMIT_RETRIES:
                    backoff = RATE_LIMIT_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[{API_PROVIDER}] 429 rate limit, backoff {backoff:.1f}s then retry ({attempt + 1}/{MAX_RATE_LIMIT_RETRIES})"
                    )
                    time.sleep(backoff)
                    continue
            logger.error(f"[{API_PROVIDER}] API call error: {e}")
            # Local Ollama can return 429 when previous timed-out requests are still running.
            # Brief backoff reduces retry pressure and queue buildup.
            if IS_LOCAL and ("429" in msg or "too many concurrent requests" in msg):
                time.sleep(2.0)
            return None
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
