# StitchLabOS

A Raspberry Pi OS image that turns a retired household sewing machine into a
computerized embroidery machine.

StitchLabOS is the software half of [StitchLAB](https://github.com/prntr): a
3D-printed conversion driven by 3D-printer electronics and Klipper. Flash one SD
card and the machine has motion control, a web UI, a visual stitch editor and
WiFi — no separate installation steps.

> **Status: beta.** There are a handful of working machines. This is aimed at
> people who have built something like a Voron or a DIY 3D printer before: parts
> have to be printed, cables crimped and soldered, and a machine has to be
> assembled. See [Is this for you?](#is-this-for-you) before you start.

## What you need

| | |
|---|---|
| Single-board computer | Raspberry Pi 4 or Pi 5 (64-bit) |
| SD card | 8 GB or larger |
| Controller board | BTT SKR Pico V1.0, wired to the Pi over UART (GPIO14/15) |
| Machine | A Pfaff Tipmatic/Hobbymatic conversion, or your own adaptation |
| Once, for commissioning | A USB data cable from the Pi to the Pico |

The mechanical side — printed parts, bill of materials, assembly — is not in
this repo.

## Getting started

### 1. Flash the card

Start [Raspberry Pi Imager](https://www.raspberrypi.com/software/) with the
current release's OS list, then pick **StitchLabOS** under *Choose OS*:

```bash
rpi-imager --repo https://github.com/prntr/StitchlabOS/releases/latest/download/os_list.json
```

Or download the `.img.xz` from the
[releases page](https://github.com/prntr/StitchlabOS/releases/latest) and use
*Choose OS → Use custom*. Imager's customisation dialog is unavailable on that
path, but nothing needs configuring — the image ships ready to use.

### 2. First boot

Insert the card and power the Pi. After about a minute:

- **WiFi AP** `Stitchlab` (password `praxistest`) → open http://stitchlab.local
- **SSH** `ssh pi@stitchlab.local` (password `lab`)

Mainsail loads but reports no MCU. That is expected — step 3 fixes it.

### 3. Bring up the SKR Pico

A factory-fresh SKR Pico holds no Klipper firmware, and an RP2040 only accepts
its first code over USB. The image carries the firmware, so this needs no second
computer and no internet:

```bash
ssh pi@stitchlab.local
stitchlab-flash-pico
```

Hold **BOOTSEL** on the Pico and plug it into a USB port of the Pi when
prompted. The script writes Katapult over USB, flashes Klipper over the UART and
verifies the MCU came up. The USB cable is needed exactly once — every later
firmware update runs over the UART alone.

The full walkthrough, including what to do when something sticks:
[docs/11-commissioning.md](docs/11-commissioning.md). The same guide is attached
to every release, matching that image.

### 4. Stitch

Open http://stitchlab.local. Upload G-code produced by
[Ink/Stitch](https://inkstitch.org/), or program a pattern directly in
TurtleStitch at http://stitchlab.local:3000 and send it to the machine.

## What is included

| Component | Source | What it does |
|---|---|---|
| [Klipper](https://github.com/Klipper3d/klipper) | upstream | Motion control, plus prebuilt SKR Pico firmware |
| [Moonraker](https://github.com/Arksine/moonraker) | upstream | API server |
| [Mainsail](https://github.com/prntr/mainsail) | prntr fork | Web UI with embroidery panel, WiFi manager, G-code studio, StitchLAB theme |
| [TurtleStitch](https://github.com/prntr/turtlestitch) | prntr fork | Visual stitch programming, offline, with G-code export to the machine |
| [stitchlabos-config](https://github.com/prntr/stitchlabos-config) | prntr | Embroidery macros, WiFi manager component, G-code intake checks |
| [Katapult](https://github.com/Arksine/katapult) | upstream | MCU bootloader, so firmware updates need no jumper |
| AccessPopup | third party | WiFi with access-point fallback |

Klipper, Moonraker, Mainsail and TurtleStitch update over the air from the
Mainsail update panel. After a Klipper host update, reflash the Pico with
`stitchlab-flash-pico --uart`.

## Default access

- **WiFi AP:** `Stitchlab` / `praxistest`, IP `192.168.50.5` — appears when no
  known network is in range
- **SSH:** `pi` / `lab`
- **Web UI:** http://stitchlab.local · **TurtleStitch:** `:3000` · **Moonraker:** `:7125`
- **UART to the SKR Pico:** GPIO14/15, 115200 baud

These are defaults for a workshop machine on a local network. Change the
password before putting a machine anywhere else.

## Is this for you?

This project is in development and assumes prior knowledge in several places.
Honest self-check:

- Have you 3D printed something, and do slicer, infill, support, brim and layer
  height mean something to you?
- Have you assembled a mechanism before — a DIY kit, a bicycle, a 3D printer?
- If you are not using one of the machines already tested, are you able to adapt
  parts in CAD from STEP files?

Including sourcing and printing the parts this is a substantial project. There
are no kits. Build at your own risk.

## Where this is going

StitchLAB Classic — this machine — is the shipping generation. Hybrid adds
actual sewing to the same machine; OpenRSS is a planned ground-up replacement
for this software stack aimed at modular textile robotics. See
[docs/10-roadmap.md](docs/10-roadmap.md).

## For developers

| | |
|---|---|
| Documentation index | [docs/README.md](docs/README.md) |
| Architecture | [docs/02-architecture.md](docs/02-architecture.md) |
| Building the image | [docs/08-image-building.md](docs/08-image-building.md) |
| SKR Pico firmware | [firmware/README.md](firmware/README.md) |
| All related repos | [docs/00-ecosystem.md](docs/00-ecosystem.md) |

Images are built with [CustomPiOS](https://github.com/guysoft/CustomPiOS) on
GitHub Actions; pushing a `v*` tag builds the image and creates a release. The
image is not built locally.

`mainsail/`, `turtlestitch/` and `stitchlabos-config/` are submodules — clone
with `--recurse-submodules`.

## Credits

Built on Klipper, Moonraker, Mainsail, TurtleStitch, AccessPopup, Katapult and
Raspberry Pi OS. Developed at Studio Praxistest and the tailoring workshop of
the art education department, University of Applied Arts Vienna, to give schools
and the DIY community a low-threshold entry into embroidery.

Related open source embroidery work: [Ink/Stitch](https://inkstitch.org/),
[Embroiderino](https://lordovervolt.com/embroidery).

## License

GPLv3
