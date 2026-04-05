import os
from google import genai

import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Test 1: list models to see what embedding models are available
print("Available Embedding Models:")
for m in client.models.list():
    if 'embed' in m.name.lower() or 'embedding' in m.name.lower():
        print(f" - {m.name} supported methods: {m.supported_actions}")

print("\nTesting text-embedding-004 again...")
try:
    response = client.models.embed_content(
        model='text-embedding-004',
        contents="Hello"
    )
    print("Success with text-embedding-004")
except Exception as e:
    print("Error text-embedding-004:", e)
