# Architecture

> System composition, ownership boundaries, and component status.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MAINSAIL FRONTEND                               │
│                                                                         │
│  ┌──────────────────────────┐    ┌────────────────────────────────────┐ │
│  │  EmbroideryControlPanel  │    │  TheControllerMenu                 │ │
│  │  • Needle Toggle         │    │  • Dongle status                   │ │
│  │  • Stitch / Lock Stitch  │    │  • Controller pairing              │ │
│  │  • Zero Position         │    │  • WiFi controls                   │ │
│  └────────────┬─────────────┘    └─────────────────┬──────────────────┘ │
│               │ G-code via Moonraker               │ WebSocket :7150    │
└───────────────┼────────────────────────────────────┼────────────────────┘
                │                                    │ (not yet implemented)
                ▼                                    ▼
┌───────────────────────────┐        ┌────────────────────────────────────┐
│  Moonraker (Port 7125)    │◄───────│  live_jogd.py                      │
│  Klipper                  │  HTTP  │  USB Serial ↔ Binary Protocol      │ 
│  embroidery_macros.cfg    │        └─────────────────┬──────────────────┘
└───────────────────────────┘                          │
                                                       ▼
                                     ┌────────────────────────────────────┐
                                     │  StitchLabDongle (ESP32-C3)        │
                                     │  ESP-NOW ↔ StitchLabController     │
                                     └────────────────────────────────────┘
```

## Ownership Boundaries

| Layer | Components | Docs Location |
|-------|------------|---------------|
| Upstream | Mainsail, Klipper, Moonraker, TurtleStitch | Nested repo READMEs |
| StitchLAB glue | Ports, config, Pi runbooks, integration | `docs/` (this folder) |
| StitchLAB code | UI panels, macros, WiFi manager, live control | `stitchlabos/`, `mainsail/` fork |

## Needle Position Model

```
1 full handwheel rotation = 5mm Z travel = 1 complete stitch

Z=0.0mm  → Needle UP (0°)     - After homing
Z=2.5mm  → Needle DOWN (180°) - Needle in fabric
Z=5.0mm  → Needle UP (360°)   - 1 stitch complete
Z=7.5mm  → Needle DOWN
Z=10.0mm → Needle UP          - 2 stitches complete
```

Macros use `G92` to hide physical Z movement from the logical position.

## StitchLAB Building Blocks

| Block | Location | Purpose |
|-------|----------|---------|
| Klipper macros | `stitchlabos/config/klipper/embroidery_macros.cfg` | Needle model, stitch commands |
| WiFi manager | `stitchlabos/config/moonraker/wifi_manager.py` | Moonraker WiFi API extension |
| Deploy scripts | `stitchlabos/scripts/rpi/` | Reproducible Pi setup |
| Embroidery UI | `mainsail/src/components/panels/EmbroideryControlPanel.vue` | Web controls |
| Controller menu | `mainsail/src/components/TheControllerMenu.vue` | Dongle/WiFi UI |
| G-Code Studio | `mainsail/src/components/gcodestudio/` | Embroidery visualization |

## Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| EmbroideryControlPanel | Done | Works via Moonraker |
| Klipper Macros | Done | All macros functional |
| live_jogd daemon | Done | Serial + HTTP working |
| StitchLabDongle | Done | ESP-NOW + Serial API |
| StitchLabController | Done | LVGL UI + joystick |
| TheControllerMenu UI | Partial | UI done, needs WebSocket backend |
| Browser ↔ live_jogd | Missing | WebSocket :7150 not implemented |

## Klipper Coordinate Systems

Embroidery macros rely on Klipper's handling of coordinate systems, especially `G92`.

Reference: [Klipper Code Overview: Coordinate Systems](https://www.klipper3d.org/Code_Overview.html#coordinate-systems)
