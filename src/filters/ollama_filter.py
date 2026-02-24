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
NONE_RATE_ALERT_THRESHOLD = float(os.getenv("LLM_FILTER_NONE_ALERT_THRESHOLD", "0.3"))
MIN_SCORE_FOR_LLM_FILTER = 3

DOMAIN_ORDER = [
    "factory",
    "robotics",
    "automotive",
    "supply_chain",
    "energy",
    "cybersecurity",
]

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "factory": [
        "factory", "manufacturing", "shopfloor", "production line", "process optimization",
        "quality inspection", "defect detection", "predictive maintenance", "condition monitoring",
        "plc", "scada", "mes", "oee",
    ],
    "robotics": [
        "robot", "robotics", "cobot", "amr", "agv", "humanoid", "manipulator", "end effector",
        "robot integration", "isaac", "embodied ai",
    ],
    "automotive": [
        "automotive", "vehicle", "ev", "oem", "tier 1", "autonomous driving", "battery pack",
        "车", "汽车", "车企",
    ],
    "supply_chain": [
        "supply chain", "logistics", "warehouse", "inventory", "procurement", "fulfillment",
        "demand forecasting", "material flow",
    ],
    "energy": [
        "energy", "power", "grid", "utility", "solar", "wind", "battery", "substation",
        "power plant", "电网", "能源",
    ],
    "cybersecurity": [
        "cybersecurity", "cyber security", "ot security", "ics security", "iec 62443", "threat",
        "vulnerability", "intrusion", "anomaly detection", "incident response", "ransomware",
        "zero trust", "siem", "soc", "nerc cip",
    ],
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


def _normalize_text(text: str) -> str:
    """Lowercase and normalize separators for robust keyword matching."""
    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[\s_/]+", " ", text)
    return text


def _contains_keyword(text: str, keyword: str) -> bool:
    """Keyword match with basic word-boundary protection."""
    kw = _normalize_text(keyword).strip()
    norm_text = _normalize_text(text)
    if not kw:
        return False
    # 如果包含宽字符（如中文），通常不需要单词边界，因为中文没有空格分隔
    if any(ord(c) > 0x2E7F for c in kw):
        return kw in norm_text
    # Use boundary matching for single-token keywords to avoid accidental hits.
    if " " not in kw:
        return re.search(rf"\b{re.escape(kw)}\b", norm_text) is not None
    return kw in norm_text


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

    # 1. 过滤掉单单词或过短的无意义标题
    title = (article.title or "").strip()
    words = title.split()
    # If title is 1 word and very short, or 2 words and short
    # This prevents blocking valid Chinese titles which often have 0 spaces but > 10 chars.
    if len(title) <= 15:
        if len(words) <= 1 or len(words) == 2:
            logger.debug(f"  single-word/short title filtered: {title[:80]}")
            return 0, []
        
    text = _normalize_text(f"{article.title} {article.content_snippet}")
    score = 0
    personas = set()

    # --- 域名白名单检查 (Trusted Source Domain Boost) ---
    article_url = (article.url or "").lower()
    is_trusted_domain = any(domain in article_url for domain in TRUSTED_SOURCE_DOMAINS)
    if is_trusted_domain:
        score += 1
        logger.debug("  trusted domain boost (+1) -> score=%s: %s", score, article.title[:60])

    for kw in TECHNICIAN_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 1
            personas.add("technician")
            logger.debug(f"  +1 for Technician keyword '{kw}' in: {article.title[:60]}")

    for kw in HIGH_PRIORITY_KEYWORDS:
        if _contains_keyword(text, kw):
            score += 1
            personas.add("student") # High priority usually implies core tech relevant to students
            logger.debug(f"  +1 for keyword '{kw}' in: {article.title[:60]}")

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
            score = max(0, score - 5)
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


def _infer_domain_tags(article: Article) -> list[str]:
    """
    Infer up to 3 six-domain tags from title/snippet/category text.
    如果没有命中，默认返回 ["factory"].
    """
    text = _normalize_text(
        f"{article.title} {article.content_snippet} {article.category}"
    )
    domain_scores: dict[str, int] = {domain: 0 for domain in DOMAIN_ORDER}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if _contains_keyword(text, kw):
                score += 1
        domain_scores[domain] = score

    ranked = sorted(
        DOMAIN_ORDER,
        key=lambda d: (-domain_scores[d], DOMAIN_ORDER.index(d)),
    )
    tags = [domain for domain in ranked if domain_scores[domain] > 0][:3]

    if not tags:
        logger.debug(
            "  domain tag fallback to factory (no keyword hit): %s",
            article.title[:80],
        )
        return ["factory"]
    return tags


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
    过滤流水线 (Filtering pipeline):
    1. Keyword scoring (关键词评分)
    2. Score gate: score >= MIN_SCORE_FOR_LLM_FILTER 直接进入结果集
       （不再做 LLM YES/NO 相关性门禁）

    Returns:
        list[Article]: 按相关性分数降序排列，且包含 domain_tags 的文章列表
    """
    logger.info(f"[FILTER] Starting filter on {len(articles)} articles")

    if skip_llm:
        logger.info("[FILTER] skip_llm=True: relevance gate is keyword-score based (no LLM YES/NO gate)")

    scored: list[Article] = []
    for article in articles:
        score, personas = keyword_score(article)
        article.relevance_score = score
        article.target_personas = personas
        article.domain_tags = []
        scored.append(article)

    scored.sort(key=lambda a: a.relevance_score, reverse=True)
    llm_candidates = [a for a in scored if a.relevance_score >= MIN_SCORE_FOR_LLM_FILTER]
    logger.info(
        "[FILTER] Preselect score >= %s for LLM: %s/%s articles",
        MIN_SCORE_FOR_LLM_FILTER,
        len(llm_candidates),
        len(scored),
    )

    result: list[Article] = []
    domain_distribution: dict[str, int] = {domain: 0 for domain in DOMAIN_ORDER}
    for article in llm_candidates:
        article.domain_tags = _infer_domain_tags(article)
        for tag in article.domain_tags:
            domain_distribution[tag] = domain_distribution.get(tag, 0) + 1
        result.append(article)

    logger.info(
        "[FILTER] %s/%s passed score gate (>= %s); domain_distribution=%s",
        len(result),
        len(scored),
        MIN_SCORE_FOR_LLM_FILTER,
        domain_distribution,
    )

    # Sort by relevance score descending (按分数降序排序)
    result.sort(key=lambda a: a.relevance_score, reverse=True)
    return result
