"""Article data models used across the pipeline."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """
    原始文章数据模型 (Raw Article Model)
    用于存储从 RSS 或网页抓取的原始数据。
    """
    title: str              # 文章标题
    url: str                # 文章链接
    source: str             # 来源名称 (e.g. "TechCrunch")
    content_snippet: str    # 内容片段/摘要
    language: str           # 语言代码 ("de", "en", "zh")
    category: str           # 原始分类 (e.g. "Technology")
    published_date: datetime | None = None  # 发布时间
    video_views: int | None = None  # YouTube 播放量（若可提取）
    relevance_score: int = 0  # 关联度评分 (关键词匹配得分)
    target_personas: list[str] = field(default_factory=list) # 目标受众标签
    domain_tags: list[str] = field(default_factory=list)  # 六大领域标签 (multi-label)


@dataclass
class AnalyzedArticle:
    """
    分析后的文章数据模型 (Analyzed Article Model)
    存储经过 LLM AI 深度分析后的结构化数据。
    """
    category_tag: str          # 类别标签 (e.g. "Digital Twin", "Research", "Industry 4.0")
    title_en: str              # 英文标题
    title_de: str              # 德文标题 (German Title)
    german_context: str        # 德方/行业应用背景
    source_name: str           # 来源名称 (e.g. "Fraunhofer IPA")
    source_url: str            # 原始链接
    summary_en: str            # 英文一句话摘要
    summary_de: str            # 德文一句话摘要 (German Summary)
    
    # --- New Dimensions (2026-02-13) ---
    # 新维度：不再关注求职面试，而是关注通俗解读
    tool_stack: str = ""           # 提及的工具栈/软件 (e.g. Siemens, AnyLogic)
    simple_explanation: str = ""   # 通俗解读 (Beginner-friendly explanation - Student View)
    technician_analysis_de: str = "" # 技师视角分析 (Technician View - German)
    
    target_personas: list[str] = field(default_factory=list) # 目标受众标签 (e.g. ["Student", "Technician"])
    
    original: Article | None = None  # 关联的原始文章对象
