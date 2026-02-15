# 🏭 Industrial AI News Pipeline | 工业 AI 每日情报流

> **English**: Automated intelligence pipeline that scrapes, filters, and analyzes Industrial AI news from 28 German & global sources — powered by local LLM (Ollama) and delivered daily via email with personalized views (Student/Technician).
>
> **中文**: 自动化情报流水线，从 28 个德国及全球源抓取、过滤并分析工业 AI 新闻 — 由本地 LLM (Ollama) 驱动，每日通过邮件发送个性化（学生/技术员）双视角摘要。

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

1. **Scrape**: 28 Premium sources (RSS, Web, Dynamic).
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

## 📊 Data Sources (28 Sources) | 数据源一览

The pipeline currently scrapes **28 premium sources** covering Policy, Research, and Industry.
(本系统当前覆盖 **28 个优质数据源**，囊括政策、科研与产业界。)
The table below shows core examples; see `config.py` for the complete active list.
(下表展示核心示例；完整启用清单请见 `config.py`。)

| Source (名称) | Type (类型) | Language | Focus Area (关注领域) | Priority |
|---|---|---|---|---|
| **Plattform Industrie 4.0** | Web | 🇩🇪 DE | German I4.0 Policy & Standardization (德国工业 4.0 政策与标准) | ⭐⭐⭐ (Critical) |
| **Fraunhofer IPA** | Web | 🇩🇪 DE | Applied Manufacturing Research (应用制造研究) | ⭐⭐⭐ (Critical) |
| **DFKI News** | Web | 🇩🇪 DE | AI Research & Robotics (人工智能与机器人) | ⭐⭐⭐ (Critical) |
| **TUM fml (Logistics)** | Web | 🇬🇧 EN | Logistics & Material Flow (物流与物料流) | ⭐⭐⭐ (Critical) |
| **SimPlan Blog** | Web | 🇬🇧 EN | Simulation Consulting (仿真咨询) | ⭐⭐ (High) |
| **VDI Nachrichten** | Web | 🇩🇪 DE | German Engineering News (德国工程新闻) | ⭐⭐ (High) |
| **de:hub Smart Systems** | Web | 🇬🇧 EN | IoT & Innovation Hubs (物联网与创新中心) | ⭐⭐ (High) |
| **ABB Robotics News** | Web | 🇬🇧 EN | Industrial Robotics & Automation (工业机器人与自动化) | ⭐⭐ (High) |
| **Rockwell Automation Blog** | Web | 🇬🇧 EN | Factory Automation Practice (工厂自动化实践) | ⭐⭐ (High) |
| **NVIDIA Manufacturing AI Blog** | Web | 🇬🇧 EN | Industrial AI & Synthetic Data (工业 AI 与合成数据) | ⭐⭐ (High) |
| **Bosch Stories (Manufacturing/AI)** | Web | 🇬🇧 EN | Manufacturing Transformation Cases (制造业转型案例) | ⭐⭐ (High) |
| **arXiv cs.AI** | RSS | 🇬🇧 EN | Artificial Intelligence Papers (AI 论文) | ⭐ (Standard) |
| **arXiv cs.SY** | RSS | 🇬🇧 EN | Systems & Control Theory (系统与控制理论) | ⭐ (Standard) |
| **Handelsblatt Tech** | Dynamic | 🇩🇪 DE | Business Tech News (商业技术新闻) | ⭐ (Standard) |

## 🧭 Extended Discovery Scope (Last 6 Months) | 扩展搜寻范围（近6个月）

For idea discovery beyond current pipeline sources, use the following platforms with a strict recency filter.
(用于寻找可落地创意点子的扩展渠道，统一按“近 6 个月”筛选。)

| Category (类别) | Platforms (平台) | What to find (适合找什么) | Search scope (建议搜寻范围，直接照搜) |
|---|---|---|---|
| Business-suite built-in AI (业务系统内置 AI) | AWS Supply Chain / Dynamics 365 / SAP / Oracle | Procurement, inventory, planning, replenishment use cases (采购、库存、计划、补货) | `site:aws.amazon.com "supply chain" "AI" after:2025-08-14`; `site:learn.microsoft.com "Dynamics 365" "Supply Chain Copilot" after:2025-08-14`; `site:sap.com "supply chain" "AI" after:2025-08-14`; `site:oracle.com "Fusion SCM" "AI" after:2025-08-14` |
| Factory AI platforms (工厂侧 AI 平台) | Siemens Industrial Copilot / NVIDIA Omniverse / Google Manufacturing | Line optimization, maintenance, digital twins, simulation (产线优化、维护、数字孪生、仿真) | `site:nvidia.com Omniverse manufacturing AI case after:2025-08-14`; `site:siemens.com industrial copilot factory after:2025-08-14`; `site:cloud.google.com manufacturing AI after:2025-08-14`; add `predictive maintenance`, `scheduling`, `simulation` |
| Use Case Maps (案例地图) | Plattform Industrie 4.0 Map | Real SME deployments in Germany (德国中小企业真实落地案例) | Filter by industry: `automotive`, `machinery`, `chemicals`; by capability: `quality`, `energy`, `maintenance`, `logistics`; prioritize measurable outcome fields |
| Startup aggregators (初创公司聚合) | Crunchbase / StartUs Insights | New product directions and replicable pain-point solutions (新产品方向、细分痛点、可复制方案) | Crunchbase tags: `Manufacturing + AI + Supply Chain + Computer Vision + Robotics`; stages: `Seed~Series B`; regions: `DACH / US / China`; recency: last 6 months |
| Vendor blogs (软件厂商博客) | NVIDIA Industrial AI / AnyLogic Blog | Frontier approaches such as synthetic data + simulation (前沿可实现思路) | `site:nvidia.com "industrial AI" "synthetic data" after:2025-08-14`; `site:anylogic.com blog manufacturing after:2025-08-14`; prioritize posts with architecture/data-flow diagrams |
| Competitions (学术竞赛) | Kaggle / Hackathons | Real factory problem templates and reusable baselines (真实问题模板与 baseline) | Kaggle queries: `demand forecasting`, `inventory`, `routing`, `anomaly detection`; prioritize competitions from last 6 months and top-3 solution writeups |
| Professional communities (专业技术社区) | Manufacturing.net / Medium (Industrial Data Science) | Practitioner-level engineering details and Jupyter logic (一线工程细节与 Jupyter 实操) | `site:manufacturing.net AI operations after:2025-08-14`; `site:medium.com "industrial data science" "predictive maintenance" after:2025-08-14`; filter `operations`, `plant management`, `AI` |
| Open-source repos (开源仓库) | GitHub Topics / Awesome Lists | Reusable code templates, starter pipelines (可复用代码模板) | `site:github.com "supply chain" "forecasting" "python" pushed:>=2025-08-14`; `site:github.com "industrial ai" "predictive maintenance" "jupyter" pushed:>=2025-08-14` |
| Patent/standard watch (专利与标准) | Google Patents / ISO-IEC-VDI pages | Emerging technical direction and implementation constraints (技术趋势与落地边界) | `"predictive maintenance" "manufacturing" site:patents.google.com after:2025-08-14`; `site:iso.org smart manufacturing AI standard` |
| Integrator playbooks (咨询与集成商方案) | Accenture / Deloitte / Capgemini Industry Insights | ROI framing, phased rollout patterns (ROI 框架与分阶段实施方法) | `site:accenture.com manufacturing AI supply chain after:2025-08-14`; `site:deloitte.com smart factory AI case after:2025-08-14`; `site:capgemini.com manufacturing AI operations after:2025-08-14` |

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

### Delivery Policy Updates | 投递策略更新

- Per-profile minimum target (each digest): `PROFILE_ARTICLE_TARGET=5` (default).
- Repeat cooldown window: `PROFILE_REPEAT_COOLDOWN_DAYS=7` (default).
- Filtering minimum pool: `MIN_RELEVANT_ARTICLES=12` (default) to support dual-profile delivery.
- Sent history path: `output/sent_history.json` (used for cross-day anti-dup).
- Email truncation: disabled for both Student and Technician views (no forced `...` clipping for core fields).
- Low-value source guard: known evergreen/event pages from Plattform Industrie 4.0 are excluded upstream.

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
