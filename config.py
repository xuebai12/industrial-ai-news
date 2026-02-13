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
    "Ablaufsimulation",       # Process simulation (more precise than "Simulation")
    "Fertigungssteuerung",    # Production control
    "Virtuelle Inbetriebnahme", # Virtual Commissioning
    "VIBN",
    "KI-gestützte Optimierung", # AI-supported optimization
    "KI-gestützte Fertigung",   # AI-supported manufacturing
    "Diskrete Ereignissimulation", # Discrete Event Simulation
    "Asset Administration Shell",  # AAS
    "Verwaltungsschale",           # AAS (German)
    "Industrial AI",           # 工业 AI
    "Industrielle KI",         # 工业 AI (德语)
    "AI in Production",        # 生产中的 AI
    "KI in der Produktion",    # 生产中的 AI (德语)
    "Manufacturing AI",        # 制造 AI

    # Core EN terms (英语核心词)
    "Discrete Event Simulation",
    "Digital Twin",
    "Digitaler Zwilling",
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
        language="zh",
        persona="student",
        delivery_channel="email",
        focus_keywords=["Simulation", "AI", "Python", "Job", "Thesis"],
    ),
    RecipientProfile(
        name="Technician (Maintenance)",
        email=",".join([e for e in [EMAIL_TO, "max@max-lang.de"] if e]),
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
        priority=3,
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
        name="Siemens Digital Industries",
        url="https://www.siemens.com/global/en/products/automation.html",
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

    # --- 3. Global Academic & Dynamic (Standard) (全球学术与动态源) ---
    DataSource(
        name="arXiv cs.AI (Simulation/RL)",
        url="https://rss.arxiv.org/rss/cs.AI",
        source_type="rss",
        language="en",
        category="research",
        priority=1,
    ),
    DataSource(
        name="arXiv cs.SY (Systems)",
        url="https://rss.arxiv.org/rss/cs.SY",
        source_type="rss",
        language="en",
        category="research",
        priority=1,
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
