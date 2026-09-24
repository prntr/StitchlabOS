# 12-Pin Pogo Connector — Gantry Interface

> **Applies to: StitchLAB Hybrid only.** The base StitchLAB embroidery machine has a fixed gantry and does not use this connector or any of the gantry-detection logic described here.

> The XY gantry connects to the StitchLAB Hybrid via a 12-pin pogo connector. One pin is dedicated to gantry detection (single-pin endstop-style sense). The remaining 11 pins carry motor signals, endstop inputs, and ground.

## Pin Allocation

| Pin | Signal | Direction | Notes |
|-----|--------|-----------|-------|
| 1 | X_STEP | MCU → Gantry | X stepper step signal |
| 2 | X_DIR | MCU → Gantry | X stepper direction |
| 3 | X_ENABLE | MCU → Gantry | X stepper enable (active low) |
| 4 | Y_STEP | MCU → Gantry | Y stepper step signal |
| 5 | Y_DIR | MCU → Gantry | Y stepper direction |
| 6 | Y_ENABLE | MCU → Gantry | Y stepper enable (active low) |
| 7 | X_ENDSTOP | Gantry → MCU | X endstop input (normally open) |
| 8 | Y_ENDSTOP | Gantry → MCU | Y endstop input (normally open) |
| 9 | GND | Common | Ground reference for all signals |
| 10 | GND | Common | Ground reference (redundant, also used by sense) |
| 11 | GANTRY_SENSE | Gantry → MCU | Single-pin sense, shorted to GND on gantry side |
| 12 | (spare) | — | Reserved for future use |

> **Note:** Motor power (12/24V) is NOT routed through the pogo connector. The stepper drivers are on the SKR Pico; only step/dir/enable signals go to the gantry. The stepper motors on the gantry receive power from their own driver outputs on the SKR Pico via a separate power cable, or the drivers are on the gantry side. **This needs hardware design finalization.**

### Open Design Question: Driver Placement

Two options for the XY stepper drivers:

| Option | Pros | Cons |
|--------|------|------|
| **A: Drivers on SKR Pico** | Fewer gantry components, lighter gantry, simpler gantry PCB | Need motor power wires through pogo (high current), pogo must handle motor coil signals |
| **B: Drivers on gantry PCB** | Only low-current step/dir/enable through pogo (as shown above), cleaner separation | Gantry needs its own driver board, heavier/more complex gantry |

**Current assumption: Option B** — drivers on gantry, step/dir/enable through pogo. This keeps the pogo connector low-current and protects drivers from hot-plug transients.

If Option A is chosen, pins 1-6 would carry motor coil signals (high current) instead of step/dir/enable, and the pogo connector spec must be rated accordingly.

## Sense Circuit

Detection works exactly like a mechanical endstop: a single GPIO line is shorted to GND when the gantry is mated, and floats open when detached.

### Schematic

```
SKR Pico (MCU side)                Gantry PCB
─────────────────                  ──────────

3.3V ──[ internal pull-up ]──┐
                             │
GPIO_GANTRY_SENSE ──── Pin 11 ═══╗
   (input)                        ║     ╔══ Pin 11 ──┐
                                  ╚═════╝            │ (direct short)
                                 (pogo mates)        │
                                  ╔═════╗            │
GND ────────────────── Pin 10 ═══╝     ╚══ Pin 10 ──┘
```

The gantry PCB simply ties pin 11 to pin 10 (GND). No resistor, no bridge — just a wire.

### MCU Pin: THB (gpio27)

The SKR Pico's **THB** (heated-bed thermistor) input is unused on this machine. It maps to **gpio27** and has a convenient GND pin in the same header. Reusing it:

- Avoids running new wires across the board
- Keeps the assignment obvious to anyone reading the schematic ("the unused thermistor port is now the gantry sense")
- Frees the original sense pins from the design

The pin is configured with Klipper's internal pull-up (`^gpio27`).

### Logic

| Pogo State | gpio27 reads | Meaning |
|------------|--------------|---------|
| Mated | LOW (shorted to GND) | Gantry attached |
| Unmated | HIGH (pull-up) | Gantry detached |

In Klipper's `gcode_button`, **press** = pin goes LOW, so `press_gcode` = `_GANTRY_ATTACHED` and `release_gcode` = `_GANTRY_DETACHED`.

### Future: Multi-Gantry ID via ADC

`gpio27` is ADC-capable. If multi-gantry support is added later, the same pin can be repurposed as an analog input — different resistor values to GND on different gantries would yield different ADC readings. **Not needed for the current design**, but the pin choice keeps that door open.

## Klipper Integration

> **Hybrid-only config.** The Klipper config blocks shown below must NOT be added to the shared base `printer.cfg`. They live in a separate `hybrid_macros.cfg` that is only included on Hybrid image builds. See [Build Integration](#build-integration) below.

### Option 1: Use Klipper's `[filament_switch_sensor]` Pattern

Klipper already has GPIO monitoring with event callbacks. The gantry sensor follows the same pattern:

```ini
# printer.cfg
[gcode_button gantry_detect]
pin: ^gpio27                # THB input, internal pull-up enabled
press_gcode:                # pin LOW = shorted to GND = gantry attached
    _GANTRY_ATTACHED
release_gcode:              # pin HIGH = open = gantry detached
    _GANTRY_DETACHED
```

This uses Klipper's built-in `gcode_button` module — no custom Python needed.

### Option 2: Custom Klipper Module

For richer state management (debounce, status reporting to Moonraker):

```python
# ~/klipper/klippy/extras/gantry_detect.py
class GantryDetect:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name()
        # GPIO setup
        ppins = self.printer.lookup_object('pins')
        self.sense_pin = ppins.setup_pin('digital_in', config.get('sense_pin'))
        self.sense_pin.setup_minmax(mcu_freq=10)  # 10 Hz polling
        # State
        self.attached = False
        self.debounce_count = 0
        self.debounce_threshold = config.getint('debounce_count', 3)
        # Register
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command("QUERY_GANTRY", self.cmd_QUERY_GANTRY)

    def get_status(self, eventtime):
        return {'attached': self.attached}
```

**Recommendation: Start with Option 1** (`gcode_button`). It requires zero custom code and is well-tested in Klipper. Move to Option 2 only if debounce or Moonraker status reporting becomes necessary.

## Safety Behavior

### On Detach (release_gcode)

```gcode
[gcode_macro _GANTRY_DETACHED]
gcode:
    { action_respond_info("WARNING: Gantry detached!") }
    # Immediately disable XY steppers to prevent driver damage
    SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=0
    SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=0
    # Clear homing state — XY is no longer trustworthy
    SET_KINEMATIC_POSITION X=0 Y=0
    # Update mode variable
    SAVE_VARIABLE VARIABLE=machine_mode VALUE='"sewing"'
    { action_respond_info("Machine mode: SEWING (XY disabled)") }
```

### On Attach (press_gcode)

```gcode
[gcode_macro _GANTRY_ATTACHED]
gcode:
    { action_respond_info("Gantry attached. Home XY before use.") }
    # Do NOT auto-enable steppers — require explicit homing
    SAVE_VARIABLE VARIABLE=machine_mode VALUE='"embroidery"'
    { action_respond_info("Machine mode: EMBROIDERY (home XY to begin)") }
```

### Critical Safety Rule

**XY steppers must be disabled within 1 motor step of detecting detach.** The `gcode_button` handler fires immediately on GPIO change, and `SET_STEPPER_ENABLE` is a direct MCU command — this is fast enough for the pogo disconnect scenario.

## Physical Design Considerations

### Connector Requirements

- **Pin count:** 12
- **Current per pin:** <50mA (step/dir/enable signals only, if Option B)
- **Mating cycles:** >10,000 (pogo pins are rated for 100k+ typically)
- **Alignment:** mechanical guide pins or housing to ensure correct orientation
- **Retention:** magnetic or spring-loaded (pogo pins are spring-loaded by nature)

### Pogo Pin Spec

- **Travel:** 1-2mm typical
- **Spring force:** 50-100g per pin
- **Contact resistance:** <50mΩ
- **Pitch:** 2.54mm (standard) or 2.0mm (compact)

### PCB Requirements

- **MCU side:** Pogo pin header soldered to SKR Pico breakout or custom adapter board
- **Gantry side:** Flat pad array matching pogo pin positions, with pin 11 wired directly to pin 10 (GND)

## Build Integration

Gantry detection is Hybrid-only. The base StitchLAB image must not include any of this logic. The configuration follows the same pattern already used for `embroidery_macros.cfg`: source-of-truth in the [stitchlabos-config](https://github.com/prntr/stitchlabos-config) submodule, symlinked into place by the image build script.

### File layout in `stitchlabos-config`

```
stitchlabos-config/
├── printer_data/
│   └── config/
│       ├── embroidery_macros.cfg       # shared (base + hybrid)
│       └── hybrid_macros.cfg           # NEW — hybrid only
```

`hybrid_macros.cfg` contains:
- `[gcode_button gantry_detect]` (pin: `^gpio27`)
- `[save_variables]` for `machine_mode` persistence
- `_GANTRY_ATTACHED`, `_GANTRY_DETACHED`
- `_REQUIRE_EMBROIDERY_MODE`, `_VALIDATE_MODE_ON_STARTUP`
- `QUERY_MODE`, `SET_MACHINE_MODE`

### Image build (start_chroot_script)

In [stitchlabos/image/src/modules/stitchlabos/start_chroot_script](../../stitchlabos/image/src/modules/stitchlabos/start_chroot_script), guard the hybrid symlink behind a build flag:

```bash
# Existing (always done):
ln -sf /home/pi/stitchlabos-config/printer_data/config/embroidery_macros.cfg \
    /home/pi/printer_data/config/embroidery_macros.cfg

# NEW — only for Hybrid builds:
if [ "${STITCHLABOS_VARIANT:-base}" = "hybrid" ]; then
    ln -sf /home/pi/stitchlabos-config/printer_data/config/hybrid_macros.cfg \
        /home/pi/printer_data/config/hybrid_macros.cfg
fi
```

### printer.cfg

Two options:

**A. Shared printer.cfg with conditional include** (cleaner — file just isn't there on base builds, Klipper would error on the include)

```ini
# Use [include hybrid_macros.cfg] only in a hybrid-specific printer.cfg
```

**B. Separate printer.cfg per variant** (recommended)

Maintain two printer.cfg files in the image build:
- `stitchlabos/image/src/modules/klipper/filesystem/.../printer.cfg` — base
- `stitchlabos/image/src/modules/klipper/filesystem-hybrid/.../printer.cfg` — adds `[include hybrid_macros.cfg]`

The build script copies the variant-appropriate one based on `$STITCHLABOS_VARIANT`. This keeps each printer.cfg readable and avoids Klipper conditional-include hacks.

## Testing Checklist (Hybrid only)

- [ ] gpio27 reads LOW when gantry mated
- [ ] gpio27 reads HIGH within 1ms of unmating
- [ ] `_GANTRY_DETACHED` macro fires on unmating
- [ ] XY steppers disabled within 10ms of detach
- [ ] `_GANTRY_ATTACHED` macro fires on mating
- [ ] No false triggers from vibration during operation
- [ ] Endstops read correctly through pogo
- [ ] Step/dir signals maintain integrity through pogo at max speed
- [ ] Base StitchLAB image build does not contain `hybrid_macros.cfg` or any gantry-detect references
