# 🏭 Industrial AI 每日情报系统

> 每天早上自动收集工业 AI 领域最新资讯，用 AI 分析整理，再通过邮件发送给你。
> 就像一个不睡觉的研究助理，帮你读完所有值得读的文章，再写成摘要发到你的邮箱。

---

## 🗺️ 这个系统是做什么的？

```
互联网上的文章    →    筛选相关文章    →    AI 分析    →    发送到你邮箱
(每天自动抓取)       (去掉不相关的)     (写成摘要)     (按不同读者定制)
```

**具体来说，它每次运行时会做 4 件事：**

| 步骤 | 做什么 | 就像是… |
|------|--------|--------|
| 1️⃣ 抓取 | 从 20+ 个网站和 RSS 源抓取最新文章 | 派人去翻报纸 |
| 2️⃣ 过滤 | 用关键词 + AI 判断文章是否与工业 AI 相关 | 筛掉不相关广告 |
| 3️⃣ 分析 | 用 AI 生成中/英/德三语摘要，并为不同读者写不同版本 | 秘书整理会议纪要 |
| 4️⃣ 发送 | 把摘要发送到配置好的邮箱，或存入 Notion | 发送日报 |

**当前邮件发送采用“先审后发”机制：**
- 默认先发两封审核邮件到 `baixue243@gmail.com`（Student + Technician）
- 审核通过后再执行正式群发（不会重复发给审核邮箱）

---

## 👥 会发给谁？发什么内容？

系统支持**多个收件人画像**，每个画像收到不同风格的邮件：

### 🎓 学生版（Student）
- 语言：英文
- 风格：学术视角，关注仿真、AI、求职
- 内容：核心技术要点 + 应用背景 + 通俗解释

### 🔧 技师版（Technician）
- 语言：德文
- 风格：实操导向，阅读障碍友好（大字体、高对比色块、短句优先）
- 内容：
  - 🔵 **Kernfokus**（应用场景与落地重点，短句列表）
  - 🟠 **Kernmechanismus**（用形象比喻解释“它怎么运作”）
  - 展示方式：**两个栏目、两种颜色、上下排列**

---

## 🎯 检索领域（固定 6 大类）

系统当前重点搜索以下 6 个 AI 工业应用领域：

1. 工厂（Factory）
2. 机器人（Robotics）
3. 汽车（Automotive）
4. 供应链（Supply Chain）
5. 能源（Energy）
6. 网络安全（Cybersecurity）

其中“工厂”已细分为：
- 设计与研发
- 生产与工艺优化
- 质量检测与缺陷分析
- 设备运维与预测性维护

并且默认启用 **AI 信号硬门槛**：纯行业新闻（如纯汽车新闻）不会进入分析，必须出现 AI/ML/机器视觉/大模型等信号。

---

## 📁 项目结构（文件夹说明）

```
news/
│
├── main.py                  ← 主程序：点这里启动整个运行流程
├── config.py                ← 配置中心：改这里设置收件人、关键词、数据源
├── .env                     ← 密钥文件：存放邮箱密码、API Key（不要上传到 GitHub）
│
├── src/
│   ├── scrapers/            ← 抓取器：负责从各网站拿文章
│   │   ├── rss_scraper.py      RSS 订阅源抓取
│   │   ├── web_scraper.py      普通网页抓取
│   │   └── youtube_scraper.py  YouTube 视频抓取
│   │
│   ├── filters/             ← 过滤器：判断文章是否相关
│   │
│   ├── analyzers/           ← AI 分析器：调用大模型生成摘要
│   │   └── llm_analyzer.py     核心分析逻辑（中/英/德三语）
│   │
│   └── delivery/            ← 发送器：把结果送到目的地
│       ├── email_sender.py     邮件发送（含 HTML 模板渲染）
│       ├── notion_service.py   推送到 Notion 数据库
│       └── notion_sender.py
│
├── output/                  ← 输出目录：每次运行的结果文件
│   ├── digest-YYYY-MM-DD.md        每日摘要（Markdown 格式）
│   ├── sent_history.json           已发送记录（防止重复发送）
│   └── newsletter_preview_technician.html      技师版邮件预览
│
└── tests/                   ← 自动测试：确保代码改动没有破坏功能
```

---

## ⚙️ 第一次使用：环境配置

> 只需要配置一次，之后每次运行都不需要重复。

### 第 1 步：安装依赖

在终端（Terminal）里运行：

```bash
cd /Users/baixue/news
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 第 2 步：创建密钥文件

```bash
cp .env.example .env
```

然后用文本编辑器打开 `.env`，填写以下内容：

```
# AI 模型选择（二选一）
USE_LOCAL_OLLAMA=true          # 使用本地 Ollama 模型（免费）
OLLAMA_MODEL=kimi-k2.5:cloud

# 或者使用云端 NVIDIA 模型（需要 API Key）
NVIDIA_API_KEY=你的Key

# 邮件发送配置（使用 Gmail 举例）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=你的邮箱@gmail.com
SMTP_PASS=你的应用专用密码
EMAIL_TO=收件人@gmail.com
EMAIL_REVIEWER=baixue243@gmail.com  # 审核邮箱（默认值）

# 过滤开关（建议保持默认）
REQUIRE_AI_SIGNAL=true               # 必须是 AI 相关内容才入选

# Notion（可选，不用可以留空）
NOTION_API_KEY=
NOTION_DATABASE_ID=
```

> 💡 Gmail 需要开启"两步验证"并生成"应用专用密码"，不能直接用账号密码。

---

## ▶️ 日常运行

配置完成后，每次运行只需要一行命令：

```bash
# 默认：先发审核邮件到 reviewer（student+technician 两封）
./.venv/bin/python main.py --output email

# 审核通过后：正式发送给其他收件人
./.venv/bin/python main.py --output email --approve-send

# 预览效果，不真正发送（测试用）
./.venv/bin/python main.py --dry-run --output email

# 发邮件 + 保存 Markdown + 推送 Notion
./.venv/bin/python main.py --output both

# 跳过慢速网站（运行更快）
./.venv/bin/python main.py --output email --skip-dynamic
```

---

## 🔧 运行参数说明

| 参数 | 作用 | 什么时候用 |
|------|------|-----------|
| `--output email` | 发送邮件 | 正常运行 |
| `--output markdown` | 只生成本地 Markdown 文件 | 查看结果但不发邮件 |
| `--output notion` | 推送到 Notion | 有 Notion 配置时 |
| `--output both` | 邮件 + Markdown + Notion 都做 | 完整输出 |
| `--dry-run` | 不真正发邮件，只在终端显示结果 | 测试、调试 |
| `--approve-send` | 审核通过后执行正式群发 | 第二步发送 |
| `--skip-dynamic` | 跳过需要浏览器的动态网站 | 运行慢时加速 |
| `--skip-llm-filter` | 跳过 AI 二次相关性校验 | 文章数量太少时 |
| `--mock` | 不调用 AI，使用模拟数据 | 测试邮件格式 |
| `--strict` | 任何步骤出错就直接停止 | 生产环境 |

---

## 📰 数据来源

系统抓取以下类型的来源：

| 来源类型 | 例子 |
|---------|------|
| 德国工业研究机构 | Fraunhofer IPA、DFKI、TUM |
| 汽车媒体/车厂技术源 | Volkswagen、BMW、Mercedes、Automotive News Europe、SAE |
| 中国工业与AI媒体/机构 | 36Kr、机器之心、高工机器人、甲子光年、MIIT、信通院、BYD |
| 行业媒体 | VDI Nachrichten、Handelsblatt |
| 大厂官方博客 | Siemens、ABB、Bosch、Google Cloud |
| 学术论文预印本 | arXiv（cs.AI、cs.SY） |
| 供应链平台 | SAP、AWS、Oracle |
| YouTube 视频 | Industrial AI 及工业主题频道 |

---

## 🚨 常见问题排查

### 邮件发不出去
1. 检查 `.env` 里的 `SMTP_USER`、`SMTP_PASS`、`EMAIL_TO` 是否填写正确
2. Gmail 用户确认使用的是**应用专用密码**，不是账号密码
3. 运行时加 `--dry-run` 先确认内容是否正常

### 文章数量太少（0 篇或 1-2 篇）
1. 加 `--skip-llm-filter` 绕过 AI 二次过滤，看关键词过滤是否正常
2. 检查 `REQUIRE_AI_SIGNAL=true` 是否过严；若做探索可临时关闭
3. 检查网络连接，部分德国网站在中国大陆可能需要代理

### 中文来源在英文/德文模板里显示不对
1. 系统已要求中文来源必须翻译到模板语言（Student=EN, Technician=DE）
2. 若仍出现混语，先重跑一次（模型可能返回不完整字段）
3. 如需强制更严格，可在分析提示词中提升翻译约束

### AI 分析质量差或运行很慢
1. 检查 Ollama 是否在运行：`ollama list`
2. 考虑切换到 NVIDIA 云端模型，在 `.env` 里设置 `NVIDIA_API_KEY`

### 想看邮件长什么样但不想发送
```bash
./.venv/bin/python main.py --dry-run --output email
```
也可以直接在浏览器里打开 `output/newsletter_preview_technician.html`

---

## 📊 运行日志

每次运行后，会在 `output/` 目录生成：

- `run-summary-YYYY-MM-DD.json` — 本次运行统计（抓了多少篇、过了多少篇、发给了谁）
- `digest-YYYY-MM-DD.md` — 当日摘要的 Markdown 版本
- `sent_history.json` — 发送历史记录（防止同一篇文章被重复发送）

---

## 🛠️ 技术栈（给有开发经验的读者）

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| AI 模型 | Ollama（本地）/ NVIDIA NIM Kimi-K2.5（云端） |
| 邮件模板 | Jinja2 HTML |
| 数据库 | Notion API |
| 数据抓取 | requests + BeautifulSoup + feedparser + YouTube Data API v3 |
| 测试 | pytest |

---

*最后更新：2026-02-20*
