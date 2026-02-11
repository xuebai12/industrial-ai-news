"""Central configuration for the Industrial AI Intelligence System."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


# --- API Config ---
# --- API Config ---
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# Determine which provider to use
# Priority: USE_LOCAL_OLLAMA > NVIDIA NIM > Moonshot > Local Ollama (Fallback)
USE_LOCAL_OLLAMA = os.getenv("USE_LOCAL_OLLAMA", "false").lower() == "true"

if USE_LOCAL_OLLAMA:
    KIMI_API_KEY = "ollama"
    KIMI_BASE_URL = "http://localhost:11434/v1"
    KIMI_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
    API_PROVIDER = "Local_Ollama"
elif NVIDIA_API_KEY and len(NVIDIA_API_KEY) > 10:  # Relaxed check (was startswith nvapi-)
    KIMI_API_KEY = NVIDIA_API_KEY
    KIMI_BASE_URL = "https://integrate.api.nvidia.com/v1"
    KIMI_MODEL = "moonshotai/kimi-k2.5"
    API_PROVIDER = "NVIDIA"
elif MOONSHOT_API_KEY and MOONSHOT_API_KEY.startswith("sk-"):
    KIMI_API_KEY = MOONSHOT_API_KEY
    KIMI_BASE_URL = "https://api.moonshot.cn/v1"
    KIMI_MODEL = "moonshot-v1-8k"
    API_PROVIDER = "Moonshot"
else:
    # Fallback to Local Ollama
    KIMI_API_KEY = "ollama"  # Ollama doesn't require a real key
    KIMI_BASE_URL = "http://localhost:11434/v1"
    KIMI_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
    API_PROVIDER = "Local_Ollama"

IS_CI = os.getenv("CI", "false").lower() == "true"

# Debug print for CI environment
if os.getenv("CI"):
    print(f"[DEBUG] CI Mode: {IS_CI}")
    print(f"[DEBUG] API Provider: {API_PROVIDER}")
    print(f"[DEBUG] API Key present: {bool(KIMI_API_KEY)}")
    print(f"[DEBUG] SMTP Host: {os.getenv('SMTP_HOST')}")
    print(f"[DEBUG] SMTP User present: {bool(os.getenv('SMTP_USER'))}")

# --- Email Config ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")

_smtp_port = os.getenv("SMTP_PORT")
SMTP_PORT = int(_smtp_port) if _smtp_port else 587

SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")

# --- Notion Config ---
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# --- Pipeline Config ---
_max_articles = os.getenv("MAX_ARTICLES_PER_SOURCE")
MAX_ARTICLES_PER_SOURCE = int(_max_articles) if _max_articles else 20

_relevance_threshold = os.getenv("RELEVANCE_THRESHOLD")
RELEVANCE_THRESHOLD = int(_relevance_threshold) if _relevance_threshold else 1


# --- Data Source Definitions ---
@dataclass
class DataSource:
    name: str
    url: str
    source_type: str  # "rss", "web", "dynamic"
    language: str  # "de", "en", "zh"
    category: str  # "research", "industry", "policy", "social"
    priority: int = 1  # 1=Standard, 2=High, 3=Critical


DATA_SOURCES: list[DataSource] = [
    # --- 1. German Powerhouse (Critical) ---
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

    # --- 2. Industry Leaders & Specialized (High) ---
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

    # --- 3. Global Academic & Dynamic (Standard) ---
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


# --- Keyword Scoring Rules (Knowledge Graph) ---
HIGH_PRIORITY_KEYWORDS = [
    # Core DE terms
    "Ablaufsimulation",       # Process simulation (more precise than "Simulation")
    "Fertigungssteuerung",    # Production control
    "Virtuelle Inbetriebnahme", # Virtual Commissioning
    "VIBN",
    "KI-gestützte Optimierung", # AI-supported optimization
    "KI-gestützte Fertigung",   # AI-supported manufacturing
    "Diskrete Ereignissimulation", # Discrete Event Simulation
    "Asset Administration Shell",  # AAS
    "Verwaltungsschale",           # AAS (German)

    # Core EN terms
    "Discrete Event Simulation",
    "Digital Twin",
    "Digitaler Zwilling",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "Automatisierungstechnik",
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
]
