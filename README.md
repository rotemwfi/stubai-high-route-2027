# Stubai High Route 2027 (Stubaier Höhenweg)

Interactive Mobile Topographic Web Map, 1:50,000 UTM Zone 32N Print Atlas, and Itinerary Planning Suite for the 5-day Stubai High Route trek in Tyrol, Austria.

---

## 📱 Live Interactive Mobile Map
Open directly on your phone or desktop:
👉 **[Interactive Web Map & Profile Scrubber](https://rotemwfi.github.io/stubai-high-route-2027/)**

### Features
- **Mobile Optimized**: Full-screen responsive map layout with touch-friendly floating action controls.
- **Off-Canvas Navigation Drawer**: Quick jump cards to all overnight huts and stage descriptions.
- **Bidirectional Elevation Profile**:
  - Scrub across the elevation chart with your finger to follow a glowing position marker along the 3D GPX trail.
  - Hover or tap any trail section on the map to inspect the exact profile elevation, distance from trail start, and day-relative stage distance.
- **Live Day & Stage Calculation**: Real-time HUD displaying `Day X (+X.X km) | Tot: XX.X km | Ele: XXXX m | UTM Grid`.
- **GPS "Locate Me"**: Tap `GPS 🎯` to center the map on your live smartphone GPS position with an accuracy circle.
- **UTM Zone 32N Grid**: 1 km coordinate grid toggle for field navigation and paper map cross-referencing.

---

## 🗺️ Topographic Maps & Downloads

| Document | Format | Description |
| :--- | :--- | :--- |
| **[Stubai High Route Complete Map Book (Atlas)](Stubai_High_Route_Complete_Map_Book_Final_Atlas.pdf)** | PDF (7 Pages, 300 DPI) | Complete 1:50,000 scale UTM WGS84 topographic map book (Overview + 5 daily stages + Navigation Guide). |
| **[Master Overview Poster](Stubai_High_Route_Overview_UTM_v3.pdf)** | PDF (A3 / Poster) | High-resolution overview of the full 50.2 km route across the Stubai Alps. |
| **[GPS Route Track](export.gpx)** | GPX File | Full GPX track with all stage waypoints, overnight huts, and elevation data for Garmin / Suunto / Komoot / AllTrails. |

---

## 🏔️ 5-Day Trek Itinerary

- **Day 1**: Oberissalm / Seduck ➔ **Franz-Senn-Hütte** (2,147 m) • *10.26 km*
- **Day 2**: Franz-Senn-Hütte ➔ **Neue Regensburger Hütte** (2,286 m) via Schrimmennieder • *9.25 km*
- **Day 3**: Neue Regensburger Hütte ➔ **Dresdner Hütte** (2,308 m) via Grawagrubennieder • *12.49 km*
- **Day 4**: Dresdner Hütte ➔ **Sulzenauhütte** (2,191 m) via Peiljoch • *6.02 km*
- **Day 5**: Sulzenauhütte ➔ **Nürnberger Hütte** (2,278 m) & descent to Bsuchalm / Ranalt • *12.18 km*

---

## 🛠️ Local Development & Regeneration

To regenerate the maps or interactive viewer:
```bash
# Build the interactive mobile HTML map
python scripts/build_interactive_viewer_open_circles.py

# Build the complete 7-page 300 DPI UTM PDF Atlas
python scripts/build_complete_map_book.py
```
