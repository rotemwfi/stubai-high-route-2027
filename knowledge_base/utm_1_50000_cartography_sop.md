# 1:50,000 Topographic & UTM Contour Map Builder — Standard Operating Procedure (SOP)

## 1. Purpose & Design Philosophy
This SOP governs the generation of **1:50,000 scale navigation maps** from any user-supplied `.gpx` file.
The map is intentionally designed with **extreme cartographic clarity** (military/alpine navigation style), showing **ONLY**:
1. **Elevation Contours** (derived from real-world Digital Elevation Model data fetched from the web)
2. **Roads & Vehicle Tracks** (derived from real-world OpenStreetMap highway data via Overpass API)
3. **UTM Coordinate Grid** (WGS84 / Universal Transverse Mercator in meters, with 1 km and 5 km grid lines)
4. **The User's GPX Route & Waypoints**

All visual clutter (forest shading, building footprints, commercial POIs, land-use polygons, tourist icons) is **strictly excluded** to keep the map ultra-legible for terrain reading and compass/UTM navigation.

---

## 2. True 1:50,000 Scale & +20 km Buffer Geometry

### Bounding Box Calculation
1. Parse all `<trkpt>`, `<rtept>`, and `<wpt>` coordinates from the input `.gpx` file.
2. Determine the appropriate **UTM Zone** from the mean longitude of the GPX track:
   $$\text{Zone} = \lfloor (\text{lon}_{\text{mean}} + 180) / 6 \rfloor + 1$$
   *(For the Stubai Alps around $11.2^\circ\text{E}, 47.0^\circ\text{N}$, this is **UTM Zone 32N / EPSG:32632**).*
3. Project all GPX points to **UTM Easting ($E$) and Northing ($N$)** in meters.
4. Expand the GPX bounding box by **+20,000 meters (+20 km)** in all four directions:
   - $E_{\min} = \lfloor (E_{\text{gpx,min}} - 20000) / 1000 \rfloor \times 1000$
   - $E_{\max} = \lceil (E_{\text{gpx,max}} + 20000) / 1000 \rceil \times 1000$
   - $N_{\min} = \lfloor (N_{\text{gpx,min}} - 20000) / 1000 \rfloor \times 1000$
   - $N_{\max} = \lceil (N_{\text{gpx,max}} + 20000) / 1000 \rceil \times 1000$

### Physical Scale Enforcement (1:50,000)
- At **1:50,000 scale**, $1\text{ cm}$ on the map equals $500\text{ m}$ ($0.5\text{ km}$) on the ground, so each **$1\text{ km} \times 1\text{ km}$ UTM grid square measures exactly $2.0\text{ cm} \times 2.0\text{ cm}$** on the exported PDF/vector sheet.
- The script computes the exact physical page size (including map collar/margins for UTM coordinate labels, title block, legend, and scale bar) so printing at 100% scale yields an exact 1:50,000 map.

---

## 3. Real Web Data Sources

1. **Elevation Contours (AWS Open Data Terrain Tiles — Terrarium DEM)**:
   - Fetched directly from `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`.
   - Decoded into floating-point meters via:
     $$\text{Elevation (m)} = (R \times 256 + G + B / 256) - 32768$$
   - Reprojected into UTM coordinates and contoured at:
     - **Regular contours**: Every **25 m** (or 20 m), thin topographic brown (`#b4693c`).
     - **Index contours**: Every **100 m**, bold topographic brown (`#8c461e`) with inline elevation labels in meters.

2. **Roads & Tracks (OpenStreetMap Overpass API)**:
   - Queries only `way["highway"]` features inside the expanded bounding box:
     - **Main / Regional Roads** (`motorway`, `trunk`, `primary`, `secondary`): Solid dark slate lines.
     - **Local / Valley Roads** (`tertiary`, `unclassified`, `residential`): Medium solid lines.
     - **Mountain / Forest Tracks** (`track`, `service`): Fine dashed lines.

3. **UTM Grid Overlay**:
   - **1 km Minor Grid**: Thin cyan/blue grid lines (`1,000 m` spacing) with 2-digit kilometer labels (e.g., `68`, `69`, `70`) along all four borders.
   - **5 km Major Grid**: Bold cyan/blue grid lines (`5,000 m` spacing) with full UTM meter coordinates (e.g., `665000m E`, `5210000m N`).
