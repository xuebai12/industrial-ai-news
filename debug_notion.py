
import os
import sys
from dotenv import load_dotenv
from notion_client import Client
from pprint import pprint

# Load env vars
load_dotenv()

api_key = os.getenv("NOTION_API_KEY")
db_id = os.getenv("NOTION_DATABASE_ID")

def main():
    print(f"Python: {sys.executable}")
    try:
        import notion_client
        print(f"notion_client file: {notion_client.__file__}")
        # print(f"notion_client version: {notion_client.__version__}")
    except ImportError:
        print("notion_client not installed")
        return

    client = Client(auth=api_key)
    
    # 0. Search for all accessible databases
    print("\n--- Searching for all accessible databases ---")
    try:
        results = client.search(filter={"value": "database", "property": "object"}).get("results", [])
        print(f"Found {len(results)} databases:")
        for r in results:
            print(f"- Name: {r.get('title', [{}])[0].get('plain_text', 'Untitled')}")
            print(f"  ID: {r.get('id')}")
            print(f"  URL: {r.get('url')}")
    except Exception as e:
        print(f"❌ Search failed: {e}")

    # 1. Check database attributes
    print("\n--- Inspecting DatabasesEndpoint ---")
    print(dir(client.databases))
    
    # 2. Try to retrieve database info (schema)
    print(f"\n--- Retrieving Database {db_id} ---")
    try:
        db = client.databases.retrieve(database_id=db_id)
        print("✅ Database found!")
        print("\nFull Database Metadata:")
        import json
        print(json.dumps(db, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Failed to retrieve database: {e}")

    # 3. Try query
    print("\n--- Testing Query ---")
    try:
        client.databases.query(database_id=db_id, page_size=1)
        print("✅ Query method exists and works")
    except AttributeError:
        print("❌ client.databases.query does NOT exist")
    except Exception as e:
        print(f"❌ Query failed with other error: {e}")

if __name__ == "__main__":
    main()
