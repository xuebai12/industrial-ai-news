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

过滤采用“两层 + 兜底”模型：

### 6.1 第一层：关键词打分

- `TECHNICIAN_KEYWORDS` 命中：`+3`
- `HIGH_PRIORITY_KEYWORDS` 命中：`+2`
- `MEDIUM_PRIORITY_KEYWORDS` 命中：`+1`
- 命中 6 大目标领域：额外 `+1`

### 6.2 工业语境门槛

- `STRICT_INDUSTRY_CONTEXT_GATING=true` 时：
  - 理论高风险词 + 无工业语境会被强降权

### 6.3 AI 硬门槛（重要）

- `REQUIRE_AI_SIGNAL=true` 时：
  - 若文章没有 AI 信号词（AI/ML/机器视觉/大模型等）
  - 直接不通过（score 置 0）
- 目标：防止“纯汽车新闻/纯行业新闻”混入

### 6.4 第二层：LLM 相关性校验

- 对关键词通过的文章做 YES/NO 二次校验
- 若 LLM 不可判定：仅高分项可按规则兜底

### 6.5 最低补量策略

- 目标：避免日报条目过少
- 但补量仍受工业语境与 AI 信号约束，不放入明显噪音

### 6.6 分析前排序与限流（重要）

- 过滤通过集合先排序，再进入分析
- 排序规则：
  1. `relevance_score` 高到低
  2. 来源 `priority` 高到低
  3. `published_date` 新到旧
- 默认仅分析前 `20` 条（`--top-n 20`），可降低本地模型超时与 429 风险

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

- 英文表达优先
- 面向学习和理解

### 8.2 Technician 模板

- 德文输出
- 两个核心区块：
  - `Kernfokus`（应用场景重点）
  - `Kernmechanismus`（机制解释）
- 视觉：蓝色 + 橙色，上下布局
- `Kernfokus` 使用完整句子（不再词级截断）
- 每条新闻都显示来源（Source）
- 邮件末尾追加“未分析但相关”表格（Titel / Quelle / Score / Link），默认最多 20 条

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
- 过滤门槛：`STRICT_INDUSTRY_CONTEXT_GATING`, `FALLBACK_REQUIRE_INDUSTRY_CONTEXT`, `REQUIRE_AI_SIGNAL`
- 关键词体系：`TECHNICIAN_KEYWORDS`, `HIGH_PRIORITY_KEYWORDS`, `MEDIUM_PRIORITY_KEYWORDS`, `AI_RELEVANCE_KEYWORDS`
- 收件画像：`RECIPIENT_PROFILES`

`.env` 中建议设置：

```env
EMAIL_REVIEWER=baixue243@gmail.com
REQUIRE_AI_SIGNAL=true
```

---

## 11. 故障排查

### 11.1 为什么没有某类新闻（如中国工业/汽车 AI）

优先检查：
- 对应来源是否在 `DATA_SOURCES`
- 是否被白名单策略排除（`RSS_WEB_PRIORITY_ONLY`）
- 是否未命中 AI 信号门槛（`REQUIRE_AI_SIGNAL=true`）

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
