import pyproj
import numpy as np
from PIL import Image, ImageEnhance
import math
from scipy.ndimage import map_coordinates
from pathlib import Path

CACHE_DIR = Path("state/tiles/opentopomap")
to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def fetch_tile(z, x, y):
    p = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if p.exists() and p.stat().st_size > 1000:
        return Image.open(p).convert("RGB")
    return Image.new("RGB", (256, 256), (235, 230, 215))

def test_crop(zoom, res, name):
    # Franz Senn area: 663559, 5217472
    e0, e1 = 663559 - 1000, 663559 + 1000
    n0, n1 = 5217472 - 1000, 5217472 + 1000
    W = int(round((e1 - e0) / res))
    H = int(round((n1 - n0) / res))
    
    lons, lats = to_wgs84.transform([e0, e1, e0, e1], [n1, n1, n0, n0])
    x0, y0 = deg2num(max(lats), min(lons), zoom)
    x1, y1 = deg2num(min(lats), max(lons), zoom)
    
    nx = x1 - x0 + 1
    ny = y1 - y0 + 1
    stitched = Image.new("RGB", (nx * 256, ny * 256))
    for iy, y in enumerate(range(y0, y1 + 1)):
        for ix, x in enumerate(range(x0, x1 + 1)):
            stitched.paste(fetch_tile(zoom, x, y), (ix * 256, iy * 256))
            
    stitched_arr = np.array(stitched)
    e_coords = np.linspace(e0, e1, W)
    n_coords = np.linspace(n1, n0, H)
    grid_e, grid_n = np.meshgrid(e_coords, n_coords)
    grid_lon, grid_lat = to_wgs84.transform(grid_e, grid_n)
    
    lat_rad = np.radians(grid_lat)
    n_tiles = 2.0 ** zoom
    frac_x = (grid_lon + 180.0) / 360.0 * n_tiles
    frac_y = (1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n_tiles
    
    pix_x = (frac_x - x0) * 256.0
    pix_y = (frac_y - y0) * 256.0
    
    coords = np.array([pix_y, pix_x])
    reprojected = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        map_coordinates(stitched_arr[:, :, c], coords, output=reprojected[:, :, c], order=1, mode='nearest')
    
    # Save image
    out_im = Image.fromarray(reprojected)
    out_im.save(f"state/maps/test_zoom_{name}.png")
    print(f"Saved test_zoom_{name}.png ({W}x{H})")

test_crop(14, 2.5, "z14_res25")
test_crop(15, 2.5, "z15_res25")
test_crop(16, 2.5, "z16_res25")
