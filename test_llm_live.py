import sys
import os
import json
from src.models import Article
from src.analyzers.llm_analyzer import analyze_article
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_prompt():
    print("--- Testing Technician Persona (Live API Call) ---")
    
    # 1. Create a dummy article with TECHNICIAN keywords
    article = Article(
        title="Predictive Maintenance for Siemens S7-1500 PLCs Using Edge Computing",
        url="https://example.com/test-technician",
        source="TechBlog Test",
        content_snippet="""
        In modern factories, unintended downtime is a major cost factor. 
        Maintenance technicians often struggle with reactive repairs on Siemens S7-1500 PLCs. 
        By implementing an Edge Computing layer, we can monitor PLC cycle times and memory usage in real-time via TIA Portal. 
        This data allows for predictive maintenance (Vorausschauende Wartung), significantly improving OEE. 
        The secure integration ensures that safety protocols (Sicherheit) are not compromised during data extraction.
        """,
        language="en",
        category="Industry 4.0",
        target_personas=["technician"] # Manually tag for test
    )

    print(f"Article: {article.title}")
    print(f"Target Personas: {article.target_personas}")
    print("Sending to LLM API... (This may take 10-20 seconds)")

    # 2. Call the real analysis function (mock=False to use real API)
    try:
        analyzed = analyze_article(article, mock=False)
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return

    if not analyzed:
        print("❌ Analysis failed (returned None).")
        return

    # 3. Print the result
    print("\n" + "="*60)
    print("✅ Analysis Result:")
    print("="*60)
    print(f"Title (ZH): {analyzed.title_zh}")
    print(f"Category:   {analyzed.category_tag}")
    print("-" * 20)
    print(f"💡 [Student View / Simple Explanation]:\n{analyzed.simple_explanation}")
    print("-" * 20)
    print(f"🔧 [Technician View / DE Analysis]:\n{analyzed.technician_analysis_de}")
    print("-" * 20)
    print(f"Tool Stack: {analyzed.tool_stack}")
    print("="*60)

if __name__ == "__main__":
    test_prompt()
