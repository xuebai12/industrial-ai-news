
import os
import sys
from notion_client import Client
from pprint import pprint

# Load env vars manually since we might not be running via main.py
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
    
    # 1. Check database attributes
    print("\n--- Inspecting DatabasesEndpoint ---")
    print(dir(client.databases))
    
    # 2. Try to retrieve database info (schema)
    print(f"\n--- Retrieving Database {db_id} ---")
    try:
        db = client.databases.retrieve(database_id=db_id)
        print("✅ Database found!")
        print("Existing Properties:")
        pprint(db.get("properties", {}).keys())
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
