import urllib.request
import json
import pyproj

to_utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32632', always_xy=True)

overpass_url = 'https://overpass-api.de/api/interpreter'
query = """[out:json][timeout:25];
(
  node["tourism"="alpine_hut"](46.97,11.10,47.11,11.26);
  node["amenity"="shelter"](46.97,11.10,47.11,11.26);
  node["tourism"="wilderness_hut"](46.97,11.10,47.11,11.26);
  node["tourism"="chalet"](46.97,11.10,47.11,11.26);
  node["amenity"="restaurant"](46.97,11.10,47.11,11.26);
);
out body;"""

req = urllib.request.Request(overpass_url, data=query.encode('utf-8'), headers={'User-Agent': 'StubaiExactAudit/1.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f"Total elements: {len(data['elements'])}")
        for el in data['elements']:
            tags = el.get('tags', {})
            name = tags.get('name', '')
            if name:
                lat, lon = el['lat'], el['lon']
                e, n = to_utm.transform(lon, lat)
                ele = tags.get('ele', '')
                t = tags.get('tourism', tags.get('amenity', ''))
                print(f"{name:32s} [{t:10s}] ele={ele:5s} | lat={lat:.6f}, lon={lon:.6f} | UTM E={e:8.1f}, N={n:9.1f}")
except Exception as e:
    print('Error:', e)
