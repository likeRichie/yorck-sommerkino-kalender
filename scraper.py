#!/usr/bin/env python3
"""
Scraped das Tagesprogramm des ARTE Sommerkino Kulturforum (Yorck Kinos)
und erzeugt daraus eine ICS-Datei zum Abonnieren (z.B. in iCloud).

Quelle: https://www.yorck.de/kinos/sommerkino-kulturforum?tab=daily&date=YYYY-MM-DD
"""

import re
import sys
import hashlib
import datetime as dt
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.yorck.de/kinos/sommerkino-kulturforum"
TZ = ZoneInfo("Europe/Berlin")

# Saisonzeitraum. Bei Bedarf anpassen (z.B. wenn Yorck die Saison verlängert).
SEASON_START = dt.date(2026, 6, 17)
SEASON_END = dt.date(2026, 8, 26)

# Erkennt Zeit+Fassungs-Angaben wie "21:15OmU", "21:30DF", "21:45OmeU"
TIME_RE = re.compile(r"^(\d{2}:\d{2})([A-Za-zÄÖÜäöüß]*)$")
DURATION_RE = re.compile(r"(\d+)\s*min")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SommerkinoICSBot/1.0; +https://github.com/)"
}


def fetch_day(day: dt.date) -> str:
    params = {
        "tab": "daily",
        "date": day.isoformat(),
        "sort": "Popularity",
        "sessionsExpanded": "false",
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_day(html: str, day: dt.date):
    """
    Läuft in Dokumentreihenfolge über alle <a>-Tags.
    Ein Link auf /filme/<slug> mit sichtbarem Text (nicht leer, kein
    Zeit-Muster) setzt den 'aktuellen' Filmtitel. Ein Link mit Text im
    Format 'HH:MMVersion' erzeugt daraufhin einen Termin-Eintrag.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    current_title = None
    current_href = None
    current_container = None

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]

        time_match = TIME_RE.match(text)
        if time_match and href == "#":
            if current_title:
                hh, mm = time_match.group(1).split(":")
                version = time_match.group(2) or ""

                duration_min = None
                if current_container is not None:
                    block_text = current_container.get_text(" ", strip=True)
                    dur_match = DURATION_RE.search(block_text)
                    if dur_match:
                        duration_min = int(dur_match.group(1))

                entries.append(
                    {
                        "date": day,
                        "title": current_title,
                        "hour": int(hh),
                        "minute": int(mm),
                        "version": version,
                        "duration_min": duration_min,
                        "url": current_href,
                    }
                )
        elif (
            href.startswith("/filme/")
            and text
            and not TIME_RE.match(text)
            and a.find_parent(["h2", "h3", "h4"]) is not None
        ):
            # Nur der echte Titel-Link (steht in einer Überschrift) zählt.
            # Der "(Mehr)"-Link im Fließtext hat denselben href, aber
            # keine Überschrift als Elternelement - wird hier ausgefiltert.
            current_title = text
            current_href = "https://www.yorck.de" + href
            # Container etwas weiter oben im Baum, um Genre/Dauer/FSK
            # desselben Film-Blocks mit einzufangen.
            container = a
            for _ in range(4):
                if container.parent is not None:
                    container = container.parent
            current_container = container

    return entries


def daterange(start: dt.date, end: dt.date):
    day = start
    while day <= end:
        yield day
        day += dt.timedelta(days=1)


def make_uid(entry) -> str:
    raw = f"{entry['date'].isoformat()}-{entry['hour']:02d}{entry['minute']:02d}-{entry['title']}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@sommerkino-kulturforum"


def escape_ics_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_line(line: str) -> str:
    """ICS-Zeilen dürfen laut RFC 5545 nicht länger als 75 Byte sein."""
    if len(line.encode("utf-8")) <= 75:
        return line
    out = []
    while len(line.encode("utf-8")) > 75:
        # naive Trennung nach Zeichen statt Byte-genauer Prüfung reicht hier
        out.append(line[:74])
        line = " " + line[74:]
    out.append(line)
    return "\r\n".join(out)


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

    for entry in entries:
        start_local = dt.datetime(
            entry["date"].year,
            entry["date"].month,
            entry["date"].day,
            entry["hour"],
            entry["minute"],
            tzinfo=TZ,
        )
        duration_min = entry["duration_min"] or 150
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
        lines.append(fold_line(f"SUMMARY:{escape_ics_text(summary)}"))
        lines.append("LOCATION:ARTE Sommerkino Kulturforum\\, Matthäikirchplatz\\, Berlin")
        if entry["url"]:
            lines.append(fold_line(f"URL:{entry['url']}"))
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    today = dt.datetime.now(TZ).date()
    start = max(SEASON_START, today)
    end = SEASON_END

    if start > end:
        sys.stderr.write("Saison ist vorbei, keine Tage zu scrapen.\n")
        print(build_ics([]))
        return

    all_entries = []
    for day in daterange(start, end):
        try:
            html = fetch_day(day)
            entries = parse_day(html, day)
            all_entries.extend(entries)
            sys.stderr.write(f"{day.isoformat()}: {len(entries)} Vorstellungen\n")
        except Exception as exc:  # robust: ein Tag darf nicht alles blockieren
            sys.stderr.write(f"{day.isoformat()}: Fehler beim Scrapen ({exc})\n")

    ics = build_ics(all_entries)
    print(ics)


if __name__ == "__main__":
    main()
