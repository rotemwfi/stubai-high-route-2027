import xml.etree.ElementTree as ET
import math

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"]), float(p.find("{*}ele").text if p.find("{*}ele") is not None else 0)) for p in root.findall(".//{*}trkpt")]

print(f"Total track points: {len(pts)}")
print(f"First point: {pts[0]}")
print(f"Last point:  {pts[-1]}")

# Look at points where direction changes significantly or elevation peaks/troughs
# Let's calculate cumulative distance
dists = [0.0]
for i in range(1, len(pts)):
    dlat = math.radians(pts[i][0] - pts[i-1][0])
    dlon = math.radians(pts[i][1] - pts[i-1][1])
    latmid = math.radians((pts[i][0] + pts[i-1][0]) / 2)
    dx = dlon * math.cos(latmid) * 6371000
    dy = dlat * 6371000
    dists.append(dists[-1] + math.hypot(dx, dy))

print(f"Total distance: {dists[-1]/1000:.2f} km")

# Find elevation peaks (> 2500m)
peaks = []
for i in range(10, len(pts)-10):
    if pts[i][2] > 2400 and pts[i][2] == max(pts[j][2] for j in range(i-20, i+21)):
        peaks.append((i, dists[i]/1000, pts[i]))

print("\nElevation High Points / Passes:")
for p in peaks:
    print(f"  km {p[1]:5.2f} (idx {p[0]:4d}): ele={p[2][2]:.0f}m at ({p[2][0]:.5f}, {p[2][1]:.5f})")

# Find elevation low points / Huts along the way
lows = []
for i in range(10, len(pts)-10):
    if pts[i][2] == min(pts[j][2] for j in range(i-20, i+21)):
        lows.append((i, dists[i]/1000, pts[i]))

print("\nElevation Low Points / Valleys / Huts:")
for l in lows:
    if l[2][2] < 2400:
        print(f"  km {l[1]:5.2f} (idx {l[0]:4d}): ele={l[2][2]:.0f}m at ({l[2][0]:.5f}, {l[2][1]:.5f})")
