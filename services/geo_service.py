from typing import List, Optional
import json
import re

import rag_manager
import time
from auto_search_tools import _haversine, get_all_substations_in_area
from tools import get_gee_tile_url, get_layer_thumbnail_url, get_location_details, _run_overpass_query

# Simple Memory Cache for speed
LINE_CACHE = {}
CACHE_EXPIRY = 3600 * 24 # 24 hours


def get_layer_tile(layer_id: str, lat: float, lon: float, area_acres: float = 100):
    return get_gee_tile_url(layer_id, lat, lon, area_acres)


def get_layer_thumbnail(layer_id: str, lat: float, lon: float, area_acres: float = 100):
    return get_layer_thumbnail_url(layer_id, lat, lon, area_acres)


def _substations_from_structured_store(lat: float, lon: float, radius_m: int) -> list[dict]:
    radius_km = radius_m / 1000.0
    results = []
    try:
        entries = rag_manager.retrieve_all_structured_gss_data()
    except Exception as exc:
        print(f"GeoService Error (Structured substations): {exc}")
        return []

    for entry in entries:
        try:
            entry_lat = entry.get("latitude", entry.get("lat"))
            entry_lon = entry.get("longitude", entry.get("lon"))
            if entry_lat is None or entry_lon is None:
                continue
            distance_km = _haversine(lat, lon, float(entry_lat), float(entry_lon))
            if distance_km <= radius_km:
                results.append(
                    {
                        "name": entry.get("gss_name") or entry.get("name") or "Unnamed Substation",
                        "lat": float(entry_lat),
                        "lon": float(entry_lon),
                        "distance_km": round(distance_km, 2),
                        "voltage": entry.get("voltage", ""),
                        "capacity_mw": entry.get("capacity_mw", 50),
                    }
                )
        except Exception:
            continue

    results.sort(key=lambda item: item["distance_km"])
    return results


def _classify_voltage_level(raw_value) -> str:
    value = str(raw_value or "").lower()
    for voltage in ("400", "220", "132"):
        if voltage in value:
            return f"{voltage}kV"
    return "unknown"


def _confidence_for_source(source: str, verification_status: str) -> str:
    source = (source or "").lower()
    verification_status = (verification_status or "").lower()
    if "internal" in source and verification_status in {"verified", "approved", "validated"}:
        return "high"
    if "internal" in source:
        return "medium"
    return "low"


def _remark_for_distance(distance_km: float, has_any: bool) -> str:
    if not has_any:
        return "Low feasibility"
    if distance_km <= 5:
        return "High potential, subject to bay/capacity verification"
    if distance_km <= 10:
        return "Good potential"
    if distance_km <= 15:
        return "Moderate potential"
    return "Higher evacuation cost/risk"


def _internal_master_substations(lat: float, lon: float, radius_m: int) -> list[dict]:
    try:
        entries = rag_manager.retrieve_all_structured_gss_data()
    except Exception as exc:
        print(f"GeoService Error (Internal master lookup): {exc}")
        return []

    radius_km = radius_m / 1000.0
    results = []
    for entry in entries:
        try:
            entry_lat = entry.get("latitude", entry.get("lat"))
            entry_lon = entry.get("longitude", entry.get("lon"))
            if entry_lat is None or entry_lon is None:
                continue
            distance_km = _haversine(lat, lon, float(entry_lat), float(entry_lon))
            if distance_km <= radius_km:
                results.append(
                    {
                        "name": entry.get("gss_name") or entry.get("name") or entry.get("substation_name") or "Unnamed Substation",
                        "lat": float(entry_lat),
                        "lon": float(entry_lon),
                        "distance_km": round(distance_km, 2),
                        "voltage_level": _classify_voltage_level(entry.get("voltage_level") or entry.get("voltage")),
                        "data_source": "Internal DB",
                        "verification_status": entry.get("verification_status", "Verified" if entry.get("bay_status") else "Unknown"),
                        "confidence_level": _confidence_for_source("internal", entry.get("verification_status", "")),
                        "available_capacity_mw": entry.get("available_capacity_mw"),
                        "bay_status": entry.get("bay_status"),
                    }
                )
        except Exception:
            continue
    results.sort(key=lambda item: item["distance_km"])
    return results


def _osm_substations(lat: float, lon: float, radius_m: int) -> list[dict]:
    try:
        query = f"""
        [out:json];
        (
          node["power"="substation"](around:{radius_m},{lat},{lon});
          way["power"="substation"](around:{radius_m},{lat},{lon});
          relation["power"="substation"](around:{radius_m},{lat},{lon});
        );
        out center tags;
        """
        elements = _run_overpass_query(query)
    except Exception as exc:
        print(f"GeoService Error (OSM fallback): {exc}")
        return []

    results = []
    for element in elements:
        el_lat = element.get("lat") or element.get("center", {}).get("lat")
        el_lon = element.get("lon") or element.get("center", {}).get("lon")
        if el_lat is None or el_lon is None:
            continue
        tags = element.get("tags", {})
        distance_km = _haversine(lat, lon, float(el_lat), float(el_lon))
        voltage = tags.get("voltage", "")
        
        # Comprehensive naming fallback
        gss_name = tags.get("name") or tags.get("operator") or tags.get("ref") or tags.get("substation:name") or f"GSS {voltage}kV"
        if "Unnamed" in gss_name or not gss_name:
            gss_name = f"Substation near {round(el_lat,3)},{round(el_lon,3)}"

        results.append(
            {
                "name": gss_name,
                "lat": float(el_lat),
                "lon": float(el_lon),
                "distance_km": round(distance_km, 2),
                "voltage_level": _classify_voltage_level(voltage),
                "data_source": "OSM",
                "verification_status": "Unverified",
                "confidence_level": "low",
                "available_capacity_mw": None,
                "bay_status": None,
            }
        )
    results.sort(key=lambda item: item["distance_km"])
    return results


def get_substations(lat: float, lon: float, radius_m: int = 20000):
    try:
        subs = get_all_substations_in_area(lat, lon, radius_m)
        if not subs:
          subs = _substations_from_structured_store(lat, lon, radius_m)
        enriched = []
        for substation in subs:
            dist = _haversine(lat, lon, substation["lat"], substation["lon"])
            enriched.append(
                {
                    "name": substation["name"],
                    "lat": substation["lat"],
                    "lon": substation["lon"],
                    "distance_km": round(dist, 2),
                    "voltage": substation.get("voltage", ""),
                    "capacity_mw": substation.get("capacity_mw", 50),
                }
            )
        enriched.sort(key=lambda item: item["distance_km"])
        return enriched
    except Exception as e:
        print(f"GeoService Error (Substations): {e}")
        return [] # Return empty list on error to prevent API hang


def auto_find_gss(lat: float, lon: float, radius_m: int = 25000) -> dict:
    radius_m = max(1000, int(radius_m or 25000))
    internal = _internal_master_substations(lat, lon, radius_m)
    osm = []
    if not internal:
        osm = _osm_substations(lat, lon, radius_m)
    results = internal or osm
    remark = _remark_for_distance(results[0]["distance_km"] if results else 0, bool(results))
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_km": round(radius_m / 1000.0, 2),
        "results": results,
        "summary": {
            "nearest_gss_name": results[0]["name"] if results else None,
            "distance_km": results[0]["distance_km"] if results else None,
            "voltage_level": results[0].get("voltage_level") if results else None,
            "risk_remark": remark,
            "next_action": "verify bay availability and STU connectivity status",
        },
        "source_mode": "Internal DB" if internal else ("OSM" if osm else "None"),
    }


def get_location(lat: float, lon: float):
    try:
        return get_location_details(lat, lon)
    except Exception as e:
        print(f"GeoService Error (Location): {e}")
        return {"full_address": "Service Temporarily Unavailable"}





def get_nearby_places(lat: float, lon: float, radius_m: int = 5000) -> list[dict]:
    """
    Fetches nearby villages, towns, and landmarks using OSM Overpass.
    """
    try:
        query = f"""
        [out:json][timeout:25];
        (
          node["place"~"village|town|city|hamlet|suburb"](around:{radius_m},{lat},{lon});
          node["tourism"~"attraction|viewpoint|museum"](around:{radius_m},{lat},{lon});
          node["amenity"~"hospital|school|university|police"](around:{radius_m},{lat},{lon});
        );
        out center tags;
        """
        elements = _run_overpass_query(query)
        results = []
        for element in elements:
            el_lat = element.get("lat") or element.get("center", {}).get("lat")
            el_lon = element.get("lon") or element.get("center", {}).get("lon")
            if el_lat is None or el_lon is None:
                continue
            tags = element.get("tags", {})
            place_type = tags.get("place") or tags.get("tourism") or tags.get("amenity") or "landmark"
            results.append({
                "name": tags.get("name") or tags.get("official_name") or "Unnamed Place",
                "lat": float(el_lat),
                "lon": float(el_lon),
                "type": place_type.capitalize(),
                "distance_km": round(_haversine(lat, lon, float(el_lat), float(el_lon)), 2)
            })
        # Sort by distance
        results.sort(key=lambda x: x["distance_km"])
        return results[:20]  # Limit to top 20 nearby places
    except Exception as e:
        print(f"GeoService Error (Nearby Places): {e}")
        return []

def _fetch_internal_transmission_lines(lat: float, lon: float, radius_m: int) -> list[dict]:
    """
    Placeholder for fetching verified transmission lines from Supabase/Internal DB.
    """
    # For now, we query the structured GSS data and see if it has associated line geometry
    # In a full implementation, this would query a 'transmission_lines' table.
    return []

def _fetch_imagery_transmission_lines(lat: float, lon: float, radius_m: int) -> list[dict]:
    """
    Placeholder for synthetic line candidates detected via satellite imagery (Gemini Vision / GEE).
    Now uses the helper from tools.py.
    """
    from tools import detect_lines_from_imagery_placeholder
    return detect_lines_from_imagery_placeholder(lat, lon, radius_m)

def get_nearby_transmission_lines(lat: float, lon: float, radius_m: int = 15000) -> dict:
    """
    Fused Power Line Detection Feature:
    Aggregates lines from Internal DB, OSM, and Imagery Candidates.
    """
    cache_key = f"fused_lines_{round(lat, 3)}_{round(lon, 3)}_{radius_m}"
    now = time.time()
    
    if cache_key in LINE_CACHE:
        entry = LINE_CACHE[cache_key]
        if now - entry['timestamp'] < CACHE_EXPIRY:
            return entry['data']

    def _normalize_line(el: dict, source: str) -> dict:
        """
        Ensures all transmission lines follow a strict institutional schema.
        """
        tags = el.get("tags", {})
        
        # 1. Voltage Normalization
        raw_voltage = tags.get("voltage") or tags.get("voltage:primary") or ""
        voltage_match = re.search(r'(\d+)', str(raw_voltage))
        voltage_kv = int(voltage_match.group(1)) if voltage_match else None
        
        # 2. Geometry Extraction
        coords = [[p["lat"], p["lon"]] for p in el.get("geometry", []) if "lat" in p and "lon" in p]
        
        # 3. Confidence Scoring & Tiering
        confidence_map = {
            "Internal": 0.95,  # Verified institutional records
            "OSM": 0.70,       # Community verified
            "Imagery": 0.40    # Synthetic candidate (low confidence)
        }
        
        tier_map = {
            "Internal": "Verified",
            "OSM": "Probable",
            "Imagery": "Inferred"
        }

        reasoning_map = {
            "Internal": "Cross-referenced with verified institutional grid database.",
            "OSM": "Detected via public GIS records and community-verified power tags.",
            "Imagery": "Identified as a potential infrastructure corridor via satellite imagery analysis."
        }
        
        # 4. Centroid for alignment/dedup
        centroid = [0, 0]
        if coords:
            centroid = [sum(p[0] for p in coords) / len(coords), sum(p[1] for p in coords) / len(coords)]

        return {
            "id": f"{source}_{el.get('id', hash(str(coords)))}",
            "source": source,
            "tier": tier_map.get(source, "Inferred"),
            "confidence_score": confidence_map.get(source, 0.5),
            "detection_reason": reasoning_map.get(source, "Automated heuristic detection."),
            "voltage_kv": voltage_kv,
            "coordinates": coords,
            "operator": tags.get("operator") or "Unknown",
            "centroid": centroid,
            "last_verified": el.get("last_verified") or ( "OSM Sync" if source == "OSM" else "Pending")
        }

    all_lines = []
    
    # 1. Internal DB
    internal_lines = _fetch_internal_transmission_lines(lat, lon, radius_m)
    all_lines.extend([_normalize_line(l, "Internal") for l in internal_lines])

    # 2. OSM Lines
    try:
        osm_query = f"""
        [out:json][timeout:25];
        (
          way["power"="line"](around:{radius_m},{lat},{lon});
          way["power"="cable"](around:{radius_m},{lat},{lon});
          relation["power"="line"](around:{radius_m},{lat},{lon});
        );
        out tags geom center;
        """
        osm_elements = _run_overpass_query(osm_query)
        all_lines.extend([_normalize_line(el, "OSM") for el in osm_elements])
    except Exception as e:
        print(f"OSM Fetch Error: {e}")

    # 3. Imagery Candidates
    imagery_lines = _fetch_imagery_transmission_lines(lat, lon, radius_m)
    all_lines.extend([_normalize_line(l, "Imagery") for l in imagery_lines])

    # 4. Geometry-Aware Deduplication (Nearest Alignment)
    # Strategy: Group by source priority, then prune overlapping centroids within 50m
    unique_lines = []
    all_lines.sort(key=lambda x: x["confidence_score"], reverse=True) # Priority to high confidence
    
    for candidate in all_lines:
        is_duplicate = False
        for existing in unique_lines:
            # Check centroid proximity (approx 50m threshold)
            dist_km = _haversine(candidate["centroid"][0], candidate["centroid"][1], existing["centroid"][0], existing["centroid"][1])
            if dist_km < 0.05: # 50 meters
                # Check if voltage matches or one is unknown
                if not candidate["voltage_kv"] or not existing["voltage_kv"] or abs(candidate["voltage_kv"] - existing["voltage_kv"]) < 10:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            unique_lines.append(candidate)

    payload = {
        "lines": unique_lines,
        "source_summary": {
            "internal_count": len(internal_lines),
            "osm_count": len(all_lines) - len(internal_lines) - len(imagery_lines),
            "imagery_candidate_count": len(imagery_lines)
        }
    }
    
    LINE_CACHE[cache_key] = {'data': payload, 'timestamp': now}
    return payload

def get_hydrology_analysis(lat: float, lon: float, area_acres: float = 100) -> dict:
    """
    Simulates GEE Hydrology analysis for water risk.
    In a full implementation, this calls GEE's 'Flow Accumulation' algorithm.
    """
    # This is a placeholder for the logic that will be expanded in the next step
    return {
        "risk_level": "Low",
        "nearest_water_body_km": 2.4,
        "flood_zone_proximity": "Outside 100-year zone",
        "catchment_area_ha": 15.2,
        "remark": "Site shows natural drainage away from center. Low flood risk."
    }
