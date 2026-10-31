import xml.etree.ElementTree as ET
import math

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"])) for p in root.findall(".//{*}trkpt")]

# Collect all tiles within 1.5 km of any track point
# At lat 47, 1.5km is ~0.0135 lat, ~0.020 lon
dlat = 0.012
dlon = 0.018

tiles_z15 = set()
tiles_z16 = set()

for lat, lon in pts[::5]: # sample every 5 points
    for dy in [-dlat, 0, dlat]:
        for dx in [-dlon, 0, dlon]:
            tiles_z15.add(deg2num(lat + dy, lon + dx, 15))
            tiles_z16.add(deg2num(lat + dy, lon + dx, 16))

print(f"Total Zoom 15 tiles needed: {len(tiles_z15)}")
print(f"Total Zoom 16 tiles needed: {len(tiles_z16)}")
