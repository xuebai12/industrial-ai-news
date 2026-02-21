"""Central configuration for the Industrial AI Intelligence System."""
"""
工业 AI 情报系统中心配置文件 (Central Configuration)
包含所有环境变量读取、API 设置、邮件配置、数据源定义以及筛选关键词。
"""

import os
from dataclasses import dataclass
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# --- API Config (API 配置) ---
# -----------------------------
# 读取 NVIDIA 的 API Key (MOONSHOT_API_KEY 已移除)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# 外部收件人列表（仅在手动审核通过后，使用 --forward 转发）
# External recipients – only sent after owner review via `python main.py --forward`
EXTERNAL_RECIPIENTS: dict[str, list[str]] = {
    "technician": ["max@max-lang.de"],
}

# Determine which provider to use (自动判断使用哪个模型提供商)
# 优先级 Priority: USE_LOCAL_OLLAMA > NVIDIA NIM > Local Ollama (Fallback)
USE_LOCAL_OLLAMA = os.getenv("USE_LOCAL_OLLAMA", "false").lower() == "true"

if USE_LOCAL_OLLAMA:
    LLM_API_KEY = "ollama"
    LLM_BASE_URL = "http://localhost:11434/v1"
    LLM_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
    API_PROVIDER = "Local_Ollama"
elif NVIDIA_API_KEY and len(NVIDIA_API_KEY) > 10:
    LLM_API_KEY = NVIDIA_API_KEY
    LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"
    LLM_MODEL = "moonshotai/kimi-k2.5"
    API_PROVIDER = "NVIDIA"
else:
    # Fallback to Local Ollama (默认回退到本地 Ollama)
    LLM_API_KEY = "ollama"  # Ollama doesn't require a real key
    LLM_BASE_URL = "http://localhost:11434/v1"
    LLM_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
    API_PROVIDER = "Local_Ollama"

IS_CI = os.getenv("CI", "false").lower() == "true"  # Check if running in CI environment (是否在 CI 环境运行)

# --- Email Config (邮件配置) ---
# -------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")

_smtp_port = os.getenv("SMTP_PORT")
SMTP_PORT = int(_smtp_port) if _smtp_port else 587

SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")

# --- Notion Config (Notion 配置) ---
# -----------------------------------
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# --- Pipeline Config (流水线配置) ---
# ------------------------------------
_max_articles = os.getenv("MAX_ARTICLES_PER_SOURCE")
MAX_ARTICLES_PER_SOURCE = int(_max_articles) if _max_articles else 20  # 每个源最大抓取文章数

_relevance_threshold = os.getenv("RELEVANCE_THRESHOLD")
RELEVANCE_THRESHOLD = int(_relevance_threshold) if _relevance_threshold else 1  # 关键词相关性阈值


# --- Keyword Scoring Rules (Knowledge Graph) ---
# --- 关键词评分规则 (筛选逻辑) ---
# ---------------------------------

# 高优先级关键词 (+2 分)
HIGH_PRIORITY_KEYWORDS = [
    # Core DE terms (德语核心词)
    "Ablaufsimulation",
    "Fertigungssteuerung",
    "Virtuelle Inbetriebnahme",
    "VIBN",
    "KI-gestützte Optimierung",
    "KI-gestützte Fertigung",
    "Diskrete Ereignissimulation",
    "Asset Administration Shell",
    "Verwaltungsschale",
    "Industrial AI",
    "Industrielle KI",
    "AI in Production",
    "KI in der Produktion",
    "Manufacturing AI",

    # Core EN terms (英语核心词)
    "Discrete Event Simulation",
    "Digital Twin",
    "Digitaler Zwilling",
    "Machine Vision",
    "Industrial Vision",
    "Edge AI",
    "AIoT",
    "Virtual Commissioning",
    "Predictive Quality",
    "Condition Monitoring",
    "Industrial Copilot",
    "Production Optimization",
    "Smart Maintenance",
]

# 技师视角高优先级关键词 (+3 分)
TECHNICIAN_KEYWORDS = [
    "Instandhaltung",          # Maintenance
    "Anlagenverfügbarkeit",    # Plant availability
    "SPS",                     # PLC (German)
    "PLC",
    "TIA Portal",
    "OEE",                     # Overall Equipment Effectiveness
    "Sicherheit",              # Safety
    "Störungsbehebung",        # Troubleshooting
    "Wartung",                 # Servicing
    "Inbetriebnahme",          # Commissioning
    "Fernwartung",             # Remote maintenance
    "SCADA",
    "MES",
    "HMI",
    "OPC UA",
    "Anomaly Detection",
    "collaborative robot",     # Cobot applications (e.g. Universal Robots videos)
    "cobot",                   # Shorthand for collaborative robot
    "AI chip",                 # AI chip supply/demand news (high signal for industrial AI readers)
]

# 中优先级关键词 (+1 分)
MEDIUM_PRIORITY_KEYWORDS = [
    "Automatisierungstechnik", # Automation technology
    "Smart Factory",
    "Intelligente Fabrik",
    "Predictive Maintenance",
    "Vorausschauende Wartung",
    "Reinforcement Learning",
    "Deep Reinforcement Learning",
    "Multi-Agent System",
    "Cyber-Physical Systems",
    "Materialfluss",          # Material flow
    "Logistiksimulation",     # Logistics simulation
    "Industrie 4.0",
    "Industry 4.0",
    "AnyLogic",
    "Tecnomatix",
    "Plant Simulation",
    "Siemens",
    "Omniverse",
    "Machine Learning in Manufacturing",
    "Computer Vision in Manufacturing",
    "Industrial Computer Vision",
    "Applied AI",
    "AI in manufacturing",
    "Production AI",
    "Factory AI",
    "Shopfloor AI",
    "Industrial GenAI",
    "MLOps",
    "DataOps",
    "Quality Inspection",
    "Defect Detection",
    "Process Mining",
    "Time Series Forecasting",
    "Demand Forecasting",
    "Adaptive Control",
    "Closed-loop optimization",
    "Asset Performance Management",
    "Energy Management",
    "Lean Manufacturing",
    "Batch Optimization",
    "Universal Robots",        # UR brand (cobot manufacturer) - like "Siemens"
]

# 负向词：纯理论/招聘培训/营销活动类噪音
NEGATIVE_THEORY_ONLY_KEYWORDS = [
    # Pure theory / benchmark-heavy
    "theorem",
    "proof",
    "lemma",
    "corollary",
    "axiom",
    "hypergraph",
    "graph neural network benchmark",
    "reasoning benchmark",
    "formal verification",
    "formal logic",
    "meta-learning benchmark",
    "synthetic dataset",
    "toy dataset",
    "ablation study only",
    "state-of-the-art on",
    "leaderboard",
    "openreview",
    "arxiv preprint",
    "multimodal reasoning",
    "chain-of-thought benchmark",
    "spatio-temporal dual-stage",
    "corridor traffic signal control",
    "convex optimization framework",
    "variational bound",
    # Hiring / training
    "job",
    "jobs",
    "hiring",
    "career",
    "careers",
    "internship",
    "vacancy",
    "recruiting",
    "apply now",
    "course",
    "training",
    "bootcamp",
    "certification",
    "workshop",
    "masterclass",
    "tutorial",
    "how to become",
    "stellenangebot",
    "karriere",
    "bewerben",
    "ausbildung",
    "schulung",
    "kurs",
    # Event / recap
    "webinar",
    "register now",
    "event recap",
    "highlights",
    "keynote recap",
    "conference recap",
    "expo highlights",
    "livestream",
    "live stream",
    "podcast episode",
    "summit highlights",
    "meet us at",
    "join us at",
    "save the date",
    "veranstaltung",
    "rückblick",
    "messe",
    "live-übertragung",
    # Marketing / PR
    "press release",
    "brand campaign",
    "award",
    "winner",
    "partnership announcement",
    "sponsored",
    "advertorial",
    "promotion",
    "promo",
    "limited offer",
    "new brochure",
    "customer story",
    "success story",
    "testimonial",
    "pressemitteilung",
    "auszeichnung",
    "partnerschaft",
    "werbung",
]

# 强制排除词：命中即过滤（与工业语境无关）
HARD_EXCLUDE_NOISE_KEYWORDS = [
    "livestream",
    "live stream",
    "webinar",
    "podcast episode",
    "event recap",
    "conference recap",
    "expo highlights",
    "summit highlights",
    "register now",
    "save the date",
    "meet us at",
    "join us at",
    # Product tutorials / how-to videos (not news)
    "how to use",          # e.g. "How to use Device Libraries with FactoryTalk View"
    "armorblock",          # Rockwell product manual content, not news
    # Explicit recurring noisy titles/topics
    "news about mtp",
    "mtp",
    "device libraries - overview",
    "looking back on a successful sps 2025",
    "breaking the encryption: analyzing the automationdirect click plus plc protocol",
    "power device library overview",
    "besuchen",
    "pressemitteilungen",
    "pressekontakt",
    "software package for energy-efficient and sustainable building operation",
    "celebrating",
    "built by us. driven by you",
]

# 降权词：命中后降低分数，但不直接过滤
DOWNWEIGHT_NOISE_KEYWORDS = [
    "software package",
    "make a sequence",
    # Tutorial / demo style (usually low news value)
    "demo",
    "walkthrough",
    "step by step",
    "quick start",
    "getting started",
    "how-to",
    "how to",
    "tutorial",
    # Version/update notes without clear AI deployment context
    "release notes",
    "version update",
    "feature update",
    "patch notes",
    # Event / exhibition promotion
    "booth",
    "hall",
    "visit us",
    "join our booth",
    "expo recap",
    "trade fair recap",
    # Brand / PR style
    "company announcement",
    "corporate update",
    "brand story",
    "customer testimonial",
    # Generic trend / thought leadership wording
    "future of",
    "industry trends",
    "top trends",
    "insights",
    "thought leadership",
    # Weak-signal video wording
    "no subtitles",
    "teaser",
    "trailer",
    "highlights only",
    # German common low-value wording
    "einfuehrung",
    "ueberblick",
    "rueckblick",
    "veranstaltungsbericht",
    "kundenstory",
    # Chinese common low-value wording
    "发布会",
    "活动回顾",
    "参展",
    "品牌故事",
    "功能介绍",
    "教程",
    "上手指南",
]

# Universal Robots 品牌宣传组合词（仅组合触发硬过滤）
UNIVERSAL_ROBOTS_PROMO_KEYWORDS = [
    "celebrating",
    "built by us. driven by you",
]

# 工业场景语境词：用于理论负向词的共现豁免（命中则降权，不直接过滤）
INDUSTRY_CONTEXT_KEYWORDS = [
    "manufacturing",
    "factory",
    "production line",
    "shopfloor",
    "plant",
    "plc",
    "mes",
    "scada",
    "hmi",
    "opc ua",
    "oee",
    "condition monitoring",
    "predictive maintenance",
    "asset performance",
    "equipment",
    "robot cell",
    "industrial robot",
    "quality inspection",
    "defect detection",
    "digital twin",
    "industrie 4.0",
    "instandhaltung",
    "fertigung",
    "produktionslinie",
]


# --- Trusted Source Domains Whitelist (来源域名白名单) ---
# --------------------------------------------------------
# 命中以下域名的文章直接获得最低通过分数，跳过关键词阈值检查。
# 适用于已知高质量、垂直领域的来源（如 plattform-i40.de、ifr.org）。
# 这些来源发布的内容几乎都与工业 AI/自动化主题相关，关键词命中率天然较低
# （如缩写词 AAS、标题为活动名称等）。
# 注意：白名单文章仍会参与 LLM Cloud 二次校验（不跳过 LLM 层）。
TRUSTED_SOURCE_DOMAINS: list[str] = [
    "plattform-i40.de",        # Plattform Industrie 4.0 (policy/AAS/Manufacturing-X)
    "ifr.org",                 # International Federation of Robotics
    "ipa.fraunhofer.de",       # Fraunhofer IPA (manufacturing research)
    "dfki.de",                 # DFKI (German AI institute)
    "simplan.de",              # SimPlan (simulation consultancy)
    "augury.com",              # Augury (predictive maintenance)
    "nozominetworks.com",      # Nozomi Networks (OT/ICS cybersecurity)
    "dragos.com",              # Dragos (OT cybersecurity)
    "bosch.com",               # Bosch (manufacturing AI/IoT/industry stories)
]

# --- Recipient Profiles (Multi-Audience) (多受众画像配置) ---
# ------------------------------------------------------------
@dataclass
class RecipientProfile:
    """
    接收者画像配置
    定义不同的用户群体，以发送不同风格的日报。
    """
    name: str              # 画像名称 (e.g. "Student Group")
    email: str             # 接收邮箱 (Recipient email)
    language: str          # 语言偏好 ("zh", "de")
    persona: str           # 角色设定 ("student", "technician") - 决定了邮件模板和分析侧重点
    delivery_channel: str  # 投递渠道 ("email", "notion", "both")
    focus_keywords: list[str]  # 关注关键词 (Keywords to highlight)


RECIPIENT_PROFILES = [
    RecipientProfile(
        name="Student (Simulation)",
        email=EMAIL_TO,  # Default to env var for now
        language="en",
        persona="student",
        delivery_channel="email",
        focus_keywords=["Simulation", "AI", "Python", "Job", "Thesis"],
    ),
    RecipientProfile(
        name="Technician (Maintenance)",
        email=EMAIL_TO,  # 默认只发给自己审核；审核通过后用 --forward 转发至 EXTERNAL_RECIPIENTS
        language="de",  # German localization
        persona="technician",
        delivery_channel="email",
        focus_keywords=TECHNICIAN_KEYWORDS,
    ),
]


def validate_config(mode: str, mock: bool = False) -> tuple[bool, list[str]]:
    """
    验证运行时配置 (Validate Runtime Config).
    
    Args:
        mode: 运行模式 "email", "markdown", "both", or "notion"
        mock: 是否为模拟模式 (Mock mode) - 模拟模式下不检查 LLM API Key
        
    Returns:
        (bool, list[str]): 验证是否通过, 以及错误信息列表
    """
    errors: list[str] = []

    if mode in ("email", "both"):
        if not SMTP_HOST:
            errors.append("SMTP_HOST is required for email output (邮件发送需要 SMTP_HOST)")
        if not SMTP_USER:
            errors.append("SMTP_USER is required for email output (邮件发送需要 SMTP_USER)")
        if not SMTP_PASS:
            errors.append("SMTP_PASS is required for email output (邮件发送需要 SMTP_PASS)")
        if not EMAIL_TO:
            errors.append("EMAIL_TO is required for email output (邮件发送需要 EMAIL_TO)")

    if mode in ("notion", "both"):
        if not NOTION_API_KEY:
            errors.append("NOTION_API_KEY is required for notion output (Notion 需要 API Key)")
        if not NOTION_DATABASE_ID:
            errors.append("NOTION_DATABASE_ID is required for notion output (Notion 需要 Database ID)")

    # Only validate model provider when real analysis is enabled.
    if not mock and not LLM_API_KEY:
        errors.append("Model API key is required when mock mode is disabled (非 Mock 模式需要 LLM API Key)")

    if IS_CI:
        logger.info(
            "[CONFIG] ci=%s provider=%s smtp_user=%s notion=%s",
            IS_CI,
            API_PROVIDER,
            bool(SMTP_USER),
            bool(NOTION_API_KEY and NOTION_DATABASE_ID),
        )

    return len(errors) == 0, errors


# --- Data Source Definitions (数据源定义) ---
# -------------------------------------------
@dataclass
class DataSource:
    """
    数据源配置模型
    """
    name: str              # 数据源名称
    url: str               # URL 地址 (RSS feed 或 网页链接)
    source_type: str       # 抓取类型 ("rss", "web", "dynamic")
    language: str          # 内容语言 ("de", "en", "zh")
    category: str          # 类别 ("research", "industry", "policy", "social")
    priority: int = 1      # 优先级 (1=Standard, 2=High, 3=Critical)


DATA_SOURCES: list[DataSource] = [
    # --- 1. German Powerhouse (Critical) (德国核心工业源) ---
    DataSource(
        name="Plattform Industrie 4.0",
        url="https://www.plattform-i40.de/",
        source_type="web",
        language="de",
        category="policy",
        priority=1,
    ),
    DataSource(
        name="Fraunhofer IPA Press",
        url="https://www.ipa.fraunhofer.de/de/presse/presseinformationen.html",
        source_type="web",
        language="de",
        category="research",
        priority=3,
    ),
    DataSource(
        name="DFKI News",
        url="https://www.dfki.de/web/news-media/presse",
        source_type="web",
        language="de",
        category="research",
        priority=3,
    ),
    DataSource(
        name="TUM fml (Logistics)",
        url="https://www.mec.ed.tum.de/en/fml/cover-page/",
        source_type="web",
        language="en",
        category="research",
        priority=3,
    ),

    # --- 2. Industry Leaders & Specialized (High) (行业领袖与垂直媒体) ---
    DataSource(
        name="SimPlan Blog/News",
        url="https://www.simplan.de/en/news/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="VDI Nachrichten Tech",
        url="https://www.vdi-nachrichten.com/technik/",
        source_type="web",
        language="de",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="de:hub Smart Systems",
        url="https://www.de-hub.de/en/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="ABB Robotics News",
        url="https://new.abb.com/news",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Rockwell Automation Blog",
        url="https://www.rockwellautomation.com/en-us/company/news/blogs.html",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Bosch Stories (Manufacturing/AI)",
        url="https://www.bosch.com/stories/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # --- 2b. China Industrial AI Incremental Sources (中文增量来源) ---
    DataSource(
        name="36Kr AI",
        url="https://www.36kr.com/information/AI",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Jiqizhixin",
        url="https://www.jiqizhixin.com/",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Jazzyear (甲子光年)",
        url="https://www.jazzyear.com/",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="MIIT News",
        url="https://www.miit.gov.cn/xwdt/gxdt/",
        source_type="web",
        language="zh",
        category="policy",
        priority=2,
    ),
    # --- 2c. Germany Automotive / Semiconductors / China Robotics (增量扩展) ---
    DataSource(
        name="Volkswagen Group Newsroom",
        url="https://www.volkswagen-group.com/en/news",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="BMW Group PressClub",
        url="https://www.press.bmwgroup.com/global",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Mercedes-Benz Group Media",
        url="https://media.mercedes-benz.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Automobilwoche",
        url="https://www.automobilwoche.de/",
        source_type="web",
        language="de",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="VDA News",
        url="https://www.vda.de/de/presse/Pressemeldungen",
        source_type="web",
        language="de",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Infineon News",
        url="https://www.infineon.com/cms/en/about-infineon/press/press-releases/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="STMicroelectronics Newsroom",
        url="https://newsroom.st.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="SemiEngineering",
        url="https://semiengineering.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Estun Robotics News",
        url="https://www.estun.com/?list/29.html",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Siasun News",
        url="https://www.siasun.com/index.php?m=content&c=index&a=lists&catid=16",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Inovance News",
        url="https://www.inovance.com/cn/news",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Hikrobot News",
        url="https://www.hikrobotics.com/cn/news",
        source_type="web",
        language="zh",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Robot-Forum China News",
        url="https://www.robot-forum.com/",
        source_type="web",
        language="zh",
        category="industry",
        priority=1,
    ),
    # --- 2d. Domain-Oriented Expansion (固定 6 大领域 + 工厂 4 子类) ---
    # Factory / 子类1: 设计与研发 (Design & R&D)
    DataSource(
        name="Siemens Software Blog (R&D)",
        url="https://blogs.sw.siemens.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Factory / 子类2: 生产与工艺优化 (Production & Process Optimization)
    DataSource(
        name="Manufacturing Digital",
        url="https://manufacturingdigital.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Factory / 子类3: 质量检测与缺陷分析 (Quality & Defect Analytics)
    DataSource(
        name="Cognex Blog",
        url="https://www.cognex.com/blogs",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Factory / 子类4: 设备运维与预测性维护 (Asset Ops & Predictive Maintenance)
    DataSource(
        name="Augury Blog",
        url="https://www.augury.com/blog/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Fluke Reliability Blog",
        url="https://reliability.fluke.com/blog/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Robotics
    DataSource(
        name="IFR Press Releases",
        url="https://ifr.org/ifr-press-releases",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="The Robot Report",
        url="https://www.therobotreport.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Automotive
    DataSource(
        name="Automotive World",
        url="https://www.automotiveworld.com/news-releases/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Supply Chain
    DataSource(
        name="SupplyChainBrain",
        url="https://www.supplychainbrain.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Logistics Management",
        url="https://www.logisticsmgmt.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Energy
    DataSource(
        name="Energy Storage News",
        url="https://www.energy-storage.news/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="pv magazine Industry",
        url="https://www.pv-magazine.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    # Cybersecurity
    DataSource(
        name="CISA ICS Advisories",
        url="https://www.cisa.gov/news-events/cybersecurity-advisories",
        source_type="web",
        language="en",
        category="policy",
        priority=2,
    ),
    DataSource(
        name="Nozomi Networks Blog",
        url="https://www.nozominetworks.com/blog",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Dragos Blog",
        url="https://www.dragos.com/blog/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),

    # --- 3. Global Academic & Dynamic (Mixed) (全球学术与动态源) ---
    DataSource(
        name="arXiv cs.AI (Simulation/RL)",
        url="https://rss.arxiv.org/rss/cs.AI",
        source_type="rss",
        language="en",
        category="research",
        priority=2,
    ),
    DataSource(
        name="arXiv cs.SY (Systems)",
        url="https://rss.arxiv.org/rss/cs.SY",
        source_type="rss",
        language="en",
        category="research",
        priority=2,
    ),
    # --- 3b. YouTube Whitelist via Channel RSS (工业频道白名单) ---
    DataSource(
        name="YouTube RSS: Siemens Knowledge Hub",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCaEEm-0s0x3MHg9jzFcHuQQ",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Siemens",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCzFihlQ45oSUuxotAm6w0KA",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: ABB Robotics",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCM_CsBtYQd5zVuYdwmNpT6g",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Rockwell Automation",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UC0q6j_EisHf1o_olWCvUHdA",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Schneider Electric",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCnpqjEw2RHDBNVGDe8pI7tw",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Bosch Rexroth",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCr9G5B3I3iiPUk-bsQcA1lg",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Beckhoff Automation",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCzXmGvm1ami9yKhEcbREdaQ",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Universal Robots",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCM09iVHDc416V8qLj-qhcWQ",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: FANUC America",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UC1FuphciagC13Oz__5UPSYw",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: NVIDIA Omniverse",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCSKUoczbGAcMld7HjpCR8OA",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Hexagon MI",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCaWe8GGxY3M7ACgdH1pfFuw",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: IIoT World",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCv7XrDJAwAPpaZOgpsyLG8A",
        source_type="rss",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Fraunhofer IPA",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCLiDvwE91B9zF015Psf_xdA",
        source_type="rss",
        language="de",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="YouTube RSS: Schneider Electric Deutschland",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCVPf33n1Mr9gQL9clrxj2fQ",
        source_type="rss",
        language="de",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Handelsblatt Tech",
        url="https://www.handelsblatt.com/technik/",
        source_type="dynamic",
        language="de",
        category="industry",
        priority=1,
    ),
]
