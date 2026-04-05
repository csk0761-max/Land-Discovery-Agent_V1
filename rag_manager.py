import os
import json
import logging
import math
from typing import List, Dict
from google import genai

DB_FILE = "rag_db.json"
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
EMBEDDING_MODEL = 'gemini-embedding-001'

def _load_db() -> List[Dict]:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load RAG DB: {e}")
        return []

def _save_db(data: List[Dict]):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save RAG DB: {e}")

def get_embedding(text: str) -> List[float]:
    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text
        )
        return response.embeddings[0].values
    except Exception as e:
        logging.error(f"Failed to get embedding: {e}")
        return []

def add_feedback(context: str, correction: str) -> bool:
    """
    Saves the user feedback to the RAG database.
    Embeds a combination of the context and the correction to allow semantic retrieval.
    """
    full_text = f"Context: {context}\nFeedback/Rule: {correction}"
    embedding = get_embedding(full_text)
    
    if not embedding:
        raise ValueError("Could not generate embedding for the feedback.")
        
    db = _load_db()
    db.append({
        "context": context,
        "correction": correction,
        "embedding": embedding
    })
    _save_db(db)
    return True

def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    
    norm_a = math.sqrt(sum(x*x for x in a))
    norm_b = math.sqrt(sum(y*y for y in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)

def retrieve_relevant_context(query: str, top_k: int = 2) -> List[Dict]:
    """
    Finds the most relevant past human feedback using cosine similarity.
    """
    db = _load_db()
    if not db:
        return []
        
    query_emb = get_embedding(query)
    if not query_emb:
        return []
        
    results = []
    for entry in db:
        sim = cosine_similarity(query_emb, entry["embedding"])
        results.append((sim, entry))
        
    # Sort by similarity descending
    results.sort(key=lambda x: x[0], reverse=True)
    
    # Filter and return top_k based on arbitrary relevancy threshold
    threshold = 0.55
    top_results = [res[1] for res in results if res[0] > threshold]
    
    return top_results[:top_k]

def add_grid_intelligence(gss_name: str, intelligence: str) -> bool:
    """Saves proprietary grid feasibility documents/knowledge to the DB."""
    full_text = f"Substation Intelligence: {gss_name}\nData: {intelligence}"
    embedding = get_embedding(full_text)
    
    if not embedding:
        raise ValueError("Could not generate embedding.")
        
    db = _load_db()
    db.append({
        "type": "grid_intelligence",
        "gss_name": gss_name,
        "intelligence": intelligence,
        "embedding": embedding
    })
    _save_db(db)
    return True

def retrieve_grid_intelligence(gss_name: str, top_k: int = 2) -> List[Dict]:
    """Finds intelligence specifically for a matched or related GSS."""
    db = _load_db()
    if not db:
        return []
        
    query_emb = get_embedding(f"Substation Intelligence for {gss_name}")
    if not query_emb:
        return []
        
    results = []
    for entry in db:
        if entry.get("type") == "grid_intelligence":
            sim = cosine_similarity(query_emb, entry["embedding"])
            results.append((sim, entry))
            
    results.sort(key=lambda x: x[0], reverse=True)
    threshold = 0.50 # slightly lower to catch broader naming matches
    return [res[1] for res in results if res[0] > threshold][:top_k]

