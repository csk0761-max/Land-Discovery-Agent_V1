import os
import io
import json
import requests
import datetime
import textwrap
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import base64
import threading
import google.generativeai as genai

# Import our parcel analysis tools
from tools import calculate_polygon_area_acres, get_region_slope, get_land_cover_details, get_solar_and_wind_data, get_environmental_risk, get_grid_proximity_proxy, get_satellite_image_url, get_location_details, get_nearest_substation, calculate_financial_roi, get_layer_thumbnail_url, get_esg_environmental_baseline, get_hydrology_risk, calculate_grading_costs
import rag_manager
from crew_manager import run_premium_expert_analysis
from services.rules_service import check_deterministic_rules, verify_evidence_thresholds
from jsonschema import validate, ValidationError


load_dotenv()

# Configure Clients — initialized lazily so the service can start without the key present.
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

# GEE/Gemini setup (Optional fallback)
gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
else:
    gemini_model = None

REPORT_LAYER_NAMES = {
    'land_cover': 'ESA WorldCover Land Classification',
    'slope': 'USGS SRTM Terrain Slope',
    'surface_water': 'JRC Global Surface Water Occurrence',
    'ndvi': 'MODIS NDVI Vegetation Index',
    'nighttime_lights': 'NOAA VIIRS Nighttime Lights',
    'solar_ghi': 'ECMWF ERA5 Solar GHI Heatmap',
    'protected_areas': 'WCMC WDPA Protected Areas Boundaries',
}

SNAPSHOT_LAYER_NAMES = {
    'land_cover': 'Land Cover — ESA WorldCover 10m',
    'slope': 'Terrain Slope — USGS SRTM',
    'surface_water': 'Surface Water Occurrence — JRC',
    'ndvi': 'Vegetation Index (NDVI) — MODIS 2023',
    'nighttime_lights': 'Nighttime Lights — NOAA VIIRS 2023',
    'solar_ghi': 'Solar GHI — ECMWF ERA5-Land 2023',
    'protected_areas': 'Protected Areas — WCMC WDPA',
}


REPORT_SCHEMA = {
    "type": "object",
    "required": ["executive_summary", "sections", "risk_matrix", "financial_summary", "expert_verdict_summary"],
    "properties": {
        "executive_summary": {
            "type": "object",
            "required": ["verdict", "confidence", "ic_simulation", "thesis"],
            "properties": {
                "verdict": {"type": "string"},
                "confidence": {"type": "string"},
                "ic_simulation": {"type": "string"},
                "thesis": {"type": "string"}
            }
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "claims"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["observation", "citation", "confidence", "inference", "recommendation"]
                        }
                    }
                }
            }
        },
        "risk_matrix": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["category", "level", "observation", "impact", "mitigation"]
            }
        },
        "financial_summary": {
            "type": "object",
            "required": ["civil_capex", "gentie_capex", "commercial_outlook"]
        },
        "expert_verdict_summary": {"type": "string"}
    }
}


def _bounded_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _compute_project_suitability_score(slope: float, ghi: float, env_risk: bool, land_type: str, area_acres: float) -> int:
    score = 100
    score -= min(40, slope * 4)
    score += min(15, max(0, (ghi - 4.5) * 10))
    if env_risk:
        score -= 35
    if land_type in {"forest", "water", "wetland", "built-up"}:
        score -= 25
    elif land_type == "barren":
        score += 10
    if area_acres < 250:
        score -= 15
    return _bounded_score(score)


def build_parcel_analysis_context(
    *,
    lat: float,
    lon: float,
    area_acres: float,
    slope: float,
    land_type: str,
    has_forest: bool,
    ghi: float,
    wind: float,
    env_risk: bool,
    grid_dist: float,
    img_url: str,
    slope_heatmap: str,
    solar_heatmap: str,
    land_cover_map: str,
    gss_info: str,
    substation_dist: str,
    resource_data: dict,
    roi_data: dict,
    location_details: dict,
    esg_data: dict,
    hydrology: dict,
    grading: dict,
    geo_signals: dict = None,
    rules_data: dict = None,
):
    return {
        "site": {
            "coordinates": {"lat": lat, "lon": lon},
            "location": location_details.get("full_address", "Unknown Location"),
            "jurisdiction": {
                "village": location_details.get("village", "Unknown Village"),
                "tehsil": location_details.get("tehsil", "Unknown Tehsil"),
                "district": location_details.get("district", "Unknown District"),
                "state": location_details.get("state", "Unknown State"),
            },
            "area_acres": area_acres,
        },
        "technical": {
            "slope_deg": round(slope, 2),
            "land_type": land_type,
            "has_forest": has_forest,
            "solar_ghi_kwh_m2_day": round(ghi, 2),
            "wind_speed_m_s": round(wind, 2),
            "solar_resource_source": resource_data.get("source"),
            "solar_resource_detail": resource_data.get("source_detail"),
            "solar_resource_period": resource_data.get("period"),
            "solar_resource_basis": resource_data.get("spatial_basis"),
            "solar_resource_tier": resource_data.get("bankability_tier"),
            "environmental_risk": env_risk,
            "grid_proximity_proxy_km": grid_dist,
            "substation_reference": gss_info or substation_dist,
            "project_suitability_score": _compute_project_suitability_score(
                slope, ghi, env_risk, land_type, area_acres
            ),
        },
        "financial": {
            "estimated_capacity_mw": roi_data.get("capacity_mw"),
            "estimated_annual_yield_mwh": roi_data.get("annual_yield_mwh"),
            "estimated_annual_yield_mwh_p75": roi_data.get("annual_yield_mwh_p75"),
            "estimated_annual_yield_mwh_p90": roi_data.get("annual_yield_mwh_p90"),
            "estimated_capex_cr": roi_data.get("capex_cr"),
            "estimated_annual_revenue_lakhs": roi_data.get("revenue_annual_lakhs"),
            "simple_payback_years": roi_data.get("payback_years"),
            "simple_payback_years_p90": roi_data.get("payback_years_p90"),
            "specific_yield_kwh_kw_year": roi_data.get("specific_yield_kwh_kw_year"),
            "net_capacity_factor_pct": roi_data.get("net_capacity_factor_pct"),
            "resource_source": roi_data.get("resource_source"),
            "resource_period": roi_data.get("resource_period"),
            "bankability_tier": roi_data.get("bankability_tier"),
            "losses_assumption": roi_data.get("losses_assumption", {}),
            "currency": roi_data.get("currency", "INR"),
        },
        "raster_assets": {
            "satellite_image_url": img_url,
            "slope_heatmap_url": slope_heatmap,
            "solar_heatmap_url": solar_heatmap,
            "land_cover_map_url": land_cover_map,
        },
        "deterministic_rules": rules_data or {},
        "geo_intelligence": geo_signals or {},
        "environmental_esg": {
            "us_aqi": esg_data.get("us_aqi", "N/A"),
            "european_aqi": esg_data.get("european_aqi", "N/A"),
            "pm10_ug_m3": esg_data.get("pm10", "N/A"),
            "pm2_5_ug_m3": esg_data.get("pm2_5", "N/A"),
            "carbon_monoxide_ug_m3": esg_data.get("carbon_monoxide", "N/A"),
            "nitrogen_dioxide_ug_m3": esg_data.get("nitrogen_dioxide", "N/A"),
        },
        "premium_intelligence": {
            "hydrology": hydrology,
            "grading": grading,
        }
    }


def render_report_to_markdown(data: dict, context: dict, current_time_str: str) -> str:
    """
    Renders a beautiful markdown report from structured JSON data.
    """
    def _get(mapping, *keys, default="N/A"):
        current = mapping
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current

    site = context["site"]
    technical = context["technical"]
    raster_assets = context["raster_assets"]
    
    sections_md = ""
    for section in data.get("sections", []):
        claims_md = ""
        for claim in section.get("claims", []):
            claims_md += f"""
#### Claim: {_get(claim, 'observation')}
- **CITATION**: {_get(claim, 'citation')} [Confidence: {_get(claim, 'confidence')}]
- **INFERENCE**: {_get(claim, 'inference')}
- **RECOMMENDATION**: {_get(claim, 'recommendation')}
"""
        sections_md += f"""
### {_get(section, 'id')}. {_get(section, 'title')}
{claims_md}
"""

    risk_rows = ""
    for risk in data.get("risk_matrix", []):
        risk_rows += f"| {_get(risk, 'category')} | {_get(risk, 'level')} | {_get(risk, 'observation')} | {_get(risk, 'impact')} | {_get(risk, 'mitigation')} |\n"

    rules_list = context.get('deterministic_rules', {}).get('rules', [])
    rules_table_rows = "\n".join([f"| {r['name']} | {r['criteria']} | {r['value']} | **{r['status']}** | [GEE/OSM] |" for r in rules_list])

    key_metrics = [
        ("Parcel Size", f"{site.get('area_acres', 'N/A')} acres"),
        ("Nearest GSS", f"{_get(data, 'key_metrics', 'nearest_gss')}"),
        ("Slope", f"{technical.get('slope_deg', 'N/A')}°"),
        ("Grid Distance", f"{technical.get('grid_proximity_proxy_km', 'N/A')} km"),
        ("Power Lines", f"{_get(data, 'key_metrics', 'power_lines')}"),
        ("Evidence Completeness", f"{_get(data, 'key_metrics', 'evidence_completeness')}"),
    ]

    key_metrics_rows = "\n".join([f"| {label} | {value} |" for label, value in key_metrics])

    top_reasons = _get(data, 'executive_summary', 'top_reasons', default=[])
    if isinstance(top_reasons, str):
        top_reasons = [top_reasons]
    top_risks = _get(data, 'executive_summary', 'top_risks', default=[])
    if isinstance(top_risks, str):
        top_risks = [top_risks]
    next_action = _get(data, 'executive_summary', 'next_action')
    if next_action == "N/A":
        next_action = "Proceed with detailed verification."

    def _render_asset_row(label: str, url: str, source: str, notes: str) -> str:
        if not url:
            return f"- **{label}**: unavailable"
        if str(url).startswith("data:"):
            return f"- **{label}**: embedded preview generated from {source}. {notes}"
        return f"- **{label}**: [Open link]({url}) | Source: {source} | {notes}"

    def _render_preview_row(label: str, url: str) -> str:
        if not url:
            return f"- **{label}**: preview unavailable"
        if str(url).startswith("data:"):
            return f"- **{label}**: embedded preview included in report"
        return f"- **{label}**: [Open preview]({url})"

    spatial_rows = [
        _render_asset_row("Site Boundary (Satellite)", raster_assets.get('satellite_image_url', ''), "Google Earth Engine / map tiles", "Primary parcel context and visual confirmation."),
        _render_asset_row("Terrain Slope Analytics", raster_assets.get('slope_heatmap_url', ''), "Google Earth Engine", "Slope gradient and grading risk evidence."),
        _render_asset_row("Solar Resource Intensity", raster_assets.get('solar_heatmap_url', ''), "Google Earth Engine / ERA5", "Resource availability and yield context."),
        _render_asset_row("Ecological Classification", raster_assets.get('land_cover_map_url', ''), "Google Earth Engine / Dynamic World", "Land-cover context for permitting and suitability."),
    ]

    report = f"""
# [CONFIDENTIAL] INVESTMENT COMMITTEE SITE EVALUATION DOSSIER
**Project ID:** {site['location'][:20].upper()}-{datetime.datetime.now().strftime('%Y%m%d')} | **Analysis Date:** {current_time_str}
**Subject:** Comprehensive Technical & Financial Feasibility Assessment
**Overall Feasibility Score: {technical['project_suitability_score']}/100**

---

## I. EXECUTIVE SUMMARY
- **Verdict**: **{_get(data, 'executive_summary', 'verdict')}**
- **Confidence**: {_get(data, 'executive_summary', 'confidence')}
- **Next Action**: {next_action}

### Top Reasons
{chr(10).join([f"- {item}" for item in top_reasons]) if top_reasons else "- N/A"}

### Top Risks
{chr(10).join([f"- {item}" for item in top_risks]) if top_risks else "- N/A"}

---

## II. KEY METRICS
| Metric | Value |
| :--- | :--- |
{key_metrics_rows}

---

## III. DETERMINISTIC PASS/FAIL ANALYSIS (HARD CONSTRAINTS)
**HARD VERDICT**: {context.get('deterministic_rules', {}).get('hard_verdict', 'N/A')} [GEE/OSM]
**SUMMARY**: {context.get('deterministic_rules', {}).get('summary', 'N/A')}

| Rule | Criteria | Observed Value | Status | Source |
| :--- | :--- | :--- | :--- | :--- |
{rules_table_rows}

---

## IV. FINAL VERDICT & INVESTMENT THESIS
- **Developer IC Simulation**: 
    > {_get(data, 'executive_summary', 'ic_simulation')}
- **Executive Thesis**: {_get(data, 'executive_summary', 'thesis')}

{sections_md}

## V. STRATEGIC EXPERT VERDICT (CREWAI COMMITTEE)
*Consensus reached by Land Scout, Technical, Risk, and Financial leads:*

{_get(data, 'expert_verdict_summary', default='Pending committee results...')}

---

## VI. RISK HEATMAP & MITIGATION MATRIX
| Risk Category | Level | Observation | Financial / Operational Impact | Mitigation |
| :--- | :--- | :--- | :--- | :--- |
{risk_rows}

## VII. COST IMPACT & FINANCIAL SUMMARY
- **Civil CAPEX Impact**: {_get(data, 'financial_summary', 'civil_capex')}
- **Interconnection CAPEX**: {_get(data, 'financial_summary', 'gentie_capex')}
- **Commercial Outlook**: {_get(data, 'financial_summary', 'commercial_outlook')}

## VIII. SPATIAL & VISUAL INTELLIGENCE
{chr(10).join(spatial_rows)}

### Evidence Preview
{chr(10).join([
    _render_preview_row("Site Boundary Preview", raster_assets.get('satellite_image_url', '')),
    _render_preview_row("Slope Preview", raster_assets.get('slope_heatmap_url', '')),
    _render_preview_row("Solar Preview", raster_assets.get('solar_heatmap_url', '')),
    _render_preview_row("Land Cover Preview", raster_assets.get('land_cover_map_url', '')),
])}

---
**End of Memorandum**
*Generated by Auxilium Land Discovery Agent*
"""
    return report.strip()


def build_parcel_report_prompt(context: dict, current_time_str: str, expert_verdict: str) -> str:
    facts_json = json.dumps(context, indent=2)
    
    return textwrap.dedent(f"""
    Return a structured JSON object representing an Investment Committee (IC) Report for the following parcel data:
    {facts_json}

    JSON SCHEMA:
    {{
      "executive_summary": {{
        "verdict": "GO/NO-GO/CONDITIONAL GO/INSUFFICIENT EVIDENCE",
        "confidence": "High/Medium/Low",
        "top_reasons": ["Reason 1", "Reason 2", "Reason 3"],
        "top_risks": ["Risk 1", "Risk 2", "Risk 3"],
        "next_action": "Single concise next step",
        "ic_simulation": "Short quote about IC approval probability",
        "thesis": "3-paragraph investment thesis"
      }},
      "key_metrics": {{
        "nearest_gss": "Nearest grid substation name or distance",
        "power_lines": "Detected/estimated line count with confidence note",
        "evidence_completeness": "Percentage or qualitative completeness"
      }},
      "sections": [
        {{
          "id": "II",
          "title": "SITE MORPHOLOGY & CIVIL ASSESSMENT",
          "claims": [
            {{
              "observation": "Raw fact from GIS",
              "citation": "GEE / OSM / ERA5",
              "confidence": "High/Medium/Low",
              "inference": "Implication for CAPEX/Yield",
              "recommendation": "Actionable step"
            }}
          ]
        }},
        {{
          "id": "III",
          "title": "RESOURCE & REVENUE MODELING",
          "claims": [
            {{
              "observation": "GHI/Yield fact",
              "citation": "NASA/MODIS",
              "confidence": "High/Medium/Low",
              "inference": "Revenue stability impact",
              "recommendation": "Optimization step"
            }}
          ]
        }}
        // ... continue for IV and V
      ],
      "risk_matrix": [
        {{ "category": "Topographical", "level": "...", "observation": "...", "impact": "...", "mitigation": "..." }},
        {{ "category": "Grid/Substation", "level": "...", "observation": "...", "impact": "...", "mitigation": "..." }},
        {{ "category": "Environmental", "level": "...", "observation": "...", "impact": "...", "mitigation": "..." }},
        {{ "category": "Hydrology", "level": "...", "observation": "...", "impact": "...", "mitigation": "..." }}
      ],
      "financial_summary": {{
        "civil_capex": "Impact of grading costs...",
        "gentie_capex": "Impact of Gen-Tie distance...",
        "commercial_outlook": "Investor language on LCOE/IRR..."
      }},
      "expert_verdict_summary": "Synthesized consensus from the CrewAI committee: " + expert_verdict
    }}

    WRITING MANDATE:
    - Separate content into OBSERVATION, INFERENCE, and RECOMMENDATION.
    """)


def distill_report_into_insights(report_text: str, context: dict):
    """
    Background task to extract 1-3 high-level strategic insights from a report
    to be stored in the AI memory.
    """
    print("Agent: 🧠 Distilling strategic insights for long-term memory...")
    try:
        lat = context["site"]["coordinates"]["lat"]
        lon = context["site"]["coordinates"]["lon"]
        location_name = context["site"]["location"]
        
        prompt = textwrap.dedent(f"""
            # OPERATION: STRATEGIC KNOWLEDGE DISTILLATION
            You are a Senior Infrastructure Knowledge Architect. Your task is to analyze the provided Land Analysis Report and extract 1-3 "Strategic Insights" that should be remembered for future analyses in this region or for similar parcels.
            
            ## REPORT CONTENT:
            {report_text[:10000]} # Truncate if too long
            
            ## SITE CONTEXT:
            Location: {location_name}
            Coordinates: {lat}, {lon}
            
            ## OBJECTIVE:
            Extract lessons that are NOT obvious from raw data.
            - GOOD: "In this part of Rajasthan, high soil salinity requires specialized foundation coatings, increasing CAPEX by 5-8%."
            - GOOD: "Proximity to the XXX Wildlife Sanctuary in this district often leads to 12-18 month permitting delays despite low initial environmental risk scores."
            - BAD: "The slope is 2 degrees." (This is raw data, not an insight)
            
            ## FORMAT:
            Return a JSON list of strings. Example: ["Insight 1", "Insight 2"]
        """)
        
        response = _get_openai_client().chat.completions.create(
            model='gpt-4o-mini',
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        insights = result.get("insights", []) or result.get("list", []) or list(result.values())[0]
        
        if isinstance(insights, str):
            insights = [insights]
            
        for insight in insights:
            if isinstance(insight, str) and len(insight) > 20:
                rag_manager.add_strategic_insight(lat, lon, location_name, insight)
                print(f"Agent: 💾 Saved new insight: {insight[:100]}...")
                
    except Exception as e:
        print(f"Agent: ⚠️ Insight distillation failed: {e}")


def agent_evaluate_parcel(
    lat: float, 
    lon: float, 
    area_acres: float, 
    polygon: list = None, 
    custom_prompt: str = None, 
    selected_layers: list = None, 
    layer_thumbnails: dict = None, 
    gss_info: str = None,
    geo_signals: dict = None
) -> str:
    """
    1. Compiles metrics from open-data tools (supporting dynamic polygon areas).
    2. Downloads satellite thumbnail.
    3. Passes data + Image to Gemini Vision LLM.
    """
    try:
        if polygon and len(polygon) > 2:
            computed_area = calculate_polygon_area_acres(polygon)
            area_acres = round(computed_area, 2)
            print(f"Agent: Scanning custom polygon area ({area_acres} acres)...")
        else:
            print(f"Agent: Scanning radial area at ({lat}, {lon}) for {area_acres} acres...")
            
        print(" -> Fetching parcel intelligence from open data sources...")
        with ThreadPoolExecutor(max_workers=16) as executor:
            fut_slope = executor.submit(get_region_slope, lat, lon, 30, polygon)
            fut_weather = executor.submit(get_solar_and_wind_data, lat, lon, polygon)
            fut_img = executor.submit(get_satellite_image_url, lat, lon, area_acres, polygon)
            fut_loc = executor.submit(get_location_details, lat, lon)
            fut_esg = executor.submit(get_esg_environmental_baseline, lat, lon)
            
            # Fetch Heatmaps (New)
            fut_slope_img = executor.submit(get_layer_thumbnail_url, 'slope', lat, lon, area_acres, polygon)
            fut_solar_img = executor.submit(get_layer_thumbnail_url, 'solar_ghi', lat, lon, area_acres, polygon)
            fut_cover_img = executor.submit(get_layer_thumbnail_url, 'land_cover', lat, lon, area_acres, polygon)

            if not gss_info:
                fut_sub = None

            slope = fut_slope.result()
            resource_data = fut_weather.result()
            ghi = resource_data.get("ghi_kwh_m2_day", 0.0)
            wind = resource_data.get("wind_speed_m_s", 0.0)
            img_url = fut_img.result()
            location_details = fut_loc.result()
            location_string = location_details.get('full_address', 'Unknown Location')
            esg_data = fut_esg.result()

            # Overpass-backed heuristics are run sequentially to avoid public API rate limits.
            land_type, has_forest = get_land_cover_details(lat, lon, polygon)
            env_risk = get_environmental_risk(lat, lon, polygon)
            grid_dist = get_grid_proximity_proxy(lat, lon, polygon)
            
            # Heatmap URLs
            slope_heatmap = fut_slope_img.result().get('thumbnailUrl', '')
            solar_heatmap = fut_solar_img.result().get('thumbnailUrl', '')
            land_cover_map = fut_cover_img.result().get('thumbnailUrl', '')

            if not gss_info:
                substation_dist = get_nearest_substation(lat, lon)
            else:
                substation_dist = "Provided by UI"
            
            # calculate ROI
            roi_data = calculate_financial_roi(lat, lon, area_acres, resource_data)
            
        print(" -> Extracted comprehensive GIS and Infrastructure data successfully.")
        
        # --- RAG RETRIEVAL ---
        try:
            rag_query = f"Land analysis in {location_string}. Slope {slope:.2f}, Land type {land_type}. Forest {has_forest}."
            print(f" -> Querying AI Memory (RAG) for past expert feedback...")
            past_feedback = rag_manager.retrieve_relevant_context(rag_query, top_k=2)
            if past_feedback:
                print(f" -> Found {len(past_feedback)} relevant past rule(s) in AI Memory.")
        except Exception as e:
            print(f" -> RAG Retrieval Error: {e}")
            past_feedback = []
            
        # --- PROPRIETARY GRID INTELLIGENCE RETRIEVAL ---
        gss_raw = gss_info if gss_info else substation_dist
        gss_name = gss_raw.split('(')[0].strip() if '(' in gss_raw else gss_raw
        try:
            print(f" -> Querying Data Moat for proprietary intelligence on '{gss_name}'...")
            grid_intel = rag_manager.retrieve_grid_intelligence(gss_name, top_k=1)
            if grid_intel:
                print(" -> Found Proprietary Grid Intelligence!")
        except Exception as e:
            print(f" -> Grid Intel Retrieval Error: {e}")
            grid_intel = []
            
        # --- STRATEGIC INSIGHTS RETRIEVAL (Self-Learning Memory) ---
        try:
            print(f" -> Querying Institutional Memory for regional insights...")
            past_insights = rag_manager.retrieve_strategic_insights(
                query=f"Land development challenges in {location_string}",
                lat=lat,
                lon=lon,
                top_k=3
            )
            if past_insights:
                print(f" -> Found {len(past_insights)} strategic insights from past analyses.")
        except Exception as e:
            print(f" -> Strategic Insights Retrieval Error: {e}")
            past_insights = []
        
    except Exception as e:
        return f"Error extracting open-data parcel intelligence: {e}"

    # Vision Integration
    img_part = None
    if img_url and not img_url.startswith("data:image/svg+xml"):
        print(" -> Downloading satellite patch for Gemini Vision inspection...")
        try:
            resp = requests.get(img_url, timeout=10)
            if resp.status_code == 200:
                img_part = Image.open(io.BytesIO(resp.content))
                print(" -> Vision model primed with satellite insight.")
        except Exception as e:
            print(f"Warning: Failed to fetch vision image locally. ({e})")

    print(f"\nAgent: All GIS data acquired. Analyzing with OpenAI...")
    
    current_time_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    analysis_context = build_parcel_analysis_context(
        lat=lat,
        lon=lon,
        area_acres=area_acres,
        slope=slope,
        land_type=land_type,
        has_forest=has_forest,
        ghi=ghi,
        wind=wind,
        env_risk=env_risk,
        grid_dist=grid_dist,
        img_url=img_url,
        slope_heatmap=slope_heatmap,
        solar_heatmap=solar_heatmap,
        land_cover_map=land_cover_map,
        gss_info=gss_info,
        substation_dist=substation_dist,
        resource_data=resource_data,
        roi_data=roi_data,
        location_details=location_details,
        esg_data=esg_data,
        hydrology=get_hydrology_risk(lat, lon, polygon),
        grading=calculate_grading_costs(slope, area_acres),
        geo_signals=geo_signals,
    )
    
    # --- Deterministic Rules Layer ---
    rules_data = check_deterministic_rules(analysis_context)
    analysis_context["deterministic_rules"] = rules_data
    
    # --- Programmatic Evidence Threshold Enforcement ---
    evidence_report = verify_evidence_thresholds(analysis_context)
    analysis_context["evidence_threshold"] = evidence_report
    
    if not evidence_report["is_sufficient"]:
        print(f"Agent: ⚠️ INSUFFICIENT EVIDENCE DETECTED ({evidence_report['completeness_pct']}%). Aborting AI analysis.")
        error_json = {
            "executive_summary": {
                "verdict": "INSUFFICIENT EVIDENCE",
                "confidence": "Low",
                "ic_simulation": "The Investment Committee cannot review this site due to major data gaps.",
                "thesis": f"This analysis was programmatically aborted because the site only met {evidence_report['completeness_pct']}% of the required data threshold. Missing critical fields: {', '.join(evidence_report['missing_critical_fields'])}."
            },
            "sections": [],
            "risk_matrix": [],
            "financial_summary": {
                "civil_capex": "N/A",
                "gentie_capex": "N/A",
                "commercial_outlook": "N/A"
            },
            "expert_verdict_summary": "Expert committee analysis suspended due to insufficient data telemetry."
        }
        return f"![Auxilium Logo](/auxilium-logo.svg)\n\n" + render_report_to_markdown(error_json, analysis_context, current_time_str)

    # --- CrewAI Expert Meeting ---
    print("\nAgent: 🗳️ Convening CrewAI Expert Committee for a premium review...")
    try:
        expert_verdict = run_premium_expert_analysis(analysis_context)
        print("Agent: ✅ Expert verdict received.")
    except Exception as e:
        print(f"Agent: ⚠️ CrewAI Meeting failed ({e}). Falling back to standard analysis.")
        expert_verdict = "Expert committee unavailable for this session."

    # --- Final Report Generation (JSON FIRST) ---
    print("Agent: 📝 Drafting Investment Committee JSON report...")
    prompt = build_parcel_report_prompt(analysis_context, current_time_str, expert_verdict)
    
    if custom_prompt:
        prompt += f"\n\n### USER SPECIFIC DIRECTIVES\n**CRITICAL INSTRUCTION**: The user has provided the following specific custom instructions for this analysis. You MUST prioritize these instructions and tailor your entire report and recommendations to address them: \"{custom_prompt}\""

    if selected_layers:
        layer_names_str = ', '.join([REPORT_LAYER_NAMES.get(l, l) for l in selected_layers])
        prompt += f"\n\n### ENHANCED LAYER ANALYSIS REQUEST\nThe user has specifically activated the following open-data analytical layers on the map for this analysis: **{layer_names_str}**.\nFor EACH of these layers, you MUST dedicate a specific paragraph in the `Comprehensive Risk Analysis` section discussing the implications of that dataset for THIS specific parcel. Make these paragraphs detailed and developer-actionable."

    if past_feedback:
        feedback_str = "\n".join([f"- **Expert Context**: {fb['context']}\n  **Rule/Correction**: {fb['correction']}" for fb in past_feedback])
        prompt += f"\n\n### CRITICAL AI MEMORY: PAST HUMAN EXPERT FEEDBACK (RAG)\nWhen analyzing this parcel, you MUST adhere to the following human-verified rules and past corrections if they apply to the current context:\n{feedback_str}\nExplicitly mention in the report how this past expert feedback influenced your analysis."

    if grid_intel:
        intel_str = "\n".join([f"- {item['intelligence']}" for item in grid_intel])
        prompt += f"\n\n### 🔒 PROPRIETARY GRID INTELLIGENCE (DATA MOAT)\n**CRITICAL INSIDER KNOWLEDGE**: Proprietary feasibility notes for substation '{gss_name}':\n{intel_str}\n\nYou MUST heavily highlight this insider knowledge in the Executive Summary and decisively alter your Interconnection Risk matrix based on this data. This overrides basic screening metrics."

    if past_insights:
        insights_str = "\n".join([f"- {item['insight']} (Observed near {item['location_name']})" for item in past_insights])
        prompt += f"\n\n### 🧠 INSTITUTIONAL KNOWLEDGE: REGIONAL STRATEGIC INSIGHTS\nThe following insights were 'learned' from previous analyses in this region or for similar sites. You MUST incorporate these into your thesis as if they were established institutional knowledge:\n{insights_str}"

    try:
        print(f"Agent: Finalizing structured report with OpenAI GPT-4o-mini...")
        response = _get_openai_client().chat.completions.create(
            model='gpt-4o-mini',
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=120.0
        )
        report_json = json.loads(response.choices[0].message.content)
        
        # --- JSON SCHEMA VALIDATION ---
        print("Agent: 🛡️ Validating report structure against Institutional Schema...")
        try:
            validate(instance=report_json, schema=REPORT_SCHEMA)
            print("Agent: ✅ Schema validation passed.")
        except ValidationError as ve:
            print(f"Agent: ❌ SCHEMA VALIDATION FAILED: {ve.message}")
            # We could attempt a retry here, but for now we'll log it as a critical failure.
            return f"### ⚠️ Institutional Schema Violation\nThe AI generated a report that failed structural validation: {ve.message}. This prevents rendering of a bankable memorandum."

        # --- RENDER TO MARKDOWN ---
        print("Agent: 🎨 Rendering JSON to professional markdown memorandum...")
        report_text = f"![Auxilium Logo](/auxilium-logo.svg)\n\n" + render_report_to_markdown(report_json, analysis_context, current_time_str)
        
        # --- START BACKGROUND LEARNING LOOP ---
        threading.Thread(
            target=distill_report_into_insights,
            args=(report_text, analysis_context),
            daemon=True
        ).start()
        
        # Append layer map snapshots section if thumbnails were provided
        if layer_thumbnails:
            snapshots_section = "\n\n---\n## 📸 Open-Data Layer Snapshots\n*The following analytical layer snapshots were attached at the parcel boundary for reference.*\n"
            for layer_id, thumb_url in layer_thumbnails.items():
                label = SNAPSHOT_LAYER_NAMES.get(layer_id, layer_id)
                snapshots_section += f"\n### {label}\n![{label}]({thumb_url})\n"
            report_text += snapshots_section

        return report_text
    except Exception as e:
        print(f"OpenAI Error: {e}")
        # Fallback in case of total failure
        return f"### ⚠️ Analysis Encountered an Error\n\nThe AI committee was unable to finalize the report due to a timeout or connection error: {e}. Please try again."




if __name__ == "__main__":
    lat1, lon1 = 27.0238, 71.9213 
    area1 = 600.0 # acres
    report1 = agent_evaluate_parcel(lat1, lon1, area1)
    print("\n" + report1)
