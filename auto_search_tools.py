"""
auto_search_tools.py
Provides GEE-based grid scoring, OSM substation finding, and
transmission route estimation for the Auto Search Land feature.
"""
import ee
import math
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

OVERPASS_API_URL = os.getenv("AUXILIUM_OVERPASS_URL", "https://overpass-api.de/api/interpreter")

def _run_overpass_query(query: str) -> list[dict]:
    """Helper to run Overpass queries using requests with standard headers/timeout."""
    try:
        response = requests.post(
            OVERPASS_API_URL,
            data=query,
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "User-Agent": "land_discovery_agent_v1",
            },
            timeout=25,
        )
        response.raise_for_status()
        return response.json().get("elements", [])
    except Exception as e:
        print(f"Overpass Error: {e}")
        return []

# Initialize Earth Engine
try:
    ee.Initialize(project='gen-lang-client-0332197840')
except Exception as e:
    print(f"Failed to initialize EE in auto_search_tools: {e}")


# ---------------------------------------------------------------------------
# Helper: Convert km radius to approximate degree offset
# ---------------------------------------------------------------------------
def _km_to_deg(km):
    return km / 111.0  # ~111 km per degree


# ---------------------------------------------------------------------------
# Helper: Haversine distance between two points (km)
# ---------------------------------------------------------------------------
def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# LAND COVER CODE → SCORE  (barren/grassland best for renewables)
# ---------------------------------------------------------------------------
LANDCOVER_SCORE = {
    0: 0,     # Water — avoid
    1: 0,     # Trees/Forest — avoid
    2: 80,    # Grass
    3: 0,     # Flooded Veg — avoid
    4: 20,    # Crops — low preference (food security concern)
    5: 60,    # Shrub & Scrub
    6: 0,     # Built Area — avoid
    7: 100,   # Bare/Barren — best
    8: 50,    # Snow/ice
}


def _point_in_polygon(x, y, polygon):
    """Ray casting alg to determine if point is inside a polygon array of [lat, lon]"""
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside



# ---------------------------------------------------------------------------
# Core: Score a grid of candidate sites within radius
# ---------------------------------------------------------------------------
def score_search_area(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    project_type: str,  # 'solar', 'wind', 'both'
    area_acres: float,
    search_polygon: list = None,
    weights: dict = None,
    top_n: int = 10
) -> list:
    """
    Samples the search area on a grid and scores each candidate site using dynamically weighted factors.
    Returns top_n candidate dicts sorted by score descending.
    """
    # Determine grid step: coarsen for large radii to keep GEE calls manageable
    if radius_km <= 30:
        step_km = 3
    elif radius_km <= 75:
        step_km = 5
    else:
        step_km = 8

    step_deg = _km_to_deg(step_km)
    deg_radius = _km_to_deg(radius_km)

    candidates = []
    
    # Build grid of candidate points
    if search_polygon and len(search_polygon) >= 3:
        lats = [p[0] for p in search_polygon]
        lons = [p[1] for p in search_polygon]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        lat = min_lat
        while lat <= max_lat:
            lon = min_lon
            while lon <= max_lon:
                if _point_in_polygon(lat, lon, search_polygon):
                    candidates.append((round(lat, 5), round(lon, 5)))
                lon += step_deg
            lat += step_deg
    else:
        lat = center_lat - deg_radius
        while lat <= center_lat + deg_radius:
            lon = center_lon - deg_radius
            while lon <= center_lon + deg_radius:
                dist = _haversine(center_lat, center_lon, lat, lon)
                if dist <= radius_km:
                    candidates.append((round(lat, 5), round(lon, 5)))
                lon += step_deg
            lat += step_deg

    if not candidates:
        return []

    print(f"Auto Search: Scoring {len(candidates)} candidate grid points (batched + parallel)...")

    # -----------------------------------------------------------------------
    # PRE-BUILD the GEE image stack ONCE (reused for every point).
    # Merging slope, land cover, ERA5 solar & wind into one multi-band image
    # so each point only needs ONE getInfo() call instead of 4.
    # -----------------------------------------------------------------------
    SCALE_M = 500  # 500 m resolution — fast and accurate enough for site screening
    ERA5_SCALE = 11132  # ERA5 native grid spacing ~0.1°

    # Slope band (Copernicus DEM 30m)
    slope_img = ee.Terrain.slope(ee.ImageCollection("COPERNICUS/DEM/GLO30").select('DEM').mosaic()).rename('slope')

    # Land cover band (Dynamic World 10m mode over 2023)
    lc_img = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterDate('2023-01-01', '2023-12-31')
        .select('label').mode().rename('lc')
    )

    # Solar DSR from MODIS (W/m2)
    solar_img = (
        ee.ImageCollection("MODIS/061/MCD18A1")
        .filterDate('2023-01-01', '2023-12-31')
        .select(['DSR'], ['rad'])
        .mean()
    )

    # Wind components from ERA5 Land
    wind_img = (
        ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
        .filterDate('2023-01-01', '2023-12-31')
        .mean()
        .select(
            ['u_component_of_wind_10m', 'v_component_of_wind_10m'],
            ['u10', 'v10']
        )
    )

    weather_stack = solar_img.addBands(wind_img).resample('bilinear')
    full_stack = slope_img.addBands(lc_img).addBands(weather_stack)

    # Pre-build Mask: Protected areas + Historical floods
    wdpa_mask = (
        ee.FeatureCollection("WCMC/WDPA/current/polygons")
        .filter(ee.Filter.neq('STATUS', 'Proposed'))
        .map(lambda f: f.set('prot', 1))
        .reduceToImage(['prot'], ee.Reducer.first())
        .unmask(0)
    )
    
    flood_img = (
        ee.ImageCollection("GLOBAL_FLOOD_DB/MODIS_EVENTS/V1")
        .select('flooded')
        .max()
        .unmask(0)
    )

    risk_mask = wdpa_mask.Or(flood_img).rename('protected')
    full_stack = full_stack.addBands(risk_mask)

    # -----------------------------------------------------------------------
    # Per-point fetch: ONE reduceRegion() call with all bands at once
    # -----------------------------------------------------------------------
    def _fetch_point_data(plat, plon):
        try:
            pt = ee.Geometry.Point([plon, plat])
            vals = full_stack.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=pt,
                scale=SCALE_M,
                bestEffort=True
            ).getInfo()

            slope_val = vals.get('slope', 999)
            lc_val    = int(round(vals.get('lc', 0) or 0))
            rad       = vals.get('rad', 0) or 0
            u10       = vals.get('u10', 0) or 0
            v10       = vals.get('v10', 0) or 0
            prot_val  = vals.get('protected', 0) or 0

            ghi       = (rad * 24) / 1000.0        # convert MODIS W/m² → kWh/m²/day
            wind      = math.sqrt(u10**2 + v10**2)
            protected = prot_val > 0.5             # majority protected

            return {
                'lat':       plat,
                'lon':       plon,
                'slope':     round(float(slope_val), 2) if slope_val not in (None, 999) else 999,
                'lc_code':   lc_val,
                'ghi':       round(ghi, 2),
                'wind':      round(wind, 2),
                'protected': protected,
            }
        except Exception as e:
            print(f"  GEE error at ({plat},{plon}): {e}")
            return None

    # Calculate polygon offset degrees for the requested area_acres
    area_sqm    = area_acres * 4046.86
    side_m      = math.sqrt(area_sqm)
    offset_deg  = (side_m / 2) / 111000.0

    # -----------------------------------------------------------------------
    # Parallel execution — fetch all grid points concurrently
    # GEE getInfo() is I/O-bound so threads give a big speedup.
    # Cap at 12 workers to stay within GEE's concurrent-request quota.
    # -----------------------------------------------------------------------
    MAX_WORKERS = 12
    raw_results = [None] * len(candidates)  # preserve order

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_point_data, lat, lon): i
            for i, (lat, lon) in enumerate(candidates)
        }
        done_count = 0
        for future in as_completed(futures):
            idx = futures[future]
            raw_results[idx] = future.result()
            done_count += 1
            if done_count % 20 == 0:
                print(f"  GEE progress: {done_count}/{len(candidates)} points scored...")

    # -----------------------------------------------------------------------
    # Score, filter, sort
    # -----------------------------------------------------------------------
    lc_names = {
        0: 'Water', 1: 'Forest', 2: 'Grassland',
        3: 'Wetland', 4: 'Cropland', 5: 'Shrubland',
        6: 'Built-up', 7: 'Barren', 8: 'Snow/Ice'
    }

    scored = []
    for data in raw_results:
        if data is None:
            continue

        slope     = data['slope']
        lc        = data['lc_code']
        ghi       = data['ghi']
        wind      = data['wind']
        protected = data['protected']
        plat      = data['lat']
        plon      = data['lon']

        # Slope score
        if slope <= 2:    s_slope = 100
        elif slope <= 5:  s_slope = 80
        elif slope <= 10: s_slope = 50
        elif slope <= 15: s_slope = 20
        else:             s_slope = 0

        s_lc = LANDCOVER_SCORE.get(lc, 30)

        if project_type == 'wind':
            s_resource = min(100, (wind / 8.0) * 100)
        elif project_type == 'solar':
            s_resource = min(100, (ghi / 7.0) * 100)
        else:
            s_resource = min(100, ((ghi / 7.0) * 50 + (wind / 8.0) * 50))

        s_env  = 0 if protected else 100
        
        w_slope = (weights.get('slope', 30) / 100.0) if weights else 0.30
        w_lc = (weights.get('land', 25) / 100.0) if weights else 0.25
        w_resource = (weights.get('resource', 25) / 100.0) if weights else 0.25
        w_env = (weights.get('environment', 20) / 100.0) if weights else 0.20
        
        total  = s_slope * w_slope + s_lc * w_lc + s_resource * w_resource + s_env * w_env

        if slope > 20 or protected:
            total = 0

        scored.append({
            **data,
            'lat':        round(float(plat), 5),
            'lon':        round(float(plon), 5),
            'land_type':  lc_names.get(lc, f'Class {lc}'),
            's_slope':    round(s_slope),
            's_lc':       round(s_lc),
            's_resource': round(s_resource),
            's_env':      round(s_env),
            'score':      round(total, 1),
            'polygon': [
                [round(float(plat) + offset_deg, 5), round(float(plon) - offset_deg, 5)],
                [round(float(plat) + offset_deg, 5), round(float(plon) + offset_deg, 5)],
                [round(float(plat) - offset_deg, 5), round(float(plon) + offset_deg, 5)],
                [round(float(plat) - offset_deg, 5), round(float(plon) - offset_deg, 5)],
            ]
        })

    # Sort and return top N
    scored.sort(key=lambda x: x['score'], reverse=True)
    top = scored[:top_n]
    for i, s in enumerate(top):
        s['rank'] = i + 1

    print(f"Auto Search: Top {len(top)} candidates identified.")
    return top


def _calculate_gss_capacity(voltage_str) -> int:
    """Estimates MW hosting capacity based on voltage tags from OSM."""
    if not voltage_str:
        return 50  # Default conservative estimate
    try:
        # Handle cases like "220000;132000", "220 kV", or "220kV".
        normalized = str(voltage_str).split(';')[0].strip().lower()
        main_v = normalized.replace("kv", "").strip()
        v = float(main_v)
        if v <= 1000:
            v *= 1000
        if v >= 765000: return 2000
        if v >= 400000: return 1000
        if v >= 220000: return 500
        if v >= 132000: return 150
        if v >= 66000: return 50
        if v >= 33000: return 20
        return 10
    except:
        return 50

def get_all_substations_in_area(lat: float, lon: float, radius_m: int) -> list:
    """
    Fetches nearby substations using Google Places or Overpass.

    If no substations are found within the requested radius, progressively widens
    the search so the scan still returns the nearest available GSS candidates.
    """
    radius_m = max(1000, int(radius_m or 0))
    search_radii = [radius_m]
    for candidate in (radius_m * 2, radius_m * 4, 200000):
        if candidate not in search_radii:
            search_radii.append(candidate)

    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    google_queries = [
        "substation",
        "electric substation",
        "electrical substation",
        "power substation",
        "gss",
        "grid substation",
    ]

    def _dedupe_sort(features: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for feature in features:
            key = (
                round(float(feature["lat"]), 5),
                round(float(feature["lon"]), 5),
                str(feature.get("name", "")).strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(feature)
        unique.sort(key=lambda item: _haversine(lat, lon, item["lat"], item["lon"]))
        return unique

    def _fetch_google(radius: int) -> list[dict]:
        if not google_key:
            return []
        try:
            all_features = []
            print(
                f"Backend: Bulk fetching substations via Google Places API around ({lat}, {lon}) "
                f"with radius {radius}m..."
            )
            for query in google_queries:
                url = (
                    "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                    f"?location={lat},{lon}&radius={radius}&keyword={requests.utils.quote(query)}&key={google_key}"
                )
                response = requests.get(url, timeout=15)
                data = response.json()
                status = data.get("status")
                if status not in {"OK", "ZERO_RESULTS"}:
                    print(f"Backend: Google Places query '{query}' returned status {status}.")
                    continue

                query_features = []
                for place in data.get("results", []):
                    loc = place.get("geometry", {}).get("location", {})
                    if loc.get("lat") is None or loc.get("lng") is None:
                        continue
                    query_features.append({
                        "name": place.get("name", "Unnamed Substation"),
                        "lat": float(loc.get("lat")),
                        "lon": float(loc.get("lng")),
                        "voltage": "Unknown (Google API)",
                        "capacity_mw": 50,
                        "source": f"google:{query}",
                    })

                if query_features:
                    print(f"Backend: Google Places query '{query}' returned {len(query_features)} features.")
                    all_features.extend(query_features)

            if all_features:
                print(f"Backend: Google Places returned {len(all_features)} total features across all queries.")
                return all_features
        except Exception as e:
            print(f"Backend: Google Places error: {e}")
        return []

    def _fetch_overpass(radius: int) -> list[dict]:
        try:
            print(f"Backend: Bulk fetching substations via Overpass around ({lat}, {lon}) with radius {radius}m...")
            query = f"""
            [out:json][timeout:30];
            (
              node["power"="substation"](around:{radius},{lat},{lon});
              way["power"="substation"](around:{radius},{lat},{lon});
              relation["power"="substation"](around:{radius},{lat},{lon});
            );
            out center tags;
            """
            elements = _run_overpass_query(query)
            print(f"Backend: Bulk Overpass query returned {len(elements)} features.")
            all_features = []
            for element in elements:
                el_lat = element.get("lat") or element.get("center", {}).get("lat")
                el_lon = element.get("lon") or element.get("center", {}).get("lon")
                if el_lat is None or el_lon is None:
                    continue
                tags = element.get("tags", {})
                v_val = tags.get('voltage', '')
                all_features.append({
                    'name': tags.get('name', 'Unnamed Substation'),
                    'lat': float(el_lat),
                    'lon': float(el_lon),
                    'voltage': v_val,
                    'capacity_mw': _calculate_gss_capacity(v_val),
                    'source': 'osm'
                })
            return all_features
        except Exception as e:
            print(f"Error fetching bulk substations: {e}")
            return []

    all_features = []
    # Try multiple radii but AGGREGATE results instead of breaking immediately
    for radius in search_radii:
        # Cap radius for Google Places (max 50,000m)
        google_radius = min(radius, 50000)
        google_features = _fetch_google(google_radius)
        if google_features:
            all_features.extend(google_features)
        
        overpass_features = _fetch_overpass(radius)
        if overpass_features:
            all_features.extend(overpass_features)
            
        # If we have a decent number of features, we can stop widening
        if len(all_features) >= 5:
            break

    if not all_features:
        return []

    return _dedupe_sort(all_features)

# ---------------------------------------------------------------------------
# Substation Finder: Returns substation with full coords
# ---------------------------------------------------------------------------
def get_candidate_substation(lat: float, lon: float, preferred_name: str = None, radius_m: int = 80000, pre_fetched_subs: list = None) -> dict:
    """
    Uses OSM Overpass API to find the closest substation within radius_m.
    If pre_fetched_subs is provided, computes distance purely in memory, saving massive network latency.
    """
    try:
        if pre_fetched_subs is not None:
            all_features = pre_fetched_subs
        else:
            print(f"Backend: Searching for candidate substation within {radius_m}m of ({lat}, {lon})...")
            query = f"""
            [out:json][timeout:10];
            (
              node["power"="substation"](around:{radius_m},{lat},{lon});
              way["power"="substation"](around:{radius_m},{lat},{lon});
              relation["power"="substation"](around:{radius_m},{lat},{lon});
            );
            out center tags;
            """
            elements = _run_overpass_query(query)
            print(f"Backend: Substation query returned {len(elements)} features.")

            all_features = []
            for element in elements:
                el_lat = element.get("lat") or element.get("center", {}).get("lat")
                el_lon = element.get("lon") or element.get("center", {}).get("lon")
                if el_lat is None or el_lon is None:
                    continue
                tags = element.get("tags", {})
                all_features.append({
                    'name': tags.get('name', 'Unnamed Substation'),
                    'lat': float(el_lat),
                    'lon': float(el_lon),
                    'voltage': tags.get('voltage', ''),
                    'capacity_mw': _calculate_gss_capacity(tags.get('voltage', ''))
                })

        best = None
        best_dist = float('inf')

        # If preferred name given, try to match it first
        if preferred_name:
            for f in all_features:
                if preferred_name.lower() in f['name'].lower():
                    d = _haversine(lat, lon, f['lat'], f['lon'])
                    if d < best_dist:
                        best = f
                        best_dist = d

        # Fallback: find nearest
        if not best:
            for f in all_features:
                d = _haversine(lat, lon, f['lat'], f['lon'])
                if d < best_dist:
                    best = f
                    best_dist = d

        if best:
            return {
                'name': best['name'],
                'lat': best['lat'],
                'lon': best['lon'],
                'distance_km': round(best_dist, 2),
                'voltage': best.get('voltage', ''),
                'capacity_mw': best.get('capacity_mw', 50)
            }
        return {
            'name': 'Not found within search radius',
            'lat': None, 'lon': None,
            'distance_km': None,
            'voltage': None,
            'capacity_mw': None
        }

    except Exception as e:
        return {'name': f'Error: {e}', 'lat': None, 'lon': None, 'distance_km': None}


# ---------------------------------------------------------------------------
# Transmission Route Estimator
# ---------------------------------------------------------------------------
def estimate_transmission_route(site_lat, site_lon, sub_lat, sub_lon, n_waypoints=6) -> dict:
    """
    Returns intermediate waypoints along the straight-line transmission path
    from site to substation, annotated with max slope from SRTM.
    Also returns total distance and terrain difficulty label.
    """
    if sub_lat is None or sub_lon is None:
        return {'waypoints': [], 'distance_km': None, 'difficulty': 'Unknown'}

    total_dist = _haversine(site_lat, site_lon, sub_lat, sub_lon)

    # Interpolate waypoints
    waypoints = []
    for i in range(n_waypoints + 1):
        t = i / n_waypoints
        wp_lat = site_lat + t * (sub_lat - site_lat)
        wp_lon = site_lon + t * (sub_lon - site_lon)
        waypoints.append([round(wp_lat, 5), round(wp_lon, 5)])

    # Sample max slope along the route
    max_slope = 0
    try:
        slope_img = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
        coords_ee = [[wp[1], wp[0]] for wp in waypoints]
        line = ee.Geometry.LineString(coords_ee)
        slope_val = slope_img.reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=line,
            scale=200,
            maxPixels=1e6
        ).getInfo().get('slope', 0)
        max_slope = round(slope_val, 1) if slope_val else 0
    except Exception:
        pass

    if max_slope < 5:
        difficulty = 'Easy'
    elif max_slope < 15:
        difficulty = 'Moderate'
    else:
        difficulty = 'Challenging'

    return {
        'waypoints': waypoints,
        'distance_km': round(total_dist, 2),
        'max_slope_deg': max_slope,
        'difficulty': difficulty,
    }
