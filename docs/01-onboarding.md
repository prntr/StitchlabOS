# Onboarding

> What's in this workspace and how to get started.

## Workspace Projects

| Project | Path | Purpose |
|---------|------|---------|
| UI | `mainsail/` | Vue 2 + Vite + Vuetify frontend |
| Simulator | `virtual-klipper-printer/` | Dockerized Moonraker/Klipper |
| TurtleStitch | `turtlestitch/` | Snap!/TurtleStitch tooling |
| StitchlabOS | `stitchlabos/` | OS/config/scripts for Pi |
| Image Build | `stitchlabos/image/` | CustomPiOS image tooling |
| Live control | `KlipperLiveControl/` | ESP32 controller + daemon |

## StitchLAB Extensions

| Feature | UI | Backend |
|---------|-----|---------|
| `EmbroideryControlPanel.vue` | `embroidery_macros.cfg` |
| `TheControllerMenu.vue` | `wifi_manager.py` |
| TurtleStitch offline | Nav link | nginx on Pi `:3000` |

See [02-architecture.md](02-architecture.md) for full component locations.

## Development Modes

| Mode | UI | Backend |
|------|-----|---------|
| Local | `npm run serve` | Docker simulator |
| Dev Pi | rsync to Pi | Pi services |

Pick one:
- [Quickstart (Local)](03-quickstart-local.md)
- [Quickstart (Dev Pi)](04-quickstart-pi.md)
