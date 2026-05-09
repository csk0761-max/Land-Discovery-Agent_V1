from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks, File, UploadFile
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from pydantic import BaseModel
import uvicorn
from typing import Optional, List, Dict, Any

from auth import require_admin, require_operator
from services.analysis_service import analyze_parcel as analyze_parcel_service
from services.analysis_service import auto_search as auto_search_service
from services.geo_service import (
    auto_find_gss as auto_find_gss_service,
    get_layer_thumbnail as get_layer_thumbnail_service,
    get_layer_tile as get_layer_tile_service,
    get_location as get_location_service,
    get_nearby_places as get_nearby_places_service,
    get_substations as get_substations_service,
    get_nearby_transmission_lines as get_nearby_transmission_lines_service,
    get_hydrology_analysis as get_hydrology_analysis_service,
)
from services.grid_service import (
    extract_and_store_grid_data,
    get_structured_substations,
    save_feedback,
    save_grid_intelligence,
)
import rag_manager
from services.supabase_service import supabase_service
from settings import get_settings

app = FastAPI(title="Land Discovery Agent API")
settings = get_settings()

# CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if os.getenv("FRONTEND_URL"):
    origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if os.getenv("FRONTEND_URL") else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ─── Parcel Analysis Models ────────────────────────────────────────────────
class ParcelQuery(BaseModel):
    lat: float
    lon: float
    area_acres: float
    polygon: Optional[List[List[float]]] = None
    custom_prompt: Optional[str] = None
    selected_layers: Optional[List[str]] = None
    layer_thumbnails: Optional[Dict[str, str]] = None
    gss_info: Optional[str] = None

class ParcelResponse(BaseModel):
    report: str

class TileUrlResponse(BaseModel):
    tileUrl: Optional[str] = None
    attribution: Optional[str] = None
    error: Optional[str] = None

class ThumbnailResponse(BaseModel):
    thumbnailUrl: Optional[str] = None
    label: Optional[str] = None
    error: Optional[str] = None




# ─── Auto Search Models ────────────────────────────────────────────────────
class AutoSearchQuery(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    project_type: str = 'solar'      # 'solar', 'wind', 'both'
    capacity_mw: float = 100.0
    area_acres: float = 500.0
    substation_query: Optional[str] = None
    search_polygon: Optional[List[List[float]]] = None
    weights: Optional[Dict[str, float]] = None

class AutoSearchResponse(BaseModel):
    report: str
    candidates: List[Dict[str, Any]] = []
    search_center: Dict[str, Any] = {}  # {lat, lon, radius_km, display_name}
    



# ─── HITL Feedback Models ──────────────────────────────────────────────────
class FeedbackItem(BaseModel):
    context: str
    correction: str

class GridIntelligenceItem(BaseModel):
    substation_name: str
    intelligence_text: str

# ─── Layer Endpoints ───────────────────────────────────────────────────────
@app.get("/layers/{layer_id}/tile-url", response_model=TileUrlResponse)
def get_layer_tile_url(layer_id: str, lat: float, lon: float, area_acres: float = 100):
    result = get_layer_tile_service(layer_id, lat, lon, area_acres)
    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])
    return TileUrlResponse(tileUrl=result.get('tileUrl'), attribution=result.get('attribution'))


@app.get("/layers/{layer_id}/thumbnail", response_model=ThumbnailResponse)
def get_layer_thumbnail(layer_id: str, lat: float, lon: float, area_acres: float = 100):
    result = get_layer_thumbnail_service(layer_id, lat, lon, area_acres)
    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])
    return ThumbnailResponse(thumbnailUrl=result.get('thumbnailUrl'), label=result.get('label'))


# ─── Substations Endpoint ──────────────────────────────────────────────────
class SubstationResponse(BaseModel):
    name: str
    lat: float
    lon: float
    distance_km: float
    voltage: Optional[str] = None
    capacity_mw: Optional[int] = None


class AutoGssFinderQuery(BaseModel):
    lat: float
    lon: float
    radius_km: int = 25


class AutoGssFinderResult(BaseModel):
    name: str
    lat: float
    lon: float
    distance_km: float
    voltage_level: str = "unknown"
    data_source: str
    confidence_level: str
    verification_status: str
    available_capacity_mw: Optional[float] = None
    bay_status: Optional[str] = None


class AutoGssFinderSummary(BaseModel):
    nearest_gss_name: Optional[str] = None
    distance_km: Optional[float] = None
    voltage_level: Optional[str] = None
    risk_remark: str
    next_action: str


class AutoGssFinderResponse(BaseModel):
    center: Dict[str, float]
    radius_km: float
    source_mode: str
    results: List[AutoGssFinderResult]
    summary: AutoGssFinderSummary

@app.get("/find-substations", response_model=List[SubstationResponse])
def find_substations(lat: float, lon: float, radius_m: int = 20000):
    try:
        return get_substations_service(lat, lon, radius_m)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gss/auto-finder", response_model=AutoGssFinderResponse)
def auto_gss_finder(query: AutoGssFinderQuery):
    try:
        return AutoGssFinderResponse(**auto_find_gss_service(query.lat, query.lon, query.radius_km * 1000))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/location-details")
async def location_details_endpoint(lat: float, lon: float):
    return await get_location_service(lat, lon)

@app.get("/api/nearby-places")
async def nearby_places_endpoint(lat: float, lon: float, radius_m: int = 5000):
    try:
        return get_nearby_places_service(lat, lon, radius_m)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.get("/api/transmission-lines")
async def transmission_lines_endpoint(lat: float, lon: float, radius_m: int = 15000):
    try:
        print(f"Backend: 🛰️ Fetching fused transmission lines for ({lat}, {lon})")
        data = get_nearby_transmission_lines_service(lat, lon, radius_m)
        lines_count = len(data.get("lines", []))
        print(f"Backend: ✅ Found {lines_count} power lines across multiple sources.")
        return data
    except Exception as e:
        print(f"Backend: ❌ Transmission Line Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hydrology-risk")
async def hydrology_risk_endpoint(lat: float, lon: float, area: float = 100):
    try:
        return get_hydrology_analysis_service(lat, lon, area)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





# ─── Parcel Analysis Endpoint ──────────────────────────────────────────────
@app.post("/analyze", response_model=ParcelResponse)
def analyze_parcel(query: ParcelQuery, _: None = Depends(require_operator)):
    try:
        result = analyze_parcel_service(
            query.lat,
            query.lon,
            query.area_acres,
            query.polygon,
            query.custom_prompt,
            query.selected_layers or [],
            query.layer_thumbnails or {},
            query.gss_info,
        )
        return ParcelResponse(report=result["report"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Auto Search Endpoint ──────────────────────────────────────────────────
@app.post("/auto-search", response_model=AutoSearchResponse)
def auto_search(query: AutoSearchQuery, _: None = Depends(require_operator)):
    """
    Automatically screens a search area for optimal solar/wind project sites.
    Uses OSM Nominatim to resolve State/District -> Coordinates & bounds.
    Uses GEE grid scoring + OSM substation finding + Gemini AI ranked report.
    """
    try:
        result = auto_search_service(
            state=query.state,
            district=query.district,
            project_type=query.project_type,
            capacity_mw=query.capacity_mw,
            area_acres=query.area_acres,
            substation_query=query.substation_query,
            search_polygon=query.search_polygon,
            weights=query.weights,
        )
        return AutoSearchResponse(
            report=result.get('report', ''),
            candidates=result.get('candidates', []),
            search_center=result.get('search_center', {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# ─── HITL Feedback Endpoint ────────────────────────────────────────────────
@app.post("/feedback")
async def submit_feedback(item: FeedbackItem, _: None = Depends(require_admin)):
    try:
        return save_feedback(item.context, item.correction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-intelligence")
async def upload_intelligence(item: GridIntelligenceItem, _: None = Depends(require_admin)):
    try:
        return save_grid_intelligence(item.substation_name, item.intelligence_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Grid Mapping Engine Endpoints ─────────────────────────────────────────

class GridExtractionQuery(BaseModel):
    text: str


@app.post("/api/grid-engine/extract")
async def extract_grid_data_api(query: GridExtractionQuery, _: None = Depends(require_admin)):
    result = extract_and_store_grid_data(query.text)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@app.get("/api/grid-engine/substations")
async def get_grid_engine_substations():
    try:
        return get_structured_substations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Storage Endpoints ─────────────────────────────────────────────────────

@app.post("/api/storage/upload")
async def upload_file_to_supabase(
    bucket: str, 
    path: str, 
    file: UploadFile = File(...), 
    _: None = Depends(require_operator)
):
    try:
        content = await file.read()
        result = supabase_service.upload_file(
            bucket=bucket, 
            path=path, 
            file_content=content, 
            content_type=file.content_type
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to upload to Supabase Storage")
        return {"success": True, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Static Files / Frontend ───────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
