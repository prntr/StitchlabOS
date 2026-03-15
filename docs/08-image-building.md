# Image Building

> Build and distribute StitchLabOS images for Raspberry Pi.

## Overview

StitchLabOS is built using [CustomPiOS](https://github.com/guysoft/CustomPiOS), a framework for creating custom Raspberry Pi distributions. The image includes all StitchLAB components pre-configured.

**Included Components:**

| Component | Purpose |
|-----------|---------|
| Klipper + Moonraker | Motion control and API |
| Mainsail | Web UI |
| TurtleStitch | Visual programming for embroidery |
| KIAUH | Klipper management tool |
| Katapult | MCU bootloader |
| AccessPopup | WiFi AP fallback mode |
| live_jogd | USB serial bridge |

## Using Pre-built Images

### Raspberry Pi Imager

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Select **Choose OS → Other general-purpose OS → Use custom**
3. Enter URL: `https://github.com/stitchlab/stitchlabos/releases/latest/download/StitchLabOS-latest.img.xz`
4. Configure hostname, WiFi, SSH via Imager settings
5. Flash to SD card

### Direct Download

Download from [GitHub Releases](https://github.com/stitchlab/stitchlabos/releases).

## Building Locally

### Prerequisites

- Linux system (Ubuntu/Debian recommended)
- 10GB+ free disk space
- `sudo` access

### Build Steps

```bash
# Clone CustomPiOS
git clone https://github.com/guysoft/CustomPiOS.git

# Update paths
cd stitchlabos/image
../../CustomPiOS/src/update-custompios-paths

# Build
cd src
sudo bash -x ./build_dist
```

Output: `src/workspace/StitchLabOS-*.img`

## CI/CD Pipeline

GitHub Actions automatically builds on:
- Push to `main`
- Tags (`v*`)
- Manual dispatch

**Workflow:** [.github/workflows/build.yml](../stitchlabos/image/.github/workflows/build.yml)

Steps:
1. Build Mainsail from `mainsail/` submodule
2. Copy TurtleStitch from `turtlestitch/` submodule
3. Run CustomPiOS build
4. Compress with xz
5. Upload artifacts (7-day retention)
6. Create GitHub Release on tags

## Module Structure

```
stitchlabos/image/src/modules/
├── klipper/          # Klipper + Moonraker
├── kiauh/            # KIAUH tool
├── katapult/         # Katapult bootloader
├── accesspopup/      # AP mode scripts
├── mainsail/         # Web UI + nginx
├── turtlestitch/     # TurtleStitch + nginx
├── live-jogd/        # USB serial daemon
└── stitchlabos/      # Final customizations
```

Each module contains:
- `config` - Module variables
- `start_chroot_script` - Installation script
- `filesystem/` - Files to copy to image

Build order is defined in `src/config`:
```
MODULES="base(klipper,kiauh,katapult,accesspopup,mainsail,turtlestitch,live-jogd,stitchlabos)"
```

## First Boot

After flashing and booting:

1. **Hostname**: As configured in Imager (default: `stitchlab`)
2. **WiFi**: Connects automatically if configured
3. **SSH**: Enabled with configured credentials
4. **AP Mode**: If WiFi fails, AccessPopup creates hotspot within 2 minutes
   - SSID: `AccessPopup`
   - IP: `192.168.50.5`

### Verify Services

```bash
ssh pi@stitchlab.local
systemctl status nginx moonraker klipper
systemctl list-timers | grep AccessPopup
```

### Access Points

| Service | URL |
|---------|-----|
| Mainsail | http://stitchlab.local |
| TurtleStitch | http://stitchlab.local:3000 |
| Moonraker API | http://stitchlab.local:7125 |

## Adding a Module

1. Create directory: `src/modules/mymodule/`
2. Create `config` with variables
3. Create `start_chroot_script` with installation logic
4. Add `filesystem/` for static files
5. Add to `MODULES` in `src/config`

See [CustomPiOS docs](https://github.com/guysoft/CustomPiOS) for details.

## Troubleshooting

### Build fails with "loop device" error

```bash
sudo modprobe loop
```

### Image too large

- Base image is Raspberry Pi OS Full (~8GB extracted)
- Use xz compression for distribution

### Pi Imager doesn't show customization options

- Ensure `KEEP_CLOUDINIT="yes"` in `src/config`
- `os_list.json` must have `"init_format": "cloudinit-rpi"`

## Building with UTM (macOS)

CustomPiOS requires Linux. On macOS, use a UTM virtual machine.

### Recommended Setup

**Ubuntu Server 24.04 LTS (ARM64)** - native on Apple Silicon, no emulation overhead.

| Setting | Value |
|---------|-------|
| Architecture | ARM64 (Virtualize, not Emulate) |
| RAM | 8 GB |
| CPU | 4 cores |
| Disk | 40 GB |
| Network | Shared Network |

### VM Installation

1. Download: [Ubuntu Server ARM64](https://ubuntu.com/download/server/arm)
2. Create VM in UTM with above settings
3. Install Ubuntu Server (minimal, enable SSH)

### Post-Install Setup

```bash
# Update and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    git qemu-user-static binfmt-support p7zip-full xz-utils jq \
    curl wget coreutils util-linux gawk realpath file \
    kpartx dosfstools e2fsprogs parted zerofree zip bsdtar

# Enable loop device
sudo modprobe loop
echo "loop" | sudo tee /etc/modules-load.d/loop.conf

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### SSH Access

```bash
# Get VM IP
ip addr show

# On macOS ~/.ssh/config
Host stitchlab-builder
    HostName <VM-IP>
    User builder
```

### Build Script

Create `~/build-stitchlabos.sh` on the VM:

```bash
#!/bin/bash
set -e

BUILD_DIR="$HOME/build"
REPO_DIR="$HOME/MainsailDev"

sudo modprobe loop
mkdir -p "$BUILD_DIR" && cd "$BUILD_DIR"

# Clone CustomPiOS
[ ! -d "CustomPiOS" ] && git clone https://github.com/guysoft/CustomPiOS.git

# Build Mainsail
cd "$REPO_DIR/mainsail" && npm ci && npm run build
mkdir -p "$REPO_DIR/stitchlabos/image/src/modules/mainsail/filesystem/home/pi/mainsail"
cp -r dist/* "$REPO_DIR/stitchlabos/image/src/modules/mainsail/filesystem/home/pi/mainsail/"

# Prepare TurtleStitch
mkdir -p "$REPO_DIR/stitchlabos/image/src/modules/turtlestitch/filesystem/home/pi/turtlestitch"
cp -r "$REPO_DIR/turtlestitch/"* "$REPO_DIR/stitchlabos/image/src/modules/turtlestitch/filesystem/home/pi/turtlestitch/" 2>/dev/null || true
rm -rf "$REPO_DIR/stitchlabos/image/src/modules/turtlestitch/filesystem/home/pi/turtlestitch/.git"

# Build image
cd "$REPO_DIR/stitchlabos/image"
"$BUILD_DIR/CustomPiOS/src/update-custompios-paths"
cd src && sudo bash -x ./build_dist

# Compress
cd workspace
IMAGE=$(ls *.img 2>/dev/null | head -1)
[ -n "$IMAGE" ] && xz -9 -T0 -v "$IMAGE" && sha256sum "${IMAGE}.xz" > "${IMAGE}.xz.sha256"
```

### Usage

```bash
# Sync code to VM
rsync -avz --exclude='.git' --exclude='node_modules' \
    ~/Documents/Projekte/MainsailDev/ builder@stitchlab-builder:~/MainsailDev/

# Build
ssh stitchlab-builder "~/build-stitchlabos.sh"

# Copy output
scp builder@stitchlab-builder:~/MainsailDev/stitchlabos/image/src/workspace/*.xz* .
