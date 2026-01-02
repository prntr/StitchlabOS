# Architecture

## System overview

The StitchLAB system is a composition of:

- Mainsail UI (browser)
- Moonraker API (HTTP/WebSocket)
- Klipper firmware (host + MCU)
- StitchLAB extensions:
  - Embroidery macros (`embroidery_macros.cfg`)
  - Optional live control (controller + dongle + `live_jogd`)
  - G-Code Studio features for embroidery/plotter workflows

## Ownership boundaries

To keep the project maintainable, treat these as separate layers:

- **Upstream**: Mainsail, Klipper, Moonraker, TurtleStitch
- **StitchLAB glue** (this workspace documentation):
  - How the pieces connect
  - Ports and configuration
  - Pi runbooks
  - StitchLAB-specific UI panels and macros

## StitchLAB-owned building blocks

- `stitchlabos/`
  - Klipper macros (needle model, stitch commands)
  - Moonraker component(s), notably WiFi management
  - Deployment scripts to keep the Pi reproducible (no one-off SSH edits)

- Mainsail fork additions
  - Embroidery UI controls/panels
  - WiFi + controller menu integration
  - G-Code Studio enhancements for embroidery workflows

- Pi services
  - `turtlestitch.service` for offline TurtleStitch serving (plus CORS)
  - `live_jogd` for dongle/controller bridging (WS planned but not implemented)

## Important concept: Klipper coordinate systems

Embroidery macros and UI features rely heavily on Klipper’s handling of coordinate systems, especially the effect of `G92`.

Reference: see [Klipper Code Overview: Coordinate Systems](https://www.klipper3d.org/Code_Overview.html#coordinate-systems).
