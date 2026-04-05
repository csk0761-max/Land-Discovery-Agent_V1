from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from typing import Optional, List, Dict, Any

from agent import agent_evaluate_parcel
from tools import get_gee_tile_url, get_layer_thumbnail_url
from auto_search_agent import agent_auto_search
from auto_search_tools import get_all_substations_in_area, _haversine
import rag_manager
import revenue_tools

app = FastAPI(title="Land Discovery Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
async def get_layer_tile_url(layer_id: str, lat: float, lon: float, area_acres: float = 100):
    result = get_gee_tile_url(layer_id, lat, lon, area_acres)
    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])
    return TileUrlResponse(tileUrl=result.get('tileUrl'), attribution=result.get('attribution'))


@app.get("/layers/{layer_id}/thumbnail", response_model=ThumbnailResponse)
async def get_layer_thumbnail(layer_id: str, lat: float, lon: float, area_acres: float = 100):
    result = get_layer_thumbnail_url(layer_id, lat, lon, area_acres)
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

@app.get("/find-substations", response_model=List[SubstationResponse])
async def find_substations(lat: float, lon: float, radius_m: int = 20000):
    try:
        subs = get_all_substations_in_area(lat, lon, radius_m)
        enriched = []
        for s in subs:
            dist = _haversine(lat, lon, s['lat'], s['lon'])
            enriched.append({
                'name': s['name'],
                'lat': s['lat'],
                'lon': s['lon'],
                'distance_km': round(dist, 2),
                'voltage': s.get('voltage', ''),
                'capacity_mw': s.get('capacity_mw', 50)
            })
        # Sort by proximity
        enriched.sort(key=lambda x: x['distance_km'])
        return enriched
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/location-details")
async def location_details(lat: float, lon: float):
    try:
        from tools import get_location_details
        return get_location_details(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/revenue/wms-config")
async def get_wms_config(state: str = 'Rajasthan'):
    return revenue_tools.get_wms_config(state)


@app.get("/revenue/plot-info")
async def get_plot_info(lat: float, lon: float, state: str = 'Rajasthan'):
    try:
        return revenue_tools.get_plot_owner_info(lat, lon, state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Parcel Analysis Endpoint ──────────────────────────────────────────────
@app.post("/analyze", response_model=ParcelResponse)
async def analyze_parcel(query: ParcelQuery):
    try:
        report = agent_evaluate_parcel(
            query.lat, query.lon, query.area_acres,
            query.polygon, query.custom_prompt,
            query.selected_layers or [],
            query.layer_thumbnails or {},
            query.gss_info
        )
        return ParcelResponse(report=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Auto Search Endpoint ──────────────────────────────────────────────────
@app.post("/auto-search", response_model=AutoSearchResponse)
async def auto_search(query: AutoSearchQuery):
    """
    Automatically screens a search area for optimal solar/wind project sites.
    Uses OSM Nominatim to resolve State/District -> Coordinates & bounds.
    Uses GEE grid scoring + OSM substation finding + Gemini AI ranked report.
    """
    try:
        result = agent_auto_search(
            state=query.state,
            district=query.district,
            project_type=query.project_type,
            capacity_mw=query.capacity_mw,
            area_acres=query.area_acres,
            substation_query=query.substation_query,
            search_polygon=query.search_polygon,
            weights=query.weights
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
async def submit_feedback(item: FeedbackItem):
    try:
        rag_manager.add_feedback(item.context, item.correction)
        return {"status": "success", "message": "Feedback securely saved to AI Memory for future analyses."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-intelligence")
async def upload_intelligence(item: GridIntelligenceItem):
    try:
        rag_manager.add_grid_intelligence(item.substation_name, item.intelligence_text)
        return {"status": "success", "message": f"Intelligence for {item.substation_name} embedded in proprietary vault."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
