# Inbetriebnahme — von der SD-Karte zur laufenden Maschine

> Der Weg für eine neue Maschine: SD-Karte flashen, Pico in Betrieb nehmen,
> Achsen prüfen. Für Entwicklungs-Deployments auf eine bereits laufende Maschine
> siehe [04-quickstart-pi.md](04-quickstart-pi.md).

Gebraucht werden: Raspberry Pi 4 oder 5, microSD (≥ 8 GB), ein USB-Kabel zum
SKR Pico für genau einen Schritt, und die verdrahtete Maschine.

---

## 1. SD-Karte flashen

```bash
rpi-imager --repo https://github.com/prntr/StitchlabOS/releases/latest/download/os_list.json
```

StitchLabOS erscheint dann unter *Choose OS*. Die Anpassungen (Hostname, WLAN,
SSH) sind auf diesem Weg verfügbar, aber **nicht nötig** — das Image bringt SSH,
Hostname und AP-Modus bereits mit.

Ohne `--repo` geht es auch: *Choose OS → Use custom* und die `.img.xz` von der
[Release-Seite](https://github.com/prntr/StitchlabOS/releases/latest) wählen. Auf
diesem Weg bleibt Imagers Anpassen-Dialog ausgegraut, weil Imager zu einem frei
gewählten Image kein `init_format` kennt.

## 2. Erster Start

Karte einlegen, Pi einschalten, etwa eine Minute warten.

- **AP-Modus**: WLAN `Stitchlab`, Passwort `praxistest`, dann http://stitchlab.local
  (oder http://192.168.50.5)
- **SSH**: `ssh pi@stitchlab.local`, Passwort `lab`

Mainsail lädt, meldet aber **keinen MCU**. Das ist an dieser Stelle richtig und
kein Fehler — Schritt 3 behebt es.

## 3. SKR Pico in Betrieb nehmen

Ein fabrikneuer SKR Pico hat keine Klipper-Firmware. Ein RP2040 nimmt den ersten
Code ausschließlich über USB im BOOTSEL-Modus an; über die UART-Leitungen, an
denen Klipper später spricht, ist ein jungfräuliches Board nicht erreichbar.

Das Image bringt die Firmware mit, es braucht also weder einen zweiten Rechner
noch Internet:

```bash
ssh pi@stitchlab.local
stitchlab-flash-pico
```

Das Skript führt durch den Ablauf:

1. Es stoppt `klipper`, das sonst `/dev/serial0` belegt.
2. Es fordert auf, **BOOTSEL** am Pico zu halten und den Pico per USB an einen
   USB-Port des Pi zu stecken.
3. Es schreibt `katapult.uf2` auf das dann erscheinende `RPI-RP2`-Laufwerk.
4. Nach dem Neustart des Pico flasht es `klipper.bin` über `/dev/serial0`
   (bis zu drei Versuche — der RP2040 verpasst gelegentlich die erste
   Serial-Resynchronisierung).
5. Es startet `klipper` neu und prüft `klippy.log` auf den MCU.

**Das USB-Kabel wird genau einmal gebraucht.** Sobald Katapult auf dem Board ist,
läuft jedes weitere Firmware-Update über dieselben UART-Leitungen:

```bash
stitchlab-flash-pico --uart
```

## 4. Prüfen

```bash
ls /dev/serial0                    # muss existieren
systemctl status klipper moonraker nginx
tail -5 /home/pi/printer_data/logs/klippy.log
```

In Mainsail: Temperatur `pico` wird angezeigt, und die Achsen lassen sich nach
einem Homing bewegen.

---

## Wenn etwas klemmt

### Kein `RPI-RP2`-Laufwerk erscheint

Das Skript wartet 120 Sekunden auf ein Laufwerk mit diesem Label.

- BOOTSEL muss **beim Einstecken** gedrückt sein, nicht danach.
- Manche USB-C-Kabel führen nur Strom. Ein Datenkabel verwenden.
- Prüfen, ob der Pi das Gerät überhaupt sieht: `lsusb | grep 2e8a`
  (`2e8a:0003` ist der RP2040 im BOOTSEL-Modus).

### `/dev/serial0` fehlt

Die UART ist auf Raspberry Pi OS standardmäßig aus. Das Image setzt die nötigen
Werte beim Build; falls sie fehlen:

```bash
grep 'enable_uart\|disable-bt' /boot/firmware/config.txt
grep 'serial0' /boot/firmware/cmdline.txt   # darf nichts liefern
```

Siehe [08-image-building.md](08-image-building.md).

### MCU meldet sich nicht

```bash
tail -30 /home/pi/printer_data/logs/klippy.log
```

| Meldung | Ursache |
|---|---|
| `Unable to open port /dev/serial0` | UART nicht aktiviert, oder `console=serial0` steht noch in `cmdline.txt` |
| `Unable to connect` | Firmware ist nicht auf dem Pico, oder TX/RX sind vertauscht |
| `Serial connection closed` bei jedem Kaltstart | Plymouth schreibt auf die UART — `plymouth.ignore-serial-consoles` in `cmdline.txt` fehlt |
| `MCU protocol error` / Versionswarnung | Host-Klipper wurde aktualisiert, Firmware nicht. `stitchlab-flash-pico --uart` |

Verdrahtung gegenprüfen — TX und RX sind gekreuzt:

```text
Pi GPIO14 (TXD) ──► Pico GPIO1 (UART0 RX)
Pi GPIO15 (RXD) ──► Pico GPIO0 (UART0 TX)
GND ─────────────── GND
```

### Katapult ist zerschossen

Wenn `--uart` nicht mehr greift, das Board aber noch über BOOTSEL erreichbar ist:

```bash
stitchlab-flash-pico --bootsel     # Katapult neu schreiben, dann normal weiter
```

Wenn Katapult selbst das Problem ist, hilft der bootloaderfreie Build. Danach
braucht **jedes** weitere Update wieder BOOTSEL, bis Katapult erneut geschrieben
wird:

```bash
stitchlab-flash-pico --standalone
```

### Klipper-Version passt nicht zur Firmware

Host und Firmware stammen aus demselben CI-Lauf. Nach einem Update über
Moonrakers `update_manager` liegt der Host vor der Firmware — einmal
`stitchlab-flash-pico --uart`, dann stimmt es wieder. Das ist der übliche
Klipper-Ablauf, kein StitchLAB-Sonderfall.
