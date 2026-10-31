import xml.etree.ElementTree as ET
import pyproj
import numpy as np

transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"]), float(p.find("{*}ele").text if p.find("{*}ele") is not None else 0)) for p in root.findall(".//{*}trkpt")]

lats = [p[0] for p in pts]
lons = [p[1] for p in pts]
eastings, northings = transformer.transform(lons, lats)
eastings = np.array(eastings)
northings = np.array(northings)

# Cumulative distance
import math
dists = [0.0]
for i in range(1, len(pts)):
    dists.append(dists[-1] + math.hypot(eastings[i]-eastings[i-1], northings[i]-northings[i-1]))

# Split into 5 days based on distance or key huts:
# Day 1: Oberissalm (0km) to Franz-Senn + glacier loop (ends around km 11.5)
# Day 2: Franz-Senn to Neue Regensburger (km 11.5 to km 21.0)
# Day 3: Neue Regensburger to Dresdner (km 21.0 to km 32.5)
# Day 4: Dresdner to Sulzenau (km 32.5 to km 40.0)
# Day 5: Sulzenau to Ranalt (km 40.0 to km 50.1)

stages = [
    ("Day 1: Oberissalm to Franz-Senn-Hütte & Alpeiner Tal", 0.0, 11500.0),
    ("Day 2: Franz-Senn-Hütte to Neue Regensburger Hütte", 11000.0, 21500.0),
    ("Day 3: Neue Regensburger Hütte to Dresdner Hütte", 21000.0, 33000.0),
    ("Day 4: Dresdner Hütte to Sulzenauhütte", 32500.0, 40500.0),
    ("Day 5: Sulzenauhütte to Grawa Alm & Ranalt", 40000.0, 50200.0),
]

for name, d0, d1 in stages:
    mask = (np.array(dists) >= d0) & (np.array(dists) <= d1)
    e_sub = eastings[mask]
    n_sub = northings[mask]
    print(f"{name}:")
    print(f"  Easting:  [{e_sub.min():.0f} .. {e_sub.max():.0f}] span {e_sub.max()-e_sub.min():.0f}m")
    print(f"  Northing: [{n_sub.min():.0f} .. {n_sub.max():.0f}] span {n_sub.max()-n_sub.min():.0f}m")
