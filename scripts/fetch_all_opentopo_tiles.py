import os
import sys
import time
import math
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import xml.etree.ElementTree as ET

CACHE_DIR = Path("state/tiles/opentopomap")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SERVERS = ["a", "b", "c"]

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def fetch_single_tile(z, x, y):
    tile_path = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if tile_path.exists() and tile_path.stat().st_size > 1000:
        return z, x, y, True, "cached"
    
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    server = SERVERS[(x + y) % len(SERVERS)]
    url = f"https://{server}.tile.opentopomap.org/{z}/{x}/{y}.png"
    headers = {
        "User-Agent": "StubaiAlpineMapBook/1.0 (Mozilla/5.0 Windows NT 10.0)",
        "Referer": "https://opentopomap.org/"
    }
    
    for attempt in range(4):
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200 and len(resp.content) > 1000:
                tile_path.write_bytes(resp.content)
                return z, x, y, True, "downloaded"
            elif resp.status_code == 429:
                time.sleep(1.0 * (attempt + 1))
        except Exception:
            time.sleep(0.4 * (attempt + 1))
            
    return z, x, y, False, "failed"

def main():
    tree = ET.parse("export.gpx")
    root = tree.getroot()
    pts = [(float(p.attrib["lat"]), float(p.attrib["lon"])) for p in root.findall(".//{*}trkpt")]

    dlat = 0.015
    dlon = 0.022

    tiles_z15 = set()
    tiles_z16 = set()

    for lat, lon in pts[::4]:
        for dy in [-dlat, 0, dlat]:
            for dx in [-dlon, 0, dlon]:
                tiles_z15.add(deg2num(lat + dy, lon + dx, 15))
                tiles_z16.add(deg2num(lat + dy, lon + dx, 16))

    all_tasks = [(15, x, y) for (x, y) in tiles_z15] + [(16, x, y) for (x, y) in tiles_z16]
    print(f"Total tiles to verify/fetch: {len(all_tasks)} (z15: {len(tiles_z15)}, z16: {len(tiles_z16)})")
    
    t0 = time.time()
    downloaded = 0
    cached = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_single_tile, z, x, y): (z, x, y) for z, x, y in all_tasks}
        for i, fut in enumerate(as_completed(futures)):
            z, x, y, success, status = fut.result()
            if success:
                if status == "downloaded":
                    downloaded += 1
                else:
                    cached += 1
            else:
                failed += 1
            if (i + 1) % 100 == 0 or (i + 1) == len(all_tasks):
                print(f"Progress: {i+1}/{len(all_tasks)} ({downloaded} dl, {cached} cached, {failed} fail)")

    print(f"Done in {time.time()-t0:.2f}s! Total: {len(all_tasks)}, Downloaded: {downloaded}, Cached: {cached}, Failed: {failed}")

if __name__ == "__main__":
    main()
