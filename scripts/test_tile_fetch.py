import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CACHE_DIR = Path("state/tiles/opentopomap")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SERVERS = ["a", "b", "c"]

def fetch_tile(z, x, y):
    tile_path = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if tile_path.exists() and tile_path.stat().st_size > 1000:
        return True, "cached"
    
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    server = SERVERS[(x + y) % len(SERVERS)]
    url = f"https://{server}.tile.opentopomap.org/{z}/{x}/{y}.png"
    headers = {
        "User-Agent": "StubaiAlpineMapBook/1.0 (Mozilla/5.0 Windows NT 10.0)",
        "Referer": "https://opentopomap.org/"
    }
    
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                tile_path.write_bytes(resp.content)
                return True, "downloaded"
            elif resp.status_code == 429:
                time.sleep(1.0 * (attempt + 1))
        except Exception as e:
            time.sleep(0.5)
    return False, "failed"

# Test 12 tiles around Franz-Senn-Hütte at zoom 15
t0 = time.time()
tasks = []
with ThreadPoolExecutor(max_workers=4) as pool:
    for x in range(17398, 17402):
        for y in range(11514, 11517):
            tasks.append(pool.submit(fetch_tile, 15, x, y))
    results = [t.result() for t in tasks]

elapsed = time.time() - t0
print(f"Fetched {len(results)} tiles in {elapsed:.2f}s: {results.count((True, 'downloaded'))} downloaded, {results.count((True, 'cached'))} cached")
