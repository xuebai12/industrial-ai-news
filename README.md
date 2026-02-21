# Industrial AI Daily Intelligence

工业 AI 日报系统：自动抓取 -> 过滤 -> 分析 -> 按不同收件人模板发送。

## 1. 系统目标

这个项目解决三个问题：
- 信息源分散：工业 AI 新闻、论文、视频跨多个网站。
- 噪音高：大量“非 AI”或“纯理论”内容混入。
- 读者差异大：学生和技术员需要不同语言与表达方式。

系统每天运行一次，输出邮件（可选 Markdown / Notion）。

---

## 2. 流程总览

1. 抓取（Scrape）
2. 去重（Dedupe）
3. 相关性过滤（Keyword + LLM）
4. LLM 分析（多语言、多视角）
5. 分画像投递（Email / Markdown / Notion）

说明：
- 过滤通过后会先排序，再按 `--top-n` 截断进入分析（默认 20）
- 剩余候选会在邮件末尾追加“未分析但相关”的后续列表（默认再展示 20 条）

代码入口：`/Users/baixue/news/main.py`

---

## 3. 收件与发送机制

### 3.1 收件人画像

定义在：`/Users/baixue/news/config.py` -> `RECIPIENT_PROFILES`

当前主要画像：
- Student（英文）
- Technician（德文）

### 3.2 先审后发（关键）

- 默认运行：先发审核邮件到 `EMAIL_REVIEWER`（默认 `baixue243@gmail.com`）
- 审核通过后：使用 `--approve-send` 正式发给其他收件人
- 正式发送时会自动排除 reviewer，避免重复收到

相关逻辑：`/Users/baixue/news/main.py`

---

## 4. 数据来源规则（Source Rules）

来源定义在：`/Users/baixue/news/config.py` -> `DATA_SOURCES`

### 4.1 来源类型

- `web`：普通网页抓取
- `rss`：RSS 订阅
- `dynamic`：动态页面（可选跳过）
- `youtube`：YouTube 搜索与频道结果

### 4.2 来源优先级

- 通过 `priority` 字段定义重要程度
- 通过 `RSS_WEB_PRIORITY_SOURCES` 做 RSS/Web 白名单优先
- 可用 `RSS_WEB_PRIORITY_ONLY=true` 强制只抓白名单

### 4.3 当前策略重点

- 保留 DE/US 工业核心来源
- 增加 Automotive 与中国工业增量来源（媒体、机构、厂商新闻中心）
- YouTube 查询词按工业主题扩展，不只单一关键词

---

## 5. 检索主题规则（6 大领域）

定义在：`/Users/baixue/news/config.py` -> `TARGET_SEARCH_DOMAINS`

固定聚焦 6 类：
1. Factory
2. Robotics
3. Automotive
4. Supply Chain
5. Energy
6. Cybersecurity

Factory 进一步细分：
- 设计与研发
- 生产与工艺优化
- 质量检测与缺陷分析
- 设备运维与预测性维护

---

## 6. 过滤规则（Filter Rules）

核心文件：`/Users/baixue/news/src/filters/ollama_filter.py`

当前采用“关键词打分 + 可选 LLM 校验 + 最低补量”的三段式。

### 6.1 第一步：关键词打分（必走）

- `TECHNICIAN_KEYWORDS` 命中：`+3`
- `HIGH_PRIORITY_KEYWORDS` 命中：`+2`
- `MEDIUM_PRIORITY_KEYWORDS` 命中：`+1`
- 若前三类都未命中，则用 `BROAD_KEYWORDS` 做低权重召回（`+1`）
- 若命中 `TRUSTED_SOURCE_DOMAINS`，分数至少抬到 `RELEVANCE_THRESHOLD`

### 6.2 第二步：硬过滤（直接拒绝）

- 命中 `HARD_EXCLUDE_NOISE_KEYWORDS`：`score=0`
- URL 包含以下路径直接过滤：
  - `/presse/`
  - `/press/`
  - `/media-contact`
  - `/press-contact`
- Universal Robots 组合过滤：
  - 同时命中 `universal robots` + `UNIVERSAL_ROBOTS_PROMO_KEYWORDS` 时直接过滤
  - 不会因为品牌词单独被硬过滤

### 6.3 第三步：降权规则（不过滤）

- 命中 `DOWNWEIGHT_NOISE_KEYWORDS`：`score -= 2`（最低 0）
- 命中 `NEGATIVE_THEORY_ONLY_KEYWORDS`：
  - 若无工业语境词（`INDUSTRY_CONTEXT_KEYWORDS`）-> 直接过滤
  - 若有工业语境词 -> 降权（`score -= 2`，最低保留 1）
- YouTube 规则：
  - `shorts` 且分数不高时降权（`-1`）
  - 播放量 `<10` 时降权（`-2`）

### 6.4 LLM 二次校验（可选）

- 未使用 `--skip-llm-filter` 时执行
- 提示词要求：必须同时满足“AI信号 + 六大工业领域之一”才返回 YES
- LLM 返回 `None` 且关键词分数 `>=2` 时允许兜底放行
- 支持限流参数：
  - `KIMI_FILTER_MIN_REQUEST_INTERVAL_SECONDS`
  - `KIMI_FILTER_RATE_LIMIT_BACKOFF_SECONDS`
  - `KIMI_FILTER_RATE_LIMIT_MAX_RETRIES`
  - `KIMI_FILTER_TIMEOUT_SECONDS`

### 6.5 最低补量策略

- 当结果少于 `MIN_RELEVANT_ARTICLES` 时，从 `scored` 中按高分补齐
- 仅补 `score>=2` 项，避免低质量内容回流

### 6.6 过滤后排序与分析截断

- 过滤后的文章先排序：
  1. `relevance_score` 降序
  2. 来源 `priority` 降序
  3. `published_date` 降序
- 再按 `--top-n` 截断进入分析（默认 20）
- 截断后剩余最多 20 条在邮件末尾以简表展示

### 6.7 全量关键词列表（当前代码）

`TECHNICIAN_KEYWORDS` (+3):
`Instandhaltung`, `Anlagenverfügbarkeit`, `SPS`, `PLC`, `TIA Portal`, `OEE`, `Sicherheit`, `Störungsbehebung`, `Wartung`, `Inbetriebnahme`, `Fernwartung`, `SCADA`, `MES`, `HMI`, `OPC UA`, `Anomaly Detection`, `collaborative robot`, `cobot`, `AI chip`

`HIGH_PRIORITY_KEYWORDS` (+2):
`Ablaufsimulation`, `Fertigungssteuerung`, `Virtuelle Inbetriebnahme`, `VIBN`, `KI-gestützte Optimierung`, `KI-gestützte Fertigung`, `Diskrete Ereignissimulation`, `Asset Administration Shell`, `Verwaltungsschale`, `Industrial AI`, `Industrielle KI`, `AI in Production`, `KI in der Produktion`, `Manufacturing AI`, `Discrete Event Simulation`, `Digital Twin`, `Digitaler Zwilling`, `Machine Vision`, `Industrial Vision`, `Edge AI`, `AIoT`, `Virtual Commissioning`, `Predictive Quality`, `Condition Monitoring`, `Industrial Copilot`, `Production Optimization`, `Smart Maintenance`

`MEDIUM_PRIORITY_KEYWORDS` (+1):
`Automatisierungstechnik`, `Smart Factory`, `Intelligente Fabrik`, `Predictive Maintenance`, `Vorausschauende Wartung`, `Reinforcement Learning`, `Deep Reinforcement Learning`, `Multi-Agent System`, `Cyber-Physical Systems`, `Materialfluss`, `Logistiksimulation`, `Industrie 4.0`, `Industry 4.0`, `AnyLogic`, `Tecnomatix`, `Plant Simulation`, `Siemens`, `Omniverse`, `Machine Learning in Manufacturing`, `Computer Vision in Manufacturing`, `Industrial Computer Vision`, `Applied AI`, `AI in manufacturing`, `Production AI`, `Factory AI`, `Shopfloor AI`, `Industrial GenAI`, `MLOps`, `DataOps`, `Quality Inspection`, `Defect Detection`, `Process Mining`, `Time Series Forecasting`, `Demand Forecasting`, `Adaptive Control`, `Closed-loop optimization`, `Asset Performance Management`, `Energy Management`, `Lean Manufacturing`, `Batch Optimization`, `Universal Robots`

`BROAD_KEYWORDS` (fallback +1):
`industrial`, `industry`, `manufacturing`, `factory`, `automation`, `robot`, `digital`, `smart`, `simulation`, `predictive`, `maintenance`, `plc`, `iot`, `ai`, `machine learning`, `computer vision`

`HARD_EXCLUDE_NOISE_KEYWORDS` (直接过滤):
`livestream`, `live stream`, `webinar`, `podcast episode`, `event recap`, `conference recap`, `expo highlights`, `summit highlights`, `register now`, `save the date`, `meet us at`, `join us at`, `how to use`, `armorblock`, `news about mtp`, `mtp`, `device libraries - overview`, `looking back on a successful sps 2025`, `breaking the encryption: analyzing the automationdirect click plus plc protocol`, `power device library overview`, `besuchen`, `pressemitteilungen`, `pressekontakt`, `software package for energy-efficient and sustainable building operation`, `celebrating`, `built by us. driven by you`

`DOWNWEIGHT_NOISE_KEYWORDS` (降权 -2):
`software package`, `make a sequence`, `demo`, `walkthrough`, `step by step`, `quick start`, `getting started`, `how-to`, `how to`, `tutorial`, `release notes`, `version update`, `feature update`, `patch notes`, `booth`, `hall`, `visit us`, `join our booth`, `expo recap`, `trade fair recap`, `company announcement`, `corporate update`, `brand story`, `customer testimonial`, `future of`, `industry trends`, `top trends`, `insights`, `thought leadership`, `no subtitles`, `teaser`, `trailer`, `highlights only`, `einfuehrung`, `ueberblick`, `rueckblick`, `veranstaltungsbericht`, `kundenstory`, `发布会`, `活动回顾`, `参展`, `品牌故事`, `功能介绍`, `教程`, `上手指南`

`NEGATIVE_THEORY_ONLY_KEYWORDS`（理论/招聘/活动/营销类；结合工业语境门槛）:
`theorem`, `proof`, `lemma`, `corollary`, `axiom`, `hypergraph`, `graph neural network benchmark`, `reasoning benchmark`, `formal verification`, `formal logic`, `meta-learning benchmark`, `synthetic dataset`, `toy dataset`, `ablation study only`, `state-of-the-art on`, `leaderboard`, `openreview`, `arxiv preprint`, `multimodal reasoning`, `chain-of-thought benchmark`, `spatio-temporal dual-stage`, `corridor traffic signal control`, `convex optimization framework`, `variational bound`, `job`, `jobs`, `hiring`, `career`, `careers`, `internship`, `vacancy`, `recruiting`, `apply now`, `course`, `training`, `bootcamp`, `certification`, `workshop`, `masterclass`, `tutorial`, `how to become`, `stellenangebot`, `karriere`, `bewerben`, `ausbildung`, `schulung`, `kurs`, `webinar`, `register now`, `event recap`, `highlights`, `keynote recap`, `conference recap`, `expo highlights`, `livestream`, `live stream`, `podcast episode`, `summit highlights`, `meet us at`, `join us at`, `save the date`, `veranstaltung`, `rückblick`, `messe`, `live-übertragung`, `press release`, `brand campaign`, `award`, `winner`, `partnership announcement`, `sponsored`, `advertorial`, `promotion`, `promo`, `limited offer`, `new brochure`, `customer story`, `success story`, `testimonial`, `pressemitteilung`, `auszeichnung`, `partnerschaft`, `werbung`

`INDUSTRY_CONTEXT_KEYWORDS`（与理论负向词共现时用于降权而非拦截）:
`manufacturing`, `factory`, `production line`, `shopfloor`, `plant`, `plc`, `mes`, `scada`, `hmi`, `opc ua`, `oee`, `condition monitoring`, `predictive maintenance`, `asset performance`, `equipment`, `robot cell`, `industrial robot`, `quality inspection`, `defect detection`, `digital twin`, `industrie 4.0`, `instandhaltung`, `fertigung`, `produktionslinie`

`UNIVERSAL_ROBOTS_PROMO_KEYWORDS`（与 `universal robots` 组合触发硬过滤）:
`celebrating`, `built by us. driven by you`

---

## 7. 分析与语言规则（Analyzer Rules）

核心文件：`/Users/baixue/news/src/analyzers/llm_analyzer.py`

### 7.1 输出字段

LLM 输出结构化字段（中/英/德 + 技术要点 + 场景要点）。

### 7.2 中文来源语言一致性（重要）

- 若来源是中文，仍必须产出英文/德文字段
- Student 模板使用英文字段
- Technician 模板使用德文字段
- 不允许把中文直接塞进英文/德文模板

---

## 8. 邮件模板规则（Email Template Rules）

核心文件：`/Users/baixue/news/src/delivery/email_sender.py`

### 8.1 Student 模板

- 只限英文输出（English-only）
- 面向学习和理解

### 8.2 Technician 模板

- 德文输出
- 两个核心区块：
  - `Kernfokus`（应用场景重点）
  - `Kernmechanismus`（机制解释）
- 视觉：蓝色 + 橙色，上下布局
- `Kernfokus` 使用完整句子（不再词级截断）
- 每条新闻都显示来源（Source）
- 邮件末尾追加“未分析但相关”表格（Kategorie / Titel / Link），默认最多 20 条

---

## 9. 运行方式

### 9.1 常用命令

```bash
# 默认：审核发送（发 reviewer）
./.venv/bin/python main.py --output email

# 审核通过后：正式发送
./.venv/bin/python main.py --output email --approve-send

# 干跑（不发邮件）
./.venv/bin/python main.py --dry-run --output email

# 邮件 + Markdown + Notion
./.venv/bin/python main.py --output both
```

### 9.2 常用参数

- `--approve-send`：审核通过后正式群发
- `--skip-dynamic`：跳过动态抓取
- `--skip-llm-filter`：跳过 LLM 二次过滤
- `--top-n`：过滤后仅分析前 N 条（默认 20；`<=0` 不限制）
- `--mock`：分析使用 mock 数据
- `--strict`：任一关键步骤失败即退出

---

## 10. 关键配置项速查

配置文件：`/Users/baixue/news/config.py`

- 来源与优先：`DATA_SOURCES`, `RSS_WEB_PRIORITY_SOURCES`, `RSS_WEB_PRIORITY_ONLY`
- 领域聚焦：`TARGET_SEARCH_DOMAINS`
- 过滤门槛：`RELEVANCE_THRESHOLD`, `MIN_RELEVANT_ARTICLES`
- 关键词体系：`TECHNICIAN_KEYWORDS`, `HIGH_PRIORITY_KEYWORDS`, `MEDIUM_PRIORITY_KEYWORDS`, `HARD_EXCLUDE_NOISE_KEYWORDS`, `DOWNWEIGHT_NOISE_KEYWORDS`, `NEGATIVE_THEORY_ONLY_KEYWORDS`, `INDUSTRY_CONTEXT_KEYWORDS`
- 收件画像：`RECIPIENT_PROFILES`

`.env` 中建议设置：

```env
EMAIL_REVIEWER=baixue243@gmail.com
RELEVANCE_THRESHOLD=2
```

---

## 11. 故障排查

### 11.1 为什么没有某类新闻（如中国工业/汽车 AI）

优先检查：
- 对应来源是否在 `DATA_SOURCES`
- 是否被白名单策略排除（`RSS_WEB_PRIORITY_ONLY`）
- 是否因硬过滤词或 URL 规则被拦截（`HARD_EXCLUDE_NOISE_KEYWORDS` + press/contact URL 规则）

### 11.2 为什么技术员模板句子被截断

已改为完整句策略；若仍异常，检查是否为上游 LLM 输出本身断句。

### 11.3 为什么 GitHub 首页 README 没更新

通常是分支未合并到 `main`，或页面缓存未刷新。

---

## 12. 项目结构

```text
/Users/baixue/news
├── main.py
├── config.py
├── src/
│   ├── scrapers/
│   ├── filters/
│   ├── analyzers/
│   └── delivery/
├── tests/
└── output/
```
