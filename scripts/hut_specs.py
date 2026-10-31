import pyproj
import numpy as np

to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

# Coordinates of huts in UTM Zone 32N:
# e, n: Exact building icon location on ground / GPX track
# circle_e, circle_n: Centroid of [building icon + OpenTopoMap name label]
# circle_r: Radius in meters to comfortably encompass both icon and name without cutting any text
# badge_offset: (dE, dN) offset for external badge [Night X] outside the circle
HUTS = [
    {
        "id": "franz_senn",
        "name": "Franz-Senn-Hütte",
        "label": "Franz-Senn-Hütte [Night 1 • 2,147m]",
        "badge": "Franz-Senn-Hütte [Night 1 • 2,147m]",
        "e": 664611, "n": 5216908,
        "circle_e": 664611, "circle_n": 5216908,
        "circle_r": 165,
        "badge_offset": (0, 195),
        "ele": "2,147m", "overnight": True, "night": 1
    },
    {
        "id": "regensburger",
        "name": "Neue Regensburger Hütte",
        "label": "Neue Regensburger Hütte [Night 2 • 2,286m]",
        "badge": "Neue Regensburger Hütte [Night 2 • 2,286m]",
        "e": 666952, "n": 5213592,
        "circle_e": 666950, "circle_n": 5213525,  # Shifted ~67m South so circle frames building + text below it
        "circle_r": 165,
        "badge_offset": (0, 195),
        "ele": "2,286m", "overnight": True, "night": 2
    },
    {
        "id": "dresdner",
        "name": "Dresdner Hütte",
        "label": "Dresdner Hütte [Night 3 • 2,308m]",
        "badge": "Dresdner Hütte [Night 3 • 2,308m]",
        "e": 662663, "n": 5207172,
        "circle_e": 662715, "circle_n": 5207140,  # Shifted ~52m East so circle frames building + text to right
        "circle_r": 155,
        "badge_offset": (0, 185),
        "ele": "2,308m", "overnight": True, "night": 3
    },
    {
        "id": "sulzenau",
        "name": "Sulzenauhütte",
        "label": "Sulzenauhütte [Night 4 • 2,191m]",
        "badge": "Sulzenauhütte [Night 4 • 2,191m]",
        "e": 665888, "n": 5207011,
        "circle_e": 665888, "circle_n": 5207011,
        "circle_r": 155,
        "badge_offset": (0, 185),
        "ele": "2,191m", "overnight": True, "night": 4
    },
    {
        "id": "oberissalm",
        "name": "Oberissalm",
        "label": "Oberissalm (1,742m • Trailhead)",
        "badge": "Oberissalm (Trailhead)",
        "e": 666518, "n": 5218158,
        "circle_e": 666610, "circle_n": 5218158,
        "circle_r": 140,
        "badge_offset": (0, 160),
        "ele": "1,742m", "overnight": False
    },
    {
        "id": "alpeineralm",
        "name": "Alpeineralm",
        "label": "Alpeineralm (2,040m)",
        "badge": "Alpeineralm",
        "e": 665420, "n": 5217680,
        "circle_e": 665420, "circle_n": 5217680,
        "circle_r": 125,
        "badge_offset": (0, 145),
        "ele": "2,040m", "overnight": False
    },
    {
        "id": "sulzenaualm",
        "name": "Sulzenaualm",
        "label": "Sulzenaualm (1,857m)",
        "badge": "Sulzenaualm",
        "e": 666164, "n": 5207953,
        "circle_e": 666260, "circle_n": 5208010,
        "circle_r": 125,
        "badge_offset": (0, 145),
        "ele": "1,857m", "overnight": False
    },
    {
        "id": "grawaalm",
        "name": "Grawa Alm",
        "label": "Grawa Alm (1,530m)",
        "badge": "Grawa Alm",
        "e": 666213, "n": 5209073,
        "circle_e": 666290, "circle_n": 5209040,
        "circle_r": 135,
        "badge_offset": (0, 155),
        "ele": "1,530m", "overnight": False
    },
    {
        "id": "tschangelair",
        "name": "Tschangelair Alm",
        "label": "Tschangelair Alm (1,380m)",
        "badge": "Tschangelair Alm",
        "e": 668106, "n": 5210102,
        "circle_e": 668150, "circle_n": 5210102,
        "circle_r": 135,
        "badge_offset": (0, 155),
        "ele": "1,380m", "overnight": False
    },
]

# Add WGS84 lat/lon to each hut for HTML/Leaflet viewer:
for h in HUTS:
    lon, lat = to_wgs84.transform(h["e"], h["n"])
    h["lat"] = lat
    h["lon"] = lon
    c_lon, c_lat = to_wgs84.transform(h["circle_e"], h["circle_n"])
    h["circle_lat"] = c_lat
    h["circle_lon"] = c_lon
