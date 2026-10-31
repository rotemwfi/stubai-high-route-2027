import math
import pyproj
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

CACHE_DIR = Path("state/tiles/opentopomap")
to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

stage_boxes = [
    (661000, 668000, 5214000, 5221000), # Stage 1
    (663000, 670000, 5211000, 5218000), # Stage 2
    (660000, 667000, 5206000, 5214000), # Stage 3
    (661000, 668000, 5203000, 5210000), # Stage 4
    (664000, 671000, 5207000, 5214000), # Stage 5
]

all_tiles_z16 = set()

for e0, e1, n0, n1 in stage_boxes:
    lons, lats = to_wgs84.transform([e0, e1, e0, e1], [n1, n1, n0, n0])
    x0, y0 = deg2num(max(lats), min(lons), 16)
    x1, y1 = deg2num(min(lats), max(lons), 16)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            all_tiles_z16.add((x, y))

print(f"Total unique zoom 16 tiles for all 5 stages: {len(all_tiles_z16)}")

# Check how many are missing from cache
missing = []
for x, y in all_tiles_z16:
    p = CACHE_DIR / "16" / str(x) / f"{y}.png"
    if not p.exists() or p.stat().st_size < 1000:
        missing.append((x, y))

print(f"Already cached: {len(all_tiles_z16) - len(missing)}, Missing: {len(missing)}")

SERVERS = ["a", "b", "c"]
def fetch_tile_task(x, y):
    p = CACHE_DIR / "16" / str(x) / f"{y}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    server = SERVERS[(x + y) % len(SERVERS)]
    url = f"https://{server}.tile.opentopomap.org/16/{x}/{y}.png"
    headers = {"User-Agent": "StubaiMapBook16/1.0", "Referer": "https://opentopomap.org/"}
    for attempt in range(4):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                p.write_bytes(r.content)
                return True
        except:
            time.sleep(0.3)
    return False

if missing:
    print(f"Fetching {len(missing)} missing zoom 16 tiles...")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(fetch_tile_task, x, y) for x, y in missing]
        done = sum(1 for f in as_completed(futs) if f.result())
    print(f"Downloaded {done}/{len(missing)} missing tiles.")
else:
    print("All zoom 16 tiles already in cache!")
