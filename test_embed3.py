import os
from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
try:
    response = client.models.embed_content(
        model='gemini-embedding-001',
        contents="Hello"
    )
    print("Success:", response)
    if hasattr(response, 'embeddings') and response.embeddings:
        print("Values:", response.embeddings[0].values[:5]) # print first 5
except Exception as e:
    print("Error:", e)
