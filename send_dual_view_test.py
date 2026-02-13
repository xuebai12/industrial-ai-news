import logging
from datetime import date
from src.models import AnalyzedArticle, Article
from src.delivery.email_sender import send_email
from config import RECIPIENT_PROFILES

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_test_emails():
    print("🚀 Starting Dual-View Email Test...")
    
    # 1. Create Mock Articles
    # Article 1: General Industry 4.0 (Student focus)
    article_student = AnalyzedArticle(
        category_tag="Simulation",
        title_zh="[测试] 工业 4.0 数字孪生入门",
        title_en="[TEST] Introduction to Industry 4.0 Digital Twins",
        title_de="[TEST] Einführung in Industrie 4.0 Digitale Zwillinge",
        summary_zh="这篇文章介绍了数字孪生的基本概念。",
        summary_en="This article introduces basic Digital Twin concepts.",
        summary_de="Dieser Artikel führt in die grundlegenden Konzepte des digitalen Zwillings ein.",
        core_tech_points="Digital Twin, Python, Simulation",
        german_context="German Research Center for AI (DFKI)",
        source_name="Test Source",
        source_url="http://example.com/student",
        tool_stack="Python, AnyLogic",
        simple_explanation="这是给学生的通俗解释：数字孪生就像工厂的虚拟替身。",
        technician_analysis_de="", # Empty for student article
        target_personas=["student"],
        original=Article(title="Test 1", url="http://e.com/1", source="Test", content_snippet="Test", language="en", category="Research")
    )

    # Article 2: Technical Maintenance (Technician focus)
    article_tech = AnalyzedArticle(
        category_tag="Industry 4.0",
        title_zh="[测试] 西门子 S7-1500 PLC 预测性维护指南",
        title_en="[TEST] Predictive Maintenance for Siemens S7-1500 PLC",
        title_de="[TEST] Vorausschauende Wartung für Siemens S7-1500 SPS",
        summary_zh="详细讲解了如何通过 TIA Portal 获取 PLC 运行数据。",
        summary_en="Detailed guide on extracting PLC data via TIA Portal.",
        summary_de="Detaillierte Anleitung zum Extrahieren von SPS-Daten über das TIA Portal.",
        core_tech_points="PLC, S7-1500, TIA Portal, MQTT",
        german_context="Siemens Factory Amberg",
        source_name="Siemens Blog",
        source_url="http://example.com/tech",
        tool_stack="TIA Portal, S7-PLCSIM",
        simple_explanation="这是给学生的解释：PLCs 是控制工厂的电脑。",
        technician_analysis_de="Technician Analysis (DE): Hier wird erklärt, wie man DBs im TIA Portal optimiert, um Zykluszeiten zu reduzieren. Wichtig für die OEE.",
        target_personas=["technician"],
        original=Article(title="Test 2", url="http://e.com/2", source="Test", content_snippet="Test", language="en", category="Industry")
    )
    
    # Article 3: Both
    article_both = AnalyzedArticle(
        category_tag="AI in Manufacturing",
        title_zh="[测试] AI 驱动的传送带故障检测",
        title_en="[TEST] AI-driven Conveyor Belt Fault Detection",
        title_de="[TEST] KI-gesteuerte Fehlererkennung an Förderbändern",
        summary_zh="结合了 AI 算法与 PLC 控制。",
        summary_en="Combining AI algorithms with PLC control.",
        summary_de="Kombination von KI-Algorithmen mit SPS-Steuerung.",
        core_tech_points="AI, PLC, Python",
        german_context="Volkswagen Wolfsburg",
        source_name="VDI Nachrichten",
        source_url="http://example.com/both",
        tool_stack="PyTorch, Siemens PLC",
        simple_explanation="学生视角：AI 像眼睛一样看着传送带。",
        technician_analysis_de="Technician View: Die Integration erfolgt über OPC UA direkt in die Steuerungsebene. Reduziert Stillstandszeiten.",
        target_personas=["student", "technician"],
        original=Article(title="Test 3", url="http://e.com/3", source="Test", content_snippet="Test", language="en", category="AI")
    )

    all_articles = [article_student, article_tech, article_both]

    # 2. Iterate Profiles and Send
    today = date.today().strftime("%Y-%m-%d")
    
    for profile in RECIPIENT_PROFILES:
        print(f"\n📨 Preparing email for profile: {profile.name} ({profile.email})")
        
        # Filter logic from main.py
        filtered_articles = [
            a for a in all_articles 
            if profile.persona in (a.target_personas or [])
            or (not a.target_personas and profile.persona == "student")
        ]
        
        if not filtered_articles:
            print(f"   ⚠️ No articles matched for {profile.name}")
            continue
            
        print(f"   ✅ Found {len(filtered_articles)} matching articles.")
        for a in filtered_articles:
            print(f"      - {a.title_zh}")
            
        success = send_email(filtered_articles, today, profile=profile)
        if success:
            print(f"   🎉 Email sent successfully to {profile.email}!")
        else:
            print(f"   ❌ Failed to send email.")

if __name__ == "__main__":
    send_test_emails()
