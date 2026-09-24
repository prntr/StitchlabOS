# Image Building

> Build and distribute StitchLabOS images for Raspberry Pi.

## Overview

StitchLabOS is built using [CustomPiOS](https://github.com/guysoft/CustomPiOS) (devel branch) via GitHub Actions. The image includes all StitchLAB components pre-configured and is compatible with Raspberry Pi Imager (hostname/WiFi/SSH configurable at flash time).

**Included Components:**

| Component | Purpose |
|-----------|---------|
| Klipper + Moonraker | Motion control and API |
| Mainsail | Web UI (custom StitchLAB fork) |
| TurtleStitch | Visual programming for embroidery |
| KIAUH | Klipper management tool |
| Katapult | MCU bootloader |
| AccessPopup | WiFi AP fallback mode |
| live_jogd | USB serial bridge, installed but started by the Controller menu on demand |

### SKR Pico firmware is part of the image

A factory-fresh SKR Pico holds no Klipper firmware, so a freshly flashed card
alone leaves Klipper without an MCU. Beta1 required building firmware on a
separate dev machine; a Pi in AP mode has no internet, so "build it on the Pi"
was not an option either.

CI now builds the firmware from `firmware/skr-pico/*.config` and the
`pico-firmware` module ships it in `/home/pi/firmware/`:

| File | Purpose |
|---|---|
| `katapult.uf2` | Bootloader at `0x10000100`, written once over USB BOOTSEL |
| `klipper.bin` | Application at `0x10004000`, written through Katapult over `/dev/serial0` |
| `klipper.uf2` | Same application as a UF2 — only boots with Katapult present |
| `klipper-standalone.uf2` | Bootloader-free build at `0x10000100` for rescuing a board |

Commissioning is one command on the Pi:

```bash
ssh pi@stitchlab.local
stitchlab-flash-pico
```

It stops Klipper, waits for the Pico to appear in BOOTSEL mode, writes Katapult,
flashes Klipper over the UART (retrying the known RP2040 serial-resync quirk),
restarts Klipper and checks `klippy.log` for the MCU. After that, every firmware
update runs over `/dev/serial0` alone — no jumper, no cable. See
[11-commissioning.md](11-commissioning.md).

**Config contract.** The seed configs pin UART0 on GPIO0/GPIO1 at **115200 baud**,
which must equal `baud:` in
[`printer.cfg`](../stitchlabos/image/src/modules/klipper/filesystem/home/pi/printer_data/config/printer.cfg).
Upstream renamed these symbols to the `RPXXXX_*` / `MACH_RPXXXX` family (older
notes say `CONFIG_RP2040_FLASH_START_4000`); the addresses are unchanged. CI
asserts that every seeded symbol survives `make olddefconfig`, so a further
rename fails the build instead of shipping mute firmware.

**Klipper version.** Host and firmware are both built from master within the same
CI run. After `update_manager` later updates the host Klipper, reflash the Pico
with `stitchlab-flash-pico --uart` to clear the version-mismatch warning.

## GitHub Repository

- Repo: `https://github.com/prntr/StitchlabOS`
- Main submodules: `mainsail` → `prntr/mainsail` (branch `stitchlabos/v2.17.0`), `turtlestitch` → `prntr/turtlestitch` (branch `master`)

## Using Pre-built Images

### Raspberry Pi Imager

**Preferred — StitchLabOS as a selectable OS.** CI publishes an `os_list.json`
with each release, so Imager can offer StitchLabOS like any other image, with its
customisation dialog available:

```bash
rpi-imager --repo https://github.com/prntr/StitchlabOS/releases/latest/download/os_list.json
```

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Start it with the `--repo` argument above
3. **Choose OS → StitchLabOS**
4. Customisation (hostname/WiFi/SSH) is optional — the image already ships SSH, a
   default password and AP-mode WiFi setup
5. Flash to SD card

**Fallback — direct image.** **Choose OS → Use custom**, then pick the `.img.xz`
from the [release page](https://github.com/prntr/StitchlabOS/releases/latest). Do
not hand-type an asset URL: the filename carries the version
(`StitchLabOS-v0.1.0-beta.1.img.xz`), and there is deliberately no `-latest`
alias. On this path Imager cannot read an `init_format`, so its customisation
dialog stays greyed out — see
[Troubleshooting](#pi-imager-anpassen-button-is-grayed-out).

### Direct Download

Download from [GitHub Releases](https://github.com/prntr/StitchlabOS/releases).

## CI/CD Pipeline

GitHub Actions builds on tags (`v*`) and manual dispatch. **Never** on every push to main — builds take ~60-90 minutes.

**Workflow:** `.github/workflows/build-image.yml`

### Build Steps (in order)

1. Checkout repo with `submodules: recursive` (pulls `prntr/mainsail` and `prntr/turtlestitch`)
2. Build Mainsail: `npm ci && npm run build`, copy `dist/` → `modules/mainsail/filesystem/home/pi/mainsail/`
3. Copy TurtleStitch submodule → `modules/turtlestitch/filesystem/home/pi/turtlestitch/`
4. Install host dependencies (including `gitpython` for CustomPiOS's `execution_order.py`)
5. Clone CustomPiOS (`--depth=1`)
6. Download Raspberry Pi OS Lite arm64 (`.img.xz`) into `stitchlabos/image/src/image-raspberrypiarm64/` — **this exact path is required** by CustomPiOS's `generate_board_config.py` which searches `$DIST_PATH/image-{BOARD}/` for `*.xz` files to set `BASE_ZIP_IMG`. The image is also **expanded to 6GB** before recompressing: Pi OS Lite only has ~1.5GB free on its rootfs which isn't enough for Klipper/Moonraker deps + pip virtualenvs. Expansion: `truncate -s 6G img` → `parted resizepart 2 100%` → `losetup -P` → `e2fsck -fy` + `resize2fs` → `xz -1 -T0`.
7. Run CustomPiOS build: `sudo DIST_PATH=... CUSTOM_PI_OS_PATH=... bash -x .../build`
8. Compress output with `xz -9`, generate sha256
9. Upload as artifact (7-day retention)
10. Create GitHub Release on tags

### Key CustomPiOS API Notes

- **Script name**: `CustomPiOS/src/build` (not `build_dist` — that was renamed)
- **Entry method**: Must pass `DIST_PATH` and `CUSTOM_PI_OS_PATH` as env vars to the `sudo` call
- **Base image discovery**: `generate_board_config.py` looks for `*.xz`/`*.zip`/`*.7z` in `$DIST_PATH/image-{BASE_BOARD}/`. Our board is `raspberrypiarm64`, so the download goes into `stitchlabos/image/src/image-raspberrypiarm64/`
- **`CLEAN` env var**: Do NOT set — it deletes the pre-downloaded base image before building
- **`-d` flag**: Does NOT exist in the devel branch despite the error message; the "auto-download" feature was never implemented

### Triggering a Build

```bash
# Trigger manual run
gh workflow run build-image.yml --repo prntr/StitchlabOS

# Monitor
gh run list --repo prntr/StitchlabOS --limit 5
gh run view <RUN_ID> --repo prntr/StitchlabOS
gh run view <RUN_ID> --repo prntr/StitchlabOS --log-failed

# Tag release (triggers build + GitHub Release)
git tag v1.0.0 && git push origin v1.0.0
```

## Module Structure

```
stitchlabos/image/src/
├── config                          # Main CustomPiOS config (BASE_BOARD, MODULES, etc.)
├── image-raspberrypiarm64/         # Base image download directory (gitignored)
├── workspace/                      # Build output (gitignored)
└── modules/
    ├── klipper/                    # Klipper + Moonraker + virtualenvs
    ├── kiauh/                      # KIAUH tool
    ├── katapult/                   # Katapult bootloader
    ├── accesspopup/                # AP mode fallback
    ├── mainsail/                   # nginx config; dist files copied by CI
    ├── turtlestitch/               # nginx config; files copied by CI
    ├── live-jogd/                  # USB serial daemon
    └── stitchlabos/                # Final customizations (wifi_manager, macros, hostname)
```

Each module contains:
- `config` — exported shell variables (prefixed `MODULENAME_`)
- `start_chroot_script` — runs inside the ARM chroot; must start with `source /common.sh`
- `filesystem/` — files unpacked into the image via `unpack /filesystem/... /target owner`

Build order is defined in `src/config`:
```bash
MODULES="base(klipper,kiauh,katapult,accesspopup,mainsail,turtlestitch,live-jogd,stitchlabos)"
```

### Module Script Notes

- **virtualenvs**: Use `virtualenv -p python3 <path>` not `python3 -m venv` — `ensurepip` fails on Debian Trixie
- **git clones**: Always use `--depth=1` to save image space
- **Klipper/Moonraker**: Remove `docs/` after cloning — large image assets cause "No space left on device"
- **ARM toolchain** (`gcc-arm-none-eabi`, `libnewlib-arm-none-eabi`, `avrdude`): NOT installed in the image — firmware is compiled on a dev machine, not on the Pi
- **Mainsail/TurtleStitch**: Both `start_chroot_script` files must call `unpack /filesystem/home/pi /home/pi pi` to copy CI-built assets into the image

## src/config Reference

```bash
export DIST_NAME="StitchLabOS"
export DIST_VERSION="0.1.0"
export BASE_BOARD="raspberrypiarm64"
export BASE_IMAGE_SECTION="latest"
export MODULES="base(klipper,kiauh,katapult,accesspopup,mainsail,turtlestitch,live-jogd,stitchlabos)"
export DIST_HOSTNAME="stitchlab"
export BASE_OVERRIDE_HOSTNAME="stitchlab"   # Prevents CustomPiOS from using lowercased DIST_NAME
export BASE_USER="pi"
export BASE_USER_PASSWORD="lab"             # Default SSH password
export KEEP_CLOUDINIT="yes"
```

> **Note:** `BASE_OVERRIDE_HOSTNAME` is required because CustomPiOS auto-generates a hostname from `DIST_NAME` (which would produce `stitchlabos`). `BASE_USER_PASSWORD` is used by the `userconf-pi` first-boot service — it overrides any `chpasswd` call made inside a chroot script.

## First Boot

No Pi Imager customization needed — StitchLabOS is ready to use out of the box:

1. **AP Mode**: On first boot (no WiFi configured), AccessPopup creates a hotspot within ~30 seconds
   - SSID: `Stitchlab`, password: `praxistest`, IP: `192.168.50.5`
2. **Adding WiFi**: Connect to the Stitchlab AP → open `http://stitchlab.local` (or `http://192.168.50.5`) → use the WiFi Manager in Mainsail
3. **SSH**: Enabled by default. Login: `pi` / `lab`
4. **Hostname**: `stitchlab` (resolves as `stitchlab.local` via avahi)

### Access

```bash
# Over Stitchlab AP or local network
ssh pi@stitchlab.local   # password: lab

# Or by IP when connected to the Stitchlab AP
ssh pi@192.168.50.5
```

### Verify Services

```bash
ssh pi@stitchlab.local
systemctl status nginx moonraker klipper
systemctl is-enabled live_jogd       # expected: static
systemctl is-active live_jogd || true # expected: inactive until Controller-menu connect
grep -qx live_jogd /home/pi/printer_data/moonraker.asvc && echo live_jogd-allowed
systemctl is-enabled stitchlab-moonraker-service-control-patch.service
systemctl list-timers | grep AccessPopup
ls /dev/serial0   # UART for SKR Pico — must exist
tail -5 /home/pi/printer_data/logs/klippy.log
```

### Access Points

| Service | URL |
|---------|-----|
| Mainsail | http://stitchlab.local |
| TurtleStitch | http://stitchlab.local:3000 |
| Moonraker API | http://stitchlab.local:7125 |

## Troubleshooting

### Pi Imager "Anpassen" button is grayed out

This is a property of the **Use custom** path, not of the image. Imager greys the
customisation dialog out whenever it cannot read an `init_format` for the
selected image — and a hand-picked `.img.xz` carries no metadata.

Start Imager with `--repo .../os_list.json` (see [Using Pre-built
Images](#using-pre-built-images)) and the dialog is available: the image keeps
cloud-init (`KEEP_CLOUDINIT="yes"` in `src/config`), which is why the OS list
declares `init_format: cloudinit-rpi` — the same value current Raspberry Pi OS
uses. `systemd` is the *Legacy* Raspberry Pi OS value and would be wrong here.

Either way no manual configuration is required: StitchLabOS ships with SSH
enabled (`pi` / `lab`), the hostname `stitchlab`, and AP mode
(`Stitchlab` / `praxistest`) for WiFi setup on first boot.

### AccessPopup WiFi not appearing

Most likely cause: standalone `dnsmasq` is installed alongside NetworkManager. When the AP activates, NetworkManager spawns its own internal dnsmasq for `ipv4.method=shared` — but if a system dnsmasq is already running, it has already bound port 53 and NM's instance fails to start, causing the AP activation to silently fail every 2 minutes.

**Fix:**
```bash
sudo systemctl stop dnsmasq
sudo systemctl disable dnsmasq
sudo /usr/bin/accesspopup
```

The `stitchlabos` module must NOT install `dnsmasq` as a package. Custom DNS entries (e.g. `stitchlab.local → 192.168.50.5`) go in `/etc/NetworkManager/dnsmasq-shared.d/` which NM's internal dnsmasq picks up automatically.

### SKR Pico not reachable (`/dev/serial0` missing)

UART is disabled by default on Raspberry Pi OS. Required additions to `/boot/firmware/config.txt` under `[all]`:
```
enable_uart=1
dtoverlay=disable-bt
```
Also remove `console=serial0,115200` from `/boot/firmware/cmdline.txt` — it claims the UART for the Linux console, blocking Klipper.

### SKR Pico: "Serial connection closed" on every boot

Plymouth (boot splash) sends data to the hardware UART during boot, corrupting the Pico's serial state. Required addition to `/boot/firmware/cmdline.txt`:
```
quiet splash plymouth.ignore-serial-consoles
```

Without this, Klipper fails to connect to the MCU on every cold boot and the Pico must be manually reset.

The `stitchlabos` module's `start_chroot_script` applies all UART fixes (`config.txt`, `cmdline.txt`, Plymouth) automatically during the build.

### Shutdown/Reboot not working from Mainsail

Moonraker needs polkit rules to call `systemctl poweroff/reboot`. The `klipper` module creates `/etc/polkit-1/rules.d/moonraker.rules` during the build. If missing, the Mainsail shutdown/reboot buttons silently fail with `Interactive authentication required` in the Moonraker log. See [06-troubleshooting.md](06-troubleshooting.md#shutdown--reboot-from-mainsail) for the manual fix.

### Hostname is `stitchlabos` instead of `stitchlab`

CustomPiOS auto-generates `BASE_OVERRIDE_HOSTNAME` from `DIST_NAME` (lowercased). Explicitly set `BASE_OVERRIDE_HOSTNAME="stitchlab"` in `src/config` to override it.

### Password doesn't match expected value

`userconf-pi` runs on first boot and sets the password from `BASE_USER_PASSWORD`. Any `chpasswd` call inside a chroot script is overwritten. Always set the password via `BASE_USER_PASSWORD` in `src/config`.

### SSH login closes with "This account is currently not available"

SSH is enabled, and the password was accepted, but the `pi` user's shell is set to `nologin` instead of `/bin/bash`. The StitchLabOS module forces `pi` to `/bin/bash` during the image build before setting the default password, so releases remain SSH-accessible even if the base Raspberry Pi OS image has a first-boot `userconf-pi` regression.

Manual recovery on a mounted/root shell:
```bash
sudo usermod -s /bin/bash pi
sudo passwd pi
```

### "No space left on device" during build

- The base image is expanded to 6GB in the CI workflow before building (see step 6 above)
- ARM toolchain (`gcc-arm-none-eabi` etc.) is NOT installed — ~700MB saving
- All `git clone` calls use `--depth=1`
- `docs/` is removed from Klipper and Moonraker after cloning

### "Error: could not find image"

- Base image must be in `stitchlabos/image/src/image-raspberrypiarm64/*.xz`
- Do NOT set `CLEAN=true` — it deletes the downloaded image before building

### `ModuleNotFoundError: No module named 'git'`

- Host runner needs `gitpython`: `pip3 install gitpython --break-system-packages`

### `ensurepip` failure in virtualenv creation

- Use `virtualenv -p python3 <path>` instead of `python3 -m venv <path>`

### Build fails with "loop device" error

```bash
sudo modprobe loop
echo "loop" | sudo tee /etc/modules-load.d/loop.conf
```

## Adding a Module

1. Create `src/modules/mymodule/config` with exported variables
2. Create `src/modules/mymodule/start_chroot_script` starting with `#!/usr/bin/env bash\nset -e\nsource /common.sh`
3. Add `filesystem/` for static files (copied via `unpack`)
4. Add module name to `MODULES` in `src/config`

See [CustomPiOS docs](https://github.com/guysoft/CustomPiOS) for details.
