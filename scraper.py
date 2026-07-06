#!/usr/bin/env python3
"""
Liest den eingebetteten Next.js-Datenblock (__NEXT_DATA__) der Yorck-Seite
für das ARTE Sommerkino Kulturforum aus und baut daraus eine ICS-Datei.

Jeder Film hat in der Saison genau eine (oder wenige) Vorstellung(en),
gespeichert unter props.pageProps.filmsSpecials[*].fields.sessions.
Einträge mit einem "type"-Feld (Filmreihe / Special Screening) sind
Wrapper, die dieselbe Session-ID wie der zugehörige Film noch einmal
referenzieren - werden übersprungen, um Dubletten zu vermeiden.
"""

import re
import sys
import json
import hashlib
import datetime as dt
from zoneinfo import ZoneInfo

import requests

URL = "https://www.yorck.de/kinos/sommerkino-kulturforum"
CINEMA_NAME = "ARTE Sommerkino Kulturforum"
DEFAULT_DURATION_MIN = 150
BERLIN_TZ = ZoneInfo("Europe/Berlin")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SommerkinoICSBot/1.0; +https://github.com/)"
}


def fetch_next_data() -> dict:
    resp = requests.get(URL, params={"tab": "daily"}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("__NEXT_DATA__-Block nicht gefunden - hat sich das Seitenlayout geändert?")
    return json.loads(match.group(1))


def extract_entries(data: dict):
    films = data.get("props", {}).get("pageProps", {}).get("filmsSpecials", [])
    entries = []

    for film in films:
        fields = film.get("fields", {})

        # Wrapper-Einträge (Filmreihe / Special Screening) referenzieren
        # dieselbe Session-ID wie der eigentliche Film erneut - überspringen,
        # sonst gibt es Dubletten im Kalender.
        if "type" in fields:
            continue

        title = fields.get("title")
        slug = fields.get("slug")
        runtime = fields.get("runtime")

        for session in fields.get("sessions", []):
            sfields = session.get("fields", {})
            cinema_name = sfields.get("cinema", {}).get("fields", {}).get("name")
            if cinema_name and cinema_name != CINEMA_NAME:
                continue

            start_raw = sfields.get("startTime")
            if not title or not start_raw:
                continue

            start_dt = dt.datetime.fromisoformat(start_raw)
            # Die Website liefert den Offset fälschlich konstant als +01:00,
            # auch während der Sommerzeit (+02:00 wäre korrekt). Wir nehmen
            # daher nur die "Wanduhr"-Zeit und wenden die echte Berliner
            # Zeitzone (inkl. korrekter Sommerzeit-Umstellung) an.
            start_dt = start_dt.replace(tzinfo=None).replace(tzinfo=BERLIN_TZ)
            formats = sfields.get("formats") or []

            entries.append(
                {
                    "title": title,
                    "slug": slug,
                    "runtime": runtime,
                    "start": start_dt,
                    "version": "/".join(formats),
                    "session_id": session.get("sys", {}).get("id"),
                }
            )

    return entries


def make_uid(entry) -> str:
    raw = f"{entry.get('session_id') or entry['start'].isoformat()}-{entry['title']}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@sommerkino-kulturforum"


def escape_ics_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_ics(entries) -> str:
    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sommerkino-kulturforum-ics//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:ARTE Sommerkino Kulturforum",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]

    # nach Startzeit sortieren, damit die ICS-Datei chronologisch ist
    for entry in sorted(entries, key=lambda e: e["start"]):
        start_local = entry["start"]
        duration_min = entry["runtime"] or DEFAULT_DURATION_MIN
        end_local = start_local + dt.timedelta(minutes=duration_min)

        start_utc = start_local.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end_utc = end_local.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        summary = entry["title"]
        if entry["version"]:
            summary += f" ({entry['version']})"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{make_uid(entry)}")
        lines.append(f"DTSTAMP:{now_utc}")
        lines.append(f"DTSTART:{start_utc}")
        lines.append(f"DTEND:{end_utc}")
        lines.append(f"SUMMARY:{escape_ics_text(summary)}")
        lines.append("LOCATION:ARTE Sommerkino Kulturforum\\, Matthäikirchplatz\\, Berlin")
        if entry.get("slug"):
            film_url = f"https://www.yorck.de/filme/{entry['slug']}"
            lines.append(f"URL:{film_url}")
            lines.append(f"DESCRIPTION:{escape_ics_text(film_url)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    data = fetch_next_data()
    entries = extract_entries(data)
    sys.stderr.write(f"{len(entries)} Vorstellungen gefunden\n")
    ics = build_ics(entries)
    print(ics)


if __name__ == "__main__":
    main()
