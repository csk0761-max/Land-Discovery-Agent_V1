import ee

ee.Initialize(project='gen-lang-client-0332197840')

# location
point = ee.Geometry.Point([83.3109, 22.0976])

# SRTM elevation
elevation = ee.Image("USGS/SRTMGL1_003")

# slope
slope = ee.Terrain.slope(elevation)

# extract slope value
slope_value = slope.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=point,
    scale=30
)

print(slope_value.getInfo())

# Sentinel-2 collection
dataset = ee.ImageCollection("COPERNICUS/S2")

image = dataset.filterBounds(point).first()

print(image.getInfo())
