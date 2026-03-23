# StitchLAB Documentation

> Integration docs for the StitchLAB workspace. Upstream project docs live in their repos.

## Start Here

- [01 Onboarding](01-onboarding.md) - What's here
- [03 Quickstart (Local)](03-quickstart-local.md) - Dev with simulator
- [04 Quickstart (Dev Pi)](04-quickstart-pi.md) - Deploy to Pi

## Reference

- [02 Architecture](02-architecture.md) - System diagram, components, status
- [05 Configuration](05-configuration.md) - Ports, endpoints, macros
- [06 Troubleshooting](06-troubleshooting.md) - Common issues
- [07 Development Guidelines](07-development-guidelines.md) - Coding standards
- [08 Image Building](08-image-building.md) - Build distributable images
- [09 Update Strategy](09-update-strategy.md) - OTA updates, upstream sync, release cycle

## Components

- [G-Code Studio](components/gcode-studio.md) - 2D viewer status
  - [Agent Notes](components/gcode-studio/agents-notes.md)
  - [Repositioning Plan](components/gcode-studio/repositioning-feature-plan.md)
- [TurtleStitch](components/turtlestitch.md) - Offline app, hosting, project file management
  - [Agent Notes](components/turtlestitch/agents-notes.md)

## StitchLAB Hybrid (Embroidery + Sewing)

- [Hybrid Overview](hybrid/README.md) - Dual-mode machine concept and status
  - [Pogo Connector](hybrid/POGO_CONNECTOR.md) - 12-pin connector, sense circuit, gantry detection
  - [Mode Switching](hybrid/MODE_SWITCHING.md) - State machine, safety interlocks, macros
  - [Foot Pedal](hybrid/FOOT_PEDAL.md) - Fly-by-wire pedal via ESP dongle
  - [Implementation Plan](hybrid/IMPLEMENTATION_PLAN.md) - Phased roadmap with dependencies
- [Encoder](encoder/README.md) - AS5600 handwheel encoder (shared by both modes)
  - [Encoder Architecture](encoder/ARCHITECTURE.md) - Multi-phase development roadmap
  - [System Guide](encoder/SYSTEM_GUIDE.md) - Complete system guide
  - [Hardware Wiring](encoder/HARDWARE_WIRING.md) - Wiring diagrams

## Research

- [Sensorless Homing](sensorless-homing-research.md) - TMC2209 StallGuard research for XY axes (not implemented)

## Operations

- [Runbook: Pi Services](runbooks/pi-services.md) - Service management
- [Runbook: AP Troubleshooting](runbooks/ap-troubleshooting.md) - Mainsail access in AP mode

## External

- [External References](references/external.md) - Upstream docs
