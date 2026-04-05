import os
import io
import requests
import datetime
import textwrap
from PIL import Image
from google import genai
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# Import our custom Earth Engine tools
from tools import get_ee_geometry, get_region_slope, get_land_cover_details, get_solar_and_wind_data, get_environmental_risk, get_grid_proximity_proxy, get_satellite_image_url, get_location_details, get_nearest_substation, calculate_financial_roi, get_layer_thumbnail_url
from revenue_tools import get_polygon_owner_info
import rag_manager

load_dotenv()

# Configure Google GenAI Client
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def agent_evaluate_parcel(lat: float, lon: float, area_acres: float, polygon: list = None, custom_prompt: str = None, selected_layers: list = None, layer_thumbnails: dict = None, gss_info: str = None) -> str:
    """
    1. Compiles metrics from GEE tools (supporting dynamic polygon areas).
    2. Downloads satellite thumbnail.
    3. Passes data + Image to Gemini Vision LLM.
    """
    try:
        if polygon and len(polygon) > 2:
            import ee
            geom = get_ee_geometry(lat, lon, polygon)
            computed_area = geom.area().getInfo() / 4046.86
            area_acres = round(computed_area, 2)
            print(f"Agent: Scanning custom polygon area ({area_acres} acres)...")
        else:
            print(f"Agent: Scanning radial area at ({lat}, {lon}) for {area_acres} acres...")
            
        print(" -> Fetching GIS and Infrastructure data concurrently...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            fut_slope = executor.submit(get_region_slope, lat, lon, 30, polygon)
            fut_land = executor.submit(get_land_cover_details, lat, lon, polygon)
            fut_weather = executor.submit(get_solar_and_wind_data, lat, lon, polygon)
            fut_env = executor.submit(get_environmental_risk, lat, lon, polygon)
            fut_grid = executor.submit(get_grid_proximity_proxy, lat, lon, polygon)
            fut_img = executor.submit(get_satellite_image_url, lat, lon, area_acres, polygon)
            fut_loc = executor.submit(get_location_details, lat, lon)
            fut_revenue = executor.submit(get_polygon_owner_info, lat, lon, area_acres, 'Chhattisgarh')
            
            # Fetch Heatmaps (New)
            fut_slope_img = executor.submit(get_layer_thumbnail_url, 'slope', lat, lon, area_acres, polygon)
            fut_solar_img = executor.submit(get_layer_thumbnail_url, 'solar_ghi', lat, lon, area_acres, polygon)
            fut_cover_img = executor.submit(get_layer_thumbnail_url, 'land_cover', lat, lon, area_acres, polygon)

            if not gss_info:
                fut_sub = executor.submit(get_nearest_substation, lat, lon)

            slope = fut_slope.result()
            land_type, has_forest = fut_land.result()
            ghi, wind = fut_weather.result()
            env_risk = fut_env.result()
            grid_dist = fut_grid.result()
            img_url = fut_img.result()
            
            # Heatmap URLs
            slope_heatmap = fut_slope_img.result().get('thumbnailUrl', '')
            solar_heatmap = fut_solar_img.result().get('thumbnailUrl', '')
            land_cover_map = fut_cover_img.result().get('thumbnailUrl', '')

            if not gss_info:
                substation_dist = fut_sub.result()
            else:
                substation_dist = "Provided by UI"
            
            # calculate ROI
            roi_data = calculate_financial_roi(lat, lon, area_acres, ghi)
            location_details = fut_loc.result()
            location_string = location_details.get('full_address', 'Unknown Location')
            revenue_data = fut_revenue.result()
            
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
        
    except Exception as e:
        return f"Error connecting to Google Earth Engine: {e}"

    # Vision Integration
    img_part = None
    if img_url:
        print(" -> Downloading satellite patch for Gemini Vision inspection...")
        try:
            resp = requests.get(img_url, timeout=10)
            if resp.status_code == 200:
                img_part = Image.open(io.BytesIO(resp.content))
                print(" -> Vision model primed with satellite insight.")
        except Exception as e:
            print(f"Warning: Failed to fetch vision image locally. ({e})")

    print(f"\nAgent: All GIS data acquired. Analyzing with Gemini AI...")
    
    current_time_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    prompt = textwrap.dedent(f"""
    # Pre-Liminary Site Feasibility Report
    **Generated On**: {current_time_str}
    **Reference Context**: {location_string}

    ---

    ## I. EXECUTIVE SUMMARY & STRATEGIC RECOMMENDATION
    You are acting as a Senior GIS Consultant and Lead Project Developer for a multi-billion dollar renewable energy fund. Provide a high-level "Go/No-Go" summary based on a synthesis of topology, resource accessibility, and grid connectivity.
    
    ### 🏆 PROJECT SUITABILITY SCORE: [CALCULATED_SCORE]/100

    ---

    ## II. TECHNICAL PARAMETRIC DASHBOARD
    | Metric Class | Measured Value | Risk Impact (🟢/🟡/🔴) | Technical Remark |
    | :--- | :--- | :--- | :--- |
    | **Slope (Avg)** | {slope:.2f}° | [SCORE] | Earth-moving complexity & racking limits |
    | **Solar GHI** | {ghi:.2f} kWh/m²/d | [SCORE] | Potential yield vs regional benchmarks |
    | **Wind Speed** | {wind:.2f} m/s | [SCORE] | Suitability for hybrid/wind projects |
    | **Grid Proximity** | {gss_info or substation_dist} | [SCORE] | Transmission line Capex implication |
    | **Land Cover** | {land_type} | [SCORE] | Permitting & forest clearance status |
    | **Net Area** | {area_acres} Acres | [SCORE] | Modeled Capacity: {roi_data.get('capacity_mw')} MW |

    ---

    ## III. GEOSPATIAL HEATMAP GALLERY (RASTER ANALYTICS)
    | 🗺️ Slope Heatmap (Roughness) | ☀️ Solar intensity (GHI) | 🌿 Land Cover Classification |
    | :---: | :---: | :---: |
    | ![{slope:.2f}° Slope]({slope_heatmap}) | ![{ghi:.2f} GHI]({solar_heatmap}) | ![{land_type}]({land_cover_map}) |
    | *Blue = Flat, Red = Steep* | *Red = High Yield potential* | *Green = Forest, Yellow = Barren* |

    ---

    ## IV. SWOT ANALYSIS & COMPETITIVE RISK MATRIX
    ### 1. SWOT Dashboard (2x2 Grid)
    | STRENGTHS (Internal) | WEAKNESSES (Internal) |
    | :--- | :--- |
    | **S1**: [E.g., High GHI {ghi:.2f}] | **W1**: [E.g., Steep slope {slope:.2f}°] |
    | **S2**: [E.g., Proximity to GSS] | **W2**: [E.g., Surface water flags] |
    | **OPPORTUNITIES (External)** | **THREATS (External)** |
    | **O1**: State RE Policy incentives | **T1**: Environmental/Forest litigation |
    | **O2**: Local industry power demand | **T2**: Grid congestion (Host Capacity) |

    ### 2. 3x3 Site Risk Matrix (Impact vs Probability)
    | Risk ID | Probability | Impact | mitigation Strategy |
    | :--- | :--- | :--- | :--- |
    | **Topographical** | Low/Med/High | Low/Med/High | Tracking System Optimization |
    | **Interconnection** | Low/Med/High | Low/Med/High | Preliminary GSS Feasibility |
    | **Regulatory** | Low/Med/High | Low/Med/High | Village Tehsil Ownership Verification |

    ---

    ## V. FINANCIAL VIABILITY & ROI FORECAST (CONCEPTUAL)
    *Based on standard Indian utility-scale solar benchmarks (₹4.5 Cr/MW and ₹2.5/unit PPA):*

    - **Estimated Project Capacity**: {roi_data.get('capacity_mw')} MW (AC)
    - **Estimated Annual Yield**: {roi_data.get('annual_yield_mwh', '0')} MWh
    - **Estimated CAPEX**: ₹{roi_data.get('capex_cr', '0')} Cr
    - **Estimated Annual Revenue**: ₹{roi_data.get('revenue_annual_lakhs', '0')} Lakhs
    - **Simple Payback Period**: {roi_data.get('payback_years', '0')} Years
    
    *Provide a concise financial narrative here. Discuss LCOE potential based on resource density.*

    ---

    ## VI. SATELLITE IMAGE LOG & ANOMALY DETECTION
    ![Satellite Inspection Patch]({img_url})
    *(AI Inspection: Confirm land use matches {land_type}, detect houses/encroachment, and identify rock outcrops)*

    ---
    
    ## VII. FORWARD-LOOKING ACTION PLAN (DEVELOPER NEXT STEPS)
    1. **Pre-Construction**: Fine-grained contour mapping.
    2. **Grid Application**: Secure "No-Objection Certificate" for {roi_data.get('capacity_mw')} MW at the nearest {gss_info or substation_dist}.
    3. **Legal Check**: Cross-reference {lat}, {lon} with Village records in {location_details.get('village', 'Unknown Village')} Tehsil.

    ---

    ## VIII. REVENUE MAP & OWNERSHIP AUDIT (CADASTRAL)
    *Note: This section summarizes the cadastral identity of the parcel based on the current revenue overlay.*
    
    - **Jurisdiction**: {location_details.get('village')}, {location_details.get('tehsil')}, {location_details.get('district')}
    - **Official Record Portal**: {revenue_data.get('portal', 'Unknown Portal')}
    - **Intersecting Survey / Khasra Numbers Found**: {revenue_data.get('total_khasras_found', 0)}
    
    ### Identified Khasra & Ownership Records
    | Khasra No. | Registered Owner | Est. Area (Acres) | Land Classification |
    | :--- | :--- | :--- | :--- |
    {"\\n    ".join([f"| **{r['khasra_no']}** | {r['owner']} | {r['area_acres']:.2f} | {r['land_type']} |" for r in revenue_data.get('khasra_records', [])])}

    - **Recommended Verification**: 
        1. Compare satellite patch boundaries with superimposed Cadastral (Bhu Naksha) lines.
        2. Verify the identity of registered owners listed above directly on the State Portal.
        3. Confirm final land classification to determine conversion (CLU) feasibility.

    ---
    *Disclaimer: This AI-generated report is for preliminary feasibility screening only. GIS Raster analysis from GEE Dynamic World & Copernicus Digital Elevation Models.*
    """)
    
    if custom_prompt:
        prompt += f"\n\n### USER SPECIFIC DIRECTIVES\n**CRITICAL INSTRUCTION**: The user has provided the following specific custom instructions for this analysis. You MUST prioritize these instructions and tailor your entire report and recommendations to address them: \"{custom_prompt}\""

    if selected_layers:
        LAYER_NAMES = {
            'land_cover': 'ESA WorldCover Land Classification',
            'slope': 'USGS SRTM Terrain Slope',
            'surface_water': 'JRC Global Surface Water Occurrence',
            'ndvi': 'MODIS NDVI Vegetation Index',
            'nighttime_lights': 'NOAA VIIRS Nighttime Lights',
            'solar_ghi': 'ECMWF ERA5 Solar GHI Heatmap',
            'protected_areas': 'WCMC WDPA Protected Areas Boundaries',
        }
        layer_names_str = ', '.join([LAYER_NAMES.get(l, l) for l in selected_layers])
        prompt += f"\n\n### ENHANCED LAYER ANALYSIS REQUEST\nThe user has specifically activated the following GEE data layers on the map for this analysis: **{layer_names_str}**.\nFor EACH of these layers, you MUST dedicate a specific paragraph in the `Comprehensive Risk Analysis` section discussing the implications of that dataset for THIS specific parcel. Make these paragraphs detailed and developer-actionable."

    if past_feedback:
        feedback_str = "\n".join([f"- **Expert Context**: {fb['context']}\n  **Rule/Correction**: {fb['correction']}" for fb in past_feedback])
        prompt += f"\n\n### CRITICAL AI MEMORY: PAST HUMAN EXPERT FEEDBACK (RAG)\nWhen analyzing this parcel, you MUST adhere to the following human-verified rules and past corrections if they apply to the current context:\n{feedback_str}\nExplicitly mention in the report how this past expert feedback influenced your analysis."

    if grid_intel:
        intel_str = "\n".join([f"- {item['intelligence']}" for item in grid_intel])
        prompt += f"\n\n### 🔒 PROPRIETARY GRID INTELLIGENCE (DATA MOAT)\n**CRITICAL INSIDER KNOWLEDGE**: Proprietary feasibility notes for substation '{gss_name}':\n{intel_str}\n\nYou MUST heavily highlight this insider knowledge in the Executive Summary and decisively alter your Interconnection Risk matrix based on this data. This overrides basic GEE metrics."

    try:
        contents = [prompt]
        if img_part:
            contents.append(img_part)
            
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
        )
        report_text = f"![Auxilium Logo](/auxilium-logo.svg)\n\n" + response.text

        # Append layer map snapshots section if thumbnails were provided
        if layer_thumbnails:
            LAYER_NAMES = {
                'land_cover': 'Land Cover — ESA WorldCover 10m',
                'slope': 'Terrain Slope — USGS SRTM',
                'surface_water': 'Surface Water Occurrence — JRC',
                'ndvi': 'Vegetation Index (NDVI) — MODIS 2023',
                'nighttime_lights': 'Nighttime Lights — NOAA VIIRS 2023',
                'solar_ghi': 'Solar GHI — ECMWF ERA5-Land 2023',
                'protected_areas': 'Protected Areas — WCMC WDPA',
            }
            snapshots_section = "\n\n---\n## 📸 GEE Layer Map Snapshots\n*The following satellite and geospatial layer images were captured at the parcel boundary for reference.*\n"
            for layer_id, thumb_url in layer_thumbnails.items():
                label = LAYER_NAMES.get(layer_id, layer_id)
                snapshots_section += f"\n### {label}\n![{label}]({thumb_url})\n"
            report_text += snapshots_section

        return report_text
    except Exception as e:
        return f"Error generating report: {e}"

if __name__ == "__main__":
    lat1, lon1 = 27.0238, 71.9213 
    area1 = 600.0 # acres
    report1 = agent_evaluate_parcel(lat1, lon1, area1)
    print("\n" + report1)
