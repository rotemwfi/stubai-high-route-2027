#!/usr/bin/env python3
"""
build_1_50000_utm_map.py
Builds a true-scale 1:50,000 navigation map from any GPX file (+20 km buffer around the GPX route)
using real-world elevation data (AWS Terrarium DEM tiles) and real OpenStreetMap roads (Overpass API).
Shows ONLY:
  1. Elevation Contours (25m regular + 100m bold labeled index contours)
  2. Roads & Tracks (OpenStreetMap highway vectors)
  3. UTM Coordinate Grid (1 km minor grid + 5 km major grid with meter & 2-digit tactical labels)
  4. The supplied GPX Route & Waypoints

Outputs strictly to /state/maps/:
  - <stem>_1_50000_utm_map.pdf (True 1:50,000 scale vector PDF: 2.0 cm = 1,000 m)
  - <stem>_1_50000_utm_map.png (High-resolution PNG)
  - <stem>_1_50000_utm_viewer.html (Interactive zoom/pan HTML viewer)
  - <stem>_map_manifest.json (Metadata receipt)
"""

import argparse
import base64
import io
import json
import math
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
import numpy as np
from PIL import Image
import requests
from scipy.ndimage import gaussian_filter, map_coordinates

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "map_builder_config.json"
STATE_MAPS_DIR = BASE_DIR / "state" / "maps"


# ==============================================================================
# 1. Exact WGS84 (Lat/Lon) <-> UTM (Easting/Northing) Projection (Pure NumPy)
# ==============================================================================

def get_utm_zone(lon_deg: float) -> int:
    return int(math.floor((lon_deg + 180.0) / 6.0)) + 1


def latlon_to_utm(lat_deg: np.ndarray, lon_deg: np.ndarray, zone: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Vectorized WGS84 (lat, lon in degrees) to UTM (Easting, Northing in meters) for a fixed UTM zone.
    Accurate to <1 mm.
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    ep2 = e2 / (1.0 - e2)
    k0 = 0.9996

    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    lon0 = math.radians((zone - 1) * 6.0 - 180.0 + 3.0)

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    tan_lat = np.tan(lat)

    N = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)
    T = tan_lat * tan_lat
    C = ep2 * cos_lat * cos_lat
    A = cos_lat * (lon - lon0)

    e4 = e2 * e2
    e6 = e4 * e2
    M = a * (
        (1.0 - e2 / 4.0 - 3.0 * e4 / 64.0 - 5.0 * e6 / 256.0) * lat
        - (3.0 * e2 / 8.0 + 3.0 * e4 / 32.0 + 45.0 * e6 / 1024.0) * np.sin(2.0 * lat)
        + (15.0 * e4 / 256.0 + 45.0 * e6 / 1024.0) * np.sin(4.0 * lat)
        - (35.0 * e6 / 3072.0) * np.sin(6.0 * lat)
    )

    easting = k0 * N * (
        A
        + (1.0 - T + C) * (A ** 3) / 6.0
        + (5.0 - 18.0 * T + T * T + 72.0 * C - 58.0 * ep2) * (A ** 5) / 120.0
    ) + 500000.0

    northing = k0 * (
        M
        + N * tan_lat * (
            (A ** 2) / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C * C) * (A ** 4) / 24.0
            + (61.0 - 58.0 * T + T * T + 600.0 * C - 330.0 * ep2) * (A ** 6) / 720.0
        )
    )
    return easting, northing


def utm_to_latlon(easting: float, northing: float, zone: int) -> Tuple[float, float]:
    """Inverse UTM (Easting, Northing in meters, Northern Hemisphere) to WGS84 (lat, lon in degrees)."""
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    ep2 = e2 / (1.0 - e2)
    k0 = 0.9996
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))

    x = easting - 500000.0
    y = northing
    lon0 = math.radians((zone - 1) * 6.0 - 180.0 + 3.0)

    M = y / k0
    mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * (e2 ** 2) / 64.0 - 5.0 * (e2 ** 3) / 256.0))

    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * (e1 ** 3) / 32.0) * math.sin(2.0 * mu)
        + (21.0 * (e1 ** 2) / 16.0 - 55.0 * (e1 ** 4) / 32.0) * math.sin(4.0 * mu)
        + (151.0 * (e1 ** 3) / 96.0) * math.sin(6.0 * mu)
    )

    sin1 = math.sin(phi1)
    cos1 = math.cos(phi1)
    tan1 = math.tan(phi1)
    N1 = a / math.sqrt(1.0 - e2 * sin1 * sin1)
    T1 = tan1 * tan1
    C1 = ep2 * cos1 * cos1
    R1 = a * (1.0 - e2) / ((1.0 - e2 * sin1 * sin1) ** 1.5)
    D = x / (N1 * k0)

    lat = phi1 - (N1 * tan1 / R1) * (
        (D ** 2) / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 * C1 - 9.0 * ep2) * (D ** 4) / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 * T1 - 252.0 * ep2 - 3.0 * C1 * C1) * (D ** 6) / 720.0
    )
    lon = lon0 + (
        D
        - (1.0 + 2.0 * T1 + C1) * (D ** 3) / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 * C1 + 8.0 * ep2 + 24.0 * T1 * T1) * (D ** 5) / 120.0
    ) / cos1
    return math.degrees(lat), math.degrees(lon)


def utm_to_latlon_vec(easting: np.ndarray, northing: np.ndarray, zone: int) -> Tuple[np.ndarray, np.ndarray]:
    """Vectorized Inverse UTM (Easting, Northing in meters) to WGS84 (lat, lon in degrees)."""
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    ep2 = e2 / (1.0 - e2)
    k0 = 0.9996
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))

    x = easting - 500000.0
    y = northing
    lon0 = math.radians((zone - 1) * 6.0 - 180.0 + 3.0)

    M = y / k0
    mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * (e2 ** 2) / 64.0 - 5.0 * (e2 ** 3) / 256.0))

    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * (e1 ** 3) / 32.0) * np.sin(2.0 * mu)
        + (21.0 * (e1 ** 2) / 16.0 - 55.0 * (e1 ** 4) / 32.0) * np.sin(4.0 * mu)
        + (151.0 * (e1 ** 3) / 96.0) * np.sin(6.0 * mu)
    )

    sin1 = np.sin(phi1)
    cos1 = np.cos(phi1)
    tan1 = np.tan(phi1)
    N1 = a / np.sqrt(1.0 - e2 * sin1 * sin1)
    T1 = tan1 * tan1
    C1 = ep2 * cos1 * cos1
    R1 = a * (1.0 - e2) / ((1.0 - e2 * sin1 * sin1) ** 1.5)
    D = x / (N1 * k0)

    lat = phi1 - (N1 * tan1 / R1) * (
        (D ** 2) / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 * C1 - 9.0 * ep2) * (D ** 4) / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 * T1 - 252.0 * ep2 - 3.0 * C1 * C1) * (D ** 6) / 720.0
    )
    lon = lon0 + (
        D
        - (1.0 + 2.0 * T1 + C1) * (D ** 3) / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 * C1 + 8.0 * ep2 + 24.0 * T1 * T1) * (D ** 5) / 120.0
    ) / cos1
    return np.degrees(lat), np.degrees(lon)


# ==============================================================================
# 2. GPX Parser
# ==============================================================================

def parse_gpx(gpx_path: Path) -> Tuple[List[Tuple[float, float]], List[Dict[str, Any]], str]:
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    track_pts: List[Tuple[float, float]] = []
    waypoints: List[Dict[str, Any]] = []
    route_name = gpx_path.stem

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "name" and elem == root.find(".//{*}trk/{*}name"):
            if elem.text:
                route_name = elem.text.strip()
        elif tag in ("trkpt", "rtept"):
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            track_pts.append((lat, lon))
        elif tag == "wpt":
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            wname = ""
            for child in elem:
                if child.tag.split("}")[-1] == "name" and child.text:
                    wname = child.text.strip()
            waypoints.append({"lat": lat, "lon": lon, "name": wname})

    if not track_pts and waypoints:
        track_pts = [(w["lat"], w["lon"]) for w in waypoints]
    if not track_pts:
        raise ValueError(f"No track points (<trkpt>, <rtept>, <wpt>) found in {gpx_path}")

    return track_pts, waypoints, route_name


# ==============================================================================
# 3. Web Data Fetchers: AWS Terrarium DEM Tiles & OSM Overpass Roads
# ==============================================================================

def deg2tile(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    lat_rad = math.radians(lat_deg)
    n = 2 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def tile2latlon_grid(x_min: int, x_max: int, y_min: int, y_max: int, zoom: int) -> Tuple[np.ndarray, np.ndarray]:
    """Returns 2D arrays of (lat, lon) for every pixel in the stitched tile mosaic."""
    n = 2.0 ** zoom
    w_px = (x_max - x_min + 1) * 256
    h_px = (y_max - y_min + 1) * 256

    xs = x_min + (np.arange(w_px) + 0.5) / 256.0
    ys = y_min + (np.arange(h_px) + 0.5) / 256.0

    lons_1d = xs / n * 360.0 - 180.0
    lats_1d = np.degrees(np.arctan(np.sinh(math.pi * (1.0 - 2.0 * ys / n))))

    lon_grid, lat_grid = np.meshgrid(lons_1d, lats_1d)
    return lat_grid, lon_grid


def fetch_dem_mosaic(
    lat_min: float, lon_min: float, lat_max: float, lon_max: float, zoom: int = 11
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Tuple[int, int, int, int, int]]:
    x0, y1 = deg2tile(lat_min, lon_min, zoom)
    x1, y0 = deg2tile(lat_max, lon_max, zoom)
    x_min, x_max = min(x0, x1), max(x0, x1)
    y_min, y_max = min(y0, y1), max(y0, y1)

    cache_dir = STATE_MAPS_DIR / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"dem_z{zoom}_{x_min}_{x_max}_{y_min}_{y_max}.npy"

    if cache_file.exists():
        mosaic = np.load(cache_file)
        print(f"[DEM] Loaded cached DEM mosaic ({mosaic.shape[1]}x{mosaic.shape[0]} px) from {cache_file.name}")
    else:
        w_tiles = x_max - x_min + 1
        h_tiles = y_max - y_min + 1
        mosaic = np.zeros((h_tiles * 256, w_tiles * 256), dtype=np.float32)

        def download_one(tx: int, ty: int) -> Tuple[int, int, np.ndarray]:
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{zoom}/{tx}/{ty}.png"
            resp = requests.get(url, timeout=12)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            arr = np.asarray(img, dtype=np.float32)
            elev = (arr[:, :, 0] * 256.0 + arr[:, :, 1] + arr[:, :, 2] / 256.0) - 32768.0
            return tx, ty, elev

        tasks = [(tx, ty) for ty in range(y_min, y_max + 1) for tx in range(x_min, x_max + 1)]
        print(f"[DEM] Downloading {len(tasks)} real elevation tiles (Zoom {zoom}) from AWS Terrarium...")
        with ThreadPoolExecutor(max_workers=12) as ex:
            futures = [ex.submit(download_one, tx, ty) for tx, ty in tasks]
            for fut in as_completed(futures):
                tx, ty, elev = fut.result()
                ix = (tx - x_min) * 256
                iy = (ty - y_min) * 256
                mosaic[iy:iy + 256, ix:ix + 256] = elev
        np.save(cache_file, mosaic)

    lat_grid, lon_grid = tile2latlon_grid(x_min, x_max, y_min, y_max, zoom)
    return lat_grid, lon_grid, mosaic, (x_min, x_max, y_min, y_max, zoom)


def compute_alpine_hillshade_rgba(
    mosaic: np.ndarray,
    tile_bounds: Tuple[int, int, int, int, int],
    e_min: float,
    e_max: float,
    n_min: float,
    n_max: float,
    utm_zone: int,
    cell_m: float = 25.0
) -> np.ndarray:
    """
    Resamples the DEM onto a uniform UTM meter grid and computes a Swiss/Alpine-style
    multi-directional 3D relief hillshade + steep scree/rock stippling matching the reference style.
    """
    x_min, x_max, y_min, y_max, zoom = tile_bounds
    n_tiles = 2.0 ** zoom

    cols = int(round((e_max - e_min) / cell_m))
    rows = int(round((n_max - n_min) / cell_m))
    e_1d = np.linspace(e_min, e_max, cols, dtype=np.float64)
    n_1d = np.linspace(n_min, n_max, rows, dtype=np.float64)
    e_grid, n_grid = np.meshgrid(e_1d, n_1d)

    lat_g, lon_g = utm_to_latlon_vec(e_grid, n_grid, utm_zone)
    lat_rad = np.radians(lat_g)
    px = ((lon_g + 180.0) / 360.0 * n_tiles - x_min) * 256.0 - 0.5
    py = ((1.0 - np.arcsinh(np.tan(lat_rad)) / math.pi) / 2.0 * n_tiles - y_min) * 256.0 - 0.5

    z_utm = map_coordinates(mosaic, [py, px], order=3, mode="nearest")
    z_hill = gaussian_filter(z_utm, sigma=0.85)

    # Surface gradients in meters (origin='lower': axis 0 is Northing, axis 1 is Easting)
    dz_dn, dz_de = np.gradient(z_hill, cell_m, cell_m)

    # 1. Multi-directional hillshade (Primary NW 315 deg + secondary WNW 285 deg & NNW 345 deg)
    z_factor = 1.65
    slope = np.arctan(z_factor * np.hypot(dz_de, dz_dn))
    aspect = np.arctan2(-dz_dn, -dz_de)  # math angle of steepest descent

    def hillshade_dir(az_deg: float, alt_deg: float) -> np.ndarray:
        az_math = math.radians(90.0 - az_deg)
        zenith = math.radians(90.0 - alt_deg)
        hs = np.cos(zenith) * np.cos(slope) + np.sin(zenith) * np.sin(slope) * np.cos(az_math - aspect)
        return np.clip(hs, 0.0, 1.0)

    hs_main = hillshade_dir(315.0, 36.0)
    hs_w = hillshade_dir(280.0, 42.0)
    hs_n = hillshade_dir(350.0, 42.0)
    hs_combined = 0.65 * hs_main + 0.20 * hs_w + 0.15 * hs_n

    # Normalize so flat ground (cos(36 deg) ~ 0.809) and lit NW slopes are crisp white,
    # while SE shadow slopes get smooth, deeply modeled neutral grey relief shading
    shadow = np.clip((0.78 - hs_combined) / 0.78, 0.0, 1.0) ** 1.08
    true_slope_deg = np.degrees(np.arctan(np.hypot(dz_de, dz_dn)))
    slope_dark = np.clip((true_slope_deg - 10.0) / 52.0, 0.0, 1.0) * 0.22

    darkness = np.clip(shadow * 0.44 + slope_dark, 0.0, 0.56)

    # 2. Alpine rock / scree stipple texture on steep high-alpine slopes (>31 deg)
    rng = np.random.default_rng(2027)
    fine_noise = rng.uniform(0.0, 1.0, size=z_utm.shape).astype(np.float32)
    coarse_noise = gaussian_filter(rng.uniform(0.0, 1.0, size=z_utm.shape).astype(np.float32), sigma=1.1)
    stipple_dots = ((fine_noise > 0.52) & (coarse_noise > 0.44)).astype(np.float32)
    scree_weight = (
        np.clip((true_slope_deg - 30.0) / 15.0, 0.0, 1.0)
        * np.clip((z_utm - 1900.0) / 350.0, 0.0, 1.0)
    )
    scree_dark = scree_weight * (0.07 + 0.18 * stipple_dots)

    total_dark = np.clip(darkness + scree_dark, 0.0, 0.62)

    # Cool-neutral alpine shadow RGB over white base
    rgba = np.ones((rows, cols, 4), dtype=np.float32)
    rgba[:, :, 0] = 1.0 - total_dark * 0.96
    rgba[:, :, 1] = 1.0 - total_dark * 0.95
    rgba[:, :, 2] = 1.0 - total_dark * 0.92
    rgba[:, :, 3] = 1.0
    return rgba


def fetch_osm_roads(
    lat_min: float, lon_min: float, lat_max: float, lon_max: float, endpoints: List[str],
    gpx_bbox: Tuple[float, float, float, float] = None
) -> Dict[str, List[List[Tuple[float, float]]]]:
    """
    Fetches real roads from OpenStreetMap via Overpass API using a single-pass spatial scan
    and filters highway classes in Python.
    Returns categorized polyline lists in (lat, lon).
    """
    if gpx_bbox is not None:
        glat_min, glon_min, glat_max, glon_max = gpx_bbox
        q_lat_min = max(lat_min, glat_min - 0.10)
        q_lon_min = max(lon_min, glon_min - 0.14)
        q_lat_max = min(lat_max, glat_max + 0.10)
        q_lon_max = min(lon_max, glon_max + 0.14)
    else:
        q_lat_min, q_lon_min, q_lat_max, q_lon_max = lat_min, lon_min, lat_max, lon_max

    bbox_str = f"{q_lat_min:.4f},{q_lon_min:.4f},{q_lat_max:.4f},{q_lon_max:.4f}"
    query = f"[out:json][timeout:60];way[highway]({bbox_str});out geom qt;"

    roads: Dict[str, List[List[Tuple[float, float]]]] = {
        "motorway_trunk": [],
        "primary_secondary": [],
        "tertiary_minor": [],
        "track_service": []
    }
    headers = {"User-Agent": "StubaiMapBuilder/1.0"}

    cache_dir = STATE_MAPS_DIR / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"osm_roads_{bbox_str.replace(',', '_')}.json"

    elements = None
    if cache_file.exists():
        try:
            elements = json.loads(cache_file.read_text(encoding="utf-8")).get("elements", [])
            print(f"[OSM] Loaded {len(elements)} cached OSM ways from {cache_file.name}")
        except Exception:
            elements = None

    if elements is None:
        for url in endpoints:
            try:
                print(f"[OSM] Querying real road vectors from {url} ({bbox_str}) ...")
                resp = requests.post(url, data={"data": query}, headers=headers, timeout=70)
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    cache_file.write_text(json.dumps({"elements": elements}), encoding="utf-8")
                    break
                else:
                    print(f"[WARN] Overpass endpoint {url} returned HTTP {resp.status_code}")
            except Exception as e:
                print(f"[WARN] Overpass endpoint {url} failed: {e}")

    if elements:
        valid_hw = {
            "motorway", "trunk", "motorway_link", "trunk_link",
            "primary", "secondary", "primary_link", "secondary_link",
            "tertiary", "tertiary_link", "unclassified", "residential",
            "track", "service"
        }
        for el in elements:
            hw = el.get("tags", {}).get("highway", "")
            if hw not in valid_hw:
                continue
            geom = el.get("geometry", [])
            if len(geom) < 2:
                continue
            pts = [(float(pt["lat"]), float(pt["lon"])) for pt in geom]
            if hw in ("motorway", "trunk", "motorway_link", "trunk_link"):
                roads["motorway_trunk"].append(pts)
            elif hw in ("primary", "secondary", "primary_link", "secondary_link"):
                roads["primary_secondary"].append(pts)
            elif hw in ("tertiary", "tertiary_link", "unclassified", "residential"):
                roads["tertiary_minor"].append(pts)
            else:
                roads["track_service"].append(pts)
        total_ways = sum(len(v) for v in roads.values())
        print(f"[OSM] Classified {total_ways} road & track segments for map rendering.")

    return roads


def fetch_osm_water(
    lat_min: float, lon_min: float, lat_max: float, lon_max: float, endpoints: List[str],
    gpx_bbox: Tuple[float, float, float, float] = None
) -> Dict[str, List[List[Tuple[float, float]]]]:
    """
    Fetches real streams, rivers, lakes, and glaciers from OpenStreetMap via Overpass API.
    Returns categorized lists in (lat, lon):
      - 'rivers': main rivers (e.g. Ruetz, Sill)
      - 'streams': mountain brooks & streams
      - 'lakes': lakes & tarns (closed polygons)
      - 'glaciers': alpine glaciers & ice fields (closed polygons)
    """
    if gpx_bbox is not None:
        glat_min, glon_min, glat_max, glon_max = gpx_bbox
        q_lat_min = max(lat_min, glat_min - 0.12)
        q_lon_min = max(lon_min, glon_min - 0.16)
        q_lat_max = min(lat_max, glat_max + 0.12)
        q_lon_max = min(lon_max, glon_max + 0.16)
    else:
        q_lat_min, q_lon_min, q_lat_max, q_lon_max = lat_min, lon_min, lat_max, lon_max

    bbox_str = f"{q_lat_min:.4f},{q_lon_min:.4f},{q_lat_max:.4f},{q_lon_max:.4f}"
    query = (
        f"[out:json][timeout:60];("
        f"way[waterway]({bbox_str});"
        f"way[natural=water]({bbox_str});"
        f"way[natural=glacier]({bbox_str});"
        f");out geom qt;"
    )

    water_data: Dict[str, List[List[Tuple[float, float]]]] = {
        "rivers": [],
        "streams": [],
        "lakes": [],
        "glaciers": []
    }
    headers = {"User-Agent": "StubaiWaterMapBuilder/1.0"}

    cache_dir = STATE_MAPS_DIR / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"osm_water_{bbox_str.replace(',', '_')}.json"

    elements = None
    if cache_file.exists():
        try:
            elements = json.loads(cache_file.read_text(encoding="utf-8")).get("elements", [])
            print(f"[WATER] Loaded {len(elements)} cached OSM water elements from {cache_file.name}")
        except Exception:
            elements = None

    if elements is None:
        for url in endpoints:
            try:
                print(f"[WATER] Querying real streams, lakes & glaciers from {url} ({bbox_str}) ...")
                resp = requests.post(url, data={"data": query}, headers=headers, timeout=70)
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    cache_file.write_text(json.dumps({"elements": elements}), encoding="utf-8")
                    break
                else:
                    print(f"[WARN] Overpass endpoint {url} returned HTTP {resp.status_code}")
            except Exception as e:
                print(f"[WARN] Overpass endpoint {url} failed: {e}")

    if elements:
        for el in elements:
            geom = el.get("geometry", [])
            if len(geom) < 2:
                continue
            pts = [(float(pt["lat"]), float(pt["lon"])) for pt in geom]
            tags = el.get("tags", {})
            natural = tags.get("natural", "")
            waterway = tags.get("waterway", "")

            if natural == "glacier":
                water_data["glaciers"].append(pts)
            elif natural == "water" or "water" in tags:
                water_data["lakes"].append(pts)
            elif waterway in ("river", "canal"):
                water_data["rivers"].append(pts)
            elif waterway in ("stream", "brook", "drain", "ditch", "flowline"):
                water_data["streams"].append(pts)

        print(
            f"[WATER] Classified {len(water_data['streams'])} streams, "
            f"{len(water_data['rivers'])} rivers, {len(water_data['lakes'])} lakes/tarns, "
            f"and {len(water_data['glaciers'])} glaciers."
        )

    return water_data


# ==============================================================================
# 4. 1:50,000 Map Renderer (Contours + Roads + UTM Grid + GPX Only)
# ==============================================================================

def build_map(gpx_path: Path, buffer_km: float = 20.0, dpi: int = 200) -> Dict[str, Any]:
    STATE_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    track_pts, waypoints, route_title = parse_gpx(gpx_path)
    lats = np.array([p[0] for p in track_pts])
    lons = np.array([p[1] for p in track_pts])

    utm_zone = get_utm_zone(float(np.mean(lons)))
    trk_e, trk_n = latlon_to_utm(lats, lons, utm_zone)

    buf_m = buffer_km * 1000.0
    e_min = math.floor((float(np.min(trk_e)) - buf_m) / 1000.0) * 1000.0
    e_max = math.ceil((float(np.max(trk_e)) + buf_m) / 1000.0) * 1000.0
    n_min = math.floor((float(np.min(trk_n)) - buf_m) / 1000.0) * 1000.0
    n_max = math.ceil((float(np.max(trk_n)) + buf_m) / 1000.0) * 1000.0

    width_m = e_max - e_min
    height_m = n_max - n_min

    # Convert UTM corners back to lat/lon with a small margin for data fetching
    c_lats, c_lons = [], []
    for ce in (e_min - 1500, e_max + 1500):
        for cn in (n_min - 1500, n_max + 1500):
            la, lo = utm_to_latlon(ce, cn, utm_zone)
            c_lats.append(la)
            c_lons.append(lo)
    lat_min, lat_max = min(c_lats), max(c_lats)
    lon_min, lon_max = min(c_lons), max(c_lons)

    # Fetch real DEM & OSM Roads
    dem_lat, dem_lon, dem_elev, tile_bounds = fetch_dem_mosaic(
        lat_min, lon_min, lat_max, lon_max, zoom=cfg["dem_source"]["zoom_level"]
    )
    dem_e, dem_n = latlon_to_utm(dem_lat, dem_lon, utm_zone)
    dem_smooth = gaussian_filter(dem_elev, sigma=cfg["dem_source"]["smoothing_sigma"])

    print("[SHADE] Computing Swiss/Alpine 3D multi-directional relief hillshade & steep scree texture...")
    hillshade_rgba = compute_alpine_hillshade_rgba(
        dem_elev, tile_bounds, e_min, e_max, n_min, n_max, utm_zone, cell_m=25.0
    )

    gpx_bbox = (float(np.min(lats)), float(np.min(lons)), float(np.max(lats)), float(np.max(lons)))
    roads_latlon = fetch_osm_roads(
        lat_min, lon_min, lat_max, lon_max, cfg["roads_source"]["overpass_endpoints"], gpx_bbox=gpx_bbox
    )
    water_data = fetch_osm_water(
        lat_min, lon_min, lat_max, lon_max, cfg["roads_source"]["overpass_endpoints"], gpx_bbox=gpx_bbox
    )

    # True 1:50,000 Physical Page Sizing:
    # At 1:50,000, 1,000 m = 2.0 cm = 0.78740157 inches
    scale_denom = cfg["scale_denominator"]
    map_w_cm = (width_m / scale_denom) * 100.0
    map_h_cm = (height_m / scale_denom) * 100.0
    margin_cm = 6.0  # 3 cm border on each side for UTM collar & title
    fig_w_in = (map_w_cm + margin_cm) / 2.54
    fig_h_in = (map_h_cm + margin_cm) / 2.54

    fig = plt.figure(figsize=(fig_w_in, fig_h_in), facecolor="#ffffff")
    ax_left = (margin_cm / 2.0) / (map_w_cm + margin_cm)
    ax_bottom = (margin_cm / 2.0) / (map_h_cm + margin_cm)
    ax_w = map_w_cm / (map_w_cm + margin_cm)
    ax_h = map_h_cm / (map_h_cm + margin_cm)
    ax = fig.add_axes([ax_left, ax_bottom, ax_w, ax_h], facecolor="#ffffff")

    ax.set_xlim(e_min, e_max)
    ax.set_ylim(n_min, n_max)
    ax.set_aspect("equal", adjustable="box")

    # 0. Plot 3D Alpine Relief Hillshade + Scree Texture
    ax.imshow(
        hillshade_rgba,
        extent=[e_min, e_max, n_min, n_max],
        origin="lower",
        interpolation="bicubic",
        zorder=1
    )

    # 0.5 Plot Glaciers, Lakes, Streams & Rivers
    if water_data.get("glaciers"):
        glacier_polys = []
        for pts in water_data["glaciers"]:
            glats = np.array([p[0] for p in pts])
            glons = np.array([p[1] for p in pts])
            ge, gn = latlon_to_utm(glats, glons, utm_zone)
            glacier_polys.append(np.column_stack([ge, gn]))
        if glacier_polys:
            pc_glaciers = PolyCollection(
                glacier_polys,
                facecolors="#cffafe",
                edgecolors="#67e8f9",
                linewidths=0.45,
                alpha=0.65,
                zorder=1.2
            )
            ax.add_collection(pc_glaciers)

    if water_data.get("lakes"):
        lake_polys = []
        for pts in water_data["lakes"]:
            llats = np.array([p[0] for p in pts])
            llons = np.array([p[1] for p in pts])
            le, ln = latlon_to_utm(llats, llons, utm_zone)
            lake_polys.append(np.column_stack([le, ln]))
        if lake_polys:
            pc_lakes = PolyCollection(
                lake_polys,
                facecolors="#7dd3fc",
                edgecolors="#0284c7",
                linewidths=0.65,
                alpha=0.88,
                zorder=1.4
            )
            ax.add_collection(pc_lakes)

    if water_data.get("streams"):
        stream_segs = []
        for pts in water_data["streams"]:
            slats = np.array([p[0] for p in pts])
            slons = np.array([p[1] for p in pts])
            se, sn = latlon_to_utm(slats, slons, utm_zone)
            stream_segs.append(np.column_stack([se, sn]))
        if stream_segs:
            lc_streams = LineCollection(
                stream_segs,
                colors="#2563eb",
                linewidths=0.75,
                alpha=0.85,
                zorder=1.6
            )
            ax.add_collection(lc_streams)

    if water_data.get("rivers"):
        river_segs = []
        for pts in water_data["rivers"]:
            rlats = np.array([p[0] for p in pts])
            rlons = np.array([p[1] for p in pts])
            re, rn = latlon_to_utm(rlats, rlons, utm_zone)
            river_segs.append(np.column_stack([re, rn]))
        if river_segs:
            lc_rivers = LineCollection(
                river_segs,
                colors="#1d4ed8",
                linewidths=1.4,
                alpha=0.92,
                zorder=1.7
            )
            ax.add_collection(lc_rivers)

    # 1. Plot Elevation Contours ONLY (100m contours + bold index contours)
    reg_step = cfg["contours"]["regular_interval_m"]
    idx_step = cfg["contours"]["index_interval_m"]
    z_min = math.floor(float(np.min(dem_smooth)) / idx_step) * idx_step
    z_max = math.ceil(float(np.max(dem_smooth)) / idx_step) * idx_step

    reg_levels = [z for z in range(int(z_min), int(z_max) + reg_step, reg_step) if z % idx_step != 0]
    idx_levels = list(range(int(z_min), int(z_max) + idx_step, idx_step))

    if reg_levels:
        cs_reg = ax.contour(
            dem_e, dem_n, dem_smooth,
            levels=reg_levels,
            colors=cfg["contours"]["regular_color"],
            linewidths=cfg["contours"]["regular_linewidth"],
            alpha=0.78,
            zorder=2
        )
        if reg_step >= 100:
            ax.clabel(
                cs_reg,
                inline=True,
                fontsize=cfg["contours"]["label_fontsize"] - 0.5,
                fmt="%d m",
                colors=cfg["contours"]["regular_color"]
            )
    cs_idx = ax.contour(
        dem_e, dem_n, dem_smooth,
        levels=idx_levels,
        colors=cfg["contours"]["index_color"],
        linewidths=cfg["contours"]["index_linewidth"],
        alpha=0.95,
        zorder=3
    )
    ax.clabel(
        cs_idx,
        inline=True,
        fontsize=cfg["contours"]["label_fontsize"],
        fmt="%d m",
        colors=cfg["contours"]["index_color"]
    )

    # 2. Plot Real OpenStreetMap Roads ONLY
    road_styles = cfg["roads_source"]["styles"]
    for category, polylines in roads_latlon.items():
        if not polylines:
            continue
        style = road_styles[category]
        segments = []
        for poly in polylines:
            rlats = np.array([p[0] for p in poly])
            rlons = np.array([p[1] for p in poly])
            re, rn = latlon_to_utm(rlats, rlons, utm_zone)
            segments.append(np.column_stack([re, rn]))
        lc = LineCollection(
            segments,
            colors=style["color"],
            linewidths=style["linewidth"],
            linestyles=style["linestyle"],
            zorder=4
        )
        ax.add_collection(lc)

    # 3. Plot 1 km & 5 km UTM Coordinate Grid
    minor_step = cfg["utm_grid"]["minor_step_m"]
    major_step = cfg["utm_grid"]["major_step_m"]

    e_ticks = np.arange(e_min, e_max + 1, minor_step)
    n_ticks = np.arange(n_min, n_max + 1, minor_step)

    for et in e_ticks:
        is_major = (int(round(et)) % major_step == 0)
        ax.axvline(
            et,
            color=cfg["utm_grid"]["major_color"] if is_major else cfg["utm_grid"]["minor_color"],
            linewidth=cfg["utm_grid"]["major_linewidth"] if is_major else cfg["utm_grid"]["minor_linewidth"],
            alpha=cfg["utm_grid"]["major_alpha"] if is_major else cfg["utm_grid"]["minor_alpha"],
            zorder=5
        )

    for nt in n_ticks:
        is_major = (int(round(nt)) % major_step == 0)
        ax.axhline(
            nt,
            color=cfg["utm_grid"]["major_color"] if is_major else cfg["utm_grid"]["minor_color"],
            linewidth=cfg["utm_grid"]["major_linewidth"] if is_major else cfg["utm_grid"]["minor_linewidth"],
            alpha=cfg["utm_grid"]["major_alpha"] if is_major else cfg["utm_grid"]["minor_alpha"],
            zorder=5
        )

    # Format UTM Grid Labels (2-digit tactical km on every 1 km, full meters on every 5 km)
    def fmt_utm_label(val: float) -> str:
        iv = int(round(val))
        km_two = (iv // 1000) % 100
        if iv % major_step == 0:
            return f"{km_two:02d}\n({iv}m)"
        return f"{km_two:02d}"

    ax.set_xticks(e_ticks)
    ax.set_xticklabels([fmt_utm_label(v) for v in e_ticks], fontsize=7, color="#0369a1", fontweight="bold")
    ax.set_yticks(n_ticks)
    ax.set_yticklabels([fmt_utm_label(v) for v in n_ticks], fontsize=7, color="#0369a1", fontweight="bold")
    ax.tick_params(top=True, labeltop=True, right=True, labelright=True, direction="out", length=4, color="#0369a1")

    # 4. Plot GPX Route & Waypoints
    ax.plot(
        trk_e, trk_n,
        color=cfg["gpx_route_style"]["casing_color"],
        linewidth=cfg["gpx_route_style"]["casing_linewidth"],
        solid_capstyle="round",
        zorder=6
    )
    ax.plot(
        trk_e, trk_n,
        color=cfg["gpx_route_style"]["color"],
        linewidth=cfg["gpx_route_style"]["linewidth"],
        solid_capstyle="round",
        label="GPX Route",
        zorder=7
    )

    if waypoints:
        w_lats = np.array([w["lat"] for w in waypoints])
        w_lons = np.array([w["lon"] for w in waypoints])
        we, wn = latlon_to_utm(w_lats, w_lons, utm_zone)
        ax.scatter(we, wn, s=36, c="#dc2626", edgecolors="#ffffff", linewidths=1.2, zorder=8)
        for idx, w in enumerate(waypoints):
            if w["name"]:
                ax.annotate(
                    w["name"],
                    (we[idx], wn[idx]),
                    xytext=(4, 4),
                    textcoords="offset points",
                    fontsize=6.5,
                    fontweight="bold",
                    color="#991b1b",
                    bbox=dict(boxstyle="round,pad=0.15", fc="#ffffff", ec="none", alpha=0.8),
                    zorder=9
                )

    # Map Title & Collar Metadata
    title_str = (
        f"1:50,000 TOPOGRAPHIC CONTOUR, ROAD & UTM NAVIGATION MAP — {route_title}\n"
        f"Projection: WGS84 / UTM Zone {utm_zone}N | Grid: 1,000 m (1 km = 2.0 cm at 1:50,000) | "
        f"Contours: {reg_step}m (Index {idx_step}m) | Buffer: +{buffer_km:.0f} km around GPX ("
        f"{width_m/1000:.0f} km x {height_m/1000:.0f} km)"
    )
    fig.suptitle(title_str, fontsize=11, fontweight="bold", y=0.992, color="#0f172a")

    stem = f"{gpx_path.stem}_{reg_step}m_shaded_water"
    pdf_path = STATE_MAPS_DIR / f"{stem}_1_50000_utm_map.pdf"
    png_path = STATE_MAPS_DIR / f"{stem}_1_50000_utm_map.png"
    html_path = STATE_MAPS_DIR / f"{stem}_1_50000_utm_viewer.html"
    manifest_path = STATE_MAPS_DIR / f"{stem}_map_manifest.json"

    print(f"[RENDER] Saving true-scale 1:50,000 Vector PDF to {pdf_path} ...")
    fig.savefig(pdf_path, format="pdf")
    print(f"[RENDER] Saving High-Res PNG ({dpi} DPI) to {png_path} ...")
    fig.savefig(png_path, format="png", dpi=dpi)
    plt.close(fig)

    # Create Interactive Pan/Zoom HTML Viewer wrapping the PNG + PDF download link
    b64_png = base64.b64encode(png_path.read_bytes()).decode("ascii")
    viewer_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>1:50,000 UTM Contour & Road Map — {route_title}</title>
<style>
  body {{ margin: 0; background: #0f172a; color: #f8fafc; font-family: system-ui, sans-serif; display: flex; flex-direction: column; height: 100vh; }}
  header {{ padding: 12px 20px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }}
  .meta {{ font-size: 13px; color: #cbd5e1; }}
  .btns a, .btns button {{ background: #2563eb; color: #fff; text-decoration: none; border: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; margin-left: 8px; }}
  #viewport {{ flex: 1; overflow: auto; background: #334155; padding: 20px; text-align: center; }}
  #map-img {{ background: #fff; box-shadow: 0 8px 30px rgba(0,0,0,0.5); transition: width 0.15s ease; width: 100%; max-width: none; }}
</style>
</head>
<body>
<header>
  <div>
    <strong>1:50,000 UTM Contour & Road Map: {route_title}</strong>
    <div class="meta">UTM Zone {utm_zone}N | Area: {width_m/1000:.0f} km &times; {height_m/1000:.0f} km (+{buffer_km:.0f} km Buffer) | Contours: {reg_step}m (Index {idx_step}m) | Grid: 1 km / 5 km</div>
  </div>
  <div class="btns">
    <button onclick="setZoom(100)">Fit Screen</button>
    <button onclick="setZoom(200)">200% Zoom</button>
    <button onclick="setZoom(350)">350% Detail</button>
    <a href="{pdf_path.name}" download>Download True 1:50,000 Vector PDF</a>
    <a href="{png_path.name}" download>Download PNG</a>
  </div>
</header>
<div id="viewport">
  <img id="map-img" src="data:image/png;base64,{b64_png}" alt="1:50,000 UTM Contour Map"/>
</div>
<script>
  function setZoom(pct) {{
    document.getElementById('map-img').style.width = pct + '%';
  }}
</script>
</body>
</html>"""
    html_path.write_text(viewer_html, encoding="utf-8")

    manifest = {
        "gpx_input": str(gpx_path),
        "route_title": route_title,
        "scale": "1:50,000 (1 cm = 500 m, 2 cm = 1 km)",
        "utm_zone": f"{utm_zone}N (EPSG:326{utm_zone})",
        "buffer_km": buffer_km,
        "utm_bounds_m": {
            "easting_min": e_min,
            "easting_max": e_max,
            "northing_min": n_min,
            "northing_max": n_max,
            "width_km": width_m / 1000.0,
            "height_km": height_m / 1000.0
        },
        "physical_sheet_cm": {
            "map_frame_width_cm": round(map_w_cm, 2),
            "map_frame_height_cm": round(map_h_cm, 2),
            "total_sheet_width_cm": round(map_w_cm + margin_cm, 2),
            "total_sheet_height_cm": round(map_h_cm + margin_cm, 2)
        },
        "outputs": {
            "vector_pdf": str(pdf_path),
            "raster_png": str(png_path),
            "interactive_viewer_html": str(html_path)
        }
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[DONE] Manifest written to {manifest_path}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a 1:50,000 UTM Contour & Road Map from a GPX file.")
    parser.add_argument("--gpx", required=True, help="Path to the input .gpx file")
    parser.add_argument("--buffer-km", type=float, default=20.0, help="Buffer around GPX in km (default: 20)")
    parser.add_argument("--dpi", type=int, default=180, help="PNG render DPI (default: 180)")
    args = parser.parse_args()
    build_map(Path(args.gpx).resolve(), buffer_km=args.buffer_km, dpi=args.dpi)
