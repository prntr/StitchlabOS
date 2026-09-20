# Plan - G-Code Intake, Compatibility Check und stabile Stick-Job-Vorschau

## Implementierungsstand

| Phase | Status | Pfad |
|-------|--------|------|
| 1 — Parser & Check-CLI | ✓ implementiert | [stitchlabos/image/src/modules/stitchlab-intake/](../stitchlabos/image/src/modules/stitchlab-intake/) |
| 2 — Thumbnail-Generator | ✓ implementiert | siehe `renderer.py` im selben Modul |
| 3 — Moonraker-Komponente | ✓ implementiert | [stitchlabos-config/moonraker/components/stitchlab_intake.py](../stitchlabos-config/moonraker/components/stitchlab_intake.py) + `component.py` im Intake-Modul |
| 4 — Mainsail Files UI / Start-Flow | offen | — |
| 5 — Dashboard ersetzen | offen | — |
| 6 — Stabilitäts-/Performance-Gate | offen | — |

Tests: 54 grün (Parser 20, Checks 6, CLI 10, Renderer 8, Component 10).
Drift-Test verifiziert pro Fixture, dass Renderer-Bounds == Parser-Bounds —
Klasse-A-Normalisierungs-Divergenz wird sofort gefangen.

## Kontext

Die aktuelle Dashboard-Preview ist eine Live-Stichpfad-Preview: sie lädt den aktiven G-Code im Browser, parsed ihn auf dem Main Thread, rendert Stitch-Pfade und hält große Hilfsarrays wie `moveOffsets` und `stitchPointMoveIndices` im Frontend-State. Das ist für die Dashboard-Aufgabe zu teuer.

Die neue Zielarchitektur ist eine stabile Job-Vorschau:

- Jede stickbare Datei bekommt ein gecachtes Thumbnail.
- Das Dashboard konsumiert nur Thumbnail + Metadaten.
- G-Code-Analyse und Thumbnail-Erzeugung laufen einmalig serverseitig.
- Beim Start wird nur neu finalisiert, wenn sich Rahmen oder Placement geändert haben.

## Hintergrund: Validierungslücke in Klipper/Moonraker

Weder Moonraker noch Klipper führen eine Pre-Flight-Validierung von G-Code durch:

- Moonrakers `file_manager`/`metadata.py` extrahiert nur Slicer-Thumbnails und 3D-Druck-Stats. Keine Kommando-, Bounds- oder Einheitenprüfung.
- Klipper validiert pro Zeile **erst zur Laufzeit**. `Move out of range`, unbekannte Kommandos, fehlende Makros → Abbruch mitten im Job.

Für Stickbetrieb ist Mid-Job-Abbruch besonders teuer (Stoff, Nadel, Spannung verloren). Der Intake füllt damit eine echte Lücke; es ist keine Doppelarbeit zu bestehender Klipper-Funktionalität.

## Ziel

Ein allgemeiner StitchLab G-Code Intake verarbeitet jede Datei, die auf der Maschine gestickt werden soll:

1. G-Code auf Format, Kompatibilität und Sicherheitsrisiken prüfen.
2. Stick-relevante Metadaten extrahieren.
3. Ein Design-Thumbnail beim Upload vorbereiten.
4. Ein finales Job-Thumbnail beim Laden/Starten mit gewähltem Rahmen und Placement erzeugen.
5. Mainsail entlasten: kein Full-G-Code-Fetch und kein Stitchpfad-Rendering im Dashboard.

## Nicht-Ziele

- Kein Ersatz für den G-Code-Studio-Editor.
- Kein vollständiger G-Code-Simulator.
- Keine Live-Stichreihenfolge im Dashboard.
- Keine Browser-basierte Thumbnail-Erzeugung.
- Kein Boot-Time-Vollscan über alle Dateien.

## Auswirkung auf den Cross-Platform-Stability-Plan

Dieser Plan ist die langfristige Lösung für die Dashboard-Preview-Ursache `A11`, aber er ersetzt nicht den kurzfristigen Stabilitätsfix.

Für den Cross-Platform-Stability-Plan bedeutet das:

- Der schnelle P0-Fix bleibt: Dashboard darf keinen kompletten G-Code mehr laden, parsen oder als Stichpfad rendern.
- Wenn noch kein Intake-Thumbnail existiert, zeigt das Dashboard einen leichten Platzhalter statt auf Browser-Parsing zurückzufallen.
- Die vollständige Garantie "jedes stickbare File bekommt ein korrektes Thumbnail" wird über diesen Intake-Plan umgesetzt.
- Der Intake-Service darf nicht Teil von `guiIsReady`, Mainsail-Cold-Load oder Dashboard-Render sein.
- Upload-Analyse läuft asynchron und niedrig priorisiert; nur der Start-/Prepare-Flow darf auf einen fehlenden Check warten.
- Kein Boot-Time-Vollscan und keine parallelen Renderjobs, sonst wird aus der Lösung eine neue Cross-Platform-Stabilitätsursache.
- **Job-Gating**: Die Intake-Queue pausiert hart, solange `print_stats.state == printing` (oder ein laufender Stickjob anderweitig signalisiert wird). Begründung: Klipper-Host ist Single-Threaded und CPU-empfindlich (Risiko `Timer too close`), `live_jogd` ist latenzsensitiv. In den meisten Workflows wird während eines Sticklaufs nichts hochgeladen, deshalb ist Pausieren akzeptabel; bereits laufende Render werden sauber zu Ende geführt, neue Aufgaben warten in der Queue.

## Architektur

### Komponenten

| Komponente | Aufgabe |
|------------|---------|
| `stitchlab-gcode-intake` CLI | Streamender Parser, Compatibility-Check, Metadata/Thumbnail-Erzeugung. |
| Moonraker-Komponente `stitchlab_intake` | Queue, API, Start-Gating, Integration mit Upload/Datei-Metadaten. |
| Mainsail Files UI | Zeigt Check-Status, Warnungen und Thumbnail-Status. |
| Mainsail Start-Flow | Ruft `prepare` mit finalem Rahmen/Placement auf. |
| Dashboard Job Preview | Zeigt nur finales Thumbnail + einfache Job-Metadaten. |

### Trigger

| Trigger | Verhalten |
|---------|-----------|
| Upload nach `gcodes/` | Analyse und Basis-Thumbnail im Hintergrund starten. Upload selbst bleibt schnell. |
| Save from G-Code Studio | Analyse nach dem Upload starten; Placement aus G-Code-Studio mitschreiben. |
| Save & Start | Upload, Analyse, finale Vorbereitung, dann Start nur bei `valid` oder bestätigten Warnungen. |
| Load / Start existing file | Prüfen, ob Analyse/Thumbnail aktuell sind; falls Placement geändert wurde, nur Job-Thumbnail neu erzeugen. |
| Manuelle Aktion "Recheck" | Cache verwerfen und Datei neu analysieren. |

### Cache-Keys

```text
analysis_key = sha256(gcode_content) + checker_version
preview_key  = analysis_key + hoop_id + hoop_version + offset_x + offset_y + rotation_deg + scale + pivot
```

Wenn nur Rahmen oder Placement geändert werden, bleibt die G-Code-Analyse gültig. Nur die Platzierungsprüfung und das finale Thumbnail müssen neu erzeugt werden.

## Artefakte

Für eine Datei:

```text
/home/pi/printer_data/gcodes/design.gcode
```

werden gecachte Artefakte abgelegt:

```text
/home/pi/printer_data/gcodes/.stitchlab_meta/design.<analysis_key>.json
/home/pi/printer_data/gcodes/.stitchlab_thumbs/design.<preview_key>.png
```

Die Moonraker-Komponente soll diese Artefakte in die Datei-Metadaten einhängen, idealerweise so, dass Mainsail sie wie normale `current_file.thumbnails` verwenden kann. Falls Moonrakers Standard-Metadata-Scanner keine Sidecar-Thumbnails akzeptiert, liefert `stitchlab_intake` zusätzlich eine eigene Metadata-API. Ziel bleibt trotzdem: Dashboard lädt nur ein kleines Bild und JSON, keinen kompletten G-Code.

## Modifikationspolitik

Der Intake fasst die Original-Datei nicht an. Modifikationen sind in zwei klar getrennte Klassen aufgeteilt:

### Klasse A — Parse-Zeit-Normalisierung (immer, intern, nicht persistent)

Findet ausschließlich im Parser-State statt, schreibt nichts zurück. Die Datei auf Disk bleibt bit-identisch.

- BOM strippen (UTF-8/UTF-16) für interne Verarbeitung
- Line-Endings normalisieren (`\r\n`/`\r` → `\n`)
- Dezimalkomma → Dezimalpunkt für numerische Auswertung
- Leading/Trailing Whitespace tolerieren
- Case-Insensitive für `STITCHLAB_*`-Keys (Ausgabe wird normalisiert)

### Klasse B — Auto-Fix (explizite User-Aktion, neue Datei)

Wird nur auf Knopfdruck ausgelöst, erzeugt eine neue Datei `<name>.fixed.gcode` neben dem Original. Original bleibt unverändert. Diff wird vor dem Schreiben in der UI angezeigt, User bestätigt.

Kandidaten für Auto-Fix:
- Unterminierte `(...)`-Kommentare schließen
- Fehlende `G21`-Einheitendeklaration am Anfang ergänzen
- Inkonsistente Line-Endings normalisieren (persistent)
- InkStitch-typische Kommentarformatierung normalisieren

### Optional — Runtime-Cache (`<name>.runtime.gcode`)

Falls Klasse-A-Normalisierung über Trivialitäten hinausgeht, kann der Intake ein internes Runtime-File ablegen, das Klipper tatsächlich ausführt. Verantwortlichkeiten bleiben sauber: Original = User-Intent, Runtime-File = ausgeführter Code, niemals dem Nutzer als "die Datei" präsentiert. `analysis_key` referenziert den Hash des Originals; `runtime_key` ist separat.

### Was der Intake niemals tut

- Original-Datei stillschweigend überschreiben.
- Sicherheitsrelevante Kommandos (Temperatur, Shell, Homing im Job) auto-entfernen — solche Dateien werden blockiert, nicht repariert.
- Bounds- oder Placement-Korrekturen ohne explizite User-Bestätigung.

## Metadata-Schema

```json
{
  "schema": "stitchlab_intake.v1",
  "status": "valid|warnings|blocked",
  "analysis_key": "sha256...:v1",
  "preview_key": "sha256...:v1|hoop=standard|hv=preliminary|ox=0.000|oy=0.000|rot=0.00|sc=1.0000|pv=design",
  "source": {
    "filename": "design.gcode",
    "size": 1234567,
    "modified": 1788888888,
    "sha256": "017b4adb...",
    "detected_origin": "turtlestitch|inkstitch|gcode_studio|external|unknown"
  },
  "units": "mm",
  "units_explicit": true,
  "bounds": {
    "min_x": 12.3,
    "min_y": 8.0,
    "max_x": 84.7,
    "max_y": 56.1,
    "width": 72.4,
    "height": 48.1
  },
  "stats": {
    "stitch_count": 12345,
    "jump_count": 210,
    "long_jump_count": 3,
    "color_changes": 4,
    "segment_count": 14000,
    "command_count": 14800
  },
  "stitchlab_meta": {"HOOP_ID": "standard", "SOURCE": "gcode_studio"},
  "referenced_unknown_macros": [],
  "placement": {
    "hoop_id": "standard",
    "offset_x": 0,
    "offset_y": 0,
    "rotation_deg": 0,
    "scale": 1,
    "pivot": "design"
  },
  "thumbnail": {
    "relative_path": ".stitchlab_thumbs/design.hash.png",
    "width": 768,
    "height": 768
  },
  "errors": [],
  "warnings": [],
  "info": []
}
```

Hinweise:

- `analysis_key` bekommt das `CHECKER_VERSION`-Suffix automatisch angehängt; ein Bump invalidiert den Cache ohne Datei-Touch.
- `preview_key` ist vollständig — auch wenn Placement Identity ist — damit Caches deterministisch keyen.
- `info`-Liste ist neu und enthält non-blocking Hinweise (z.B. `BOM_DETECTED`, `RELATIVE_MODE`).
- `referenced_unknown_macros` listet Custom-Kommandos für den Phase-3-Abgleich mit Klippers `gcode_macro`-Definitionen.

## Kanonisches Kommentarformat

Neue StitchLab-Dateien sollten maschinenlesbare Kommentare am Anfang enthalten. Externe Dateien bleiben erlaubt, bekommen aber Warnungen, wenn Metadaten fehlen.

```gcode
; STITCHLAB_VERSION: 1
; STITCHLAB_SOURCE: turtlestitch
; STITCHLAB_UNITS: mm
; STITCHLAB_STITCH_COUNT: 12345
; STITCHLAB_HOOP_ID: standard
; STITCHLAB_PLACEMENT: x=0 y=0 rotation=0 scale=1 pivot=design
; STITCHLAB_BOUNDS: min_x=12.3 min_y=8.0 max_x=84.7 max_y=56.1
; STITCHLAB_COLOR: r=230 g=80 b=65 name=red
```

Zusätzlich weiter akzeptieren:

- `; color r:<0-255> g:<0-255> b:<0-255>`
- `(STITCH_COUNT:123)`
- normale `;`-Kommentare
- normale Klammer-Kommentare `(comment)`

Regeln:

- `STITCHLAB_*`-Kommentare sind case-insensitive beim Key, aber die Ausgabe normalisiert auf uppercase.
- Unbekannte `STITCHLAB_*`-Keys sind Warnungen, keine Fehler.
- Ungültige numerische Werte in `STITCHLAB_*` sind Fehler, wenn sie sicherheitsrelevant sind, sonst Warnungen.
- Kommentare dürfen nie als Ersatz für eine echte Sicherheitsprüfung gelten; Bounds und Kommandos werden immer aus dem G-Code validiert.

## G-Code Compatibility Checks

### Format-Checks

| Check | Severity | Grund |
|-------|----------|-------|
| Datei nicht lesbar | error | Start nicht sicher möglich. |
| Leere Datei oder nur Kommentare | error | Kein ausführbarer Job. |
| Datei überschreitet Maximalgröße (z.B. 50 MB) | error | DoS-/Müll-Schutz, schützt Pi und Queue. |
| Datei überschreitet Maximalzeilenzahl (z.B. 10M) | error | Gleicher Grund. |
| NUL/Binary-Daten | error | Kein valider Text-G-Code. |
| Encoding nicht UTF-8/ASCII-kompatibel | warning/error | Warnung bei reparierbar, Fehler bei Parser-Abbruch. |
| BOM am Dateianfang (UTF-8/UTF-16) | info | Wird intern gestrippt; bei UTF-16 Konversion. |
| Extrem lange Zeilen | warning | Kann Parser/Renderer belasten. |
| Uneinheitliche Line Endings | info | Wird normalisiert. |
| Dezimalkomma statt Dezimalpunkt | info | Wird intern normalisiert. |
| Unterminierte `(...)`-Kommentare | error | Häufige InkStitch-Falle, bricht Klipper-Parser zur Laufzeit. |
| Mehrere Kommandos in einer Zeile | warning | Klipper-Parser akzeptiert das nicht überall zuverlässig. |

### Modal- und Einheiten-Checks

| Check | Severity | Grund |
|-------|----------|-------|
| Keine explizite Einheit `G20`/`G21` | warning | Default muss angenommen werden. Empfehlung: `G21`. |
| `G20` Inch-Modus | warning | Unterstützen, aber in mm normalisieren. |
| Wechsel zwischen `G90`/`G91` | warning/error | Erlaubt, wenn eindeutig nachverfolgbar; Fehler bei unklarer Geometrie. |
| `G92` Ursprung-Reset | warning | Kann Placement/Bilderwartung beeinflussen. |
| Nicht zurückgesetzter relativer Modus am Ende | warning | Für Wiederaufnahme/Debug riskant. |

### Befehls-Whitelist

Erlaubt:

- `G0`, `G1` für XY/Z-Bewegungen
- `G2`, `G3` mit Arc-Flattening; werden in Stitch-Segmente überführt und so gerendert
- `G4` Dwell, falls maschinell nötig
- `G20`, `G21`, `G90`, `G91`, `G92`
- `M400`, falls als Synchronisationspunkt genutzt
- definierte StitchLab-Makros aus Whitelist, z.B. `STITCH`, `LOCK_STITCH`, `NEEDLE_TOGGLE`, wenn sie in Job-Dateien wirklich vorkommen sollen

Blockieren:

- Not-Aus oder Systembefehle: `M112`
- Konfigurations-/Update-/Shell-nahe Befehle: `SAVE_CONFIG`, `RUN_SHELL_COMMAND`
- Homing im Job: `G28`, sofern nicht explizit erlaubt
- Stepper-Off/Power-Off: `M18`, `M84`
- 3D-Druck-Temperatur: `M104`, `M109`, `M140`, `M190`
- Extrusion: `E`-Achse in Bewegungsbefehlen
- Unbekannte Makros außerhalb einer expliziten Allowlist

Warnen:

- `M117`, `RESPOND`, Display-/Log-Kommandos
- Feedrate fehlt in Bewegungsbefehlen
- Sehr hohe Feedrates
- Sehr kurze Segmente in großer Menge
- Sehr viele Farbwechsel

### Makro-Existenz-Check

Wichtigster echter Mehrwert für InkStitch- und ähnliche Workflows. Datei referenziert Custom-Kommandos wie `STITCH`, `TRIM`, `COLOR_CHANGE`, `PEN_UP`, die zur Laufzeit als `gcode_macro` in Klipper definiert sein müssen.

Ablauf:

1. Parser sammelt alle nicht-Standard-Kommandos (alles, was kein G/M-Code aus der Whitelist ist).
2. Intake fragt Moonraker nach Klippers definierten Makros (`server.objects.query` / Klipper-Status zu `configfile`).
3. Abgleich: Fehlende Makros werden als **error** gemeldet, weil sonst mid-job-Abbruch droht.
4. Ergebnis wird Teil des `analysis_key`-Berichts; Cache invalidiert, wenn sich die Klipper-Makro-Liste ändert (separates Versionierungs-Token).

Hinweis: Dieser Check ist konfigurationsabhängig und kann sich ändern, ohne dass die G-Code-Datei sich ändert. `prepare` ruft ihn deshalb immer erneut auf, statt blind auf den `analysis_key`-Cache zu vertrauen.

### Stick-spezifische Checks

| Check | Severity | Grund |
|-------|----------|-------|
| Keine XY-Geometrie | error | Kein stickbarer Job. |
| Design überschreitet nutzbare Rahmenfläche | error | Mechanisch/sicherheitsrelevant. |
| Design überschreitet Maschinenverfahrweg | error | Kollisions-/Limit-Risiko. |
| XY-Bewegung bei Nadel-unten-Zustand | error/warning | Abhängig von finaler Z-/Nadelmodell-Spezifikation. |
| Z-Bewegung außerhalb definierter Nadel-Up/Down-Werte | warning/error | In reiner Stickkonfig sollten Z-Moves auf bekannte Werte beschränkt sein. |
| Feedrate fehlt im ersten Bewegungsbefehl | warning | Klipper benutzt sonst letzten globalen State, kann unerwartet schnell sein. |
| Feedrate `F0` oder über Maschinenmaximum | error | Stillstand bzw. Übersteuern. |
| Sehr lange Jump-Moves ohne Stiche (über Schwellwert) | warning | Trimm-Empfehlung; sonst Faden über das Design. |
| Sehr hohe Stichdichte in kleinen Bereichen | warning | Nadelbruch-Risiko. |
| Color-Change ohne abschließenden Stich davor | warning | Inkonsistenter Color-Block. |
| Anzahl Farbwechsel > Maschinenfähigkeit | error/warning | Abhängig vom Hoop-/Maschinenmodell. |
| Erstes Bewegungsziel weit vom erwarteten Startpunkt | warning | Startposition rahmenabhängig; auffälliger Sprung am Anfang. |
| Keine Stitch-Marker/Stichzahl erkennbar | warning | Preview möglich, Statistik unsicher. |
| G0/G1-Heuristik notwendig | warning | Externe Dateien ohne klare Semantik. |
| Arcs/Bezier nicht exakt darstellbar | warning | Thumbnail wird approximiert. |

## Thumbnail-Generierung

### Prinzip

Der Generator arbeitet serverseitig, streamend und mit festen Limits:

- kein Browser
- kein Paper.js
- kein Full-G-Code im Frontend
- keine großen Arrays im Vuex
- keine Stich-für-Stich-Live-Renderdaten

### Algorithmus

1. Datei zeilenweise lesen.
2. Kommentare und `STITCHLAB_*`-Metadaten erfassen.
3. Modal State verfolgen: Einheit, absolut/relativ, aktuelle X/Y/Z-Position, Feedrate, Farbe.
4. Erster Pass:
   - Bounds berechnen
   - Commands klassifizieren
   - Fehler/Warnungen sammeln
   - Stitch-/Jump-/Color-Stats zählen
5. Placement anwenden:
   - Offset
   - Rotation
   - Scale
   - Pivot
   - Hoop-Koordinaten
6. Rahmen- und Maschinenlimits prüfen.
7. Zweiter Pass:
   - direkt in ein Rasterbild rendern
   - nur sichtbare Stitch-Segmente zeichnen
   - Travel Moves auslassen oder nur optional sehr dezent in Debug-Thumbnails
   - Farbwechsel berücksichtigen
8. PNG speichern.
9. Metadata JSON schreiben.
10. Moonraker-Dateimetadaten aktualisieren oder eigene Metadata-API aktualisieren.

### Rendering-Details

Empfohlene Defaults:

| Parameter | Wert |
|-----------|------|
| Thumbnail groß | 768 x 768 PNG |
| Thumbnail klein | 256 x 256 PNG, optional |
| Hintergrund | transparent oder StitchLab preview surface |
| Hoop outline | dünne Linie |
| Nutzbare Fläche | gestrichelte/helle Linie |
| Design | farbige Linien, anti-aliased |
| Out-of-bounds | roter Rahmen/Fehlerstatus, Start blockieren |

Performance-Regeln:

- Segment-Deduplizierung auf Pixel-Ebene: wiederholte Linien auf denselben Pixeln nicht tausendfach zeichnen.
- Arc-Flattening mit maximaler Segmentanzahl pro Arc.
- Maximalzeit pro Datei, z.B. 10-30 s je nach Pi-Modell.
- Maximaler Speicherverbrauch fest begrenzen.
- Ein Worker gleichzeitig.
- `nice`/`ionice` oder systemd `Nice=10`, `IOSchedulingClass=idle`, optional `CPUQuota=25%`.

## Rahmen- und Placement-Daten

Im aktuellen Mainsail/G-Code-Studio-State existieren bereits:

- `gui.gcodeStudio.frameWidth`
- `gui.gcodeStudio.frameHeight`
- `gui.gcodeStudio.framePreset`
- `gui.gcodeStudio.designOffsetX`
- `gui.gcodeStudio.designOffsetY`
- `gui.gcodeStudio.rotationDeg`
- `gui.gcodeStudio.rotationPivot`

Für eine sichere Maschinenentscheidung fehlen noch die physischen Rahmenspezifikationen.

### Benötigte Rahmendaten

| Feld | Beschreibung |
|------|--------------|
| `hoop_id` | stabile interne ID, z.B. `standard`. |
| `display_name` | sichtbarer Name. |
| `outer_width_mm`, `outer_height_mm` | physische Außenmaße. |
| `usable_width_mm`, `usable_height_mm` | tatsächlich bestickbare Fläche. |
| `safe_margin_mm` | zusätzlicher Sicherheitsabstand. |
| `origin` | Ursprung: Mittelpunkt, links unten, Maschinen-Nullpunkt oder anderer Punkt. |
| `machine_origin_x/y` | Bezug zwischen Rahmen und Maschinenkoordinaten. |
| `mount_orientation` | Einspannrichtung, falls asymmetrisch. |
| `no_go_zones` | Klemmen-/Randbereiche, falls vorhanden. |
| `max_rotation_deg` | erlaubte Rotation, falls eingeschränkt. |
| `allow_scale` | ob Skalierung erlaubt ist. |
| `version` | Hoop-Spezifikation-Version für Cache-Invalidierung. |

### Vorläufige Annahme bis Spezifikation vorliegt

Bis der Standardrahmen exakt spezifiziert ist:

- `hoop_id = standard`
- `usable_width_mm = frameWidth`
- `usable_height_mm = frameHeight`
- Ursprung = Rahmenzentrum für Vorschau
- Placement aus G-Code Studio wird als visuelle Platzierung behandelt
- Start-Gating auf Maschinenlimits bleibt conservative bzw. deaktiviert für unbekannte physische Offsets

## Moonraker-/Mainsail-Integration

### Neue API

Vorschlag als Moonraker-Komponente:

```text
server.stitchlab_intake.analyze
server.stitchlab_intake.prepare
server.stitchlab_intake.status
server.stitchlab_intake.recheck
server.stitchlab_intake.cancel
```

`analyze`:

```json
{
  "filename": "gcodes/design.gcode"
}
```

`prepare`:

```json
{
  "filename": "gcodes/design.gcode",
  "placement": {
    "hoop_id": "standard",
    "offset_x": 0,
    "offset_y": 0,
    "rotation_deg": 0,
    "scale": 1,
    "pivot": "design"
  }
}
```

Antwort:

```json
{
  "status": "valid",
  "blocking": false,
  "thumbnail": {
    "relative_path": ".stitchlab_thumbs/design.hash.png",
    "width": 768,
    "height": 768
  },
  "errors": [],
  "warnings": []
}
```

### UI-Verhalten

Files UI:

- Badge: `Unchecked`, `Checking`, `Valid`, `Warnings`, `Blocked`
- Thumbnail anzeigen, sobald vorhanden
- "Recheck" Aktion
- Warn-/Fehlerdialog

Start Flow:

- `prepare` wird vor `printer.print.start` aufgerufen.
- Fehler blockieren.
- Warnungen verlangen Bestätigung.
- Bei Cache-Hit startet der Job ohne merkbare Verzögerung.
- Bei Cache-Miss zeigt die UI "Preparing job preview/check" und wartet nur im Start-Flow.

Dashboard:

- kein G-Code-Fetch
- kein `parseEmbroideryGcode`
- kein Stitchpfad-Renderer
- Anzeige: finales Thumbnail, Rahmenname, Placement, Fortschritt, Nadelstatus

## Implementierungsphasen

### Phase 1 - Parser und Check-CLI ✓

Geliefert:

- CLI `stitchlab-gcode-intake analyze <file>` mit Exit-Codes 0/1/2/3.
- Streamender Parser mit Modal State (units, abs/rel, XY, F, Color).
- Format-Checks: BOM, Encoding, NUL/Binary, max Size/Lines/LineLength, unterminierte Klammern, leere Datei.
- Command-Checks: Whitelist (G0/G1/G2/G3/G4/G20/G21/G90/G91/G92/M400), Blocklist (M104/109/140/190, M18/84, M112, G28, SAVE_CONFIG, RUN_SHELL_COMMAND), Embroidery-Macros (STITCH/TRIM/COLOR_CHANGE/…), Unknown-Macro-Collection für Phase-3-Klipper-Abgleich.
- Stick-Checks: E-Achse blockiert, Feedrate-Sanity (`F0`, > max, fehlend), Long-Jump-Threshold, Color-Change-Counter.
- Bounds-Berechnung in mm; G20-Inch-Mode wird automatisch konvertiert.
- JSON-Report nach `stitchlab_intake.v1`-Schema mit Diagnostik-Capping (max 25 pro Code + Summary).
- Hoop-Bounds-Check als externe Cross-Cutting-Prüfung in `checks.py`.
- 38 Tests in `tests/test_parser.py`, `tests/test_checks.py`, `tests/test_cli.py`.

Nicht in Phase 1 (bewusst verschoben): Stichdichte-Check (Schwellwerte brauchen reale Fixtures), Z-Konsistenz (offene Entscheidung #7), Multi-Command-pro-Zeile (Tokenizer-Scanner bei Bedarf), Maschinenenvelope (Phase 3 mit Moonraker), Macro-Existenz gegen Klipper (Phase 3).

### Phase 2 - Thumbnail-Generator ✓

Geliefert:

- `stitchlab-gcode-intake render <file> -o thumb.png` und `analyze --thumbnail-out`.
- Pillow-RGBA-Renderer, Default 768×768, konfigurierbar via `--size`.
- Streaming-Move-Iterator in `renderer.py`; nutzt geteilte Helpers aus `parser.py` (`split_line`, `parse_command`, `to_mm`, `_compute_new_xy`, `iter_lines`, `sniff_encoding`) damit Klasse-A-Normalisierung beider Pässe identisch bleibt.
- Drift-Test (`test_drift_renderer_matches_parser_bounds`) vergleicht Renderer-Bounds gegen Parser-Bounds über alle Fixtures.
- Viewport-Transform mit Hoop-Framing wenn `HoopSpec` gegeben; sonst Design-Bounds + 24 px Margin.
- Hoop-Outline + Safe-Margin-Rechteck zeichnen.
- Pixel-Pair-Deduplizierung: aufeinanderfolgende identische Linien werden übersprungen.
- Color-Tracking aus Kommentaren (`STITCHLAB_COLOR: r=… g=… b=…` und InkStitch-Stil `color r:… g:… b:…`).
- Travel-Moves (G0) standardmäßig verborgen; `RenderOptions.show_travel=True` macht sie sichtbar (für Debug-Thumbnails).
- `preview_key`-Builder: `analysis_key | hoop_id | hoop_version | offset_x | offset_y | rotation_deg | scale | pivot` — Placement-Änderung invalidiert nur Thumbnail, nicht Parser-Analyse.
- 6 Renderer-Tests + 4 zusätzliche CLI-Tests.

Nicht in Phase 2 (bewusst verschoben): echtes G2/G3 Arc-Flattening (aktuell als Sehne approximiert; Warnung `ARC_FLATTENED` bleibt), Placement-Transform (Phase 4), Stichdichte-Visualisierung (braucht reale Fixtures + Schwellwerte).

### Phase 3 - Moonraker-Komponente

- `stitchlab_intake` Komponente hinzufügen.
- Queue mit einem Worker.
- API-Endpunkte implementieren.
- Upload-/Save-Trigger integrieren.
- Status-Events an Mainsail melden.

### Phase 4 - Mainsail Files UI und Start Flow

- Check-Status in Dateiliste anzeigen.
- `prepare` vor Start/Save&Start aufrufen.
- Warn-/Fehlerdialog bauen.
- Thumbnail-URL aus Intake-Metadata oder `current_file.thumbnails` anzeigen.

### Phase 5 - Dashboard ersetzen

- `EmbroideryPreview.vue` zu stabiler Job-Preview umbauen.
- Full-G-Code-Fetch und Browser-Parser entfernen.
- `PrintstatusEmbroidery.vue` von `moveOffsets`/`stitchPointMoveIndices` entkoppeln.
- Fortschritt nur noch aus Moonraker/Print Progress ableiten.

### Phase 6 - Stabilitäts- und Performance-Gate

- Upload großer Datei bleibt responsiv.
- Dashboard lädt kein >MB-G-Code.
- CPU-Last des Generators ist begrenzt.
- Mehrere Browser-Tabs erzeugen keine zusätzliche Analysearbeit.
- Start-Flow ist bei Cache-Hit schnell.

## Tests

| Test | Erwartung |
|------|-----------|
| TurtleStitch Export Upload | Analyse läuft, Thumbnail entsteht, keine UI-Blockade. |
| Externer G-Code ohne Kommentare | Warnungen, aber wenn Geometrie sicher ist: Thumbnail und Start möglich. |
| Datei mit Temperaturbefehlen | Fehler, Start blockiert. |
| Datei größer 5 MB | Intake arbeitet im Hintergrund; Dashboard bleibt stabil. |
| Placement in G-Code Studio ändern | Analyse bleibt gültig, Job-Thumbnail wird neu erzeugt. |
| Rahmen zu klein | Fehler, Start blockiert, Thumbnail zeigt Out-of-bounds. |
| Cache-Hit Start | Kein erneutes Parsen, schneller Start. |
| Mehrere Uploads | Queue verarbeitet nacheinander, Moonraker/Mainsail bleiben nutzbar. |

## Offene Entscheidungen

1. Genaue Spezifikation des Standardrahmens.
2. Ob Moonraker Sidecar-Thumbnails direkt in `current_file.thumbnails` integrieren kann.
3. Exakte Befehls-Whitelist für echte StitchLab-Jobdateien.
4. Wie G-Code-Studio Placement gespeichert wird: nur als UI-Settings, als G-Code-Kommentar oder als Sidecar-Metadata.
5. Ob Warnungen per Nutzerbestätigung überschreibbar sind oder nur im Developer Mode.
6. Schwellwerte für Jump-Length und Stichdichte (maschinen-/nadelabhängig).
7. Genaue Definition "Nadel-Up/Down-Z-Werte" für Z-Konsistenz-Check.
8. Ob der Runtime-Cache (`<name>.runtime.gcode`) aktiviert wird oder Klasse-A-Normalisierung rein In-Memory bleibt.

## Akzeptanzkriterien

- Jede Datei, die gestartet werden soll, hat vorher einen Intake-Status.
- Jede valide stickbare Datei bekommt ein Thumbnail.
- Das finale Thumbnail entspricht gewähltem Rahmen und Placement.
- Das Dashboard lädt nie den kompletten G-Code nur für die Vorschau.
- G-Code-Analyse und Thumbnail-Generierung laufen nicht im Browser.
- Generatorlast ist begrenzt und beeinträchtigt Moonraker/Mainsail nicht spürbar.
- Fehlerhafte oder inkompatible Dateien können nicht versehentlich gestartet werden.
