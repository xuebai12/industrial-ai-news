# 工业 AI 新闻智能监控与推送系统 - 产品需求与设计文档 (PRD)

## 1. 产品背景与目标 (Project Overview)
**目标**：构建一个端到端的自动化信息处理管线。系统需要从 RSS 和网页中抓取指定数据源的工业 AI 资讯，利用本地过滤与关键字列表进行初步打分过滤，随后调用大模型 (LLM) 进行深度解析（提取摘要、工业应用背景、技术术语等），最终根据不同的订阅者画像（如：学生、设备技师），生成针对性语言（英文或德文）并进行多渠道投递（Email、Notion 等）。

## 2. 核心架构与处理流程 (Core Pipeline)
1. **数据采集 (Scraping)**：定时从新闻网站、RSS 等数据源（`config.py` 定义）获取原始文章片段。
2. **数据清洗与排重 (Deduplication)**：根据 URL 与标题排重，避免重复内容。
3. **初步过滤与打分 (Filtering & Scoring)**：基于关键词矩阵（优先词 / 拯救白名单等）计算相关性分数；结合规则引擎或本地轻量级 LLM 模型过滤无关新闻（Noise）。
4. **深度分析与结构化 (AI Analysis)**：将高分文章片段输入 LLM（如 OpenAI/Ollama API），按照严格的 JSON Schema 提取摘要、行业背景、通俗解释等结构化数据。
5. **分发与推送 (Delivery)**：根据用户的订阅配置（`Profile`），使用对应语言渲染邮件模板（HTML/TEXT）并通过 SMTP 发送，同时将其写入 Notion 数据库以供长期留存归档。

## 3. 核心数据模型 (Data Models)
文件：`src/models.py`
为了保证系统数据流的一致性，定义了以下两个核心 DataClass 流转实体：
* **`Article` (原始文章模型)**：
    * 字段：`title` (标题)、`url` (链接)、`source` (来源)、`content_snippet` (原始内容片段)、`language`、`relevance_score` (关键词打分)、`target_personas` 等。
    * 作用：系统初期各大抓取模块返回的统一实体格式。

* **`AnalyzedArticle` (分析后结构化文章)**：
    * 字段：`category_tag` (自动分类)、`title_en`/`title_de` (各语言标题)、`summary_en`/`summary_de` (多语言一句话摘要)、`german_context` (德方行业背景)、`tool_stack` (提及的数据/AI软硬件工具)、`simple_explanation` (针对学生/新手的通俗英文通俗解释)、`technician_analysis_de` (针对厂房底层技师的直白德文技术分析)、`original` (带有原始文章对象的引用)。
    * 作用：LLM 吐出的标准化 JSON 结果反序列化后的最终结构。我们系统彻底抛弃了中文(zh)支持，所以该实体必须完全基于英文(En)/德文(De)输出。

## 4. 模块与文件级详细逻辑 (Module & File Details)

小白开发者在开发和阅读代码时，应该按照下方文件拆分的逻辑顺序去理解系统：

### 4.1 配置文件与核心入口
* **`config.py` (配置总线)**
    * **作用**：项目的配置中心与“中枢神经”。所有易变的常量都在此修改，不用去改代码。
    * **内容逻辑**：
        1. `Profile` 定义：用户画像列表（包含接收邮箱、受众角色 `student`/`technician`、需要推送的语言 `en`/`de` 以及关注的个性化关键词）。
        2. `DataSource` 矩阵：系统从哪里抓取新闻的字典配置，包含名称、链接与默认品类分类。
        3. **Keywords 矩阵逻辑**：`HIGH_PRIORITY_KEYWORDS`（提及此词汇强加分）、`HARD_TECH_KEYWORDS`（“免死金牌/急救白名单”：不论被判别为多少分废话，只要涉及此技术就会被直接拯救并抓取）、`HARD_EXCLUDE_NOISE_KEYWORDS`（完全包含水文标志的垃圾新闻直接抛弃）。
* **`main.py` (主控制台)**
    * **作用**：项目主调度脚本（Controller）。
    * **逻辑主线**：参数解析（如通过命令行传入 `--dry-run` 不实际发送邮件） -> 调度 `scrape_all` 拉取所有网站文章 -> 使用本地过滤规则与 LLM 为文章判定相关度打分与去重 -> 截取高分 Top N 强行发送至分析器提取 `AnalyzedArticle` -> 经过受众匹配后，分发进入 `email_sender.py` 或 `notion_service.py` 收尾。

### 4.2 数据抓取层 (Scrapers)
* 本层功能：负责对接千奇百怪的外部上游资讯网络，将其统一转换为 `Article` 对象。
* **`src/scrapers/rss_scraper.py`**：利用 `feedparser` 库抓取最为传统的 RSS 流（常用于博客和主流新闻站）。
* **`src/scrapers/web_scraper.py`**：利用 `requests` 与 `BeautifulSoup` 获取传统无动态渲染的静态网页列表。
* **`src/scrapers/dynamic_scraper.py`**：用于处理 JS 后渲染的列表或者特定防爬机制网站的请求封装接口保障。

### 4.3 过滤与识别引擎 (Filters)
* **`src/filters/ollama_filter.py`**
    * **作用**：使用本地轻巧的端侧大模型（例如本地部署的 Ollama 等）进行高并发的“二分类粗筛判定”。用于判断新闻是否为真正的“硬核工业AI内容”。
    * **设计初衷**：以几乎零成本对海量抓取到的新闻数据做第一道防线，极大地分担并节省后续由云端调用商业级强大大模型深度分析的数据量以省钱。

### 4.4 大模型分析核心枢纽 (AI Analyzers)
* **`src/analyzers/llm_analyzer.py`**
    * **作用**：将初筛留下并打好分的干货文章请求大型 AI 来深度阅读翻译，并规定它严格吐出 JSON 回馈。
    * **逻辑**：
        1. 针对不同的角色定义了 Prompt：`STUDENT_EN_PROMPT`（只生成简短和带通俗化背景的英文输出）和 `TECHNICIAN_DE_PROMPT`（纯德文输出，针对机械领域技师给出实际痛点建议）。
        2. 调用大模型聊天接口，以严格的结构返回属性。
        3. `_extract_json`/`_call_and_parse` 逻辑：该系统最脆弱的地方就是 AI 回复内容可能不是严谨的格式。所以这里拥有极为健壮的反序列化容错处理（会试图寻找并修复那些首尾可能截断的 JSON 符号或清理多余的 Markdown 标记）。若异常还会执行自动重试。

### 4.5 分发输出展示系统 (Delivery Network)
* **`src/delivery/email_sender.py`**
    * **作用**：基于不同的角色偏好和系统结果，用 `smtplib` 邮递出最终邮件。
    * **逻辑**：
        1. 配合 HTML 模板引擎框架，渲染可视化报告。
        2. **语言与受众切分视图隔离**：根据用户的 `profile.persona` 决定 `lang` 使用。如果受众是普通学生 (Student)，则调用 `summary_en` 和通俗理解属性组装邮件元素；如果受众是技师 (Technician)，则抓取 `technician_analysis_de` 等纯德语实事求是的元素，实现“看不同维度的信息”体验定制。
* **`src/delivery/notion_service.py`**
    * **作用**：将当日挖掘的优质新闻作为“历史知识库”沉淀。
    * **逻辑**：利用 Notion Database API，将 JSON 解析后的数据映射至 Properties 列当中，并将主体内容作为区块按照（Heading, Paragraph 格式）在具体内页结构化排版。内部已封装完善去重机制防暴写。

## 5. 小白工程师扩展建议路线 (Best Practices Guide)
1. **要新增抓取源怎么做：** 绝大多数情况下都不用写爬虫代码，只需要在 `config.py` 的数据源清单 `DataSource` 中新增一个 URL 和对应的标签配置项即可；若碰到爬取解析乱码、失败异常，才需要到 `scrapers/` 中定位具体的解析器打补丁。
2. **需要 AI 帮我再提炼一个"作者/发文机构"字段怎么做：**
   - 先走到结构中心：在 `src/models.py` 的 `AnalyzedArticle` 里加上成员属性 (e.g. `author: str = ""`)。
   - 再去控制大脑：到 `src/analyzers/llm_analyzer.py` 中更新系统核心的 `PROMPT` （要求 AI 在返回的 JSON 对象里多按这个字段格式写信息）。
   - 在同样文件中实例化对象的组装代码处，取出值带上安全的防御代码: `author=_ensure_str(data.get("author", "未知"))`。
   - 最后在你想要展示的 `notion_service.py` (加到 Property 里) 或 `email_sender.py` (放进 HTML 里) 完成对应的前端绑定就好。
3. **保持语言管线的极简：** 系统刚结束大型重构剥离了中文冗余代码。如果将来遇到报错提示 `AttributeError` 说没有 `title_zh` 类似现象存在，记住检查是不是之前有残留的逻辑引用或自己手误复制了旧有字段，全盘拥抱 `_en` / `_de` 特性。

---
最后，如果有文档中不明确或者与你预期有冲突的想法，可以直接要求针对某个单一的文件深挖，比如询问：“请详细补充 `main.py` 是怎么给文章打分的机制” 等。
