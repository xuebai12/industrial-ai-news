import os
import logging
from datetime import date
from dotenv import load_dotenv

# Load envs
load_dotenv()

from notion_client import Client
from src.models import AnalyzedArticle, Article
from src.delivery.notion_service import NotionDeliveryService

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_push():
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_DATABASE_ID")

    if not api_key or not db_id:
        print("❌ Missing NOTION_API_KEY or NOTION_DATABASE_ID")
        return

    print(f"Using DB ID: {db_id}")
    
    # Create Mock Article
    mock_article = AnalyzedArticle(
        category_tag="Industry 4.0",
        title_zh="[通过测试] 工业 AI 系统集成验证",
        title_en="[TEST] Industrial AI System Integration Verification",
        title_de="[TEST] Validierung der industriellen KI-Systemintegration",
        summary_zh="这条记录用于验证 Notion 数据库字段是否配置正确。",
        summary_en="This entry verifies that Notion database fields are correctly configured.",
        summary_de="Dieser Eintrag überprüft, ob die Notion-Datenbankfelder korrekt konfiguriert sind.",
        core_tech_points="Notion API, Python, Integration Testing",
        german_context="Test Environment (Baixue's Setup)",
        source_name="System Test",
        source_url="https://github.com/xuebai12/industrial-ai-news/test_run",
        tool_stack="Notion Client, Pytest",
        simple_explanation="这是一个测试条目，如果你能看到它，说明 Notion 集成成功了！",
        technician_analysis_de="Technician View: Die Schnittstelle funktioniert einwandfrei. Datenübertragung erfolgreich getestet.",
        target_personas=["student", "technician"],
        original=Article(
            title="Test Article",
            url="https://github.com/xuebai12/industrial-ai-news/test_run",
            source="System Test",
            content_snippet="Test content",
            language="en",
            category="Test"
        )
    )

    client = Client(auth=api_key)
    service = NotionDeliveryService(client, db_id)

    print("Pushing article...")
    try:
        count = service.push_articles([mock_article], date.today().strftime("%Y-%m-%d"))
        if count > 0:
            print("✅ Successfully pushed test article to Notion!")
        else:
            print("⚠️ Article processed but not pushed (maybe duplicate?)")
    except Exception as e:
        print(f"❌ Failed to push: {e}")

if __name__ == "__main__":
    test_push()
