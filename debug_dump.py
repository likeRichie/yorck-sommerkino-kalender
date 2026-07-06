#!/usr/bin/env python3
"""
Diagnose-Tool: Lädt die Sommerkino-Seite einmal roh herunter und extrahiert
den eingebetteten Next.js-Datenblock (__NEXT_DATA__), der vermutlich die
echte tagesgenaue Programmstruktur enthält (im Gegensatz zur sichtbaren
HTML-Liste, die für jeden Tag identisch aussieht).

Ergebnis wird als hübsch formatiertes JSON nach debug_nextdata.json
geschrieben, damit wir die Struktur inspizieren können.
"""

import json
import re
import sys

import requests

URL = "https://www.yorck.de/kinos/sommerkino-kulturforum"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SommerkinoICSBot/1.0; +https://github.com/)"
}


def main():
    resp = requests.get(URL, params={"tab": "daily", "date": "2026-07-06"}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    # Next.js embeddet die Seiten-Props üblicherweise in einem Script-Tag:
    # <script id="__NEXT_DATA__" type="application/json">{...}</script>
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )

    if not match:
        sys.stderr.write("Kein __NEXT_DATA__-Block gefunden. Schreibe stattdessen rohes HTML.\n")
        with open("debug_nextdata.json", "w", encoding="utf-8") as f:
            f.write(html[:200000])  # Sicherheitslimit
        return

    raw_json = match.group(1)
    try:
        data = json.loads(raw_json)
        with open("debug_nextdata.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        sys.stderr.write(f"__NEXT_DATA__ gefunden, {len(raw_json)} Zeichen, geschrieben nach debug_nextdata.json\n")
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"JSON-Parse-Fehler: {exc}\n")
        with open("debug_nextdata.json", "w", encoding="utf-8") as f:
            f.write(raw_json[:200000])


if __name__ == "__main__":
    main()
