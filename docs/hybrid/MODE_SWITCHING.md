# Mode Switching — Embroidery / Sewing State Machine

> The StitchLAB Hybrid operates in two modes determined by gantry attachment state. This document defines the state machine, safety interlocks, macro design, and UI behavior for each mode.

## State Machine

```
                    ┌──────────────────┐
                    │     STARTUP      │
                    │  Read saved mode │
                    │  Check sense pin │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
              ┌─────│  VALIDATE STATE  │─────┐
              │     │ saved vs. actual │     │
              │     └──────────────────┘     │
              │                              │
     sense=HIGH                         sense=LOW
     (gantry on)                        (gantry off)
              │                              │
    ┌─────────▼──────────┐      ┌────────────▼───────────┐
    │    EMBROIDERY       │      │       SEWING            │
    │                     │      │                         │
    │ • XY enabled        │      │ • XY disabled           │
    │ • Homing required   │      │ • Foot pedal active     │
    │ • Stitch macros OK  │      │ • Encoder → UI only     │
    │ • Encoder syncs XY  │      │ • No XY commands        │
    │ • G-code jobs OK    │      │ • Stitch counter active  │
    └─────────┬───────────┘      └────────────┬────────────┘
              │                                │
         sense→LOW                        sense→HIGH
         (detach!)                         (attach!)
              │                                │
    ┌─────────▼───────────┐      ┌─────────────▼───────────┐
    │  EMERGENCY DISABLE  │      │  GANTRY DETECTED         │
    │  • M84 X Y          │      │  • Log event             │
    │  • Clear homing     │      │  • Prompt: "Home XY?"    │
    │  • Log event        │      │  • Wait for user action  │
    │  • → SEWING         │      │  • → EMBROIDERY          │
    └─────────────────────┘      └──────────────────────────┘
```

## Klipper Configuration

### Prerequisites

```ini
# printer.cfg

# Persistent variable storage (required for mode tracking)
[save_variables]
filename: ~/printer_data/config/variables.cfg

# Gantry detection sensor
[gcode_button gantry_detect]
pin: ^!mcu:gpio<N>
press_gcode:
    _GANTRY_ATTACHED
release_gcode:
    _GANTRY_DETACHED
```

### Mode Variable

The current mode is stored persistently:

```ini
# variables.cfg (auto-managed by SAVE_VARIABLE)
[Variables]
machine_mode = 'embroidery'
```

Macros read it via:
```jinja2
{% set mode = printer.save_variables.variables.machine_mode|default('embroidery') %}
```

## Macro Library

### Core Mode Macros

```ini
[gcode_macro _GANTRY_DETACHED]
description: Safety handler — fires when gantry sense loop breaks
gcode:
    { action_respond_info("⚠ GANTRY DETACHED — disabling XY steppers") }
    SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=0
    SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=0
    SAVE_VARIABLE VARIABLE=machine_mode VALUE='"sewing"'
    { action_respond_info("Mode: SEWING") }

[gcode_macro _GANTRY_ATTACHED]
description: Handler — fires when gantry sense loop connects
gcode:
    { action_respond_info("Gantry attached. Run EMBROIDERY_HOME to begin.") }
    SAVE_VARIABLE VARIABLE=machine_mode VALUE='"embroidery"'
    { action_respond_info("Mode: EMBROIDERY (unhomed — run EMBROIDERY_HOME)") }

[gcode_macro QUERY_MODE]
description: Display current machine mode and gantry state
gcode:
    {% set mode = printer.save_variables.variables.machine_mode|default('unknown') %}
    {% set gantry = printer["gcode_button gantry_detect"] %}
    { action_respond_info("Machine mode: %s" % mode) }
    { action_respond_info("Gantry sensor: %s" % ("ATTACHED" if gantry.state == "PRESSED" else "DETACHED")) }
```

### Mode Guards for Existing Macros

Existing embroidery macros should refuse to run in sewing mode if they involve XY movement:

```ini
[gcode_macro _REQUIRE_EMBROIDERY_MODE]
description: Guard macro — errors if not in embroidery mode
gcode:
    {% set mode = printer.save_variables.variables.machine_mode|default('embroidery') %}
    {% if mode != 'embroidery' %}
        { action_raise_error("Command requires EMBROIDERY mode (current: %s). Attach gantry first." % mode) }
    {% endif %}

[gcode_macro EMBROIDERY_HOME]
description: Home embroidery machine — XY first, then Z (needle to UP)
gcode:
    _REQUIRE_EMBROIDERY_MODE
    {% set x_center = printer.configfile.settings.stepper_x.position_max / 2 %}
    {% set y_center = printer.configfile.settings.stepper_y.position_max / 2 %}
    G28 X Y
    G28 Z
    G90
    G1 X{x_center} Y{y_center} F6000
```

### Sewing Mode Macros

```ini
[gcode_macro SEWING_STATUS]
description: Display sewing mode status
gcode:
    {% set mode = printer.save_variables.variables.machine_mode|default('unknown') %}
    {% if mode != 'sewing' %}
        { action_respond_info("Not in sewing mode (current: %s)" % mode) }
    {% else %}
        {% set z_pos = printer.toolhead.position.z %}
        {% set stitch_count = (z_pos / 5.0)|int %}
        { action_respond_info("=== Sewing Mode Status ===") }
        { action_respond_info("Stitch Count: %d" % stitch_count) }
        {% if printer["as5600 e0_encoder"] is defined %}
            {% set encoder = printer["as5600 e0_encoder"] %}
            { action_respond_info("Needle Angle: %.1f°" % encoder.degrees) }
        {% endif %}
        { action_respond_info("==========================") }
    {% endif %}

[gcode_macro RESET_STITCH_COUNTER]
description: Reset the stitch counter for sewing mode
gcode:
    G92 Z0
    { action_respond_info("Stitch counter reset to 0") }
```

## UI Behavior by Mode

### Embroidery Mode (Gantry Attached)

**Show:**
- EmbroideryControlPanel (needle toggle, stitch, lock stitch, zero, home)
- G-Code Studio (embroidery file viewer)
- XY jog controls
- File upload and print start

**Hide:**
- SewingControlPanel
- Pedal speed display

### Sewing Mode (Gantry Detached)

**Show:**
- SewingControlPanel:
  - Real-time pedal input (0-100% bar)
  - Needle speed (SPM or RPM)
  - Stitch counter
  - Reverse indicator
  - Needle position (if encoder present)
- Manual needle controls (STITCH, NEEDLE_TOGGLE still work — they only use Z)

**Hide:**
- XY jog controls (disabled, steppers off)
- G-Code Studio (no XY movement possible)
- Embroidery-specific buttons (EMBROIDERY_HOME)
- File upload / print start

### Always Visible

- Mode indicator badge: "EMBROIDERY" (green) or "SEWING" (blue)
- Gantry status: "Attached" / "Detached" with icon
- Emergency stop button
- Encoder readout (if present)
- Temperature displays (if applicable)

### Frontend Implementation Approach

The Mainsail frontend can detect mode via Moonraker's printer objects API:

```javascript
// In Vuex store or component
const mode = this.$store.state.printer['save_variables']?.variables?.machine_mode || 'embroidery'
const gantryAttached = this.$store.state.printer['gcode_button gantry_detect']?.state === 'PRESSED'
```

Conditional rendering:
```vue
<EmbroideryControlPanel v-if="machineMode === 'embroidery'" />
<SewingControlPanel v-if="machineMode === 'sewing'" />
<ModeIndicator :mode="machineMode" :gantry-attached="gantryAttached" />
```

## Safety Matrix

| Action | Embroidery Mode | Sewing Mode |
|--------|:-:|:-:|
| XY movement (G1 X Y) | Allowed (if homed) | Blocked by mode guard |
| Z movement (needle) | Allowed | Allowed |
| STITCH / LOCK_STITCH | Allowed | Allowed |
| EMBROIDERY_HOME | Allowed | Blocked |
| G-code job start | Allowed | Blocked |
| Foot pedal input | Ignored | Active |
| Encoder reading | Sync + verify | UI feedback only |

## Edge Cases

### Hot Detach During Print

1. Gantry sense goes LOW
2. `_GANTRY_DETACHED` fires immediately
3. XY steppers disabled (prevents driver damage)
4. **Active print is aborted** — Klipper will error because XY steppers are now disabled mid-move
5. User must re-home and restart print after reattaching

### Power-On with Gantry Already Attached

1. Klipper starts, reads `variables.cfg` → `machine_mode = 'embroidery'`
2. `gcode_button` reads sense pin → HIGH (attached) → consistent, no action needed
3. XY steppers are enabled but **not homed** — user must run `EMBROIDERY_HOME`

### Power-On with Gantry Detached, But Last Mode Was Embroidery

1. Klipper starts, reads `variables.cfg` → `machine_mode = 'embroidery'`
2. `gcode_button` reads sense pin → LOW (detached) → **mismatch**
3. On klippy:ready, a startup macro should validate and correct:

```ini
[delayed_gcode _VALIDATE_MODE_ON_STARTUP]
initial_duration: 2.0
gcode:
    {% set saved_mode = printer.save_variables.variables.machine_mode|default('embroidery') %}
    {% set gantry = printer["gcode_button gantry_detect"] %}
    {% if saved_mode == 'embroidery' and gantry.state != "PRESSED" %}
        { action_respond_info("Mode mismatch: saved=embroidery but gantry detached. Switching to sewing.") }
        SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=0
        SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=0
        SAVE_VARIABLE VARIABLE=machine_mode VALUE='"sewing"'
    {% endif %}
```

## Testing Checklist

- [ ] Mode variable persists across Klipper restarts
- [ ] Gantry detach during idle → XY disabled, mode switches to sewing
- [ ] Gantry detach during print → XY disabled, print aborted cleanly
- [ ] Gantry attach → mode switches to embroidery, requires homing
- [ ] Power-on mismatch (saved embroidery, gantry detached) → auto-corrects
- [ ] EMBROIDERY_HOME blocked in sewing mode
- [ ] STITCH and NEEDLE_TOGGLE work in both modes
- [ ] UI updates within 1s of mode change
- [ ] No false triggers from vibration
