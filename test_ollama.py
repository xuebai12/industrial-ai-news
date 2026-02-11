import os
from openai import OpenAI

# Check environment for OLLAMA_MODEL or default
# You can set OLLAMA_MODEL=qwen2.5:32b in .env before running this
model = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
print(f"Testing local Ollama model: {model}")

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

try:
    print("Sending request...")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello! Reply in one sentence."}],
    )
    print("✅ Response received:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"❌ Error: {e}")
    print("Please make sure 'ollama serve' is running and you have pulled the model.")
