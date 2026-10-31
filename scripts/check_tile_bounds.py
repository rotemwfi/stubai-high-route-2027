import math

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

lat_min, lat_max = 46.983952, 47.095555
lon_min, lon_max = 11.122922, 11.231681

# Add 1.5 km margin in lat/lon
margin_lat = 0.015
margin_lon = 0.020

min_lat = lat_min - margin_lat
max_lat = lat_max + margin_lat
min_lon = lon_min - margin_lon
max_lon = lon_max + margin_lon

print(f"Padded BBox: lat [{min_lat:.5f}, {max_lat:.5f}], lon [{min_lon:.5f}, {max_lon:.5f}]")

for z in [14, 15, 16]:
    x0, y0 = deg2num(max_lat, min_lon, z)
    x1, y1 = deg2num(min_lat, max_lon, z)
    nx = x1 - x0 + 1
    ny = y1 - y0 + 1
    print(f"Zoom {z:2d}: x=[{x0}..{x1}] ({nx:2d} tiles), y=[{y0}..{y1}] ({ny:2d} tiles), total={nx*ny:4d} tiles, px={nx*256}x{ny*256}")
