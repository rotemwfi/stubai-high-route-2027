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
    p.parent.mkdir(parents=True, exist_ok=True)
    server = ["a", "b", "c"][(x + y) % 3]
    url = f"https://{server}.tile.opentopomap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "StubaiAlpineMapBook/1.0", "Referer": "https://opentopomap.org/"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            p.write_bytes(r.content)
            return Image.open(p).convert("RGB")
    except:
        pass
    return Image.new("RGB", (256, 256), (235, 230, 215))

def get_utm_reprojected_map(e_min, e_max, n_min, n_max, res=4.0, zoom=14):
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
            t = ax.text(bx, by, h["badge"], fontsize=7.2, fontweight='bold', color='#1d4ed8',
                        ha='center', va='bottom' if h["badge_offset"][1] > 0 else 'top', zorder=14)
            t.set_path_effects([pe.withStroke(linewidth=2.6, foreground='white')])

def build_master_overview_map(output_pdf="state/maps/Stubai_High_Route_Overview_UTM_v2.pdf", output_png="state/maps/Stubai_High_Route_Overview_UTM_v2.png"):
    Path("state/maps").mkdir(parents=True, exist_ok=True)
    
    pts = parse_gpx("export.gpx")
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    eles = [p[2] for p in pts]
    
    eastings, northings = to_utm.transform(lons, lats)
    eastings = np.array(eastings)
    northings = np.array(northings)
    
    dists = [0.0]
    for i in range(1, len(pts)):
        d = math.hypot(eastings[i] - eastings[i-1], northings[i] - northings[i-1])
        dists.append(dists[-1] + d)
    dists = np.array(dists)
    
    e_min, e_max = 659000.0, 671000.0
    n_min, n_max = 5204000.0, 5220000.0
    
    print(f"Generating reprojected OpenTopoMap raster for [{e_min}..{e_max}, {n_min}..{n_max}] at Zoom 14...")
    res = 4.0
    bg_img = get_utm_reprojected_map(e_min, e_max, n_min, n_max, res=res, zoom=14)
    print("Reprojection done!")
    
    fig = plt.figure(figsize=(11.69, 16.54), dpi=300)
    
    # Main map axis (top 72%)
    ax_map = fig.add_axes([0.08, 0.22, 0.86, 0.72])
    ax_map.imshow(bg_img, extent=[e_min, e_max, n_min, n_max], origin='upper', interpolation='bilinear')
    
    # 1 km UTM Grid lines
    e_ticks = np.arange(int(e_min), int(e_max) + 1, 1000)
    n_ticks = np.arange(int(n_min), int(n_max) + 1, 1000)
    
    for e in e_ticks:
        ax_map.axvline(e, color='#0284c7', linestyle='-', linewidth=0.55, alpha=0.50, zorder=3)
    for n in n_ticks:
        ax_map.axhline(n, color='#0284c7', linestyle='-', linewidth=0.55, alpha=0.50, zorder=3)
        
    # Entire 50 km Route Line (slim 1.3 pt with halo)
    ax_map.plot(eastings, northings, color='white', linewidth=2.4, alpha=0.8, zorder=5)
    ax_map.plot(eastings, northings, color='#dc2626', linewidth=1.3, alpha=1.0, zorder=6, label='Stubai High Route (50.1 km)')
    
    # Subtle Trailhead & Finish dots
    ax_map.plot(eastings[0], northings[0], marker='o', markersize=4.5, markerfacecolor='#16a34a', markeredgecolor='white', markeredgewidth=1.0, zorder=8)
    ax_map.plot(eastings[-1], northings[-1], marker='s', markersize=4.5, markerfacecolor='#b91c1c', markeredgecolor='white', markeredgewidth=1.0, zorder=8)
    
    # Draw Open Circles around huts so original location & icon are visible!
    draw_open_circle_huts(ax_map, e_min, e_max, n_min, n_max)
    
    # Set Map Axis limits and labels
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
    
    ax_map.tick_params(axis='both', which='both', length=5, width=1.2, color='#0284c7', direction='out')
    
    ax_top = ax_map.secondary_xaxis('top')
    ax_top.set_xticks(e_ticks)
    ax_top.set_xticklabels(e_labels, fontsize=8, fontweight='bold', color='#0369a1')
    ax_top.tick_params(length=5, width=1.2, color='#0284c7', direction='out')
    
    ax_right = ax_map.secondary_yaxis('right')
    ax_right.set_yticks(n_ticks)
    ax_right.set_yticklabels(n_labels, fontsize=8, fontweight='bold', color='#0369a1')
    ax_right.tick_params(length=5, width=1.2, color='#0284c7', direction='out')
    
    for spine in ax_map.spines.values():
        spine.set_edgecolor('#0369a1')
        spine.set_linewidth(1.8)
        
    fig.text(0.50, 0.975, "STUBAI HIGH TRAIL (STUBAIER HÖHENWEG) — 5-DAY ALPINE TREK",
             fontsize=14, fontweight='bold', ha='center', color='#0f172a')
    fig.text(0.50, 0.955, "Complete Topographic Navigation Map with 1 km UTM Grid (Zone 32N) • OpenTopoMap Cartography & GPX Route",
             fontsize=9, ha='center', color='#475569')

    # BOTTOM AREA: Elevation Profile (Left) and Scale Bar & Legend Block (Right)
    ax_prof = fig.add_axes([0.08, 0.040, 0.46, 0.14])
    dists_km = dists / 1000.0
    ax_prof.plot(dists_km, eles, color='#dc2626', linewidth=1.6, zorder=4)
    ax_prof.fill_between(dists_km, eles, 1000, color='#fee2e2', alpha=0.7, zorder=3)
    
    prof_marks = [
        ("Oberissalm", 0.0, 1742, (0, 14)),
        ("Franz-Senn [N1]", 2.8, 2147, (0, 16)),
        ("Schrimmennieder", 16.5, 2714, (0, 12)),
        ("Regensburger [N2]", 19.5, 2286, (0, -20)),
        ("Grawagrubennieder", 23.4, 2880, (0, 12)),
        ("Dresdner [N3]", 32.0, 2308, (0, -20)),
        ("Peiljoch", 34.0, 2676, (0, 12)),
        ("Sulzenau [N4]", 38.0, 2191, (0, -20)),
        ("Ranalt", 50.1, 1214, (0, 14)),
    ]
    for name, km_mark, h_ele, offset in prof_marks:
        ax_prof.plot(km_mark, h_ele, marker='o', markersize=3.8, markerfacecolor='#dc2626', markeredgecolor='white', zorder=5)
        ax_prof.annotate(f"{name}\n{h_ele}m", (km_mark, h_ele), xytext=offset, textcoords='offset points',
                         fontsize=6.2, fontweight='bold', ha='center', color='#1e293b',
                         bbox=dict(boxstyle='round,pad=0.15', facecolor='white', edgecolor='#cbd5e1', alpha=0.85),
                         arrowprops=dict(arrowstyle='-', color='#94a3b8', lw=0.6),
                         zorder=6)
        
    ax_prof.set_xlim(0, dists_km[-1])
    ax_prof.set_ylim(1000, 3100)
    ax_prof.set_xlabel("Cumulative Distance (km)", fontsize=7.8, fontweight='bold', color='#1e293b')
    ax_prof.set_ylabel("Elevation (m)", fontsize=7.8, fontweight='bold', color='#1e293b')
    ax_prof.grid(True, linestyle=':', alpha=0.5, color='#94a3b8')
    ax_prof.tick_params(labelsize=6.8)
    ax_prof.set_title("Route Elevation Profile (50.1 km • Ascent: +3,329 m • Descent: -3,857 m)", fontsize=8.2, fontweight='bold', color='#0f172a', pad=4)
    
    # Right Box: Scale Bar, North Arrow, UTM Grid Legend & Info
    ax_legend = fig.add_axes([0.56, 0.040, 0.38, 0.14])
    ax_legend.set_xlim(0, 100)
    ax_legend.set_ylim(0, 100)
    ax_legend.axis('off')
    
    card = patches.FancyBboxPatch((0, 0), 100, 100, boxstyle="round,pad=1.5", fc="#f8fafc", ec="#0284c7", lw=1.2)
    ax_legend.add_patch(card)
    
    ax_legend.text(4, 91, "SCALE & UTM GRID SPECIFICATION", fontsize=8.5, fontweight='bold', color='#0369a1')
    
    # Graphical Scale Bar (0 to 2 km)
    sb_x, sb_y, sb_w, sb_h = 4, 76, 56, 5.5
    seg_w = sb_w / 4.0
    for i in range(4):
        fc = '#0f172a' if i % 2 == 0 else '#ffffff'
        rect = patches.Rectangle((sb_x + i * seg_w, sb_y), seg_w, sb_h, fc=fc, ec='#0f172a', lw=0.9, zorder=3)
        ax_legend.add_patch(rect)
    
    for i, val in enumerate(["0", "500m", "1.0k", "1.5k", "2 km"]):
        ax_legend.text(sb_x + i * seg_w, sb_y + sb_h + 2.0, val, fontsize=6.8, fontweight='bold', ha='center', color='#0f172a')
        
    ax_legend.text(4, 66, "SCALE 1 : 45,000   •   1 cm = 450 m on ground", fontsize=7.8, fontweight='bold', color='#0f172a')
    ax_legend.text(4, 56, "1 UTM Grid Square = 1,000 m × 1,000 m (1.0 km² • 100 ha)", fontsize=7.2, color='#0369a1', fontweight='bold')
    ax_legend.text(4, 46, "Datum: WGS 84 • Projection: UTM Zone 32N • Central Meridian: 9°E", fontsize=6.8, color='#475569')
    
    # North Arrow
    na_x, na_y = 86, 70
    ax_legend.annotate('', xy=(na_x, na_y + 18), xytext=(na_x, na_y - 8),
                       arrowprops=dict(facecolor='#dc2626', edgecolor='#0f172a', width=2.2, headwidth=7, headlength=8),
                       zorder=5)
    ax_legend.text(na_x, na_y + 20, "GN", fontsize=7.8, fontweight='bold', color='#dc2626', ha='center')
    ax_legend.text(na_x, na_y - 14, "TN\n+1.5°", fontsize=5.8, color='#475569', ha='center')
    
    ax_legend.plot([4, 96], [39, 39], color='#cbd5e1', lw=0.8)
    
    summary_txt = (
        "OVERNIGHT HUTS: ○ [Blue Ring] = Overnight DAV Sleeping Hut (Stages 1–4)\n"
        "NIGHTS: 1: Franz-Senn (2,147m) • 2: Regensburger (2,286m) • 3: Dresdner (2,308m) • 4: Sulzenau (2,191m)\n"
        "EMERGENCY: Mountain Rescue 140 • Euro 112 • Avalanche: lawine.tirol.gv.at"
    )
    ax_legend.text(4, 28, summary_txt, fontsize=6.2, va='top', color='#1e293b', family='monospace')

    print(f"Saving updated Overview PDF to {output_pdf}...")
    plt.savefig(output_pdf, format="pdf", dpi=300)
    print(f"Saving updated Overview PNG to {output_png}...")
    plt.savefig(output_png, format="png", dpi=300)
    plt.close()
    print("Master Overview Map build complete!")

if __name__ == "__main__":
    build_master_overview_map()
