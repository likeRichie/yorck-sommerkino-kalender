# Sommerkino Kulturforum – ICS-Kalender

Scraped täglich das Tagesprogramm des ARTE Sommerkino Kulturforum
(https://www.yorck.de/kinos/sommerkino-kulturforum) und baut daraus eine
`sommerkino.ics`, die du als Kalenderabo in iCloud einbinden kannst.

## Setup (einmalig)

1. Diese Dateien in dein neues Repo hochladen (Struktur beibehalten,
   inkl. `.github/workflows/update.yml`).
2. Im Repo unter **Settings → Actions → General → Workflow permissions**:
   "Read and write permissions" aktivieren (nötig, damit die Action die
   ics-Datei committen darf).
3. Unter dem Tab **Actions** einmal "Update Sommerkino ICS" auswählen und
   manuell per "Run workflow" starten (nicht auf den ersten Cron warten).
4. Prüfen: Danach sollte im Repo eine Datei `sommerkino.ics` liegen.

## Kalender in iCloud abonnieren

1. Raw-Link der Datei kopieren:
   `https://raw.githubusercontent.com/<dein-username>/<repo-name>/main/sommerkino.ics`
2. `https://` durch `webcal://` ersetzen.
3. Auf dem iPhone/Mac: Kalender-App → Kalender hinzufügen → Kalenderabo
   hinzufügen → die `webcal://`-URL einfügen.
4. Aktualisierungsintervall auf "Täglich" stellen (iCloud entscheidet
   das teils selbst, per Einstellung nicht immer erzwingbar).

## Wie es funktioniert

- `scraper.py` ruft für jeden Tag der Saison (siehe `SEASON_START` /
  `SEASON_END` im Script) die Yorck-Tagesansicht auf und liest
  Filmtitel, Uhrzeit und Sprachfassung (OmU/OmeU/DF) aus.
- Ein GitHub Actions Cronjob (`.github/workflows/update.yml`) führt das
  Script täglich aus und committed die neue `sommerkino.ics`, falls sich
  etwas geändert hat.
- Events bekommen eine stabile UID (Hash aus Datum+Uhrzeit+Titel), damit
  bei jedem Lauf keine Dubletten entstehen.

## Falls sich das Programm mal falsch/unvollständig anzeigt

Die Yorck-Seite kann ihr HTML-Layout ändern, dann greift das Parsing
nicht mehr sauber. In dem Fall: kurzen Blick in die Action-Logs
(Tab "Actions" → letzter Lauf → "Run scraper") werfen und mir Bescheid
geben – dann passe ich `scraper.py` an.

## Anpassbare Parameter (in `scraper.py`)

- `SEASON_START` / `SEASON_END`: Saisonzeitraum
- `duration_min` Fallback: 150 Minuten, falls keine Laufzeit gefunden wird
