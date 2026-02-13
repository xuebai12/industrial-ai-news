"""Relevance filtering with keyword scoring + cloud LLM validation."""
"""
相关性过滤模块 (Relevance Filtering)
结合 关键词评分 (Keyword Scoring) 和 云端 LLM 校验 (Cloud LLM Validation) 进行双重过滤。
"""

import logging
import re

from openai import OpenAI

from src.models import Article
from config import (
    HIGH_PRIORITY_KEYWORDS,
    MEDIUM_PRIORITY_KEYWORDS,
    TECHNICIAN_KEYWORDS,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    RELEVANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)
_relevance_client: OpenAI | None = None


def keyword_score(article: Article) -> tuple[int, list[str]]:
    """
    基于关键词匹配计算文章得分与受众标签 (Score article & tag personas).
    - Technician keywords: +3 (Tags: Technician)
    - High-priority keywords: +2 (Tags: Student)
    - Medium-priority keywords: +1
    """
    text = f"{article.title} {article.content_snippet}".lower()
    score = 0
    personas = set()

    for kw in TECHNICIAN_KEYWORDS:
        if kw.lower() in text:
            score += 3
            personas.add("technician")
            logger.debug(f"  +3 for Technician keyword '{kw}' in: {article.title[:60]}")

    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw.lower() in text:
            score += 2
            personas.add("student") # High priority usually implies core tech relevant to students
            logger.debug(f"  +2 for keyword '{kw}' in: {article.title[:60]}")

    for kw in MEDIUM_PRIORITY_KEYWORDS:
        if kw.lower() in text:
            score += 1
            logger.debug(f"  +1 for keyword '{kw}' in: {article.title[:60]}")
    
    # Default to Student if relevant but no specific persona tag
    if score >= RELEVANCE_THRESHOLD and not personas:
        personas.add("student")

    return score, list(personas)


def llm_relevance_check(article: Article) -> bool:
    """
    使用 LLM Cloud 进行二次相关性校验 (Secondary Relevance Check using LLM).
    Returns True if relevant (如果相关则返回 True).
    """
    if not LLM_API_KEY:
        logger.warning("  LLM API key not set — accepting article by default")
        return True

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

        answer = response.choices[0].message.content.strip().upper()
        # 判断回答是否为 YES
        is_relevant = answer.startswith("YES")
        logger.debug(f"  LLM says {'YES' if is_relevant else 'NO'} for: {article.title[:60]}")
        return is_relevant

    except Exception as e:
        logger.warning(f"  LLM check failed (accepting by default): {e}")
        return True  # Accept if API is unavailable (API不可用时默认放行)


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
        for article in scored:
            if llm_relevance_check(article):
                result.append(article)
        logger.info(f"[FILTER] {len(result)}/{len(scored)} passed LLM Cloud validation")

    # Sort by relevance score descending (按分数降序排序)
    result.sort(key=lambda a: a.relevance_score, reverse=True)
    return result
