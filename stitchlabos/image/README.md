# StitchLabOS Image Build

This directory contains the CustomPiOS configuration for building StitchLabOS, a distributable Raspberry Pi image for DIY embroidery machines.

## Features

- **Klipper + Moonraker**: 3D printer/CNC motion control
- **Mainsail**: Web-based UI for machine control
- **TurtleStitch**: Visual programming for embroidery patterns
- **AccessPopup**: Automatic WiFi AP fallback mode
- **KIAUH**: Klipper management tool for updates
- **Katapult**: MCU bootloader for CAN/USB flashing
- **live_jogd**: USB serial bridge for StitchLab Dongle

## Flashing the Image

### Raspberry Pi Imager (v2.0+)

> **WARNING:** Do NOT select a Raspberry Pi model in the first step.
> Pi Imager v2.0+ will silently replace your custom image with the stock
> Raspberry Pi OS for the selected model. Skip the model selection or choose
> "No filtering" to flash the actual StitchLabOS image.

1. Open Raspberry Pi Imager
2. **Modell/Device:** skip or choose "No filtering"
3. **Betriebssystem/OS:** scroll to bottom → "Use custom" → select the `.img.xz`
4. **Speicher/Storage:** select your SD card
5. **Anpassung/Customisation** will be grayed out — that's fine, StitchLabOS has all defaults baked in
6. Click "Schreiben/Write"

### Alternative: command-line flash (most reliable)

```bash
diskutil unmountDisk /dev/diskN && \
xzcat StitchLabOS-*.img.xz | sudo dd of=/dev/rdiskN bs=4m && \
sync && diskutil eject /dev/diskN
```

Replace `/dev/diskN` with your SD card (find it with `diskutil list external`).
Note: `status=progress` does not work in zsh — omit it or use bash.

### Default credentials

| | Value |
|---|---|
| **SSH** | `pi@stitchlab.local`, password: `lab` |
| **WiFi AP** | SSID: `Stitchlab`, password: `praxistest` |
| **AP IP** | `192.168.50.5` |

## Building Locally

### Prerequisites

- Linux system (Ubuntu/Debian recommended)
- Docker (optional, for clean builds)
- 10GB+ free disk space

### Build Steps

1. Clone CustomPiOS:
   ```bash
   git clone https://github.com/guysoft/CustomPiOS.git
   ```

2. Update paths:
   ```bash
   cd stitchlabos/image
   ../../CustomPiOS/src/update-custompios-paths
   ```

3. Build the image:
   ```bash
   cd src
   sudo bash -x ./build_dist
   ```

The built image will be in `src/workspace/`.

## Module Structure

| Module | Description |
|--------|-------------|
| `klipper` | Installs Klipper and Moonraker |
| `kiauh` | Clones KIAUH management tool |
| `katapult` | Clones Katapult bootloader |
| `accesspopup` | WiFi AP fallback mode |
| `mainsail` | Web UI + nginx |
| `turtlestitch` | TurtleStitch offline editor |
| `live-jogd` | USB serial bridge daemon |
| `stitchlabos` | Final customizations |

## Adding to Raspberry Pi Imager

To add StitchLabOS to Raspberry Pi Imager:

1. Open Raspberry Pi Imager settings
2. Add custom repository URL:
   ```
   https://raw.githubusercontent.com/stitchlab/stitchlabos/main/stitchlabos/image/os_list.json
   ```

Or use "Use custom" and provide the direct image URL.

## Default Configuration

- **Hostname**: `stitchlab`
- **Web UI**: http://stitchlab.local (port 80)
- **TurtleStitch**: http://stitchlab.local:3000
- **Moonraker API**: http://stitchlab.local:7125
- **AP Mode SSID**: `Stitchlab` (auto-activates when no WiFi available)
- **AP Mode Password**: `praxistest`
- **AP Mode IP**: 192.168.50.5
