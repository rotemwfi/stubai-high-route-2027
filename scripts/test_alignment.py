import xml.etree.ElementTree as ET
import numpy as np
import pyproj
import matplotlib.pyplot as plt
from PIL import Image

transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)

# Bounds used in test_reproject.py
e_center, n_center = 663559, 5217472
span = 2000
e_min, e_max = e_center - span, e_center + span
n_min, n_max = n_center - span, n_center + span

img = Image.open("state/test_reprojected_franz_senn.png")

# Load GPX
tree = ET.parse("export.gpx")
root = tree.getroot()
lats, lons = [], []
for p in root.findall(".//{*}trkpt"):
    lats.append(float(p.attrib["lat"]))
    lons.append(float(p.attrib["lon"]))

eastings, northings = transformer.transform(lons, lats)
eastings = np.array(eastings)
northings = np.array(northings)

# Plot with matplotlib
fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
ax.imshow(img, extent=[e_min, e_max, n_min, n_max], origin='upper')

# Filter track points within or near the box
mask = (eastings >= e_min - 200) & (eastings <= e_max + 200) & (northings >= n_min - 200) & (northings <= n_max + 200)
ax.plot(eastings[mask], northings[mask], color='white', linewidth=4, alpha=0.9)
ax.plot(eastings[mask], northings[mask], color='#dc2626', linewidth=2.5, label='GPX Track (export.gpx)')

# Draw 1 km UTM Grid lines
for e in range(int(np.ceil(e_min / 1000.0) * 1000), int(np.floor(e_max / 1000.0) * 1000) + 1, 1000):
    ax.axvline(e, color='#0284c7', linestyle='--', linewidth=0.8, alpha=0.7)
for n in range(int(np.ceil(n_min / 1000.0) * 1000), int(np.floor(n_max / 1000.0) * 1000) + 1, 1000):
    ax.axhline(n, color='#0284c7', linestyle='--', linewidth=0.8, alpha=0.7)

ax.set_xlim(e_min, e_max)
ax.set_ylim(n_min, n_max)
ax.set_title("UTM Zone 32N Alignment Test — Franz-Senn-Hütte Area", fontsize=12, fontweight='bold')
ax.set_xlabel("UTM Easting (m)")
ax.set_ylabel("UTM Northing (m)")
ax.grid(False)

plt.tight_layout()
plt.savefig("state/test_alignment_overlay.png", dpi=150)
print("Saved test alignment overlay to state/test_alignment_overlay.png")
