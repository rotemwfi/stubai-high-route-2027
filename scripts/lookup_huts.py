import urllib.request
import json
import xml.etree.ElementTree as ET
import math

huts = [
    "Franz-Senn-Hütte",
    "Neue Regensburger Hütte",
    "Dresdner Hütte",
    "Sulzenauhütte",
    "Sulzenaualm",
    "Grawa Alm",
    "Tschangelair Alm",
    "Oberissalm"
]

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"]), float(p.find("{*}ele").text if p.find("{*}ele") is not None else 0)) for p in root.findall(".//{*}trkpt")]

for hut in huts:
    q = urllib.parse.quote(hut)
    url = f"https://nominatim.openstreetmap.org/search?q={q}+Tirol&format=json&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'StubaiHutLookup/1.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data:
                h_lat = float(data[0]['lat'])
                h_lon = float(data[0]['lon'])
                # Find min distance to track
                min_d = min(math.hypot((p[0]-h_lat)*111000, (p[1]-h_lon)*111000*math.cos(math.radians(h_lat))) for p in pts)
                print(f"{hut:25s}: ({h_lat:.5f}, {h_lon:.5f}) -> {min_d:5.1f}m from track")
            else:
                print(f"{hut:25s}: Not found")
    except Exception as e:
        print(f"{hut:25s}: Error {e}")
