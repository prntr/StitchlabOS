# Commissioning — from SD card to a stitching machine

> The path for a **new** machine: flash the card, bring the SKR Pico up, check
> the axes. To deploy a development build onto a machine that already runs, see
> [04-quickstart-pi.md](04-quickstart-pi.md).

You need a Raspberry Pi 4 or 5, a microSD card (8 GB or larger), a USB cable to
the SKR Pico for exactly one step, and the wired machine.

---

## 1. Flash the SD card

```bash
rpi-imager --repo https://github.com/prntr/StitchlabOS/releases/latest/download/os_list.json
```

StitchLabOS then appears under *Choose OS*. Imager's customisation dialog
(hostname, WiFi, SSH) is available on this path but **not needed** — the image
already ships SSH, a hostname and AP-mode WiFi setup.

Without `--repo` it also works: *Choose OS → Use custom*, then pick the
`.img.xz` from the [release page](https://github.com/prntr/StitchlabOS/releases/latest).
On that path Imager's customisation dialog stays greyed out, because Imager
cannot read an `init_format` for a hand-picked image.

## 2. First boot

Insert the card, power the Pi, wait about a minute.

- **AP mode**: WiFi `Stitchlab`, password `praxistest`, then http://stitchlab.local
  (or http://192.168.50.5)
- **SSH**: `ssh pi@stitchlab.local`, password `lab`

Mainsail loads but reports **no MCU**. That is correct at this point and not a
fault — step 3 fixes it.

## 3. Bring up the SKR Pico

A factory-fresh SKR Pico holds no Klipper firmware. An RP2040 accepts its first
code only over USB in BOOTSEL mode; over the UART lines that Klipper later talks
on, a virgin board cannot be reached at all.

The image carries the firmware, so this needs neither a second computer nor
internet access:

```bash
ssh pi@stitchlab.local
stitchlab-flash-pico
```

The script walks through it:

1. It stops `klipper`, which otherwise holds `/dev/serial0`.
2. It asks you to hold **BOOTSEL** on the Pico and plug the Pico into a USB port
   of the Pi.
3. It writes `katapult.uf2` to the `RPI-RP2` drive that appears.
4. After the Pico reboots, it flashes `klipper.bin` over `/dev/serial0` (up to
   three attempts — the RP2040 occasionally misses the first serial resync).
5. It restarts `klipper` and checks `klippy.log` for the MCU.

**The USB cable is needed exactly once.** Once Katapult is on the board, every
further firmware update runs over the same UART lines:

```bash
stitchlab-flash-pico --uart
```

## 4. Check

```bash
ls /dev/serial0                    # must exist
systemctl status klipper moonraker nginx
tail -5 /home/pi/printer_data/logs/klippy.log
```

In Mainsail: the `pico` temperature is shown, and the axes move after homing.

---

## When something sticks

### No `RPI-RP2` drive appears

The script waits 120 seconds for a drive with that label.

- BOOTSEL must be held **while plugging in**, not afterwards.
- Some USB-C cables carry power only. Use a data cable.
- Check whether the Pi sees the device at all: `lsusb | grep 2e8a`
  (`2e8a:0003` is the RP2040 in BOOTSEL mode).

### `/dev/serial0` is missing

The UART is off by default on Raspberry Pi OS. The image sets what is needed at
build time; if it is missing:

```bash
grep 'enable_uart\|disable-bt' /boot/firmware/config.txt
grep 'serial0' /boot/firmware/cmdline.txt   # must return nothing
```

See [08-image-building.md](08-image-building.md).

### The MCU does not answer

```bash
tail -30 /home/pi/printer_data/logs/klippy.log
```

| Message | Cause |
|---|---|
| `Unable to open port /dev/serial0` | UART not enabled, or `console=serial0` still in `cmdline.txt` |
| `Unable to connect` | No firmware on the Pico, or TX and RX are swapped |
| `Serial connection closed` on every cold boot | Plymouth writes to the UART — `plymouth.ignore-serial-consoles` missing from `cmdline.txt` |
| `MCU protocol error` / version warning | Host Klipper was updated, firmware was not. Run `stitchlab-flash-pico --uart` |

Check the wiring — TX and RX cross over:

```text
Pi GPIO14 (TXD) ──► Pico GPIO1 (UART0 RX)
Pi GPIO15 (RXD) ──► Pico GPIO0 (UART0 TX)
GND ─────────────── GND
```

### Katapult is broken

If `--uart` no longer works but the board is still reachable over BOOTSEL:

```bash
stitchlab-flash-pico --bootsel     # rewrite Katapult, then continue normally
```

If Katapult itself is the problem, the bootloader-free build helps. Afterwards
**every** further update needs BOOTSEL again until Katapult is written back:

```bash
stitchlab-flash-pico --standalone
```

### Klipper version does not match the firmware

Host and firmware come from the same CI run. After an update through Moonraker's
`update_manager` the host runs ahead of the firmware — one
`stitchlab-flash-pico --uart` and they match again. This is the usual Klipper
workflow, not a StitchLAB quirk.
