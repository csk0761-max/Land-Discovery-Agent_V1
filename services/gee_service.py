import ee
import math
import datetime
from typing import List, Dict, Any, Optional

# Initialize Earth Engine
# We use the same project ID found in auto_search_tools.py
try:
    ee.Initialize(project='gen-lang-client-0332197840')
except Exception as e:
    print(f"GEE Service: Failed to initialize Earth Engine: {e}")

def get_geo_intelligence_signals(lat: float, lon: float, polygon: Optional[List[List[float]]] = None) -> Dict[str, Any]:
    """
    Fetches raw geo-intelligence signals from Google Earth Engine for a specific site.
    Includes solar, land use, terrain, flood risk, and historical change.
    """
    try:
        # Define the point of interest
        poi = ee.Geometry.Point([lon, lat])
        
        # Define search area (1km radius if no polygon)
        search_area = poi.buffer(1000)
        if polygon and len(polygon) > 2:
            # GEE expects [lon, lat]
            ee_poly = ee.Geometry.Polygon([[ [p[1], p[0]] for p in polygon ]])
            search_area = ee_poly

        # 1. Solar Irradiance (MODIS DSR - 2023 Mean)
        solar_col = ee.ImageCollection("MODIS/061/MCD18A1").filterDate('2023-01-01', '2023-12-31')
        solar_mean = solar_col.select('DSR').mean()
        solar_val = solar_mean.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=search_area,
            scale=5000
        ).get('DSR').getInfo()
        
        # 2. Land Use Classification (Dynamic World - 2023 Mode)
        dw_col = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate('2023-01-01', '2023-12-31')
        dw_mode = dw_col.select('label').mode()
        lc_stats = dw_col.select('label').reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=search_area,
            scale=10
        ).get('label').getInfo()
        
        # 3. Slope & Terrain (Copernicus DEM)
        dem = ee.ImageCollection("COPERNICUS/DEM/GLO30").select('DEM').mosaic()
        slope = ee.Terrain.slope(dem)
        terrain_stats = slope.addBands(dem).reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True
            ).combine(
                reducer2=ee.Reducer.minMax(),
                sharedInputs=True
            ),
            geometry=search_area,
            scale=30
        ).getInfo()
        
        # 4. Flood / Water Risk (JRC Global Surface Water + Global Flood DB)
        jrc_gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        water_occurrence = jrc_gsw.select('occurrence').reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=search_area,
            scale=30
        ).get('occurrence').getInfo()
        
        flood_history = ee.ImageCollection("GLOBAL_FLOOD_DB/MODIS_EVENTS/V1").select('flooded').max()
        flood_val = flood_history.reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=search_area,
            scale=250
        ).get('flooded').getInfo()
        
        # 5. Historical Satellite Change (NDVI 2014 vs 2024)
        def get_ndvi_mean(year_start: str, year_end: str):
            l8_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
                .filterDate(year_start, year_end) \
                .filterBounds(search_area) \
                .filter(ee.Filter.lt('CLOUD_COVER', 20))
            
            def add_ndvi(image):
                ndvi = image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
                return image.addBands(ndvi)
            
            return l8_col.map(add_ndvi).select('NDVI').median()

        ndvi_old = get_ndvi_mean('2014-01-01', '2014-12-31')
        ndvi_new = get_ndvi_mean('2023-01-01', '2024-12-31')
        
        ndvi_diff = ndvi_new.subtract(ndvi_old)
        change_val = ndvi_diff.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=search_area,
            scale=30
        ).get('NDVI').getInfo()

        # Compile Raw Signals
        signals = {
            "solar": {
                "avg_dsr_w_m2": solar_val,
                "ghi_estimate_kwh_m2_day": (solar_val * 24) / 1000.0 if solar_val else None,
                "period": "2023"
            },
            "land_use": {
                "class_distribution": lc_stats,
                "primary_class": max(lc_stats, key=lc_stats.get) if lc_stats else "unknown",
                "source": "Dynamic World V1"
            },
            "terrain": {
                "avg_slope_deg": terrain_stats.get('slope_mean'),
                "max_slope_deg": terrain_stats.get('slope_max'),
                "min_elevation_m": terrain_stats.get('DEM_min'),
                "max_elevation_m": terrain_stats.get('DEM_max'),
                "avg_elevation_m": terrain_stats.get('DEM_mean'),
                "elevation_std_dev": terrain_stats.get('DEM_stdDev')
            },
            "hydrology": {
                "surface_water_occurrence_pct": water_occurrence,
                "historical_flood_detected": bool(flood_val),
                "flood_risk_score": 100 if flood_val else (water_occurrence if water_occurrence else 0)
            },
            "change_detection": {
                "ndvi_delta_10yr": change_val,
                "encroachment_risk": "low" if change_val is not None and change_val > -0.1 else "high",
                "remark": "Negative NDVI delta suggests loss of vegetation or potential construction/encroachment."
            },
            "metadata": {
                "lat": lat,
                "lon": lon,
                "area_analyzed_sqm": search_area.area().getInfo() if hasattr(search_area, 'area') else 1000000,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }
        
        return signals

    except Exception as e:
        print(f"GEE Service Error: {e}")
        return {"error": str(e)}
