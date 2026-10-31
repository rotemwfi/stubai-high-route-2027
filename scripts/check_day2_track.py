from inspect_huts_on_tiles import render_crop
from pathlib import Path

out_dir = Path("state/maps/inspect_huts")
# Let's inspect along the GPX track between km 16 and km 21 (end of Day 2)
# We know trkpt 1866 is at E=666963, N=5213593.
# Where does Day 2 end in config/stubai_waypoints.json or in the stage definition?
# In scripts/build_complete_map_book.py:
# d0 = 11000.0, d1 = 21500.0
# Let's see where d=18000 to d=21500 go!
import xml.etree.ElementTree as ET
import pyproj
import numpy as np

tree = ET.parse('export.gpx')
root = tree.getroot()
to_utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32632', always_xy=True)
pts = [(float(p.attrib['lat']), float(p.attrib['lon'])) for p in root.findall('.//{*}trkpt')]
e, n = to_utm.transform([p[1] for p in pts], [p[0] for p in pts])
e, n = np.array(e), np.array(n)

# Let's find trkpts between d=18000 and 22000
dists = [0.0]
for i in range(1, len(pts)):
    dists.append(dists[-1] + np.hypot(e[i]-e[i-1], n[i]-n[i-1]))
dists = np.array(dists)

idx_18k = np.argmin(np.abs(dists - 18000))
idx_20k = np.argmin(np.abs(dists - 20000))
idx_21k = np.argmin(np.abs(dists - 21500))

print(f"d=18km: pt {idx_18k} at E={e[idx_18k]:.1f}, N={n[idx_18k]:.1f}")
print(f"d=20km: pt {idx_20k} at E={e[idx_20k]:.1f}, N={n[idx_20k]:.1f}")
print(f"d=21.5km: pt {idx_21k} at E={e[idx_21k]:.1f}, N={n[idx_21k]:.1f}")
