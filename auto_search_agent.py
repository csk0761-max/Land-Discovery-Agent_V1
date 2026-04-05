"""
auto_search_agent.py
Orchestrates the Auto Search Land with AI pipeline:
1. Scores candidate grid sites using GEE
2. Finds nearest substations via OSM
3. Estimates transmission routes
4. Generates a Gemini AI ranked report
"""
import requests
import math
import datetime
from google import genai
from concurrent.futures import ThreadPoolExecutor
from auto_search_tools import (
    score_search_area,
    get_candidate_substation,
    estimate_transmission_route,
    get_all_substations_in_area
)
import rag_manager

import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def _get_nominatim_bounds(state: str, district: str = None):
    """
    Queries OSM Nominatim to find the lat, lon, and compute a radius_km
    for the given state and (optional) district.
    """
    query_parts = []
    if district:
        query_parts.append(district)
    query_parts.append(state)
    query_parts.append("India")
    
    q = ", ".join(query_parts)
    print(f"Auto Search Geocoding: {q}")
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': q,
        'format': 'json',
        'limit': 1
    }
    headers = {'User-Agent': 'RenewableEnergyLandDiscoveryAgent/1.0'}
    
    try:
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        
        place = data[0]
        lat = float(place['lat'])
        lon = float(place['lon'])
        
        # boundingbox is [south, north, west, east]
        bbox = [float(x) for x in place['boundingbox']]
        
        # calculate rough radius from center to corner
        # Using simple haversine approximation
        lat1, lon1 = lat, lon
        lat2, lon2 = bbox[1], bbox[3] # north, east corner
        
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        radius_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        # Cap radius to avoid massive GEE queries if they just select a whole state
        if radius_km > 150:
            print(f"Capping radius from {radius_km}km to 150km to stay within GEE quotas.")
            radius_km = 150.0
            
        return {
            'lat': lat,
            'lon': lon,
            'radius_km': round(radius_km, 1),
            'display_name': place.get('display_name', q)
        }
    except Exception as e:
        print(f"Nominatim error: {e}")
        return None


def agent_auto_search(
    state: str,
    district: str,
    project_type: str,    # 'solar', 'wind', 'both'
    capacity_mw: float,
    area_acres: float,
    substation_query: str = None,
    search_polygon: list = None,
    weights: dict = None,
    top_n: int = 8,
) -> dict:
    """
    Runs the full auto-search pipeline and returns:
    - 'report': AI markdown report
    - 'candidates': list of scored site dicts (with substation + transmission data)
    - 'search_center': {lat, lon, radius_km, display_name}
    """
    print(f"Auto Search Agent: Starting search — {project_type.upper()} {capacity_mw}MW in {district or ''} {state}")

    # Step 0: Resolve state/district to lat, lon, radius via OSM or Polygon
    if search_polygon and len(search_polygon) >= 3:
        lats = [p[0] for p in search_polygon]
        lons = [p[1] for p in search_polygon]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        radius_km = 10.0 # Bounding approx default
        location_name = "Custom Polygon Search Area"
        center_data = {'lat': center_lat, 'lon': center_lon, 'radius_km': radius_km, 'display_name': location_name}
    else:
        center_data = _get_nominatim_bounds(state, district)
        if not center_data:
            return {
                'report': f"**Error:** Could not locate '{district or ''} {state}' via OSM Geocoding. Please check the spelling.",
                'candidates': [],
                'search_center': {}
            }
        
        center_lat = center_data['lat']
        center_lon = center_data['lon']
        radius_km = center_data['radius_km']
        location_name = center_data['display_name']
    
    print(f"Resolved to {location_name} at ({center_lat}, {center_lon}) with radius {radius_km}km")

    # Step 1: Score the search area
    raw_candidates = score_search_area(
        center_lat, center_lon, radius_km, project_type, area_acres,
        search_polygon=search_polygon, weights=weights, top_n=top_n
    )

    if not raw_candidates:
        return {
            'report': "**No viable candidates found** in the specified region. "
                      "Try adjusting the project parameters or target area.",
            'candidates': [],
            'search_center': center_data
        }

    # Step 2: For each top candidate, find nearest substation + estimate transmission
    print("  → Initiating parallel substation bounds & transmission routing...")
    
    # BULK FETCH: Get all substations in the region ONCE to bypass Overpass API throttling/latency
    search_radius_m = int((radius_km + 40) * 1000)
    print(f"  → Bulk fetching substations for entire {radius_km}km region around center...")
    all_subs_in_region = get_all_substations_in_area(center_lat, center_lon, search_radius_m)

    def enrich_candidate(c):
        sub = get_candidate_substation(c['lat'], c['lon'], preferred_name=substation_query, pre_fetched_subs=all_subs_in_region)
        route = estimate_transmission_route(c['lat'], c['lon'], sub.get('lat'), sub.get('lon'))
        return {**c, 'substation': sub, 'transmission': route}

    with ThreadPoolExecutor(max_workers=8) as executor:
        enriched = list(executor.map(enrich_candidate, raw_candidates))

    # Step 3: Build Gemini prompt
    # RAG Retrieval
    try:
        rag_query = f"Auto search for {project_type} in {district or ''} {state}. Capacity {capacity_mw}MW."
        print(f"  → Querying AI Memory (RAG) for past expert feedback...")
        past_feedback = rag_manager.retrieve_relevant_context(rag_query, top_k=2)
    except Exception as e:
        print(f"  → RAG Retrieval Error: {e}")
        past_feedback = []

    project_label = {'solar': 'Solar PV', 'wind': 'Wind', 'both': 'Solar & Wind Hybrid'}[project_type]
    resource_label = 'Solar GHI (kWh/m²/day)' if project_type in ('solar', 'both') else 'Wind Speed (m/s)'

    site_rows = []
    for c in enriched:
        sub = c['substation']
        tx = c['transmission']
        resource_val = c['ghi'] if project_type == 'solar' else c['wind']
        site_rows.append(
            f"| #{c['rank']} | {c['lat']}, {c['lon']} | {c['score']}/100 | "
            f"{c['slope']}° | {c['land_type']} | {resource_val} | "
            f"{sub.get('name', 'N/A')} | {sub.get('distance_km', 'N/A')} km | "
            f"{tx.get('distance_km', 'N/A')} km | {tx.get('difficulty', 'N/A')} |"
        )

    site_table = "\n".join(site_rows)
    current_time_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Financial estimates
    avg_ghi = sum(c['ghi'] for c in enriched) / len(enriched) if enriched else 5.0
    est_annual_generation_mwh = avg_ghi * 365 * capacity_mw * 1000 * 0.15 # 15% PR
    est_capex = capacity_mw * 1000000 * 0.75 # ~$0.75/W utility solar

    prompt = f"""
You are an expert renewable energy developer's GIS analyst. A client has requested an automated site screening report for a **{project_label} project** with the following parameters:

- **Report Generated On**: {current_time_str}
- **Project Type**: {project_label}
- **Target Capacity**: {capacity_mw} MW
- **Minimum Area Required**: {area_acres} acres per site
- **Search Region**: {location_name}
- **Resolved Centre Point**: {center_lat}°N, {center_lon}°E
- **Search Radius Assessed**: {radius_km} km
- **Preferred Substation** (if any): {substation_query or 'No preference — nearest substation used'}

Our GIS engine has algorithmically screened the entire search area and identified {len(enriched)} candidate sites. The scoring methodology weights: Slope (30%), Land Cover (25%), {resource_label} Resource (25%), Environmental Protection Status (20%).

**Candidate Site Data:**

| Rank | Coordinates | Score | Slope | Land Type | Resource | Nearest Substation | Sub Dist | Tx Length | Terrain |
|------|-------------|-------|-------|-----------|----------|--------------------|----------|-----------|---------| 
{site_table}

**YOUR TASK — Generate a professional "Auto Site Screening Report" with the following structure:**

## 🎯 Executive Summary
Briefly summarise the screening outcome, how many viable sites were found and the general suitability of the region.

## 💰 Financial Viability Overview
Use the provided capacity and these mathematical projections to summarize the financial scale of the developer's target project:
- **Estimated Annual Yield**: ~{int(est_annual_generation_mwh):,} MWh/year (assuming 15% system efficiency and the region's {avg_ghi:.2f} kWh/m²/day average).
- **Estimated Generic CAPEX**: ~${int(est_capex):,} USD (assuming industry average $0.75/W utility-scale).
Provide brief comments on how the identified terrain difficulty or transmission line lengths might increase this baseline CAPEX.

## 🏆 Top 3 Recommended Sites
For each of the top 3 ranked sites provide a dedicated sub-section with:
- **Location**: Coordinates
- **Score**: X/100
- **Nearest Substation**: **[State the exact substation name from the data]** — distance in km
- **Why recommended**: Specific data-driven justifications (slope, land type, resource value)
- **Key advantage**: The single biggest strength
- **Key risk**: The most significant challenge
- **Power Evacuation Route**: Specific commentary on the named substation, estimated Tx line length, and terrain difficulty

## 📊 Full Candidate Comparison Table
Re-present the data table above with an added "Recommendation" column (Highly Recommended / Recommended / Conditional / Not Recommended).

## ⚡ Power Evacuation Strategy
List each unique substation identified in the candidate data by name. Discuss the overall grid infrastructure in this search area, typical Tx voltage levels needed for {capacity_mw} MW, and which named substation(s) are most strategically valuable for power evacuation.

## 🛣️ Transmission Routing Observations
Highlight any terrain challenges or opportunities for the transmission corridors identified.

## 📋 Next Steps for Due Diligence
Provide a numbered list of 5–7 specific next steps (ground-truthing, regulatory checks, grid connectivity studies, substation capacity confirmation etc.).

Be highly specific, data-driven, and professional. Always refer to substations by their exact names from the data.
"""

    if past_feedback:
        feedback_str = "\n".join([f"- **Expert Context**: {fb['context']}\n  **Rule/Correction**: {fb['correction']}" for fb in past_feedback])
        prompt += f"\n\n### CRITICAL AI MEMORY: PAST HUMAN EXPERT FEEDBACK (RAG)\nWhen screening these sites, you MUST adhere to the following human-verified rules and past corrections if they apply to the current context:\n{feedback_str}\nExplicitly mention in the report how this past expert feedback influenced your recommendations."

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt],
        )
        report = response.text
    except Exception as e:
        report = f"Error generating AI report: {e}"

    return {
        'report': report,
        'candidates': enriched,
        'search_center': center_data
    }
