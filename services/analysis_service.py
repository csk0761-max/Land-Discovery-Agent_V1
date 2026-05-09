from typing import Dict, List, Optional, Any

from agent import agent_evaluate_parcel
from auto_search_agent import agent_auto_search
from services.gee_service import get_geo_intelligence_signals


def analyze_parcel(
    lat: float,
    lon: float,
    area_acres: float,
    polygon: Optional[List[List[float]]] = None,
    custom_prompt: Optional[str] = None,
    selected_layers: Optional[List[str]] = None,
    layer_thumbnails: Optional[Dict[str, str]] = None,
    gss_info: Optional[str] = None,
):
    # Fetch GEE-based raw geo-intelligence signals
    geo_signals = get_geo_intelligence_signals(lat, lon, polygon)

    report = agent_evaluate_parcel(
        lat,
        lon,
        area_acres,
        polygon,
        custom_prompt,
        selected_layers or [],
        layer_thumbnails or {},
        gss_info,
        geo_signals=geo_signals,
    )
    return {"report": report}


def auto_search(
    state: Optional[str],
    district: Optional[str],
    project_type: str,
    capacity_mw: float,
    area_acres: float,
    substation_query: Optional[str] = None,
    search_polygon: Optional[List[List[float]]] = None,
    weights: Optional[Dict[str, float]] = None,
):
    return agent_auto_search(
        state=state,
        district=district,
        project_type=project_type,
        capacity_mw=capacity_mw,
        area_acres=area_acres,
        substation_query=substation_query,
        search_polygon=search_polygon,
        weights=weights,
    )


