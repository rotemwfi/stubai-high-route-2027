import math
import pyproj
import numpy as np
from PIL import Image, ImageDraw
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

def fetch_tile(z, x, y):
    p = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if p.exists() and p.stat().st_size > 1000:
        return Image.open(p).convert("RGB")
    return Image.new("RGB", (256, 256), (235, 230, 215))

def render_crop(e_center, n_center, half_span=350, res=1.5, zoom=15):
    """
    Renders a high-res UTM aligned crop with a metric grid overlay (every 100m)
    so we can precisely identify the exact icon center in UTM coordinates.
    """
    e_min, e_max = e_center - half_span, e_center + half_span
    n_min, n_max = n_center - half_span, n_center + half_span
    
    W = int(round((e_max - e_min) / res))
    H = int(round((n_max - n_min) / res))
    
    corners_lon, corners_lat = to_wgs84.transform([e_min, e_max, e_min, e_max], [n_max, n_max, n_min, n_min])
    x0, y0 = deg2num(max(corners_lat), min(corners_lon), zoom)
    x1, y1 = deg2num(min(corners_lat), max(corners_lon), zoom)
    
    nx = x1 - x0 + 1
    ny = y1 - y0 + 1
    stitched = Image.new("RGB", (nx * 256, ny * 256))
    for iy, y in enumerate(range(y0, y1 + 1)):
        for ix, x in enumerate(range(x0, x1 + 1)):
            stitched.paste(fetch_tile(zoom, x, y), (ix * 256, iy * 256))
            
    stitched_arr = np.array(stitched)
    e_coords = np.linspace(e_min, e_max, W)
    n_coords = np.linspace(n_max, n_min, H)
    grid_e, grid_n = np.meshgrid(e_coords, n_coords)
    grid_lon, grid_lat = to_wgs84.transform(grid_e, grid_n)
    
    lat_rad = np.radians(grid_lat)
    n_tiles = 2.0 ** zoom
    frac_x = (grid_lon + 180.0) / 360.0 * n_tiles
    frac_y = (1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n_tiles
    
    coords = np.array([(frac_y - y0) * 256.0, (frac_x - x0) * 256.0])
    reproj = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        map_coordinates(stitched_arr[:, :, c], coords, output=reproj[:, :, c], order=1, mode='nearest')
        
    im = Image.fromarray(reproj)
    draw = ImageDraw.Draw(im)
    
    # Draw 100m grid ticks & lines
    for e in range(int(math.ceil(e_min / 100.0) * 100), int(e_max) + 1, 100):
        px = int(round((e - e_min) / res))
        draw.line([(px, 0), (px, H)], fill=(2, 132, 199, 120), width=1)
        draw.text((px + 2, H - 20), f"{e}", fill=(2, 132, 199))
        
    for n in range(int(math.ceil(n_min / 100.0) * 100), int(n_max) + 1, 100):
        py = int(round((n_max - n) / res))
        draw.line([(0, py), (W, py)], fill=(2, 132, 199, 120), width=1)
        draw.text((4, py - 14), f"{n}", fill=(2, 132, 199))
        
    # Mark current center
    cx, cy = int(round((e_center - e_min) / res)), int(round((n_max - n_center) / res))
    draw.ellipse([(cx-4, cy-4), (cx+4, cy+4)], outline=(220, 38, 38), width=2)
    
    return im

huts_to_inspect = {
    "franz_senn": (664611, 5216908),
    "regensburger": (666956, 5213587),
    "dresdner": (662663, 5207172),
    "sulzenau": (665888, 5207011),
    "oberissalm": (666518, 5218158),
    "sulzenaualm": (666164, 5207953),
    "grawaalm": (666213, 5209073),
    "tschangelair": (668106, 5210102)
}

out_dir = Path("state/maps/inspect_huts")
out_dir.mkdir(parents=True, exist_ok=True)

for name, (ec, nc) in huts_to_inspect.items():
    crop_im = render_crop(ec, nc, half_span=300, res=1.5, zoom=15)
    crop_im.save(out_dir / f"{name}_crop.png")
    print(f"Saved {name}_crop.png")
