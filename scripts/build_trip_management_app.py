# -*- coding: utf-8 -*-
import json
import xml.etree.ElementTree as ET
import pyproj
import numpy as np
import sys
from pathlib import Path

# Add scripts directory to path to import hut_specs
sys.path.append(str(Path(__file__).resolve().parent))
from hut_specs import HUTS

# Load precomputed offline tiles
offline_tiles_path = Path("config/offline_tiles.json")
if offline_tiles_path.exists():
    offline_tiles = json.loads(offline_tiles_path.read_text(encoding="utf-8"))
else:
    offline_tiles = []

# Load gear items from config
gear_items_path = Path("config/gear_items.json")
if gear_items_path.exists():
    gear_items = json.loads(gear_items_path.read_text(encoding="utf-8"))
else:
    gear_items = []

transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
to_wgs = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

# Parse GPX
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
html_huts = []
for h in HUTS:
    is_overnight = h.get("overnight", False)
    badge = f"Night {h['night']}" if is_overnight else "Daytime Alm"
    html_huts.append({
        "name": h["name"],
        "lat": h["lat"],
        "lon": h["lon"],
        "ele": h["ele"],
        "overnight": is_overnight,
        "night": h.get("night", None),
        "stage": h.get("stage", 1),
        "badge": badge,
        "desc": h.get("desc", ""),
        "radius_meters": 220 if is_overnight else 90
    })

print(f"Loaded {len(track_points)} track points, {len(html_huts)} huts, {len(gear_items)} gear items.")

# Assemble the complete Web Application HTML
html_content = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"/>
<meta name="theme-color" content="#0f172a"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
<meta name="apple-mobile-web-app-title" content="שטובאי 2027"/>
<link rel="manifest" href="manifest.webmanifest"/>
<link rel="apple-touch-icon" href="apple-touch-icon.png"/>
<title>שטובאי 2027 — אפליקציית ניהול מסע ומפה אלפינית</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.0/proj4.js"></script>
<style>
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  html, body {{
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: #090d16;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Heebo", "Assistant", Helvetica, Arial, sans-serif;
    color: #f1f5f9;
  }}

  #app-root {{
    display: flex;
    flex-direction: column;
    width: 100vw;
    height: 100vh;
    position: relative;
    overflow: hidden;
  }}

  /* VIEWS CONTAINER */
  #views-container {{
    flex: 1;
    position: relative;
    width: 100%;
    height: calc(100% - 60px);
    overflow: hidden;
  }}

  .app-view {{
    display: none;
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    background: #090d16;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }}
  .app-view.active {{
    display: block;
  }}

  /* MAP VIEW HAS OVERFLOW HIDDEN FOR LEAFLET */
  #view-map {{
    overflow: hidden;
  }}

  /* TOP ACTION BAR ON MAP */
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
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid #334155;
    color: #f1f5f9;
    padding: 7px 14px;
    border-radius: 20px;
    font-size: 11.5px;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35);
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
  }}
  .floating-pill:hover, .floating-pill:active {{ background: #1e293b; border-color: #38bdf8; }}

  #floating-coords {{
    font-family: monospace;
    font-size: 10.5px;
    color: #38bdf8;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid #334155;
    padding: 6px 12px;
    border-radius: 16px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 52%;
    direction: ltr;
  }}

  #gps-btn {{
    pointer-events: auto;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid #334155;
    color: #38bdf8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 17px;
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

  /* LEAFLET CONTROLS */
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

  /* MAP CONTAINER */
  #map {{
    width: 100%;
    height: 100%;
    background: #090d16;
  }}

  /* FAB GROUP (ON MAP) */
  #fab-group {{
    position: absolute;
    bottom: 235px;
    left: 14px;
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
    z-index: 1200;
    box-shadow: 0 -4px 15px rgba(0,0,0,0.5);
    transition: transform 0.25s ease;
  }}
  #profile-panel.hidden {{
    transform: translateY(100%);
  }}
  #profile-panel.hidden ~ #fab-group {{
    bottom: 20px;
  }}

  #profile-header {{
    height: 34px;
    background: #0f172a;
    border-bottom: 1px solid #1e293b;
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
    direction: ltr;
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

  /* BOTTOM NAVIGATION BAR */
  #bottom-nav {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    background: rgba(15, 23, 42, 0.98);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-top: 1px solid #334155;
    display: flex;
    align-items: center;
    justify-content: space-around;
    z-index: 2500;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.4);
  }}
  .nav-tab {{
    flex: 1;
    height: 100%;
    background: transparent;
    border: none;
    color: #94a3b8;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    cursor: pointer;
    transition: color 0.15s ease;
    user-select: none;
  }}
  .nav-tab.active {{
    color: #38bdf8;
    font-weight: bold;
  }}
  .nav-tab .nav-icon {{
    font-size: 19px;
  }}
  .nav-tab .nav-label {{
    font-size: 11px;
    letter-spacing: -0.2px;
  }}

  /* SLIDING SIDEBAR DRAWER (OVERLAY MENU) */
  #sidebar {{
    position: fixed;
    top: 0;
    bottom: 0;
    right: 0;
    width: 320px;
    max-width: 85vw;
    background: #0f172a;
    color: #f8fafc;
    display: flex;
    flex-direction: column;
    border-left: 1px solid #334155;
    z-index: 3000;
    box-shadow: -4px 0 20px rgba(0,0,0,0.6);
    transform: translateX(100%);
    transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  #sidebar.open {{
    transform: translateX(0);
  }}
  #drawer-backdrop {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.65);
    z-index: 2999;
  }}
  #drawer-backdrop.open {{
    display: block;
  }}

  #sidebar-header {{
    padding: 16px;
    border-bottom: 1px solid #334155;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #0a0f1d;
  }}
  #sidebar-header h1 {{ margin: 0; font-size: 16px; font-weight: 700; color: #38bdf8; }}
  #sidebar-header p {{ margin: 3px 0 0; font-size: 11px; color: #94a3b8; }}
  #close-sidebar {{
    background: none; border: none; color: #94a3b8; font-size: 20px; cursor: pointer; padding: 4px 8px; border-radius: 4px;
  }}
  #close-sidebar:hover {{ color: white; background: #334155; }}

  .drawer-section {{
    padding: 14px 16px;
    border-bottom: 1px solid #1e293b;
  }}
  .drawer-section-title {{
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .drawer-link {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    color: #f1f5f9;
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
    margin-bottom: 4px;
  }}
  .drawer-link:hover, .drawer-link:active {{
    background: #1e293b;
    color: #38bdf8;
  }}
  .drawer-link .link-icon {{ font-size: 17px; }}

  /* GENERIC BUTTONS */
  .btn {{
    background: #0284c7;
    color: white;
    border: none;
    padding: 9px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    margin-bottom: 6px;
    transition: all 0.15s;
  }}
  .btn:active {{ background: #0369a1; transform: scale(0.98); }}
  .btn-outline {{
    background: transparent;
    border: 1px solid #334155;
    color: #cbd5e1;
  }}
  .btn-outline:hover, .btn-outline:active {{ background: #1e293b; border-color: #38bdf8; color: #f1f5f9; }}

  /* CONTENT VIEWS STYLING (SCHEDULE, GEAR, HUTS) */
  .content-container {{
    max-width: 680px;
    margin: 0 auto;
    padding: 16px 16px 85px 16px;
  }}
  .view-hero {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }}
  .view-hero h2 {{ margin: 0 0 6px 0; font-size: 18px; color: #38bdf8; }}
  .view-hero p {{ margin: 0; font-size: 12px; color: #cbd5e1; line-height: 1.5; }}

  /* SCHEDULE TIMELINE */
  .timeline-card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 12px;
    position: relative;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  }}
  .timeline-card.trek-day {{
    border-right: 4px solid #38bdf8;
  }}
  .timeline-card.travel-day {{
    border-right: 4px solid #a855f7;
  }}
  .timeline-card.rest-day {{
    border-right: 4px solid #10b981;
  }}
  .card-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }}
  .card-date {{
    font-size: 12px;
    font-weight: 700;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    padding: 2px 8px;
    border-radius: 12px;
  }}
  .card-tag {{
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    background: #1e293b;
    color: #94a3b8;
  }}
  .card-title {{
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 6px;
  }}
  .card-metrics {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0;
    font-size: 11.5px;
  }}
  .metric-badge {{
    background: #1e293b;
    border: 1px solid #334155;
    padding: 3px 8px;
    border-radius: 6px;
    color: #cbd5e1;
  }}
  .metric-badge strong {{ color: #38bdf8; }}
  .card-desc {{
    font-size: 12.5px;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 10px;
  }}
  .card-btn-map {{
    background: #1e293b;
    border: 1px solid #334155;
    color: #38bdf8;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: all 0.15s;
  }}
  .card-btn-map:active {{ background: #0284c7; color: white; }}

  /* GEAR CHECKLIST */
  .gear-summary {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 14px;
  }}
  .progress-wrap {{
    margin-top: 8px;
    background: #1e293b;
    border-radius: 8px;
    height: 10px;
    overflow: hidden;
  }}
  .progress-fill {{
    background: linear-gradient(90deg, #10b981, #38bdf8);
    height: 100%;
    width: 0%;
    transition: width 0.25s ease;
  }}
  .gear-filters {{
    display: flex;
    gap: 6px;
    margin-bottom: 14px;
  }}
  .filter-pill {{
    background: #1e293b;
    border: 1px solid #334155;
    color: #94a3b8;
    padding: 5px 12px;
    border-radius: 16px;
    font-size: 11px;
    cursor: pointer;
  }}
  .filter-pill.active {{
    background: #0284c7;
    color: white;
    border-color: #38bdf8;
    font-weight: 600;
  }}

  .gear-group-title {{
    font-size: 13px;
    font-weight: 700;
    color: #38bdf8;
    margin: 16px 0 8px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #1e293b;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .gear-item-row {{
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    transition: background 0.12s;
  }}
  .gear-item-row:active {{ background: #1e293b; }}
  .gear-checkbox {{
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 2px solid #64748b;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    color: white;
    flex-shrink: 0;
    transition: all 0.15s;
  }}
  .gear-item-row.checked .gear-checkbox {{
    background: #10b981;
    border-color: #10b981;
  }}
  .gear-text {{
    font-size: 13px;
    color: #f1f5f9;
    flex: 1;
    transition: all 0.15s;
  }}
  .gear-item-row.checked .gear-text {{
    text-decoration: line-through;
    color: #64748b;
  }}

  /* HUTS DIRECTORY */
  .hut-detail-card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.3);
  }}
  .hut-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 10px;
  }}
  .hut-name {{
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
  }}
  .hut-badge-night {{
    background: #1d4ed8;
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 12px;
  }}
  .hut-key-stats {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    background: #1e293b;
    border-radius: 8px;
    padding: 10px;
    margin-bottom: 12px;
    font-size: 12px;
  }}
  .hut-stat-label {{ color: #94a3b8; font-size: 10.5px; }}
  .hut-stat-val {{ color: #f1f5f9; font-weight: 600; }}
  .hut-stat-val.price {{ color: #38bdf8; font-weight: 700; font-size: 13px; }}
  .hut-desc {{
    font-size: 12.5px;
    color: #cbd5e1;
    line-height: 1.5;
    margin-bottom: 12px;
  }}

  /* OFFLINE MODAL */
  #offline-modal {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.8);
    z-index: 9999;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  .modal-box {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 22px;
    max-width: 360px;
    width: 100%;
    box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    text-align: center;
  }}

  /* BADGES IN MAP */
  .badge-tag {{ display: inline-block; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 4px; margin-left: 6px; vertical-align: middle; }}
  .badge-night {{ background: #1d4ed8; color: white; }}
  .grid-label {{ background: rgba(15, 23, 42, 0.85); color: #38bdf8; font-family: monospace; font-size: 10px; font-weight: bold; padding: 2px 4px; border-radius: 3px; border: 1px solid #0284c7; white-space: nowrap; }}

  /* MOBILE RESPONSIVE ADJUSTMENTS */
  @media (max-width: 768px) {{
    #profile-panel {{ height: 175px; }}
    #fab-group {{ bottom: 190px; }}
    #profile-panel.hidden ~ #fab-group {{ bottom: 20px; }}
  }}
</style>
</head>
<body>
<div id="app-root">
  
  <!-- VIEWS CONTAINER -->
  <div id="views-container">
    
    <!-- ==========================================
         VIEW 1: INTERACTIVE TOPOGRAPHIC MAP
         ========================================== -->
    <div id="view-map" class="app-view active">
      <div id="map"></div>

      <!-- FLOATING TOP BAR -->
      <div id="floating-top-bar">
        <div class="floating-pill" id="menu-trigger">
          <span>☰</span> <strong>תפריט</strong>
        </div>
        <div id="floating-coords">Stubai 50.2 km</div>
        <div id="gps-btn" title="Find My Location">🎯</div>
      </div>

      <!-- FLOATING ACTION BUTTONS (ON MAP) -->
      <div id="fab-group">
        <div class="fab" id="fab-profile">📈 פרופיל</div>
        <div class="fab" id="fab-grid">🧭 רשת UTM</div>
      </div>

      <!-- ELEVATION PROFILE DOCK -->
      <div id="profile-panel">
        <div id="profile-header">
          <div class="profile-title">
            <span>📈</span>
            <span>פרופיל גבהים</span>
            <span class="profile-meta">(50.2 ק"מ • 3,180+ מ')</span>
          </div>
          <div id="profile-readout">גרור אצבע על הפרופיל או המפה לבדיקה...</div>
          <button id="close-profile" title="סגור פרופיל">✕</button>
        </div>
        <div id="profile-chart-wrap">
          <canvas id="profile-canvas"></canvas>
        </div>
      </div>
    </div>

    <!-- ==========================================
         VIEW 2: SCHEDULE / ITINERARY
         ========================================== -->
    <div id="view-schedule" class="app-view">
      <div class="content-container">
        <div class="view-hero">
          <h2>📅 לוח זמנים ומסלול הטרק</h2>
          <p>מסע של 5 ימי הליכה אלפיניים בעמק שטובאי, טירול, אוסטריה (05.09.2027 – 13.09.2027).</p>
        </div>

        <!-- 05.09.2027 -->
        <div class="timeline-card travel-day">
          <div class="card-top">
            <span class="card-date">05.09.2027 • יום ראשון</span>
            <span class="card-tag">טיסות והגעה</span>
          </div>
          <div class="card-title">✈️ טיסה למינכן ונסיעה לשטובאי</div>
          <div class="card-desc">טיסת אל על למינכן, איסוף רכב או נסיעה ברכבת דרך אינסברוק לעמק שטובאי (Stubaital). התארגנות במלון/פנסיון בעמק, בדיקת ציוד אחרונה וארוחת ערב צוותית.</div>
        </div>

        <!-- 06.09.2027 -->
        <div class="timeline-card trek-day">
          <div class="card-top">
            <span class="card-date">06.09.2027 • יום שני</span>
            <span class="card-tag">יום הליכה 1</span>
          </div>
          <div class="card-title">⛰️ תחילת מסלול: Oberissalm ➔ Franz-Senn-Hütte</div>
          <div class="card-metrics">
            <span class="metric-badge">מרחק: <strong>10.3 ק"מ</strong></span>
            <span class="metric-badge">עלייה: <strong>600+ מ'</strong></span>
            <span class="metric-badge">ירידה: <strong>190- מ'</strong></span>
            <span class="metric-badge">זמן משוער: <strong>~3.5 שעות</strong></span>
          </div>
          <div class="card-desc">כניסה אל עמק Alpeiner Tal לאורך נחל שוצף. יום הליכה מתון ומושלם לחימום והתאקלמות. לינה בבקתת פרנץ סן (2,147 מ').</div>
          <button class="card-btn-map" onclick="jumpToDay(1)">📍 הצג יום 1 במפה</button>
        </div>

        <!-- 07.09.2027 -->
        <div class="timeline-card trek-day">
          <div class="card-top">
            <span class="card-date">07.09.2027 • יום שלישי</span>
            <span class="card-tag">יום הליכה 2</span>
          </div>
          <div class="card-title">⛰️ יום 2: Franz-Senn-Hütte ➔ Neue Regensburger Hütte</div>
          <div class="card-metrics">
            <span class="metric-badge">מרחק: <strong>9.3 ק"מ</strong></span>
            <span class="metric-badge">עלייה: <strong>880+ מ'</strong></span>
            <span class="metric-badge">ירידה: <strong>740- מ'</strong></span>
            <span class="metric-badge">זמן משוער: <strong>~4.5 שעות</strong></span>
          </div>
          <div class="card-desc">טיפוס אל מעבר ההרים Schrimmennieder (2,714 מ') עם נוף פנורמי אדיר לפסגת ה-Habicht. ירידה אל בקתת נויה רגנסבורגר (2,286 מ') התלויה מול מפל עוצמתי.</div>
          <button class="card-btn-map" onclick="jumpToDay(2)">📍 הצג יום 2 במפה</button>
        </div>

        <!-- 08.09.2027 -->
        <div class="timeline-card trek-day">
          <div class="card-top">
            <span class="card-date">08.09.2027 • יום רביעי</span>
            <span class="card-tag">יום הליכה 3</span>
          </div>
          <div class="card-title">⛰️ יום 3: Neue Regensburger Hütte ➔ Dresdner Hütte</div>
          <div class="card-metrics">
            <span class="metric-badge">מרחק: <strong>12.5 ק"מ</strong></span>
            <span class="metric-badge">עלייה: <strong>950+ מ'</strong></span>
            <span class="metric-badge">ירידה: <strong>930- מ'</strong></span>
            <span class="metric-badge">זמן משוער: <strong>~6.5 שעות</strong></span>
          </div>
          <div class="card-desc">היום הארוך והמאתגר של הטרק: מעבר ליד אגם Falbesoner See הטורקיזי, עלייה אל Grawagrubennieder (2,881 מ') עם מעברי כבלים קצרים וירידה לבקתת דרזדנר (2,308 מ').</div>
          <button class="card-btn-map" onclick="jumpToDay(3)">📍 הצג יום 3 במפה</button>
        </div>

        <!-- 09.09.2027 -->
        <div class="timeline-card trek-day">
          <div class="card-top">
            <span class="card-date">09.09.2027 • יום חמישי</span>
            <span class="card-tag">יום הליכה 4</span>
          </div>
          <div class="card-title">⛰️ יום 4: Dresdner Hütte ➔ Sulzenauhütte</div>
          <div class="card-metrics">
            <span class="metric-badge">מרחק: <strong>6.0 ק"מ</strong></span>
            <span class="metric-badge">עלייה: <strong>480+ מ'</strong></span>
            <span class="metric-badge">ירידה: <strong>600- מ'</strong></span>
            <span class="metric-badge">זמן משוער: <strong>~3.5 שעות</strong></span>
          </div>
          <div class="card-desc">עלייה אל אוכף Peiljoch (2,676 מ') המעוטר במאות רוג'ומים, תצפית עוצרת נשימה על קרחון זולצנאו והאגם הקרחוני, וירידה לבקתת זולצנאו (2,191 מ').</div>
          <button class="card-btn-map" onclick="jumpToDay(4)">📍 הצג יום 4 במפה</button>
        </div>

        <!-- 10.09.2027 - 11.09.2027 -->
        <div class="timeline-card trek-day">
          <div class="card-top">
            <span class="card-date">10.09–11.09.2027 • שישי–שבת</span>
            <span class="card-tag">סוף מסלול (יום 5)</span>
          </div>
          <div class="card-title">⛰️ יום 5: Sulzenauhütte ➔ ירידה לעמק Ranalt</div>
          <div class="card-metrics">
            <span class="metric-badge">מרחק: <strong>12.2 ק"מ</strong></span>
            <span class="metric-badge">עלייה: <strong>550+ מ'</strong></span>
            <span class="metric-badge">ירידה: <strong>1,480- מ'</strong></span>
            <span class="metric-badge">זמן משוער: <strong>~5 שעות</strong></span>
          </div>
          <div class="card-desc">מעבר Niederl או טיפוס לפסגת Mairspitze (3,056 מ'), עצירה בבקתת נירנברגר (Nürnberger Hütte) וירידה פסטורלית לאורך מפלי Bsuchalm עד נקודת הסיום בעמק Ranalt.</div>
          <button class="card-btn-map" onclick="jumpToDay(5)">📍 הצג יום 5 במפה</button>
        </div>

        <!-- 12.09.2027 -->
        <div class="timeline-card rest-day">
          <div class="card-top">
            <span class="card-date">12.09.2027 • שבת</span>
            <span class="card-tag">שבת מנוחה</span>
          </div>
          <div class="card-title">🌲 שבת בשטובאי</div>
          <div class="card-desc">יום מנוחה, שבת שלווה בעמק שטובאי, ארוחות מקומיות מפנקות, ספא והתאוששות מהמסע המדהים.</div>
        </div>

        <!-- 13.09.2027 -->
        <div class="timeline-card travel-day">
          <div class="card-top">
            <span class="card-date">13.09.2027 • יום ראשון</span>
            <span class="card-tag">טיסה חזרה</span>
          </div>
          <div class="card-title">✈️ טיסה חזרה ממינכן לתל אביב</div>
          <div class="card-desc">נסיעה משטובאי לנמל התעופה של מינכן וטיסת אל על חזרה הביתה לישראל.</div>
        </div>
      </div>
    </div>

    <!-- ==========================================
         VIEW 3: GEAR CHECKLIST
         ========================================== -->
    <div id="view-gear" class="app-view">
      <div class="content-container">
        <div class="view-hero">
          <h2>🎒 רשימת ציוד אינטראקטיבית</h2>
          <p>כל הפריטים מהאקסל. סמנו ב-V מה שנארז. הסימונים נשמרים אוטומטית בטלפון גם באופליין!</p>
        </div>

        <!-- PROGRESS & SUMMARY -->
        <div class="gear-summary">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 13px; font-weight: 700;" id="gear-counter">0 / 0 פריטים נארזו</span>
            <span style="font-size: 13px; font-weight: 700; color: #38bdf8;" id="gear-percent">0%</span>
          </div>
          <div class="progress-wrap">
            <div class="progress-fill" id="gear-progress-bar"></div>
          </div>
        </div>

        <!-- FILTERS & ACTIONS -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="gear-filters">
            <span class="filter-pill active" onclick="setGearFilter('all')">הכל</span>
            <span class="filter-pill" onclick="setGearFilter('unpacked')">טרם נארז</span>
            <span class="filter-pill" onclick="setGearFilter('packed')">נארז</span>
          </div>
          <button class="btn btn-outline" style="width: auto; padding: 4px 10px; font-size: 11px; margin: 0;" onclick="resetGearChecklist()">🔄 איפוס</button>
        </div>

        <!-- ITEMS CONTAINER (POPULATED VIA JS) -->
        <div id="gear-items-list"></div>

        <!-- ADD CUSTOM ITEM -->
        <div style="margin-top: 20px; background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 12px; display: flex; gap: 8px;">
          <input type="text" id="new-item-input" placeholder="הוסף פריט אישי משלך..." style="flex: 1; background: #1e293b; border: 1px solid #334155; color: white; padding: 8px 12px; border-radius: 6px; font-size: 13px;">
          <button class="btn" style="width: auto; margin: 0; padding: 8px 16px;" onclick="addCustomGearItem()">➕ הוסף</button>
        </div>
      </div>
    </div>

    <!-- ==========================================
         VIEW 4: HUTS DIRECTORY
         ========================================== -->
    <div id="view-huts" class="app-view">
      <div class="content-container">
        <div class="view-hero">
          <h2>🏡 בקתות הלינה בטרק</h2>
          <p>4 בקתות אלפיניות אותנטיות. כל המחירים כוללים חצי פנסיון (HB) כפי שהוגדרו באקסל.</p>
        </div>

        <!-- FRANZ-SENN-HÜTTE -->
        <div class="hut-detail-card">
          <div class="hut-header">
            <div>
              <div class="hut-name">Franz-Senn-Hütte</div>
              <div style="color: #94a3b8; font-size: 12px; margin-top: 2px;">בקתת פרנץ סן • Alpeiner Tal</div>
            </div>
            <span class="hut-badge-night">לילה 1</span>
          </div>
          <div class="hut-key-stats">
            <div>
              <div class="hut-stat-label">תאריך צ'ק-אין:</div>
              <div class="hut-stat-val">06.09.2027</div>
            </div>
            <div>
              <div class="hut-stat-label">מחיר משוער (כולל HB):</div>
              <div class="hut-stat-val price">120 €</div>
            </div>
            <div>
              <div class="hut-stat-label">גובה מעל פני הים:</div>
              <div class="hut-stat-val">2,147 מטר</div>
            </div>
            <div>
              <div class="hut-stat-label">סיום יום:</div>
              <div class="hut-stat-val">יום הליכה 1 (10.3 ק"מ)</div>
            </div>
          </div>
          <div class="hut-desc">
            הבקתה הגדולה והמפורסמת ביותר ברכס. כוללת חדר ייבוש נעליים ובגדים עם חימום, מקלחות חמות (אסימונים בתשלום סמלי), שק שינה דק (Liner) חובה, וויפיי זמין בלובי, וארוחת ערב משותפת ב-18:30.
          </div>
          <button class="card-btn-map" onclick="jumpToHut('Franz-Senn-Hütte')">📍 הצג בקתה במפה</button>
        </div>

        <!-- NEUE REGENSBURGER HÜTTE -->
        <div class="hut-detail-card">
          <div class="hut-header">
            <div>
              <div class="hut-name">Neue Regensburger Hütte</div>
              <div style="color: #94a3b8; font-size: 12px; margin-top: 2px;">בקתת נויה רגנסבורגר</div>
            </div>
            <span class="hut-badge-night">לילה 2</span>
          </div>
          <div class="hut-key-stats">
            <div>
              <div class="hut-stat-label">תאריך צ'ק-אין:</div>
              <div class="hut-stat-val">07.09.2027</div>
            </div>
            <div>
              <div class="hut-stat-label">מחיר משוער (כולל HB):</div>
              <div class="hut-stat-val price">120 €</div>
            </div>
            <div>
              <div class="hut-stat-label">גובה מעל פני הים:</div>
              <div class="hut-stat-val">2,286 מטר</div>
            </div>
            <div>
              <div class="hut-stat-label">סיום יום:</div>
              <div class="hut-stat-val">יום הליכה 2 (9.3 ק"מ)</div>
            </div>
          </div>
          <div class="hut-desc">
            מיקום דרמטי ועוצר נשימה בראש צוק, המשקיף ישירות על מפל מים גועש. מרפסת פנורמית מושלמת לבירה של סוף יום, ארוחת ערב בת 3 מנות ברמה גבוהה מאוד, מקלחות חמות ונעלי בקתה מסופקות בכניסה.
          </div>
          <button class="card-btn-map" onclick="jumpToHut('Neue Regensburger Hütte')">📍 הצג בקתה במפה</button>
        </div>

        <!-- DRESDNER HÜTTE -->
        <div class="hut-detail-card">
          <div class="hut-header">
            <div>
              <div class="hut-name">Dresdner Hütte</div>
              <div style="color: #94a3b8; font-size: 12px; margin-top: 2px;">בקתת דרזדנר • קרחון שטובאי</div>
            </div>
            <span class="hut-badge-night">לילה 3</span>
          </div>
          <div class="hut-key-stats">
            <div>
              <div class="hut-stat-label">תאריך צ'ק-אין:</div>
              <div class="hut-stat-val">08.09.2027</div>
            </div>
            <div>
              <div class="hut-stat-label">מחיר משוער (כולל HB):</div>
              <div class="hut-stat-val price">80 €</div>
            </div>
            <div>
              <div class="hut-stat-label">גובה מעל פני הים:</div>
              <div class="hut-stat-val">2,308 מטר</div>
            </div>
            <div>
              <div class="hut-stat-label">סיום יום:</div>
              <div class="hut-stat-val">יום הליכה 3 (12.5 ק"מ)</div>
            </div>
          </div>
          <div class="hut-desc">
            בקתה מודרנית ורחבת ידיים הממוקמת בסמוך לתחנת הרכבל המרכזית של קרחון שטובאי. מקלחות חמות מצוינות, חיבור אינטרנט יציב, אפשרות נוחה לתשלום בכרטיס אשראי, וסאונה מפנקת (בתוספת תשלום סמלית).
          </div>
          <button class="card-btn-map" onclick="jumpToHut('Dresdner Hütte')">📍 הצג בקתה במפה</button>
        </div>

        <!-- SULZENAUHÜTTE -->
        <div class="hut-detail-card">
          <div class="hut-header">
            <div>
              <div class="hut-name">Sulzenauhütte</div>
              <div style="color: #94a3b8; font-size: 12px; margin-top: 2px;">בקתת זולצנאו • ליד האגם הקרחוני</div>
            </div>
            <span class="hut-badge-night">לילה 4</span>
          </div>
          <div class="hut-key-stats">
            <div>
              <div class="hut-stat-label">תאריך צ'ק-אין:</div>
              <div class="hut-stat-val">09.09.2027</div>
            </div>
            <div>
              <div class="hut-stat-label">מחיר משוער (כולל HB):</div>
              <div class="hut-stat-val price">100 €</div>
            </div>
            <div>
              <div class="hut-stat-label">גובה מעל פני הים:</div>
              <div class="hut-stat-val">2,191 מטר</div>
            </div>
            <div>
              <div class="hut-stat-label">סיום יום:</div>
              <div class="hut-stat-val">יום הליכה 4 (6.0 ק"מ)</div>
            </div>
          </div>
          <div class="hut-desc">
            בקתה אלפינית ציורית עם אווירה מסורתית חמה במיוחד. מפורסמת ברחבי האלפים בזכות קינוח הקייזרשמארן (Kaiserschmarrn) הטרי שלהם. שק שינה דק חובה, מומלץ להחזיק מזומן באירו לתשלום.
          </div>
          <button class="card-btn-map" onclick="jumpToHut('Sulzenauhütte')">📍 הצג בקתה במפה</button>
        </div>

        <!-- ETIOUETTE / RULES -->
        <div style="background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 14px;">
          <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;">📌 4 כללי ברזל ללינה בבקתות:</div>
          <ul style="margin: 0; padding-right: 20px; font-size: 12px; color: #cbd5e1; line-height: 1.6;">
            <li><strong>נעלי בית חובה (Hüttenschuhe):</strong> מיד בכניסה לבקתה מורידים נעלי הליכה ועוברים לכפכפים.</li>
            <li><strong>שק שינה דק (Liner):</strong> חובה לישון עם סדין/ליינר משלכם (הבקתה מספקת רק כריות ושמיכות צמר).</li>
            <li><strong>מזומן באירו:</strong> תמיד החזיקו מספיק מזומן ללינה ולאקסטרות למקרה שאין קליטה לסליקה.</li>
            <li><strong>שקט לילי (Hüttenruhe):</strong> החל מ-22:00 שמירה מוחלטת על שקט בכל שטח הבקתה.</li>
          </ul>
        </div>
      </div>
    </div>

  </div><!-- #views-container -->

  <!-- ==========================================
       BOTTOM NAVIGATION BAR
       ========================================== -->
  <nav id="bottom-nav">
    <button class="nav-tab active" data-view="view-map" onclick="switchView('view-map')">
      <span class="nav-icon">🗺️</span>
      <span class="nav-label">מפה</span>
    </button>
    <button class="nav-tab" data-view="view-schedule" onclick="switchView('view-schedule')">
      <span class="nav-icon">📅</span>
      <span class="nav-label">לו"ז</span>
    </button>
    <button class="nav-tab" data-view="view-gear" onclick="switchView('view-gear')">
      <span class="nav-icon">🎒</span>
      <span class="nav-label">ציוד</span>
    </button>
    <button class="nav-tab" data-view="view-huts" onclick="switchView('view-huts')">
      <span class="nav-icon">🏡</span>
      <span class="nav-label">בקתות</span>
    </button>
  </nav>

  <!-- ==========================================
       DRAWER / SIDEBAR (MAIN FOLDING MENU)
       ========================================== -->
  <div id="drawer-backdrop" onclick="closeSidebar()"></div>
  <div id="sidebar">
    <div id="sidebar-header">
      <div>
        <h1>שטובאי 2027</h1>
        <p>ניהול מסע ומפה טופוגרפית</p>
      </div>
      <button id="close-sidebar" onclick="closeSidebar()">✕</button>
    </div>

    <!-- QUICK SECTION LINKS -->
    <div class="drawer-section">
      <div class="drawer-section-title">קטגוריות ראשיות</div>
      <div class="drawer-link" onclick="switchView('view-map'); closeSidebar();">
        <span class="link-icon">🗺️</span>
        <span>מפה ופרופיל גבהים</span>
      </div>
      <div class="drawer-link" onclick="switchView('view-schedule'); closeSidebar();">
        <span class="link-icon">📅</span>
        <span>לוח זמנים ומסלול הטרק</span>
      </div>
      <div class="drawer-link" onclick="switchView('view-gear'); closeSidebar();">
        <span class="link-icon">🎒</span>
        <span>רשימת ציוד אינטראקטיבית</span>
      </div>
      <div class="drawer-link" onclick="switchView('view-huts'); closeSidebar();">
        <span class="link-icon">🏡</span>
        <span>בקתות ולינה</span>
      </div>
    </div>

    <!-- OFFLINE & DOWNLOADS -->
    <div class="drawer-section">
      <div class="drawer-section-title">אופליין והורדות</div>
      <button class="btn" id="btn-offline" onclick="startOfflineDownload()" style="background: #0284c7; border: 1px solid #38bdf8; font-weight: bold; color: white;">📲 שמירה לאופליין (PWA)</button>
      <a class="btn btn-outline" href="Stubai_High_Route_Complete_Map_Book_Final_Atlas.pdf" target="_blank">📥 אטלס מפות מלא (PDF)</a>
      <a class="btn btn-outline" href="Stubai_High_Route_Overview_UTM_v3.pdf" target="_blank">🗺️ פוסטר סקירה ראשי (PDF)</a>
    </div>

    <!-- COORDINATES & HUTS JUMP -->
    <div class="drawer-section" style="flex: 1; overflow-y: auto;">
      <div class="drawer-section-title">קואורדינטות UTM 32N</div>
      <div id="utm-coords" style="font-family: monospace; font-size: 11px; color: #38bdf8; margin-bottom: 12px; direction: ltr;">Move cursor or tap map...</div>
      
      <div class="drawer-section-title">בקתות ונקודות ציון</div>
      <div id="wp-list"></div>
    </div>
  </div>

  <!-- OFFLINE PROGRESS MODAL -->
  <div id="offline-modal">
    <div class="modal-box">
      <div style="font-size: 34px; margin-bottom: 8px;" id="modal-icon">📲</div>
      <div style="font-size: 16px; font-weight: bold; margin-bottom: 6px;" id="modal-title">שומר מפה לאופליין</div>
      <div style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;" id="modal-status">מוריד 280 אריחי מפה טופוגרפיים לכל 5 הימים...</div>
      
      <div style="background: #1e293b; border-radius: 8px; height: 10px; overflow: hidden; margin-bottom: 14px; border: 1px solid #334155;">
        <div id="progress-bar" style="background: #38bdf8; width: 0%; height: 100%; transition: width 0.15s ease;"></div>
      </div>

      <div id="ios-guide" style="display: none; background: #1e293b; border: 1px solid #38bdf8; border-radius: 10px; padding: 12px; margin-bottom: 14px; text-align: right; font-size: 12px; line-height: 1.5; color: #cbd5e1;">
        <strong style="color: #38bdf8;">📲 להוספת סמל האפליקציה למסך הבית:</strong><br/>
        1. לחצו על כפתור <strong>השיתוף (Share ⎙)</strong> בתחתית הספארי.<br/>
        2. גללו מטה ובחרו <strong>"הוסף למסך הבית" (➕)</strong>.<br/>
        3. לחצו על <strong>"הוסף" (Add)</strong> בפינה העליונה.
      </div>

      <button class="btn btn-outline" id="modal-close" style="width: 100%; display: none; margin-top: 10px;" onclick="closeOfflineModal()">הבנתי / סגור</button>
    </div>
  </div>

</div><!-- #app-root -->

<script>
// ==========================================
// CORE DATA INGESTION
// ==========================================
proj4.defs("EPSG:32632", "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs");

const map = L.map('map', {{
  center: [47.05, 11.18],
  zoom: 13,
  maxZoom: 17,
  minZoom: 11,
  zoomControl: false
}});

L.control.zoom({{ position: 'topright' }}).addTo(map);

const openTopoMap = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 17,
  attribution: '&copy; OpenStreetMap, SRTM | OpenTopoMap'
}}).addTo(map);

const rawTrack = {json.dumps(track_points)};
const trackPoints = rawTrack.map(p => ({{ lat: p[0], lon: p[1], ele: p[2], dist: p[3] }}));
const trackCoords = trackPoints.map(p => [p.lat, p.lon]);

// Underlay and main crimson trail
L.polyline(trackCoords, {{ color: '#ffffff', weight: 3.8, opacity: 0.85, lineCap: 'round', lineJoin: 'round' }}).addTo(map);
const trackPolyline = L.polyline(trackCoords, {{ color: '#dc2626', weight: 2.0, opacity: 1.0, lineCap: 'round', lineJoin: 'round' }}).addTo(map);
map.fitBounds(trackPolyline.getBounds(), {{ padding: [25, 25] }});

// 1 km UTM Grid Layer
const gridGeoJSON = {json.dumps(grid_geojson)};
let gridLayer = L.geoJSON(gridGeoJSON, {{
  style: function(f) {{ return {{ color: '#0284c7', weight: 0.7, opacity: 0.35, dashArray: '4, 4' }}; }}
}}).addTo(map);

// HUTS & WAYPOINTS DATA
const hutsData = {json.dumps(html_huts)};
const hutMarkerItems = [];

function getHutRadius(zoom, isOvernight) {{
  if (!isOvernight) return 0;
  if (zoom >= 16) return 18;
  if (zoom >= 15) return 16;
  if (zoom >= 14) return 14;
  if (zoom >= 13) return 12;
  return 10;
}}

const wpList = document.getElementById('wp-list');
hutsData.forEach(h => {{
  if (h.overnight) {{
    const circle = L.circleMarker([h.lat, h.lon], {{
      radius: getHutRadius(map.getZoom(), true),
      color: '#1d4ed8',
      weight: 1.2,
      opacity: 0.95,
      fillColor: 'transparent',
      fillOpacity: 0.0,
      interactive: false
    }}).addTo(map);
    hutMarkerItems.push({{ name: h.name, marker: circle, overnight: true, lat: h.lat, lon: h.lon }});
  }}

  const iconHtml = `<div style="display:flex;align-items:center;gap:4px;white-space:nowrap;filter:drop-shadow(0 1px 3px rgba(0,0,0,0.8));">
    <div style="background:${{h.overnight ? '#1d4ed8' : '#475569'}};color:white;font-size:10px;font-weight:bold;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:1.5px solid white;">${{h.overnight ? h.night : '⌂'}}</div>
    <span style="font-size:10.5px;font-weight:700;color:#f8fafc;background:rgba(15,23,42,0.85);padding:1px 5px;border-radius:3px;border:1px solid #334155;">${{h.name}}</span>
  </div>`;
  const mIcon = L.divIcon({{ html: iconHtml, className: 'custom-hut-icon', iconSize: [120, 20], iconAnchor: [9, 10] }});
  const m = L.marker([h.lat, h.lon], {{ icon: mIcon }}).addTo(map);

  const utmCoord = proj4("EPSG:4326", "EPSG:32632", [h.lon, h.lat]);
  const popContent = `<div style="font-family:sans-serif;font-size:12px;color:#0f172a;min-width:180px;">
    <strong style="font-size:13px;color:#0284c7;">${{h.name}}</strong>
    <span class="badge-tag ${{h.overnight ? 'badge-night' : ''}}">${{h.badge}}</span><br/>
    <strong>גובה:</strong> ${{h.ele}} מטר<br/>
    <strong>UTM 32N:</strong> E ${{Math.round(utmCoord[0])}} N ${{Math.round(utmCoord[1])}}<br/>
    <div style="margin-top:4px;color:#475569;font-size:11px;">${{h.desc}}</div>
  </div>`;
  m.bindPopup(popContent);

  // Add to drawer list
  const card = document.createElement('div');
  card.className = 'drawer-link';
  card.style.fontSize = '12px';
  card.style.padding = '6px 8px';
  card.innerHTML = `<span class="link-icon">${{h.overnight ? '🔵' : '⚪'}}</span><span>${{h.name}} (${{h.ele}}m)</span>`;
  card.addEventListener('click', () => {{
    switchView('view-map');
    map.setView([h.lat, h.lon], 15, {{ animate: true }});
    setTimeout(() => m.openPopup(), 300);
    closeSidebar();
  }});
  wpList.appendChild(card);
}});

map.on('zoomend', () => {{
  const z = map.getZoom();
  hutMarkerItems.forEach(item => {{
    item.marker.setRadius(getHutRadius(z, item.overnight));
  }});
}});

// ==========================================
// VIEW SWITCHING ENGINE
// ==========================================
function switchView(viewId) {{
  document.querySelectorAll('.app-view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));

  const targetView = document.getElementById(viewId);
  if (targetView) targetView.classList.add('active');

  const activeTab = document.querySelector(`.nav-tab[data-view="${{viewId}}"]`);
  if (activeTab) activeTab.classList.add('active');

  if (viewId === 'view-map') {{
    setTimeout(() => map.invalidateSize(), 100);
  }}
}}

function jumpToDay(dayNum) {{
  switchView('view-map');
  const stageRanges = {{
    1: [0.0, 10.26],
    2: [10.26, 19.51],
    3: [19.51, 32.00],
    4: [32.00, 38.02],
    5: [38.02, 50.20]
  }};
  const r = stageRanges[dayNum];
  if (r) {{
    const pts = trackPoints.filter(p => p.dist >= r[0] && p.dist <= r[1]);
    if (pts.length > 0) {{
      const b = L.latLngBounds(pts.map(p => [p.lat, p.lon]));
      map.fitBounds(b, {{ padding: [35, 35], animate: true }});
    }}
  }}
}}

function jumpToHut(hutName) {{
  switchView('view-map');
  const item = hutMarkerItems.find(h => h.name === hutName);
  if (item) {{
    map.setView([item.lat, item.lon], 15, {{ animate: true }});
  }}
}}

// SIDEBAR / DRAWER CONTROLS
const sidebar = document.getElementById('sidebar');
const drawerBackdrop = document.getElementById('drawer-backdrop');

function openSidebar() {{
  sidebar.classList.add('open');
  drawerBackdrop.classList.add('open');
}}

function closeSidebar() {{
  sidebar.classList.remove('open');
  drawerBackdrop.classList.remove('open');
}}

document.getElementById('menu-trigger').addEventListener('click', openSidebar);

// ==========================================
// TWO-WAY GPS / STUBAI TRAIL TOGGLE
// ==========================================
let userLocationMarker = null;
let userAccuracyCircle = null;
let lastUserLatLng = null;
let isAtUserLocation = false;
const gpsBtn = document.getElementById('gps-btn');
const trailBounds = trackPolyline.getBounds();

gpsBtn.addEventListener('click', function() {{
  if (isAtUserLocation) {{
    map.fitBounds(trailBounds, {{ padding: [25, 25], animate: true }});
    isAtUserLocation = false;
    gpsBtn.innerText = "🎯";
    gpsBtn.title = "Find My Location";
    gpsBtn.classList.remove('active-user');
  }} else {{
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
// ELEVATION PROFILE ENGINE & HUD
// ==========================================
function getDayInfo(distKm) {{
  const stages = [
    {{ day: 1, startKm: 0.0, endKm: 10.26, name: "Oberissalm ➔ Franz-Senn" }},
    {{ day: 2, startKm: 10.26, endKm: 19.51, name: "Franz-Senn ➔ Regensburger" }},
    {{ day: 3, startKm: 19.51, endKm: 32.00, name: "Regensburger ➔ Dresdner" }},
    {{ day: 4, startKm: 32.00, endKm: 38.02, name: "Dresdner ➔ Sulzenau" }},
    {{ day: 5, startKm: 38.02, endKm: 50.20, name: "Sulzenau ➔ Ranalt" }}
  ];
  for (const s of stages) {{
    if (distKm <= s.endKm || s.day === 5) {{
      const dayDist = Math.max(0, distKm - s.startKm);
      return {{ day: s.day, dayDist: dayDist.toFixed(1), name: s.name }};
    }}
  }}
  return {{ day: 1, dayDist: distKm.toFixed(1), name: stages[0].name }};
}}

const profilePanel = document.getElementById('profile-panel');
const profileCanvas = document.getElementById('profile-canvas');
const profileCtx = profileCanvas.getContext('2d');
const profileReadout = document.getElementById('profile-readout');
const floatingCoords = document.getElementById('floating-coords');
const utmCoordsDiv = document.getElementById('utm-coords');

let profileVisible = true;
let activeProfileIndex = null;

const trailHoverMarker = L.circleMarker([trackPoints[0].lat, trackPoints[0].lon], {{
  radius: 8,
  color: '#ffffff',
  fillColor: '#38bdf8',
  fillOpacity: 1.0,
  weight: 3.0
}});

function drawProfile(hoverIndex = null) {{
  const w = profileCanvas.width = profileCanvas.offsetWidth * window.devicePixelRatio;
  const h = profileCanvas.height = profileCanvas.offsetHeight * window.devicePixelRatio;
  const ctx = profileCtx;

  ctx.clearRect(0, 0, w, h);

  const padLeft = 46 * window.devicePixelRatio;
  const padRight = 16 * window.devicePixelRatio;
  const padTop = 16 * window.devicePixelRatio;
  const padBottom = 22 * window.devicePixelRatio;

  const chartW = w - padLeft - padRight;
  const chartH = h - padTop - padBottom;

  const minEle = 1200;
  const maxEle = 3000;
  const maxDist = total_dist_km;

  function getX(dist) {{ return padLeft + (dist / maxDist) * chartW; }}
  function getY(ele) {{ return padTop + chartH - ((ele - minEle) / (maxEle - minEle)) * chartH; }}

  // Grid lines
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#64748b';
  ctx.font = `${{10 * window.devicePixelRatio}}px monospace`;
  ctx.textAlign = 'right';

  for (let ele = 1500; ele <= maxEle; ele += 500) {{
    const y = getY(ele);
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();
    ctx.fillText(`${{ele}}m`, padLeft - 6, y + 3 * window.devicePixelRatio);
  }}

  // Gradient area
  const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
  grad.addColorStop(0, 'rgba(56, 189, 248, 0.45)');
  grad.addColorStop(1, 'rgba(56, 189, 248, 0.02)');

  ctx.beginPath();
  ctx.moveTo(getX(trackPoints[0].dist), getY(trackPoints[0].ele));
  for (let i = 1; i < trackPoints.length; i++) {{
    ctx.lineTo(getX(trackPoints[i].dist), getY(trackPoints[i].ele));
  }}
  ctx.lineTo(getX(trackPoints[trackPoints.length - 1].dist), padTop + chartH);
  ctx.lineTo(padLeft, padTop + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Trail stroke
  ctx.beginPath();
  ctx.moveTo(getX(trackPoints[0].dist), getY(trackPoints[0].ele));
  for (let i = 1; i < trackPoints.length; i++) {{
    ctx.lineTo(getX(trackPoints[i].dist), getY(trackPoints[i].ele));
  }}
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 2.2 * window.devicePixelRatio;
  ctx.stroke();

  // Hover indicator
  if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < trackPoints.length) {{
    const pt = trackPoints[hoverIndex];
    const hx = getX(pt.dist);
    const hy = getY(pt.ele);

    ctx.strokeStyle = '#f43f5e';
    ctx.lineWidth = 1.5 * window.devicePixelRatio;
    ctx.beginPath();
    ctx.moveTo(hx, padTop);
    ctx.lineTo(hx, padTop + chartH);
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(hx, hy, 5 * window.devicePixelRatio, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#f43f5e';
    ctx.lineWidth = 2.5 * window.devicePixelRatio;
    ctx.stroke();
  }}
}}

function setHoverPoint(idx) {{
  if (idx < 0 || idx >= trackPoints.length) return;
  activeProfileIndex = idx;
  const pt = trackPoints[idx];
  const utm = proj4("EPSG:4326", "EPSG:32632", [pt.lon, pt.lat]);
  const dInfo = getDayInfo(pt.dist);

  const statusText = `Day ${{dInfo.day}} (+${{dInfo.dayDist}}k) | Tot: ${{pt.dist.toFixed(1)}}k | Ele: ${{Math.round(pt.ele)}}m | UTM: E ${{Math.round(utm[0]/1000)}}k N ${{Math.round(utm[1]/1000)}}k`;
  profileReadout.innerText = statusText;
  floatingCoords.innerText = `Day ${{dInfo.day}} • ${{pt.dist.toFixed(1)}}k • ${{Math.round(pt.ele)}}m`;
  utmCoordsDiv.innerText = `E ${{Math.round(utm[0])}} N ${{Math.round(utm[1])}} (Zone 32N)`;

  trailHoverMarker.setLatLng([pt.lat, pt.lon]);
  if (!map.hasLayer(trailHoverMarker)) trailHoverMarker.addTo(map);

  drawProfile(idx);
}}

function clearHover() {{
  activeProfileIndex = null;
  profileReadout.innerText = "גרור אצבע על הפרופיל או המפה לבדיקה...";
  floatingCoords.innerText = `Stubai 50.2 km`;
  if (map.hasLayer(trailHoverMarker)) map.removeLayer(trailHoverMarker);
  drawProfile(null);
}}

// PROFILE TOUCH / MOUSE INTERACTION
function handleProfileEvent(clientX) {{
  const rect = profileCanvas.getBoundingClientRect();
  const padLeft = 46;
  const padRight = 16;
  const chartW = rect.width - padLeft - padRight;
  const relX = clientX - rect.left - padLeft;

  if (relX < 0 || relX > chartW) {{
    clearHover();
    return;
  }}

  const targetDist = (relX / chartW) * total_dist_km;
  let closestIdx = 0;
  let minDiff = Infinity;
  for (let i = 0; i < trackPoints.length; i++) {{
    const diff = Math.abs(trackPoints[i].dist - targetDist);
    if (diff < minDiff) {{
      minDiff = diff;
      closestIdx = i;
    }}
  }}
  setHoverPoint(closestIdx);
}}

profileCanvas.addEventListener('mousemove', e => handleProfileEvent(e.clientX));
profileCanvas.addEventListener('mouseleave', clearHover);

profileCanvas.addEventListener('touchstart', e => {{
  if (e.touches.length > 0) handleProfileEvent(e.touches[0].clientX);
}}, {{ passive: true }});

profileCanvas.addEventListener('touchmove', e => {{
  if (e.touches.length > 0) handleProfileEvent(e.touches[0].clientX);
}}, {{ passive: true }});

profileCanvas.addEventListener('touchend', clearHover);

// Toggle profile dock
function toggleProfile() {{
  profileVisible = !profileVisible;
  if (profileVisible) {{
    profilePanel.classList.remove('hidden');
    drawProfile(activeProfileIndex);
  }} else {{
    profilePanel.classList.add('hidden');
    clearHover();
  }}
}}
document.getElementById('fab-profile').addEventListener('click', toggleProfile);
document.getElementById('close-profile').addEventListener('click', toggleProfile);

// Toggle 1 km UTM Grid
let gridVisible = true;
document.getElementById('fab-grid').addEventListener('click', () => {{
  gridVisible = !gridVisible;
  if (gridVisible) map.addLayer(gridLayer);
  else map.removeLayer(gridLayer);
}});

// ==========================================
// GEAR CHECKLIST INTERACTIVITY & LOCALSTORAGE
// ==========================================
const defaultGear = {json.dumps(gear_items, ensure_ascii=False)};
let currentGearFilter = 'all';

function loadGearState() {{
  try {{
    const saved = localStorage.getItem('stubai_gear_state_v2');
    return saved ? JSON.parse(saved) : {{}};
  }} catch(e) {{
    return {{}};
  }}
}}

function saveGearState(state) {{
  try {{
    localStorage.setItem('stubai_gear_state_v2', JSON.stringify(state));
  }} catch(e) {{}}
}}

function loadCustomItems() {{
  try {{
    const saved = localStorage.getItem('stubai_gear_custom_v2');
    return saved ? JSON.parse(saved) : [];
  }} catch(e) {{
    return [];
  }}
}}

function saveCustomItems(items) {{
  try {{
    localStorage.setItem('stubai_gear_custom_v2', JSON.stringify(items));
  }} catch(e) {{}}
}}

function renderGearList() {{
  const gearListContainer = document.getElementById('gear-items-list');
  if (!gearListContainer) return;

  const state = loadGearState();
  const custom = loadCustomItems();
  const allItems = [...defaultGear, ...custom];

  gearListContainer.innerHTML = '';

  // Group by category
  const groups = {{}};
  allItems.forEach(item => {{
    const cat = item.cat || 'ציוד אישי';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  }});

  let totalCount = allItems.length;
  let packedCount = 0;

  for (const [catName, items] of Object.entries(groups)) {{
    const groupBlock = document.createElement('div');
    groupBlock.className = 'gear-group-block';

    const groupTitle = document.createElement('div');
    groupTitle.className = 'gear-group-title';
    groupTitle.innerText = catName;
    groupBlock.appendChild(groupTitle);

    let visibleInGroup = 0;

    items.forEach(item => {{
      const isChecked = !!state[item.id];
      if (isChecked) packedCount++;

      // Filter check
      if (currentGearFilter === 'packed' && !isChecked) return;
      if (currentGearFilter === 'unpacked' && isChecked) return;

      visibleInGroup++;

      const row = document.createElement('div');
      row.className = `gear-item-row ${{isChecked ? 'checked' : ''}}`;
      row.innerHTML = `
        <div class="gear-checkbox">${{isChecked ? '✓' : ''}}</div>
        <div class="gear-text">${{item.name}}</div>
      `;
      row.addEventListener('click', () => {{
        state[item.id] = !state[item.id];
        saveGearState(state);
        renderGearList();
      }});
      groupBlock.appendChild(row);
    }});

    if (visibleInGroup > 0) {{
      gearListContainer.appendChild(groupBlock);
    }}
  }}

  // Update counter & progress bar
  const pct = totalCount > 0 ? Math.round((packedCount / totalCount) * 100) : 0;
  const counterEl = document.getElementById('gear-counter');
  const percentEl = document.getElementById('gear-percent');
  const progressFill = document.getElementById('gear-progress-bar');

  if (counterEl) counterEl.innerText = `${{packedCount}} / ${{totalCount}} פריטים נארזו`;
  if (percentEl) percentEl.innerText = `${{pct}}%`;
  if (progressFill) progressFill.style.width = `${{pct}}%`;
}}

function setGearFilter(filter) {{
  currentGearFilter = filter;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  const target = Array.from(document.querySelectorAll('.filter-pill')).find(p => {{
    if (filter === 'all' && p.innerText === 'הכל') return true;
    if (filter === 'unpacked' && p.innerText === 'טרם נארז') return true;
    if (filter === 'packed' && p.innerText === 'נארז') return true;
    return false;
  }});
  if (target) target.classList.add('active');
  renderGearList();
}}

function resetGearChecklist() {{
  if (confirm("האם לאפס את סימוני הציוד לכולם?")) {{
    saveGearState({{}});
    renderGearList();
  }}
}}

function addCustomGearItem() {{
  const input = document.getElementById('new-item-input');
  const val = input.value.trim();
  if (!val) return;
  const custom = loadCustomItems();
  custom.push({{
    id: 'custom_' + Date.now(),
    cat: 'ציוד אישי',
    name: val
  }});
  saveCustomItems(custom);
  input.value = '';
  renderGearList();
}}

// Initialize gear checklist
renderGearList();

// ==========================================
// OFFLINE PWA & TILE PRE-CACHING
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

const offlineModal = document.getElementById('offline-modal');
const modalIcon = document.getElementById('modal-icon');
const modalTitle = document.getElementById('modal-title');
const modalStatus = document.getElementById('modal-status');
const progressBar = document.getElementById('progress-bar');
const iosGuide = document.getElementById('ios-guide');
const modalClose = document.getElementById('modal-close');

function closeOfflineModal() {{
  offlineModal.style.display = 'none';
}}

async function startOfflineDownload() {{
  closeSidebar();
  if (deferredPrompt) {{
    try {{
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(() => {{ deferredPrompt = null; }});
    }} catch(e) {{}}
  }}

  offlineModal.style.display = 'flex';
  modalIcon.innerText = "⏳";
  modalTitle.innerText = "שומר מפה לאופליין";
  modalStatus.innerText = "מוריד 280 אריחי מפה טופוגרפיים לכל 5 הימים...";
  progressBar.style.width = '0%';
  modalClose.style.display = 'none';
  if (iosGuide) iosGuide.style.display = 'none';

  if (!('caches' in window)) {{
    modalIcon.innerText = "⚠️";
    modalTitle.innerText = "שמירה לאופליין אינה נתמכת בדפדפן זה";
    modalStatus.innerText = "נסה לפתוח ב-Chrome או Safari.";
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
      }} catch (err) {{}}
      done++;
      const pct = Math.round((done / total) * 100);
      progressBar.style.width = pct + '%';
      modalStatus.innerText = `הורדו ${{done}} מתוך ${{total}} אריחים (${{pct}}%)...`;
    }}));
  }}

  modalIcon.innerText = "✅";
  modalTitle.innerText = "המפה זמינה 100% באופליין!";
  modalStatus.innerHTML = "<strong>כל 5 הימים של שביל שטובאי שמורים כעת בטלפון שלכם!</strong><br/><br/>ניתן לפתוח את האפליקציה בכל מקום באלפים, לעקוב אחר השביל ולהשתמש ב-GPS ללא קליטה סלולרית.";
  modalClose.style.display = 'block';

  if (isIOS) {{
    iosGuide.style.display = 'block';
  }}
}}

window.addEventListener('resize', () => {{
  if (profileVisible) drawProfile(activeProfileIndex);
}});

// Initial Profile Draw
setTimeout(() => drawProfile(null), 150);
</script>
</body>
</html>"""

# Write to state/maps and root index.html
output_path = Path("state/maps/Stubai_High_Route_Interactive_UTM_Map.html")
output_path.write_text(html_content, encoding="utf-8")
print(f"Saved mobile-optimized interactive viewer to {output_path}")

index_path = Path("index.html")
index_path.write_text(html_content, encoding="utf-8")
print(f"Also created {index_path} in root directory for GitHub Pages hosting!")
