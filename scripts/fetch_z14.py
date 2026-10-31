import os, time, requests
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE_DIR = Path("state/tiles/opentopomap")
SERVERS = ["a", "b", "c"]

def fetch_z14_tile(x, y):
    p = CACHE_DIR / "14" / str(x) / f"{y}.png"
    if p.exists() and p.stat().st_size > 1000:
        return True
    p.parent.mkdir(parents=True, exist_ok=True)
    server = SERVERS[(x + y) % len(SERVERS)]
    url = f"https://{server}.tile.opentopomap.org/14/{x}/{y}.png"
    headers = {"User-Agent": "StubaiMapMaker/1.0", "Referer": "https://opentopomap.org/"}
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                p.write_bytes(r.content)
                return True
        except:
            time.sleep(0.3)
    return False

tasks = [(x, y) for x in range(8696, 8706) for y in range(5754, 5766)]
print(f"Fetching {len(tasks)} Zoom 14 tiles...")
with ThreadPoolExecutor(max_workers=6) as pool:
    results = list(pool.map(lambda pt: fetch_z14_tile(*pt), tasks))
print(f"Downloaded/verified {sum(results)}/{len(tasks)} Zoom 14 tiles.")
