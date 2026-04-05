import ee
import math
import overpy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Initialize Earth Engine 
try:
    ee.Initialize(project='gen-lang-client-0332197840')
except Exception as e:
    print(f"Failed to initialize Earth Engine: {e}")

def get_ee_geometry(lat: float, lon: float, polygon: list = None) -> ee.Geometry:
    """Helper to return either a Point or a Polygon feature."""
    if polygon and len(polygon) > 2:
        # GeoJSON/EarthEngine expects [lon, lat] pairs. Frontend sent [lat, lon].
        coords = [[p[1], p[0]] for p in polygon]
        return ee.Geometry.Polygon([coords])
    return ee.Geometry.Point([lon, lat])


def get_region_slope(lat: float, lon: float, scale_meters: int = 30, polygon: list = None) -> float:
    """Returns the mean slope (in degrees) for a specific coordinate or polygon."""
    geometry = get_ee_geometry(lat, lon, polygon)
    elevation = ee.ImageCollection("COPERNICUS/DEM/GLO30").select('DEM').mosaic()
    slope = ee.Terrain.slope(elevation)
    slope_value = slope.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=scale_meters,
        maxPixels=1e9
    ).getInfo()
    return slope_value.get('slope', 0.0)


def get_land_cover_details(lat: float, lon: float, polygon: list = None) -> tuple:
    """Returns (Land_Type_String, Has_Forest_Boolean) using Google Dynamic World."""
    geometry = get_ee_geometry(lat, lon, polygon)
    dataset = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1") \
                .filterDate('2023-01-01', '2023-12-31') \
                .select('label').mode()
    
    # Get the majority class for the polygon/point
    land_cover_val = dataset.reduceRegion(
        reducer=ee.Reducer.mode(),
        geometry=geometry,
        scale=10,
        maxPixels=1e9
    ).getInfo()
    
    class_code = land_cover_val.get('label', 0)
    has_forest = (class_code == 1)
    
    land_type = "unknown"
    if class_code == 0: land_type = "water"
    elif class_code == 1: land_type = "forest"
    elif class_code == 2: land_type = "grassland"
    elif class_code == 3: land_type = "wetland"
    elif class_code == 4: land_type = "cropland"
    elif class_code == 5: land_type = "shrubland"
    elif class_code == 6: land_type = "built-up"
    elif class_code == 7: land_type = "barren"
    elif class_code == 8: land_type = "snow/ice"

    return land_type, has_forest


def get_solar_and_wind_data(lat: float, lon: float, polygon: list = None) -> tuple:
    """
    Returns (GHI_kWh_m2_day, Wind_Speed_m_s) using MODIS MCD18A1 (Solar) and ERA5 (Wind).
    """
    geometry = get_ee_geometry(lat, lon, polygon)
    
    # Solar DSR from MODIS 1km
    solar_dataset = ee.ImageCollection("MODIS/061/MCD18A1") \
                .filterDate('2023-01-01', '2023-12-31') \
                .select('DSR').mean()
    solar_data = solar_dataset.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=1000,
        maxPixels=1e9
    ).getInfo()
    dsr_w_m2 = solar_data.get('DSR', 0.0)
    ghi_kwh = ((dsr_w_m2 * 24) / 1000.0) if dsr_w_m2 else 0.0
    
    # Wind from ERA5
    wind_dataset = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR") \
                .filterDate('2023-01-01', '2023-12-31') \
                .mean()
    
    wind_data = wind_dataset.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=11132,
        maxPixels=1e9
    ).getInfo()
    
    # Wind speed vector calculating Magnitude (m/s)
    u10 = wind_data.get('u_component_of_wind_10m', 0.0)
    v10 = wind_data.get('v_component_of_wind_10m', 0.0)
    if u10 is not None and v10 is not None:
        wind_speed = math.sqrt(u10**2 + v10**2)
    else:
        wind_speed = 0.0
        
    return round(ghi_kwh, 2), round(wind_speed, 2)


def get_environmental_risk(lat: float, lon: float, polygon: list = None) -> bool:
    """
    Checks if the projected area intersects with a recognized Protected Area from WDPA
    or falls within a historically mapped Flood Zone.
    Returns True if Environmental Risk is detected.
    """
    geometry = get_ee_geometry(lat, lon, polygon)
    
    # If it's a single point, buffer it to approx 500 acres. If it's a polygon, use it directly.
    if not polygon:
        geometry = geometry.buffer(1420)
    
    wdpa = ee.FeatureCollection("WCMC/WDPA/current/polygons")
    intersects = wdpa.filterBounds(geometry)
    count = intersects.size().getInfo()

    # Flood Risk mask
    flood_db = ee.ImageCollection("GLOBAL_FLOOD_DB/MODIS_EVENTS/V1")
    flood_img = flood_db.select('flooded').max()
    flood_val = flood_img.reduceRegion(ee.Reducer.max(), geometry, scale=250).getInfo().get('flooded', 0)
    has_flood_risk = (flood_val is not None and flood_val > 0)
    
    return (count > 0) or has_flood_risk


def get_grid_proximity_proxy(lat: float, lon: float, polygon: list = None) -> float:
    """
    Estimates proximity to local grid/infrastructure by measuring the distance
    (in kilometers) to the nearest 'Built-up' land cover (Class 6 in Dynamic World).
    """
    geometry = get_ee_geometry(lat, lon, polygon)
    
    worldcover = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate('2023-01-01', '2023-12-31').select('label').mode()
    built_up = worldcover.eq(6)
    
    # Calculate distance to closest built up pixel (max 5km search radius to avoid kernel pixel limit)
    distance = built_up.distance(ee.Kernel.euclidean(5000, 'meters'))
    
    dist_val = distance.reduceRegion(
        reducer=ee.Reducer.min(), # Find minimum distance from the polygon
        geometry=geometry,
        scale=30,
        maxPixels=1e9
    ).getInfo()
    
    dist_meters = dist_val.get('Map', 50000)
    if dist_meters is None: dist_meters = 50000
    
    return round(dist_meters / 1000.0, 2)


def get_satellite_image_url(lat: float, lon: float, area_acres: float, polygon: list = None) -> str:
    """
    Returns a public URL to a Sentinel-2 RGB thumbnail perfectly cropped to the parcel area.
    """
    try:
        geometry = get_ee_geometry(lat, lon, polygon)
        
        if polygon:
            region = geometry.buffer(100).bounds() # 100m padding around custom polygon
        else:
            sq_meters = area_acres * 4046.86
            radius = math.sqrt(sq_meters / math.pi) * 1.5
            region = geometry.buffer(radius).bounds()
        
        # Get Sentinel-2 image (fastest cloud-free image instead of computing a 1-year median)
        image = ee.ImageCollection("COPERNICUS/S2_HARMONIZED") \
            .filterBounds(region) \
            .filterDate('2023-01-01', '2023-12-31') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
            .sort('CLOUDY_PIXEL_PERCENTAGE') \
            .first()
        
        vis_params = {
            'bands': ['B4', 'B3', 'B2'],
            'min': 0,
            'max': 3000,
            'gamma': 1.4,
            'region': region,
            'dimensions': 600,
            'format': 'png'
        }
        
        url = image.getThumbURL(vis_params)
        return url
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return ""


def get_location_details(lat: float, lon: float) -> dict:
    """
    Reverse geocodes the coordinates to find human-readable village, district, state.
    Returns a dictionary of address components.
    """
    try:
        geolocator = Nominatim(user_agent="land_discovery_agent_v1")
        location = geolocator.reverse((lat, lon), timeout=5)
        if location:
            address = location.raw.get('address', {})
            village = address.get('village', address.get('suburb', address.get('town', address.get('city', 'Unknown Village'))))
            tehsil = address.get('subdistrict', address.get('county', 'Unknown Tehsil'))
            district = address.get('state_district', 'Unknown District')
            state = address.get('state', 'Unknown State')
            country = address.get('country', 'Unknown Country')
            display_name = location.address
            return {
                "village": village,
                "tehsil": tehsil,
                "district": district,
                "state": state,
                "country": country,
                "full_address": display_name
            }
        return {"full_address": "Unknown Location"}
    except Exception as e:
        return {"full_address": f"Location tracking failed: {e}"}


def calculate_financial_roi(lat: float, lon: float, area_acres: float, ghi: float) -> dict:
    """
    Calculates conceptual ROI for a utility-scale solar project.
    - Capacity: ~200kW (0.2MW) per acre for modern bifacial modules.
    - Performance Ratio: 0.78 (standard for utility scale).
    - CAPEX: ₹4.5 Cr per MW ($540k approx).
    - Revenue: ₹2.5 per unit (Average Competitive PPA).
    """
    try:
        # 1. Project Capacity
        capacity_mw = area_acres * 0.2
        
        # 2. Annual Generation (kWh)
        # GHI (kWh/m2/day) * 365 days * 1000 (standard STC) * Capacity(MW) * PR
        # Simplified: GHI * 365 * Capacity_kW * PR
        annual_yield_kwh = ghi * 365 * (capacity_mw * 1000) * 0.78
        
        # 3. CAPEX (INR) - 1 Crore = 10,000,000
        total_capex_cr = capacity_mw * 4.5
        total_capex_inr = total_capex_cr * 10000000
        
        # 4. Annual Revenue (INR)
        annual_revenue_inr = annual_yield_kwh * 2.5
        
        # 5. Simple Payback (Years)
        payback_years = total_capex_inr / annual_revenue_inr if annual_revenue_inr > 0 else 0
        
        return {
            "capacity_mw": round(capacity_mw, 2),
            "annual_yield_mwh": round(annual_yield_kwh / 1000, 2),
            "capex_cr": round(total_capex_cr, 2),
            "revenue_annual_lakhs": round(annual_revenue_inr / 100000, 2),
            "payback_years": round(payback_years, 1),
            "currency": "INR"
        }
    except Exception as e:
        print(f"ROI Calculation Error: {e}")
        return {}


def get_nearest_substation(lat: float, lon: float, search_radius_meters: int = 25000) -> str:
    """
    Uses OpenStreetMap Overpass API to find the closest electrical substation
    within a specific radius and returns distance inside the network.
    """
    try:
        api = overpy.Overpass()
        
        # Query OSM for substations within radius
        query = f"""
        [out:json][timeout:5];
        (
          node["power"="substation"](around:{search_radius_meters},{lat},{lon});
          way["power"="substation"](around:{search_radius_meters},{lat},{lon});
          relation["power"="substation"](around:{search_radius_meters},{lat},{lon});
        );
        out center;
        """
        
        result = api.query(query)
        
        closest_distance = float('inf')
        
        # Function to calculate haversine distance exactly
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371.0 # Earth radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c
            
        for node in result.nodes:
            d = haversine(lat, lon, float(node.lat), float(node.lon))
            if d < closest_distance:
                closest_distance = d
                
        # Overpy ways have a center attribute if requested in query
        for way in result.ways:
            if hasattr(way, 'center_lat') and hasattr(way, 'center_lon'):
              d = haversine(lat, lon, float(way.center_lat), float(way.center_lon))
              if d < closest_distance:
                  closest_distance = d
                  
        if closest_distance != float('inf'):
             return f"{round(closest_distance, 2)}"
        else:
             return f"> {search_radius_meters / 1000}"

    except Exception as e:
        print(f"Error fetching OSM data: {e}")
        return "Unknown"

def get_gee_tile_url(layer_id: str, lat: float, lon: float, area_acres: float = 100, polygon: list = None) -> dict:
    """
    Returns a dict with 'tileUrl' and 'attribution' for the given layer_id.
    Uses GEE getMapId() to generate a real-time tile map service URL.
    """
    try:
        geometry = get_ee_geometry(lat, lon, polygon)

        if layer_id == 'land_cover':
            image = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate('2023-01-01', '2023-12-31').select('label').mode()
            map_id = image.getMapId({
                'min': 0, 'max': 8,
                'palette': ['#419BDF','#397D49','#88B053','#7A87C6','#E49635','#DFC35A','#C4281B','#A59B8F','#B39FE1']
            })
            attribution = 'Google Dynamic World 10m'

        elif layer_id == 'slope':
            elevation = ee.ImageCollection("COPERNICUS/DEM/GLO30").select('DEM').mosaic()
            slope_img = ee.Terrain.slope(elevation)
            map_id = slope_img.getMapId({
                'min': 0, 'max': 30,
                'palette': ['#ffffd9','#edf8b1','#c7e9b4','#7fcdbb','#41b6c4','#1d91c0','#225ea8','#253494','#081d58']
            })
            attribution = 'Copernicus DEM 30m'

        elif layer_id == 'surface_water':
            water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
            map_id = water.select('occurrence').getMapId({
                'min': 0, 'max': 100,
                'palette': ['#ffffff','#aadaff','#4499ee','#0055cc','#003399']
            })
            attribution = 'JRC Global Surface Water v1.4'

        elif layer_id == 'ndvi':
            ndvi_collection = ee.ImageCollection("MODIS/061/MOD13A1") \
                .filterDate('2023-01-01', '2023-12-31') \
                .select('NDVI').mean()
            map_id = ndvi_collection.getMapId({
                'min': -2000, 'max': 10000,
                'palette': ['#d73027','#f46d43','#fdae61','#fee08b','#ffffbf','#d9ef8b','#a6d96a','#66bd63','#1a9850']
            })
            attribution = 'MODIS MOD13A1 NDVI 2023'

        elif layer_id == 'nighttime_lights':
            lights = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG") \
                .filterDate('2023-01-01', '2023-12-31') \
                .select('avg_rad').mean()
            map_id = lights.getMapId({
                'min': 0, 'max': 60,
                'palette': ['#000000','#1a1a00','#555500','#aaaa00','#ffff00','#ffcc00','#ff8800']
            })
            attribution = 'NOAA VIIRS Nighttime Lights 2023'

        elif layer_id == 'solar_ghi':
            solar = ee.ImageCollection("MODIS/061/MCD18A1").filterDate('2023-01-01', '2023-12-31').select('DSR').mean()
            map_id = solar.getMapId({
                'min': 100, 'max': 350,
                'palette': ['#313695','#4575b4','#74add1','#fdae61','#f46d43','#d73027','#a50026']
            })
            attribution = 'MODIS MCD18A1 Solar DSR'

        elif layer_id == 'protected_areas':
            wdpa = ee.FeatureCollection("WCMC/WDPA/current/polygons")
            wdpa_image = wdpa.style(color='#ff4444', fillColor='#ff444480', width=1)
            map_id = wdpa_image.getMapId()
            attribution = 'WCMC WDPA Protected Areas'

        else:
            return {'error': f'Unknown layer_id: {layer_id}'}

        tile_url = map_id['tile_fetcher'].url_format
        return {
            'tileUrl': tile_url,
            'attribution': attribution
        }

    except Exception as e:
        return {'error': str(e)}


def get_layer_thumbnail_url(layer_id: str, lat: float, lon: float, area_acres: float = 100, polygon: list = None) -> dict:
    """
    Returns a static PNG thumbnail URL for the given layer_id, cropped to the parcel.
    Uses GEE getThumbURL() which returns a directly embeddable PNG image URL.
    """
    try:
        geometry = get_ee_geometry(lat, lon, polygon)

        # Build a bounding region around the parcel
        if polygon:
            region = geometry.buffer(500).bounds()
        else:
            sq_meters = area_acres * 4046.86
            radius = math.sqrt(sq_meters / math.pi) * 1.8
            region = geometry.buffer(radius).bounds()

        THUMB_DIMS = 512  # px width/height

        VIS_CONFIGS = {
            'land_cover': {
                'image': ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate('2023-01-01', '2023-12-31').select('label').mode(),
                'vis': {'min': 0, 'max': 8,
                        'palette': ['419BDF','397D49','88B053','7A87C6','E49635','DFC35A','C4281B','A59B8F','B39FE1']},
                'label': 'Land Cover — Dynamic World 10m',
            },
            'slope': {
                'image': ee.Terrain.slope(ee.ImageCollection("COPERNICUS/DEM/GLO30").select('DEM').mosaic()),
                'vis': {'min': 0, 'max': 30,
                        'palette': ['ffffd9','edf8b1','c7e9b4','7fcdbb','41b6c4','1d91c0','225ea8','253494','081d58']},
                'label': 'Terrain Slope — Copernicus DEM',
            },
            'surface_water': {
                'image': ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('occurrence'),
                'vis': {'min': 0, 'max': 100,
                        'palette': ['ffffff','aadaff','4499ee','0055cc','003399']},
                'label': 'Surface Water Occurrence — JRC',
            },
            'ndvi': {
                'image': ee.ImageCollection("MODIS/061/MOD13A1").filterDate('2023-01-01','2023-12-31').select('NDVI').mean(),
                'vis': {'min': -2000, 'max': 10000,
                        'palette': ['d73027','f46d43','fdae61','fee08b','ffffbf','d9ef8b','a6d96a','66bd63','1a9850']},
                'label': 'Vegetation Index (NDVI) — MODIS 2023',
            },
            'nighttime_lights': {
                'image': ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG").filterDate('2023-01-01','2023-12-31').select('avg_rad').mean(),
                'vis': {'min': 0, 'max': 60,
                        'palette': ['000000','1a1a00','555500','aaaa00','ffff00','ffcc00','ff8800']},
                'label': 'Nighttime Lights — NOAA VIIRS 2023',
            },
            'solar_ghi': {
                'image': ee.ImageCollection("MODIS/061/MCD18A1").filterDate('2023-01-01', '2023-12-31').select('DSR').mean(),
                'vis': {'min': 100, 'max': 350,
                        'palette': ['313695','4575b4','74add1','fdae61','f46d43','d73027','a50026']},
                'label': 'Solar GHI — MODIS MCD18A1 1km',
            },
            'protected_areas': {
                'image': ee.FeatureCollection("WCMC/WDPA/current/polygons").style(color='ff4444', fillColor='ff444455', width=2),
                'vis': {},
                'label': 'Protected Areas — WCMC WDPA',
            },
        }

        if layer_id not in VIS_CONFIGS:
            return {'error': f'Unknown layer_id: {layer_id}'}

        cfg = VIS_CONFIGS[layer_id]
        img = cfg['image']

        thumb_params = {
            'region': region,
            'dimensions': THUMB_DIMS,
            'format': 'png',
        }
        if cfg['vis']:
            thumb_params.update(cfg['vis'])

        url = img.getThumbURL(thumb_params)
        return {
            'thumbnailUrl': url,
            'label': cfg['label'],
        }

    except Exception as e:
        return {'error': str(e)}


if __name__ == "__main__":

    lat, lon = 27.0238, 71.9213
    print(f"Testing Expanded GEE Tools for coordinates: {lat}, {lon}")
    
    loc = get_location_details(lat, lon)
    print(f"Location: {loc}")
    
    substation_dist = get_nearest_substation(lat, lon)
    print(f"Nearest Substation: {substation_dist} km away")
