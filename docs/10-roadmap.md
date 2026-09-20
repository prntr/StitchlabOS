# Entwicklungsroadmap

> Wohin StitchLAB geht, und was als Nächstes dran ist. Wer was macht, steht in
> [00-oekosystem.md](00-oekosystem.md).
>
> Stand: 2026-09-20. Die inhaltlichen Ziele stammen aus
> `Reports&Plans/Development Roadmap.md`
> und der Planung in [`OpenRSS`](../../OpenRSS/roadmap.md); diese Seite ordnet
> sie in eine Reihenfolge und benennt, was ein Meilenstein abgeschlossen haben
> muss.

## Die Linie

```text
Beta1          Beta2            1.0              Hybrid            OpenRSS
ausgeliefert   Inbetriebnahme   reproduzierbar   Nähen + Sticken   neuer Kern
2026-04-14     ← hier           Classic fertig   dieselbe Maschine ab Planung
```

Classic und Hybrid laufen auf Klipper. OpenRSS ersetzt den Kern. Classic wird
davon nicht abgeschaltet — es bleibt die günstige Einstiegsmaschine und ein
Zielsystem für OpenRSS.

---

## Beta1 — ausgeliefert (v0.1.0-beta.1, 2026-04-14)

Erstes öffentliches Image. Klipper, Moonraker, Mainsail-Fork, TurtleStitch,
AP-Modus, `live_jogd`.

Die Kinderkrankheiten, die daraus sichtbar wurden:

- Die `os_list.json` zeigte auf ein Asset, das nie veröffentlicht wurde — der
  dokumentierte Imager-Weg war für alle ein 404.
- `extract_sha256` war wörtlich der Platzhalter aus der Vorlage.
- Ein frisch geflashtes System fand keinen MCU: die Pico-Firmware war nicht Teil
  des Images, und ein Pi im AP-Modus hat kein Internet, um sie zu bauen.
- Das `stitchlab-intake`-Modul stand nicht in `MODULES`, obwohl `moonraker.conf`
  bereits darauf verwies.

## Beta2 — eine Maschine wird ohne Vorwissen in Betrieb genommen

**Das Ziel:** SD-Karte flashen, einschalten, eine Anleitung befolgen, sticken.
Ohne zweiten Rechner, ohne Toolchain, ohne Repo-Kenntnis.

| | Status |
|---|---|
| Pico-Firmware wird in CI gebaut und im Image ausgeliefert | erledigt |
| `stitchlab-flash-pico` — geführte Inbetriebnahme auf dem Pi | erledigt |
| Bootloaderfreier Rettungs-Build für zerschossene Boards | erledigt |
| `os_list.json` aus echten Prüfsummen generiert und veröffentlicht | erledigt |
| CI bricht ab, wenn eine veröffentlichte URL nicht auflöst | erledigt |
| `stitchlab-intake` und `pico-firmware` in `MODULES` | erledigt |
| `moonraker.asvc` mit Upstream-Defaults statt nur `live_jogd` | erledigt |
| [11-inbetriebnahme.md](11-inbetriebnahme.md) als durchgehender Weg | erledigt |
| **Auf echter Hardware durchlaufen — fremde SD-Karte, fremder Pico** | **offen** |
| Aufbauanleitung aus `Bauplan` mit der Software-Inbetriebnahme verzahnt | offen |

Der letzte Punkt ist der einzige, der zählt: Beta2 ist fertig, wenn jemand
anderes als die Autorinnen und Autoren eine Maschine damit zum Laufen bringt.

**Abnahme:** ein Durchlauf von Schritt 1 bis Schritt 4 in
[11-inbetriebnahme.md](11-inbetriebnahme.md) auf einem unbenutzten Pi und einem
fabrikneuen SKR Pico, protokolliert.

## 1.0 — Classic ist reproduzierbar

Nicht mehr Funktionen, sondern Verlässlichkeit.

- Ein Release-Build ist wiederholbar: Klipper-Host und Pico-Firmware kommen
  nachweislich aus demselben Stand.
- Update-Weg ist dokumentiert und getestet — auch der Fall „Host aktualisiert,
  Firmware nicht".
- Die offenen Punkte aus dem Praxistest sind abgearbeitet: Koordinatensystem und
  Homing erklärt, Ober-/Unterfaden dokumentiert, TurtleStitch-Beispiele auf dem
  Pi vorhanden.
- WLAN-Bedienung ist mehr als ein Patch um AccessPopup herum.
- Eine Liste getesteter Nähmaschinen, nicht nur die Pfaff 917.

## Hybrid — Nähen und Sticken in einer Maschine

Läuft weiter auf Klipper, erweitert Classic um die Mechanik und Regelung des
Nähens. Details in [hybrid/IMPLEMENTATION_PLAN.md](hybrid/IMPLEMENTATION_PLAN.md).

- Abnehmbares Gantry mit Verriegelung und Pogo-Steckverbinder
- AS5600-Encoder am Handrad als Nadelphase
- Nähmotor unter Klipper, Fußpedal über den ESP-Dongle
- Moduswechsel mit Sicherheitsverriegelung, in Mainsail sichtbar

Der Engpass ist der Antrieb: `MKSdrivemini` muss den Closed Loop belastbar
zeigen, `StitchHEAD` hat mit der TMC2209-UART-Konfiguration ein ungelöstes
Problem. Beides vor Terminzusagen klären.

## OpenRSS — der neue Kern

Eigenes Repo, eigene Planung, eigener Takt. Kein Zeitdruck aus Classic heraus.

- **Phase 0** Planungsbasis — läuft
- **Phase 1** Domänenmodell: Vokabular, Maschinen-, Prozess- und Auftragsmodell,
  Sicherheitsmodell
- **Phase 2** Motion-Kern: Entscheidung über LinuxCNC als Realtime-Schicht
  (Prototypplan liegt vor), sonst eigener Scheduler
- **Phase 3** Backend-neutraler Dienst (`stitchlabd`), der UI und Controller
  bedient und Motion an Adapter delegiert

Die Trennlinie zu diesem Repo: **aus StitchLabOS wandern Konzepte, kein Code.**
Bedienmuster, Dongle-Protokoll und die Lehren aus dem Praxistest sind Eingaben
für den Entwurf. Klipper, Moonraker und Mainsail sind es nicht.

---

## Was diese Roadmap nicht entscheidet

- Ob es Bausätze gibt. Derzeit nicht geplant.
- Ob StitchLabOS in die offizielle Raspberry-Pi-Imager-Liste aufgenommen wird.
  Sinnvoll erst nach einem stabilen 1.0 und mit fremdem Review.
- Wann `RPIcam2Embroidery` Teil des Images wird. Bisher eigenständig.
