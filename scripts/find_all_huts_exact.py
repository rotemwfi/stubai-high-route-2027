import urllib.request
import json
import pyproj

to_utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32632', always_xy=True)

names = [
    "Franz-Senn-Hütte",
    "Neue Regensburger Hütte",
    "Dresdner Hütte",
    "Sulzenauhütte",
    "Sulzenaualm",
    "Oberissalm",
    "Alpeineralm",
    "Grawa Alm",
    "Tschangelair Alm"
]

print("=== EXACT OSM / OPENTOPOMAP COORDINATES ===")
for name in names:
    q = urllib.parse.quote(name)
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'StubaiExactHutAudit/2.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                e, n = to_utm.transform(lon, lat)
                print(f"{name:26s} | Lat: {lat:10.6f}, Lon: {lon:10.6f} | UTM Easting: {e:8.1f} m, Northing: {n:9.1f} m")
            else:
                print(f"{name:26s} | NOT FOUND")
    except Exception as e:
        print(f"{name:26s} | Error: {e}")
