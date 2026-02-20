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

# YouTube API Key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

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

def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# --- Industry Context Gating (工业语境门槛) ---
# ---------------------------------------------
INDUSTRY_CONTEXT_KEYWORDS = [
    "industrial",
    "manufacturing",
    "factory",
    "shopfloor",
    "production line",
    "production",
    "plant",
    "equipment",
    "machine",
    "robot",
    "automation",
    "maintenance",
    "predictive maintenance",
    "plc",
    "sps",
    "mes",
    "scada",
    "oee",
    "iiot",
    "iot",
    "opc ua",
    "warehouse",
    "supply chain",
    "industrie 4.0",
    "industry 4.0",
    "fertigung",
    "produktion",
    "instandhaltung",
    "anlagen",
    "automotive",
    "vehicle",
    "oem",
    "tier 1",
    "ev",
    "battery production",
    "battery line",
    "digital factory",
    "industrial internet",
    "embodied ai",
    "cobot",
    "汽车",
    "汽车制造",
    "主机厂",
    "整车厂",
    "产线",
    "锂电产线",
    "动力电池",
    "数字工厂",
    "工业互联网",
    "机器视觉",
    "协作机器人",
    "具身智能",
    "总装",
    "焊装",
    "冲压",
    "涂装",
]

THEORY_ONLY_RISK_KEYWORDS = [
    "hypergraph",
    "theorem",
    "proof",
    "formal logic",
    "meta synthesis",
    "meta-synthesis",
    "reasoning benchmark",
    "corridor traffic signal control",
    "traffic signal control",
    "reinforcement learning",
    "deep reinforcement learning",
    "multi-agent",
    "multi agent",
    "marl",
]

# Keywords that should score only when industrial context is present.
THEORY_CONTEXT_DEPENDENT_KEYWORDS = [
    "Reinforcement Learning",
    "Deep Reinforcement Learning",
    "Multi-Agent System",
    "Adaptive Control",
    "MPC",
    "Reinforcement Learning for Scheduling",
]

STRICT_INDUSTRY_CONTEXT_GATING = _env_flag("STRICT_INDUSTRY_CONTEXT_GATING", "true")
FALLBACK_REQUIRE_INDUSTRY_CONTEXT = _env_flag("FALLBACK_REQUIRE_INDUSTRY_CONTEXT", "true")

PRIORITY_INDUSTRIAL_SOURCES = [
    "YouTube: Industrial AI (US)",
    "YouTube: Industrial AI (DE)",
    "SimPlan Blog/News",
    "ABB Robotics News",
    "Rockwell Automation Blog",
    "Siemens Industrial Copilot",
    "NVIDIA Omniverse Blog",
    "Google Cloud Manufacturing Blog",
    "Manufacturing.net",
    "VDI Nachrichten Tech",
    "Handelsblatt",
    "Fraunhofer IPA Press",
    "DFKI News",
    "Volkswagen Group Newsroom",
    "BMW Group PressClub",
    "Mercedes-Benz Group Media",
    "Automotive News Europe",
    "SAE International News",
    "36Kr AI",
    "Jiqizhixin",
    "Gaogong Robotics",
    "Jazzyear (甲子光年)",
    "MIIT News",
    "CAICT News",
    "BYD Newsroom",
]

# RSS/Web source prioritization:
# - default: prioritize whitelist first, then backfill others.
# - set RSS_WEB_PRIORITY_ONLY=true to scrape only whitelist sources.
RSS_WEB_PRIORITY_SOURCES = [
    "arXiv cs.AI (Simulation/RL)",
    "arXiv cs.SY (Systems)",
    "Fraunhofer IPA Press",
    "DFKI News",
    "SimPlan Blog/News",
    "VDI Nachrichten Tech",
    "Plattform Industrie 4.0",
    "Manufacturing.net",
    "NVIDIA Omniverse Blog",
    "Google Cloud Manufacturing Blog",
    "Handelsblatt Tech",
    "Volkswagen Group Newsroom",
    "BMW Group PressClub",
    "Mercedes-Benz Group Media",
    "Automotive News Europe",
    "SAE International News",
    "36Kr AI",
    "Jiqizhixin",
    "Gaogong Robotics",
    "Jazzyear (甲子光年)",
    "MIIT News",
    "CAICT News",
    "BYD Newsroom",
]
RSS_WEB_PRIORITY_ONLY = _env_flag("RSS_WEB_PRIORITY_ONLY", "false")

# --- YouTube Focus Channels (优先频道白名单) ---
# ----------------------------------------------
YOUTUBE_FOCUS_CHANNELS_BY_REGION: dict[str, list[str]] = {
    "US": [
        "UCaEEm-0s0x3MHg9jzFcHuQQ",  # Siemens Knowledge Hub
        "UCzFihlQ45oSUuxotAm6w0KA",  # siemens
        "UCM_CsBtYQd5zVuYdwmNpT6g",  # ABB Robotics
        "UC0q6j_EisHf1o_olWCvUHdA",  # Rockwell Automation
        "UCnpqjEw2RHDBNVGDe8pI7tw",  # Schneider Electric
        "UCr9G5B3I3iiPUk-bsQcA1lg",  # Bosch Rexroth
        "UCzXmGvm1ami9yKhEcbREdaQ",  # Beckhoff Automation
        "UCM09iVHDc416V8qLj-qhcWQ",  # Universal Robots
        "UC1FuphciagC13Oz__5UPSYw",  # FANUC America Corporation
        "UCSKUoczbGAcMld7HjpCR8OA",  # NVIDIA Omniverse
        "UCaWe8GGxY3M7ACgdH1pfFuw",  # Hexagon Manufacturing Intelligence
        "UCv7XrDJAwAPpaZOgpsyLG8A",  # IIoT World
    ],
    "DE": [
        "UCLiDvwE91B9zF015Psf_xdA",  # FraunhoferIPA
        "UCoEBqeN3sltnn4tkWBRot0w",  # Beckhoff Automation Deutschland
        "UCVPf33n1Mr9gQL9clrxj2fQ",  # Schneider Electric Deutschland
        "UCaEEm-0s0x3MHg9jzFcHuQQ",  # Siemens Knowledge Hub
    ],
}


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
    "Supply Chain AI",
    "Supply Chain Optimization",
    "Demand Planning",
    "Supply Planning",
    "Inventory Optimization",
    "Replenishment Planning",
    "Procurement Optimization",
    "Production Scheduling",
    "Finite Scheduling",
    "APS",
    "MES Integration",
    "Warehouse Automation",
    "Intralogistics",
    "Material Flow Optimization",
    "Operation Research",
    "Prescriptive Analytics",
    "Synthetic Data",
    "Factory Copilot",
    "Industrial GenAI",
    "Lieferkettenoptimierung",
    "Bedarfsprognose",
    "Bestandsoptimierung",
    "Produktionsplanung",
    "Feinplanung",
    "Intralogistik",
    "Materialflussoptimierung",
    "Automotive AI",
    "AI in Automotive Manufacturing",
    "Battery Manufacturing AI",
    "Software-defined Vehicle Manufacturing",
    "智能制造",
    "工业人工智能",
    "工业AI",
    "数字工厂",
    "工业互联网",
    "机器视觉",
    "协作机器人",
    "具身智能",
    "锂电产线",
    "动力电池制造",
    "汽车制造数字化",
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
    "CMMS",
    "EAM",
    "HMI",
    "OPC UA",
    "ISA-95",
    "SPC",
    "Root Cause Analysis",
    "Downtime",
    "MTBF",
    "MTTR",
    "Condition-based Maintenance",
    "Predictive Maintenance",
    "Line Balancing",
    "Cycle Time",
    "Throughput",
    "WIP",
    "Scheduling",
    "Dispatching",
    "Andon",
    "SMED",
    "TPM",
    "Quality Inspection",
    "Defect Detection",
    "Traceability",
    "Batch Tracking",
    "Wareneingang",
    "Schichtplanung",
    "Anlagenstillstand",
    "Durchsatz",
    "Rüstzeit",
    "Anomaly Detection",
    "车身焊装",
    "总装线",
    "电池装配",
    "视觉质检",
    "设备稼动率",
    "良率",
    "换型",
    "节拍",
    "协作机器人",
    "AGV",
    "AMR",
    "边缘计算",
    "数字孪生产线",
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
    "Supply Chain",
    "Logistics",
    "Warehouse",
    "Inventory",
    "Replenishment",
    "Procurement",
    "S&OP",
    "IBP",
    "Demand Sensing",
    "Forecast Accuracy",
    "Safety Stock",
    "Order Fulfillment",
    "Route Optimization",
    "Last Mile",
    "Production Planning",
    "Scheduling Optimization",
    "Constraint-based Scheduling",
    "Manufacturing Execution",
    "Shop Floor",
    "Digital Thread",
    "Digital Factory",
    "CPS",
    "Reinforcement Learning for Scheduling",
    "MPC",
    "Simulation Optimization",
    "Synthetic Data Generation",
    "Generative AI for Manufacturing",
    "Automotive",
    "Automotive Manufacturing",
    "Vehicle Production",
    "OEM",
    "Tier 1 Supplier",
    "Battery Pack",
    "Cell-to-Pack",
    "E-Mobility Manufacturing",
    "智能工厂",
    "数字化车间",
    "汽车工厂",
    "工业机器人",
    "机器人工作站",
    "视觉检测",
    "缺陷检测",
    "工业大模型",
    "边缘AI",
    "产线优化",
    "预测性维护",
    "工厂排产",
    "柔性制造",
    "离散制造",
    "工业软件",
    "工业控制",
    "工控安全",
    "工业质检",
    "仓储自动化",
    "物流机器人",
    "新能源汽车制造",
    "电池制造",
    "智能焊接",
    "设备健康管理",
    "Lieferkette",
    "Bestandsmanagement",
    "Nachschub",
    "Beschaffung",
    "Fertigungsplanung",
    "Schichtbetrieb",
    "Qualitätsprüfung",
    "Routenoptimierung",
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
        name="Technician",
        email=",".join(
            [
                e
                for e in [
                    EMAIL_TO,
                    "max@max-lang.de",
                    "reinhard.lang.mak@googlemail.com",
                ]
                if e
            ]
        ),
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
    source_type: str       # 抓取类型 ("rss", "web", "dynamic", "youtube")
    language: str          # 内容语言 ("de", "en", "zh")
    category: str          # 类别 ("research", "industry", "policy", "social")
    priority: int = 1      # 优先级 (1=Standard, 2=High, 3=Critical)
    region_code: str = ""  # 可选: YouTube regionCode (e.g. "US", "DE")


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
    DataSource(
        name="AWS Supply Chain Blog",
        url="https://aws.amazon.com/blogs/supply-chain/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="SAP Supply Chain News",
        url="https://news.sap.com/tag/supply-chain/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Oracle SCM",
        url="https://www.oracle.com/scm/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Siemens Industrial Copilot",
        url="https://press.siemens.com/global/en/search?query=industrial%20copilot",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="Google Cloud Manufacturing Blog",
        url="https://cloud.google.com/blog/topics/manufacturing",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="StartUs Insights Manufacturing",
        url="https://www.startus-insights.com/innovators-guide/tag/manufacturing/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="AnyLogic Blog",
        url="https://www.anylogic.com/blog/",
        source_type="web",
        language="en",
        category="research",
        priority=2,
    ),
    DataSource(
        name="Kaggle Competitions",
        url="https://www.kaggle.com/competitions",
        source_type="web",
        language="en",
        category="research",
        priority=1,
    ),
    # --- 3. Automotive & China Incremental Layer (汽车与中国增量层) ---
    DataSource(
        name="Volkswagen Group Newsroom",
        url="https://www.volkswagen-group.com/en/news-stories",
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
        name="Automotive News Europe",
        url="https://europe.autonews.com/",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
    DataSource(
        name="SAE International News",
        url="https://www.sae.org/news",
        source_type="web",
        language="en",
        category="industry",
        priority=2,
    ),
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
        name="Gaogong Robotics",
        url="https://www.gg-robot.com/",
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
    DataSource(
        name="CAICT News",
        url="https://www.caict.ac.cn/kxyj/qwfb/",
        source_type="web",
        language="zh",
        category="research",
        priority=2,
    ),
    DataSource(
        name="BYD Newsroom",
        url="https://www.bydglobal.com/cn/news/",
        source_type="web",
        language="zh",
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
    DataSource(
        name="Handelsblatt Tech",
        url="https://www.handelsblatt.com/technik/",
        source_type="dynamic",
        language="de",
        category="industry",
        priority=1,
    ),
    # --- 4. YouTube Channels (Video) ---
    DataSource(
        name="YouTube: Industrial AI (US)",
        url='("industrial ai" OR "ai in manufacturing" OR "smart manufacturing" OR "industry 4.0" OR "digital twin" OR "factory automation" OR "predictive maintenance" OR "industrial robotics" OR "ot cybersecurity" OR "industrial iot") -job -hiring -career -course',
        source_type="youtube",
        language="en",
        category="industry",
        priority=2,
        region_code="US",
    ),
    DataSource(
        name="YouTube: Industrial AI (DE)",
        url='("industrie 4.0" OR "industrielle ki" OR "digitale zwillinge" OR "fabrikautomatisierung" OR "vorausschauende wartung" OR "industrierobotik" OR "ot-sicherheit" OR "industrial ai") -job -hiring -career -kurs',
        source_type="youtube",
        language="de",
        category="industry",
        priority=2,
        region_code="DE",
    ),
]
