# Das StitchLAB-Ökosystem — wer was macht

> Landkarte über alle Repos, die zu StitchLAB gehören. Dieses Repo ist der
> Integrationspunkt, aber nicht das ganze Projekt. Die Roadmap darüber steht in
> [10-roadmap.md](10-roadmap.md).

Ohne diese Seite liest sich die Ablage so, als wären es ein Dutzend unabhängiger
Projekte. Sind es nicht: sie hängen an einer Maschine und an einer Ablösung.

## Die drei Generationen

```text
StitchLAB Classic ──► StitchLAB Hybrid ──► OpenRSS
Stickmaschine aus     Nähen und Sticken    Modulare Textilrobotik,
Haushaltsnähmaschine  in einer Maschine    eigener Motion-Kern
(ausgeliefert)        (in Entwicklung)     (in Planung)
```

**Classic** läuft. Es ist eine ausgediente Haushaltsnähmaschine (Pfaff
Tipmatic/Hobbymatic) mit 3D-gedrucktem Anbau, SKR Pico und Klipper. Das
Software-Abbild dazu ist StitchLabOS, also dieses Repo.

**Hybrid** erweitert dieselbe Maschine um echtes Nähen: abnehmbares Gantry,
Encoder am Handrad, Fußpedal, Moduswechsel. Läuft weiter auf Klipper.

**OpenRSS** ist der Bruch, nicht die Fortsetzung. Es ersetzt den
Klipper/Moonraker/Mainsail-Stack durch einen eigenen, prozessbewussten
Motion-Kern. OpenRSS' eigene Planung nennt den heutigen Stack ausdrücklich
*StitchLAB OS Legacy* — dessen UX-Muster und Lehren wandern mit, dessen
Implementierung nicht.

---

## Was in diesem Repo steckt

`MainsailDev` heißt aus historischen Gründen so; das GitHub-Remote ist
`prntr/StitchlabOS`. Vier eingebettete Repos gehören dazu:

| Ordner | Was | Herkunft |
|---|---|---|
| `mainsail/` | Web-UI, Fork mit StitchLAB-Panels | Submodul, `prntr/mainsail` |
| `turtlestitch/` | Offline-Editor auf dem Pi | Submodul, `prntr/turtlestitch` |
| `stitchlabos-config/` | Moonraker-Komponenten, Makros, WLAN-Skripte | Submodul, `prntr/stitchlabos-config` |
| `virtual-klipper-printer/` | Simulator zum Testen | eigener Klon, **kein** Submodul |

---

## Die anderen Repos

### Maschine und Firmware

| Projekt | Rolle | Stand |
|---|---|---|
| [`StitchHEAD`](../../StitchHEAD) | Firmware für den SKR Pico als Antriebskopf, TMC2209 über UART | **Offenes Problem**: UART-Konfiguration der TMC2209 funktioniert unter keinem getesteten Arduino-Framework. Siehe dessen `PROBLEM_ANALYSIS.md`, bevor dort etwas gebaut wird. |
| [`MKSdrivemini`](../../MKSdrivemini) | MKS XDrive Mini, BLDC im Closed Loop — Vorarbeit für den Nähmotor | Bring-up-Phase, bewusst minimal gehalten |
| [`KlipperLiveControl`](../../KlipperLiveControl) | ESP-NOW-Funkstrecke: Handcontroller → Dongle → `live_jogd` → Moonraker | Teil von StitchLabOS; `live_jogd` ist in diesem Image enthalten |
| [`PCBs`](../../PCBs), [`eez-projects`](../../eez-projects) | Leiterplatten und Messtechnik | Zuarbeit |

### Modell und Simulation

| Projekt | Rolle | Stand |
|---|---|---|
| [`stitchLABsim`](../../stitchLABsim) | Fadenhebel- und Stichbildungsmodell nach Manoilenko et al. (2024), als Paket | Angebotsseite fertig, Bedarfsseite offen |
| [`stitchlabPROdev`](../../stitchlabPROdev) | Explorative Vorarbeit zu demselben Modell, Pfaff-Nockenanalyse | Skripte, kein Paket — `stitchLABsim` ist die aufgeräumte Form |
| [`StatorTwin`](../../StatorTwin) | Motorseitige Modellierung | eigenständig |

### Vom Bild zum Stich

| Projekt | Rolle | Stand |
|---|---|---|
| [`IMG2SVG2SITCH`](../../IMG2SVG2SITCH) | Rasterbild → SVG → Stickpfad/G-Code | Zwei Skripte, kein Paket |
| [`RPIcam2Embroidery`](../../RPIcam2Embroidery) | Kamerabild → Stickdatei, Flask-Backend für den Pi | eigenständig, noch nicht im Image |
| [`StitchlabAssets`](../../StitchlabAssets) | Grafikpipeline: CAD-PDF → SVG/AI, Logo, `gcode_to_svg.py` | Werkzeug, liefert unter anderem das Imager-Icon |

### Dokumentation, Lehre, Aufbau

| Projekt | Rolle | Stand |
|---|---|---|
| `Stitch(x)App` | Quellmaterial der Maschine (STEP/GLB/STL) plus `PLAN.md` für die geplante Wissensplattform | Material und Plan, noch kein Code |
| [`Bauplan`](../../Bauplan) | Erzeugt aus STEP plus Schrittskript die Aufbauanleitung: SVGs, PDF, Stückliste | Liest `Stitch(x)App`, schreibt nie hinein |
| [`ZeitleisteStitchTexTech`](../../ZeitleisteStitchTexTech) | Interaktive Zeitleiste für die Lehrveranstaltung | Web, eigenes GitHub-Repo |

### Die Zukunft

| Projekt | Rolle | Stand |
|---|---|---|
| [`OpenRSS`](../../OpenRSS) | Open Robotic Sewing System — hardwareunabhängige Näh-/Textilrobotik-Plattform | Planungsphase 0–1. `README.md`, `architecture.md`, `roadmap.md`, `docs/adr/` |

OpenRSS ist kein umbenanntes Klipper-Setup. Es zielt auf mehrere koordinierte
Aktoren — Nadel, Fadenhebel, Greifer, Transport, Fadenspannung, Schneider —,
auf die Nadelphase als eigene Koordinate und auf Closed-Loop-Antriebe. Ob
LinuxCNC den Realtime-Kern liefern kann, untersucht
`Reports&Plans/LinuxCNC Motion Kernel Prototype Plan.md`.

Classic bleibt dabei ein erstklassiges Zielsystem: OpenRSS soll auf derselben
billigen Hardware laufen — nur mit eigenem Motion-Kern statt Klipper.

---

## Wo was hingehört

Wenn unklar ist, in welches Repo eine Änderung gehört:

| Es geht um … | Repo |
|---|---|
| Das Pi-Abbild, Module, CI, Release | dieses Repo |
| Mainsail-Panels, UI-Verhalten | `mainsail/` (Submodul) |
| Moonraker-Komponenten, Makros, WLAN-Skripte | `stitchlabos-config/` (Submodul) |
| MCU-Firmware für den Pico unter Klipper | `firmware/skr-pico/` hier |
| Eigenständige Pico-Firmware ohne Klipper | `StitchHEAD` |
| Fadenphysik, Stichgeometrie | `stitchLABsim` |
| Aufbauanleitung, Explosionszeichnungen | `Bauplan` (aus `Stitch(x)App`) |
| Neuer Motion-Kern, Maschinenmodell | `OpenRSS` |

## Hausordnung

Jedes dieser Projekte hat ein `AGENTS.md` mit `CLAUDE.md` als Symlink darauf, und
verweist auf `~/Code/_std/AGENTS.base.md` sowie
`~/Code/active/plattform/pipeline.md`. Den Stand prüft:

```bash
~/Code/_std/bin/agents-doctor
```
