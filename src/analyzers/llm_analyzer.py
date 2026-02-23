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
if IS_LOCAL:
    _requested_local_max_tokens = int(os.getenv("KIMI_MAX_TOKENS", "1400"))
    _local_max_tokens_cap = int(os.getenv("KIMI_LOCAL_MAX_TOKENS_CAP", "1400"))
    MAX_TOKENS = min(_requested_local_max_tokens, _local_max_tokens_cap)
else:
    MAX_TOKENS = int(os.getenv("KIMI_MAX_TOKENS", "800"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("KIMI_TIMEOUT_SECONDS", "60"))
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "1" if IS_LOCAL else "4")))
CLIENT_MAX_RETRIES = int(os.getenv("KIMI_CLIENT_MAX_RETRIES", "1" if IS_LOCAL else "0"))
MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("KIMI_MIN_REQUEST_INTERVAL_SECONDS", "2.0" if not IS_LOCAL else "0.2"))
RATE_LIMIT_BACKOFF_SECONDS = float(os.getenv("KIMI_RATE_LIMIT_BACKOFF_SECONDS", "10"))
MAX_RATE_LIMIT_RETRIES = int(os.getenv("KIMI_RATE_LIMIT_MAX_RETRIES", "2"))
# For local inference, keep retries conservative to avoid long backlogs.
LOCAL_ENABLE_FINAL_RETRY = os.getenv("LOCAL_ENABLE_FINAL_RETRY", "false").lower() == "true"
LOCAL_SNIPPET_LIMIT = int(os.getenv("KIMI_LOCAL_SNIPPET_LIMIT", "300"))
LOCAL_RETRY_SNIPPET_LIMIT = int(os.getenv("KIMI_LOCAL_RETRY_SNIPPET_LIMIT", "220"))
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

    def _escape_controls_in_strings(s: str) -> str:
        """Escape raw control chars inside quoted strings (invalid JSON from local models)."""
        out: list[str] = []
        in_string = False
        escaped = False
        for ch in s:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                if in_string:
                    escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = not in_string
                continue
            if in_string:
                if ch == "\n":
                    out.append("\\n")
                    continue
                if ch == "\r":
                    out.append("\\r")
                    continue
                if ch == "\t":
                    out.append("\\t")
                    continue
                if ord(ch) < 0x20:
                    continue
            out.append(ch)
        return "".join(out)

    def _try_parse(candidate: str) -> dict | None:
        s = (candidate or "").strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            # Common repairs for local model outputs
            repaired = s.replace("“", '"').replace("”", '"').replace("’", "'")
            repaired = repaired.replace("\ufeff", "")
            repaired = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', "", repaired)
            repaired = _escape_controls_in_strings(repaired)
            repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
            try:
                parsed = json.loads(repaired)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None

    def _close_truncated_json(candidate: str) -> str:
        """Best-effort close for truncated JSON text (local model length cutoffs)."""
        s = (candidate or "").strip()
        if not s:
            return s

        brace_depth = 0
        in_string = False
        escaped = False

        for ch in s:
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth = max(0, brace_depth - 1)

        repaired = s
        if in_string:
            repaired += '"'
        if brace_depth > 0:
            repaired += "}" * brace_depth
        return repaired

    # Strategy 1: Try direct parse (ideal case)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    # Strategy 1b: Recover from truncated tail (e.g. finish_reason=length)
    parsed = _try_parse(_close_truncated_json(raw))
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

        # Strategy 3c: Truncated mid-string/mid-object (unclosed quote + missing braces)
        parsed = _try_parse(_close_truncated_json(tail))
        if parsed is not None:
            return parsed

    return None


def _json_error_message(exc: json.JSONDecodeError) -> str:
    return f"{exc.msg} at line {exc.lineno}, column {exc.colno} (char {exc.pos})"


def _diagnose_json_parse_error(text: str) -> str:
    """Return best-effort JSON parse diagnostics with line/column."""
    raw = (text or "").strip()
    if not raw:
        return "empty response text"

    candidates: list[tuple[str, str]] = [("raw", raw)]

    repaired = raw.replace("“", '"').replace("”", '"').replace("’", "'")
    repaired = repaired.replace("\ufeff", "")
    repaired = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', "", repaired)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    if repaired != raw:
        candidates.append(("repaired", repaired))

    brace_start = raw.find("{")
    if brace_start != -1:
        tail = raw[brace_start:]
        depth = 0
        in_string = False
        escaped = False
        for ch in tail:
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        tail_closed = tail + ("}" * max(0, depth))
        if tail_closed != tail:
            candidates.append(("tail_autoclose", tail_closed))

    errors: list[str] = []
    for label, candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return f"{label}: parseable JSON object (extractor likely failed on formatting path)"
            return f"{label}: parsed JSON but top-level type is {type(parsed).__name__}, expected object"
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: {_json_error_message(exc)}")

    return " | ".join(errors) if errors else "unknown parse failure"


# Prompt design:
# - STUDENT_EN_PROMPT: concise English brief for student-facing outputs
# - TECHNICIAN_DE_PROMPT: concise German brief for technician-facing outputs
# Both keep the key constraints from the original long Chinese prompt.
STUDENT_EN_PROMPT = (
    "Extract key info into a JSON object with strictly these keys: "
    '"category_tag","title_zh","title_en","title_de","summary_zh","summary_en","summary_de",'
    '"german_context","tool_stack","simple_explanation","technician_analysis_de". '
    "Return ONLY valid JSON. No markdown. No reasoning. No tags like <think>. "
    "Use predefined tags (factory, robotics, automotive, supply chain, energy, cybersecurity) for category_tag. "
    "Write 2 clear Chinese sentences for simple_explanation. "
    "german_context and technician_analysis_de MUST be strictly in German. "
    "Fill other fields concisely based on the content. Use empty strings if uncertain."
)
TECHNICIAN_DE_PROMPT = (
    "Erstelle ein reines JSON-Objekt mit exakt diesen Schlüsseln: "
    '"category_tag","title_zh","title_en","title_de","summary_zh","summary_en","summary_de",'
    '"german_context","tool_stack","simple_explanation","technician_analysis_de". '
    "Nur gültiges JSON ausgeben. Kein Markdown. Keine Erklärungen. Keine <think> Tags. "
    "Zielgruppe für technician_analysis_de: Ein durchschnittlicher Facharbeiter in der Maschinenbauindustrie. "
    "german_context: Kurzer industrieller Kontext (Deutsch). "
    "technician_analysis_de: Kurze technische Analyse und nächster Schritt (Deutsch). MUSS sehr einfach und allgemein verständlich sein, ohne Fachjargon. "
    "Einfache, direkte Sprache."
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

    snippet_limit = LOCAL_SNIPPET_LIMIT if IS_LOCAL else 800
    user_content = (
        f"标题: {article.title}\n"
        f"来源: {article.source}\n"
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:snippet_limit]}\n\n"
        f"请只输出JSON。"
    )

    def _needs_technician_enhance(payload: dict | None) -> bool:
        if not payload:
            return True
        german_context = str(payload.get("german_context", "") or "").strip()
        technician_de = str(payload.get("technician_analysis_de", "") or "").strip()
        return len(german_context) < 24 or len(technician_de) < 24

    def _merge_payload(base: dict | None, patch: dict | None) -> dict | None:
        if base is None:
            return patch
        if patch is None:
            return base
        merged = dict(base)
        for key, value in patch.items():
            if isinstance(value, str):
                if value.strip():
                    merged[key] = value
            elif value is not None:
                merged[key] = value
        return merged

    # Attempt strategy:
    # - Local: student prompt first, then technician prompt to strengthen DE fields
    # - Remote/cloud: full prompt first, then simplified fallback
    if IS_LOCAL:
        student_data = _call_and_parse(client, STUDENT_EN_PROMPT, user_content)
        tech_data = None
        if _needs_technician_enhance(student_data):
            tech_data = _call_and_parse(client, TECHNICIAN_DE_PROMPT, user_content)
        data = _merge_payload(student_data, tech_data)
    else:
        data = _call_and_parse(client, STUDENT_EN_PROMPT, user_content)

    # Cloud fallback: simplified schema + shorter input can recover empty/non-JSON responses.
    if data is None and not IS_LOCAL:
        logger.warning(f"[{API_PROVIDER}] Retry with student prompt for '{article.title[:40]}'")
        short_user_content = (
            f"title: {article.title[:180]}\n"
            f"source: {article.source}\n"
            f"url: {article.url}\n"
            f"snippet: {article.content_snippet[:350]}\n"
            f"reply with JSON only."
        )
        data = _call_and_parse(client, STUDENT_EN_PROMPT, short_user_content)

    # --- Attempt 3: Retry with strict minimal schema + shorter input (尝试 3: 最小化输入重试) ---
    if data is None and IS_LOCAL:
        logger.warning(f"[{API_PROVIDER}] Retry with minimal strict schema for '{article.title[:40]}'")
        minimal_user_content = (
            f"title: {article.title[:180]}\n"
            f"source: {article.source}\n"
            f"url: {article.url}\n"
            f"snippet: {article.content_snippet[:LOCAL_RETRY_SNIPPET_LIMIT]}\n"
        )
        minimal_prompt = (
            'Return ONLY valid JSON. No markdown. No explanation. '
            'Required keys: category_tag,title_zh,title_en,title_de,summary_zh,summary_en,summary_de,'
            'german_context,tool_stack,simple_explanation,technician_analysis_de. '
            'Use empty string if unknown. '
            'simple_explanation must be exactly 2 Chinese sentences. '
            'german_context and technician_analysis_de should be concise German operational points.'
        )
        data = _call_and_parse(client, minimal_prompt, minimal_user_content)

    # Optional final retry for local model. Disabled by default to prevent timeout storms.
    if data is None and IS_LOCAL and LOCAL_ENABLE_FINAL_RETRY:
        logger.warning(f"[{API_PROVIDER}] Final retry with technician prompt for '{article.title[:40]}'")
        final_retry_content = (
            f"title: {article.title[:140]}\n"
            f"source: {article.source}\n"
            f"url: {article.url}\n"
            f"snippet: {article.content_snippet[:180]}\n"
            "reply with JSON only."
        )
        data = _call_and_parse(client, TECHNICIAN_DE_PROMPT, final_retry_content)

    if data is None:
        logger.error(f"[{API_PROVIDER}] All parse attempts failed for '{article.title[:40]}'")
        # Skip this article when model output is empty/unparseable.
        # 上游会尝试从尚未分析的候选中补位。
        return None

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
    def _message_debug_snapshot(message: object) -> str:
        """Compact structural snapshot for empty-response diagnosis."""
        try:
            model_dump = getattr(message, "model_dump", None)
            if callable(model_dump):
                dumped = model_dump()
                content = dumped.get("content")
                content_type = type(content).__name__
                content_len = len(content) if isinstance(content, (list, str)) else 0
                keys = sorted(list(dumped.keys()))
                return (
                    f"keys={keys}; content_type={content_type}; content_len={content_len}; "
                    f"tool_calls={bool(dumped.get('tool_calls'))}; refusal={bool(dumped.get('refusal'))}"
                )
        except Exception:
            pass

        content = getattr(message, "content", None)
        return (
            f"fallback content_type={type(content).__name__}; "
            f"tool_calls={bool(getattr(message, 'tool_calls', None))}; "
            f"refusal={bool(getattr(message, 'refusal', None))}"
        )

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
                else:
                    # OpenAI/Ollama compat may return typed content-part objects.
                    text = getattr(item, "text", None) or getattr(item, "content", None)
                    if isinstance(text, str):
                        parts.append(text)
                    elif isinstance(text, list):
                        for sub in text:
                            if isinstance(sub, str):
                                parts.append(sub)
                            elif isinstance(sub, dict):
                                sub_text = sub.get("text") or sub.get("content")
                                if isinstance(sub_text, str):
                                    parts.append(sub_text)
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
                # Explicitly set num_predict for local models to match MAX_TOKENS
                # and ensure context window is sufficient.
                request_kwargs["extra_body"] = {
                    "format": "json",
                    "options": {
                        "num_predict": MAX_TOKENS,
                        "num_ctx": 4096,
                        "temperature": request_kwargs["temperature"]
                    }
                }

            response = client.chat.completions.create(
                **request_kwargs
            )

            raw = _message_to_text(response.choices[0].message)
            if not raw:
                finish_reason = getattr(response.choices[0], "finish_reason", "unknown")
                logger.warning(f"[{API_PROVIDER}] Empty response from model (finish_reason={finish_reason})")
                logger.warning(
                    f"[{API_PROVIDER}] Empty-response message snapshot: "
                    f"{_message_debug_snapshot(response.choices[0].message)}"
                )
                return None

            raw = raw.strip()
            preview = raw[:300]
            suffix = "..." if len(raw) > 300 else ""
            logger.info(f"[{API_PROVIDER}] Raw response ({len(raw)} chars): {preview}{suffix}")

            data = _extract_json(raw)
            if data is None:
                finish_reason = getattr(response.choices[0], "finish_reason", "unknown")
                parse_error = _diagnose_json_parse_error(raw)
                logger.warning(
                    f"[{API_PROVIDER}] Could not extract JSON from response "
                    f"(finish_reason={finish_reason}; parse_error={parse_error})"
                )
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
