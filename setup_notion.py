
import os
import logging
from notion_client import Client

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_notion")

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def setup_database():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.error("Missing API Key or Database ID")
        return

    client = Client(auth=NOTION_API_KEY)

    logger.info(f"Updating schema for database {NOTION_DATABASE_ID}...")

    properties = {
        "标题": {"title": {}},
        "评分": {"number": {"format": "number"}},
        "类别": {"select": {
            "options": [
                {"name": "AI", "color": "blue"},
                {"name": "Simulation", "color": "purple"},
                {"name": "Industry 4.0", "color": "gray"},
                {"name": "Robotics", "color": "orange"},
                {"name": "Other", "color": "default"}
            ]
        }},
        "AI 摘要": {"rich_text": {}},
        "核心技术": {"multi_select": {}},
        "来源/机构": {"select": {}},
        "原文链接": {"url": {}},
        "日期": {"date": {}},
        "工具链": {"rich_text": {}},
        "通俗解读": {"rich_text": {}},
        "Persona Match": {"multi_select": {
             "options": [
                {"name": "student", "color": "blue"},
                {"name": "technician", "color": "orange"}
            ]
        }},
    }

    try:
        resp = client.databases.update(database_id=NOTION_DATABASE_ID, properties=properties)
        logger.info("✅ Database schema updated successfully!")
        import json
        logger.info(f"Update Response Sample: {json.dumps(list(resp.get('properties', {}).keys()))}")
    except Exception as e:
        logger.error(f"❌ Failed to update schema: {e}")

if __name__ == "__main__":
    setup_database()
