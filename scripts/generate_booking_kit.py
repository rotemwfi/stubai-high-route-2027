#!/usr/bin/env python3
"""
generate_booking_kit.py
Generates hut booking checklists, direct Alpsonline links, and pre-drafted German/English group reservation emails
for 10-15 hikers in September 2027. Writes strictly to /state/.
"""

import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"

BOOKING_DATA = {
    "1": {
        "title": "Winner Route 1 Booking Kit (Franz-Senn, Neue Regensburger, Dresdner, Sulzenau)",
        "huts": [
            {
                "night": "Night 1 — Mon, 06 SEP 2027",
                "name": "Franz-Senn-Hütte (2,147 m)",
                "email": "office@franzsennhuette.at",
                "phone": "+43 5226 2218",
                "website": "https://www.franzsennhuette.at",
                "alpsonline": "https://fsh.alpinenetwork.at/reservieren",
                "room_advice": "Request 2–6 bed rooms (Mehrbettzimmer / Zimmerlager) for 10–15 guests with Half Board (Halbpension)."
            },
            {
                "night": "Night 2 — Tue, 07 SEP 2027",
                "name": "Neue Regensburger Hütte (2,286 m)",
                "email": "info@regensburgerhuette.at",
                "phone": "+43 664 2025070 / +43 5226 2252",
                "website": "https://www.regensburgerhuette.at",
                "alpsonline": "https://www.hut-reservation.org/reservation/book-hut/275/wizard",
                "room_advice": "Request 2–3 four/six-bed rooms (Mehrbettzimmer in the new timber wing) for 10–15 guests with Half Board (Halbpension)."
            },
            {
                "night": "Night 3 — Wed, 08 SEP 2027",
                "name": "Dresdner Hütte (2,308 m)",
                "email": "info@dresdnerhuette.at",
                "phone": "+43 5226 8112",
                "website": "https://www.dresdnerhuette.at",
                "alpsonline": "https://www.hut-reservation.org/reservation/book-hut/692/wizard",
                "room_advice": "Request 3–5 multi-bed rooms (Zimmer mit Dusche/WC or Mehrbettzimmer) with Half Board."
            },
            {
                "night": "Night 4 — Thu, 09 SEP 2027",
                "name": "Sulzenauhütte (2,191 m)",
                "email": "info@sulzenauhuette.at",
                "phone": "+43 5226 2432",
                "website": "https://www.sulzenauhuette.at",
                "alpsonline": "https://www.hut-reservation.org/reservation/book-hut/648/wizard",
                "room_advice": "Request group allocation in Zimmerlager (4–6 bed rooms) with Half Board."
            }
        ]
    },
    "2": {
        "title": "Alternative 2 Booking Kit (Sulzenau, Nürnberger, Bremer, Innsbrucker)",
        "huts": [
            {
                "night": "Night 1 — Mon, 06 SEP 2027",
                "name": "Sulzenauhütte (2,191 m)",
                "email": "info@sulzenauhuette.at",
                "phone": "+43 5226 2432",
                "website": "https://www.sulzenauhuette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=255",
                "room_advice": "Request Zimmerlager (4–6 bed rooms) for 10–15 guests with Half Board."
            },
            {
                "night": "Night 2 — Tue, 07 SEP 2027",
                "name": "Nürnberger Hütte (2,297 m)",
                "email": "info@nuernbergerhuette.at",
                "phone": "+43 5226 2492",
                "website": "https://www.nuernbergerhuette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=199",
                "room_advice": "Request Mehrbettzimmer / Zimmerlager for 10–15 guests with Half Board."
            },
            {
                "night": "Night 3 — Wed, 08 SEP 2027",
                "name": "Bremer Hütte (2,411 m)",
                "email": "info@bremerhuette.at",
                "phone": "+43 5275 51921",
                "website": "https://www.bremerhuette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=32",
                "room_advice": "Smaller historic hut: book immediately when Alpsonline opens (usually Dec/Jan) or email warden early; expect Matratzenlager / Lager."
            },
            {
                "night": "Night 4 — Thu, 09 SEP 2027",
                "name": "Innsbrucker Hütte (2,369 m)",
                "email": "info@innsbrucker-huette.at",
                "phone": "+43 664 4126166",
                "website": "https://www.innsbrucker-huette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=117",
                "room_advice": "Request Mehrbettzimmer / Zimmerlager for 10–15 guests with Half Board."
            }
        ]
    },
    "3": {
        "title": "Alternative 3 Booking Kit (~60 km Grand Traverse: Neue Regensburger, Dresdner, Nürnberger, Bremer / or Franz-Senn + Sulzenau)",
        "huts": [
            {
                "night": "Night 1 — Mon, 06 SEP 2027 (or Night 2 in Variant 3A)",
                "name": "Neue Regensburger Hütte (2,286 m)",
                "email": "info@regensburgerhuette.at",
                "phone": "+43 5226 2252",
                "website": "https://www.regensburgerhuette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=197",
                "room_advice": "Request 2–3 four/six-bed rooms (Mehrbettzimmer in the new timber wing) for 10–15 guests with Half Board."
            },
            {
                "night": "Night 2 — Tue, 07 SEP 2027 (or Night 3 in Variant 3A)",
                "name": "Dresdner Hütte (2,308 m)",
                "email": "info@dresdnerhuette.at",
                "phone": "+43 5226 8112",
                "website": "https://www.dresdnerhuette.at",
                "alpsonline": "https://www.dresdnerhuette.at/de/reservierung/",
                "room_advice": "Request 3–5 multi-bed rooms (Zimmer mit Dusche/WC or Mehrbettzimmer) with Half Board."
            },
            {
                "night": "Night 3 — Wed, 08 SEP 2027 (Variant 3B) / Franz-Senn-Hütte (Variant 3A Night 1)",
                "name": "Nürnberger Hütte (2,297 m) / Franz-Senn-Hütte (2,147 m)",
                "email": "info@nuernbergerhuette.at / office@franzsennhuette.at",
                "phone": "+43 5226 2492 / +43 5226 2218",
                "website": "https://www.nuernbergerhuette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=199",
                "room_advice": "Request Mehrbettzimmer / Zimmerlager for 10–15 guests with Half Board."
            },
            {
                "night": "Night 4 — Thu, 09 SEP 2027 (Variant 3B: Bremer Hütte / Variant 3A: Sulzenauhütte)",
                "name": "Bremer Hütte (2,411 m) / Sulzenauhütte (2,191 m)",
                "email": "info@bremerhuette.at / info@sulzenauhuette.at",
                "phone": "+43 5275 51921 / +43 5226 2432",
                "website": "https://www.bremerhuette.at",
                "alpsonline": "https://www.alpsonline.org/reservation/calendar?hut_id=32",
                "room_advice": "For Bremer Hütte (3B) book early for Lager; for Sulzenauhütte (3A) request 4–6 bed Zimmerlager."
            }
        ]
    }
}


def build_kit(alt_id: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = BOOKING_DATA[alt_id]
    lines = [
        f"# {data['title']}",
        "",
        "## 1. Hut Contact & Reservation Table (Group of 10–15 Friends)",
        "",
        "| Night & Date | Hut Name | Direct Email | Phone | Website / Alpsonline | Room Strategy |",
        "|---|---|---|---|---|---|"
    ]
    for h in data["huts"]:
        lines.append(
            f"| **{h['night']}** | **{h['name']}** | `{h['email']}` | `{h['phone']}` | [Website]({h['website']}) / [Booking]({h['alpsonline']}) | {h['room_advice']} |"
        )

    lines.extend([
        "",
        "## 2. Important Booking Timeline for 10–15 People (2027 Season)",
        "- **Direct Group Email Window**: Send direct group inquiry emails in **October–December 2026** (many wardens pre-allocate group blocks of 10–15 beds before opening public calendars, or will tell you the exact day their 2027 Alpsonline calendar unlocks, typically **late December 2026 / early January 2027**).",
        "- **Alpsonline Tip**: On Alpsonline.org, individual online bookings sometimes cap at 8–10 people per transaction; for 10–15 people, either email the hut directly or split into two bookings (e.g., 7 + 6) if booking via the web portal.",
        "",
        "## 3. Pre-Drafted Group Booking Template (German & English)",
        "```text",
        "Subject: Gruppenreservierung (12-14 Personen) – September 2027 / Stubaier Höhenweg – Rotem Sade",
        "",
        "Sehr geehrtes Hüttenteam,",
        "",
        "wir sind eine Gruppe von 12–14 erfahrenen Bergwanderern (ca. 50 Jahre alt) und planen im September 2027 eine 5-tägige Wanderung auf dem Stubaier Höhenweg.",
        "",
        "Gerne möchten wir bei Ihnen folgende Übernachtung mit Halbpension (HP) anfragen bzw. vormerken:",
        "- Datum: [INSERT DATE, z.B. Montag, 06.09.2027]",
        "- Personenanzahl: ca. 12–14 Personen",
        "- Zimmerwunsch: Nach Möglichkeit Mehrbettzimmer / Zimmerlager (ansonsten Matratzenlager)",
        "- Verpflegung: Halbpension (Abendessen & Frühstück)",
        "",
        "Können Sie diese Gruppenreservierung bereits für uns eintragen oder uns mitteilen, ab wann das Buchungssystem für September 2027 freigeschaltet wird?",
        "",
        "Vielen Dank und herzliche Grüße,",
        "Rotem Sade",
        "```"
    ])

    out_path = STATE_DIR / f"hut_booking_kit_alt{alt_id}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--alternative", choices=["1", "2", "3", "all"], default="all")
    args = parser.parse_args()
    if args.alternative == "all":
        build_kit("1")
        build_kit("2")
        build_kit("3")
    else:
        build_kit(args.alternative)
