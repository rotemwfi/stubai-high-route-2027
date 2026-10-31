import json
import xml.etree.ElementTree as ET
import math

with open("config/stubai_waypoints.json", encoding="utf-8") as f:
    cfg = json.load(f)

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"]), float(p.find("{*}ele").text if p.find("{*}ele") is not None else 0)) for p in root.findall(".//{*}trkpt")]

print("Waypoints matching to export.gpx:")
for wp in cfg["selected_route_waypoints"]:
    wplat, wplon = wp["lat"], wp["lon"]
    min_d = 1e9
    min_i = -1
    for i, p in enumerate(pts):
        d = math.hypot((p[0]-wplat)*111000, (p[1]-wplon)*111000*math.cos(math.radians(wplat)))
        if d < min_d:
            min_d = d
            min_i = i
    print(f"{wp['id']:25s} (Day {wp['day']}): min_d={min_d:5.1f}m at trkpt {min_i:4d} | {wp['name']}")
