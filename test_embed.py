import os
import sys

from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
EMBEDDING_MODEL = 'text-embedding-004'

text = "Hello world"
try:
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    )
    print("Success:", response)
    if hasattr(response, 'embeddings'):
        print("Embeddings:", response.embeddings)
    elif hasattr(response, 'embedding'):
        print("Embedding:", response.embedding)
    elif hasattr(response, 'values'):
         print("Values:", response.values)
    else:
        print("Dir:", dir(response))
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Error:", e)
