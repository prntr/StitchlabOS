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
| Embroidery Panel | `EmbroideryControlPanel.vue` | `embroidery_macros.cfg` |
| Controller Menu | `TheControllerMenu.vue` | `wifi_manager.py` |
| TurtleStitch offline | Nav link | nginx on Pi `:3000` |

### StitchLAB Hybrid (In Development)

The Hybrid variant adds sewing mode with a detachable XY gantry and foot pedal control.

| Feature | Status | Docs |
|---------|--------|------|
| Pogo connector (gantry detection) | Planning | [hybrid/POGO_CONNECTOR.md](hybrid/POGO_CONNECTOR.md) |
| Mode switching (embroidery/sewing) | Planning | [hybrid/MODE_SWITCHING.md](hybrid/MODE_SWITCHING.md) |
| Foot pedal via ESP dongle | Planning | [hybrid/FOOT_PEDAL.md](hybrid/FOOT_PEDAL.md) |
| AS5600 encoder | Prototype | [encoder/README.md](encoder/README.md) |
| Implementation roadmap | Documented | [hybrid/IMPLEMENTATION_PLAN.md](hybrid/IMPLEMENTATION_PLAN.md) |

See [02-architecture.md](02-architecture.md) for full component locations.

## Development Modes

| Mode | UI | Backend |
|------|-----|---------|
| Local | `npm run serve` | Docker simulator |
| Dev Pi | rsync to Pi | Pi services |

Pick one:
- [Quickstart (Local)](03-quickstart-local.md)
- [Quickstart (Dev Pi)](04-quickstart-pi.md)
