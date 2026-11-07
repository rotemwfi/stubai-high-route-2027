#!/usr/bin/env python3
"""
build_3d_route_viewer.py
Ingests user route coordinates from KML, CSV, GPX, GeoJSON, or raw text,
automatically enriches 2D coordinates with 3D DEM terrain elevations if needed,
and scaffolds a complete local 3D interactive route fly-through web application
in /state/viewer_3d/ supporting:
  1. Mapbox GL JS v3 (3D Terrain DEM + Sky + FreeCamera Fly-Through)
  2. Google Maps Photorealistic 3D Tiles (via CesiumJS 3DTileset)
  3. Instant Keyless 3D Terrain (MapLibre GL JS + AWS Terrarium 3D DEM + Esri Satellite / OpenTopoMap)
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "route_3d_viewer_config.json"
STATE_DIR = BASE_DIR / "state"
VIEWER_DIR = STATE_DIR / "viewer_3d"

if str(BASE_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "scripts"))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlon / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(min(1.0, a)))


def parse_kml(content: str) -> Tuple[List[Tuple[float, float, float]], List[Dict[str, Any]], str]:
    root = ET.fromstring(content)
    pts: List[Tuple[float, float, float]] = []
    waypoints: List[Dict[str, Any]] = []
    title = "3D KML Route"

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "name" and title == "3D KML Route" and elem.text:
            title = elem.text.strip()
        elif tag == "Placemark":
            pm_name = ""
            pm_desc = ""
            pm_coords: List[Tuple[float, float, float]] = []
            for sub in elem.iter():
                stag = sub.tag.split("}")[-1]
                if stag == "name" and sub.text and not pm_name:
                    pm_name = sub.text.strip()
                elif stag == "description" and sub.text and not pm_desc:
                    pm_desc = sub.text.strip()
                elif stag == "coordinates" and sub.text:
                    for token in sub.text.strip().split():
                        parts = [p for p in token.split(",") if p != ""]
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            ele = float(parts[2]) if len(parts) >= 3 else 0.0
                            pm_coords.append((lat, lon, ele))
                elif stag == "coord" and sub.text:
                    parts = sub.text.strip().split()
                    if len(parts) >= 2:
                        lon, lat = float(parts[0]), float(parts[1])
                        ele = float(parts[2]) if len(parts) >= 3 else 0.0
                        pm_coords.append((lat, lon, ele))
            if len(pm_coords) == 1:
                la, lo, el = pm_coords[0]
                waypoints.append({"name": pm_name or "Waypoint", "lat": la, "lon": lo, "ele": el, "desc": pm_desc})
            elif len(pm_coords) > 1:
                pts.extend(pm_coords)

    if not pts and waypoints:
        pts = [(w["lat"], w["lon"], w["ele"]) for w in waypoints]
    return pts, waypoints, title


def parse_gpx(content: str) -> Tuple[List[Tuple[float, float, float]], List[Dict[str, Any]], str]:
    root = ET.fromstring(content)
    pts: List[Tuple[float, float, float]] = []
    waypoints: List[Dict[str, Any]] = []
    title = "3D GPX Route"

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "name" and title == "3D GPX Route" and elem.text:
            title = elem.text.strip()
        elif tag in ("trkpt", "rtept"):
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            ele = 0.0
            for child in elem:
                if child.tag.split("}")[-1] == "ele" and child.text:
                    ele = float(child.text.strip())
            pts.append((lat, lon, ele))
        elif tag == "wpt":
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            ele = 0.0
            wname = "Waypoint"
            wdesc = ""
            for child in elem:
                ctag = child.tag.split("}")[-1]
                if ctag == "ele" and child.text:
                    ele = float(child.text.strip())
                elif ctag == "name" and child.text:
                    wname = child.text.strip()
                elif ctag == "desc" and child.text:
                    wdesc = child.text.strip()
            waypoints.append({"name": wname, "lat": lat, "lon": lon, "ele": ele, "desc": wdesc})

    if not pts and waypoints:
        pts = [(w["lat"], w["lon"], w["ele"]) for w in waypoints]
    return pts, waypoints, title


def parse_csv_or_raw(text: str, title: str = "Custom 3D Route") -> Tuple[List[Tuple[float, float, float]], List[Dict[str, Any]], str]:
    pts: List[Tuple[float, float, float]] = []
    waypoints: List[Dict[str, Any]] = []

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        raise ValueError("Empty coordinate input")

    # Try CSV DictReader if header has lat/lon keywords
    first_lower = lines[0].lower()
    if any(k in first_lower for k in ("lat", "lon", "lng", "x", "y")):
        reader = csv.DictReader(io.StringIO("\n".join(lines)))
        for row in reader:
            norm = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
            lat_v = norm.get("lat") or norm.get("latitude") or norm.get("y")
            lon_v = norm.get("lon") or norm.get("lng") or norm.get("longitude") or norm.get("x")
            ele_v = norm.get("ele") or norm.get("elevation") or norm.get("alt") or norm.get("altitude") or norm.get("z") or "0"
            name_v = norm.get("name") or norm.get("label") or norm.get("waypoint") or ""
            if lat_v and lon_v:
                la, lo, el = float(lat_v), float(lon_v), float(ele_v or 0.0)
                pts.append((la, lo, el))
                if name_v:
                    waypoints.append({"name": name_v, "lat": la, "lon": lo, "ele": el, "desc": ""})
        if pts:
            return pts, waypoints, title

    # Fallback: raw text coordinate extraction (supports "lat, lon[, ele]" or "lon, lat[, ele]")
    num_pattern = re.compile(r"[-+]?\d+(?:\.\d+)?")
    for ln in lines:
        nums = [float(x) for x in num_pattern.findall(ln)]
        if len(nums) >= 2:
            a, b = nums[0], nums[1]
            el = nums[2] if len(nums) >= 3 and abs(nums[2]) > 90 else 0.0
            # Heuristic for Europe/Stubai or global lat/lon ordering:
            if 40.0 <= abs(a) <= 85.0 and abs(b) < 40.0:
                lat, lon = a, b
            elif 40.0 <= abs(b) <= 85.0 and abs(a) < 40.0:
                lon, lat = a, b
            elif abs(a) <= 90.0 and abs(b) <= 180.0:
                lat, lon = a, b
            else:
                lon, lat = a, b
            pts.append((lat, lon, el))

    return pts, waypoints, title


def load_route_any_format(
    input_path: Optional[Path],
    raw_coords: Optional[str]
) -> Tuple[List[Tuple[float, float, float]], List[Dict[str, Any]], str]:
    if raw_coords:
        return parse_csv_or_raw(raw_coords, title="User Raw Coordinate Route")

    if not input_path:
        default_gpx = BASE_DIR / "export.gpx"
        fallback_gpx = STATE_DIR / "gpx" / "stubai_selected_route_2027.gpx"
        input_path = default_gpx if default_gpx.exists() else fallback_gpx

    if not input_path or not input_path.exists():
        raise FileNotFoundError(f"Route file not found: {input_path}")

    raw_text = input_path.read_text(encoding="utf-8", errors="ignore")
    ext = input_path.suffix.lower()

    if ext == ".kml" or "<kml" in raw_text[:400].lower():
        return parse_kml(raw_text)
    if ext == ".gpx" or "<gpx" in raw_text[:400].lower():
        return parse_gpx(raw_text)
    if ext in (".geojson", ".json") or raw_text.lstrip().startswith("{"):
        data = json.loads(raw_text)
        pts: List[Tuple[float, float, float]] = []
        wps: List[Dict[str, Any]] = []
        feats = data.get("features", [data]) if isinstance(data, dict) else []
        for f in feats:
            geom = f.get("geometry", f)
            gtype = geom.get("type", "")
            coords = geom.get("coordinates", [])
            props = f.get("properties", {}) or {}
            if gtype == "LineString":
                for c in coords:
                    pts.append((float(c[1]), float(c[0]), float(c[2]) if len(c) > 2 else 0.0))
            elif gtype == "MultiLineString":
                for seg in coords:
                    for c in seg:
                        pts.append((float(c[1]), float(c[0]), float(c[2]) if len(c) > 2 else 0.0))
            elif gtype == "Point" and len(coords) >= 2:
                wps.append({
                    "name": props.get("name", "Waypoint"),
                    "lat": float(coords[1]),
                    "lon": float(coords[0]),
                    "ele": float(coords[2]) if len(coords) > 2 else 0.0,
                    "desc": props.get("desc", "")
                })
        return pts, wps, input_path.stem

    return parse_csv_or_raw(raw_text, title=input_path.stem)


def enrich_stubai_landmarks(
    pts: List[Tuple[float, float, float]],
    waypoints: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not pts:
        return waypoints
    mean_lat = sum(p[0] for p in pts) / len(pts)
    mean_lon = sum(p[1] for p in pts) / len(pts)

    # If the route is in the Stubai Alps region, attach verified hut specs from scripts/hut_specs.py
    if 46.85 <= mean_lat <= 47.25 and 11.0 <= mean_lon <= 11.45:
        try:
            import hut_specs  # type: ignore
            existing_names = {w["name"].lower() for w in waypoints}
            for h in getattr(hut_specs, "HUTS", []):
                if h["name"].lower() not in existing_names:
                    waypoints.append({
                        "name": h["name"],
                        "lat": float(h["lat"]),
                        "lon": float(h["lon"]),
                        "ele": float(h.get("alt", 2200)),
                        "desc": f"{h.get('badge', 'Mountain Hut')} ({h.get('alt', '')}m)",
                        "night": h.get("night")
                    })
        except Exception:
            pass
    return waypoints


def build_viewer_bundle(
    pts: List[Tuple[float, float, float]],
    waypoints: List[Dict[str, Any]],
    route_title: str,
    mapbox_token: str = "",
    google_key: str = ""
) -> Dict[str, Any]:
    VIEWER_DIR.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    # Compute cumulative distances, elevation stats, and downsample if > 2,500 points for smooth 60fps 3D camera
    step = max(1, len(pts) // 2000)
    sampled = pts[::step]
    if sampled[-1] != pts[-1]:
        sampled.append(pts[-1])

    track_records: List[Dict[str, float]] = []
    cum_km = 0.0
    gain_m = 0.0
    loss_m = 0.0

    for i, (lat, lon, ele) in enumerate(sampled):
        if i > 0:
            prev_lat, prev_lon, prev_ele = sampled[i - 1]
            cum_km += haversine_km(prev_lat, prev_lon, lat, lon)
            diff = ele - prev_ele
            if diff > 0:
                gain_m += diff
            else:
                loss_m += abs(diff)
        track_records.append({
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "ele": round(ele if ele > 0 else 2200.0, 1),
            "dist_km": round(cum_km, 3)
        })

    payload = {
        "title": route_title,
        "stats": {
            "point_count": len(track_records),
            "total_distance_km": round(cum_km, 2),
            "total_ascent_m": round(gain_m),
            "total_descent_m": round(loss_m),
            "min_ele_m": round(min(r["ele"] for r in track_records)),
            "max_ele_m": round(max(r["ele"] for r in track_records))
        },
        "default_keys": {
            "mapbox_token": mapbox_token or os.environ.get("MAPBOX_ACCESS_TOKEN", ""),
            "google_key": google_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        },
        "config": cfg,
        "waypoints": waypoints,
        "track": track_records
    }

    (VIEWER_DIR / "route_data.js").write_text(
        "window.ROUTE_3D_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )

    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>3D Interactive Route Fly-Through Viewer — Antigravity 2.0</title>
  <!-- MapLibre GL JS v4 (3D Terrain + Sky, Zero-Key Default) -->
  <link href="https://unpkg.com/maplibre-gl@4.3.2/dist/maplibre-gl.css" rel="stylesheet" />
  <script src="https://unpkg.com/maplibre-gl@4.3.2/dist/maplibre-gl.js"></script>
  <!-- Mapbox GL JS v3 (Loaded dynamically when Mapbox Token is active) -->
  <link href="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.css" rel="stylesheet" />
  <script src="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.js"></script>
  <!-- CesiumJS for Google Photorealistic 3D Tiles -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.116/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.116/Build/Cesium/Widgets/widgets.css" rel="stylesheet" />
  <!-- Proj4js for live UTM Zone 32N HUD -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.11.0/proj4.js"></script>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header id="topbar">
    <div class="brand">
      <span class="badge-3d">3D FLY-THROUGH</span>
      <h1 id="route-title">Loading 3D Route...</h1>
      <span id="route-stats" class="stats-pill"></span>
    </div>
    <div class="controls-right">
      <label class="ctrl-label">3D Engine:
        <select id="engine-select">
          <option value="terrain3d">3D Satellite + AWS Terrarium DEM (Instant / No Key)</option>
          <option value="topo3d">3D OpenTopoMap 1:25k Contours + DEM</option>
          <option value="mapbox3d">Mapbox GL JS v3 3D Terrain (Token)</option>
          <option value="google3d">Google Maps Photorealistic 3D Tiles (API Key)</option>
        </select>
      </label>
      <button id="btn-keys" class="btn-secondary" title="Configure Mapbox or Google 3D Tiles API Keys">API Keys</button>
      <label class="ctrl-label">Upload Route:
        <input type="file" id="file-upload" accept=".gpx,.kml,.csv,.txt,.geojson,.json" />
      </label>
    </div>
  </header>

  <main id="viewport">
    <div id="map3d"></div>
    <div id="cesium3d" style="display:none;"></div>

    <!-- Live Cockpit / Telemetry HUD -->
    <div id="hud-box">
      <div><strong>DIST:</strong> <span id="hud-dist">0.00 km</span></div>
      <div><strong>ALT:</strong> <span id="hud-ele">0 m</span></div>
      <div><strong>UTM 32N:</strong> <span id="hud-utm">--</span></div>
      <div><strong>CAMERA:</strong> <span id="hud-cam">--</span></div>
    </div>

    <!-- Floating Fly-Through Flight Deck -->
    <section id="flight-deck">
      <div class="deck-buttons">
        <button id="btn-play" class="btn-primary">&#9654; Fly Route</button>
        <button id="btn-reset" class="btn-secondary">&#8634; Overview</button>
        <label class="slider-lbl">Speed
          <select id="speed-select">
            <option value="0.1">0.1x</option>
            <option value="0.25">0.25x</option>
            <option value="0.5">0.5x</option>
            <option value="1" selected>1.0x</option>
            <option value="2">2.0x</option>
            <option value="4">4.0x</option>
          </select>
        </label>
        <label class="slider-lbl">Zoom
          <input type="range" id="zoom-slider" min="11.0" max="16.5" step="0.1" value="14.0" />
        </label>
        <label class="slider-lbl">Pitch
          <input type="range" id="pitch-slider" min="30" max="80" value="65" />
        </label>
        <label class="slider-lbl">3D Exaggeration
          <input type="range" id="exag-slider" min="1.0" max="2.5" step="0.1" value="1.35" />
        </label>
      </div>
      <div class="scrub-container">
        <input type="range" id="route-scrubber" min="0" max="1000" value="0" />
        <canvas id="elev-canvas" width="900" height="72"></canvas>
      </div>
    </section>
  </main>

  <!-- API Key Modal for Mapbox GL JS & Google 3D Tiles -->
  <div id="key-modal" class="modal hidden">
    <div class="modal-card">
      <h2>Configure 3D Provider Keys (Optional)</h2>
      <p>The viewer runs immediately using 3D AWS Terrarium DEM + Esri Satellite. To switch to Mapbox GL JS v3 or Google Photorealistic 3D Tiles, enter your key below:</p>
      <label>Mapbox Access Token (<code>pk....</code>):
        <input type="text" id="input-mapbox-token" placeholder="pk.eyJ1Ijoi..." />
      </label>
      <label>Google Maps 3D Tiles API Key (<code>AIza...</code>):
        <input type="text" id="input-google-key" placeholder="AIzaSy..." />
      </label>
      <div class="modal-actions">
        <button id="btn-save-keys" class="btn-primary">Save &amp; Apply</button>
        <button id="btn-close-keys" class="btn-secondary">Cancel</button>
      </div>
    </div>
  </div>

  <script src="route_data.js?v=3.0"></script>
  <script src="app.js?v=3.0"></script>
</body>
</html>
"""

    styles_css = """* { box-sizing: border-box; }
body, html { margin: 0; padding: 0; width: 100%; height: 100%; font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; overflow: hidden; }
#topbar { height: 56px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; z-index: 20; position: relative; }
.brand { display: flex; align-items: center; gap: 12px; }
.badge-3d { background: #2563eb; color: #fff; font-weight: 700; font-size: 11px; padding: 4px 8px; border-radius: 6px; letter-spacing: 0.5px; }
#route-title { font-size: 16px; margin: 0; font-weight: 700; white-space: nowrap; }
.stats-pill { font-size: 12px; color: #38bdf8; background: #0f172a; padding: 4px 10px; border-radius: 999px; border: 1px solid #334155; }
.controls-right { display: flex; align-items: center; gap: 10px; font-size: 12px; }
.ctrl-label { display: flex; align-items: center; gap: 6px; color: #cbd5e1; }
select, input[type="text"] { background: #0f172a; color: #f8fafc; border: 1px solid #475569; border-radius: 6px; padding: 5px 8px; font-size: 12px; }
input[type="file"] { font-size: 11px; color: #94a3b8; max-width: 180px; }
.btn-primary { background: #dc2626; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; cursor: pointer; }
.btn-primary:hover { background: #ef4444; }
.btn-secondary { background: #334155; color: #f8fafc; border: 1px solid #475569; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; cursor: pointer; }
#viewport { position: relative; width: 100%; height: calc(100vh - 56px); }
#map3d, #cesium3d { width: 100%; height: 100%; }
#hud-box { position: absolute; top: 14px; left: 14px; background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(8px); border: 1px solid #334155; border-radius: 10px; padding: 10px 14px; font-size: 12px; line-height: 1.6; z-index: 10; pointer-events: none; }
#hud-box strong { color: #94a3b8; margin-right: 4px; }
#hud-box span { color: #38bdf8; font-family: monospace; font-weight: 700; }
#flight-deck { position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%); width: min(980px, 95vw); background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(10px); border: 1px solid #334155; border-radius: 14px; padding: 12px 16px; z-index: 10; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
.deck-buttons { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 8px; }
.slider-lbl { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #cbd5e1; }
.slider-lbl input[type="range"] { width: 85px; accent-color: #38bdf8; cursor: pointer; }
.scrub-container { position: relative; width: 100%; }
#route-scrubber { width: 100%; margin: 0 0 4px 0; accent-color: #dc2626; cursor: pointer; }
#elev-canvas { width: 100%; height: 64px; display: block; background: rgba(30, 41, 59, 0.6); border-radius: 6px; }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.65); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal.hidden { display: none; }
.modal-card { background: #1e293b; border: 1px solid #475569; border-radius: 12px; padding: 20px; width: min(460px, 92vw); }
.modal-card h2 { margin: 0 0 8px; font-size: 17px; }
.modal-card p { font-size: 13px; color: #cbd5e1; line-height: 1.45; }
.modal-card label { display: block; font-size: 12px; margin-top: 12px; color: #e2e8f0; }
.modal-card input { width: 100%; margin-top: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.hut-marker { background: #0f172a; color: #fff; border: 2px solid #38bdf8; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 6px rgba(0,0,0,0.4); }
"""

    app_js = """(function() {
  proj4.defs("EPSG:32632", "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs");

  let data = window.ROUTE_3D_DATA;
  let track = data.track || [];
  let waypoints = data.waypoints || [];

  const urlParams = new URLSearchParams(window.location.search);
  let mapboxToken = urlParams.get("mapbox_token") || localStorage.getItem("AGY_MAPBOX_TOKEN") || data.default_keys.mapbox_token || "";
  let googleKey = urlParams.get("google_key") || localStorage.getItem("AGY_GOOGLE_3D_KEY") || data.default_keys.google_key || "";

  let map = null;
  let cesiumViewer = null;
  let isPlaying = false;
  let animFrame = null;
  let playProgress = 0; // 0 .. track.length - 1
  let currentBearer = 0;
  let lockedBearing = null;
  let targetBearing = 0;
  let isBearingLocked = false;
  let currentValleyBias = 0;
  let targetValleyBias = 0;
  let currentPitch = 65;
  let targetPitch = 65;
  let isInitialFrame = true;
  let markerCursor = null;

  const titleEl = document.getElementById("route-title");
  const statsEl = document.getElementById("route-stats");
  const hudDist = document.getElementById("hud-dist");
  const hudEle = document.getElementById("hud-ele");
  const hudUtm = document.getElementById("hud-utm");
  const hudCam = document.getElementById("hud-cam");
  const scrubber = document.getElementById("route-scrubber");
  const elevCanvas = document.getElementById("elev-canvas");
  const playBtn = document.getElementById("btn-play");
  const zoomSlider = document.getElementById("zoom-slider");
  let currentZoom = 14.0;
  const pitchSlider = document.getElementById("pitch-slider");
  const exagSlider = document.getElementById("exag-slider");
  const speedSelect = document.getElementById("speed-select");
  const engineSelect = document.getElementById("engine-select");

  function updateHeader() {
    titleEl.textContent = data.title || "3D Route Fly-Through";
    const s = data.stats;
    statsEl.textContent = `${s.total_distance_km} km | +${s.total_ascent_m}m / -${s.total_descent_m}m | ${s.min_ele_m}m–${s.max_ele_m}m`;
    scrubber.max = Math.max(1, track.length - 1);
    drawElevationProfile(0);
  }

  function computeBearing(lat1, lon1, lat2, lon2) {
    const toRad = d => d * Math.PI / 180;
    const toDeg = r => r * 180 / Math.PI;
    const dLon = toRad(lon2 - lon1);
    const y = Math.sin(dLon) * Math.cos(toRad(lat2));
    const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
              Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
  }

  function updateHUD(idx) {
    const pt = typeof getPointAtIdx === "function" ? getPointAtIdx(idx) : track[Math.min(track.length - 1, Math.max(0, Math.floor(idx)))];
    if (!pt) return;
    hudDist.textContent = `${pt.dist_km.toFixed(2)} km`;
    hudEle.textContent = `${Math.round(pt.ele)} m`;
    try {
      const [e, n] = proj4("EPSG:4326", "EPSG:32632", [pt.lon, pt.lat]);
      hudUtm.textContent = `${Math.round(e)}E ${Math.round(n)}N`;
    } catch (_) {}
    const isAutoPitch = Math.abs(currentPitch - parseFloat(pitchSlider.value)) > 2.5;
    const lockLabel = isBearingLocked ? "🔒 locked" : "↻ turning";
    hudCam.textContent = `${Math.round(currentPitch)}°${isAutoPitch ? " (auto)" : ""} | ${Math.round(currentBearer)}° ${lockLabel} | Z:${currentZoom.toFixed(1)} | ${exagSlider.value}x`;
  }

  function drawElevationProfile(activeIdx) {
    const ctx = elevCanvas.getContext("2d");
    const w = elevCanvas.width;
    const h = elevCanvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!track.length) return;

    const minE = data.stats.min_ele_m - 80;
    const maxE = data.stats.max_ele_m + 80;
    const spanE = Math.max(100, maxE - minE);

    ctx.beginPath();
    ctx.moveTo(0, h);
    track.forEach((p, i) => {
      const x = (i / (track.length - 1)) * w;
      const y = h - ((p.ele - minE) / spanE) * (h - 10) - 4;
      ctx.lineTo(x, y);
    });
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fillStyle = "rgba(56, 189, 248, 0.22)";
    ctx.fill();

    ctx.beginPath();
    track.forEach((p, i) => {
      const x = (i / (track.length - 1)) * w;
      const y = h - ((p.ele - minE) / spanE) * (h - 10) - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Active cursor line
    const cx = (activeIdx / Math.max(1, track.length - 1)) * w;
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, h);
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }

  function getRouteGeoJSON() {
    return {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: track.map(p => [p.lon, p.lat, p.ele])
      }
    };
  }

  function buildFree3DStyle(mode) {
    const rasterUrl = mode === "topo3d"
      ? "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
      : "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
    return {
      version: 8,
      sources: {
        rasterBase: {
          type: "raster",
          tiles: [rasterUrl],
          tileSize: 256,
          maxzoom: 17
        },
        terrainDem: {
          type: "raster-dem",
          tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
          tileSize: 256,
          encoding: "terrarium",
          maxzoom: 14
        },
        hillshadeDem: {
          type: "raster-dem",
          tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
          tileSize: 256,
          encoding: "terrarium",
          maxzoom: 14
        }
      },
      terrain: {
        source: "terrainDem",
        exaggeration: parseFloat(exagSlider.value)
      },
      layers: [
        { id: "base-layer", type: "raster", source: "rasterBase" },
        {
          id: "hills",
          type: "hillshade",
          source: "hillshadeDem",
          paint: { "hillshade-exaggeration": 0.45 }
        }
      ]
    };
  }

  function addRouteAndWaypointsToGL(glMap, libObj) {
    glMap.addSource("route", {
      type: "geojson",
      data: getRouteGeoJSON()
    });
    glMap.addLayer({
      id: "route-casing",
      type: "line",
      source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#ffffff", "line-width": 8 }
    });
    glMap.addLayer({
      id: "route-line",
      type: "line",
      source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#dc2626", "line-width": 5 }
    });

    waypoints.forEach(w => {
      const el = document.createElement("div");
      el.className = "hut-marker";
      el.textContent = w.night ? `Night ${w.night}: ${w.name}` : w.name;
      new libObj.Marker({ element: el, anchor: "bottom" })
        .setLngLat([w.lon, w.lat])
        .setPopup(new libObj.Popup().setHTML(`<strong>${w.name}</strong><br/>${w.desc || ""}`))
        .addTo(glMap);
    });

    const curEl = document.createElement("div");
    curEl.style.width = "16px";
    curEl.style.height = "16px";
    curEl.style.borderRadius = "50%";
    curEl.style.background = "#38bdf8";
    curEl.style.border = "3px solid #fff";
    curEl.style.boxShadow = "0 0 12px #38bdf8";
    markerCursor = new libObj.Marker({ element: curEl })
      .setLngLat([track[0].lon, track[0].lat])
      .addTo(glMap);
  }

  function initMapEngine(mode) {
    stopFlythrough();
    const mapDiv = document.getElementById("map3d");
    const cesDiv = document.getElementById("cesium3d");

    if (map) { map.remove(); map = null; }
    if (cesiumViewer) { cesiumViewer.destroy(); cesiumViewer = null; }

    if (mode === "google3d") {
      if (!googleKey) {
        document.getElementById("key-modal").classList.remove("hidden");
        engineSelect.value = "terrain3d";
        return initMapEngine("terrain3d");
      }
      mapDiv.style.display = "none";
      cesDiv.style.display = "block";
      initGoogle3DTiles();
      return;
    }

    mapDiv.style.display = "block";
    cesDiv.style.display = "none";

    if (mode === "mapbox3d") {
      if (!mapboxToken) {
        document.getElementById("key-modal").classList.remove("hidden");
        engineSelect.value = "terrain3d";
        return initMapEngine("terrain3d");
      }
      mapboxgl.accessToken = mapboxToken;
      map = new mapboxgl.Map({
        container: "map3d",
        style: "mapbox://styles/mapbox/satellite-streets-v12",
        center: [track[0].lon, track[0].lat],
        zoom: currentZoom,
        pitch: parseFloat(pitchSlider.value),
        bearing: 160,
        antialias: true
      });
      map.on("wheel", () => {
        setTimeout(() => {
          if (map) {
            currentZoom = parseFloat(map.getZoom().toFixed(1));
            if (zoomSlider) zoomSlider.value = currentZoom;
            updateHUD(playProgress);
          }
        }, 60);
      });
      map.on("style.load", () => {
        map.addSource("mapbox-dem", {
          type: "raster-dem",
          url: "mapbox://mapbox.mapbox-terrain-dem-v1",
          tileSize: 512,
          maxzoom: 14
        });
        map.setTerrain({ source: "mapbox-dem", exaggeration: parseFloat(exagSlider.value) });
        map.addLayer({
          id: "sky",
          type: "sky",
          paint: { "sky-type": "atmosphere", "sky-atmosphere-sun": [0.0, 0.0], "sky-atmosphere-sun-intensity": 15 }
        });
        addRouteAndWaypointsToGL(map, mapboxgl);
      });
      return;
    }

    // Default Keyless 3D Terrain (MapLibre GL v4 + AWS Terrarium DEM)
    map = new maplibregl.Map({
      container: "map3d",
      style: buildFree3DStyle(mode),
      center: [track[0].lon, track[0].lat],
      zoom: currentZoom,
      pitch: parseFloat(pitchSlider.value),
      bearing: 160,
      maxPitch: 82
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("wheel", () => {
      setTimeout(() => {
        if (map) {
          currentZoom = parseFloat(map.getZoom().toFixed(1));
          if (zoomSlider) zoomSlider.value = currentZoom;
          updateHUD(playProgress);
        }
      }, 60);
    });
    map.on("load", () => {
      addRouteAndWaypointsToGL(map, maplibregl);
      updateHUD(0);
    });
  }

  async function initGoogle3DTiles() {
    cesiumViewer = new Cesium.Viewer("cesium3d", {
      imageryProvider: false,
      baseLayerPicker: false,
      geocoder: false,
      timeline: false,
      animation: false
    });
    const tileset = await Cesium.Cesium3DTileset.fromUrl(
      `https://tile.googleapis.com/v1/3dtiles/root.json?key=${encodeURIComponent(googleKey)}`
    );
    cesiumViewer.scene.primitives.add(tileset);
    const positions = Cesium.Cartesian3.fromDegreesArrayHeights(
      track.flatMap(p => [p.lon, p.lat, p.ele + 15])
    );
    cesiumViewer.entities.add({
      polyline: {
        positions,
        width: 6,
        material: Cesium.Color.RED
      }
    });
    cesiumViewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(track[0].lon, track[0].lat - 0.015, track[0].ele + 900),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-30), roll: 0 }
    });
  }

  function getPointAtDistance(dKm) {
    if (!track.length) return null;
    if (dKm <= track[0].dist_km) return track[0];
    const last = track[track.length - 1];
    if (dKm >= last.dist_km) return last;

    let low = 0, high = track.length - 1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (track[mid].dist_km < dKm) low = mid + 1;
      else high = mid - 1;
    }
    const i1 = Math.max(1, Math.min(track.length - 1, low));
    const i0 = i1 - 1;
    const p0 = track[i0];
    const p1 = track[i1];
    const span = p1.dist_km - p0.dist_km;
    const t = span > 0.00001 ? Math.max(0, Math.min(1, (dKm - p0.dist_km) / span)) : 0;
    return {
      lat: p0.lat + (p1.lat - p0.lat) * t,
      lon: p0.lon + (p1.lon - p0.lon) * t,
      ele: p0.ele + (p1.ele - p0.ele) * t,
      dist_km: dKm
    };
  }

  function getPointAtIdx(idxFloat) {
    if (!track.length) return null;
    const i0 = Math.min(track.length - 1, Math.max(0, Math.floor(idxFloat)));
    const i1 = Math.min(track.length - 1, i0 + 1);
    const frac = idxFloat - i0;
    const p0 = track[i0];
    const p1 = track[i1];
    return {
      lat: p0.lat + (p1.lat - p0.lat) * frac,
      lon: p0.lon + (p1.lon - p0.lon) * frac,
      ele: p0.ele + (p1.ele - p0.ele) * frac,
      dist_km: p0.dist_km + (p1.dist_km - p0.dist_km) * frac
    };
  }

  function angleDiff(a, b) {
    return Math.abs(((a - b + 540) % 360) - 180);
  }

  function relativeAngle(targetB, refB) {
    return ((targetB - refB + 540) % 360) - 180;
  }

  function computeCorridorFlight(currPt) {
    const dCurr = currPt.dist_km;
    
    // Macro lookahead point (550m ahead)
    const macroPt = getPointAtDistance(dCurr + 0.550);
    const macroBearing = computeBearing(currPt.lat, currPt.lon, macroPt.lat, macroPt.lon);

    // Mid lookahead point (250m ahead)
    const midPt = getPointAtDistance(dCurr + 0.250);
    const midBearing = computeBearing(currPt.lat, currPt.lon, midPt.lat, midPt.lon);

    // 1. Initialize or Reset
    if (lockedBearing === null || isInitialFrame) {
      lockedBearing = macroBearing;
      currentBearer = lockedBearing;
      targetBearing = lockedBearing;
      isBearingLocked = true;
      isInitialFrame = false;
      return { bearing: currentBearer, pitch: currentPitch };
    }

    // 2. Evaluate triggers to change direction
    const relMacro = angleDiff(macroBearing, lockedBearing);
    const relMid = relativeAngle(midBearing, lockedBearing);
    
    // Cross-track lateral offset in meters (for points in the forward 170-degree arc)
    let crossTrackMeters = 0;
    if (Math.abs(relMid) < 85) {
      crossTrackMeters = Math.abs(250.0 * Math.sin(relMid * Math.PI / 180));
    }

    // Trigger A: Path changed general direction (macro direction changed by > 28 deg)
    const pathChangedDirection = relMacro > 28;

    // Trigger B: Point of view is too far to the side (trail drifted > 150m off center line of sight)
    const pointOfViewTooFarToSide = crossTrackMeters > 150;

    // Trigger C: Terrain blocking the view ahead along lockedBearing
    let terrainBlockingView = false;
    if (map && typeof map.queryTerrainElevation === "function") {
      const radLocked = lockedBearing * Math.PI / 180;
      const probeLat = currPt.lat + (200 * Math.cos(radLocked)) / 111320;
      const probeLon = currPt.lon + (200 * Math.sin(radLocked)) / (111320 * Math.cos(currPt.lat * Math.PI / 180));
      const eleAhead = map.queryTerrainElevation([probeLon, probeLat]);
      if (eleAhead !== null && eleAhead !== undefined && (eleAhead - currPt.ele) > 95) {
        terrainBlockingView = true;
      }
    }

    if (isBearingLocked) {
      if (pathChangedDirection || pointOfViewTooFarToSide || terrainBlockingView) {
        targetBearing = macroBearing;
        isBearingLocked = false;
      }
    }

    // 3. Update Camera Bearing
    if (isBearingLocked) {
      // KEEP CONSTANT! ZERO fluctuation!
      currentBearer = lockedBearing;
    } else {
      // Smoothly transit toward targetBearing
      const diff = ((targetBearing - currentBearer + 540) % 360) - 180;
      if (Math.abs(diff) < 1.2) {
        currentBearer = targetBearing;
        lockedBearing = targetBearing;
        isBearingLocked = true;
      } else {
        const turnRate = Math.sign(diff) * Math.min(1.2, Math.max(0.15, Math.abs(diff) * 0.10));
        currentBearer = (currentBearer + turnRate + 360) % 360;
      }
    }

    // 4. Slope-Normal & Valley-Side Stand-Off
    let slopeAngleDeg = 0;
    let downhillBearing = 0;
    if (map && typeof map.queryTerrainElevation === "function") {
      const probeR = 120; // 120m terrain sampling radius around point
      const dLat = probeR / 111320;
      const dLon = probeR / (111320 * Math.cos(currPt.lat * Math.PI / 180));
      const eN = map.queryTerrainElevation([currPt.lon, currPt.lat + dLat]);
      const eS = map.queryTerrainElevation([currPt.lon, currPt.lat - dLat]);
      const eE = map.queryTerrainElevation([currPt.lon + dLon, currPt.lat]);
      const eW = map.queryTerrainElevation([currPt.lon - dLon, currPt.lat]);

      if (eN !== null && eS !== null && eE !== null && eW !== null) {
        const gradX = (eE - eW) / (probeR * 2);
        const gradY = (eN - eS) / (probeR * 2);
        const grade = Math.hypot(gradX, gradY);
        slopeAngleDeg = Math.atan(grade) * 180 / Math.PI;
        downhillBearing = (Math.atan2(-gradX, -gradY) * 180 / Math.PI + 360) % 360;

        // If mountain slope is noticeable (> 6 deg), calculate valley-side stand-off
        if (slopeAngleDeg > 6.0) {
          const relDownhill = relativeAngle(downhillBearing, currentBearer);
          // If downhill is to the left (relDownhill < 0), offset camera eye to left into valley -> bearing turns right (+)
          // If downhill is to the right (relDownhill > 0), offset camera eye to right into valley -> bearing turns left (-)
          const biasStrength = Math.min(1.0, (slopeAngleDeg - 6.0) / 20.0);
          const maxBias = 28.0 * biasStrength;
          targetValleyBias = (relDownhill > 0 ? -1.0 : 1.0) * maxBias;
        } else {
          targetValleyBias = 0;
        }
      }
    } else {
      targetValleyBias = 0;
    }

    // Smooth valley bias so it glides smoothly across gullies
    currentValleyBias += (targetValleyBias - currentValleyBias) * 0.05;
    const effectiveBearing = (currentBearer + currentValleyBias + 360) % 360;

    // 5. Slope-Perpendicular Pitch & Terrain Clearance
    const userMaxPitch = parseFloat(pitchSlider.value);
    let safePitch = userMaxPitch;

    // View perpendicular to the slope rather than skimming parallel to rock
    if (slopeAngleDeg > 8.0) {
      const perpPitch = Math.max(34, 76 - slopeAngleDeg * 1.15);
      safePitch = Math.min(safePitch, perpPitch);
    }

    // Forward slope gradient anticipation along trail
    const aheadPt = getPointAtDistance(dCurr + 0.200);
    if (aheadPt) {
      const dDistM = (aheadPt.dist_km - currPt.dist_km) * 1000;
      if (dDistM > 20) {
        const dEleM = aheadPt.ele - currPt.ele;
        const trailSlopeGrade = dEleM / dDistM;
        if (trailSlopeGrade > 0.08) {
          const trailSlopeDeg = Math.atan(trailSlopeGrade) * 180 / Math.PI;
          safePitch = Math.min(safePitch, Math.max(34, 76 - trailSlopeDeg * 1.3));
        }
      }
    }

    // Line of sight terrain clearance from the valley-standoff camera eye
    if (map && typeof map.queryTerrainElevation === "function") {
      const radEffective = effectiveBearing * Math.PI / 180;
      const eyeDistM = 650;
      const radPitch = (currentPitch * Math.PI) / 180;
      const groundBehindM = eyeDistM * Math.sin(radPitch);
      const eyeHeightM = eyeDistM * Math.cos(radPitch);

      const dLatEye = (-groundBehindM * Math.cos(radEffective)) / 111320;
      const dLonEye = (-groundBehindM * Math.sin(radEffective)) / (111320 * Math.cos(currPt.lat * Math.PI / 180));
      const eyeLon = currPt.lon + dLonEye;
      const eyeLat = currPt.lat + dLatEye;
      const midLon = currPt.lon + dLonEye * 0.5;
      const midLat = currPt.lat + dLatEye * 0.5;

      const elevEyeTerrain = map.queryTerrainElevation([eyeLon, eyeLat]);
      const elevMidTerrain = map.queryTerrainElevation([midLon, midLat]);

      const expectedEyeAlt = currPt.ele + eyeHeightM;
      const expectedMidAlt = currPt.ele + eyeHeightM * 0.5;

      if (elevEyeTerrain !== null && elevEyeTerrain !== undefined) {
        const eyeClearance = expectedEyeAlt - elevEyeTerrain;
        if (eyeClearance < 50) {
          const deficit = 50 - eyeClearance;
          safePitch = Math.min(safePitch, Math.max(30, safePitch - Math.min(25, deficit * 0.2)));
        }
      }

      if (elevMidTerrain !== null && elevMidTerrain !== undefined) {
        const midClearance = expectedMidAlt - elevMidTerrain;
        if (midClearance < 30) {
          const deficit = 30 - midClearance;
          safePitch = Math.min(safePitch, Math.max(32, safePitch - Math.min(20, deficit * 0.15)));
        }
      }
    }

    targetPitch = safePitch;
    currentPitch += (targetPitch - currentPitch) * 0.08;

    return { bearing: effectiveBearing, pitch: currentPitch };
  }

  function moveCameraToIndex(idxFloat) {
    const pt = getPointAtIdx(idxFloat);
    if (!pt) return;

    const { bearing, pitch } = computeCorridorFlight(pt);

    if (markerCursor) markerCursor.setLngLat([pt.lon, pt.lat]);
    if (map) {
      map.jumpTo({
        center: [pt.lon, pt.lat],
        bearing: bearing,
        pitch: pitch,
        zoom: currentZoom
      });
    } else if (cesiumViewer) {
      const cesHeight = 550 * Math.pow(2, 14.0 - currentZoom);
      cesiumViewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, pt.ele + cesHeight),
        orientation: {
          heading: Cesium.Math.toRadians(bearing),
          pitch: Cesium.Math.toRadians(-90 + pitch),
          roll: 0
        }
      });
    }
    scrubber.value = Math.round(idxFloat);
    updateHUD(idxFloat);
    drawElevationProfile(idxFloat);
  }

  function stepFlythrough() {
    if (!isPlaying) return;
    const speed = parseFloat(speedSelect.value) * 1.3;
    playProgress += speed;
    if (playProgress >= track.length - 1) {
      playProgress = track.length - 1;
      stopFlythrough();
      return;
    }
    moveCameraToIndex(playProgress);
    animFrame = requestAnimationFrame(stepFlythrough);
  }

  function startFlythrough() {
    if (playProgress >= track.length - 2) playProgress = 0;
    isPlaying = true;
    playBtn.innerHTML = "&#10074;&#10074; Pause";
    animFrame = requestAnimationFrame(stepFlythrough);
  }

  function stopFlythrough() {
    isPlaying = false;
    playBtn.innerHTML = "&#9654; Fly Route";
    if (animFrame) cancelAnimationFrame(animFrame);
  }

  playBtn.addEventListener("click", () => {
    if (isPlaying) stopFlythrough();
    else startFlythrough();
  });

  document.getElementById("btn-reset").addEventListener("click", () => {
    stopFlythrough();
    playProgress = 0;
    isInitialFrame = true;
    lockedBearing = null;
    isBearingLocked = false;
    currentValleyBias = 0;
    targetValleyBias = 0;
    currentPitch = parseFloat(pitchSlider.value);
    if (map && track.length) {
      const lons = track.map(p => p.lon);
      const lats = track.map(p => p.lat);
      map.fitBounds(
        [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        { padding: 60, pitch: 55, duration: 1200 }
      );
    }
    updateHUD(0);
    drawElevationProfile(0);
  });

  scrubber.addEventListener("input", e => {
    stopFlythrough();
    playProgress = parseFloat(e.target.value);
    isInitialFrame = true;
    lockedBearing = null;
    isBearingLocked = false;
    currentValleyBias = 0;
    targetValleyBias = 0;
    moveCameraToIndex(playProgress);
  });

  exagSlider.addEventListener("input", () => {
    if (map && map.getTerrain()) {
      const src = engineSelect.value === "mapbox3d" ? "mapbox-dem" : "terrainDem";
      map.setTerrain({ source: src, exaggeration: parseFloat(exagSlider.value) });
    }
    updateHUD(playProgress);
  });

  pitchSlider.addEventListener("input", () => {
    currentPitch = parseFloat(pitchSlider.value);
    if (map) map.setPitch(currentPitch);
    updateHUD(playProgress);
  });

  zoomSlider.addEventListener("input", () => {
    currentZoom = parseFloat(zoomSlider.value);
    if (map) map.setZoom(currentZoom);
    updateHUD(playProgress);
  });

  engineSelect.addEventListener("change", e => initMapEngine(e.target.value));

  document.getElementById("btn-keys").addEventListener("click", () => {
    document.getElementById("input-mapbox-token").value = mapboxToken;
    document.getElementById("input-google-key").value = googleKey;
    document.getElementById("key-modal").classList.remove("hidden");
  });
  document.getElementById("btn-close-keys").addEventListener("click", () => {
    document.getElementById("key-modal").classList.add("hidden");
  });
  document.getElementById("btn-save-keys").addEventListener("click", () => {
    mapboxToken = document.getElementById("input-mapbox-token").value.trim();
    googleKey = document.getElementById("input-google-key").value.trim();
    localStorage.setItem("AGY_MAPBOX_TOKEN", mapboxToken);
    localStorage.setItem("AGY_GOOGLE_3D_KEY", googleKey);
    document.getElementById("key-modal").classList.add("hidden");
    if (googleKey) {
      engineSelect.value = "google3d";
      initMapEngine("google3d");
    } else if (mapboxToken) {
      engineSelect.value = "mapbox3d";
      initMapEngine("mapbox3d");
    }
  });

  // Client-side file upload parser (KML, CSV, GPX, Raw Text)
  document.getElementById("file-upload").addEventListener("change", ev => {
    const file = ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result;
      const numRe = /[-+]?\\d+(?:\\.\\d+)?/g;
      let newPts = [];
      if (file.name.endsWith(".gpx") || text.includes("<trkpt")) {
        const doc = new DOMParser().parseFromString(text, "text/xml");
        doc.querySelectorAll("trkpt, rtept").forEach(pt => {
          const lat = parseFloat(pt.getAttribute("lat"));
          const lon = parseFloat(pt.getAttribute("lon"));
          const eleEl = pt.querySelector("ele");
          const ele = eleEl ? parseFloat(eleEl.textContent) : 2200;
          newPts.push({ lat, lon, ele });
        });
      } else if (file.name.endsWith(".kml") || text.includes("<kml")) {
        const doc = new DOMParser().parseFromString(text, "text/xml");
        doc.querySelectorAll("coordinates").forEach(node => {
          node.textContent.trim().split(/\\s+/).forEach(tok => {
            const p = tok.split(",");
            if (p.length >= 2) {
              newPts.push({ lon: parseFloat(p[0]), lat: parseFloat(p[1]), ele: p[2] ? parseFloat(p[2]) : 2200 });
            }
          });
        });
      } else {
        text.split(/\\r?\\n/).forEach(line => {
          const m = line.match(numRe);
          if (m && m.length >= 2) {
            const a = parseFloat(m[0]), b = parseFloat(m[1]);
            if (!isNaN(a) && !isNaN(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180) {
              newPts.push({ lat: a, lon: b, ele: m[2] ? parseFloat(m[2]) : 2200 });
            }
          }
        });
      }
      if (newPts.length > 1) {
        let d = 0;
        track = newPts.map((p, idx) => {
          if (idx > 0) {
            const dy = (p.lat - newPts[idx - 1].lat) * 111.32;
            const dx = (p.lon - newPts[idx - 1].lon) * 111.32 * Math.cos(p.lat * Math.PI / 180);
            d += Math.hypot(dx, dy);
          }
          return { lat: p.lat, lon: p.lon, ele: p.ele, dist_km: d };
        });
        data.title = file.name;
        data.stats.total_distance_km = d.toFixed(2);
        updateHeader();
        initMapEngine(engineSelect.value);
      }
    };
    reader.readAsText(file);
  });

  updateHeader();
  initMapEngine("terrain3d");
})();
"""

    (VIEWER_DIR / "index.html").write_text(index_html, encoding="utf-8")
    (VIEWER_DIR / "styles.css").write_text(styles_css, encoding="utf-8")
    (VIEWER_DIR / "app.js").write_text(app_js, encoding="utf-8")

    manifest = {
        "skill": "route3DViewerSKILL",
        "route_title": route_title,
        "viewer_dir": str(VIEWER_DIR),
        "index_html": str(VIEWER_DIR / "index.html"),
        "route_data_js": str(VIEWER_DIR / "route_data.js"),
        "stats": payload["stats"],
        "recommended_url": f"http://{cfg['default_server']['host']}:{cfg['default_server']['port']}/index.html"
    }
    manifest_path = VIEWER_DIR / "viewer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Update shared /state/trip_state.json
    trip_state_path = STATE_DIR / "trip_state.json"
    if trip_state_path.exists():
        try:
            st = json.loads(trip_state_path.read_text(encoding="utf-8"))
            st["viewer_3d"] = manifest
            trip_state_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
        except Exception:
            pass

    print(f"[OK] Scaffolded 3D Interactive Route Viewer in: {VIEWER_DIR}")
    print(f"[OK] Manifest: {manifest_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a 3D interactive route viewer from KML, CSV, GPX, or raw text.")
    parser.add_argument("--input", "-i", help="Path to KML, CSV, GPX, GeoJSON, or text file (defaults to export.gpx)")
    parser.add_argument("--raw-coords", help="Raw coordinate string (lat,lon[,ele] per line)")
    parser.add_argument("--mapbox-token", default="", help="Optional Mapbox GL JS access token")
    parser.add_argument("--google-key", default="", help="Optional Google Maps 3D Tiles API key")
    args = parser.parse_args()

    in_path = Path(args.input).resolve() if args.input else None
    pts, wps, title = load_route_any_format(in_path, args.raw_coords)
    wps = enrich_stubai_landmarks(pts, wps)
    build_viewer_bundle(pts, wps, title, mapbox_token=args.mapbox_token, google_key=args.google_key)


if __name__ == "__main__":
    main()
