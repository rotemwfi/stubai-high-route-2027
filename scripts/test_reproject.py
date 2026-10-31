import math
import numpy as np
import pyproj
import requests
from PIL import Image
from pathlib import Path
from scipy.ndimage import map_coordinates

CACHE_DIR = Path("state/tiles/opentopomap")
to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)

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

def fetch_tile(z, x, y):
    p = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if p.exists() and p.stat().st_size > 1000:
        return Image.open(p).convert("RGB")
    p.parent.mkdir(parents=True, exist_ok=True)
    server = ["a", "b", "c"][(x + y) % 3]
    url = f"https://{server}.tile.opentopomap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "StubaiAlpineMapBook/1.0", "Referer": "https://opentopomap.org/"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        p.write_bytes(r.content)
        return Image.open(p).convert("RGB")
    raise RuntimeError(f"Failed to fetch tile {z}/{x}/{y}")

def get_utm_reprojected_map(e_min, e_max, n_min, n_max, res=2.0, zoom=15):
    """
    Produces a numpy RGB array of shape (H, W, 3) aligned to UTM coordinates.
    pixel (x, y) corresponds to:
    easting = e_min + x * res
    northing = n_max - y * res
    """
    W = int(round((e_max - e_min) / res))
    H = int(round((n_max - n_min) / res))
    
    # 4 corners in UTM to WGS84
    corners_utm_x = [e_min, e_max, e_min, e_max]
    corners_utm_y = [n_max, n_max, n_min, n_min]
    corners_lon, corners_lat = to_wgs84.transform(corners_utm_x, corners_utm_y)
    
    lat_min_deg, lat_max_deg = min(corners_lat), max(corners_lat)
    lon_min_deg, lon_max_deg = min(corners_lon), max(corners_lon)
    
    # Tile indices
    x0, y0 = deg2num(lat_max_deg, lon_min_deg, zoom)
    x1, y1 = deg2num(lat_min_deg, lon_max_deg, zoom)
    
    # Download and stitch tiles
    nx = x1 - x0 + 1
    ny = y1 - y0 + 1
    stitched = Image.new("RGB", (nx * 256, ny * 256))
    
    for iy, y in enumerate(range(y0, y1 + 1)):
        for ix, x in enumerate(range(x0, x1 + 1)):
            im = fetch_tile(zoom, x, y)
            stitched.paste(im, (ix * 256, iy * 256))
            
    stitched_arr = np.array(stitched)
    
    # Grid of target UTM points
    e_coords = np.linspace(e_min, e_max, W)
    n_coords = np.linspace(n_max, n_min, H) # top to bottom
    grid_e, grid_n = np.meshgrid(e_coords, n_coords)
    
    grid_lon, grid_lat = to_wgs84.transform(grid_e, grid_n)
    
    # Convert lon, lat to fractional tile coordinates
    lat_rad = np.radians(grid_lat)
    n_tiles = 2.0 ** zoom
    frac_x = (grid_lon + 180.0) / 360.0 * n_tiles
    frac_y = (1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n_tiles
    
    # Map into stitched image pixel coordinates
    pix_x = (frac_x - x0) * 256.0
    pix_y = (frac_y - y0) * 256.0
    
    coords = np.array([pix_y, pix_x])
    reprojected = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        map_coordinates(stitched_arr[:, :, c], coords, output=reprojected[:, :, c], order=1, mode='nearest')
        
    return reprojected

# Test around Franz-Senn-Hütte: Easting 663500, Northing 5217500
e_center, n_center = 663559, 5217472
res = 4.0 # 4m/pixel for quick test
span = 2000 # 2km radius
img = get_utm_reprojected_map(e_center - span, e_center + span, n_center - span, n_center + span, res=res, zoom=15)
Image.fromarray(img).save("state/test_reprojected_franz_senn.png")
print(f"Success! Saved test image of shape {img.shape} to state/test_reprojected_franz_senn.png")
