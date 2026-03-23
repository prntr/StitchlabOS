# StitchLAB Hybrid — Implementation Plan

> Phased roadmap from current state to fully functional hybrid embroidery/sewing machine.

## Dependency Graph

```
Phase 0 (DONE)                Phase 1                    Phase 2                  Phase 3
──────────────                ───────                    ───────                  ───────

Embroidery macros ─┐
                   │
Embroidery UI ─────┤
                   │    Pogo sense circuit ──┐
ESP dongle ────────┤    (hardware + GPIO)    │    Pedal ADC input ──┐
                   │           │             │    (controller FW)   │
live_jogd ─────────┤    Gantry detect ───────┤           │         │
                   │    (gcode_button)       │    Pedal serial ─────┤
Controller store ──┤           │             │    (dongle FW)       │
                   │    Safety macros ───────┤           │         │
Encoder prototype ─┤    (_GANTRY_DETACHED)   │    live_jogd pedal ──┤
                   │           │             │    (pedal→speed)     │
                   │    Mode state machine ──┤           │         │    Synced embroidery
                   │    (SET_MACHINE_MODE)    │    SewingPanel UI ──┤    (WAIT_NEEDLE_UP)
                   │           │             │           │         │         │
                   │    Mode guards ─────────┘    Max speed slider ─┘    Mode-aware UI
                   │    (_REQUIRE_EMBROIDERY)           │                (conditional panels)
                   │                                    │                      │
                   │                              Pedal watchdog              Full hybrid
                   │                              (safety timeout)            operation
                   │
                   └── Encoder mount + calibration (can start anytime after Phase 0)
```

## Phase 0 — Foundation (DONE)

Everything listed here is already built and working.

| Item | Location | Status |
|------|----------|--------|
| Embroidery macros (STITCH, NEEDLE_TOGGLE, etc.) | `stitchlabos-config/.../embroidery_macros.cfg` | Done |
| EmbroideryControlPanel | `mainsail/src/components/panels/EmbroideryControlPanel.vue` | Done |
| ESP32-C3 dongle firmware | `KlipperLiveControl/` | Done |
| live_jogd daemon | `stitchlabos/image/.../live_jogd.py` | Done |
| Controller WebSocket plugin | `mainsail/src/plugins/controllerWebSocket.ts` | Done |
| Controller Vuex store | `mainsail/src/store/server/controller/` | Done |
| AS5600 encoder module (prototype) | `docs/encoder/as5600.py` | Done |
| Encoder documentation | `docs/encoder/` | Done |

## Phase 1 — Gantry Detection + Mode Switching

**Goal:** Machine knows whether gantry is attached, switches modes safely, prevents driver damage.

**Depends on:** Phase 0 + pogo connector hardware prototype

### 1.1 Hardware: Pogo Sense Circuit

| Task | Detail | Output |
|------|--------|--------|
| Select pogo connector | 12-pin, 2.54mm pitch, spring-loaded | Part number + datasheet |
| Design gantry PCB | Sense bridge resistor (1kΩ), pad layout for pogo contact | KiCad schematic + PCB |
| Wire sense pins to SKR Pico | GPIO_SENSE_OUT → Pin 11, GPIO_SENSE_IN ← Pin 12 | Tested on breadboard |
| Verify sense loop | HIGH when mated, LOW when unmated, no bounce | Test report |

**Deliverable:** Working sense circuit on breadboard, verified with multimeter and Klipper console.

### 1.2 Klipper: Gantry Detection

| Task | Detail | File |
|------|--------|------|
| Add `[gcode_button gantry_detect]` | GPIO pin, press/release gcode | `printer.cfg` |
| Write `_GANTRY_DETACHED` macro | Disable XY, save mode, log | `embroidery_macros.cfg` |
| Write `_GANTRY_ATTACHED` macro | Save mode, prompt homing | `embroidery_macros.cfg` |
| Add `[save_variables]` | Persistent mode storage | `printer.cfg` |
| Write `_VALIDATE_MODE_ON_STARTUP` | Correct mismatch at boot | `embroidery_macros.cfg` |
| Write `QUERY_MODE` | Display current mode and gantry state | `embroidery_macros.cfg` |

**Deliverable:** Detaching gantry instantly disables XY steppers. Reattaching prompts for homing.

### 1.3 Klipper: Mode Guards

| Task | Detail | File |
|------|--------|------|
| Write `_REQUIRE_EMBROIDERY_MODE` | Guard macro, raises error if sewing | `embroidery_macros.cfg` |
| Add guard to `EMBROIDERY_HOME` | Refuse to home XY in sewing mode | `embroidery_macros.cfg` |
| Verify STITCH/NEEDLE_TOGGLE in both modes | These should work (Z-only) | Test |

**Deliverable:** XY commands blocked in sewing mode, Z commands work in both.

### Phase 1 Definition of Done

- [ ] Gantry detach → XY disabled within 100ms
- [ ] Gantry attach → mode=embroidery, unhomed
- [ ] `QUERY_MODE` shows correct state
- [ ] `EMBROIDERY_HOME` blocked in sewing mode
- [ ] `STITCH` works in both modes
- [ ] Mode persists across Klipper restart
- [ ] Power-on mismatch auto-corrects

---

## Phase 2 — Foot Pedal + Sewing Mode

**Goal:** User can sew with foot pedal in sewing mode. UI shows speed and stitch count.

**Depends on:** Phase 1 (mode switching must work)

### 2.1 Controller Firmware: Pedal Input

| Task | Detail | Repo |
|------|--------|------|
| Add ADC pin for pedal | ESP32 GPIO with 12-bit ADC | `KlipperLiveControl/controller/` |
| Extend ESP-NOW frame | Add `pedal` (uint16) and `pedal_dir` (uint8) fields | Controller + Dongle FW |
| Test pedal ADC | Verify full range, linearity, noise | Bench test |

### 2.2 Dongle Firmware: Forward Pedal

| Task | Detail | Repo |
|------|--------|------|
| Parse extended ESP-NOW frame | Extract pedal fields | `KlipperLiveControl/dongle/` |
| Extend USB serial protocol | New fields or new message type for pedal | Dongle FW |
| Backwards compatibility | Old controllers (no pedal) still work | Test |

### 2.3 live_jogd: Pedal → Motor Speed

| Task | Detail | File |
|------|--------|------|
| Add `PedalController` class | ADC → SPM mapping, dead zone, curve | `live_jogd.py` |
| Quadratic speed curve | Fine control at low speeds | `live_jogd.py` |
| Watchdog timer | Stop needle if no pedal update for 500ms | `live_jogd.py` |
| Mode check | Only process pedal in sewing mode | `live_jogd.py` |
| WebSocket broadcast | `pedal_update` message type | `live_jogd.py` |
| Configuration | `live_jogd.conf` pedal section | New config file |

### 2.4 Frontend: SewingControlPanel

| Task | Detail | File |
|------|--------|------|
| New `SewingControlPanel.vue` | Pedal gauge, SPM, stitch counter, direction | New component |
| Register in Dashboard | Conditional on `machine_mode == 'sewing'` | `Dashboard.vue` |
| Extend controller store | `pedal_value`, `pedal_percent`, `needle_spm` | Store module |
| Parse `pedal_update` in WebSocket plugin | Route to store | `controllerWebSocket.ts` |
| Max speed slider | Configurable max SPM from UI | `SewingControlPanel.vue` |

### Phase 2 Definition of Done

- [ ] Pedal at 0% → no movement
- [ ] Pedal at 100% → configured max SPM
- [ ] Pedal release → needle stops within 1 stitch
- [ ] Reverse direction works
- [ ] Dongle disconnect → immediate stop
- [ ] UI shows pedal %, SPM, stitch count
- [ ] Mode switch blocked while pedal pressed
- [ ] Works with existing joystick (pedal=0 if no pedal hardware)

---

## Phase 3 — Encoder Integration + Synced Embroidery

**Goal:** Encoder provides needle position feedback in both modes. In embroidery mode, XY waits for needle UP before moving.

**Depends on:** Encoder mount (hardware) — can start in parallel with Phase 2

### 3.1 Hardware: Mount Encoder

| Task | Detail |
|------|--------|
| Mount AS5600 on handwheel shaft | Diametric magnet on shaft, sensor PCB fixed to frame |
| Wire to SKR Pico I2C | GPIO0 (SDA), GPIO1 (SCL), via P9 header |
| Calibrate angles | Map 0°=needle UP, 180°=needle DOWN |
| Verify AGC and signal quality | Check magnet strength and alignment |

### 3.2 Klipper: Encoder Macros

| Task | Detail | File |
|------|--------|------|
| Deploy `as5600.py` to Klipper extras | Copy from `docs/encoder/as5600.py` | `~/klipper/klippy/extras/` |
| Add `[as5600 e0_encoder]` config | I2C bus, monitor rate, mode | `printer.cfg` |
| Write `WAIT_NEEDLE_UP` macro | Poll encoder, wait for 0°/360° range | `embroidery_macros.cfg` |
| Modify embroidery G-code post-processor | Insert `WAIT_NEEDLE_UP` before XY moves | TurtleStitch or G-Code Studio |

### 3.3 Frontend: Encoder Display

| Task | Detail |
|------|--------|
| Show needle angle in EmbroideryControlPanel | Read `printer["as5600 e0_encoder"].degrees` |
| Show needle angle in SewingControlPanel | Same data, different context |
| Visual needle position indicator | Circular gauge or simple UP/DOWN icon |

### 3.4 Mode-Aware Conditional UI

| Task | Detail |
|------|--------|
| Mode indicator badge | Always visible, color-coded |
| Conditional panel rendering | Show/hide panels based on `machine_mode` |
| Gantry status icon | Attached/detached in header |
| Transition animation | Smooth panel swap on mode change |

### Phase 3 Definition of Done

- [ ] Encoder reads needle position accurately
- [ ] UI shows needle angle in both modes
- [ ] `WAIT_NEEDLE_UP` blocks until needle is UP
- [ ] Embroidery G-code uses WAIT_NEEDLE_UP before XY moves
- [ ] UI adapts panels to current mode
- [ ] Full embroidery → detach → sew → reattach → home → embroidery cycle works

---

## Future Phases (Not Planned in Detail)

### Phase 4: MCU Firmware Encoder (Performance)

- Move encoder sampling to SKR Pico firmware (C)
- Enable 500-1000 Hz sampling
- Support 600+ SPM in embroidery mode
- Required only if Python-based 100 Hz proves insufficient

### Phase 5: Advanced Sewing Features

- Stitch pattern memory (straight, zigzag, decorative)
- Automatic thread tension feedback
- Bobbin counter / thread break detection
- Stitch length control

### Phase 6: Multi-Gantry Support

- ADC-based gantry identification (different resistor = different gantry size)
- Auto-load gantry-specific configuration (bed size, max speed)
- Gantry calibration storage

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Pogo bounce causes false detach | High — XY disabled mid-print | Medium | Debounce in gantry detect macro (50ms delay before acting) |
| Pedal latency too high | Medium — sluggish response | Low | Measured ~15ms, well within 50ms threshold |
| Encoder polling too slow for high SPM | Medium — missed needle positions | Medium | Start with 100 Hz Python, upgrade to MCU firmware if needed |
| Pogo pin contact resistance | Low — signal degradation | Low | Spec ≤50mΩ pins, test at max step rate |
| Motor driver damage on hot-detach | High — hardware replacement | Low | Sense loop + instant disable; physical connector designed to break sense first |

### Pogo Connector Contact Order

**Critical physical design requirement:** The sense pins (11, 12) should be the shortest pogo pins or positioned to **make contact last and break contact first**. This ensures:

1. On attach: power and signal pins connect before sense reports "attached"
2. On detach: sense reports "detached" before power/signal pins disconnect

This can be achieved by making sense pins 0.5mm shorter than signal pins, or by positioning them at the edges of the connector where mechanical separation happens first.
