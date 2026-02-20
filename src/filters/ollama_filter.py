"""Relevance filtering with keyword scoring + cloud LLM validation."""
"""
相关性过滤模块 (Relevance Filtering)
结合 关键词评分 (Keyword Scoring) 和 云端 LLM 校验 (Cloud LLM Validation) 进行双重过滤。
"""

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from src.models import Article
from config import (
    HIGH_PRIORITY_KEYWORDS,
    MEDIUM_PRIORITY_KEYWORDS,
    TECHNICIAN_KEYWORDS,
    INDUSTRY_CONTEXT_KEYWORDS,
    THEORY_ONLY_RISK_KEYWORDS,
    THEORY_CONTEXT_DEPENDENT_KEYWORDS,
    STRICT_INDUSTRY_CONTEXT_GATING,
    FALLBACK_REQUIRE_INDUSTRY_CONTEXT,
    PRIORITY_INDUSTRIAL_SOURCES,
    TARGET_SEARCH_DOMAINS,
    AI_RELEVANCE_KEYWORDS,
    REQUIRE_AI_SIGNAL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    RELEVANCE_THRESHOLD,
    API_PROVIDER,
)

logger = logging.getLogger(__name__)
_relevance_client: OpenAI | None = None
MIN_RELEVANT_ARTICLES = max(0, int(os.getenv("MIN_RELEVANT_ARTICLES", "12")))
IS_LOCAL = API_PROVIDER == "Local_Ollama"
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "1" if IS_LOCAL else "4")))
PRIORITY_INDUSTRIAL_SOURCE_SET = {item.strip().casefold() for item in PRIORITY_INDUSTRIAL_SOURCES}
THEORY_CONTEXT_DEPENDENT_SET = {
    re.sub(r"[\s_/]+", " ", item.lower().replace("-", " ")).strip()
    for item in THEORY_CONTEXT_DEPENDENT_KEYWORDS
    if isinstance(item, str) and item.strip()
}

# 宽进：补充更通用的工业 AI 主题词，覆盖标题/摘要中的常见表达
BROAD_KEYWORDS = [
    "industrial",
    "industry",
    "manufacturing",
    "factory",
    "automation",
    "robot",
    "digital",
    "smart",
    "simulation",
    "predictive",
    "maintenance",
    "plc",
    "iot",
    "ai",
    "machine learning",
    "computer vision",
]

_TARGET_DOMAIN_KEYWORDS = {
    name: [
        re.sub(r"[\s_/]+", " ", str(kw).lower().replace("-", " ")).strip()
        for kw in keywords
        if isinstance(kw, str) and kw.strip()
    ]
    for name, keywords in TARGET_SEARCH_DOMAINS.items()
}


def _normalize_text(text: str) -> str:
    """Lowercase and normalize separators for robust keyword matching."""
    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[\s_/]+", " ", text)
    return text


def _contains_keyword(text: str, keyword: str) -> bool:
    """Keyword match with basic word-boundary protection."""
    kw = _normalize_text(keyword).strip()
    if not kw:
        return False
    # Use boundary matching for single-token keywords to avoid accidental hits.
    if " " not in kw:
        return re.search(rf"\b{re.escape(kw)}\b", text) is not None
    return kw in text


def _has_industry_context(text: str) -> bool:
    return any(_contains_keyword(text, kw) for kw in INDUSTRY_CONTEXT_KEYWORDS)


def _has_theory_risk(text: str) -> bool:
    return any(_contains_keyword(text, kw) for kw in THEORY_ONLY_RISK_KEYWORDS)


def _matched_target_domains(text: str) -> set[str]:
    hits: set[str] = set()
    for domain, keywords in _TARGET_DOMAIN_KEYWORDS.items():
        if any(_contains_keyword(text, kw) for kw in keywords):
            hits.add(domain)
    return hits


def _has_ai_signal(text: str) -> bool:
    return any(_contains_keyword(text, kw) for kw in AI_RELEVANCE_KEYWORDS)


def _is_fallback_eligible(article: Article) -> bool:
    text = _normalize_text(f"{article.title} {article.content_snippet}")
    has_industry = _has_industry_context(text)
    has_theory_risk = _has_theory_risk(text)
    target_domains = _matched_target_domains(text)
    has_ai = _has_ai_signal(text)
    source = (article.source or "").strip().casefold()
    in_priority_source = source in PRIORITY_INDUSTRIAL_SOURCE_SET
    if REQUIRE_AI_SIGNAL and not has_ai:
        return False
    if FALLBACK_REQUIRE_INDUSTRY_CONTEXT:
        return has_industry or in_priority_source or bool(target_domains)
    return not (STRICT_INDUSTRY_CONTEXT_GATING and has_theory_risk and not has_industry)


def keyword_score(article: Article) -> tuple[int, list[str]]:
    """
    基于关键词匹配计算文章得分与受众标签 (Score article & tag personas).
    - Technician keywords: +3 (Tags: Technician)
    - High-priority keywords: +2 (Tags: Student)
    - Medium-priority keywords: +1
    """
    text = _normalize_text(f"{article.title} {article.content_snippet}")
    has_industry_context = _has_industry_context(text)
    has_theory_risk = _has_theory_risk(text)
    matched_domains = _matched_target_domains(text)
    has_ai = _has_ai_signal(text)
    score = 0
    personas = set()

    for kw in TECHNICIAN_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 3
            personas.add("technician")
            logger.debug(f"  +3 for Technician keyword '{kw}' in: {article.title[:60]}")

    for kw in HIGH_PRIORITY_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 2
            personas.add("student") # High priority usually implies core tech relevant to students
            logger.debug(f"  +2 for keyword '{kw}' in: {article.title[:60]}")

    for kw in MEDIUM_PRIORITY_KEYWORDS:
        kw_norm = _normalize_text(kw)
        if (
            STRICT_INDUSTRY_CONTEXT_GATING
            and kw_norm in THEORY_CONTEXT_DEPENDENT_SET
            and not has_industry_context
        ):
            continue
        if _contains_keyword(text, kw):
            score += 1
            logger.debug(f"  +1 for keyword '{kw}' in: {article.title[:60]}")

    # 宽进：若未命中现有清单，再用通用词做低权重召回
    if score == 0:
        for kw in BROAD_KEYWORDS:
            if _contains_keyword(text, kw):
                score += 1
                break

    # Prioritize the six target domains for retrieval.
    if matched_domains:
        score += 1

    # Add a weak positive signal only when theoretical terms appear in clear industrial context.
    if has_theory_risk and has_industry_context:
        score += 1

    # Medium-strict gate: theory-heavy but no industrial context is heavily down-ranked.
    if STRICT_INDUSTRY_CONTEXT_GATING and has_theory_risk and not has_industry_context:
        score = min(score, 1)

    # Hard gate: must be AI-related, avoid purely industrial/automotive generic news.
    if REQUIRE_AI_SIGNAL and not has_ai:
        score = 0

    # Expose flags for downstream filter/fallback decisions.
    setattr(article, "has_industry_context", has_industry_context)
    setattr(article, "has_theory_risk", has_theory_risk)
    setattr(article, "matched_target_domains", sorted(matched_domains))
    setattr(article, "has_ai_signal", has_ai)

    # Default to Student if relevant but no specific persona tag
    if score >= RELEVANCE_THRESHOLD and not personas:
        personas.add("student")

    return score, list(personas)


def llm_relevance_check(article: Article) -> bool | None:
    """
    使用 LLM Cloud 进行二次相关性校验 (Secondary Relevance Check using LLM).
    Returns True if relevant (如果相关则返回 True).
    """
    if not LLM_API_KEY:
        logger.warning("  LLM API key not set")
        return None

    try:
        global _relevance_client
        if _relevance_client is None:
            _relevance_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        client = _relevance_client

        prompt = (
            f"Title: {article.title}\n"
            f"Snippet: {article.content_snippet[:300]}\n\n"
            "Is this article about industrial AI, discrete event simulation, "
            "digital twin, or smart manufacturing? Reply with only YES or NO."
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a relevance filter for industrial technology news. "
                        "Reply with only YES or NO."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=5,
            timeout=20,
        )

        answer = (response.choices[0].message.content or "").strip().upper()
        # 容错解析：支持 YES/JA/是 的简短变体；明确 NO/NEIN/否 则拒绝。
        if re.search(r"\b(NO|NEIN)\b", answer) or "否" in answer:
            is_relevant = False
        elif re.search(r"\b(YES|JA)\b", answer) or "是" in answer:
            is_relevant = True
        else:
            # 非结构化回答，作为不确定结果交给上层兜底策略
            return None
        logger.debug(f"  LLM says {'YES' if is_relevant else 'NO'} for: {article.title[:60]}")
        return is_relevant

    except Exception as e:
        logger.warning(f"  LLM check failed: {e}")
        return None


def filter_articles(articles: list[Article], skip_llm: bool = False) -> list[Article]:
    """
    双重过滤流水线 (Two-stage filtering pipeline):
    1. Keyword scoring (关键词评分) — 必须达到阈值
    2. LLM validation (LLM 校验) — 可选步骤 (skip_llm=True 跳过)

    Returns:
        list[Article]: 按相关性分数降序排列的文章列表
    """
    logger.info(f"[FILTER] Starting filter on {len(articles)} articles")

    scored: list[Article] = []
    for article in articles:
        score, personas = keyword_score(article)
        article.relevance_score = score
        # We need to add target_personas to Article model first? 
        # Wait, Article model is raw, AnalyzedArticle has target_personas. 
        # But we filter Article objects here. 
        # Let's dynamically attach it or update Article model.
        # Check src/models.py again. Article does NOT have target_personas.
        # Decision: Add target_personas to Article model as well to carry it through.
        setattr(article, "target_personas", personas) # Temporary dynamic attribute until models.py updated for Article

        if score >= RELEVANCE_THRESHOLD:
            scored.append(article)

    logger.info(f"[FILTER] {len(scored)}/{len(articles)} passed keyword threshold (>={RELEVANCE_THRESHOLD})")

    if skip_llm:
        logger.info("[FILTER] Skipping LLM validation (keyword-only mode)")
        result = scored
    else:
        result = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
            future_to_article = {
                executor.submit(llm_relevance_check, article): article
                for article in scored
            }
            for future in future_to_article:
                article = future_to_article[future]
                try:
                    llm_result = future.result()
                except Exception as e:
                    logger.error(f"LLM check failed for {article.title[:30]}: {e}")
                    llm_result = None

                if llm_result is True:
                    result.append(article)
                    continue
                if llm_result is None and article.relevance_score >= 2:
                    # 严出兜底：仅在 LLM 不可判定时放行高分项，避免整批为 0。
                    if _is_fallback_eligible(article):
                        result.append(article)
        logger.info(f"[FILTER] {len(result)}/{len(scored)} passed LLM Cloud validation")

    # Ensure a minimum daily volume for digest stability.
    if MIN_RELEVANT_ARTICLES and len(result) < MIN_RELEVANT_ARTICLES:
        existing_keys = {
            f"{(a.url or '').strip()}|{(a.title or '').strip().lower()}"
            for a in result
        }
        for candidate in sorted(scored, key=lambda a: a.relevance_score, reverse=True):
            key = f"{(candidate.url or '').strip()}|{(candidate.title or '').strip().lower()}"
            if key in existing_keys:
                continue
            if not _is_fallback_eligible(candidate):
                continue
            result.append(candidate)
            existing_keys.add(key)
            if len(result) >= MIN_RELEVANT_ARTICLES:
                break
        logger.info(
            "[FILTER] Applied minimum-volume fallback: now %s items (target=%s)",
            len(result),
            MIN_RELEVANT_ARTICLES,
        )

    # Sort by relevance score descending (按分数降序排序)
    result.sort(key=lambda a: a.relevance_score, reverse=True)
    return result
