import json
import logging
import math
import os
import sqlite3
from pathlib import Path
from typing import Dict, List

from openai import OpenAI
from dotenv import load_dotenv
from services.supabase_service import supabase_service

load_dotenv()

_openai_client: OpenAI = None

def _get_openai_client() -> OpenAI:
    """Return a cached OpenAI client, initializing it lazily on first use.

    Deferring initialization until the key is actually needed allows the
    service to start successfully even when OPENAI_API_KEY has not been
    injected into the environment yet (e.g. during a cold Railway deploy
    before secrets are propagated).
    """
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please configure it in your Railway service variables."
            )
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_DB_PATH = "rag_store.sqlite3"
DEFAULT_LEGACY_DB_FILE = "rag_db.json"


def _db_path() -> str:
    return os.getenv("AUXILIUM_RAG_DB_PATH", DEFAULT_DB_PATH)


def _legacy_db_path() -> str:
    return os.getenv("AUXILIUM_LEGACY_RAG_JSON_PATH", DEFAULT_LEGACY_DB_FILE)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _create_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context TEXT NOT NULL,
            correction TEXT NOT NULL,
            embedding TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS grid_intelligence_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gss_name TEXT NOT NULL,
            intelligence TEXT NOT NULL,
            embedding TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structured_gss_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS strategic_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL,
            lon REAL,
            location_name TEXT,
            insight TEXT NOT NULL,
            embedding TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _load_legacy_db() -> List[Dict]:
    legacy_path = Path(_legacy_db_path())
    if not legacy_path.exists():
        return []
    try:
        with legacy_path.open("r") as handle:
            return json.load(handle)
    except Exception as exc:
        logging.error(f"Failed to load legacy RAG DB: {exc}")
        return []


def _is_migrated(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = 'legacy_json_migrated'"
    ).fetchone()
    return row is not None and row["value"] == "1"


def _mark_migrated(conn: sqlite3.Connection):
    conn.execute(
        """
        INSERT INTO metadata(key, value)
        VALUES('legacy_json_migrated', '1')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
    )
    conn.commit()


def _migrate_legacy_json_if_needed(conn: sqlite3.Connection):
    if _is_migrated(conn):
        return

    legacy_entries = _load_legacy_db()
    for entry in legacy_entries:
        if entry.get("type") == "grid_intelligence":
            conn.execute(
                """
                INSERT INTO grid_intelligence_entries(gss_name, intelligence, embedding)
                VALUES (?, ?, ?)
                """,
                (
                    entry.get("gss_name", ""),
                    entry.get("intelligence", ""),
                    json.dumps(entry.get("embedding", [])),
                ),
            )
        elif entry.get("type") == "structured_gss":
            payload = dict(entry)
            payload.pop("type", None)
            conn.execute(
                "INSERT INTO structured_gss_entries(payload) VALUES (?)",
                (json.dumps(payload),),
            )
        elif "context" in entry and "correction" in entry:
            conn.execute(
                """
                INSERT INTO feedback_entries(context, correction, embedding)
                VALUES (?, ?, ?)
                """,
                (
                    entry.get("context", ""),
                    entry.get("correction", ""),
                    json.dumps(entry.get("embedding", [])),
                ),
            )

    _mark_migrated(conn)


def _initialize_db():
    conn = _connect()
    try:
        _create_schema(conn)
        _migrate_legacy_json_if_needed(conn)
    finally:
        conn.close()


def get_embedding(text: str) -> List[float]:
    try:
        response = _get_openai_client().embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding
    except Exception as exc:
        logging.error(f"Failed to get embedding: {exc}")
        return []


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _parse_embedding(value: str) -> List[float]:
    try:
        return json.loads(value)
    except Exception:
        return []


def add_feedback(context: str, correction: str) -> bool:
    full_text = f"Context: {context}\nFeedback/Rule: {correction}"
    embedding = get_embedding(full_text)
    if not embedding:
        raise ValueError("Could not generate embedding for the feedback.")

    conn = _connect()
    try:
        _create_schema(conn)
        _migrate_legacy_json_if_needed(conn)
        conn.execute(
            """
            INSERT INTO feedback_entries(context, correction, embedding)
            VALUES (?, ?, ?)
            """,
            (context, correction, json.dumps(embedding)),
        )
        conn.commit()
    finally:
        conn.close()
    
    # Sync with Supabase
    try:
        supabase_service.add_feedback(context, correction, embedding)
    except Exception as e:
        logging.error(f"Failed to sync feedback to Supabase: {e}")
        
    return True


def retrieve_relevant_context(query: str, top_k: int = 2) -> List[Dict]:
    _initialize_db()
    query_emb = get_embedding(query)
    if not query_emb:
        return []

    # 1. Try Supabase Vector Search first
    try:
        supabase_results = supabase_service.search_relevant_context(query_emb, threshold=0.55, count=top_k)
        if supabase_results:
            return supabase_results
    except Exception as e:
        logging.error(f"Supabase Vector retrieval failed: {e}")

    # 2. Fallback to local SQLite Search
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT context, correction, embedding, created_at
            FROM feedback_entries
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    threshold = 0.55
    results = []
    for row in rows:
        embedding = _parse_embedding(row["embedding"])
        sim = cosine_similarity(query_emb, embedding)
        if sim > threshold:
            results.append(
                (
                    sim,
                    {
                        "context": row["context"],
                        "correction": row["correction"],
                        "created_at": row["created_at"],
                    },
                )
            )

    results.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in results[:top_k]]


def add_grid_intelligence(gss_name: str, intelligence: str) -> bool:
    full_text = f"Substation Intelligence: {gss_name}\nData: {intelligence}"
    embedding = get_embedding(full_text)
    if not embedding:
        raise ValueError("Could not generate embedding.")

    conn = _connect()
    try:
        _create_schema(conn)
        _migrate_legacy_json_if_needed(conn)
        conn.execute(
            """
            INSERT INTO grid_intelligence_entries(gss_name, intelligence, embedding)
            VALUES (?, ?, ?)
            """,
            (gss_name, intelligence, json.dumps(embedding)),
        )
        conn.commit()
    finally:
        conn.close()
    
    # Sync with Supabase
    try:
        supabase_service.add_grid_intelligence(gss_name, intelligence, embedding)
    except Exception as e:
        logging.error(f"Failed to sync grid intelligence to Supabase: {e}")
        
    return True


def retrieve_grid_intelligence(gss_name: str, top_k: int = 2) -> List[Dict]:
    _initialize_db()
    query_emb = get_embedding(f"Substation Intelligence for {gss_name}")
    if not query_emb:
        return []

    # 1. Try Supabase Vector Search first
    try:
        supabase_results = supabase_service.search_grid_intelligence(query_emb, threshold=0.50, count=top_k)
        if supabase_results:
            return supabase_results
    except Exception as e:
        logging.error(f"Supabase Grid Intel Vector retrieval failed: {e}")

    # 2. Fallback to local SQLite Search
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT gss_name, intelligence, embedding, created_at
            FROM grid_intelligence_entries
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    threshold = 0.50
    results = []
    for row in rows:
        embedding = _parse_embedding(row["embedding"])
        sim = cosine_similarity(query_emb, embedding)
        if sim > threshold:
            results.append(
                (
                    sim,
                    {
                        "gss_name": row["gss_name"],
                        "intelligence": row["intelligence"],
                        "created_at": row["created_at"],
                    },
                )
            )

    results.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in results[:top_k]]


def add_structured_gss_data(data: dict) -> bool:
    payload = dict(data)
    payload.pop("type", None)

    conn = _connect()
    try:
        _create_schema(conn)
        _migrate_legacy_json_if_needed(conn)
        conn.execute(
            "INSERT INTO structured_gss_entries(payload) VALUES (?)",
            (json.dumps(payload),),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def retrieve_all_structured_gss_data() -> List[Dict]:
    _initialize_db()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT payload
            FROM structured_gss_entries
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(row["payload"]) for row in rows]


def add_strategic_insight(lat: float, lon: float, location_name: str, insight: str) -> bool:
    full_text = f"Location: {location_name} ({lat}, {lon})\nStrategic Insight: {insight}"
    embedding = get_embedding(full_text)
    if not embedding:
        raise ValueError("Could not generate embedding for the insight.")

    conn = _connect()
    try:
        _create_schema(conn)
        conn.execute(
            """
            INSERT INTO strategic_insights(lat, lon, location_name, insight, embedding)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lat, lon, location_name, insight, json.dumps(embedding)),
        )
        conn.commit()
    finally:
        conn.close()

    # Sync with Supabase
    try:
        supabase_service.add_strategic_insight(lat, lon, location_name, insight, embedding)
    except Exception as e:
        logging.error(f"Failed to sync strategic insight to Supabase: {e}")

    return True


def retrieve_strategic_insights(query: str, lat: float = None, lon: float = None, top_k: int = 3) -> List[Dict]:
    _initialize_db()
    
    search_text = query
    if lat is not None and lon is not None:
        search_text = f"Insights near {lat}, {lon}: {query}"
        
    query_emb = get_embedding(search_text)
    if not query_emb:
        return []

    # 1. Try Supabase first
    try:
        supabase_results = supabase_service.search_strategic_insights(query_emb, threshold=0.50, count=top_k)
        if supabase_results:
            return supabase_results
    except Exception as e:
        logging.error(f"Supabase Strategic Insight retrieval failed: {e}")

    # 2. Local SQLite fallback
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT lat, lon, location_name, insight, embedding, created_at
            FROM strategic_insights
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    threshold = 0.50
    results = []
    for row in rows:
        embedding = _parse_embedding(row["embedding"])
        sim = cosine_similarity(query_emb, embedding)
        
        # Boost similarity if it's very close geographically (within ~50km)
        geo_boost = 0.0
        if lat is not None and lon is not None and row["lat"] is not None and row["lon"] is not None:
            dist = math.sqrt((lat - row["lat"])**2 + (lon - row["lon"])**2)
            if dist < 0.5: # Approx 50km
                geo_boost = 0.1
        
        if (sim + geo_boost) > threshold:
            results.append(
                (
                    sim + geo_boost,
                    {
                        "lat": row["lat"],
                        "lon": row["lon"],
                        "location_name": row["location_name"],
                        "insight": row["insight"],
                        "created_at": row["created_at"],
                    },
                )
            )

    results.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in results[:top_k]]


_initialize_db()
