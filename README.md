# 🏭 Industrial AI News Pipeline | 工业 AI 每日情报流

> **English**: Automated intelligence pipeline that scrapes, filters, and analyzes Industrial AI news from 11 German & global sources — powered by local LLM (Ollama) and delivered daily via email with personalized views (Student/Technician).
>
> **中文**: 自动化情报流水线，从 11 个德国及全球源抓取、过滤并分析工业 AI 新闻 — 由本地 LLM (Ollama) 驱动，每日通过邮件发送个性化（学生/技术员）双视角摘要。

## 🌟 Key Features | 核心功能

1. **Dual-View Analysis (双视角分析)**:
   - **Student View (ZH)**: Simple explanation identifying learning points & tool stacks. (学生视角：通俗解读，关注学习点与工具栈)
   - **Technician View (DE)**: Professional German analysis focusing on Maintenance, PLC, and OEE. (技术员视角：德语专业分析，关注维护、PLC 与 OEE)

2. **Smart Persona Routing (智能分发)**:
   - Specific emails for **Students** (Chinese focus) vs **Technicians** (German focus).
   - Auto-tagging based on keywords like `SPS`, `TIA Portal` (+3 score).
   - Subject prefixes are standardized as `[Student]` / `[Technician]` (no profile-name suffixes such as "Maintenance").
   - Technician daily digest is sent to both configured `EMAIL_TO` and `Max Lang <max@max-lang.de>`.

3. **Privacy First (隐私优先)**:
   - 100% Local execution supported via **Ollama**. (支持 100% 本地运行)

## 🚀 Workflow | 工作流程

```mermaid
graph LR
    A[📡 Sources] --> B[🔎 Filter & Tag]
    B --> C[🧠 LLM Analysis]
    C --> D[🔀 Persona Router]
    D --> E[📧 Student Email (ZH)]
    D --> F[📧 Technician Email (DE)]
```

1. **Scrape**: 11 Premium sources (RSS, Web, Dynamic).
2. **Filter & Tag**:
   - `+3` Score: Technician Keywords (`Instandhaltung`, `TIA Portal`) → Tag: `Technician`
   - `+2` Score: High Value (`Digital Twin`, `Simulation`) → Tag: `Student`
3. **Analyze**: LLM generates `title_de`, `summary_de`, `technician_analysis_de`, and `simple_explanation`.
4. **Deliver**: Routes content to configured profiles in `config.py`.

## 🛠️ Tech Stack | 技术栈

| Layer | Technology |
|---|---|
| **Language** | Python 3.11 |
| **Scraping** | `requests`, `BeautifulSoup`, `feedparser`, `Playwright` |
| **LLM** | **Ollama (Local)** / NVIDIA NIM |
| **Analysis** | Dual-View Prompt Engineering (ZH/DE) |
| **Delivery** | SMTP (Gmail), Notion API, Markdown |
| **CI/CD** | GitHub Actions, Pre-commit codespaces |

## 📊 Data Sources (11 Sources) | 数据源一览

The pipeline scrapes **11 premium sources** covering Policy, Research, and Industry.
(本系统覆盖 **11 个优质数据源**，囊括政策、科研与产业界。)

| Source (名称) | Type (类型) | Language | Focus Area (关注领域) | Priority |
|---|---|---|---|---|
| **Plattform Industrie 4.0** | Web | 🇩🇪 DE | German I4.0 Policy & Standardization (德国工业 4.0 政策与标准) | ⭐⭐⭐ (Critical) |
| **Fraunhofer IPA** | Web | 🇩🇪 DE | Applied Manufacturing Research (应用制造研究) | ⭐⭐⭐ (Critical) |
| **DFKI News** | Web | 🇩🇪 DE | AI Research & Robotics (人工智能与机器人) | ⭐⭐⭐ (Critical) |
| **TUM fml (Logistics)** | Web | 🇬🇧 EN | Logistics & Material Flow (物流与物料流) | ⭐⭐⭐ (Critical) |
| **Siemens Digital** | Web | 🇬🇧 EN | Automation & TIA Portal (自动化与 TIA Portal) | ⭐⭐ (High) |
| **SimPlan Blog** | Web | 🇬🇧 EN | Simulation Consulting (仿真咨询) | ⭐⭐ (High) |
| **VDI Nachrichten** | Web | 🇩🇪 DE | German Engineering News (德国工程新闻) | ⭐⭐ (High) |
| **de:hub Smart Systems** | Web | 🇬🇧 EN | IoT & Innovation Hubs (物联网与创新中心) | ⭐⭐ (High) |
| **arXiv cs.AI** | RSS | 🇬🇧 EN | Artificial Intelligence Papers (AI 论文) | ⭐ (Standard) |
| **arXiv cs.SY** | RSS | 🇬🇧 EN | Systems & Control Theory (系统与控制理论) | ⭐ (Standard) |
| **Handelsblatt Tech** | Dynamic | 🇩🇪 DE | Business Tech News (商业技术新闻) | ⭐ (Standard) |

## 🔍 Filtering Principles | 过滤原则

The system uses a **Two-Stage Filtering Pipeline** to ensure high relevance.
(系统采用 **双重过滤流水线** 以确保内容的高度相关性。)

### Stage 1: Smart Keyword Scoring (智能关键词评分)

Articles are scored based on the presence of domain keywords.
(文章根据包含的领域关键词进行评分。)

| Score | Category | Keywords (Examples) | Action / Persona |
|:---:|---|---|---|
| **+3** | **Technician (技术员)** | `Instandhaltung` (Maintenance), `SPS/PLC`, `TIA Portal`, `OEE`, `Sicherheit` (Safety), `Störungsbehebung` (Troubleshooting) | ✅ **Keep** & Tag as `Technician` (保留并标记为技术员) |
| **+2** | **Core Tech (核心技术)** | `Digital Twin`, `Ablaufsimulation`, `VIBN` (Virtual Commissioning), `Asset Administration Shell` (AAS), `Industrial AI` | ✅ **Keep** & Tag as `Student` (保留并标记为学生) |
| **+1** | **General (通用)** | `Industry 4.0`, `Smart Factory`, `Predictive Maintenance`, `AnyLogic`, `Siemens`, `Reinforcement Learning` | ⚠️ Need score ≥ 1 to pass (需总分 ≥ 1 才能通过) |

> **Threshold**: Articles with `Score >= 1` proceed to Stage 2.
> (**阈值**：总分 `>= 1` 的文章进入第二阶段。)

### Stage 2: LLM Relevance Validation (LLM 相关性校验)

(Optional / 可选)
A lightweight LLM call (Local Ollama or Cloud) verifies the context with a binary check:
(轻量级 LLM 调用进行二次确认：)

> "Is this article about industrial AI, discrete event simulation, or smart manufacturing? Reply YES or NO."

- **Parallel Execution**: Checks are run concurrently using `ThreadPoolExecutor`.
- **Configurable**: `KIMI_MAX_CONCURRENCY` controls the number of parallel threads (default: 4 for Cloud, 1 for Local).

Only articles confirmed as **"YES"** are sent for final analysis.
(只有确认为 **"YES"** 的文章才会进入最终分析。)

## 🤖 AI Analysis Environment | AI 分析环境

The core analysis is performed by a **local Large Language Model** (e.g., Kimi k2.5 via Ollama) using a specialized Prompt Engineering strategy.
(核心分析由 **本地大语言模型** 执行，采用专门的提示词工程策略。)

### System Persona (系统设定)
> **Role**: "Senior Technical Expert in German Industry 4.0, bridging OT (Automation) and IT (Data Science)."
> (**角色**: "深耕德国工业 4.0 领域的资深技术专家，连接自动化工程与数据科学。")

### Core Constraints (核心限制)
1.  **Contextual Linking (场景化链接)**: Must connect content to real tools like **Siemens TIA Portal** (OT) and **Jupyter Notebooks** (IT).
2.  **No Clichés (拒绝陈词滥调)**:
    *   **Student View**: Explain data flow (Sensor -> PLC -> Cloud).
    *   **Technician View**: Focus on Maintenance (`Instandhaltung`), Availability (`Anlagenverfügbarkeit`), and OEE.
3.  **Bilingual Alignment (双语对齐)**: Key terms must be preserved in German/English with Chinese annotations.

## 🧠 AI Analysis Output | 分析维度

Each article is analyzed into structured fields:

| Field | Description (EN) | Description (CN) |
|---|---|---|
| 🇨🇳 `title_zh` | Chinese Title | 中文标题 |
| �� `title_de` | **German Title (New)** | 德语标题 |
| 📝 `summary_zh/de` | Bilingual Summary | 双语摘要 |
| 💡 `simple_explanation` | **Student View**: Concept Simplification | **学生视角**：通俗原理解读 |
| � `technician_analysis_de` | **Technician View**: Maintenance & PLC Focus | **技术员视角**：维护与 PLC 深度分析 |
| 🛠️ `tool_stack` | Software tools (e.g. AnyLogic) | 涉及软件/工具栈 |
| 🏭 `german_context` | Industry Background | 德国产业背景 |

## 🏃 Quick Start | 快速开始

```bash
# 1. Clone & Setup
git clone https://github.com/xuebai12/industrial-ai-news.git
cd industrial-ai-news
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure Environment
cp .env.example .env
# Edit .env: Set USE_LOCAL_OLLAMA=true or provide NVIDIA_API_KEY

# 3. Configure Personas (Optional)
# Edit config.py to adjust RECIPIENT_PROFILES

# 4. Run Pipeline
python3 main.py --output email --skip-dynamic
```

### Configuration Options | 配置选项

| Option | Description |
|---|---|
| `--output email` | Send emails based on profiles. (基于画像发送邮件) |
| `--output notion` | Push to Notion database. (推送到 Notion) |
| `--mock` | Use mock data for testing. (使用模拟数据) |
| `--skip-llm-filter` | Skip LLM validation for speed. (跳过 LLM 校验) |

### Push Existing Digest to Notion

If you already have a generated digest markdown file and want to import it into Notion directly:

```bash
./.venv/bin/python push_digest_to_notion.py output/digest-2026-02-12.md --date 2026-02-12
```

### Notion Rating Feedback Loop

Pull your rated Notion entries (1-5) and generate a local optimization report:

```bash
# Step 1: fetch rated records from Notion (default lookback: 30 days)
./.venv/bin/python fetch_notion_feedback.py --days 30 --output-dir output

# Step 2: build feedback report (source/category/keyword performance)
./.venv/bin/python build_feedback_report.py --output-dir output --min-samples 3
```

Outputs:

- `output/feedback-YYYY-MM-DD.json`
- `output/feedback-report-YYYY-MM-DD.json`
- `output/feedback-report-YYYY-MM-DD.md`

## 📂 Project Structure | 项目结构

- `src/scrapers/`: Parsers for RSS and Websites.
- `src/filters/`: Keyword scoring & tagging logic.
- `src/analyzers/`: LLM Prompts & Providers (Ollama/NIM).
- `src/delivery/`: Email renderer (Jinja2) & Notion client.
- `config.py`: **Profiles**, Keywords, Sources.

## 🤝 Contribution

Running tests:
```bash
pytest
```

Running type checks:
```bash
mypy src
```
