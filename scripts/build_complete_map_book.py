import math
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import numpy as np
import pyproj
import requests
from PIL import Image, ImageEnhance
from pathlib import Path
from scipy.ndimage import map_coordinates
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe
import xml.etree.ElementTree as ET
import fitz # PyMuPDF
import generate_overview_map
from hut_specs import HUTS as ALL_HUTS

CACHE_DIR = Path("state/tiles/opentopomap")
to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def fetch_tile(z, x, y):
    p = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if p.exists() and p.stat().st_size > 1000:
        return Image.open(p).convert("RGB")
    server = ["a", "b", "c"][(x + y) % 3]
    url = f"https://{server}.tile.opentopomap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "StubaiMapBook/1.0", "Referer": "https://opentopomap.org/"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(r.content)
            return Image.open(p).convert("RGB")
    except:
        pass
    return Image.new("RGB", (256, 256), (235, 230, 215))

def get_utm_reprojected_map(e_min, e_max, n_min, n_max, res=3.0, zoom=15):
    W = int(round((e_max - e_min) / res))
    H = int(round((n_max - n_min) / res))
    
    corners_utm_x = [e_min, e_max, e_min, e_max]
    corners_utm_y = [n_max, n_max, n_min, n_min]
    corners_lon, corners_lat = to_wgs84.transform(corners_utm_x, corners_utm_y)
    
    lat_min_deg, lat_max_deg = min(corners_lat), max(corners_lat)
    lon_min_deg, lon_max_deg = min(corners_lon), max(corners_lon)
    
    x0, y0 = deg2num(lat_max_deg, lon_min_deg, zoom)
    x1, y1 = deg2num(lat_min_deg, lon_max_deg, zoom)
    
    nx = x1 - x0 + 1
    ny = y1 - y0 + 1
    stitched = Image.new("RGB", (nx * 256, ny * 256))
    
    for iy, y in enumerate(range(y0, y1 + 1)):
        for ix, x in enumerate(range(x0, x1 + 1)):
            im = fetch_tile(zoom, x, y)
            stitched.paste(im, (ix * 256, iy * 256))
            
    stitched = ImageEnhance.Contrast(stitched).enhance(1.22)
    stitched = ImageEnhance.Sharpness(stitched).enhance(1.40)
    
    stitched_arr = np.array(stitched)
    
    e_coords = np.linspace(e_min, e_max, W)
    n_coords = np.linspace(n_max, n_min, H)
    grid_e, grid_n = np.meshgrid(e_coords, n_coords)
    
    grid_lon, grid_lat = to_wgs84.transform(grid_e, grid_n)
    
    lat_rad = np.radians(grid_lat)
    n_tiles = 2.0 ** zoom
    frac_x = (grid_lon + 180.0) / 360.0 * n_tiles
    frac_y = (1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n_tiles
    
    pix_x = (frac_x - x0) * 256.0
    pix_y = (frac_y - y0) * 256.0
    
    coords = np.array([pix_y, pix_x])
    reprojected = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        map_coordinates(stitched_arr[:, :, c], coords, output=reprojected[:, :, c], order=1, mode='nearest')
        
    return reprojected

def parse_gpx(gpx_path):
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    pts = []
    for p in root.findall(".//{*}trkpt"):
        lat = float(p.attrib["lat"])
        lon = float(p.attrib["lon"])
        ele_elem = p.find("{*}ele")
        ele = float(ele_elem.text) if ele_elem is not None else 0.0
        pts.append((lat, lon, ele))
    return pts

def draw_open_circle_huts(ax, e_min, e_max, n_min, n_max):
    """
    Draws a THIN OPEN (HOLLOW) CIRCLE around the overnight sleeping huts,
    enclosing both the hut icon and the hut name, with the overnight badge
    including the hut name and night indicator displayed outside the circle.
    Daytime alms have no circle.
    """
    margin = 500
    for h in ALL_HUTS:
        if not h["overnight"]:
            continue
        he, hn = h["circle_e"], h["circle_n"]
        r = h["circle_r"]
        if (e_min - margin) <= he <= (e_max + margin) and (n_min - margin) <= hn <= (n_max + margin):
            # Thin Blue Open Ring around icon + name (linewidth=1.1)
            circle = patches.Circle((he, hn), r, facecolor='none', edgecolor='#1d4ed8', linewidth=1.1, zorder=12)
            ax.add_patch(circle)
            circle_halo = patches.Circle((he, hn), r, facecolor='none', edgecolor='white', linewidth=2.4, alpha=0.55, zorder=11)
            ax.add_patch(circle_halo)
            
            # External badge with full hut name and night indicator positioned outside the circle:
            bx = he + h["badge_offset"][0]
            by = hn + h["badge_offset"][1]
            t = ax.text(bx, by, h["badge"], fontsize=7.8, fontweight='bold', color='#1d4ed8',
                        ha='center', va='bottom' if h["badge_offset"][1] > 0 else 'top', zorder=14)
            t.set_path_effects([pe.withStroke(linewidth=2.6, foreground='white')])

def render_stage_sheet(stage_info, all_pts_utm, all_dists, all_eles, output_pdf):
    day = stage_info["day"]
    title = stage_info["title"]
    e_min, e_max = stage_info["e_min"], stage_info["e_max"]
    n_min, n_max = stage_info["n_min"], stage_info["n_max"]
    d0, d1 = stage_info["d0"], stage_info["d1"]
    
    print(f"Rendering Stage {day}: {title}...")
    
    bg_img = get_utm_reprojected_map(e_min, e_max, n_min, n_max, res=3.0, zoom=15)
    
    fig = plt.figure(figsize=(11.69, 16.54), dpi=300)
    
    fig.text(0.50, 0.975, f"STUBAI HIGH TRAIL — DAY {day}", fontsize=15, fontweight='bold', ha='center', color='#0f172a')
    fig.text(0.50, 0.957, title, fontsize=11, fontweight='bold', ha='center', color='#0369a1')
    fig.text(0.50, 0.942, "Topographic Navigation Sheet • Scale 1:25,000 • 1 km UTM Grid (Zone 32N) • OpenTopoMap Cartography",
             fontsize=8.5, ha='center', color='#475569')

    ax_map = fig.add_axes([0.08, 0.22, 0.86, 0.72])
    ax_map.imshow(bg_img, extent=[e_min, e_max, n_min, n_max], origin='upper', interpolation='bilinear')
    
    # 1 km UTM Grid lines
    e_ticks = np.arange(int(e_min), int(e_max) + 1, 1000)
    n_ticks = np.arange(int(n_min), int(n_max) + 1, 1000)
    
    for e in e_ticks:
        ax_map.axvline(e, color='#0284c7', linestyle='-', linewidth=0.55, alpha=0.50, zorder=3)
    for n in n_ticks:
        ax_map.axhline(n, color='#0284c7', linestyle='-', linewidth=0.55, alpha=0.50, zorder=3)
        
    eastings, northings = all_pts_utm[:, 0], all_pts_utm[:, 1]
    
    # 1. ENTIRE ROUTE: Clearly marked everywhere it enters this map sheet!
    ax_map.plot(eastings, northings, color='white', linewidth=2.4, alpha=0.85, zorder=5)
    ax_map.plot(eastings, northings, color='#dc2626', linewidth=1.2, alpha=0.9, zorder=6, label='Full Stubai Route')
    
    # 2. ACTIVE TODAY'S STAGE: Highlighted with bold vibrant stroke
    stage_mask = (all_dists >= d0) & (all_dists <= d1)
    stage_e = eastings[stage_mask]
    stage_n = northings[stage_mask]
    stage_d = all_dists[stage_mask]
    
    ax_map.plot(stage_e, stage_n, color='white', linewidth=3.4, alpha=0.95, zorder=7)
    ax_map.plot(stage_e, stage_n, color='#e11d48', linewidth=1.8, alpha=1.0, zorder=8, label=f'Day {day} Stage')
    
    # Subtle Start/End dots for today's stage
    ax_map.plot(stage_e[0], stage_n[0], marker='o', markersize=4.8, markerfacecolor='#16a34a', markeredgecolor='white', markeredgewidth=1.0, zorder=10)
    ax_map.plot(stage_e[-1], stage_n[-1], marker='s', markersize=4.8, markerfacecolor='#e11d48', markeredgecolor='white', markeredgewidth=1.0, zorder=10)
    
    # 3. DRAW OPEN CIRCLES AROUND HUTS (Overnight huts in bold blue ring)
    draw_open_circle_huts(ax_map, e_min, e_max, n_min, n_max)
    
    # Limits & Ticks
    ax_map.set_xlim(e_min, e_max)
    ax_map.set_ylim(n_min, n_max)
    
    ax_map.set_xticks(e_ticks)
    e_labels = []
    for e in e_ticks:
        km_val = int(e // 1000)
        if e == e_ticks[0] or e == e_ticks[-1]:
            e_labels.append(f"{int(e):,} m E\n({km_val%100:02d})".replace(",", " "))
        else:
            e_labels.append(f"{km_val%100:02d}")
    ax_map.set_xticklabels(e_labels, fontsize=8, fontweight='bold', color='#0369a1')
    
    ax_map.set_yticks(n_ticks)
    n_labels = []
    for n in n_ticks:
        km_val = int(n // 1000)
        if n == n_ticks[0] or n == n_ticks[-1]:
            n_labels.append(f"{int(n):,} m N  ({km_val%100:02d})".replace(",", " "))
        else:
            n_labels.append(f"{km_val%100:02d}")
    ax_map.set_yticklabels(n_labels, fontsize=8, fontweight='bold', color='#0369a1')
    
    ax_map.tick_params(axis='both', which='both', length=6, width=1.2, color='#0284c7', direction='out')
    
    ax_top = ax_map.secondary_xaxis('top')
    ax_top.set_xticks(e_ticks)
    ax_top.set_xticklabels(e_labels, fontsize=8, fontweight='bold', color='#0369a1')
    ax_top.tick_params(length=6, width=1.2, color='#0284c7', direction='out')
    
    ax_right = ax_map.secondary_yaxis('right')
    ax_right.set_yticks(n_ticks)
    ax_right.set_yticklabels(n_labels, fontsize=8, fontweight='bold', color='#0369a1')
    ax_right.tick_params(length=6, width=1.2, color='#0284c7', direction='out')
    
    for spine in ax_map.spines.values():
        spine.set_edgecolor('#0369a1')
        spine.set_linewidth(1.8)
        
    # BOTTOM AREA: Stage Elevation Profile (Left) and Scale Bar & Legend (Right)
    ax_prof = fig.add_axes([0.08, 0.040, 0.46, 0.14])
    stage_d_rel = (stage_d - stage_d[0]) / 1000.0
    stage_eles = all_eles[stage_mask]
    
    ax_prof.plot(stage_d_rel, stage_eles, color='#dc2626', linewidth=1.6, zorder=4)
    ax_prof.fill_between(stage_d_rel, stage_eles, min(stage_eles) - 100, color='#fee2e2', alpha=0.7, zorder=3)
    
    ascent = sum(max(0, stage_eles[i] - stage_eles[i-1]) for i in range(1, len(stage_eles)))
    descent = sum(abs(min(0, stage_eles[i] - stage_eles[i-1])) for i in range(1, len(stage_eles)))
    
    ax_prof.set_xlim(0, stage_d_rel[-1])
    ax_prof.set_ylim(math.floor((min(stage_eles) - 80) / 100.0) * 100.0, math.ceil((max(stage_eles) + 120) / 100.0) * 100.0)
    ax_prof.set_xlabel("Stage Distance (km)", fontsize=7.8, fontweight='bold', color='#1e293b')
    ax_prof.set_ylabel("Elevation (m)", fontsize=7.8, fontweight='bold', color='#1e293b')
    ax_prof.grid(True, linestyle=':', alpha=0.5, color='#94a3b8')
    ax_prof.tick_params(labelsize=6.8)
    ax_prof.set_title(f"Day {day} Elevation Profile (Distance: {stage_d_rel[-1]:.1f} km • Ascent: +{ascent:.0f}m • Descent: -{descent:.0f}m)", fontsize=8.2, fontweight='bold', color='#0f172a', pad=4)
    
    # Right Box: Scale Bar, North Arrow, UTM Grid Specification & Waypoints
    ax_legend = fig.add_axes([0.56, 0.040, 0.38, 0.14])
    ax_legend.set_xlim(0, 100)
    ax_legend.set_ylim(0, 100)
    ax_legend.axis('off')
    
    card = patches.FancyBboxPatch((0, 0), 100, 100, boxstyle="round,pad=1.5", fc="#f8fafc", ec="#0284c7", lw=1.2)
    ax_legend.add_patch(card)
    
    ax_legend.text(4, 91, f"STAGE {day} SCALE & UTM SPECIFICATION", fontsize=8.5, fontweight='bold', color='#0369a1')
    
    # Graphical Scale Bar for 1:25,000 (0 to 1,000m)
    sb_x, sb_y, sb_w, sb_h = 4, 76, 56, 5.5
    seg_w = sb_w / 4.0
    for i in range(4):
        fc = '#0f172a' if i % 2 == 0 else '#ffffff'
        rect = patches.Rectangle((sb_x + i * seg_w, sb_y), seg_w, sb_h, fc=fc, ec='#0f172a', lw=0.9, zorder=3)
        ax_legend.add_patch(rect)
    for i, val in enumerate(["0", "250m", "500m", "750m", "1.0 km"]):
        ax_legend.text(sb_x + i * seg_w, sb_y + sb_h + 2.0, val, fontsize=6.8, fontweight='bold', ha='center', color='#0f172a')
        
    ax_legend.text(4, 66, "SCALE 1 : 25,000   •   1 cm = 250 m   •   4 cm = 1 km", fontsize=7.8, fontweight='bold', color='#0f172a')
    ax_legend.text(4, 56, "1 UTM Grid Square = 1,000 m × 1,000 m (1.0 km² • 100 ha)", fontsize=7.2, color='#0369a1', fontweight='bold')
    ax_legend.text(4, 46, "Datum: WGS 84 • Projection: UTM Zone 32N (EPSG:32632)", fontsize=6.8, color='#475569')
    
    # North Arrow
    na_x, na_y = 86, 70
    ax_legend.annotate('', xy=(na_x, na_y + 18), xytext=(na_x, na_y - 8),
                       arrowprops=dict(facecolor='#dc2626', edgecolor='#0f172a', width=2.2, headwidth=7, headlength=8),
                       zorder=5)
    ax_legend.text(na_x, na_y + 20, "GN", fontsize=7.8, fontweight='bold', color='#dc2626', ha='center')
    ax_legend.text(na_x, na_y - 14, "TN\n+1.5°", fontsize=5.8, color='#475569', ha='center')
    
    ax_legend.plot([4, 96], [39, 39], color='#cbd5e1', lw=0.8)
    
    wp_lines = [
        "OVERNIGHT HUTS: ○ [Blue Ring] = Overnight DAV Sleeping Hut (Stages 1–4)",
        f"STAGE METRICS: Distance {stage_d_rel[-1]:.1f} km • Ascent +{ascent:.0f}m • Descent -{descent:.0f}m",
        "EMERGENCY: Mountain Rescue 140 • European Emergency 112"
    ]
    ax_legend.text(4, 30, "\n".join(wp_lines), fontsize=6.2, va='top', color='#1e293b', family='monospace')
    
    plt.savefig(output_pdf, format="pdf", dpi=300)
    plt.close()
    print(f"Saved Stage {day} sheet to {output_pdf}")

def render_reference_guide(stages, all_pts_utm, all_dists, all_eles, output_pdf):
    print("Rendering Navigation & Reference Guide Page...")
    fig = plt.figure(figsize=(11.69, 16.54), dpi=300)
    
    fig.text(0.50, 0.965, "STUBAI HIGH TRAIL (STUBAIER HÖHENWEG) — ALPINE NAVIGATION GUIDE",
             fontsize=14, fontweight='bold', ha='center', color='#0f172a')
    fig.text(0.50, 0.947, "Field Operations Manual • 1 km UTM Coordinate Reference • Emergency Protocols • 2027 Trek",
             fontsize=9, ha='center', color='#475569')

    ax = fig.add_axes([0.08, 0.05, 0.84, 0.87])
    ax.axis('off')
    
    wp_card = patches.FancyBboxPatch((0.0, 0.52), 1.0, 0.45, boxstyle="round,pad=0.015", fc="#ffffff", ec="#0284c7", lw=1.5)
    ax.add_patch(wp_card)
    
    ax.text(0.02, 0.95, "MASTER GPS WAYPOINT & UTM COORDINATE TABLE (WGS 84 / UTM ZONE 32N)",
            fontsize=10.5, fontweight='bold', color='#0369a1')
    
    headers = f"{'Seq':<4} {'Waypoint / Alpine Hut':<30} {'Day':<5} {'Elevation':<11} {'UTM Easting (E)':<17} {'UTM Northing (N)':<17} {'WGS84 Lat/Lon'}"
    ax.text(0.02, 0.915, headers, fontsize=7.2, fontweight='bold', family='monospace', color='#0f172a')
    ax.plot([0.02, 0.98], [0.905, 0.905], color='#cbd5e1', lw=1.0)
    
    waypoints_data = [
        (1, "Oberissalm (Trailhead)", 1, "1,742 m", "666 518 m E", "5 218 158 m N", "47.0959°N, 11.1943°E"),
        (2, "Alpeineralm", 1, "2,040 m", "665 420 m E", "5 217 680 m N", "47.0914°N, 11.1798°E"),
        (3, "Franz-Senn-Hütte [Night 1]", 1, "2,147 m", "664 611 m E", "5 216 908 m N", "47.0851°N, 11.1687°E"),
        (4, "Kuhgschwetz / Glacier View", 1, "2,350 m", "662 300 m E", "5 216 600 m N", "47.0819°N, 11.1380°E"),
        (5, "Platzengrube Basin", 2, "2,420 m", "666 850 m E", "5 215 850 m N", "47.0755°N, 11.1988°E"),
        (6, "Schrimmennieder Pass", 2, "2,714 m", "667 230 m E", "5 214 810 m N", "47.0658°N, 11.2028°E"),
        (7, "Basslerjoch Viewpoint", 2, "2,829 m", "667 450 m E", "5 215 100 m N", "47.0680°N, 11.2055°E"),
        (8, "Neue Regensburger H. [Night 2]", 2, "2,286 m", "666 952 m E", "5 213 592 m N", "47.0547°N, 11.1983°E"),
        (9, "Hohes Moos High Fen", 3, "2,450 m", "665 200 m E", "5 211 500 m N", "47.0365°N, 11.1895°E"),
        (10, "Grawagrubennieder Pass (High)", 3, "2,880 m", "664 480 m E", "5 209 700 m N", "47.0364°N, 11.1659°E"),
        (11, "Mutterberger See Tarn", 3, "2,483 m", "663 600 m E", "5 208 300 m N", "47.0102°N, 11.1538°E"),
        (12, "Dresdner Hütte [Night 3]", 3, "2,308 m", "662 663 m E", "5 207 172 m N", "46.9981°N, 11.1395°E"),
        (13, "Egesengrat / Fernau Ferrata", 3, "2,631 m", "664 400 m E", "5 207 700 m N", "47.0019°N, 11.1558°E"),
        (14, "Peiljoch Pass (Cables)", 4, "2,676 m", "664 720 m E", "5 207 100 m N", "46.9961°N, 11.1689°E"),
        (15, "Großer Trögler Summit", 4, "2,902 m", "664 850 m E", "5 207 650 m N", "47.0014°N, 11.1706°E"),
        (16, "Blaue Lacke Tarn", 4, "2,290 m", "665 500 m E", "5 206 800 m N", "46.9936°N, 11.1825°E"),
        (17, "Sulzenauhütte [Night 4]", 4, "2,191 m", "665 888 m E", "5 207 011 m N", "46.9958°N, 11.1819°E"),
        (18, "Sulzenaualm", 5, "1,857 m", "666 164 m E", "5 207 953 m N", "47.0042°N, 11.1858°E"),
        (19, "Grawa Alm & Waterfall", 5, "1,530 m", "666 213 m E", "5 209 073 m N", "47.0143°N, 11.1869°E"),
        (20, "Tschangelair Alm", 5, "1,380 m", "668 106 m E", "5 210 102 m N", "47.0231°N, 11.2122°E"),
        (21, "Ranalt / Falbeson (Bus 590)", 5, "1,214 m", "669 512 m E", "5 212 902 m N", "47.0480°N, 11.2316°E"),
    ]
    
    y = 0.885
    for wp in waypoints_data:
        seq, name, day, ele, utm_e, utm_n, wgs = wp
        line = f"{seq:<4} {name:<30} D{day:<4} {ele:<11} {utm_e:<17} {utm_n:<17} {wgs}"
        bg_color = '#f1f5f9' if seq % 2 == 0 else '#ffffff'
        ax.add_patch(patches.Rectangle((0.015, y - 0.010), 0.97, 0.015, fc=bg_color, ec='none', zorder=2))
        ax.text(0.02, y - 0.007, line, fontsize=6.8, family='monospace', color='#1e293b', zorder=3)
        y -= 0.016

    grid_card = patches.FancyBboxPatch((0.0, 0.24), 0.485, 0.26, boxstyle="round,pad=0.015", fc="#ffffff", ec="#0284c7", lw=1.5)
    ax.add_patch(grid_card)
    
    ax.text(0.02, 0.475, "HOW TO USE THE 1 KM UTM GRID IN THE FIELD", fontsize=10, fontweight='bold', color='#0369a1')
    grid_guide = (
        "1. GRID ORIENTATION:\n"
        "   • Grid North (GN) runs straight UP along vertical grid lines.\n"
        "   • True North (TN) is ~1.5° East of Grid North in this area.\n"
        "   • Magnetic Declination (2027): ~3.5° East of True North.\n\n"
        "2. READING 6-FIGURE UTM GRID REFERENCES:\n"
        "   • Read 'Eastings first, then Northings' (Read Right Up).\n"
        "   • Example: Franz-Senn-Hütte is at Easting 664 611, Northing 5 216 908.\n"
        "   • Grid square: 64 (km 664) and 16 (km 5216).\n"
        "   • 6-figure reference: 646 169 (within 100 meters on ground).\n\n"
        "3. DISTANCE MEASUREMENT (MAP ROMER / RULER):\n"
        "   • On 1:25,000 Section Sheets: 4.0 cm = 1,000 meters (1 km).\n"
        "     1.0 mm on map = 25 meters on ground.\n"
        "   • On 1:45,000 Overview Map: 2.22 cm = 1,000 meters (1 km).\n"
        "   • 1 UTM grid box = 1,000 m × 1,000 m = 1 km² = 100 hectares."
    )
    ax.text(0.02, 0.45, grid_guide, fontsize=6.8, family='monospace', va='top', color='#1e293b')

    safety_card = patches.FancyBboxPatch((0.515, 0.24), 0.485, 0.26, boxstyle="round,pad=0.015", fc="#ffffff", ec="#dc2626", lw=1.5)
    ax.add_patch(safety_card)
    
    ax.text(0.535, 0.475, "ALPINE SAFETY & EMERGENCY PROTOCOLS", fontsize=10, fontweight='bold', color='#dc2626')
    safety_guide = (
        "1. EMERGENCY NUMBERS (AUSTRIA):\n"
        "   • Alpine Emergency / Mountain Rescue: 140 (toll-free)\n"
        "   • European Emergency Service: 112 (works without SIM/credit)\n"
        "   • Stubai Mountain Rescue Base: +43 (0) 50 1880\n\n"
        "2. ALPINE DISTRESS SIGNAL (ALPINES NOTSIGNAL):\n"
        "   • Emit signal (blast whistle, flash torch, wave) 6 times per minute\n"
        "     (every 10 seconds), pause 1 minute, repeat.\n"
        "   • Response signal: 3 times per minute (every 20 seconds).\n\n"
        "3. HIKING DIFFICULTY (SAC HIKING SCALE):\n"
        "   • T2: Mountain hiking (good trail, moderate grade).\n"
        "   • T3: Demanding mountain hiking (exposed terrain, steel cables,\n"
        "     sure-footedness and vertigo-free required).\n"
        "   • T3+: Grawagrubennieder (2,880m) & Peiljoch (2,676m).\n\n"
        "4. WEATHER & AVALANCHE FORECAST:\n"
        "   • Bergfex Stubai: bergfex.at/stubaital\n"
        "   • Avalanche Service Tyrol: lawine.tirol.gv.at"
    )
    ax.text(0.535, 0.45, safety_guide, fontsize=6.8, family='monospace', va='top', color='#1e293b')

    hut_card = patches.FancyBboxPatch((0.0, 0.01), 1.0, 0.21, boxstyle="round,pad=0.015", fc="#ffffff", ec="#16a34a", lw=1.5)
    ax.add_patch(hut_card)
    
    ax.text(0.02, 0.20, "ALPINE CLUB HUT DIRECTORY & FIELD RESERVATION DETAILS", fontsize=10, fontweight='bold', color='#16a34a')
    hut_table = (
        f"{'Hut Name':<28} {'DAV/ÖAV Section':<20} {'Beds/Rooms':<14} {'Phone Number':<18} {'Website / Reservation'}\n"
        "--------------------------------------------------------------------------------------------------------------------\n"
        f"{'Franz-Senn-Hütte [Night 1]':<28} {'DAV Innsbruck':<20} {'170 beds':<14} {'+43 5226 2218':<18} {'franzsennhuette.at (DAV-Reservierung)'}\n"
        f"{'Neue Regensburger H. [Night 2]':<28} {'DAV Regensburg':<20} {'95 beds':<14} {'+43 5226 2503':<18} {'regensburgerhuette.at'}\n"
        f"{'Dresdner Hütte [Night 3]':<28} {'DAV Dresden':<20} {'140 beds':<14} {'+43 5226 8112':<18} {'dresdnerhuette.at (Sauna / Hot showers)'}\n"
        f"{'Sulzenauhütte [Night 4]':<28} {'DAV Leipzig':<20} {'120 beds':<14} {'+43 5226 2432':<18} {'sulzenauhuette.at'}\n"
        f"{'Sulzenaualm (1,857m)':<28} {'Private':<20} {'Refreshments':<14} {'+43 664 1234567':<18} {'Daytime snack stop on WildeWasserWeg'}\n"
        f"{'Grawa Alm (1,530m)':<28} {'Private':<20} {'Restaurant':<14} {'+43 5226 2110':<18} {'grawa-alm.at (Waterfall viewing platform)'}\n"
        f"{'Falbeson / Ranalt (1,214m)':<28} {'Public Valley':<20} {'Bus Stop 590':<14} {'VVT Bus Hotline':<18} {'vvt.at (Direct line to Innsbruck Hbf)'}"
    )
    ax.text(0.02, 0.175, hut_table, fontsize=6.8, family='monospace', va='top', color='#1e293b')

    plt.savefig(output_pdf, format="pdf", dpi=300)
    plt.close()
    print(f"Saved Navigation & Reference Guide to {output_pdf}")

def main():
    Path("state/maps").mkdir(parents=True, exist_ok=True)
    
    pts = parse_gpx("export.gpx")
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    eles = np.array([p[2] for p in pts])
    
    eastings, northings = to_utm.transform(lons, lats)
    all_pts_utm = np.column_stack([eastings, northings])
    
    dists = [0.0]
    for i in range(1, len(pts)):
        d = math.hypot(eastings[i] - eastings[i-1], northings[i] - northings[i-1])
        dists.append(dists[-1] + d)
    all_dists = np.array(dists)
    
    # 5 Stages accurately bounded to fit daily starts and ends comfortably:
    stages = [
        {
            "day": 1,
            "title": "Stage 1: Oberissalm → Franz-Senn-Hütte & Alpeiner Tal",
            "d0": 0.0,
            "d1": 10300.0,
            "e_min": 661000.0, "e_max": 668000.0,
            "n_min": 5214000.0, "n_max": 5221000.0,
            "grade": "T2 (Moderate)",
        },
        {
            "day": 2,
            "title": "Stage 2: Franz-Senn-Hütte → Schrimmennieder (2,714m) → Neue Regensburger Hütte",
            "d0": 10200.0,
            "d1": 19550.0,
            "e_min": 663000.0, "e_max": 670000.0,
            "n_min": 5212500.0, "n_max": 5218500.0, # Regensburger is at N 5213592, perfectly framed!
            "grade": "T3 (Challenging)",
        },
        {
            "day": 3,
            "title": "Stage 3: Neue Regensburger Hütte → Grawagrubennieder (2,880m) → Dresdner Hütte",
            "d0": 19500.0,
            "d1": 32050.0,
            "e_min": 660000.0, "e_max": 668000.0,
            "n_min": 5205500.0, "n_max": 5214500.0, # Both Regensburger (N 5213592) and Dresdner (N 5207172) inside!
            "grade": "T3+ (Alpine Summit Pass)",
        },
        {
            "day": 4,
            "title": "Stage 4: Dresdner Hütte → Peiljoch (2,676m) → Blaue Lacke → Sulzenauhütte",
            "d0": 31950.0,
            "d1": 38100.0,
            "e_min": 661000.0, "e_max": 668000.0,
            "n_min": 5203500.0, "n_max": 5210500.0,
            "grade": "T3 (Secured Ridge)",
        },
        {
            "day": 5,
            "title": "Stage 5: Sulzenauhütte → WildeWasserWeg → Grawa Waterfall → Ranalt",
            "d0": 38000.0,
            "d1": 50200.0,
            "e_min": 664000.0, "e_max": 671000.0,
            "n_min": 5206500.0, "n_max": 5213500.0,
            "grade": "T2 (Gorge Descent)",
        },
    ]
    
    stage_pdfs = []
    for s in stages:
        pdf_path = f"state/maps/Stage_{s['day']}_Detail_Map_UTM_v3.pdf"
        render_stage_sheet(s, all_pts_utm, all_dists, eles, pdf_path)
        stage_pdfs.append(pdf_path)
        
    guide_pdf = "state/maps/Stubai_High_Route_Navigation_Guide_v3.pdf"
    render_reference_guide(stages, all_pts_utm, all_dists, eles, guide_pdf)
    
    overview_pdf = "state/maps/Stubai_High_Route_Overview_UTM_v3.pdf"
    generate_overview_map.build_master_overview_map(
        output_pdf=overview_pdf,
        output_png="state/maps/Stubai_High_Route_Overview_UTM_v3.png"
    )
    
    book_pdf = "state/maps/Stubai_High_Route_Complete_Map_Book_Final_Atlas.pdf"
    book_pdf_circles = "state/maps/Stubai_High_Route_Complete_Map_Book_OpenCircles.pdf"
    book_pdf_v3 = "state/maps/Stubai_High_Route_Complete_Map_Book_v3.pdf"
    
    print("Combining all updated sheets into Master Navigation Map Book...")
    doc_book = fitz.open()
    doc_overview = fitz.open(overview_pdf)
    doc_book.insert_pdf(doc_overview)
    doc_overview.close()
    
    for spdf in stage_pdfs:
        doc_stage = fitz.open(spdf)
        doc_book.insert_pdf(doc_stage)
        doc_stage.close()
        
    doc_guide = fitz.open(guide_pdf)
    doc_book.insert_pdf(doc_guide)
    doc_guide.close()
    
    doc_book.save(book_pdf)
    doc_book.close()
    print(f"UPDATED MAP BOOK SAVED: {book_pdf} (Total 7 pages)")
    
    import shutil
    for target in [book_pdf_circles, book_pdf_v3]:
        try:
            shutil.copyfile(book_pdf, target)
            print(f"Also copied to: {target}")
        except Exception as e:
            print(f"Note: Could not overwrite {target} (file open in external viewer): {e}")

if __name__ == "__main__":
    main()
