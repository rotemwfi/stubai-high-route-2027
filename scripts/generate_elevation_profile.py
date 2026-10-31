#!/usr/bin/env python3
"""
generate_elevation_profile.py
Generates interactive HTML/SVG elevation graphs and CSV stage tables for all Stubai High Trail alternatives
using the MAIN TRAIL PASSES ONLY (without optional peak detours) and calibrated against the group's
Alta Via 1 GPS benchmark (52.50 km | +2,571 m ascent | 19-21 hrs | 2,603 m max elevation).
Writes outputs strictly to the /state/ directory.
"""

import argparse
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"

ROUTES = {
    "1": {
        "name": "Alternative 1 (Calibrated Alta Via 1 Match): 4 Luxury Huts & WildeWasser Exit (47.5 km)",
        "subtitle": "Mon Sept 6 – Fri Sept 10, 2027 | 20–21 hrs Total | +2,820m Ascent (vs +2,571m on AV1) | Avg Daily Max: 2,562m | All 4.5★–5★ Huts",
        "total_km": 47.5,
        "total_ascent": 2820,
        "total_descent": 3350,
        "total_hours": "20–21.5 hrs",
        "max_elev": 2880,
        "avg_max_elev": 2562,
        "transit_in": "Day 1: Innsbruck Hbf → Bus 590 (40m) to Neustift → Schöpf Hut Taxi (20m) to Oberissalm (1,742m, luggage lift to Franz-Senn!)",
        "transit_out": "Day 5: Scenic WildeWasserWeg descent past Grawa Waterfall to Falbeson/Ranalt → Bus 590 (50m) straight to Innsbruck Hbf",
        "waypoints": [
            {"day": "Day 1 (Start)", "label": "Oberissalm Taxi", "km": 0.0, "elev": 1742, "type": "start"},
            {"day": "Day 1", "label": "Franz-Senn-Hütte", "km": 4.5, "elev": 2147, "type": "pass"},
            {"day": "Day 1 (Max)", "label": "Alpeiner Glacier Valley Walk", "km": 6.5, "elev": 2350, "type": "peak"},
            {"day": "Day 1 (Night 1)", "label": "Franz-Senn-Hütte", "km": 8.5, "elev": 2147, "type": "hut"},
            {"day": "Day 2 (Max)", "label": "Schrimmennieder Pass", "km": 13.5, "elev": 2714, "type": "peak"},
            {"day": "Day 2 (Night 2)", "label": "Neue Regensburger Hütte", "km": 18.0, "elev": 2286, "type": "hut"},
            {"day": "Day 3", "label": "Hohes Moos", "km": 21.5, "elev": 2450, "type": "pass"},
            {"day": "Day 3 (Max)", "label": "Grawagrubennieder Pass", "km": 25.0, "elev": 2880, "type": "peak"},
            {"day": "Day 3 (Night 3)", "label": "Dresdner Hütte", "km": 29.5, "elev": 2308, "type": "hut"},
            {"day": "Day 4 (Max)", "label": "Peiljoch Pass", "km": 32.0, "elev": 2676, "type": "peak"},
            {"day": "Day 4", "label": "Blaue Lacke", "km": 34.5, "elev": 2290, "type": "pass"},
            {"day": "Day 4 (Night 4)", "label": "Sulzenauhütte", "km": 37.0, "elev": 2191, "type": "hut"},
            {"day": "Day 5", "label": "Grawa Waterfall", "km": 42.5, "elev": 1530, "type": "pass"},
            {"day": "Day 5 (End)", "label": "Falbeson (WildeWasserWeg)", "km": 47.5, "elev": 1220, "type": "end"}
        ],
        "stages": [
            {"Day": "Day 1 (Mon 06 Sep)", "Stage": "Innsbruck → Oberissalm Taxi (Luggage Lift) → Franz-Senn-Hütte + Afternoon Alpeiner Valley Walk", "Distance_km": 8.5, "Max_Elev_m": "2,350 m (Alpeiner Valley)", "Ascent_m": 610, "Descent_m": 210, "Hours": "3.5", "Hut": "Franz-Senn-Hütte (2,147m) [4.5★]", "Grade": "T2"},
            {"Day": "Day 2 (Tue 07 Sep)", "Stage": "Franz-Senn-Hütte → Schrimmennieder Pass (Main Trail) → Neue Regensburger Hütte", "Distance_km": 9.5, "Max_Elev_m": "2,714 m (Schrimmennieder)", "Ascent_m": 760, "Descent_m": 620, "Hours": "4.0–4.5", "Hut": "Neue Regensburger Hütte (2,286m) [5★]", "Grade": "T3"},
            {"Day": "Day 3 (Wed 08 Sep)", "Stage": "Neue Regensburger Hütte → Hohes Moos → Grawagrubennieder Pass → Dresdner Hütte (Sauna)", "Distance_km": 11.5, "Max_Elev_m": "2,880 m (Grawagrubennieder)", "Ascent_m": 880, "Descent_m": 860, "Hours": "5.0–5.5", "Hut": "Dresdner Hütte (2,308m) [5★]", "Grade": "T3+"},
            {"Day": "Day 4 (Thu 09 Sep)", "Stage": "Dresdner Hütte → Peiljoch Pass (Main Trail) → Blaue Lacke Lake → Sulzenauhütte", "Distance_km": 7.5, "Max_Elev_m": "2,676 m (Peiljoch)", "Ascent_m": 450, "Descent_m": 570, "Hours": "3.5–4.0", "Hut": "Sulzenauhütte (2,191m) [4.5★]", "Grade": "T3"},
            {"Day": "Day 5 (Fri 10 Sep)", "Stage": "Sulzenauhütte → Sulzenaualm → Grawa Waterfall → WildeWasserWeg Canyon Trail to Falbeson → Bus 590", "Distance_km": 10.5, "Max_Elev_m": "2,191 m (Sulzenauhütte)", "Ascent_m": 120, "Descent_m": 1090, "Hours": "3.5–4.0", "Hut": "Return to Innsbruck", "Grade": "T2"}
        ]
    },
    "1H": {
        "name": "Alternative 1-Hub: 2-Night Dresdner Hütte Hub + WildeWasser Exit (46.5 km)",
        "subtitle": "Mon Sept 6 – Fri Sept 10, 2027 | 20–22 hrs Total | +2,920m Ascent | 3 Luxury Huts (4.5★–5★) with Slackpack Day 3",
        "total_km": 46.5,
        "total_ascent": 2920,
        "total_descent": 3440,
        "total_hours": "20–22 hrs",
        "max_elev": 2880,
        "avg_max_elev": 2618,
        "transit_in": "Day 1: Innsbruck Hbf → Bus 590 (40m) to Neustift → Schöpf Hut Taxi (20m) to Oberissalm (1,742m)",
        "transit_out": "Day 5: WildeWasserWeg descent past Grawa Waterfall to Falbeson → Bus 590 (50m) straight to Innsbruck Hbf",
        "waypoints": [
            {"day": "Day 1 (Start)", "label": "Oberissalm Taxi", "km": 0.0, "elev": 1742, "type": "start"},
            {"day": "Day 1", "label": "Franz-Senn-Hütte", "km": 4.5, "elev": 2147, "type": "pass"},
            {"day": "Day 1 (Max)", "label": "Schrimmennieder Pass", "km": 9.5, "elev": 2714, "type": "peak"},
            {"day": "Day 1 (Night 1)", "label": "Neue Regensburger Hütte", "km": 14.0, "elev": 2286, "type": "hut"},
            {"day": "Day 2", "label": "Hohes Moos", "km": 17.5, "elev": 2450, "type": "pass"},
            {"day": "Day 2 (Max)", "label": "Grawagrubennieder Pass", "km": 21.0, "elev": 2880, "type": "peak"},
            {"day": "Day 2 (Night 2)", "label": "Dresdner Hütte (Hub 1)", "km": 25.5, "elev": 2308, "type": "hut"},
            {"day": "Day 3 (Slackpack)", "label": "Egesengrat / Fernau Loop", "km": 28.5, "elev": 2631, "type": "peak"},
            {"day": "Day 3 (Night 3)", "label": "Dresdner Hütte (Hub 2)", "km": 31.5, "elev": 2308, "type": "hut"},
            {"day": "Day 4 (Max)", "label": "Peiljoch Pass", "km": 34.0, "elev": 2676, "type": "peak"},
            {"day": "Day 4", "label": "Blaue Lacke", "km": 35.5, "elev": 2290, "type": "pass"},
            {"day": "Day 4 (Night 4)", "label": "Sulzenauhütte", "km": 37.0, "elev": 2191, "type": "hut"},
            {"day": "Day 5", "label": "Grawa Waterfall", "km": 42.5, "elev": 1530, "type": "pass"},
            {"day": "Day 5 (End)", "label": "Falbeson (WildeWasserWeg)", "km": 46.5, "elev": 1220, "type": "end"}
        ],
        "stages": [
            {"Day": "Day 1 (Mon 06 Sep)", "Stage": "Innsbruck → Oberissalm Taxi → Franz-Senn → Schrimmennieder Pass → Neue Regensburger Hütte", "Distance_km": 14.0, "Max_Elev_m": "2,714 m (Schrimmennieder)", "Ascent_m": 1170, "Descent_m": 620, "Hours": "5.5–6.0", "Hut": "Neue Regensburger Hütte (2,286m) [5★]", "Grade": "T3"},
            {"Day": "Day 2 (Tue 07 Sep)", "Stage": "Neue Regensburger Hütte → Hohes Moos → Grawagrubennieder Pass → Dresdner Hütte", "Distance_km": 11.5, "Max_Elev_m": "2,880 m (Grawagrubennieder)", "Ascent_m": 880, "Descent_m": 860, "Hours": "5.0–5.5", "Hut": "Dresdner Hütte (2,308m) [5★ Night 1/2]", "Grade": "T3+"},
            {"Day": "Day 3 (Wed 08 Sep)", "Stage": "Slackpack Hub Day: Egesengrat Panoramic Trail (or Optional Fernau Via Ferrata + Sauna)", "Distance_km": 6.0, "Max_Elev_m": "2,631 m (Egesengrat)", "Ascent_m": 320, "Descent_m": 320, "Hours": "3.0–3.5", "Hut": "Dresdner Hütte (2,308m) [5★ Night 2/2]", "Grade": "T2 (Opt. Ferrata)"},
            {"Day": "Day 4 (Thu 09 Sep)", "Stage": "Dresdner Hütte → Peiljoch Pass (Main Trail) → Blaue Lacke → Sulzenauhütte", "Distance_km": 5.5, "Max_Elev_m": "2,676 m (Peiljoch)", "Ascent_m": 450, "Descent_m": 570, "Hours": "3.0–3.5", "Hut": "Sulzenauhütte (2,191m) [4.5★]", "Grade": "T3"},
            {"Day": "Day 5 (Fri 10 Sep)", "Stage": "Sulzenauhütte → WildeWasserWeg & Grawa Waterfall → Canyon Trail to Falbeson → Bus 590", "Distance_km": 9.5, "Max_Elev_m": "2,191 m (Sulzenauhütte)", "Ascent_m": 100, "Descent_m": 1070, "Hours": "3.5", "Hut": "Return to Innsbruck", "Grade": "T2"}
        ]
    },
    "2": {
        "name": "Alternative 2 (Main Trail Only): Classic Eastern Traverse (37.5 km)",
        "subtitle": "Mon Sept 6 – Fri Sept 10, 2027 | 19–22 hrs Total | +2,790m Ascent (vs +2,571m on AV1) | Max Daily Pass: 2,370m – 2,754m",
        "total_km": 37.5,
        "total_ascent": 2790,
        "total_descent": 3350,
        "total_hours": "19–22 hrs",
        "max_elev": 2754,
        "avg_max_elev": 2630,
        "transit_in": "Day 1: Innsbruck Hbf → Bus 590 (65m) to Mutterbergalm → Stubaier Gletscherbahn Gondola (10m) to Dresdner Hütte (2,308m)",
        "transit_out": "Day 5: Panorama Trail to Elferbahnen Gondola (or Karalm Shuttle Taxi) → Neustift → Bus 590 to Innsbruck Hbf (40m)",
        "waypoints": [
            {"day": "Day 1 (Start)", "label": "Dresdner Hütte (Gondola)", "km": 0.0, "elev": 2308, "type": "start"},
            {"day": "Day 1 (Max)", "label": "Peiljoch Pass", "km": 2.5, "elev": 2676, "type": "peak"},
            {"day": "Day 1", "label": "Blaue Lacke", "km": 4.0, "elev": 2290, "type": "pass"},
            {"day": "Day 1 (Night 1)", "label": "Sulzenauhütte", "km": 5.5, "elev": 2191, "type": "hut"},
            {"day": "Day 2 (Max)", "label": "Niederl Pass", "km": 9.0, "elev": 2629, "type": "peak"},
            {"day": "Day 2 (Night 2)", "label": "Nürnberger Hütte", "km": 12.0, "elev": 2297, "type": "hut"},
            {"day": "Day 3 (Max)", "label": "Simmingjöchl Pass", "km": 16.5, "elev": 2754, "type": "peak"},
            {"day": "Day 3 (Night 3)", "label": "Bremer Hütte", "km": 20.5, "elev": 2411, "type": "hut"},
            {"day": "Day 4 (Max)", "label": "Pramarnspitze Pass", "km": 24.5, "elev": 2720, "type": "peak"},
            {"day": "Day 4 (Night 4)", "label": "Innsbrucker Hütte", "km": 30.0, "elev": 2369, "type": "hut"},
            {"day": "Day 5 (Max)", "label": "Pinnisjoch Panorama Trail", "km": 33.5, "elev": 2370, "type": "pass"},
            {"day": "Day 5 (End)", "label": "Elferbahnen Gondola / Karalm", "km": 37.5, "elev": 1790, "type": "end"}
        ],
        "stages": [
            {"Day": "Day 1 (Mon 06 Sep)", "Stage": "Innsbruck → Gletscherbahn to Dresdner Hütte → Peiljoch Pass (Main Trail) → Blaue Lacke → Sulzenauhütte", "Distance_km": 5.5, "Max_Elev_m": "2,676 m (Peiljoch)", "Ascent_m": 450, "Descent_m": 570, "Hours": "3.0–3.5", "Hut": "Sulzenauhütte (2,191m) [4.5★]", "Grade": "T3"},
            {"Day": "Day 2 (Tue 07 Sep)", "Stage": "Sulzenauhütte → Grünausee → Niederl Pass (Main Trail) → Nürnberger Hütte", "Distance_km": 6.5, "Max_Elev_m": "2,629 m (Niederl)", "Ascent_m": 650, "Descent_m": 540, "Hours": "3.5–4.0", "Hut": "Nürnberger Hütte (2,297m) [4★]", "Grade": "T3"},
            {"Day": "Day 3 (Wed 08 Sep)", "Stage": "Nürnberger Hütte → Paradies Glacier Slabs → Simmingjöchl Pass → Bremer Hütte", "Distance_km": 8.5, "Max_Elev_m": "2,754 m (Simmingjöchl)", "Ascent_m": 680, "Descent_m": 570, "Hours": "4.0–4.5", "Hut": "Bremer Hütte (2,411m) [3★ Rustic]", "Grade": "T3+"},
            {"Day": "Day 4 (Thu 09 Sep)", "Stage": "Queen Stage: Bremer Hütte → Pramarnspitze Pass (Cables) → Sendesgrat → Innsbrucker Hütte", "Distance_km": 9.5, "Max_Elev_m": "2,720 m (Pramarnspitze)", "Ascent_m": 880, "Descent_m": 920, "Hours": "6.0–7.0", "Hut": "Innsbrucker Hütte (2,369m) [4.5★]", "Grade": "T4 (Black)"},
            {"Day": "Day 5 (Fri 10 Sep)", "Stage": "Innsbrucker Hütte → Scenic Pinnisjoch Panorama Trail → Elferbahnen Gondola (or Karalm Taxi) → Innsbruck", "Distance_km": 7.5, "Max_Elev_m": "2,370 m (Pinnisjoch)", "Ascent_m": 130, "Descent_m": 750, "Hours": "2.5–3.0", "Hut": "Return to Innsbruck", "Grade": "T2/T3"}
        ]
    },
    "3A": {
        "name": "Alternative 3A (Main Trail Only): 56.5 km High-Comfort Traverse (6 Huts • All 4.5★–5★ Huts)",
        "subtitle": "Mon Sept 6 – Fri Sept 10, 2027 | 24–26.5 hrs Total | +3,760m Ascent | Max Daily Pass: 2,400m – 2,880m",
        "total_km": 56.5,
        "total_ascent": 3760,
        "total_descent": 4650,
        "total_hours": "24–26.5 hrs",
        "max_elev": 2880,
        "avg_max_elev": 2660,
        "transit_in": "Day 1: Innsbruck Hbf → Bus 590 (30m) or STB Tram to Fulpmes → Schlick 2000 Kreuzjochbahn Gondola to 2,136m",
        "transit_out": "Day 5: Descent from Nürnberger Hütte to Bärenbad/Neder → Bus 590 (45m) straight to Innsbruck Hbf",
        "waypoints": [
            {"day": "Day 1 (Start)", "label": "Schlick 2000 Gondola", "km": 0.0, "elev": 2136, "type": "start"},
            {"day": "Day 1", "label": "Starkenburger Hütte", "km": 3.5, "elev": 2237, "type": "pass"},
            {"day": "Day 1 (Max)", "label": "Seducker Hochalm High Point", "km": 11.0, "elev": 2400, "type": "peak"},
            {"day": "Day 1 (Night 1)", "label": "Franz-Senn-Hütte", "km": 18.5, "elev": 2147, "type": "hut"},
            {"day": "Day 2 (Max)", "label": "Schrimmennieder Pass", "km": 23.5, "elev": 2714, "type": "peak"},
            {"day": "Day 2 (Night 2)", "label": "Neue Regensburger Hütte", "km": 28.0, "elev": 2286, "type": "hut"},
            {"day": "Day 3 (Max)", "label": "Grawagrubennieder Pass", "km": 35.0, "elev": 2880, "type": "peak"},
            {"day": "Day 3 (Night 3)", "label": "Dresdner Hütte", "km": 39.5, "elev": 2308, "type": "hut"},
            {"day": "Day 4 (Max)", "label": "Peiljoch Pass", "km": 42.0, "elev": 2676, "type": "peak"},
            {"day": "Day 4", "label": "Blaue Lacke", "km": 43.5, "elev": 2290, "type": "pass"},
            {"day": "Day 4 (Night 4)", "label": "Sulzenauhütte", "km": 45.0, "elev": 2191, "type": "hut"},
            {"day": "Day 5 (Max)", "label": "Niederl Pass", "km": 48.5, "elev": 2629, "type": "peak"},
            {"day": "Day 5", "label": "Nürnberger Hütte (Lunch)", "km": 51.0, "elev": 2297, "type": "pass"},
            {"day": "Day 5 (End)", "label": "Bärenbad / Neder (Bus 590)", "km": 56.5, "elev": 1250, "type": "end"}
        ],
        "stages": [
            {"Day": "Day 1 (Mon 06 Sep)", "Stage": "Innsbruck → Schlick 2000 Gondola (2,136m) → Starkenburger Hütte → Seducker Hochalm → Franz-Senn-Hütte", "Distance_km": 18.5, "Max_Elev_m": "2,400 m (Seducker High Trail)", "Ascent_m": 1020, "Descent_m": 1010, "Hours": "6.5–7.0", "Hut": "Franz-Senn-Hütte (2,147m) [4.5★]", "Grade": "T3"},
            {"Day": "Day 2 (Tue 07 Sep)", "Stage": "Franz-Senn-Hütte → Schrimmennieder Pass (Main Trail) → Neue Regensburger Hütte", "Distance_km": 9.5, "Max_Elev_m": "2,714 m (Schrimmennieder)", "Ascent_m": 760, "Descent_m": 620, "Hours": "4.0–4.5", "Hut": "Neue Regensburger Hütte (2,286m) [5★]", "Grade": "T3"},
            {"Day": "Day 3 (Wed 08 Sep)", "Stage": "Neue Regensburger Hütte → Hohes Moos → Grawagrubennieder Pass → Dresdner Hütte", "Distance_km": 11.5, "Max_Elev_m": "2,880 m (Grawagrubennieder)", "Ascent_m": 880, "Descent_m": 860, "Hours": "5.5–6.0", "Hut": "Dresdner Hütte (2,308m) [5★]", "Grade": "T3+"},
            {"Day": "Day 4 (Thu 09 Sep)", "Stage": "Dresdner Hütte → Peiljoch Pass (Main Trail) → Blaue Lacke → Sulzenauhütte", "Distance_km": 5.5, "Max_Elev_m": "2,676 m (Peiljoch)", "Ascent_m": 450, "Descent_m": 570, "Hours": "3.0–3.5", "Hut": "Sulzenauhütte (2,191m) [4.5★]", "Grade": "T3"},
            {"Day": "Day 5 (Fri 10 Sep)", "Stage": "Sulzenauhütte → Grünausee → Niederl Pass (Main Trail) → Nürnberger Hütte (Lunch) → Bärenbad (Bus 590)", "Distance_km": 11.5, "Max_Elev_m": "2,629 m (Niederl)", "Ascent_m": 650, "Descent_m": 1590, "Hours": "5.0–5.5", "Hut": "Return to Innsbruck", "Grade": "T3"}
        ]
    }
}


def generate_outputs(alt_id: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    route = ROUTES[alt_id]
    waypoints = route["waypoints"]
    stages = route["stages"]

    # 1. Write CSV
    csv_path = STATE_DIR / f"route_stages_alt{alt_id}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Day", "Stage", "Distance_km", "Max_Elev_m", "Ascent_m", "Descent_m", "Hours", "Hut", "Grade"])
        writer.writeheader()
        writer.writerows(stages)

    # 2. Generate SVG/HTML Elevation Profile
    max_km = max(w["km"] for w in waypoints)
    min_elev = 1000
    max_elev = 3200
    width, height = 1050, 440
    pad_l, pad_r, pad_t, pad_b = 70, 60, 55, 85
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def x_coord(km: float) -> float:
        return pad_l + (km / max_km) * plot_w

    def y_coord(elev: float) -> float:
        return pad_t + plot_h - ((elev - min_elev) / (max_elev - min_elev)) * plot_h

    points_str = " ".join(f"{x_coord(w['km']):.1f},{y_coord(w['elev']):.1f}" for w in waypoints)
    area_str = f"{x_coord(0):.1f},{pad_t + plot_h} " + points_str + f" {x_coord(max_km):.1f},{pad_t + plot_h}"

    # Reference line for Alta Via 1 max pass (2,603m from group screenshot)
    av1_y = y_coord(2603)
    av1_line_svg = (
        f'<line x1="{pad_l}" y1="{av1_y:.1f}" x2="{width-pad_r}" y2="{av1_y:.1f}" stroke="#16a34a" stroke-dasharray="6,4" stroke-width="1.8"/>'
        f'<text x="{width-pad_r-6}" y="{av1_y-6:.1f}" text-anchor="end" font-size="11" font-weight="600" fill="#15803d">Your Alta Via 1 Max Elevation (2,603m | 52.5km | +2,571m | 19-21h)</text>'
    )

    # Vertical dashed day dividers for overnight huts
    hut_lines_svg = []
    for w in waypoints:
        if w["type"] == "hut":
            cx, cy = x_coord(w["km"]), y_coord(w["elev"])
            hut_lines_svg.append(
                f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{pad_t + plot_h}" stroke="#fda4af" stroke-dasharray="3,3" stroke-width="1.5"/>'
            )

    circles_svg = []
    for idx, w in enumerate(waypoints):
        cx, cy = x_coord(w["km"]), y_coord(w["elev"])
        color = "#e11d48" if w["type"] == "hut" else ("#2563eb" if w["type"] == "peak" else "#0f766e")
        r = 7 if w["type"] in ("hut", "peak") else 5.5
        y_offset = -14 if idx % 2 == 0 else -26
        if w["type"] == "hut":
            y_offset = 22
        circles_svg.append(
            f'<g class="point">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" stroke="#fff" stroke-width="2">'
            f'<title>{w["day"]}: {w["label"]} — {w["elev"]}m (km {w["km"]})</title>'
            f'</circle>'
            f'<text x="{cx:.1f}" y="{cy + y_offset:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="#1e293b">{w["label"]} ({w["elev"]}m)</text>'
            f'</g>'
        )

    # X-axis km ticks
    km_ticks_svg = []
    step = 5 if max_km <= 48 else 10
    for k in range(0, int(max_km) + 1, step):
        kx = x_coord(k)
        km_ticks_svg.append(
            f'<line x1="{kx:.1f}" y1="{pad_t + plot_h}" x2="{kx:.1f}" y2="{pad_t + plot_h + 6}" stroke="#94a3b8"/>'
            f'<text x="{kx:.1f}" y="{pad_t + plot_h + 22}" text-anchor="middle" font-size="11" fill="#64748b">{k} km</text>'
        )

    nav_links = [
        ("1", "★ Alt 1: Calibrated AV1 Match (47.5 km • +2,820m • 4 Luxury Huts)", "elevation_profile_alt1.html"),
        ("1H", "Alt 1-Hub (46.5 km • +2,920m • 2-Night Dresdner Hub)", "elevation_profile_alt1H.html"),
        ("2", "Alt 2: Eastern Traverse (37.5 km • +2,790m • Queen Stage)", "elevation_profile_alt2.html"),
        ("3A", "Alt 3A (56.5 km • +3,760m • 6-Hut Comfort)", "elevation_profile_alt3A.html"),
    ]
    nav_html = "".join(
        f'<a href="{href}" class="nav-pill {"active" if k == alt_id else ""}">{label}</a>'
        for k, label, href in nav_links
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{route["name"]} - Elevation Profile</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #f1f5f9; color: #0f172a; margin: 24px; }}
  .card {{ background: #fff; border-radius: 14px; padding: 28px; box-shadow: 0 4px 20px rgba(0,0,0,0.07); max-width: 1160px; margin: 0 auto; }}
  .nav-bar {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid #e2e8f0; }}
  .nav-pill {{ text-decoration: none; padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; background: #f8fafc; color: #334155; border: 1px solid #cbd5e1; transition: all 0.15s; }}
  .nav-pill:hover {{ background: #e2e8f0; }}
  .nav-pill.active {{ background: #1e40af; color: #fff; border-color: #1e40af; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; color: #0f172a; }}
  p.sub {{ color: #475569; margin: 0 0 18px; font-size: 14px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .kpi {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }}
  .kpi-label {{ font-size: 11.5px; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }}
  .kpi-val {{ font-size: 19px; font-weight: 700; color: #0f172a; margin-top: 4px; }}
  .kpi-sub {{ font-size: 11.5px; color: #15803d; font-weight: 600; margin-top: 2px; }}
  .transit-box {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #1e3a8a; margin-bottom: 18px; line-height: 1.5; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13.5px; }}
  th, td {{ border-bottom: 1px solid #e2e8f0; padding: 11px 10px; text-align: left; }}
  th {{ background: #f1f5f9; font-weight: 600; color: #334155; }}
  tr:hover td {{ background: #f8fafc; }}
  .total-row td {{ font-weight: 700; background: #f8fafc; border-top: 2px solid #cbd5e1; }}
  .av1-row td {{ font-weight: 600; background: #f0fdf4; color: #166534; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 22px; font-size: 13px; margin-bottom: 10px; font-weight: 500; }}
  .dot {{ display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }}
  .elev-badge {{ background: #dbeafe; color: #1e40af; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 12.5px; }}
</style>
</head>
<body>
<div class="card">
  <div class="nav-bar">
    {nav_html}
  </div>
  <h1>{route["name"]}</h1>
  <p class="sub">{route["subtitle"]}</p>
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-label">Total Length</div><div class="kpi-val">{route["total_km"]} km</div><div class="kpi-sub">AV1 was 52.50 km</div></div>
    <div class="kpi"><div class="kpi-label">Total Elev. Gain</div><div class="kpi-val">+{route["total_ascent"]:,} m</div><div class="kpi-sub">AV1 was +2,571 m</div></div>
    <div class="kpi"><div class="kpi-label">Est. Walking Time</div><div class="kpi-val">{route["total_hours"]}</div><div class="kpi-sub">AV1 was 19–21 hrs</div></div>
    <div class="kpi"><div class="kpi-label">Avg Daily Max Elev</div><div class="kpi-val">{route["avg_max_elev"]:,} m</div><div class="kpi-sub">AV1 Max was 2,603 m</div></div>
    <div class="kpi"><div class="kpi-label">Hut Sleeping Altitude</div><div class="kpi-val">2,147–2,308 m</div><div class="kpi-sub">Comfortable Oxygen Zone</div></div>
  </div>
  <div class="transit-box">
    <strong>Innsbruck Transit In:</strong> {route["transit_in"]}<br>
    <strong>Innsbruck Transit Out:</strong> {route["transit_out"]}
  </div>
  <div class="legend">
    <span><span class="dot" style="background:#e11d48"></span>Overnight Hut (Labels Below Line)</span>
    <span><span class="dot" style="background:#2563eb"></span>Main Trail Pass (No Peak Detours)</span>
    <span><span class="dot" style="background:#0f766e"></span>Valley Access / Waterfall Waypoint</span>
    <span style="color:#15803d;"><strong>---</strong> Green Dashed Line = Your Alta Via 1 Max Elevation (2,603m)</span>
  </div>
  <svg viewBox="0 0 {width} {height}" width="100%" height="auto">
    <defs>
      <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.03"/>
      </linearGradient>
    </defs>
    <!-- Grid lines -->
    {"".join(f'<line x1="{pad_l}" y1="{y_coord(e):.1f}" x2="{width-pad_r}" y2="{y_coord(e):.1f}" stroke="#e2e8f0" stroke-dasharray="4"/><text x="{pad_l-10}" y="{y_coord(e)+4:.1f}" text-anchor="end" font-size="11" fill="#64748b">{e}m</text>' for e in range(1500, 3001, 500))}
    <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{width - pad_r}" y2="{pad_t + plot_h}" stroke="#94a3b8" stroke-width="1.5"/>
    {"".join(km_ticks_svg)}
    <polygon points="{area_str}" fill="url(#grad)"/>
    {av1_line_svg}
    {"".join(hut_lines_svg)}
    <polyline fill="none" stroke="#2563eb" stroke-width="3" points="{points_str}"/>
    {"".join(circles_svg)}
  </svg>
  <table>
    <thead>
      <tr><th>Day</th><th>Main Trail Stage (No Peak Detours)</th><th>Dist (km)</th><th>Daily Max Pass</th><th>Ascent</th><th>Descent</th><th>Time (hrs)</th><th>Overnight Hut & Comfort</th><th>Grade</th></tr>
    </thead>
    <tbody>
      {"".join(f'<tr><td>{s["Day"]}</td><td>{s["Stage"]}</td><td>{s["Distance_km"]} km</td><td><span class="elev-badge">{s["Max_Elev_m"]}</span></td><td>+{s["Ascent_m"]}m</td><td>-{s["Descent_m"]}m</td><td>{s["Hours"]}</td><td><strong>{s["Hut"]}</strong></td><td>{s["Grade"]}</td></tr>' for s in stages)}
      <tr class="total-row">
        <td>STUBAI TOTAL</td>
        <td>5 Continuous Hiking Days (Sept 6 – Sept 10, 2027)</td>
        <td>{route["total_km"]} km</td>
        <td>Avg Max: {route["avg_max_elev"]:,} m (Peak: {route["max_elev"]:,} m)</td>
        <td>+{route["total_ascent"]:,}m</td>
        <td>-{route["total_descent"]:,}m</td>
        <td>{route["total_hours"]}</td>
        <td>4 Hut Nights</td>
        <td>Main Trail</td>
      </tr>
      <tr class="av1-row">
        <td>ALTA VIA 1 BENCHMARK</td>
        <td>Your 2025 Dolomites Trek (from Screenshot)</td>
        <td>52.50 km</td>
        <td>Max: 2,603 m (Min: 1,063 m)</td>
        <td>+2,571m</td>
        <td>—</td>
        <td>19–21 hrs</td>
        <td>4 Hut Nights</td>
        <td>Reference</td>
      </tr>
    </tbody>
  </table>
</div>
</body>
</html>"""

    html_path = STATE_DIR / f"elevation_profile_alt{alt_id}.html"
    html_path.write_text(html_content, encoding="utf-8")
    print(f"Generated: {html_path} and {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--alternative", choices=["1", "1H", "2", "3A", "all"], default="all")
    args = parser.parse_args()
    if args.alternative == "all":
        for key in ["1", "1H", "2", "3A"]:
            generate_outputs(key)
    else:
        generate_outputs(args.alternative)
