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
from openai import OpenAI
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

# Client initialized lazily so the service can start without the key present.
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

# Canonical spelling map for Indian states — covers all common misspellings/abbreviations
_STATE_CANONICAL = {
    # Chhattisgarh variants
    "chhattisgarh": "Chhattisgarh", "chhatisgarh": "Chhattisgarh",
    "chattisgarh": "Chhattisgarh", "chatisgarh": "Chhattisgarh",
    "chhattisghar": "Chhattisgarh", "cg": "Chhattisgarh",
    # Rajasthan
    "rajasthan": "Rajasthan", "rajsthan": "Rajasthan", "raj": "Rajasthan",
    # Gujarat
    "gujarat": "Gujarat", "gujrat": "Gujarat", "gj": "Gujarat",
    # Madhya Pradesh
    "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh",
    "madhya predesh": "Madhya Pradesh", "madhy pradesh": "Madhya Pradesh",
    # Maharashtra
    "maharashtra": "Maharashtra", "maharastra": "Maharashtra", "mh": "Maharashtra",
    # Uttar Pradesh
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
    "uttar predesh": "Uttar Pradesh",
    # Andhra Pradesh
    "andhra pradesh": "Andhra Pradesh", "ap": "Andhra Pradesh",
    "andhra predesh": "Andhra Pradesh",
    # Telangana
    "telangana": "Telangana", "telengana": "Telangana", "ts": "Telangana",
    # Karnataka
    "karnataka": "Karnataka", "karnatka": "Karnataka", "ka": "Karnataka",
    # Tamil Nadu
    "tamil nadu": "Tamil Nadu", "tamilnadu": "Tamil Nadu", "tn": "Tamil Nadu",
    # Kerala
    "kerala": "Kerala", "kerela": "Kerala", "kl": "Kerala",
    # Odisha
    "odisha": "Odisha", "orissa": "Odisha", "or": "Odisha",
    # Punjab
    "punjab": "Punjab", "pb": "Punjab",
    # Haryana
    "haryana": "Haryana", "hr": "Haryana",
    # Jharkhand
    "jharkhand": "Jharkhand", "jharkand": "Jharkhand", "jh": "Jharkhand",
    # Bihar
    "bihar": "Bihar", "br": "Bihar",
    # West Bengal
    "west bengal": "West Bengal", "wb": "West Bengal", "bengal": "West Bengal",
    # Assam
    "assam": "Assam", "as": "Assam",
    # Himachal Pradesh
    "himachal pradesh": "Himachal Pradesh", "hp": "Himachal Pradesh",
    "himachal": "Himachal Pradesh",
    # Uttarakhand
    "uttarakhand": "Uttarakhand", "uttrakhand": "Uttarakhand", "uk": "Uttarakhand",
    # Goa
    "goa": "Goa", "ga": "Goa",
    # Tripura
    "tripura": "Tripura", "tr": "Tripura",
    # Meghalaya
    "meghalaya": "Meghalaya", "ml": "Meghalaya",
    # Manipur
    "manipur": "Manipur", "mn": "Manipur",
    # Nagaland
    "nagaland": "Nagaland", "nl": "Nagaland",
    # Mizoram
    "mizoram": "Mizoram", "mz": "Mizoram",
    # Arunachal Pradesh
    "arunachal pradesh": "Arunachal Pradesh", "ar": "Arunachal Pradesh",
    # Sikkim
    "sikkim": "Sikkim", "sk": "Sikkim",
    # Delhi
    "delhi": "Delhi", "new delhi": "Delhi", "dl": "Delhi",
    # Jammu and Kashmir
    "jammu and kashmir": "Jammu and Kashmir", "j&k": "Jammu and Kashmir",
    "jammu kashmir": "Jammu and Kashmir", "jk": "Jammu and Kashmir",
    # Ladakh
    "ladakh": "Ladakh", "la": "Ladakh",
}


def _normalize_state(raw: str) -> str:
    """Return the canonical Indian state name from user input, handling typos."""
    normalized = raw.strip().lower()
    return _STATE_CANONICAL.get(normalized, raw.strip())


def _nominatim_query(q: str, structured_params: dict = None) -> dict | None:
    """
    Fire one Nominatim request and return a parsed result dict, or None.
    Accepts either free-text `q` or structured params.
    """
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'AuxiliumLandDiscoveryAgent/2.0 (contact@auxilium.ai)'}

    if structured_params:
        params = {**structured_params, 'format': 'json', 'limit': 1, 'addressdetails': 0}
    else:
        params = {'q': q, 'format': 'json', 'limit': 1}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        place = data[0]
        lat = float(place['lat'])
        lon = float(place['lon'])
        bbox = [float(x) for x in place['boundingbox']]  # [south, north, west, east]

        R = 6371.0
        dlat = math.radians(bbox[1] - lat)
        dlon = math.radians(bbox[3] - lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat)) * math.cos(math.radians(bbox[1])) * math.sin(dlon / 2) ** 2)
        radius_km = min(150.0, R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
        if radius_km < 20:
            radius_km = 20.0  # floor — avoid point-sized search areas

        return {
            'lat': lat,
            'lon': lon,
            'radius_km': round(radius_km, 1),
            'display_name': place.get('display_name', q),
        }
    except Exception as e:
        print(f"  [Nominatim] Query failed ({q!r}): {e}")
        return None


def _get_nominatim_bounds(state: str, district: str = None) -> dict | None:
    """
    Resolve an Indian state + optional district to geocoordinates via Nominatim.
    Strategy (tried in order until one succeeds):
      1. Canonical spelling + structured Nominatim lookup (most reliable)
      2. Canonical spelling + free-text "District, State, India"
      3. Original (user-typed) spelling + free-text — catches weird place forms
      4. State-only fallback (if district was given) — gives a broader search area
    """
    canonical_state = _normalize_state(state)
    print(f"Auto Search Geocoding: district={district!r}, state_raw={state!r}, state_canonical={canonical_state!r}")

    attempts = []

    if district:
        # Strategy 1 — structured Nominatim (most precise)
        attempts.append({
            'label': f'structured({district}, {canonical_state})',
            'structured': {'city': district, 'state': canonical_state, 'country': 'India'},
        })
        attempts.append({
            'label': f'structured county({district}, {canonical_state})',
            'structured': {'county': district, 'state': canonical_state, 'country': 'India'},
        })
        # Strategy 2 — canonical free-text
        attempts.append({
            'label': f'free-text canonical({district}, {canonical_state}, India)',
            'q': f"{district}, {canonical_state}, India",
        })
        # Strategy 3 — user-typed free-text (sometimes catches vernacular spellings)
        if state.strip().lower() != canonical_state.lower():
            attempts.append({
                'label': f'free-text original({district}, {state}, India)',
                'q': f"{district}, {state}, India",
            })
        # Strategy 4 — state-only fallback
        attempts.append({
            'label': f'state-only fallback ({canonical_state})',
            'q': f"{canonical_state}, India",
        })
    else:
        attempts.append({
            'label': f'state structured({canonical_state})',
            'structured': {'state': canonical_state, 'country': 'India'},
        })
        attempts.append({
            'label': f'state free-text({canonical_state})',
            'q': f"{canonical_state}, India",
        })
        if state.strip().lower() != canonical_state.lower():
            attempts.append({
                'label': f'state original({state})',
                'q': f"{state}, India",
            })

    for attempt in attempts:
        print(f"  [Geocode] Trying: {attempt['label']}")
        result = _nominatim_query(
            attempt.get('q', ''),
            structured_params=attempt.get('structured'),
        )
        if result:
            print(f"  [Geocode] ✓ Resolved → {result['display_name'][:80]}…")
            return result

    print(f"  [Geocode] ✗ All strategies exhausted — could not locate '{district or ''} {state}'")
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
            canonical_state = _normalize_state(state)
            hint = ""
            if canonical_state.lower() != state.strip().lower():
                hint = f"\n\n> **Tip:** Did you mean **{canonical_state}**? The canonical spelling has been tried but no result was found for district **'{district}'** within it. Please verify the district name spelling."
            else:
                hint = f"\n\n> **Tip:** Check that **'{district or state}'** is spelled correctly. Example: `Mungeli` is a district in `Chhattisgarh`."
            return {
                'report': (
                    f"## ⚠️ Location Not Found\n\n"
                    f"Could not geocode **'{district or ''} {state}'** via OSM Nominatim after trying multiple strategies.\n"
                    f"{hint}\n\n"
                    f"**What to try:**\n"
                    f"- Use the state dropdown and district dropdown in the UI for accurate selection\n"
                    f"- Double-check the district name against official state district lists\n"
                    f"- Try the state name only (leave district blank) to search the whole state"
                ),
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

    with ThreadPoolExecutor(max_workers=16) as executor:
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
# Grid & Site Screening Investment Report
**Generated On:** {current_time_str} | **Target Region:** {location_name}

You are a **Technical Commercial Engineer** conducting an automated M&A screening for a **{project_label} project**. Your objective is to provide a highly detailed, engineering-grade, non-generic feasibility assessment. Provide granular commentary on topographical challenges, transmission routing complexities, and civil CAPEX estimates. 

- **Project Type**: {project_label}
- **Target Capacity**: {capacity_mw} MW
- **Minimum Area Required**: {area_acres} acres per site
- **Search Region**: {location_name}
- **Resolved Centre Point**: {center_lat}°N, {center_lon}°E
- **Search Radius Assessed**: {radius_km} km

Our GIS engine has algorithmically screened the entire search area and identified {len(enriched)} candidate sites. The scoring methodology weights: Slope (30%), Land Cover (25%), {resource_label} Resource (25%), Environmental Protection Status (20%).

**Candidate Site Data:**

| Rank | Coordinates | Score | Slope | Land Type | Resource | Nearest Substation | Sub Dist | Tx Length | Terrain |
|------|-------------|-------|-------|-----------|----------|--------------------|----------|-----------|---------| 
{site_table}

**YOUR TASK — Generate a highly professional, PDF-ready "Investment Screening Report" with the following structure:**

### 1. Regional Investment Thesis
Provide a brief summary of the screening outcome. Is this region highly investable, conditionally viable, or too risky based on the number of viable sites found, resource averages, and grid density?

### 2. Base Financial Estimates
Use the provided capacity to summarize the financial scale of the developer's target project:
- **Estimated Annual Yield**: ~{int(est_annual_generation_mwh):,} MWh/year (assuming 15% system efficiency and {avg_ghi:.2f} kWh/m²/day average).
- **Estimated Generic CAPEX**: ~${int(est_capex):,} USD (assuming industry average $0.75/W utility-scale).
Discuss how the identified transmission line lengths might trigger CAPEX blowouts.

### 3. Top 3 Bankable Sites
For each of the top 3 ranked sites provide a dedicated sub-section with:
- **Location**: Coordinates
- **Score**: X/100
- **Nearest Substation**: **[Exact substation name]** — distance in km
- **Investment Rationale**: Specific data-driven justifications (slope, land type, resource value)
- **Primary Upside**: The single biggest strength
- **Deal-Breaker Risk**: The most significant challenge that could halt the project
- **Grid Evacuation CAPEX Impact**: Commentary on the named substation, estimated Tx line length, and terrain difficulty

### 4. Portfolio Risk Matrix
Identify and assess the overarching risks across the candidates in a Markdown table: **Risk Factor** | **Observation** | **Mitigation Strategy**. Include categories like Topography Risk, Grid Curtailment/Delay Risk, and Environmental/ESG Risk.

### 5. Candidate Investment Matrix
Re-present the data table above with an added "Investment Rating" column (Core / Value-Add / Opportunistic / Pass).

### 6. Due Diligence Action Plan
Provide a numbered list of 5–7 specific next steps for the deal team (ground-truthing, regulatory checks, interconnection feasibility studies, etc.).

Be highly specific, data-driven, and professional. Use clean Markdown tables and bold KPIs.
"""

    if past_feedback:
        feedback_str = "\n".join([f"- **Expert Context**: {fb['context']}\n  **Rule/Correction**: {fb['correction']}" for fb in past_feedback])
        prompt += f"\n\n### CRITICAL AI MEMORY: PAST HUMAN EXPERT FEEDBACK (RAG)\nWhen screening these sites, you MUST adhere to the following human-verified rules and past corrections if they apply to the current context:\n{feedback_str}\nExplicitly mention in the report how this past expert feedback influenced your recommendations."

    try:
        import time
        max_retries = 4
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Agent: Retrying report generation (attempt {attempt+1}/{max_retries})...")

                response = _get_openai_client().chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[{"role": "user", "content": prompt}],
                )
                report = f"![Auxilium Logo](/auxilium-logo.svg)\n\n" + response.choices[0].message.content
                break
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "429" in err_str) and attempt < max_retries - 1:
                    import re
                    match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str)
                    wait_time = int(float(match.group(1))) + 2 if match else 3 ** attempt
                    if wait_time > 15:
                        raise e
                    print(f"OpenAI API error ({err_str[:40]}), retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
    except Exception as e:
        import re
        err_str = str(e)
        if "429" in err_str:
            match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str)
            delay = int(float(match.group(1))) + 1 if match else 60
            report = f"### ⏳ OpenAI API Rate Limit Reached\n\nThe AI provider's free-tier token quota has momentarily been exceeded. \n\n**Action required: Please wait ~{delay} seconds** and click Auto Search again."
        elif "503" in err_str:
            report = f"### 🌐 OpenAI API Server Overloaded\n\nThe OpenAI backend servers are currently experiencing global high demand (503 error).\n\nSpikes are usually temporary. **Action required: Please wait 10-20 seconds** and click Auto Search again."
        else:
            report = f"Error generating AI report: {e}"

    return {
        'report': report,
        'candidates': enriched,
        'search_center': center_data
    }
