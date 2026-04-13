# StitchLabOS

A Raspberry Pi OS image that turns a Klipper-based machine into a computerized embroidery system.

StitchLabOS bundles Klipper, Moonraker, a custom Mainsail UI, TurtleStitch (visual stitch programming), WiFi management with AP fallback, and embroidery-specific macros into a single flashable image.

## Components

| Component | Source | Description |
|-----------|--------|-------------|
| [Klipper](https://github.com/Klipper3d/klipper) | upstream | Motion controller firmware |
| [Moonraker](https://github.com/Arksine/moonraker) | upstream | API server for Klipper |
| [Mainsail](https://github.com/prntr/mainsail) | prntr fork | Web UI with embroidery panel, WiFi manager, GCode Studio, StitchLab theme |
| [TurtleStitch](https://github.com/prntr/turtlestitch) | prntr fork | Visual stitch programming with Moonraker integration and G-code export |
| [stitchlabos-config](https://github.com/prntr/stitchlabos-config) | prntr repo | WiFi manager component, embroidery macros, WiFi scripts |

All components are updatable OTA via the Mainsail update panel.

## Image Build

Images are built with [CustomPiOS](https://github.com/guysoft/CustomPiOS) on GitHub Actions. A tag push (`v*`) triggers the build and creates a GitHub Release with the `.img.xz` artifact.

Flash with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) — hostname, WiFi, and SSH can be configured directly in the imager.

### Default Access

- **WiFi AP:** `Stitchlab` / `praxistest` (fallback when no known network is available)
- **SSH:** `pi` / `lab`
- **UART:** GPIO14/15 for SKR Pico connection

## Repository Structure

```
.github/workflows/
  build-image.yml         Image build CI

stitchlabos/image/src/
  modules/                CustomPiOS modules (klipper, mainsail, turtlestitch, stitchlabos, ...)

docs/                     Project documentation (architecture, setup, update strategy, ...)
```

### Submodules

| Path | Repo | Branch |
|------|------|--------|
| `mainsail/` | prntr/mainsail | `stitchlabos/v2.17.0` |
| `turtlestitch/` | prntr/turtlestitch | `master` |
| `stitchlabos-config/` | prntr/stitchlabos-config | `main` |

## Documentation

See [docs/README.md](docs/README.md) for the full documentation index — architecture, quickstart guides, configuration, troubleshooting, image building, and OTA update strategy.

## License

GPLv3
