"""Central configuration for the Industrial AI Intelligence System."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# --- API Config ---
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
MOONSHOT_MODEL = "moonshot-v1-8k"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- Email Config ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")

# --- Pipeline Config ---
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "20"))
RELEVANCE_THRESHOLD = int(os.getenv("RELEVANCE_THRESHOLD", "1"))
IS_CI = os.getenv("CI", "false").lower() == "true"


# --- Data Source Definitions ---
@dataclass
class DataSource:
    name: str
    url: str
    source_type: str  # "rss", "web", "dynamic"
    language: str  # "de", "en", "zh"
    category: str  # "research", "industry", "policy", "social"
    priority: int = 0  # higher = more important


DATA_SOURCES: list[DataSource] = [
    # --- German Focus ---
    DataSource(
        name="Fraunhofer IPA",
        url="https://www.ipa.fraunhofer.de/de/presse/presseinformationen.rss",
        source_type="rss",
        language="de",
        category="research",
        priority=2,
    ),
    DataSource(
        name="Fraunhofer IAPT",
        url="https://www.2.iapt.fraunhofer.de/en/press.rss",
        source_type="rss",
        language="en",
        category="research",
        priority=2,
    ),
    DataSource(
        name="Plattform Industrie 4.0",
        url="https://www.plattform-i40.de/IP/Navigation/EN/Home/home.html",
        source_type="web",
        language="de",
        category="policy",
        priority=1,
    ),
    DataSource(
        name="Handelsblatt Industry",
        url="https://www.handelsblatt.com/technik/",
        source_type="dynamic",
        language="de",
        category="industry",
        priority=1,
    ),
    # --- Global Horizon ---
    DataSource(
        name="arXiv cs.AI",
        url="https://rss.arxiv.org/rss/cs.AI",
        source_type="rss",
        language="en",
        category="research",
        priority=2,
    ),
    DataSource(
        name="arXiv cs.SY",
        url="https://rss.arxiv.org/rss/cs.SY",
        source_type="rss",
        language="en",
        category="research",
        priority=1,
    ),
    DataSource(
        name="Manufacturing Tomorrow",
        url="https://www.manufacturingtomorrow.com/rss/articles",
        source_type="rss",
        language="en",
        category="industry",
        priority=1,
    ),
    DataSource(
        name="Twitter #DigitalTwin (via RSSHub)",
        url="https://rsshub.app/twitter/hashtag/DigitalTwin",
        source_type="rss",
        language="en",
        category="social",
        priority=0,
    ),
]


# --- Keyword Scoring Rules ---
HIGH_PRIORITY_KEYWORDS = [
    "Discrete Event Simulation",
    "Ablaufsimulation",
    "离散事件仿真",
    "DES model",
    "discrete-event",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "Digital Twin",
    "Digitaler Zwilling",
    "数字孪生",
    "AI-driven",
    "Machine Learning",
    "Reinforcement Learning",
    "Industrie 4.0",
    "Industry 4.0",
    "工业4.0",
    "Smart Factory",
    "intelligente Fabrik",
    "simulation",
    "Simulation",
    "仿真",
]
