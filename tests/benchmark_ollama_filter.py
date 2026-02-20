import time
import os
import sys
import unittest.mock

# Simulate cloud or higher concurrency environment
os.environ["KIMI_MAX_CONCURRENCY"] = "4"
os.environ["API_PROVIDER"] = "NVIDIA" # Try to force cloud provider logic if config reloads?

# Ensure src is in path for imports to work. MUST be before imports from src.
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.models import Article
from src.filters import ollama_filter
import logging

logging.basicConfig(level=logging.INFO)

# Helper to mock llm_relevance_check with delay
def mock_llm_check(article):
    time.sleep(0.1) # Simulate network delay
    # Deterministic behavior:
    # Articles with 'Important' in title -> True
    # Articles with 'Maybe' in title -> None
    # Others -> False
    title_lower = article.title.lower()
    if 'important' in title_lower:
        return True
    if 'maybe' in title_lower:
        return None
    return False

def run_benchmark():
    print("Preparing benchmark...")

    articles = []
    for i in range(10):
        if i < 4:
            title = f"Important Article {i}" # Expect True
        elif i < 7:
            title = f"Maybe Article {i}"    # Expect None
        else:
            title = f"Discard Article {i}" # Expect False

        articles.append(Article(
            title=title,
            source="Test Source",
            url=f"http://example.com/{i}",
            content_snippet="Test content snippet with keywords like AI and Simulation.",
            language="en",
            category="Test",
            published_date=None
        ))

    # Patch keyword_score to always return a high score so we hit the LLM check loop
    # We patch it on the module where it is defined/used.
    with unittest.mock.patch('src.filters.ollama_filter.keyword_score') as mock_kw:
        # Side effect: return (score, personas).
        # For 'Maybe' articles, we want score >= 2 to test the fallback logic.
        def kw_side_effect(article):
            score = 3 # High score
            if 'Maybe' in article.title:
                 score = 2
            return score, ['student']

        mock_kw.side_effect = kw_side_effect

        # Patch llm_relevance_check in the module
        with unittest.mock.patch('src.filters.ollama_filter.llm_relevance_check', side_effect=mock_llm_check) as mock_llm:

            print(f"Running filter_articles on {len(articles)} articles...")
            start_time = time.perf_counter()

            result = ollama_filter.filter_articles(articles, skip_llm=False)

            end_time = time.perf_counter()
            duration = end_time - start_time

            print(f"Time taken: {duration:.4f} seconds")
            print(f"Articles output: {len(result)}")
            print(f"Expected output count: 7. Actual: {len(result)}")

            # Verify mock was called correct number of times (10 times)
            print(f"Mock call count: {mock_llm.call_count}")

if __name__ == "__main__":
    run_benchmark()
