# 12-Pin Pogo Connector — Gantry Interface

> The XY gantry connects to the StitchLAB Hybrid via a 12-pin pogo connector. Two pins are dedicated to gantry detection (sense loop). The remaining 10 pins carry motor signals and endstop inputs.

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
| 10 | GND | Common | Ground reference (redundant for reliability) |
| 11 | SENSE_OUT | MCU → Gantry | Sense loop output (3.3V) |
| 12 | SENSE_IN | Gantry → MCU | Sense loop return (read by MCU GPIO) |

> **Note:** Motor power (12/24V) is NOT routed through the pogo connector. The stepper drivers are on the SKR Pico; only step/dir/enable signals go to the gantry. The stepper motors on the gantry receive power from their own driver outputs on the SKR Pico via a separate power cable, or the drivers are on the gantry side. **This needs hardware design finalization.**

### Open Design Question: Driver Placement

Two options for the XY stepper drivers:

| Option | Pros | Cons |
|--------|------|------|
| **A: Drivers on SKR Pico** | Fewer gantry components, lighter gantry, simpler gantry PCB | Need motor power wires through pogo (high current), pogo must handle motor coil signals |
| **B: Drivers on gantry PCB** | Only low-current step/dir/enable through pogo (as shown above), cleaner separation | Gantry needs its own driver board, heavier/more complex gantry |

**Current assumption: Option B** — drivers on gantry, step/dir/enable through pogo. This keeps the pogo connector low-current and protects drivers from hot-plug transients.

If Option A is chosen, pins 1-6 would carry motor coil signals (high current) instead of step/dir/enable, and the pogo connector spec must be rated accordingly.

## Sense Loop Circuit

The sense loop detects whether the pogo connector is mated. It's a simple continuity check.

### Schematic

```
SKR Pico (MCU side)                  Gantry PCB
─────────────────                    ──────────

GPIO_SENSE_OUT ──── Pin 11 ═══╗
   (output HIGH)               ║     ╔══ Pin 11
                               ║     ║
                               ╚═════╝
                              (pogo mates)
                               ╔═════╗
                               ║     ║
GPIO_SENSE_IN ───── Pin 12 ═══╝     ╚══ Pin 12
   (input + pull-down)                │
                                 ┌────┴────┐
                                 │  1kΩ R  │  ← bridges Pin 11 to Pin 12
                                 └─────────┘

On MCU side:
   GPIO_SENSE_IN has 10kΩ pull-down to GND (internal or external)
```

### Logic

| Pogo State | SENSE_IN reads | Meaning |
|------------|---------------|---------|
| Mated | HIGH (3.3V through 1kΩ) | Gantry attached |
| Unmated | LOW (pulled down by 10kΩ) | Gantry detached |

### Why a Resistor (Not a Direct Bridge)

- **Current limiting:** prevents damage if pins short during mating
- **Identification:** different resistor values could identify gantry variants (future-proofing)
- **Debounce-friendly:** resistor + pull-down forms an RC filter with parasitic capacitance

### Alternative: ADC-Based Gantry ID

For future multi-gantry support, replace the digital sense with an ADC reading:

| Resistor Value | ADC Reading (~) | Gantry Type |
|----------------|-----------------|-------------|
| Open (no gantry) | 0V | Detached |
| 1.0kΩ | 2.97V | Standard (200×200mm) |
| 2.2kΩ | 2.63V | Wide (300×200mm) |
| 4.7kΩ | 2.12V | Reserved |
| 10kΩ | 1.65V | Reserved |

This uses a voltage divider: `V_sense = 3.3V × R_pull_down / (R_bridge + R_pull_down)` where R_pull_down = 10kΩ.

**For now, digital sense (attached/detached) is sufficient.**

## Klipper Integration

### Option 1: Use Klipper's `[filament_switch_sensor]` Pattern

Klipper already has GPIO monitoring with event callbacks. The gantry sensor follows the same pattern:

```ini
# printer.cfg
[gcode_button gantry_detect]
pin: ^!mcu:gpio<N>          # Active-high with external pull-down, or use ^! for active-low
press_gcode:
    _GANTRY_ATTACHED
release_gcode:
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
- **Gantry side:** Flat pad array matching pogo pin positions, plus 1kΩ sense bridge resistor

## Testing Checklist

- [ ] Sense loop reads HIGH when gantry mated
- [ ] Sense loop reads LOW within 1ms of unmating
- [ ] `_GANTRY_DETACHED` macro fires on unmating
- [ ] XY steppers disabled within 10ms of detach
- [ ] `_GANTRY_ATTACHED` macro fires on mating
- [ ] No false triggers from vibration during operation
- [ ] Endstops read correctly through pogo
- [ ] Step/dir signals maintain integrity through pogo at max speed
