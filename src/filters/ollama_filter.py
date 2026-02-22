"""Relevance filtering with keyword scoring + cloud LLM validation."""
"""
相关性过滤模块 (Relevance Filtering)
结合 关键词评分 (Keyword Scoring) 和 云端 LLM 校验 (Cloud LLM Validation) 进行双重过滤。
"""

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from src.models import Article
from config import (
    HIGH_PRIORITY_KEYWORDS,
    MEDIUM_PRIORITY_KEYWORDS,
    TECHNICIAN_KEYWORDS,
    INDUSTRY_CONTEXT_KEYWORDS,
    NEG_SOFT_LISTICLES,
    NEG_CORPORATE_PR,
    NEG_VAGUE_TRENDS,
    NEG_MARKET_MOVES,
    HARD_TECH_KEYWORDS,
    NEGATIVE_THEORY_ONLY_KEYWORDS,
    NEGATIVE_RECRUITMENT_KEYWORDS,
    HARD_EXCLUDE_NOISE_KEYWORDS,
    DOWNWEIGHT_NOISE_KEYWORDS,
    UNIVERSAL_ROBOTS_PROMO_KEYWORDS,
    TRUSTED_SOURCE_DOMAINS,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    RELEVANCE_THRESHOLD,
    API_PROVIDER,
)

logger = logging.getLogger(__name__)
_relevance_client: OpenAI | None = None
MIN_RELEVANT_ARTICLES = max(0, int(os.getenv("MIN_RELEVANT_ARTICLES", "5")))
IS_LOCAL = API_PROVIDER == "Local_Ollama"
MAX_CONCURRENCY = max(1, int(os.getenv("KIMI_MAX_CONCURRENCY", "1" if IS_LOCAL else "4")))
FILTER_MAX_RETRIES = int(os.getenv("KIMI_FILTER_MAX_RETRIES", "1" if IS_LOCAL else "0"))
FILTER_TIMEOUT_SECONDS = float(os.getenv("KIMI_FILTER_TIMEOUT_SECONDS", "20"))
FILTER_MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("KIMI_FILTER_MIN_REQUEST_INTERVAL_SECONDS", "2.0" if not IS_LOCAL else "0.2"))
FILTER_RATE_LIMIT_BACKOFF_SECONDS = float(os.getenv("KIMI_FILTER_RATE_LIMIT_BACKOFF_SECONDS", "10"))
FILTER_RATE_LIMIT_MAX_RETRIES = int(os.getenv("KIMI_FILTER_RATE_LIMIT_MAX_RETRIES", "1"))
_filter_rate_lock = threading.Lock()
_filter_last_request_ts = 0.0

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


def check_article_substance(article: Article) -> bool:
    """
    Substance Check (实质性校验):
    1. Generic placeholders: "overview", "topics", etc.
    2. Bosch Stories navigation pages: bosch.com/stories with "overview".
    3. Empty series titles: "Edition" without a topic (no : or -).
    """
    title = (article.title or "").strip()
    title_lower = title.lower()
    url = (article.url or "").lower()

    # 1. 过滤掉只有“概述”或“话题”类的单次/短词标题
    empty_placeholders = ["overview", "fachthemen", "topics", "introduction", "blog post", "news"]
    if title_lower in empty_placeholders:
        return False

    # 2. 过滤掉来自 Bosch Stories 等营销号的通用导航页
    if "bosch.com/stories" in url and "overview" in title_lower:
        return False

    # 3. 过滤掉没有具体内容的系列号
    # 例如 "MX-Talk, Edition 25" 这种只有编号没有主题的
    if "edition" in title_lower and ":" not in title_lower and "-" not in title_lower:
        return False

    return True


def keyword_score(article: Article) -> tuple[int, list[str]]:
    """
    基于关键词匹配计算文章得分与受众标签 (Score article & tag personas).
    - Technician keywords: +3 (Tags: Technician)
    - High-priority keywords: +3 (Tags: Student)
    - Medium-priority keywords: +1
    - Trusted source domain: score boosted to >= RELEVANCE_THRESHOLD
    """
    # 0) Substance check (实质性校验)
    if not check_article_substance(article):
        logger.debug(f"  substance check failed: {article.title[:80]}")
        return 0, []

    text = _normalize_text(f"{article.title} {article.content_snippet}")
    score = 0
    personas = set()

    # --- 域名白名单检查 (Trusted Source Domain Boost) ---
    # 命中受信域名的文章直接获得最低通过分数（不硬性绕过负向词/HARD_EXCLUDE，只保底）。
    article_url = (article.url or "").lower()
    is_trusted_domain = any(domain in article_url for domain in TRUSTED_SOURCE_DOMAINS)
    if is_trusted_domain:
        score = RELEVANCE_THRESHOLD  # 保底通过阈值；负向词仍可将其降回 0
        logger.debug("  trusted domain boost -> score=%s: %s", score, article.title[:60])

    for kw in TECHNICIAN_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 3
            personas.add("technician")
            logger.debug(f"  +3 for Technician keyword '{kw}' in: {article.title[:60]}")

    for kw in HIGH_PRIORITY_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 3
            personas.add("student") # High priority usually implies core tech relevant to students
            logger.debug(f"  +3 for keyword '{kw}' in: {article.title[:60]}")

    for kw in MEDIUM_PRIORITY_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 1
            logger.debug(f"  +1 for keyword '{kw}' in: {article.title[:60]}")

    # 宽进：若未命中现有清单，再用通用词做低权重召回
    if score == 0:
        for kw in BROAD_KEYWORDS:
            if _contains_keyword(text, kw):
                score += 1

    # --- 负面特征词库分类过滤 (Negative Keyword Taxonomy Filtering) ---

    # B & D: 企业公关、品牌故事、投融资、市场动作 -> 强制排除 (Hard Exclude)
    has_cat_b = any(_contains_keyword(text, kw) for kw in NEG_CORPORATE_PR)
    has_cat_d = any(_contains_keyword(text, kw) for kw in NEG_MARKET_MOVES)
    if has_cat_b or has_cat_d:
        logger.debug(f"  Category B or D noise filtered: {article.title[:80]}")
        return 0, []

    # A: 软性教程与清单 (Soft Content & Listicles) -> 降权，无技术词则过滤
    has_cat_a = any(_contains_keyword(text, kw) for kw in NEG_SOFT_LISTICLES)
    if has_cat_a:
        has_hard_tech = any(_contains_keyword(text, kw) for kw in HARD_TECH_KEYWORDS)
        if not has_hard_tech:
            logger.debug(f"  Category A noise filtered (no tech keywords): {article.title[:80]}")
            return 0, []
        else:
            score = max(0, score - 2)
            logger.debug(f"  Category A noise downweighted (with tech keywords): {article.title[:80]}")

    # C: 宏观趋势与行业观察 (Vague Trends & Insights) -> 低分直接过滤
    has_cat_c = any(_contains_keyword(text, kw) for kw in NEG_VAGUE_TRENDS)
    if has_cat_c and score < RELEVANCE_THRESHOLD:
        logger.debug(f"  Category C noise filtered (low score): {article.title[:80]}")
        return 0, []

    # Additional Hard Excludes (specific strings)
    has_hard_exclude = any(_contains_keyword(text, kw) for kw in HARD_EXCLUDE_NOISE_KEYWORDS)
    if has_hard_exclude:
        has_hard_tech = any(_contains_keyword(text, kw) for kw in HARD_TECH_KEYWORDS)
        if not has_hard_tech:
            logger.debug(f"  hard-exclude noise filtered: {article.title[:80]}")
            return 0, []
        else:
            score = max(0, score - 2)
            logger.debug(f"  hard-exclude noise downweighted (with tech keywords): {article.title[:80]}")

    # 理论/招聘类过滤
    has_negative_theory = any(_contains_keyword(text, kw) for kw in NEGATIVE_THEORY_ONLY_KEYWORDS)
    has_negative_recruitment = any(_contains_keyword(text, kw) for kw in NEGATIVE_RECRUITMENT_KEYWORDS)
    has_industry_context = any(_contains_keyword(text, kw) for kw in INDUSTRY_CONTEXT_KEYWORDS)

    if (has_negative_theory or has_negative_recruitment) and not has_industry_context:
        logger.debug(f"  theory/recruitment noise filtered: {article.title[:80]}")
        return 0, []
    if (has_negative_theory or has_negative_recruitment) and has_industry_context:
        score = max(1, score - 2)
        logger.debug(f"  theory/recruitment noise downweighted with industry context: {article.title[:80]}")

    # (Keep rest of existing logic for URL, UR promo, YouTube, etc.)
    url_text = (article.url or "").lower()
    hard_exclude_url_parts = ("/presse/", "/press/", "/media-contact", "/press-contact")
    if any(part in url_text for part in hard_exclude_url_parts):
        return 0, []

    has_ur_brand = "universal robots" in text
    has_ur_promo = any(_contains_keyword(text, kw) for kw in UNIVERSAL_ROBOTS_PROMO_KEYWORDS)
    if has_ur_brand and has_ur_promo:
        return 0, []

    has_downweight_noise = any(_contains_keyword(text, kw) for kw in DOWNWEIGHT_NOISE_KEYWORDS)
    if has_downweight_noise:
        score = max(0, score - 2)

    is_youtube_source = "youtube" in (article.source or "").lower() or "youtu" in (article.url or "").lower()
    is_shorts = "/shorts/" in (article.url or "")
    if is_shorts and score < RELEVANCE_THRESHOLD + 1:
        score = max(0, score - 1)

    if is_youtube_source and article.video_views is not None and article.video_views < 10:
        score = max(0, score - 2)

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
            _relevance_client = OpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                max_retries=FILTER_MAX_RETRIES,
            )
        client = _relevance_client

        prompt = (
            f"Title: {article.title}\n"
            f"Snippet: {article.content_snippet[:300]}\n\n"
            "Decide relevance for this newsletter.\n"
            "Return YES only if BOTH conditions are true:\n"
            "1) The content is clearly AI-related (e.g., AI/ML/LLM/computer vision/predictive model).\n"
            "2) The AI use case is in at least one target industrial domain:\n"
            "- Factory (including: design & R&D, production/process optimization, quality/defect analysis, asset ops/predictive maintenance)\n"
            "- Robotics\n"
            "- Automotive\n"
            "- Supply Chain\n"
            "- Energy\n"
            "- Cybersecurity (OT/ICS)\n"
            "If it is only generic industry/automotive/business news without concrete AI application, return NO.\n"
            "Reply with only YES or NO."
        )

        for attempt in range(FILTER_RATE_LIMIT_MAX_RETRIES + 1):
            global _filter_last_request_ts
            with _filter_rate_lock:
                now = time.monotonic()
                wait_s = FILTER_MIN_REQUEST_INTERVAL_SECONDS - (now - _filter_last_request_ts)
                if wait_s > 0:
                    time.sleep(wait_s)
                _filter_last_request_ts = time.monotonic()

            try:
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a strict relevance filter for industrial AI news. "
                                "Require explicit AI signal and target-domain fit. "
                                "Reply with only YES or NO."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=5,
                    timeout=FILTER_TIMEOUT_SECONDS,
                )
                break
            except Exception as e:
                msg = str(e).lower()
                if ("429" in msg or "too many requests" in msg) and attempt < FILTER_RATE_LIMIT_MAX_RETRIES:
                    backoff = FILTER_RATE_LIMIT_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        "  LLM filter 429, backoff %.1fs then retry (%s/%s)",
                        backoff,
                        attempt + 1,
                        FILTER_RATE_LIMIT_MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue
                raise

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
                    result.append(article)
        logger.info(f"[FILTER] {len(result)}/{len(scored)} passed LLM Cloud validation")

    # Ensure a minimum daily volume for digest stability.
    # Only pull in candidates with score >= 2 to avoid low-quality fallback content.
    if MIN_RELEVANT_ARTICLES and len(result) < MIN_RELEVANT_ARTICLES:
        existing_keys = {
            f"{(a.url or '').strip()}|{(a.title or '').strip().lower()}"
            for a in result
        }
        for candidate in sorted(scored, key=lambda a: a.relevance_score, reverse=True):
            if candidate.relevance_score < 2:
                continue  # Skip low-scored items even in fallback
            key = f"{(candidate.url or '').strip()}|{(candidate.title or '').strip().lower()}"
            if key in existing_keys:
                continue
            result.append(candidate)
            existing_keys.add(key)
            if len(result) >= MIN_RELEVANT_ARTICLES:
                break
        logger.info(
            "[FILTER] Applied minimum-volume fallback: now %s items (target=%s, min_score=2)",
            len(result),
            MIN_RELEVANT_ARTICLES,
        )

    # Sort by relevance score descending (按分数降序排序)
    result.sort(key=lambda a: a.relevance_score, reverse=True)
    return result
