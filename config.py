"""Central configuration for the Industrial AI Intelligence System."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


# --- API Config ---
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
# Use Moonshot v1 8k or 32k for longer context if needed
MOONSHOT_MODEL = "moonshot-v1-8k"

# --- Email Config ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")

# --- Pipeline Config ---
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "20"))
RELEVANCE_THRESHOLD = int(os.getenv("RELEVANCE_THRESHOLD", "1"))  # Reduced threshold to catch more articles
IS_CI = os.getenv("CI", "false").lower() == "true"


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
