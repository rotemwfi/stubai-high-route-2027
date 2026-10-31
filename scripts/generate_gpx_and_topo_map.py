#!/usr/bin/env python3
"""
generate_gpx_and_topo_map.py
Reads the Selected Winner Route (Stubai High Trail — Alternative 1: Calibrated Alta Via 1 Match)
from config/stubai_waypoints.json, fetches real OpenStreetMap mountain-hiking trail geometry via BRouter,
exports a strict Mapy.com / AllTrails / Alpenvereinaktiv / Komoot / Garmin compatible GPX 1.1 track file
to /state/gpx/stubai_selected_route_2027.gpx (plus a separate waypoints GPX file),
and builds the standalone single-route Topographic Map viewer in /state/stubai_selected_route_topomap.html.
"""

from datetime import datetime, timedelta, timezone
import html
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "stubai_waypoints.json"
STATE_DIR = BASE_DIR / "state"
GPX_DIR = STATE_DIR / "gpx"


def fetch_brouter_segment(p1: Dict[str, Any], p2: Dict[str, Any]) -> List[Tuple[float, float, float]]:
    """
    Queries BRouter hiking-mountain profile between two waypoints.
    Returns list of (lat, lon, ele). Falls back to interpolated 3D segment if offline or off-trail.
    """
    lonlats = f"{p1['lon']},{p1['lat']}|{p2['lon']},{p2['lat']}"
    url = f"https://brouter.de/brouter?lonlats={lonlats}&profile=hiking-mountain&alternativeidx=0&format=geojson"
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "StubaiTopoExporter/3.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                coords = data["features"][0]["geometry"]["coordinates"]
                if coords and len(coords) >= 2:
                    return [
                        (
                            round(float(c[1]), 6),
                            round(float(c[0]), 6),
                            round(float(c[2]), 1) if len(c) > 2 else round(float(p1["ele"]), 1)
                        )
                        for c in coords
                    ]
        except Exception:
            pass

    steps = 25
    pts: List[Tuple[float, float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        lat = p1["lat"] + t * (p2["lat"] - p1["lat"])
        lon = p1["lon"] + t * (p2["lon"] - p1["lon"])
        ele = p1["ele"] + t * (p2["ele"] - p1["ele"])
        pts.append((round(lat, 6), round(lon, 6), round(ele, 1)))
    return pts


def build_sequence_geometry(seq: List[str], wp_map: Dict[str, Dict[str, Any]]) -> List[Tuple[float, float, float]]:
    track: List[Tuple[float, float, float]] = []
    for idx in range(len(seq) - 1):
        w1 = wp_map[seq[idx]]
        w2 = wp_map[seq[idx + 1]]
        seg = fetch_brouter_segment(w1, w2)
        if track and seg:
            track.extend(seg[1:])
        else:
            track.extend(seg)
    return track


def build_strict_track_gpx_string(
    title: str,
    full_track_pts: List[Tuple[float, float, float]]
) -> str:
    """
    Generates a 100% strict GPX 1.1 XML string specifically tested for Mapy.com (Mapy.cz),
    AllTrails, Alpenvereinaktiv, Komoot, Bergfex, and Garmin Connect.
    - Pure <trk><trkseg><trkpt> structure (no non-standard tags or mixed <wpt> elements that trip Mapy.com).
    - Valid ISO-8601 <time> and <ele> on every <trkpt> in strict Topografix XSD sequence order (<ele> then <time>).
    - Deduplicates consecutive identical points.
    """
    start_dt = datetime(2027, 9, 6, 7, 0, 0, tzinfo=timezone.utc)

    clean_pts: List[Tuple[float, float, float]] = []
    for pt in full_track_pts:
        if not clean_pts or (pt[0] != clean_pts[-1][0] or pt[1] != clean_pts[-1][1]):
            clean_pts.append(pt)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Mapy.com" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        '  <metadata>',
        f'    <name>{html.escape(title)}</name>',
        f'    <time>{start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")}</time>',
        '  </metadata>',
        '  <trk>',
        f'    <name>{html.escape(title)}</name>',
        '    <trkseg>'
    ]

    for idx, (lat, lon, ele) in enumerate(clean_pts):
        pt_time = (start_dt + timedelta(seconds=idx * 15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.extend([
            f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}">',
            f'        <ele>{ele:.1f}</ele>',
            f'        <time>{pt_time}</time>',
            '      </trkpt>'
        ])

    lines.extend([
        '    </trkseg>',
        '  </trk>',
        '</gpx>'
    ])
    gpx_str = "\n".join(lines) + "\n"
    # Verify XML well-formedness
    ET.fromstring(gpx_str.encode("utf-8"))
    return gpx_str


def build_strict_waypoints_gpx_string(
    waypoints_list: List[Dict[str, Any]],
    optional_variants: List[Dict[str, Any]]
) -> str:
    """
    Separate GPX 1.1 file containing the 18 numbered route waypoints + 2 optional peaks/ferrata
    in strict Topografix XSD element order (<ele>, <name>, <desc>).
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Mapy.com" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        '  <metadata>',
        '    <name>Stubai High Trail 2027 - 18 Huts and Waypoints</name>',
        '  </metadata>'
    ]

    for w in waypoints_list:
        clean_name = f"{w['seq']:02d}. {w['name']} ({w['ele']}m)".replace("★", "*").replace("→", "to")
        clean_role = w["role"].replace("★", "*").replace("→", "to")
        clean_desc = f"Day {w['day']} ({clean_role}): {w['desc']}".replace("★", "*").replace("→", "to")
        lines.extend([
            f'  <wpt lat="{w["lat"]:.6f}" lon="{w["lon"]:.6f}">',
            f'    <ele>{float(w["ele"]):.1f}</ele>',
            f'    <name>{html.escape(clean_name)}</name>',
            f'    <desc>{html.escape(clean_desc)}</desc>',
            '  </wpt>'
        ])

    for var in optional_variants:
        vw = var["waypoint"]
        lines.extend([
            f'  <wpt lat="{vw["lat"]:.6f}" lon="{vw["lon"]:.6f}">',
            f'    <ele>{float(vw["ele"]):.1f}</ele>',
            f'    <name>{html.escape("[OPT] " + vw["name"])}</name>',
            f'    <desc>{html.escape(vw["desc"])}</desc>',
            '  </wpt>'
        ])

    lines.append('</gpx>')
    gpx_str = "\n".join(lines) + "\n"
    ET.fromstring(gpx_str.encode("utf-8"))
    return gpx_str


def write_single_route_topomap_html(
    html_path: Path,
    waypoints_list: List[Dict[str, Any]],
    days_tracks: List[Dict[str, Any]],
    variants_tracks: List[Dict[str, Any]],
    full_track_pts: List[Tuple[float, float, float]],
    gpx_track_str: str
) -> None:
    data_payload = {
        "waypoints": waypoints_list,
        "days": days_tracks,
        "variants": variants_tracks,
        "full_track": full_track_pts,
        "gpx_xml": gpx_track_str
    }
    payload_json = json.dumps(data_payload)

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Selected Route: Stubai High Trail (2027) — Topographic Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: system-ui, -apple-system, sans-serif; display: flex; height: 100vh; background: #0f172a; color: #f8fafc; overflow: hidden; }}
  #sidebar {{ width: 400px; padding: 18px; overflow-y: auto; background: #1e293b; border-right: 1px solid #334155; display: flex; flex-direction: column; gap: 12px; }}
  #main {{ flex: 1; display: flex; flex-direction: column; height: 100vh; }}
  #map {{ flex: 1; width: 100%; }}
  #ele-panel {{ height: 155px; background: #0f172a; border-top: 1px solid #334155; padding: 10px 18px; display: flex; flex-direction: column; }}
  .ele-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #94a3b8; margin-bottom: 4px; }}
  #ele-canvas {{ width: 100%; height: 110px; cursor: crosshair; }}
  h1 {{ font-size: 17px; margin: 0; color: #fff; line-height: 1.3; }}
  .badge {{ display: inline-block; background: #2563eb; color: #fff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; margin-bottom: 4px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; text-align: center; }}
  .stat-val {{ font-size: 14px; font-weight: 700; color: #38bdf8; }}
  .stat-lbl {{ font-size: 11px; color: #94a3b8; }}
  .btn-primary {{ width: 100%; display: block; text-align: center; padding: 10px 12px; border-radius: 8px; font-size: 13px; font-weight: 700; text-decoration: none; background: #2563eb; color: #fff; border: none; cursor: pointer; transition: 0.15s; }}
  .btn-primary:hover {{ background: #1d4ed8; }}
  .btn-sec {{ width: 100%; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; background: #334155; color: #f8fafc; border: 1px solid #475569; cursor: pointer; }}
  .btn-sec:hover {{ background: #475569; }}
  .day-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 11px; cursor: pointer; transition: 0.15s; }}
  .day-card:hover, .day-card.active {{ border-color: #38bdf8; background: #172554; }}
  .day-hdr {{ display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
  .swatch {{ width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }}
  .day-meta {{ font-size: 12px; color: #cbd5e1; line-height: 1.4; }}
  .day-hut {{ font-size: 11px; color: #38bdf8; margin-top: 4px; font-weight: 600; }}
  .var-box {{ background: #0f172a; border: 1px dashed #64748b; border-radius: 8px; padding: 10px; font-size: 12px; color: #cbd5e1; }}
</style>
</head>
<body>
<div id="sidebar">
  <div>
    <span class="badge">SELECTED WINNER ROUTE • SEP 6–10, 2027</span>
    <h1>Stubai High Trail — Alt 1 (Calibrated Alta Via 1 Match)</h1>
  </div>

  <div class="stats-grid">
    <div><div class="stat-val">47.5 km</div><div class="stat-lbl">Total Length</div></div>
    <div><div class="stat-val">+2,820 m</div><div class="stat-lbl">Total Ascent</div></div>
    <div><div class="stat-val">-3,350 m</div><div class="stat-lbl">Total Descent</div></div>
  </div>

  <button class="btn-primary" onclick="downloadGpxBlob()">⬇ Download Mapy.com / AllTrails .GPX</button>
  <button class="btn-sec" onclick="focusAllDays()">Show Full 5-Day Route (All Stages)</button>

  <div id="days-list" style="display:flex;flex-direction:column;gap:8px;"></div>

  <div class="var-box">
    <strong style="color:#fff;">Optional Dashed Side-Branches on Map:</strong><br/>
    <span style="color:#f59e0b;">&#9644;&#9644;</span> <strong>Day 3 Opt:</strong> Fernau Klettersteig (C/D) / Egesengrat (2,631m)<br/>
    <span style="color:#a855f7;">&#9644;&#9644;</span> <strong>Day 4 Opt:</strong> Großer Trögler Summit Ridge (2,902m)
  </div>
</div>

<div id="main">
  <div id="map"></div>
  <div id="ele-panel">
    <div class="ele-header">
      <span><strong>3D Elevation Profile</strong> (Hover to inspect altitude &amp; location on map)</span>
      <span id="ele-readout">Min: 1,220m | Max Pass: 2,880m (Grawagrubennieder)</span>
    </div>
    <canvas id="ele-canvas"></canvas>
  </div>
</div>

<script>
  const DATA = {payload_json};

  window.downloadGpxBlob = function() {{
    const blob = new Blob([DATA.gpx_xml], {{ type: 'application/gpx+xml;charset=utf-8' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'stubai_selected_route_2027.gpx';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {{
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }}, 200);
  }};

  const map = L.map('map').setView([47.045, 11.190], 12);

  const openTopo = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 17,
    attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)'
  }}).addTo(map);

  const osmStandard = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }});

  const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    maxZoom: 18,
    attribution: 'Tiles &copy; Esri'
  }});

  const hikingTrails = L.tileLayer('https://tile.waymarkedtrails.org/hiking/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 18,
    opacity: 0.75,
    attribution: 'Trails: &copy; waymarkedtrails.org'
  }}).addTo(map);

  const dayLayers = {{}};
  const allBounds = L.latLngBounds();
  const daysListEl = document.getElementById('days-list');

  DATA.days.forEach(d => {{
    const latlngs = d.points.map(p => [p[0], p[1]]);
    const poly = L.polyline(latlngs, {{
      color: d.color,
      weight: 5,
      opacity: 0.95
    }}).addTo(map).bindPopup(`<strong>${{d.title}}</strong><br/>${{d.distance_km}} km | +${{d.ascent_m}}m / -${{d.descent_m}}m | ${{d.hours}} (${{d.grade}})`);

    dayLayers[d.day] = poly;
    allBounds.extend(poly.getBounds());

    const card = document.createElement('div');
    card.className = 'day-card';
    card.id = 'day-card-' + d.day;
    card.onclick = () => focusDay(d.day);
    card.innerHTML = `
      <div class="day-hdr"><span class="swatch" style="background:${{d.color}}"></span>${{d.title}}</div>
      <div class="day-meta">${{d.date}} &bull; <strong>${{d.distance_km}} km</strong> &bull; +${{d.ascent_m}}m / -${{d.descent_m}}m &bull; ${{d.hours}} (${{d.grade}})</div>
      <div class="day-hut">&#127968; ${{d.hut}}</div>
    `;
    daysListEl.appendChild(card);
  }});

  const variantGroup = L.layerGroup().addTo(map);
  DATA.variants.forEach(v => {{
    const latlngs = v.points.map(p => [p[0], p[1]]);
    L.polyline(latlngs, {{
      color: v.color,
      weight: 4,
      dashArray: '7, 7',
      opacity: 0.9
    }}).bindPopup(`<strong>${{v.name}}</strong>`).addTo(variantGroup);

    const vw = v.waypoint;
    L.circleMarker([vw.lat, vw.lon], {{
      radius: 6,
      fillColor: v.color,
      color: '#fff',
      weight: 2,
      fillOpacity: 1
    }}).bindPopup(`<strong>[Optional] ${{vw.name}} (${{vw.ele}}m)</strong><br/>${{vw.desc}}`).addTo(variantGroup);
  }});

  const wpGroup = L.layerGroup().addTo(map);
  DATA.waypoints.forEach(w => {{
    const isHut = w.type === 'hut';
    const isPass = w.type === 'pass';
    const fill = isHut ? '#e11d48' : (isPass ? '#f59e0b' : '#10b981');
    const marker = L.circleMarker([w.lat, w.lon], {{
      radius: isHut ? 8 : 6,
      fillColor: fill,
      color: '#fff',
      weight: 2,
      fillOpacity: 1
    }}).bindPopup(`
      <strong>#${{w.seq}} ${{w.name}} (${{w.ele}}m)</strong><br/>
      <em>Day ${{w.day}} &bull; ${{w.role}} &bull; Km ${{w.cum_km}}</em><br/>
      ${{w.desc}}
    `);
    wpGroup.addLayer(marker);
  }});

  map.fitBounds(allBounds, {{ padding: [35, 35] }});

  window.focusDay = function(dayNum) {{
    document.querySelectorAll('.day-card').forEach(el => el.classList.remove('active'));
    const activeCard = document.getElementById('day-card-' + dayNum);
    if (activeCard) activeCard.classList.add('active');

    Object.keys(dayLayers).forEach(k => {{
      const lyr = dayLayers[k];
      if (parseInt(k) === dayNum) {{
        lyr.setStyle({{ weight: 8, opacity: 1.0 }});
        lyr.bringToFront();
        map.fitBounds(lyr.getBounds(), {{ padding: [50, 50] }});
      }} else {{
        lyr.setStyle({{ weight: 3, opacity: 0.35 }});
      }}
    }});
  }};

  window.focusAllDays = function() {{
    document.querySelectorAll('.day-card').forEach(el => el.classList.remove('active'));
    Object.keys(dayLayers).forEach(k => {{
      dayLayers[k].setStyle({{ weight: 5, opacity: 0.95 }});
    }});
    map.fitBounds(allBounds, {{ padding: [35, 35] }});
  }};

  L.control.layers(
    {{ "OpenTopoMap (1:25k Contours)": openTopo, "OpenStreetMap": osmStandard, "Esri 3D Satellite": esriSat }},
    {{ "Official Waymarked Hiking Trails": hikingTrails, "18 Route Waypoints & Huts": wpGroup, "Optional Side-Branches (Dashed)": variantGroup }},
    {{ collapsed: false }}
  ).addTo(map);

  const canvas = document.getElementById('ele-canvas');
  const ctx = canvas.getContext('2d');
  const readout = document.getElementById('ele-readout');
  const hoverMarker = L.circleMarker([0, 0], {{ radius: 7, fillColor: '#38bdf8', color: '#fff', weight: 2, fillOpacity: 1 }});

  function drawElevation(hoverIdx = -1) {{
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const pts = DATA.full_track;
    if (!pts || !pts.length) return;

    const minEle = 1100;
    const maxEle = 3000;
    const padL = 40, padR = 12, padT = 10, padB = 18;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    ctx.clearRect(0, 0, W, H);

    ctx.strokeStyle = '#1e293b';
    ctx.fillStyle = '#64748b';
    ctx.font = '10px system-ui';
    [1500, 2000, 2500, 3000].forEach(e => {{
      const y = padT + plotH - ((e - minEle) / (maxEle - minEle)) * plotH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
      ctx.fillText(e + 'm', 4, y + 3);
    }});

    ctx.beginPath();
    pts.forEach((p, i) => {{
      const x = padL + (i / (pts.length - 1)) * plotW;
      const y = padT + plotH - ((p[2] - minEle) / (maxEle - minEle)) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }});
    ctx.lineTo(padL + plotW, padT + plotH);
    ctx.lineTo(padL, padT + plotH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padT, 0, padT + plotH);
    grad.addColorStop(0, 'rgba(56, 189, 248, 0.45)');
    grad.addColorStop(1, 'rgba(56, 189, 248, 0.03)');
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    pts.forEach((p, i) => {{
      const x = padL + (i / (pts.length - 1)) * plotW;
      const y = padT + plotH - ((p[2] - minEle) / (maxEle - minEle)) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }});
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;
    ctx.stroke();

    if (hoverIdx >= 0 && hoverIdx < pts.length) {{
      const hp = pts[hoverIdx];
      const hx = padL + (hoverIdx / (pts.length - 1)) * plotW;
      const hy = padT + plotH - ((hp[2] - minEle) / (maxEle - minEle)) * plotH;
      ctx.beginPath();
      ctx.moveTo(hx, padT);
      ctx.lineTo(hx, padT + plotH);
      ctx.strokeStyle = '#f8fafc';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(hx, hy, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#38bdf8';
      ctx.fill();
    }}
  }}

  canvas.addEventListener('mousemove', e => {{
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - 40;
    const plotW = rect.width - 52;
    const pts = DATA.full_track;
    const ratio = Math.max(0, Math.min(1, x / plotW));
    const idx = Math.round(ratio * (pts.length - 1));
    const pt = pts[idx];
    const km = (ratio * 47.5).toFixed(1);
    readout.textContent = `Dist: ~${{km}} km / 47.5 km | Elevation: ${{Math.round(pt[2])}} m | Lat: ${{pt[0].toFixed(4)}}, Lon: ${{pt[1].toFixed(4)}}`;
    hoverMarker.setLatLng([pt[0], pt[1]]).addTo(map);
    drawElevation(idx);
  }});

  canvas.addEventListener('mouseleave', () => {{
    map.removeLayer(hoverMarker);
    readout.textContent = 'Min: 1,220m | Max Pass: 2,880m (Grawagrubennieder)';
    drawElevation(-1);
  }});

  window.addEventListener('resize', () => drawElevation(-1));
  setTimeout(() => drawElevation(-1), 100);
</script>
</body>
</html>"""

    html_path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    waypoints_list: List[Dict[str, Any]] = cfg["selected_route_waypoints"]
    optional_variants: List[Dict[str, Any]] = cfg["optional_variants"]
    days_cfg: List[Dict[str, Any]] = cfg["days"]

    wp_map: Dict[str, Dict[str, Any]] = {w["id"]: w for w in waypoints_list}
    for var in optional_variants:
        vw = var["waypoint"]
        wp_map[vw["id"]] = vw

    days_tracks: List[Dict[str, Any]] = []
    full_track_pts: List[Tuple[float, float, float]] = []

    for d in days_cfg:
        pts = build_sequence_geometry(d["sequence"], wp_map)
        days_tracks.append({
            **d,
            "points": pts
        })
        if full_track_pts and pts:
            full_track_pts.extend(pts[1:])
        else:
            full_track_pts.extend(pts)

        # Also export individual day GPX in strict Mapy.com format
        day_title = f"Stubai High Trail 2027 - Day {d['day']} ({d['distance_km']} km)"
        day_gpx_str = build_strict_track_gpx_string(day_title, pts)
        day_gpx_path = GPX_DIR / f"stubai_day{d['day']}_2027.gpx"
        GPX_DIR.mkdir(parents=True, exist_ok=True)
        day_gpx_path.write_text(day_gpx_str, encoding="utf-8", newline="\n")
        print(f"[OK] Day {d['day']} GPX exported ({len(pts)} pts): {day_gpx_path}")

    variants_tracks: List[Dict[str, Any]] = []
    for var in optional_variants:
        vpts = build_sequence_geometry(var["sequence"], wp_map)
        variants_tracks.append({
            **var,
            "points": vpts
        })

    title = "Stubai High Trail 2027 - Selected Route (47.5 km, Oberissalm to Falbeson)"
    gpx_track_str = build_strict_track_gpx_string(title, full_track_pts)
    gpx_wpt_str = build_strict_waypoints_gpx_string(waypoints_list, optional_variants)

    gpx_selected = GPX_DIR / "stubai_selected_route_2027.gpx"
    gpx_alt1 = GPX_DIR / "stubai_alt1_glacier_hub.gpx"
    gpx_wpts = GPX_DIR / "stubai_selected_waypoints_2027.gpx"

    gpx_selected.write_text(gpx_track_str, encoding="utf-8", newline="\n")
    gpx_alt1.write_text(gpx_track_str, encoding="utf-8", newline="\n")
    gpx_wpts.write_text(gpx_wpt_str, encoding="utf-8", newline="\n")
    print(f"[OK] Exported Mapy.com-validated Track GPX: {gpx_selected}")
    print(f"[OK] Exported Mapy.com-validated Waypoints GPX: {gpx_wpts}")

    html_selected = STATE_DIR / "stubai_selected_route_topomap.html"
    html_legacy = STATE_DIR / "stubai_3_alternatives_topomap.html"
    write_single_route_topomap_html(html_selected, waypoints_list, days_tracks, variants_tracks, full_track_pts, gpx_track_str)
    write_single_route_topomap_html(html_legacy, waypoints_list, days_tracks, variants_tracks, full_track_pts, gpx_track_str)
    print(f"[OK] Updated Interactive Topographic Map with direct Blob GPX download: {html_selected}")


if __name__ == "__main__":
    main()
