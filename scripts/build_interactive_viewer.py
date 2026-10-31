import json
import xml.etree.ElementTree as ET
import pyproj

transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
to_wgs = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = []
for p in root.findall(".//{*}trkpt"):
    lat = float(p.attrib["lat"])
    lon = float(p.attrib["lon"])
    ele = float(p.find("{*}ele").text) if p.find("{*}ele") is not None else 0.0
    pts.append([lat, lon, ele])

# Generate UTM grid lines for GeoJSON overlay
# Grid range: Easting 659000 to 671000, Northing 5204000 to 5220000
grid_features = []

# Vertical grid lines (constant Easting)
for e in range(659000, 672000, 1000):
    n_pts = np_n = [5204000, 5208000, 5212000, 5216000, 5220000]
    line_coords = []
    for n in n_pts:
        lon, lat = to_wgs.transform(e, n)
        line_coords.append([lon, lat])
    grid_features.append({
        "type": "Feature",
        "properties": {"name": f"{e} m E", "easting": e, "type": "easting"},
        "geometry": {"type": "LineString", "coordinates": line_coords}
    })

# Horizontal grid lines (constant Northing)
for n in range(5204000, 5221000, 1000):
    e_pts = [659000, 662000, 665000, 668000, 671000]
    line_coords = []
    for e in e_pts:
        lon, lat = to_wgs.transform(e, n)
        line_coords.append([lon, lat])
    grid_features.append({
        "type": "Feature",
        "properties": {"name": f"{n} m N", "northing": n, "type": "northing"},
        "geometry": {"type": "LineString", "coordinates": line_coords}
    })

grid_geojson = {"type": "FeatureCollection", "features": grid_features}

waypoints = [
    {"name": "Oberissalm (Start)", "lat": 47.0959, "lon": 11.1943, "ele": "1,742 m", "utm": "666 543 m E, 5 218 120 m N", "type": "start"},
    {"name": "Franz-Senn-Hütte", "lat": 47.0851, "lon": 11.1687, "ele": "2,147 m", "utm": "664 610 m E, 5 216 950 m N", "type": "hut"},
    {"name": "Schrimmennieder Pass", "lat": 47.0658, "lon": 11.2028, "ele": "2,714 m", "utm": "667 230 m E, 5 214 810 m N", "type": "pass"},
    {"name": "Neue Regensburger Hütte", "lat": 47.0547, "lon": 11.1983, "ele": "2,286 m", "utm": "667 280 m E, 5 212 950 m N", "type": "hut"},
    {"name": "Grawagrubennieder Pass", "lat": 47.0364, "lon": 11.1659, "ele": "2,880 m", "utm": "664 480 m E, 5 209 700 m N", "type": "pass"},
    {"name": "Dresdner Hütte", "lat": 46.9981, "lon": 11.1395, "ele": "2,308 m", "utm": "663 180 m E, 5 207 250 m N", "type": "hut"},
    {"name": "Peiljoch Pass", "lat": 46.9961, "lon": 11.1689, "ele": "2,676 m", "utm": "664 720 m E, 5 207 100 m N", "type": "pass"},
    {"name": "Sulzenauhütte", "lat": 46.9958, "lon": 11.1819, "ele": "2,191 m", "utm": "665 980 m E, 5 207 030 m N", "type": "hut"},
    {"name": "Sulzenaualm", "lat": 47.0042, "lon": 11.1858, "ele": "1,857 m", "utm": "666 280 m E, 5 207 960 m N", "type": "hut"},
    {"name": "Grawa Alm & Waterfall", "lat": 47.0143, "lon": 11.1869, "ele": "1,530 m", "utm": "666 500 m E, 5 209 080 m N", "type": "hut"},
    {"name": "Ranalt / Falbeson (Finish)", "lat": 47.0480, "lon": 11.2316, "ele": "1,214 m", "utm": "669 512 m E, 5 212 902 m N", "type": "finish"},
]

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stubai High Trail (2027) — OpenTopoMap with UTM Zone 32N Grid</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.0/proj4.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; height: 100vh; overflow: hidden; }}
  #sidebar {{ width: 340px; background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; border-right: 1px solid #334155; z-index: 1000; box-shadow: 2px 0 8px rgba(0,0,0,0.3); }}
  #header {{ padding: 16px; background: #1e293b; border-bottom: 1px solid #334155; }}
  #header h1 {{ margin: 0 0 6px 0; font-size: 16px; color: #38bdf8; }}
  #header p {{ margin: 0; font-size: 11px; color: #94a3b8; line-height: 1.4; }}
  #coords-box {{ padding: 10px 16px; background: #090d16; font-family: monospace; font-size: 11px; border-bottom: 1px solid #1e293b; color: #38bdf8; }}
  #controls {{ padding: 12px 16px; border-bottom: 1px solid #334155; display: flex; flex-direction: column; gap: 8px; }}
  .btn {{ background: #0284c7; color: white; border: none; padding: 8px 12px; border-radius: 6px; font-weight: bold; font-size: 12px; cursor: pointer; text-align: center; text-decoration: none; display: block; }}
  .btn:hover {{ background: #0369a1; }}
  .btn-outline {{ background: transparent; border: 1px solid #0284c7; color: #38bdf8; }}
  .btn-outline:hover {{ background: #0284c7; color: white; }}
  #wp-list {{ flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 6px; }}
  .wp-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; cursor: pointer; transition: all 0.15s; }}
  .wp-card:hover {{ border-color: #38bdf8; background: #24324a; }}
  .wp-name {{ font-weight: bold; font-size: 12px; color: #f1f5f9; }}
  .wp-sub {{ font-size: 10px; color: #94a3b8; font-family: monospace; margin-top: 2px; }}
  #map {{ flex: 1; height: 100%; }}
  .leaflet-popup-content-wrapper {{ border-radius: 8px; }}
  .grid-label {{ background: rgba(15, 23, 42, 0.85); color: #38bdf8; font-family: monospace; font-size: 10px; font-weight: bold; padding: 2px 4px; border-radius: 3px; border: 1px solid #0284c7; white-space: nowrap; }}
</style>
</head>
<body>
<div id="sidebar">
  <div id="header">
    <h1>Stubai High Trail (2027)</h1>
    <p>OpenTopoMap Topographic Viewer with 1 km UTM Zone 32N Grid Overlay</p>
  </div>
  <div id="coords-box">
    <div><strong>CURSOR UTM ZONE 32N:</strong></div>
    <div id="utm-coords">Move cursor over map...</div>
    <div style="color: #64748b; font-size: 10px; margin-top: 2px;" id="wgs-coords">Lat/Lon: --</div>
  </div>
  <div id="controls">
    <button class="btn btn-outline" id="toggle-grid">Toggle 1 km UTM Grid</button>
    <a class="btn" href="Stubai_High_Route_Complete_Map_Book.pdf" target="_blank">Download Complete PDF Atlas (7 Pages)</a>
    <a class="btn btn-outline" href="Stubai_High_Route_Overview_UTM.pdf" target="_blank">Download Overview Poster PDF</a>
  </div>
  <div id="wp-list">
    <div style="font-size: 11px; font-weight: bold; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase;">Key Trail Landmarks:</div>
    <!-- Waypoints populated by JS -->
  </div>
</div>
<div id="map"></div>

<script>
proj4.defs("EPSG:32632", "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs");

const map = L.map('map', {{
  center: [47.05, 11.18],
  zoom: 13,
  maxZoom: 17,
  minZoom: 11
}});

// Base OpenTopoMap layer
const openTopoMap = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 17,
  attribution: 'Map data: &copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href=\"https://opentopomap.org\">OpenTopoMap</a> (<a href=\"https://creativecommons.org/licenses/by-sa/3.0/\">CC-BY-SA</a>)'
}}).addTo(map);

// GPX track coordinates
const trackCoords = {json.dumps([[p[0], p[1]] for p in pts])};

// Track casing (white glow)
L.polyline(trackCoords, {{
  color: '#ffffff',
  weight: 6,
  opacity: 0.95,
  lineCap: 'round',
  lineJoin: 'round'
}}).addTo(map);

// Track core line (crimson)
const track = L.polyline(trackCoords, {{
  color: '#dc2626',
  weight: 3.5,
  opacity: 1.0,
  lineCap: 'round',
  lineJoin: 'round'
}}).addTo(map);

map.fitBounds(track.getBounds(), {{ padding: [30, 30] }});

// 1 km UTM Grid Layer
const gridGeoJSON = {json.dumps(grid_geojson)};
let gridLayer = L.geoJSON(gridGeoJSON, {{
  style: function(feature) {{
    return {{
      color: '#0284c7',
      weight: 1.0,
      opacity: 0.6,
      dashArray: '3, 4'
    }};
  }},
  onEachFeature: function(feature, layer) {{
    layer.bindTooltip(feature.properties.name, {{
      permanent: false,
      direction: 'center',
      className: 'grid-label'
    }});
  }}
}}).addTo(map);

// Grid toggle
let gridVisible = true;
document.getElementById('toggle-grid').addEventListener('click', function() {{
  if (gridVisible) {{
    map.removeLayer(gridLayer);
    this.innerText = 'Show 1 km UTM Grid';
  }} else {{
    map.addLayer(gridLayer);
    this.innerText = 'Hide 1 km UTM Grid';
  }}
  gridVisible = !gridVisible;
}});

// Cursor coordinate tracking
map.on('mousemove', function(e) {{
  const lat = e.latlng.lat;
  const lon = e.latlng.lng;
  const utm = proj4("EPSG:4326", "EPSG:32632", [lon, lat]);
  const easting = Math.round(utm[0]);
  const northing = Math.round(utm[1]);
  
  document.getElementById('utm-coords').innerText = `E ${{easting.toLocaleString()}} m  |  N ${{northing.toLocaleString()}} m`;
  document.getElementById('wgs-coords').innerText = `Lat: ${{lat.toFixed(5)}}° N, Lon: ${{lon.toFixed(5)}}° E`;
}});

// Waypoints
const waypoints = {json.dumps(waypoints)};
const wpList = document.getElementById('wp-list');

waypoints.forEach(wp => {{
  const color = wp.type === 'start' ? '#16a34a' : (wp.type === 'finish' ? '#b91c1c' : (wp.type === 'hut' ? '#0284c7' : '#9333ea'));
  const marker = L.circleMarker([wp.lat, wp.lon], {{
    radius: 7,
    fillColor: color,
    color: '#ffffff',
    weight: 2,
    fillOpacity: 0.95
  }}).addTo(map);

  const popupContent = `
    <div style=\"font-family: sans-serif;\">
      <h3 style=\"margin: 0 0 4px 0; font-size: 14px; color: ${{color}};\">${{wp.name}}</h3>
      <p style=\"margin: 0 0 4px 0; font-size: 12px;\"><strong>Elevation:</strong> ${{wp.ele}}</p>
      <p style=\"margin: 0; font-size: 11px; font-family: monospace; color: #475569;\"><strong>UTM 32N:</strong><br>${{wp.utm}}</p>
    </div>
  `;
  marker.bindPopup(popupContent);

  // Sidebar item
  const card = document.createElement('div');
  card.className = 'wp-card';
  card.innerHTML = `
    <div class=\"wp-name\" style=\"color: ${{color}};\">${{wp.name}}</div>
    <div class=\"wp-sub\">${{wp.ele}} • ${{wp.utm}}</div>
  `;
  card.addEventListener('click', () => {{
    map.flyTo([wp.lat, wp.lon], 15, {{ duration: 1 }});
    marker.openPopup();
  }});
  wpList.appendChild(card);
}});
</script>
</body>
</html>"""

with open("state/maps/Stubai_High_Route_Interactive_UTM_Map.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Saved interactive viewer to state/maps/Stubai_High_Route_Interactive_UTM_Map.html")
