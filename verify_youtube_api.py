import os
import logging
from dotenv import load_dotenv
from src.scrapers.youtube_scraper import scrape_youtube

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()

def test_youtube():
    print("--- Testing YouTube API ---")
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("❌ Error: YOUTUBE_API_KEY not found in environment.")
        return

    print(f"API Key found: {api_key[:5]}...")
    
    query = "Industrial AI"
    print(f"Searching for: '{query}'...")
    
    try:
        videos = scrape_youtube(
            name="Test Source",
            url=query,
            language="en",
            category="industry",
            max_items=1
        )
        
        if videos:
            v = videos[0]
            print("\n✅ Success! Found video:")
            print(f"Title: {v.title}")
            print(f"URL:   {v.url}")
            print(f"Date:  {v.published_date}")
            print("-" * 30)
        else:
            print("\n⚠️  No videos found (Check if API quota is exceeded or filters are too strict).")
            
    except Exception as e:
        print(f"\n❌ Error calling API: {e}")

if __name__ == "__main__":
    test_youtube()
