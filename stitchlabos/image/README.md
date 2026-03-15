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

## Raspberry Pi Imager Compatibility

The image supports Raspberry Pi Imager customization:
- Hostname configuration
- WiFi SSID/password
- SSH enable with password or key
- User account setup
- Locale/timezone

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

- **Hostname**: `stitchlab` (customizable via Imager)
- **Web UI**: http://stitchlab.local (port 80)
- **TurtleStitch**: http://stitchlab.local:3000
- **Moonraker API**: http://stitchlab.local:7125
- **AP Mode SSID**: `AccessPopup` (when WiFi disconnected)
- **AP Mode IP**: 192.168.50.5
