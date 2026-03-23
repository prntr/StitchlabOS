# StitchLAB Hybrid — Embroidery + Sewing Machine

> The StitchLAB Hybrid is a dual-mode machine: automated embroidery with a detachable XY gantry, and free-motion sewing controlled by a fly-by-wire foot pedal via the ESP WiFi dongle.

## Concept

```
EMBROIDERY MODE                         SEWING MODE
(gantry attached)                       (gantry detached)

┌─────────────────────┐                 ┌─────────────────────┐
│  Mainsail UI        │                 │  Mainsail UI        │
│  EmbroideryPanel    │                 │  SewingPanel        │
│  G-Code Studio      │                 │  Pedal speed gauge  │
│  Stitch controls    │                 │  Stitch counter     │
└────────┬────────────┘                 └────────┬────────────┘
         │                                       │
         ▼                                       ▼
┌─────────────────────┐                 ┌─────────────────────┐
│  Klipper            │                 │  live_jogd          │
│  XY + Z steppers    │                 │  Pedal → motor speed│
│  Encoder sync       │                 │  Encoder → UI       │
└────────┬────────────┘                 └────────┬────────────┘
         │                                       │
    ┌────┴────┐                             ┌────┴────┐
    │ SKR Pico│                             │ SKR Pico│
    │ XY + Z  │                             │ Z only  │
    │ Encoder │                             │ Encoder │
    └────┬────┘                             └─────────┘
         │
  ┌──────┴──────┐
  │ 12-pin POGO │  ← Detachable
  │ connector   │
  └──────┬──────┘
         │
  ┌──────┴──────┐
  │  XY Gantry  │
  │  2 steppers │
  │  2 endstops │
  └─────────────┘
```

## Key Design Decisions

1. **Not a fork** — Hybrid is a configuration variant of StitchLabOS, enabled by hardware (encoder + pogo connector) and config (`printer.cfg` sections)
2. **Gantry detection is mandatory** — the 12-pin pogo connector includes a sense loop for safety (prevents motor driver burnout on hot-detach)
3. **Mode is hardware-derived** — the machine mode follows the gantry state: attached = embroidery capable, detached = sewing only
4. **Foot pedal via existing dongle** — the ESP32-C3 dongle already handles joystick input; pedal is a new input type on the same system

## Documentation

| File | Description |
|------|-------------|
| [POGO_CONNECTOR.md](POGO_CONNECTOR.md) | 12-pin connector pinout, sense circuit, detection logic |
| [MODE_SWITCHING.md](MODE_SWITCHING.md) | State machine, safety interlocks, macro design |
| [FOOT_PEDAL.md](FOOT_PEDAL.md) | Pedal hardware, dongle integration, speed mapping |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phased roadmap with dependencies |
| [../encoder/README.md](../encoder/README.md) | AS5600 encoder (shared by both modes) |

## What Already Exists

| Component | Status | Location |
|-----------|--------|----------|
| Embroidery macros | Done | `stitchlabos-config/printer_data/config/embroidery_macros.cfg` |
| Embroidery UI panel | Done | `mainsail/src/components/panels/EmbroideryControlPanel.vue` |
| ESP dongle + live_jogd | Done | `stitchlabos/image/src/modules/live-jogd/` |
| Controller WebSocket | Done | `mainsail/src/plugins/controllerWebSocket.ts` |
| Controller store | Done | `mainsail/src/store/server/controller/` |
| Encoder module (prototype) | Done | `docs/encoder/as5600.py` |
| Encoder wiring/architecture | Done | `docs/encoder/` |

## What Needs to Be Built

| Component | Priority | Effort | Documented In |
|-----------|----------|--------|---------------|
| Pogo sense circuit + Klipper module | P0 | Small | [POGO_CONNECTOR.md](POGO_CONNECTOR.md) |
| Safety macro (XY disable on detach) | P0 | Small | [MODE_SWITCHING.md](MODE_SWITCHING.md) |
| Mode state machine + macros | P1 | Medium | [MODE_SWITCHING.md](MODE_SWITCHING.md) |
| Pedal frame type in dongle firmware | P1 | Medium | [FOOT_PEDAL.md](FOOT_PEDAL.md) |
| live_jogd pedal → motor speed | P1 | Medium | [FOOT_PEDAL.md](FOOT_PEDAL.md) |
| Encoder mount + calibration | P2 | Medium | [../encoder/README.md](../encoder/README.md) |
| Sewing mode UI panel | P2 | Medium | [MODE_SWITCHING.md](MODE_SWITCHING.md) |
| WAIT_NEEDLE_UP + synced embroidery | P3 | Medium | [../encoder/README.md](../encoder/README.md) |
| Mode-aware conditional UI | P3 | Large | [MODE_SWITCHING.md](MODE_SWITCHING.md) |
