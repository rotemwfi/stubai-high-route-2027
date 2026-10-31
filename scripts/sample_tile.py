import requests
from pathlib import Path

CACHE_DIR = Path("state/tiles/opentopomap")
headers = {
    "User-Agent": "StubaiAlpineMapBook/1.0 (Mozilla/5.0 Windows NT 10.0)",
    "Referer": "https://opentopomap.org/"
}

# Franz-Senn-Hütte: 47.09048, 11.15505
# Zoom 16:
# lat 47.09048, lon 11.15505
import math
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

x16, y16 = deg2num(47.09048, 11.15505, 16)
x15, y15 = deg2num(47.09048, 11.15505, 15)

print(f"Franz Senn: z15=({x15}, {y15}), z16=({x16}, {y16})")

for z, x, y in [(15, x15, y15), (16, x16, y16)]:
    url = f"https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
    p = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=headers)
    p.write_bytes(r.content)
    print(f"Saved z{z} tile to {p} ({len(r.content)} bytes)")
