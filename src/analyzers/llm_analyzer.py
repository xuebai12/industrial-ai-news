"""
LLM Analyzer Module
负责调用 LLM (Local Ollama / NVIDIA NIM) 对文章进行深度分析，提取结构化信息。
"""

import json
import logging
import os
import re
import ast
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from openai import OpenAI

from src.models import Article, AnalyzedArticle
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, API_PROVIDER

logger = logging.getLogger(__name__)

# Initialize client (OpenAI-compatible)
_client: OpenAI | None = None

# Local models need more tokens, but should run with low randomness for stable JSON.
IS_LOCAL = API_PROVIDER == "Local_Ollama"
MAX_TOKENS = int(os.getenv("KIMI_MAX_TOKENS", "4000" if IS_LOCAL else "2000"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("KIMI_TIMEOUT_SECONDS", "120" if IS_LOCAL else "45"))
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "1" if IS_LOCAL else "4")))
MAX_ANALYSIS_RETRIES = max(1, int(os.getenv("KIMI_ANALYSIS_RETRIES", "2")))
OPENAI_MAX_RETRIES = max(0, int(os.getenv("KIMI_OPENAI_MAX_RETRIES", "0" if IS_LOCAL else "2")))
FALLBACK_TOOLSTACK_MARKER = "__analysis_fallback__"
REQUIRED_KEYS = (
    "category_tag",
    "title_zh",
    "title_en",
    "title_de",
    "summary_zh",
    "summary_en",
    "summary_de",
    "core_tech_points",
    "german_context",
    "tool_stack",
    "simple_explanation",
    "technician_analysis_de",
)

GERMAN_COMPOUND_SPLIT_PAIRS: tuple[tuple[str, str], ...] = (
    ("zuverlaessigkeits", "modellierung"),
    ("wahrscheinlichkeits", "theoretische"),
    ("wahrscheinlichkeits", "rechnung"),
    ("rechen", "zuverlaessigkeit"),
    ("echtzeit", "daten"),
    ("daten", "verarbeitung"),
    ("netzwerk", "ueberwachung"),
    ("ueberwachungs", "system"),
    ("fehler", "zustands"),
    ("zustands", "uebergang"),
    ("anlagen", "verfuegbarkeit"),
    ("vorausschauende", "wartung"),
    ("zustands", "bewertung"),
    ("prozess", "optimierung"),
)


STRUCTURED_KEY_LABELS = {
    "relevance": "Relevance",
    "industry_sectors": "Industry Sectors",
    "regulatory_aspects": "Regulatory Aspects",
    "research_institutions": "Research Institutions",
}


def _humanize_key(key: str) -> str:
    raw = (key or "").strip()
    if not raw:
        return "Field"
    if raw in STRUCTURED_KEY_LABELS:
        return STRUCTURED_KEY_LABELS[raw]
    words = raw.replace("-", "_").split("_")
    return " ".join(w.capitalize() for w in words if w) or raw


def _format_structured_value(value: object) -> str:
    """Format dict/list payloads into readable plain text instead of raw JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts: list[str] = []
        for key, sub_value in value.items():
            rendered = _format_structured_value(sub_value)
            if rendered:
                parts.append(f"{_humanize_key(str(key))}: {rendered}")
        return " | ".join(parts)
    if isinstance(value, (list, tuple, set)):
        items = [_format_structured_value(item) for item in value]
        items = [item for item in items if item]
        return "; ".join(items)
    return str(value).strip()


def _split_compound_token(token: str) -> str:
    """Split long German compounds with conservative heuristics."""
    def _hyphenate(raw: str, idx: int) -> str:
        left = raw[:idx]
        right = raw[idx:]
        if raw[:1].isupper() and right[:1].islower():
            right = right[:1].upper() + right[1:]
        return f"{left}-{right}"

    stripped = token.strip()
    if len(stripped) < 18 or "-" in stripped or not re.fullmatch(r"[A-Za-zÄÖÜäöüß]+", stripped):
        return token
    lower = stripped.lower()
    for left, right in GERMAN_COMPOUND_SPLIT_PAIRS:
        if lower.endswith(left + right):
            cut = len(stripped) - len(right)
            return _hyphenate(stripped, cut)
        if left in lower and lower.endswith(right):
            start = lower.rfind(left)
            cut = start + len(left)
            if 4 <= cut <= len(stripped) - 4:
                return _hyphenate(stripped, cut)

    glue_parts = ("daten", "modell", "system", "technik", "analyse", "prozess", "management")
    for part in glue_parts:
        idx = lower.rfind(part)
        if idx > 4 and idx < len(stripped) - 4:
            return _hyphenate(stripped, idx)
    return token


def _split_german_compounds(text: str) -> str:
    """Split long German compounds token by token."""
    tokens = re.split(r"(\s+)", text or "")
    return "".join(_split_compound_token(token) if not token.isspace() else token for token in tokens)


def _split_long_sentence(sentence: str, max_words: int = 20) -> list[str]:
    """Break long German sentences into short, readable statements."""
    words = sentence.split()
    if len(words) <= max_words:
        return [sentence.strip()]

    split_points = [
        m.start() for m in re.finditer(r",\s+|;\s+|\s+(?:und|aber|weil|dass|sowie|wobei|wenn|oder)\s+", sentence, flags=re.IGNORECASE)
    ]
    if not split_points:
        midpoint = len(words) // 2
        return [
            " ".join(words[:midpoint]).strip(" ,;:."),
            " ".join(words[midpoint:]).strip(" ,;:."),
        ]

    parts: list[str] = []
    start = 0
    for point in split_points:
        candidate = sentence[start:point].strip(" ,;:.")
        if candidate:
            parts.append(candidate)
        start = point
    tail = sentence[start:].strip(" ,;:.")
    if tail:
        parts.append(tail)

    expanded: list[str] = []
    for part in parts:
        if len(part.split()) > max_words:
            expanded.extend(_split_long_sentence(part, max_words=max_words))
        else:
            expanded.append(part)
    return [item for item in expanded if item]


def _enforce_short_sentences_de(text: str) -> list[str]:
    """Normalize punctuation and enforce short sentence lines."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    raw_sentences = [
        part.strip(" -•\t")
        for part in re.split(r"(?<=[.!?])\s+|;\s+|\n+", cleaned)
        if part.strip(" -•\t")
    ]
    lines: list[str] = []
    for sentence in raw_sentences:
        short_parts = _split_long_sentence(sentence)
        for part in short_parts:
            final = part.strip(" ,;:.")
            if not final:
                continue
            if not re.search(r"[.!?]$", final):
                final += "."
            lines.append(final)
    return lines


def _normalize_technician_text_de(text: str) -> str:
    """
    Build dyslexia-friendly German technician output:
    short lines, split compounds, and readable bullet layout.
    """
    fallback = "Kurzanalyse nicht verfuegbar. Bitte Lauf erneut starten."
    base = (text or "").strip()
    if not base:
        return fallback
    de_noisy = base.replace("->", " -> ").replace("|", ". ")
    de_noisy = _split_german_compounds(de_noisy)
    lines = _enforce_short_sentences_de(de_noisy)
    if not lines:
        return fallback
    capped = [f"- {line}" for line in lines[:8]]
    return "\n".join(capped)


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
            max_retries=OPENAI_MAX_RETRIES,
        )
    return _client


def _is_local_endpoint_reachable() -> bool:
    """
    Fast connectivity probe for local API endpoints.
    本地端点连通性快速探测，避免整批文章反复重试。
    """
    parsed = urlparse(LLM_BASE_URL or "")
    host = parsed.hostname
    port = parsed.port
    if not host:
        return True
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    try:
        with socket.create_connection((host, int(port)), timeout=1.5):
            return True
    except OSError:
        return False


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
                # Python-literal fallback for quasi-JSON (single quotes, True/False/None)
                try:
                    py_obj = ast.literal_eval(repaired)
                    if isinstance(py_obj, dict):
                        return py_obj
                except Exception:
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

    # Strategy 4: salvage key-value pairs from malformed JSON-ish output
    salvaged = _salvage_json_like(raw)
    if salvaged:
        return salvaged

    return None


def _salvage_json_like(text: str) -> dict | None:
    """
    Best-effort extraction from malformed JSON-like text.
    从不完全合法的 JSON 文本中按 key 提取字段。
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # Remove common markdown fences to improve regex extraction.
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    data: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        # Match "key": "value" with escaped quotes/newlines tolerance
        m = re.search(
            rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"',
            raw,
            re.DOTALL,
        )
        if m:
            val = m.group(1)
            # Decode escaped sequences only when present; avoid corrupting normal UTF-8 text.
            if "\\" in val:
                try:
                    val = json.loads(f"\"{val}\"")
                except Exception:
                    pass
            data[key] = val.strip()
            continue

        # Match unquoted scalar until comma/newline/brace
        m2 = re.search(
            rf'"{re.escape(key)}"\s*:\s*([^,\n}}]+)',
            raw,
            re.DOTALL,
        )
        if m2:
            data[key] = m2.group(1).strip().strip('"').strip("'")

    # Need a minimum useful subset to treat as recoverable.
    min_keys = {"category_tag", "title_en", "summary_en"}
    if min_keys.issubset(set(k for k, v in data.items() if v)):
        return data
    return None


def _normalize_analyzed_payload(data: dict, article: Article) -> dict:
    """
    Fill missing fields and strip noise from parsed payload.
    """
    normalized = dict(data or {})
    normalized.setdefault("category_tag", article.category or "Research")
    normalized.setdefault("title_zh", article.title)
    normalized.setdefault("title_en", article.title)
    normalized.setdefault("title_de", normalized.get("title_en") or article.title)
    normalized.setdefault("summary_zh", "")
    normalized.setdefault("summary_en", "")
    normalized.setdefault("summary_de", "")
    normalized.setdefault("core_tech_points", "")
    normalized.setdefault("german_context", article.source or "")
    normalized.setdefault("tool_stack", "")
    normalized.setdefault("simple_explanation", "")
    normalized.setdefault("technician_analysis_de", "")
    # Fallback to summary or snippet if explanation is missing
    if not normalized.get("simple_explanation"):
        summary = normalized.get("summary_zh") or normalized.get("summary_en") or ""
        normalized["simple_explanation"] = f"【AI 自动生成】{summary}" if summary else f"原文摘要: {article.content_snippet[:200]}..."

    if not normalized.get("technician_analysis_de"):
        summary_de = normalized.get("summary_de") or normalized.get("summary_en") or ""
        normalized["technician_analysis_de"] = f"[AI Generated] {summary_de}" if summary_de else f"Auszug: {article.content_snippet[:200]}..."
    normalized["technician_analysis_de"] = _normalize_technician_text_de(str(normalized.get("technician_analysis_de", "")))

    return normalized


def _extract_text_from_message_content(content: object) -> str:
    """
    Normalize OpenAI-compatible message.content to plain text.
    兼容 str / list[parts] / dict 的 message.content 输出结构。
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        # Some providers may already return a JSON object-like dict
        return json.dumps(content, ensure_ascii=False)
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    chunks.append(item["text"])
                    continue
                # For unknown part shape, serialize to preserve information.
                chunks.append(json.dumps(item, ensure_ascii=False))
                continue
            chunks.append(str(item))
        return "\n".join(part for part in chunks if part).strip()
    return str(content)


def _derive_safe_fallback(article: Article) -> AnalyzedArticle:
    """
    Build a deterministic, non-empty fallback when model output is unavailable.
    在模型失败时构建可读的保底结果，避免 N/A 和空字段。
    """
    snippet = (article.content_snippet or "").strip()
    compact_snippet = re.sub(r"\s+", " ", snippet)[:240]
    summary_zh = "模型分析暂不可用，以下为基于原文标题与摘要的快速整理。"
    summary_en = "Model analysis temporarily unavailable; generated from source title and snippet."
    summary_de = "Modellanalyse vorübergehend nicht verfügbar; Zusammenfassung aus Titel und Textauszug."
    context = article.source or "Source article"

    simple_explain = (
        f"原文主题：{article.title}。"
        f"{' 摘要：' + compact_snippet if compact_snippet else ''}"
        " 建议稍后重跑以生成完整 AI 分析。"
    )
    technician_explain = (
        f"Thema: {article.title}. "
        f"{'Auszug: ' + compact_snippet + '. ' if compact_snippet else ''}"
        "Bitte Lauf erneut starten, um vollständige Techniker-Analyse zu erzeugen."
    )
    technician_explain = _normalize_technician_text_de(technician_explain)

    return AnalyzedArticle(
        category_tag=article.category or "Research",
        title_zh=article.title,
        title_en=article.title,
        title_de=article.title,
        core_tech_points="Auto fallback summary from source snippet.",
        german_context=context,
        source_name=article.source,
        source_url=article.url,
        summary_zh=summary_zh,
        summary_en=summary_en,
        summary_de=summary_de,
        tool_stack=FALLBACK_TOOLSTACK_MARKER,
        simple_explanation=simple_explain,
        technician_analysis_de=technician_explain,
        original=article,
        target_personas=article.target_personas,
    )


# 系统提示词 (System Prompt)
# 指导 LLM 以特定 JSON 格式输出分析结果
SYSTEM_PROMPT = """\
Role: 你是一位深耕德国工业 4.0 领域的资深技术专家，擅长连接自动化工程（OT）与数据科学（IT）。

Task: 请针对以下抓取到的技术动态，进行“一文两看”的多视角深度分析，分别面向“专业学生”和“行业视角（机械/制造企业决策与实施团队）”。

Constraint (核心限制):
1. 拒绝陈词滥调：
   - 学生视角：解释数据流向（传感器 -> PLC -> Jupyter -> 仿真模型）。
   - 行业视角：必须严格基于以下三个支柱组织分析：
     Reliability & Determinism：机械行业容错率接近零，强调确定性结果与可验证性，避免“幻觉”风险。
     Convergence of Physics & Digital：强调 AI 对热力学、流体力学、材料疲劳等物理机理的结合能力，而非仅文本处理。
     Protection of Long-term Assets：强调在不泄露核心工艺数据前提下应用 AI，保护知识产权与长期资产。
2. 双语对齐：关键术语保留德语和英文原词并附带中文注释。
3. 输出结构要求（industry_analysis 对应 technician_analysis_de 字段）：
   - technician_analysis_de 必须使用德语（German）输出。
   - 按三个支柱分点输出，避免泛泛而谈。
   - 每点包含“判断 + 工业影响 + 落地约束/前提”。
   - 仅讨论行业决策与落地，不重复学生视角的原理讲解。
   - 优先给出机械制造场景下的可执行建议。

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
    "simple_explanation": "深度通俗解读(学生视角): 解释技术逻辑与痛点",
    "technician_analysis_de": "Industry Analysis in German only: decision-making and implementation focus, structured by the three pillars."
}

类别选项: Digital Twin / Industry 4.0 / Simulation / AI / Research
重点关注: VDI标准, AAS(Verwaltungsschale), 工业软件工具名称
只输出JSON，不要任何解释文字。
"""

SIMPLE_JSON_PROMPT = (
    'You are a JSON generator. Output ONLY a JSON object with these keys: '
    '"category_tag", "title_zh", "title_en", "title_de", "summary_zh", "summary_en", "summary_de", '
    '"core_tech_points", "german_context", "tool_stack", "simple_explanation", "technician_analysis_de". '
    "No explanation, no markdown, ONLY JSON. "
    "simple_explanation must stay student-friendly and explain technical logic clearly. "
    "technician_analysis_de must be in German, industry-focused on decision-making and implementation only, "
    "and structured by three pillars: "
    "Reliability & Determinism, Convergence of Physics & Digital, Protection of Long-term Assets."
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

    user_content = (
        f"标题: {article.title}\n"
        f"来源: {article.source}\n"
        f"链接: {article.url}\n"
        f"内容片段:\n{article.content_snippet[:800]}\n\n"
        f"请只输出JSON。"
    )

    data = None
    for attempt in range(1, MAX_ANALYSIS_RETRIES + 1):
        # Attempt strategy:
        # - Local: simplified prompt first, then minimal prompt
        # - Remote: domain prompt directly
        if IS_LOCAL:
            data = _call_and_parse(client, SIMPLE_JSON_PROMPT, user_content)
            if data is None:
                logger.warning(
                    f"[{API_PROVIDER}] Retry with minimal strict schema for '{article.title[:40]}' (attempt {attempt}/{MAX_ANALYSIS_RETRIES})"
                )
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
                    'Use empty string if unknown. '
                    'simple_explanation must stay student-friendly. '
                    'technician_analysis_de must be in German and only cover industry decision-making and implementation, '
                    'with these three pillars: '
                    'Reliability & Determinism, Convergence of Physics & Digital, Protection of Long-term Assets.'
                )
                data = _call_and_parse(client, minimal_prompt, minimal_user_content)
        else:
            data = _call_and_parse(client, SYSTEM_PROMPT, user_content)

        if data is not None:
            break

    if data is None:
        logger.error(f"[{API_PROVIDER}] All parse attempts failed for '{article.title[:40]}'")
        return _derive_safe_fallback(article)

    # Helper to force string type
    def _ensure_str(value: any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return _format_structured_value(value)
        if isinstance(value, dict):
            return _format_structured_value(value)
        return str(value)

    data = _normalize_analyzed_payload(data, article)

    # Construct AnalyzedArticle from JSON data
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
    analyzed.technician_analysis_de = _normalize_technician_text_de(analyzed.technician_analysis_de)

    logger.info(f"[{API_PROVIDER}] ✅ Analyzed: [{analyzed.category_tag}] {analyzed.title_zh[:50]}")
    return analyzed


def _call_and_parse(client: OpenAI, system_prompt: str, user_content: str) -> dict | None:
    """Call the model and attempt to parse JSON from the response."""
    try:
        request_kwargs: dict = {
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

        raw = _extract_text_from_message_content(response.choices[0].message.content)
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
        logger.warning(f"[{API_PROVIDER}] API call with JSON mode failed: {e}")
        # Local providers can be sensitive to JSON mode flags; retry once without it.
        if not IS_LOCAL:
            return None
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                max_tokens=MAX_TOKENS,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            raw = _extract_text_from_message_content(response.choices[0].message.content)
            if not raw:
                logger.warning(f"[{API_PROVIDER}] Empty response from model (retry)")
                return None
            raw = raw.strip()
            logger.info(f"[{API_PROVIDER}] Raw response retry ({len(raw)} chars): {raw[:300]}...")
            data = _extract_json(raw)
            if data is None:
                logger.warning(f"[{API_PROVIDER}] Could not extract JSON from retry response")
            return data
        except Exception as retry_exc:
            logger.error(f"[{API_PROVIDER}] API call error (retry): {retry_exc}")
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
    if IS_LOCAL and not mock and not _is_local_endpoint_reachable():
        logger.error(
            f"[{API_PROVIDER}] Local endpoint unreachable ({LLM_BASE_URL}); using fallback summaries for all articles"
        )
        return [_derive_safe_fallback(article) for article in articles]

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
