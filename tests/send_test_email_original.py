
import logging
import sys
import os
from datetime import date
from src.models import AnalyzedArticle, Article
from src.delivery.email_sender import send_email

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def send_test_email():
    print("--- Sending Test Email (Original Version) ---")

    # Check if EMAIL_TO is set
    email_to = os.getenv("EMAIL_TO")
    if not email_to:
        print("❌ EMAIL_TO environment variable not set. Cannot send email.")
        return

    today = date.today().strftime("%Y-%m-%d")

    # ----------------
    # Article 1: Simulation in Logistics
    # ----------------
    article1_orig = Article(
        title="Optimization of AGV Routing using Reinforcement Learning",
        url="http://example.com/agv-rl",
        source="ResearchGate",
        content_snippet="Using Q-Learning to optimize Automated Guided Vehicle paths in warehouses.",
        language="en",
        category="Research"
    )

    article1_analyzed = AnalyzedArticle(
        category_tag="Research",
        title_zh="基于强化学习的 AGV 路径优化",
        title_en="Optimization of AGV Routing using Reinforcement Learning",
        summary_zh="研究利用 Q-Learning 算法优化仓库中自动导引车 (AGV) 的路径规划，通过仿真验证了效率提升。",
        summary_en="Using Q-Learning to optimize Automated Guided Vehicle paths in warehouses.",
        core_tech_points="Reinforcement Learning (Q-Learning), Pathfinder Logic, Discrete Event Simulation",
        german_context="Relevant for German logistics automation (e.g. KIVA systems alternatives).",
        source_name="ResearchGate",
        source_url="http://example.com/agv-rl",

        # New Simple Fields
        tool_stack="Python, OpenAI Gym, AnyLogic",
        simple_explanation="这就好比教机器人通过试错来找到仓库里走得最快的路，以前是死记硬背地图，现在是随机应变躲障碍。",

        original=article1_orig
    )

    # ----------------
    # Article 2: Industrial AI Career
    # ----------------
    article2_orig = Article(
        title="Skills Required for Industry 4.0 Engineers",
        url="http://example.com/skills",
        source="VDI Nachrichten",
        content_snippet="Companies are looking for engineers who know both PLC and Python.",
        language="en",
        category="Career"
    )

    article2_analyzed = AnalyzedArticle(
        category_tag="Career",
        title_zh="工业 4.0 工程师必备技能清单",
        title_en="Skills Required for Industry 4.0 Engineers",
        summary_zh="企业正在寻找既懂传统 PLC 编程，又掌握 Python 数据分析的复合型人才。",
        summary_en="Companies are looking for engineers who know both PLC and Python.",
        core_tech_points="PLC (IEC 61131-3), Python (Pandas/Scikit-learn), MQTT",
        german_context="High demand in Baden-Württemberg automotive sector.",
        source_name="VDI Nachrichten",
        source_url="http://example.com/skills",

        # New Simple Fields
        tool_stack="Siemens TIA Portal, Jupyter Notebook",
        simple_explanation="现在的工厂不仅需要会拧螺丝的老师傅，更需要会写代码分析螺丝为什么松了的工程师。",

        original=article2_orig
    )

    articles = [article1_analyzed, article2_analyzed]

    print(f"Sending {len(articles)} articles to {email_to}...")
    success = send_email(articles, today)

    if success:
        print("✅ Email sent successfully!")
    else:
        print("❌ Failed to send email. Check logs.")

if __name__ == "__main__":
    send_test_email()
