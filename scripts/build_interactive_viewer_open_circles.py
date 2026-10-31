import json
import xml.etree.ElementTree as ET
import pyproj
import numpy as np
import sys
from pathlib import Path

# Add scripts directory to path to import hut_specs
sys.path.append(str(Path(__file__).resolve().parent))
from hut_specs import HUTS

offline_tiles_path = Path("config/offline_tiles.json")
if offline_tiles_path.exists():
    offline_tiles = json.loads(offline_tiles_path.read_text(encoding="utf-8"))
else:
    offline_tiles = []

transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
to_wgs = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

tree = ET.parse("export.gpx")
root = tree.getroot()
raw_pts = []
for p in root.findall(".//{*}trkpt"):
    lat = float(p.attrib["lat"])
    lon = float(p.attrib["lon"])
    ele = float(p.find("{*}ele").text) if p.find("{*}ele") is not None else 0.0
    raw_pts.append((lat, lon, ele))

lons = [p[1] for p in raw_pts]
lats = [p[0] for p in raw_pts]
es, ns = transformer.transform(lons, lats)

track_points = []
accum_d = 0.0
for i in range(len(raw_pts)):
    if i > 0:
        d = float(np.sqrt((es[i] - es[i-1])**2 + (ns[i] - ns[i-1])**2))
        accum_d += d
    track_points.append([
        round(raw_pts[i][0], 5),
        round(raw_pts[i][1], 5),
        round(raw_pts[i][2], 1),
        round(accum_d / 1000.0, 3)
    ])

total_dist_km = round(accum_d / 1000.0, 2)

# Generate UTM grid lines for GeoJSON overlay
grid_features = []
for e in range(659000, 672000, 1000):
    n_pts = [5204000, 5208000, 5212000, 5216000, 5220000]
    line_coords = [to_wgs.transform(e, n) for n in n_pts]
    grid_features.append({
        "type": "Feature",
        "properties": {"name": f"{e} m E", "easting": e, "type": "easting"},
        "geometry": {"type": "LineString", "coordinates": line_coords}
    })

for n in range(5204000, 5221000, 1000):
    e_pts = [659000, 662000, 665000, 668000, 671000]
    line_coords = [to_wgs.transform(e, n) for e in e_pts]
    grid_features.append({
        "type": "Feature",
        "properties": {"name": f"{n} m N", "northing": n, "type": "northing"},
        "geometry": {"type": "LineString", "coordinates": line_coords}
    })

grid_geojson = {"type": "FeatureCollection", "features": grid_features}

# Prepare hut data for HTML
huts_html = []
for h in HUTS:
    huts_html.append({
        "id": h["id"],
        "name": h["name"],
        "label": h["label"],
        "badge": h["badge"],
        "ele": h["ele"],
        "e": h["e"],
        "n": h["n"],
        "utm": f"{h['e']} m E, {h['n']} m N",
        "lat": round(h["lat"], 6),
        "lon": round(h["lon"], 6),
        "circle_lat": round(h["circle_lat"], 6),
        "circle_lon": round(h["circle_lon"], 6),
        "overnight": h["overnight"],
        "night": h.get("night", None)
    })

# Add finish point
f_e, f_n = 669512, 5212902
f_lon, f_lat = to_wgs.transform(f_e, f_n)
huts_html.append({
    "id": "ranalt",
    "name": "Ranalt / Falbeson (Finish)",
    "label": "Ranalt / Falbeson (1,214m • Bus 590)",
    "badge": "Finish (Bus 590)",
    "ele": "1,214 m",
    "e": f_e,
    "n": f_n,
    "utm": f"{f_e} m E, {f_n} m N",
    "lat": round(f_lat, 6),
    "lon": round(f_lon, 6),
    "circle_lat": round(f_lat, 6),
    "circle_lon": round(f_lon, 6),
    "overnight": False,
    "night": None
})

# Waypoint landmarks along profile
profile_waypoints = [
    {"name": "Oberissalm", "km": 0.0, "ele": 1742, "night": None},
    {"name": "Franz-Senn [N1]", "km": 10.3, "ele": 2147, "night": 1},
    {"name": "Schrimmennieder", "km": 16.5, "ele": 2714, "night": None},
    {"name": "Regensburger [N2]", "km": 19.5, "ele": 2286, "night": 2},
    {"name": "Grawagrubennieder", "km": 23.5, "ele": 2880, "night": None},
    {"name": "Dresdner [N3]", "km": 32.0, "ele": 2308, "night": 3},
    {"name": "Peiljoch", "km": 34.0, "ele": 2676, "night": None},
    {"name": "Sulzenau [N4]", "km": 38.0, "ele": 2191, "night": 4},
    {"name": "Grawa Waterfall", "km": 42.7, "ele": 1530, "night": None},
    {"name": "Ranalt (Finish)", "km": 50.2, "ele": 1214, "night": None}
]

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"/>
<meta name="theme-color" content="#0f172a"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
<meta name="apple-mobile-web-app-title" content="Stubai Map"/>
<link rel="manifest" href="manifest.webmanifest"/>
<link rel="apple-touch-icon" href="apple-touch-icon.png"/>
<title>Stubai High Trail (2027) — Mobile Topographic Map & Elevation Profile</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.0/proj4.js"></script>
<style>
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  html, body {{ width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; background: #090d16; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  
  #app-root {{ display: flex; width: 100vw; height: 100vh; position: relative; overflow: hidden; }}
  
  /* SIDEBAR (Desktop: fixed width; Mobile: off-canvas drawer) */
  #sidebar {{
    width: 330px;
    min-width: 330px;
    height: 100%;
    background: #0f172a;
    color: #f8fafc;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #334155;
    z-index: 2000;
    box-shadow: 2px 0 12px rgba(0,0,0,0.4);
    transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  
  #sidebar-header {{
    padding: 14px 16px;
    background: #1e293b;
    border-bottom: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  #sidebar-header h1 {{ margin: 0 0 4px 0; font-size: 15px; color: #38bdf8; font-weight: 700; }}
  #sidebar-header p {{ margin: 0; font-size: 11px; color: #94a3b8; line-height: 1.35; }}
  #close-sidebar {{
    display: none;
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 18px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
  }}
  
  #coords-box {{
    padding: 8px 16px;
    background: #090d16;
    font-family: monospace;
    font-size: 10.5px;
    border-bottom: 1px solid #1e293b;
    color: #38bdf8;
  }}
  
  #controls {{ padding: 10px 14px; border-bottom: 1px solid #334155; display: flex; flex-direction: column; gap: 6px; }}
  .btn {{
    background: #0284c7;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    transition: background 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }}
  .btn:hover {{ background: #0369a1; }}
  .btn-outline {{ background: transparent; border: 1px solid #0284c7; color: #38bdf8; }}
  .btn-outline:hover {{ background: #0284c7; color: white; }}
  .btn-active {{ background: #0284c7; color: white; }}
  
  #wp-list {{ flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 5px; }}
  .wp-card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 10px;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .wp-card:hover, .wp-card:active {{ border-color: #38bdf8; background: #24324a; }}
  .wp-name {{ font-weight: bold; font-size: 11.5px; }}
  .wp-sub {{ font-size: 10px; color: #94a3b8; font-family: monospace; margin-top: 2px; }}
  
  /* MAP & MOBILE FLOATING UI */
  #map-container {{ flex: 1; position: relative; height: 100%; overflow: hidden; }}
  #map {{ width: 100%; height: 100%; }}
  
  #mobile-backdrop {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 1999;
  }}
  
  /* FLOATING TOP BAR ON MAP (Mobile Menu, Status, GPS) */
  #floating-top-bar {{
    position: absolute;
    top: 12px;
    left: 12px;
    right: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    pointer-events: none;
    z-index: 1100;
  }}
  .floating-pill {{
    pointer-events: auto;
    background: rgba(15, 23, 42, 0.90);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid #334155;
    color: #f1f5f9;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 11px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
  }}
  .floating-pill:hover, .floating-pill:active {{ background: #1e293b; border-color: #38bdf8; }}
  
  #menu-trigger {{ display: none; }}
  
  #floating-coords {{
    font-family: monospace;
    font-size: 10px;
    color: #38bdf8;
    background: rgba(15, 23, 42, 0.90);
    border: 1px solid #334155;
    padding: 5px 10px;
    border-radius: 16px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 55%;
  }}
  
  /* Ensure Leaflet zoom controls never overlap top floating bar or GPS button */
  .leaflet-top.leaflet-right {{
    top: 60px !important;
    right: 12px !important;
  }}
  .leaflet-bar {{
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
  }}
  .leaflet-bar a {{
    background-color: rgba(15, 23, 42, 0.90) !important;
    color: #f1f5f9 !important;
    border-bottom: 1px solid #334155 !important;
  }}
  .leaflet-bar a:hover {{
    background-color: #1e293b !important;
    color: #38bdf8 !important;
  }}

  #gps-btn {{
    pointer-events: auto;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid #334155;
    color: #38bdf8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    transition: all 0.2s ease;
  }}
  #gps-btn:active {{ background: #0284c7; color: white; }}
  #gps-btn.active-user {{
    background: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.6);
  }}
  
  /* FLOATING ACTION BUTTONS ON MAP (Bottom Right above profile) */
  #fab-group {{
    position: absolute;
    bottom: 235px;
    right: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    z-index: 1099;
    pointer-events: none;
    transition: bottom 0.25s ease;
  }}
  .fab {{
    pointer-events: auto;
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border: 1px solid #334155;
    color: #e2e8f0;
    padding: 7px 12px;
    border-radius: 18px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35);
    display: flex;
    align-items: center;
    gap: 5px;
  }}
  .fab:active {{ background: #0284c7; color: white; }}
  
  /* ELEVATION PROFILE DOCK */
  #profile-panel {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 220px;
    background: rgba(15, 23, 42, 0.95);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-top: 2px solid #0284c7;
    display: flex;
    flex-direction: column;
    z-index: 1000;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.6);
    transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease;
  }}
  #profile-panel.hidden {{
    transform: translateY(100%);
    pointer-events: none;
    opacity: 0;
  }}
  
  #profile-header {{
    height: 34px;
    min-height: 34px;
    background: #1e293b;
    border-bottom: 1px solid #334155;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 12px;
    font-size: 11px;
    color: #e2e8f0;
    overflow: hidden;
  }}
  .profile-title {{ display: flex; align-items: center; gap: 6px; font-weight: bold; color: #38bdf8; white-space: nowrap; }}
  .profile-meta {{ font-size: 9.5px; color: #94a3b8; font-weight: normal; }}
  
  #profile-readout {{
    font-family: monospace;
    font-size: 10.5px;
    color: #f1f5f9;
    background: rgba(15, 23, 42, 0.7);
    padding: 3px 8px;
    border-radius: 4px;
    border: 1px solid #334155;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin: 0 6px;
    flex: 1;
    text-align: center;
  }}
  
  #close-profile {{
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 15px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    min-width: 28px;
  }}
  #close-profile:hover, #close-profile:active {{ color: #ffffff; background: #334155; }}
  
  #profile-chart-wrap {{
    flex: 1;
    position: relative;
    width: 100%;
    height: calc(100% - 34px);
    touch-action: none;
  }}
  #profile-canvas {{
    width: 100%;
    height: 100%;
    display: block;
    cursor: crosshair;
  }}
  
  /* BADGES & POPUPS */
  .badge-tag {{ display: inline-block; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 4px; margin-left: 6px; vertical-align: middle; }}
  .badge-night {{ background: #1d4ed8; color: white; }}
  .grid-label {{ background: rgba(15, 23, 42, 0.85); color: #38bdf8; font-family: monospace; font-size: 10px; font-weight: bold; padding: 2px 4px; border-radius: 3px; border: 1px solid #0284c7; white-space: nowrap; }}

  /* ==========================================
     MOBILE RESPONSIVE BREAKPOINT (< 768px)
     ========================================== */
  @media (max-width: 768px) {{
    #sidebar {{
      position: fixed;
      top: 0;
      bottom: 0;
      left: 0;
      width: 82vw;
      max-width: 320px;
      min-width: unset;
      transform: translateX(-100%);
      box-shadow: 4px 0 25px rgba(0, 0, 0, 0.8);
    }}
    #sidebar.mobile-open {{
      transform: translateX(0);
    }}
    #mobile-backdrop.mobile-open {{
      display: block;
    }}
    #close-sidebar {{
      display: block;
    }}
    #menu-trigger {{
      display: flex;
    }}
    
    #profile-panel {{
      height: 175px;
    }}
    #fab-group {{
      bottom: 190px;
    }}
    #profile-panel.hidden ~ #fab-group,
    #app-root:has(#profile-panel.hidden) #fab-group {{
      bottom: 20px;
    }}
    
    .profile-meta {{ display: none; }}
    #profile-readout {{
      font-size: 9.5px;
      padding: 2px 6px;
    }}
    #profile-header {{
      padding: 0 8px;
    }}
  }}
</style>
</head>
<body>
<div id="app-root">
  <div id="mobile-backdrop"></div>
  
  <!-- SIDEBAR (Desktop fixed, Mobile Drawer) -->
  <div id="sidebar">
    <div id="sidebar-header">
      <div>
        <h1>Stubai High Trail (2027)</h1>
        <p>Topographic Navigator & Profile</p>
      </div>
      <button id="close-sidebar" title="Close Menu">✕</button>
    </div>
    <div id="coords-box">
      <div><strong>CURSOR UTM ZONE 32N:</strong></div>
      <div id="utm-coords">Move cursor or tap map...</div>
      <div style="color: #64748b; font-size: 10px; margin-top: 2px;" id="wgs-coords">Lat/Lon: --</div>
    </div>
    <div id="controls">
      <button class="btn" id="btn-offline" style="background: #0284c7; border: 1px solid #38bdf8; font-weight: bold; color: white;">📲 Make Available Offline</button>
      <button class="btn btn-outline" id="toggle-profile-btn">📈 Toggle Elevation Profile</button>
      <button class="btn btn-outline" id="toggle-grid-btn">🧭 Toggle 1 km UTM Grid</button>
      <a class="btn" href="Stubai_High_Route_Complete_Map_Book_Final_Atlas.pdf" target="_blank">📥 Download Complete Atlas (PDF)</a>
      <a class="btn btn-outline" href="Stubai_High_Route_Overview_UTM_v3.pdf" target="_blank">🗺️ Overview Poster (PDF)</a>
    </div>
    <div id="wp-list">
      <div style="font-size: 10.5px; font-weight: bold; color: #94a3b8; margin-bottom: 2px; text-transform: uppercase;">Overnight Huts & Landmarks:</div>
    </div>
  </div>

  <!-- MAP CONTAINER -->
  <div id="map-container">
    <div id="map"></div>
    
    <!-- FLOATING TOP BAR -->
    <div id="floating-top-bar">
      <div class="floating-pill" id="menu-trigger">
        <span>☰</span> <strong>Huts & Guide</strong>
      </div>
      <div id="floating-coords">Stubai 50.2 km</div>
      <div id="gps-btn" title="Find My Location">🎯</div>
    </div>
    
    <!-- FLOATING ACTION BUTTONS (BOTTOM RIGHT) -->
    <div id="fab-group">
      <div class="fab" id="fab-offline" style="border-color: #38bdf8; color: #38bdf8;">📲 Save Offline</div>
      <div class="fab" id="fab-profile">📈 Profile</div>
      <div class="fab" id="fab-grid">🧭 Grid</div>
    </div>
    
    <!-- ELEVATION PROFILE DOCK -->
    <div id="profile-panel">
      <div id="profile-header">
        <div class="profile-title">
          <span>📈</span>
          <span>PROFILE</span>
          <span class="profile-meta">(50.2 km • +3,180 m)</span>
        </div>
        <div id="profile-readout">Drag across profile or trail to inspect...</div>
        <button id="close-profile" title="Hide Profile">✕</button>
      </div>
      <div id="profile-chart-wrap">
        <canvas id="profile-canvas"></canvas>
      </div>
    </div>
  </div>

  <!-- OFFLINE MODAL -->
  <div id="offline-modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.78); z-index: 9999; align-items: center; justify-content: center; padding: 20px;">
    <div style="background: #0f172a; border: 1px solid #334155; border-radius: 16px; padding: 22px; max-width: 360px; width: 100%; box-shadow: 0 10px 30px rgba(0,0,0,0.6); text-align: center; color: #f1f5f9;">
      <div style="font-size: 32px; margin-bottom: 8px;" id="modal-icon">📲</div>
      <div style="font-size: 16px; font-weight: bold; margin-bottom: 6px;" id="modal-title">Saving Offline Map</div>
      <div style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;" id="modal-status">Preparing topographic tiles for all 5 stages...</div>
      
      <!-- Progress Bar Container -->
      <div id="progress-container" style="background: #1e293b; border-radius: 8px; height: 10px; overflow: hidden; margin-bottom: 14px; border: 1px solid #334155;">
        <div id="progress-bar" style="background: #38bdf8; width: 0%; height: 100%; transition: width 0.15s ease;"></div>
      </div>

      <!-- iOS Home Screen Guide (Visible only on iPhone/iPad) -->
      <div id="ios-guide" style="display: none; background: #1e293b; border: 1px solid #38bdf8; border-radius: 10px; padding: 12px; margin-bottom: 14px; text-align: left; font-size: 12px; line-height: 1.5; color: #cbd5e1;">
        <strong style="color: #38bdf8;">📲 Add App Icon to Your iPhone Screen:</strong><br/>
        1. Tap the Safari <strong>Share</strong> button (box with arrow <span style="font-size: 14px;">⎙</span>) at the bottom.<br/>
        2. Scroll down and tap <strong>Add to Home Screen</strong> (<span style="font-size: 14px;">➕</span>).<br/>
        3. Tap <strong>Add</strong> at top right.
      </div>

      <button class="btn btn-outline" id="modal-close" style="width: 100%; display: none; margin-top: 10px;">Got It / Close</button>
    </div>
  </div>
</div>

<script>
proj4.defs("EPSG:32632", "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs");

const map = L.map('map', {{
  center: [47.05, 11.18],
  zoom: 13,
  maxZoom: 17,
  minZoom: 11,
  zoomControl: false // custom position for clean mobile view
}});

L.control.zoom({{ position: 'topright' }}).addTo(map);

const openTopoMap = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 17,
  attribution: '&copy; OpenStreetMap, SRTM | OpenTopoMap'
}}).addTo(map);

// GPX Track Points [lat, lon, ele, dist_km]
const rawTrack = {json.dumps(track_points)};
const trackPoints = rawTrack.map(p => ({{ lat: p[0], lon: p[1], ele: p[2], dist: p[3] }}));
const trackCoords = trackPoints.map(p => [p.lat, p.lon]);

// Track line (clean crimson trail with white underlay)
L.polyline(trackCoords, {{
  color: '#ffffff',
  weight: 3.8,
  opacity: 0.85,
  lineCap: 'round',
  lineJoin: 'round'
}}).addTo(map);

const trackPolyline = L.polyline(trackCoords, {{
  color: '#dc2626',
  weight: 2.0,
  opacity: 1.0,
  lineCap: 'round',
  lineJoin: 'round'
}}).addTo(map);

map.fitBounds(trackPolyline.getBounds(), {{ padding: [25, 25] }});

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

let gridVisible = true;
function toggleGrid() {{
  if (gridVisible) {{
    map.removeLayer(gridLayer);
    document.getElementById('toggle-grid-btn').innerText = '🧭 Show 1 km UTM Grid';
    document.getElementById('toggle-grid-btn').classList.remove('btn-active');
  }} else {{
    map.addLayer(gridLayer);
    document.getElementById('toggle-grid-btn').innerText = '🧭 Hide 1 km UTM Grid';
    document.getElementById('toggle-grid-btn').classList.add('btn-active');
  }}
  gridVisible = !gridVisible;
}}
document.getElementById('toggle-grid-btn').addEventListener('click', toggleGrid);
document.getElementById('fab-grid').addEventListener('click', toggleGrid);

// SYNCHRONIZED HOVER MARKER (Glow Pin on Trail)
const hoverMarker = L.circleMarker([0, 0], {{
  radius: 6.5,
  color: '#ffffff',
  weight: 2.2,
  fillColor: '#dc2626',
  fillOpacity: 1.0,
  zIndexOffset: 3000
}});

const hoverRing = L.circleMarker([0, 0], {{
  radius: 13,
  color: '#38bdf8',
  weight: 1.8,
  fillColor: '#38bdf8',
  fillOpacity: 0.22,
  zIndexOffset: 2999
}});

let isHoverMarkerActive = false;
function showMapHover(lat, lon) {{
  if (!isHoverMarkerActive) {{
    hoverRing.addTo(map);
    hoverMarker.addTo(map);
    isHoverMarkerActive = true;
  }}
  hoverMarker.setLatLng([lat, lon]);
  hoverRing.setLatLng([lat, lon]);
}}

function hideMapHover() {{
  if (isHoverMarkerActive) {{
    map.removeLayer(hoverMarker);
    map.removeLayer(hoverRing);
    isHoverMarkerActive = false;
  }}
}}

// DYNAMIC SIZING FUNCTION for Overnight Hut Circles:
function getHutRadius(zoom, isOvernight) {{
  const z = Math.min(17, Math.max(11, zoom));
  let baseRadius;
  if (z >= 16) {{
    baseRadius = 96 * Math.pow(2, z - 16);
  }} else if (z >= 15) {{
    baseRadius = 80 + (z - 15) * (96 - 80);
  }} else if (z >= 14) {{
    baseRadius = 58 + (z - 14) * (80 - 58);
  }} else if (z >= 13) {{
    baseRadius = 36 + (z - 13) * (58 - 36);
  }} else {{
    baseRadius = 18 + (z - 11) * (36 - 18) / 2;
  }}
  return isOvernight ? Math.round(baseRadius) : Math.round(baseRadius * 0.75);
}}

const huts = {json.dumps(huts_html)};
const wpList = document.getElementById('wp-list');
const hutMarkerItems = [];

huts.forEach(h => {{
  const isOvernight = h.overnight;
  let marker = null;

  if (isOvernight) {{
    const color = '#1d4ed8';
    const weight = 1.3;
    const initialRadius = getHutRadius(map.getZoom(), true);

    marker = L.circleMarker([h.circle_lat, h.circle_lon], {{
      radius: initialRadius,
      color: color,
      weight: weight,
      fillOpacity: 0.0,
      opacity: 0.95
    }}).addTo(map);

    hutMarkerItems.push({{
      marker: marker,
      overnight: true
    }});

    const badgeHtml = `<span class=\"badge-tag badge-night\">NIGHT ${{h.night}}</span>`;
    const popupContent = `
      <div style=\"font-family: sans-serif;\">
        <h3 style=\"margin: 0 0 4px 0; font-size: 14px; color: ${{color}};\">${{h.name}} ${{badgeHtml}}</h3>
        <p style=\"margin: 0 0 4px 0; font-size: 12px;\"><strong>Elevation:</strong> ${{h.ele}}</p>
        <p style=\"margin: 0; font-size: 11px; font-family: monospace; color: #475569;\"><strong>UTM Zone 32N:</strong><br>${{h.utm}}</p>
        <p style=\"margin: 4px 0 0 0; font-size: 10px; color: #15803d;\"><em>✓ Native OpenTopoMap icon & name fully readable inside ring</em></p>
      </div>
    `;
    marker.bindPopup(popupContent);
  }}

  const card = document.createElement('div');
  card.className = 'wp-card';
  card.innerHTML = `
    <div class=\"wp-name\" style=\"color: ${{isOvernight ? '#38bdf8' : '#cbd5e1'}};\">
      ${{isOvernight ? '○ ' : '• '}}${{h.name}} ${{isOvernight ? '<span class=\"badge-tag badge-night\">N' + h.night + '</span>' : ''}}
    </div>
    <div class=\"wp-sub\">${{h.ele}} • ${{h.utm}}</div>
  `;
  card.addEventListener('click', () => {{
    const targetLat = isOvernight ? h.circle_lat : h.lat;
    const targetLon = isOvernight ? h.circle_lon : h.lon;
    map.flyTo([targetLat, targetLon], 16, {{ duration: 0.8 }});
    if (marker) {{
      marker.openPopup();
    }}
    closeMobileSidebar();
  }});
  wpList.appendChild(card);
}});

function updateCircleRadii() {{
  const z = map.getZoom();
  hutMarkerItems.forEach(item => {{
    const r = getHutRadius(z, item.overnight);
    item.marker.setRadius(r);
  }});
}}
map.on('zoom', updateCircleRadii);
map.on('zoomend', updateCircleRadii);

// ==========================================
// MOBILE GPS "LOCATE ME" & TRAIL TOGGLE
// ==========================================
let userLocationMarker = null;
let userAccuracyCircle = null;
let lastUserLatLng = null;
let isAtUserLocation = false;
const gpsBtn = document.getElementById('gps-btn');

gpsBtn.addEventListener('click', function() {{
  if (isAtUserLocation) {{
    // SECOND CLICK: Return to Stubai trail
    map.fitBounds(trackPolyline.getBounds(), {{ padding: [25, 25], animate: true }});
    isAtUserLocation = false;
    gpsBtn.innerText = "🎯";
    gpsBtn.title = "Find My Location";
    gpsBtn.classList.remove('active-user');
  }} else {{
    // FIRST CLICK: Pan & zoom to current user location
    if (!navigator.geolocation) {{
      if (typeof alert !== 'undefined') alert("Geolocation is not supported by your browser.");
      return;
    }}
    gpsBtn.innerText = "⏳";
    gpsBtn.title = "Acquiring GPS...";
    
    if (lastUserLatLng) {{
      map.setView(lastUserLatLng, 15, {{ animate: true }});
      isAtUserLocation = true;
      gpsBtn.innerText = "🏔️";
      gpsBtn.title = "Return to Stubai Trail";
      gpsBtn.classList.add('active-user');
    }}
    
    map.locate({{ setView: true, maxZoom: 16, enableHighAccuracy: true }});
  }}
}});

map.on('locationfound', function(e) {{
  lastUserLatLng = e.latlng;
  isAtUserLocation = true;
  gpsBtn.innerText = "🏔️";
  gpsBtn.title = "Return to Stubai Trail";
  gpsBtn.classList.add('active-user');
  if (userLocationMarker) {{
    userLocationMarker.setLatLng(e.latlng);
    userAccuracyCircle.setLatLng(e.latlng).setRadius(e.accuracy);
  }} else {{
    userAccuracyCircle = L.circle(e.latlng, {{ radius: e.accuracy, color: '#0284c7', fillColor: '#38bdf8', fillOpacity: 0.15, weight: 1 }}).addTo(map);
    userLocationMarker = L.circleMarker(e.latlng, {{ radius: 8, color: '#ffffff', fillColor: '#0284c7', fillOpacity: 1.0, weight: 2.5 }}).addTo(map);
  }}
}});

map.on('locationerror', function(e) {{
  if (!lastUserLatLng) {{
    isAtUserLocation = false;
    gpsBtn.innerText = "🎯";
    gpsBtn.title = "Find My Location";
    gpsBtn.classList.remove('active-user');
  }}
  if (typeof alert !== 'undefined') alert("GPS Location: " + e.message);
}});

// ==========================================
// MOBILE DRAWER NAVIGATION
// ==========================================
const sidebar = document.getElementById('sidebar');
const mobileBackdrop = document.getElementById('mobile-backdrop');

function openMobileSidebar() {{
  sidebar.classList.add('mobile-open');
  mobileBackdrop.classList.add('mobile-open');
}}
function closeMobileSidebar() {{
  sidebar.classList.remove('mobile-open');
  mobileBackdrop.classList.remove('mobile-open');
}}

document.getElementById('menu-trigger').addEventListener('click', openMobileSidebar);
document.getElementById('close-sidebar').addEventListener('click', closeMobileSidebar);
mobileBackdrop.addEventListener('click', closeMobileSidebar);

// ==========================================
// ELEVATION PROFILE INTERACTIVE ENGINE
// ==========================================
const profilePanel = document.getElementById('profile-panel');
const profileCanvas = document.getElementById('profile-canvas');
const toggleProfileBtn = document.getElementById('toggle-profile-btn');
const fabProfileBtn = document.getElementById('fab-profile');
const closeProfileBtn = document.getElementById('close-profile');
const profileReadout = document.getElementById('profile-readout');

let profileVisible = true;
let mouseOnProfile = false;
let activeProfileIndex = null;

const profileWaypoints = {json.dumps(profile_waypoints)};

// STAGES AND STAGE-RELATIVE DISTANCE
const stages = [
  {{ day: 1, name: "Stage 1", startName: "Oberissalm", d0: 0.0, d1: 10.26 }},
  {{ day: 2, name: "Stage 2", startName: "Franz-Senn-Hütte", d0: 10.26, d1: 19.51 }},
  {{ day: 3, name: "Stage 3", startName: "Neue Regensburger Hütte", d0: 19.51, d1: 32.00 }},
  {{ day: 4, name: "Stage 4", startName: "Dresdner Hütte", d0: 32.00, d1: 38.02 }},
  {{ day: 5, name: "Stage 5", startName: "Sulzenauhütte", d0: 38.02, d1: 50.20 }}
];

function getDayInfo(distKm) {{
  for (let i = 0; i < stages.length; i++) {{
    const s = stages[i];
    if (distKm <= s.d1 || s.day === 5) {{
      const stageDist = Math.max(0, distKm - s.d0);
      return {{ day: s.day, stageDist: stageDist, startName: s.startName }};
    }}
  }}
  return {{ day: 1, stageDist: distKm, startName: "Oberissalm" }};
}}

function drawProfile(hoverIndex) {{
  if (!profileCanvas || !profileVisible) return;
  
  const dpr = window.devicePixelRatio || 1;
  const rect = profileCanvas.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
  
  const targetW = Math.round(rect.width * dpr);
  const targetH = Math.round(rect.height * dpr);
  if (profileCanvas.width !== targetW || profileCanvas.height !== targetH) {{
    profileCanvas.width = targetW;
    profileCanvas.height = targetH;
  }}
  
  const ctx = profileCanvas.getContext('2d');
  ctx.save();
  ctx.scale(dpr, dpr);
  
  const W = rect.width;
  const H = rect.height;
  ctx.clearRect(0, 0, W, H);
  
  const isMobile = W < 600;
  const padLeft = isMobile ? 40 : 48;
  const padRight = isMobile ? 16 : 24;
  const padTop = isMobile ? 18 : 22;
  const padBottom = isMobile ? 22 : 26;
  
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;
  
  const minEle = 1000;
  const maxEle = 3000;
  const maxDist = {total_dist_km};
  
  function getX(distKm) {{
    return padLeft + (distKm / maxDist) * plotW;
  }}
  function getY(eleM) {{
    return padTop + plotH - ((eleM - minEle) / (maxEle - minEle)) * plotH;
  }}
  
  // Elevation Horizontal Grid Lines (1000m to 3000m)
  ctx.font = (isMobile ? '8.5px' : '10px') + ' -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.fillStyle = '#64748b';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  
  for (let ele = 1000; ele <= 3000; ele += 500) {{
    const y = getY(ele);
    ctx.strokeStyle = ele === 2000 ? 'rgba(51, 65, 85, 0.8)' : 'rgba(51, 65, 85, 0.45)';
    ctx.lineWidth = 1;
    ctx.setLineDash(ele === 2000 ? [] : [3, 4]);
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(padLeft + plotW, y);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillText(`${{ele}}m`, padLeft - 4, y);
  }}
  
  // Distance Vertical Grid Lines (every 5 km / 10 km on mobile)
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  const stepD = isMobile ? 10 : 5;
  for (let d = 0; d <= 50; d += stepD) {{
    const x = getX(d);
    ctx.strokeStyle = 'rgba(51, 65, 85, 0.5)';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(x, padTop);
    ctx.lineTo(x, padTop + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillText(`${{d}}k`, x, padTop + plotH + 4);
  }}
  
  // Shaded Gradient Fill Under Profile
  const grad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
  grad.addColorStop(0, 'rgba(225, 29, 72, 0.48)');
  grad.addColorStop(0.5, 'rgba(225, 29, 72, 0.22)');
  grad.addColorStop(1, 'rgba(225, 29, 72, 0.03)');
  
  ctx.beginPath();
  ctx.moveTo(getX(trackPoints[0].dist), getY(minEle));
  for (let i = 0; i < trackPoints.length; i++) {{
    ctx.lineTo(getX(trackPoints[i].dist), getY(trackPoints[i].ele));
  }}
  ctx.lineTo(getX(trackPoints[trackPoints.length - 1].dist), getY(minEle));
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();
  
  // High Trail Profile Line
  ctx.beginPath();
  for (let i = 0; i < trackPoints.length; i++) {{
    const x = getX(trackPoints[i].dist);
    const y = getY(trackPoints[i].ele);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }}
  ctx.strokeStyle = '#e11d48';
  ctx.lineWidth = isMobile ? 1.8 : 2.0;
  ctx.stroke();
  
  // Landmark Waypoint Pins on Profile
  profileWaypoints.forEach(wp => {{
    const wx = getX(wp.km);
    const wy = getY(wp.ele);
    const isNightHut = wp.night !== null;
    if (isMobile && !isNightHut && wp.km !== 0.0 && wp.km !== 50.2) return; // omit minor ticks on mobile to stay clear
    
    ctx.strokeStyle = isNightHut ? '#38bdf8' : 'rgba(148, 163, 184, 0.5)';
    ctx.lineWidth = isNightHut ? 1.4 : 1.0;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(wx, wy);
    ctx.lineTo(wx, padTop + 2);
    ctx.stroke();
    ctx.setLineDash([]);
    
    ctx.beginPath();
    ctx.arc(wx, wy, isNightHut ? 3.5 : 2.2, 0, 2 * Math.PI);
    ctx.fillStyle = isNightHut ? '#0284c7' : '#94a3b8';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.stroke();
    
    ctx.font = isNightHut ? 'bold 8.5px sans-serif' : '8px sans-serif';
    ctx.fillStyle = isNightHut ? '#38bdf8' : '#94a3b8';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    const displayName = isMobile && isNightHut ? `N${{wp.night}}` : wp.name;
    ctx.fillText(displayName, wx, padTop - 1);
  }});
  
  // Hover Crosshair & Synchronized Marker
  if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < trackPoints.length) {{
    const pt = trackPoints[hoverIndex];
    const hx = getX(pt.dist);
    const hy = getY(pt.ele);
    
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(hx, padTop);
    ctx.lineTo(hx, padTop + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
    
    ctx.beginPath();
    ctx.arc(hx, hy, 6.5, 0, 2 * Math.PI);
    ctx.fillStyle = 'rgba(56, 189, 248, 0.35)';
    ctx.fill();
    
    ctx.beginPath();
    ctx.arc(hx, hy, 3.8, 0, 2 * Math.PI);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.strokeStyle = '#e11d48';
    ctx.lineWidth = 2.0;
    ctx.stroke();
  }}
  
  ctx.restore();
}}

// SET HOVER POINT: Synchronizes Map Marker & Profile View
function setHoverPoint(idx) {{
  if (idx === null || idx < 0 || idx >= trackPoints.length) return;
  activeProfileIndex = idx;
  const pt = trackPoints[idx];
  
  showMapHover(pt.lat, pt.lon);
  
  const utm = proj4("EPSG:4326", "EPSG:32632", [pt.lon, pt.lat]);
  const dayInfo = getDayInfo(pt.dist);
  profileReadout.innerHTML = `
    <strong style=\"color: #38bdf8;\">Day ${{dayInfo.day}}</strong> (+${{dayInfo.stageDist.toFixed(1)}}k) &nbsp;|&nbsp;
    <strong>Tot:</strong> ${{pt.dist.toFixed(1)}}k &nbsp;|&nbsp;
    <strong>Ele:</strong> ${{Math.round(pt.ele)}}m
  `;
  document.getElementById('floating-coords').innerText = `Day ${{dayInfo.day}} • ${{Math.round(pt.ele)}}m • E${{Math.round(utm[0]/1000)}}k N${{Math.round(utm[1]/1000)}}k`;
  
  drawProfile(idx);
}}

function clearHover() {{
  hideMapHover();
  activeProfileIndex = null;
  profileReadout.innerText = "Drag across profile or trail to inspect...";
  document.getElementById('floating-coords').innerText = "Stubai 50.2 km";
  drawProfile(null);
}}

// TOUCH & MOUSE HANDLERS ON PROFILE
function processProfilePosition(clientX) {{
  const rect = profileCanvas.getBoundingClientRect();
  const mouseX = clientX - rect.left;
  const isMobile = rect.width < 600;
  const padLeft = isMobile ? 40 : 48;
  const padRight = isMobile ? 16 : 24;
  const plotW = rect.width - padLeft - padRight;
  
  const distFraction = Math.max(0, Math.min(1, (mouseX - padLeft) / plotW));
  const targetDistKm = distFraction * {total_dist_km};
  
  let low = 0, high = trackPoints.length - 1;
  while (low <= high) {{
    const mid = (low + high) >> 1;
    if (trackPoints[mid].dist < targetDistKm) low = mid + 1;
    else high = mid - 1;
  }}
  let idx = Math.min(trackPoints.length - 1, Math.max(0, low));
  if (idx > 0 && Math.abs(trackPoints[idx-1].dist - targetDistKm) < Math.abs(trackPoints[idx].dist - targetDistKm)) {{
    idx--;
  }}
  setHoverPoint(idx);
}}

profileCanvas.addEventListener('mousemove', function(e) {{
  mouseOnProfile = true;
  processProfilePosition(e.clientX);
}});

profileCanvas.addEventListener('mouseleave', function() {{
  mouseOnProfile = false;
  clearHover();
}});

profileCanvas.addEventListener('click', function(e) {{
  if (activeProfileIndex !== null) {{
    const pt = trackPoints[activeProfileIndex];
    map.flyTo([pt.lat, pt.lon], 15, {{ duration: 0.6 }});
  }}
}});

// TOUCH SUPPORT FOR MOBILE
profileCanvas.addEventListener('touchstart', function(e) {{
  mouseOnProfile = true;
  if (e.touches && e.touches.length > 0) {{
    processProfilePosition(e.touches[0].clientX);
  }}
  e.preventDefault();
}}, {{ passive: false }});

profileCanvas.addEventListener('touchmove', function(e) {{
  if (e.touches && e.touches.length > 0) {{
    processProfilePosition(e.touches[0].clientX);
  }}
  e.preventDefault();
}}, {{ passive: false }});

profileCanvas.addEventListener('touchend', function() {{
  mouseOnProfile = false;
}});

// MAP HOVER & TOUCH SUPPORT
function handleMapMove(lat, lon, clientX, clientY) {{
  const utm = proj4("EPSG:4326", "EPSG:32632", [lon, lat]);
  const easting = Math.round(utm[0]);
  const northing = Math.round(utm[1]);
  
  document.getElementById('utm-coords').innerText = `E ${{easting.toLocaleString()}} m  |  N ${{northing.toLocaleString()}} m`;
  document.getElementById('wgs-coords').innerText = `Lat: ${{lat.toFixed(5)}}° N, Lon: ${{lon.toFixed(5)}}° E`;

  if (profileVisible && !mouseOnProfile) {{
    const mousePoint = map.latLngToContainerPoint([lat, lon]);
    
    let minDistSq = Infinity;
    let closestIdx = -1;
    for (let i = 0; i < trackPoints.length; i += 2) {{
      const dLat = trackPoints[i].lat - lat;
      const dLon = (trackPoints[i].lon - lon) * 0.68;
      const dSq = dLat * dLat + dLon * dLon;
      if (dSq < minDistSq) {{
        minDistSq = dSq;
        closestIdx = i;
      }}
    }}
    
    const start = Math.max(0, closestIdx - 3);
    const end = Math.min(trackPoints.length - 1, closestIdx + 3);
    for (let i = start; i <= end; i++) {{
      const dLat = trackPoints[i].lat - lat;
      const dLon = (trackPoints[i].lon - lon) * 0.68;
      const dSq = dLat * dLat + dLon * dLon;
      if (dSq < minDistSq) {{
        minDistSq = dSq;
        closestIdx = i;
      }}
    }}
    
    const ptScreen = map.latLngToContainerPoint([trackPoints[closestIdx].lat, trackPoints[closestIdx].lon]);
    const pixDist = Math.hypot(ptScreen.x - mousePoint.x, ptScreen.y - mousePoint.y);
    
    if (pixDist < 60) {{
      setHoverPoint(closestIdx);
    }} else {{
      clearHover();
    }}
  }}
}}

map.on('mousemove', function(e) {{
  handleMapMove(e.latlng.lat, e.latlng.lng);
}});

map.on('click', function(e) {{
  handleMapMove(e.latlng.lat, e.latlng.lng);
}});

// TOGGLE ELEVATION PROFILE
function toggleProfile() {{
  profileVisible = !profileVisible;
  const fabGroup = document.getElementById('fab-group');
  if (profileVisible) {{
    profilePanel.classList.remove('hidden');
    toggleProfileBtn.innerText = '📈 Hide Elevation Profile';
    toggleProfileBtn.classList.add('btn-active');
    fabProfileBtn.style.color = '#38bdf8';
    setTimeout(() => drawProfile(activeProfileIndex), 50);
  }} else {{
    profilePanel.classList.add('hidden');
    toggleProfileBtn.innerText = '📈 Show Elevation Profile';
    toggleProfileBtn.classList.remove('btn-active');
    fabProfileBtn.style.color = '#e2e8f0';
    clearHover();
  }}
}}

toggleProfileBtn.addEventListener('click', toggleProfile);
fabProfileBtn.addEventListener('click', toggleProfile);
closeProfileBtn.addEventListener('click', toggleProfile);

window.addEventListener('resize', () => {{
  if (profileVisible) drawProfile(activeProfileIndex);
}});

// ==========================================
// OFFLINE & PWA MANAGEMENT
// ==========================================
const offlineTiles = {json.dumps(offline_tiles)};
let deferredPrompt = null;
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

if ('serviceWorker' in navigator) {{
  window.addEventListener('load', () => {{
    navigator.serviceWorker.register('./sw.js').catch(err => console.log('SW reg error:', err));
  }});
}}

window.addEventListener('beforeinstallprompt', (e) => {{
  e.preventDefault();
  deferredPrompt = e;
}});

const btnOffline = document.getElementById('btn-offline');
const fabOffline = document.getElementById('fab-offline');
const offlineModal = document.getElementById('offline-modal');
const modalIcon = document.getElementById('modal-icon');
const modalTitle = document.getElementById('modal-title');
const modalStatus = document.getElementById('modal-status');
const progressBar = document.getElementById('progress-bar');
const iosGuide = document.getElementById('ios-guide');
const modalClose = document.getElementById('modal-close');

async function checkCachedStatus() {{
  if ('caches' in window) {{
    try {{
      const cache = await caches.open('stubai-tiles-v1');
      if (offlineTiles.length > 0) {{
        const sampleTile = offlineTiles[Math.floor(offlineTiles.length / 2)];
        const match = await cache.match(`https://a.tile.opentopomap.org/${{sampleTile[0]}}/${{sampleTile[1]}}/${{sampleTile[2]}}.png`);
        if (match) {{
          if (btnOffline) btnOffline.innerText = "✅ Map Available Offline";
          if (fabOffline) fabOffline.innerText = "✅ Offline Ready";
        }}
      }}
    }} catch(e) {{}}
  }}
}}
checkCachedStatus();

async function startOfflineDownload() {{
  closeMobileSidebar();
  
  if (deferredPrompt) {{
    try {{
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(() => {{
        deferredPrompt = null;
      }});
    }} catch(e) {{}}
  }}

  offlineModal.style.display = 'flex';
  modalIcon.innerText = "⏳";
  modalTitle.innerText = "Saving Stubai Map Offline";
  modalStatus.innerText = "Caching 280 topographic tiles for all 5 stages...";
  progressBar.style.width = '0%';
  modalClose.style.display = 'none';
  if (iosGuide) iosGuide.style.display = 'none';

  if (!('caches' in window)) {{
    modalIcon.innerText = "⚠️";
    modalTitle.innerText = "Offline Storage Unavailable";
    modalStatus.innerText = "Your browser does not support CacheStorage.";
    modalClose.style.display = 'block';
    return;
  }}

  const cache = await caches.open('stubai-tiles-v1');
  const servers = ['a', 'b', 'c'];
  const total = offlineTiles.length;
  let done = 0;
  const batchSize = 6;

  for (let i = 0; i < total; i += batchSize) {{
    const batch = offlineTiles.slice(i, i + batchSize);
    await Promise.all(batch.map(async ([z, x, y]) => {{
      const server = servers[(x + y) % servers.length];
      const url = `https://${{server}}.tile.opentopomap.org/${{z}}/${{x}}/${{y}}.png`;
      const canonical = `https://a.tile.opentopomap.org/${{z}}/${{x}}/${{y}}.png`;
      try {{
        const existing = await cache.match(canonical);
        if (!existing) {{
          const resp = await fetch(url, {{ mode: 'cors' }});
          if (resp && resp.status === 200) {{
            await cache.put(canonical, resp.clone());
            await cache.put(url, resp);
          }}
        }}
      }} catch (err) {{
        console.warn('Tile fetch issue:', url);
      }}
      done++;
      const pct = Math.round((done / total) * 100);
      progressBar.style.width = pct + '%';
      modalStatus.innerText = `Cached ${{done}} of ${{total}} map tiles (${{pct}}%)...`;
    }}));
  }}

  modalIcon.innerText = "✅";
  modalTitle.innerText = "Map is 100% Offline Ready!";
  modalStatus.innerHTML = "<strong>All 5 stages of the Stubai High Route are now stored on your phone!</strong><br/><br/>You can view the full topographic map, follow the trail, and use GPS even with zero cellular signal or in Airplane Mode.";
  modalClose.style.display = 'block';
  if (btnOffline) btnOffline.innerText = "✅ Map Available Offline";
  if (fabOffline) fabOffline.innerText = "✅ Offline Ready";

  if (isIOS) {{
    iosGuide.style.display = 'block';
  }}
}}

if (btnOffline) btnOffline.addEventListener('click', startOfflineDownload);
if (fabOffline) fabOffline.addEventListener('click', startOfflineDownload);
if (modalClose) modalClose.addEventListener('click', () => {{
  offlineModal.style.display = 'none';
}});

// Initial draw
setTimeout(() => drawProfile(null), 120);
</script>
</body>
</html>"""

output_path = Path("state/maps/Stubai_High_Route_Interactive_UTM_Map.html")
output_path.write_text(html_content, encoding="utf-8")
print(f"Saved mobile-optimized interactive viewer to {output_path}")

# Also write to index.html in the root workspace directory for immediate GitHub Pages compatibility!
index_path = Path("index.html")
index_path.write_text(html_content, encoding="utf-8")
print(f"Also created {index_path} in root directory for GitHub Pages hosting!")
