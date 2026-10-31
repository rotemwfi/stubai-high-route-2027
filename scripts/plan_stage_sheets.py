import xml.etree.ElementTree as ET
import pyproj
import numpy as np
import math

transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"]), float(p.find("{*}ele").text if p.find("{*}ele") is not None else 0)) for p in root.findall(".//{*}trkpt")]

lats = [p[0] for p in pts]
lons = [p[1] for p in pts]
eastings, northings = transformer.transform(lons, lats)
eastings = np.array(eastings)
northings = np.array(northings)

dists = [0.0]
for i in range(1, len(pts)):
    d = math.hypot(eastings[i] - eastings[i-1], northings[i] - northings[i-1])
    dists.append(dists[-1] + d)
dists = np.array(dists)

# Define 5 Stages
stages = [
    {
        "day": 1,
        "title": "Stage 1: Oberissalm → Franz-Senn-Hütte & Alpeiner Tal",
        "d0": 0.0,
        "d1": 11500.0,
        "huts": [("Oberissalm", 666543, 5218120, "1,742m"), ("Franz-Senn-Hütte", 664610, 5216950, "2,147m"), ("Alpeiner Glacier View", 662300, 5216600, "2,350m")]
    },
    {
        "day": 2,
        "title": "Stage 2: Franz-Senn-Hütte → Schrimmennieder (2,714m) → Neue Regensburger Hütte",
        "d0": 11000.0,
        "d1": 21500.0,
        "huts": [("Franz-Senn-Hütte", 664610, 5216950, "2,147m"), ("Schrimmennieder Pass", 667230, 5214810, "2,714m"), ("Neue Regensburger Hütte", 667280, 5212950, "2,286m")]
    },
    {
        "day": 3,
        "title": "Stage 3: Neue Regensburger Hütte → Grawagrubennieder (2,880m) → Dresdner Hütte",
        "d0": 21000.0,
        "d1": 33000.0,
        "huts": [("Neue Regensburger Hütte", 667280, 5212950, "2,286m"), ("Hohes Moos", 665200, 5211500, "2,450m"), ("Grawagrubennieder Pass", 664480, 5209700, "2,880m"), ("Dresdner Hütte", 663180, 5207250, "2,308m")]
    },
    {
        "day": 4,
        "title": "Stage 4: Dresdner Hütte → Peiljoch (2,676m) → Blaue Lacke → Sulzenauhütte",
        "d0": 32500.0,
        "d1": 40500.0,
        "huts": [("Dresdner Hütte", 663180, 5207250, "2,308m"), ("Peiljoch Pass", 664720, 5207100, "2,676m"), ("Blaue Lacke", 665500, 5206800, "2,290m"), ("Sulzenauhütte", 665980, 5207030, "2,191m")]
    },
    {
        "day": 5,
        "title": "Stage 5: Sulzenauhütte → Sulzenaualm → Grawa Waterfall → WildeWasserWeg → Ranalt",
        "d0": 40000.0,
        "d1": 50200.0,
        "huts": [("Sulzenauhütte", 665980, 5207030, "2,191m"), ("Sulzenaualm", 666280, 5207960, "1,857m"), ("Grawa Alm & Fall", 666500, 5209080, "1,530m"), ("Tschangelair Alm", 668200, 5210300, "1,380m"), ("Ranalt / Falbeson", 669512, 5212902, "1,214m")]
    },
]

for s in stages:
    mask = (dists >= s["d0"]) & (dists <= s["d1"])
    e_sub = eastings[mask]
    n_sub = northings[mask]
    
    # Target size: 6km x 6km or 7km x 5km aligned to exact 1,000m grid!
    e_center = (e_sub.min() + e_sub.max()) / 2.0
    n_center = (n_sub.min() + n_sub.max()) / 2.0
    
    # Align bounds to exact 1 km multiples
    half_w = max(3000.0, (e_sub.max() - e_sub.min()) / 2.0 + 800.0)
    half_h = max(3000.0, (n_sub.max() - n_sub.min()) / 2.0 + 800.0)
    
    e0 = math.floor((e_center - half_w) / 1000.0) * 1000.0
    e1 = math.ceil((e_center + half_w) / 1000.0) * 1000.0
    n0 = math.floor((n_center - half_h) / 1000.0) * 1000.0
    n1 = math.ceil((n_center + half_h) / 1000.0) * 1000.0
    
    s["e_min"], s["e_max"] = e0, e1
    s["n_min"], s["n_max"] = n0, n1
    print(f"Stage {s['day']}: Easting [{e0:.0f} .. {e1:.0f}] ({int(e1-e0)/1000:.0f} km), Northing [{n0:.0f} .. {n1:.0f}] ({int(n1-n0)/1000:.0f} km)")
