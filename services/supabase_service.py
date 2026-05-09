import os
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any

load_dotenv()

class SupabaseService:
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            self.client = None
            print("Supabase credentials not found. Supabase operations will be skipped.")
        else:
            self.client: Client = create_client(self.url, self.key)

    def is_available(self) -> bool:
        return self.client is not None


    # Feedback
    def add_feedback(self, context: str, correction: str, embedding: List[float] = None):
        if not self.is_available(): return
        data = {"context": context, "correction": correction}
        if embedding: data["embedding"] = embedding
        self.client.table("feedback_entries").insert(data).execute()

    # Grid Intelligence
    def add_grid_intelligence(self, gss_name: str, intelligence: str, embedding: List[float] = None):
        if not self.is_available(): return
        data = {"gss_name": gss_name, "intelligence": intelligence}
        if embedding: data["embedding"] = embedding
        self.client.table("grid_intelligence_entries").insert(data).execute()

    # Strategic Insights
    def add_strategic_insight(self, lat: float, lon: float, location_name: str, insight: str, embedding: List[float] = None):
        if not self.is_available(): return
        data = {
            "lat": lat, 
            "lon": lon, 
            "location_name": location_name, 
            "insight": insight
        }
        if embedding: data["embedding"] = embedding
        self.client.table("strategic_insights").insert(data).execute()

    # Analysis Reports
    def add_analysis_report(self, lat: float, lon: float, area_acres: float, report: str):
        if not self.is_available(): return
        self.client.table("analysis_reports").insert({
            "lat": lat,
            "lon": lon,
            "area_acres": area_acres,
            "report": report
        }).execute()

    # Storage Operations
    def upload_file(self, bucket: str, path: str, file_content: bytes, content_type: str = "application/octet-stream"):
        if not self.is_available(): return None
        try:
            # Overwrite if exists
            response = self.client.storage.from_(bucket).upload(
                path, 
                file_content, 
                file_options={"content-type": content_type, "upsert": "true"}
            )
            return response
        except Exception as e:
            print(f"Supabase Storage Upload Error: {e}")
            return None

    def get_file_url(self, bucket: str, path: str, expires_in: int = 3600):
        if not self.is_available(): return None
        try:
            response = self.client.storage.from_(bucket).create_signed_url(path, expires_in)
            return response.get("signedURL")
        except Exception as e:
            print(f"Supabase Storage URL Error: {e}")
            return None

    # Vector Search Operations
    def search_relevant_context(self, query_embedding: List[float], threshold: float = 0.5, count: int = 5):
        if not self.is_available(): return []
        try:
            response = self.client.rpc("match_feedback", {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": count
            }).execute()
            return response.data
        except Exception as e:
            print(f"Supabase Vector Search Error (Feedback): {e}")
            return []

    def search_grid_intelligence(self, query_embedding: List[float], threshold: float = 0.5, count: int = 5):
        if not self.is_available(): return []
        try:
            response = self.client.rpc("match_grid_intelligence", {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": count
            }).execute()
            return response.data
        except Exception as e:
            print(f"Supabase Vector Search Error (Grid Intel): {e}")
            return []

    def search_strategic_insights(self, query_embedding: List[float], threshold: float = 0.5, count: int = 5):
        if not self.is_available(): return []
        try:
            response = self.client.rpc("match_strategic_insights", {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": count
            }).execute()
            return response.data
        except Exception as e:
            print(f"Supabase Vector Search Error (Strategic Insights): {e}")
            return []

# Global instance
supabase_service = SupabaseService()
