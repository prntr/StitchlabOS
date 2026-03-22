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
| live_jogd | USB serial bridge |

## GitHub Repository

- Repo: `https://github.com/prntr/StitchlabOS`
- Main submodules: `mainsail` → `prntr/mainsail` (branch `stitchlabos/v2.17.0`), `turtlestitch` → `prntr/turtlestitch` (branch `master`)

## Using Pre-built Images

### Raspberry Pi Imager

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Select **Choose OS → Other general-purpose OS → Use custom**
3. Enter URL: `https://github.com/prntr/StitchlabOS/releases/latest/download/StitchLabOS-latest.img.xz`
4. Configure hostname, WiFi, SSH via Imager settings (works because `KEEP_CLOUDINIT="yes"` and `"init_format": "cloudinit-rpi"` in `os_list.json`)
5. Flash to SD card

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

After flashing (Pi Imager customization is **not supported** — the "Anpassen" button is grayed out):

1. **SSH**: Enabled by default. Login: `pi` / `lab`
2. **Hostname**: `stitchlab` (resolves as `stitchlab.local` via avahi)
3. **AP Mode**: If no WiFi is configured, AccessPopup creates a hotspot within ~30 seconds
   - SSID: `Stitchlab`, password: `praxistest`, IP: `192.168.50.5`
4. **Adding WiFi**: Connect to the Stitchlab AP → open `http://stitchlab.local` → use the WiFi Manager in Mainsail

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
systemctl status nginx moonraker klipper live_jogd
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

Pi Imager customization (hostname/WiFi/SSH) does not work with this image — the button is grayed out despite `KEEP_CLOUDINIT="yes"`. Use the built-in defaults instead: SSH is enabled, password is `lab`, AP mode activates automatically.

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

The `stitchlabos` module's `start_chroot_script` applies these automatically during the build.

### Hostname is `stitchlabos` instead of `stitchlab`

CustomPiOS auto-generates `BASE_OVERRIDE_HOSTNAME` from `DIST_NAME` (lowercased). Explicitly set `BASE_OVERRIDE_HOSTNAME="stitchlab"` in `src/config` to override it.

### Password doesn't match expected value

`userconf-pi` runs on first boot and sets the password from `BASE_USER_PASSWORD`. Any `chpasswd` call inside a chroot script is overwritten. Always set the password via `BASE_USER_PASSWORD` in `src/config`.

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
