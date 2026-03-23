# Sensorless Homing Research — StitchLab OS (SKR Pico + RPi 4)

> **Status: Research only — not implemented.** This document captures findings and recommendations; no config changes have been made.

> Investigation into replacing physical endstops with TMC2209 StallGuard-based sensorless homing.

## Current Setup Summary

| Axis | Driver | UART Addr | Endstop Pin | Current (A) | StealthChop | Homing Speed |
|------|--------|-----------|-------------|-------------|-------------|-------------|
| X | TMC2209 | 0 | `^gpio4` | 0.580 | 999999 (always on) | 50 mm/s |
| Y | TMC2209 | 2 | `^gpio3` | 0.580 | 999999 (always on) | 50 mm/s |
| Z | TMC2209 | 1 | `^gpio25` | 1.200 | 0 (spreadCycle) | 5 mm/s |

- **Board**: BTT SKR Pico V1.0 (RP2040)
- **Host**: Raspberry Pi 4
- **Communication**: UART (`/dev/serial0` at 115200 baud)
- **Kinematics**: Cartesian
- **Z axis**: Drives handwheel/needle mechanism (rotation_distance: 1.087mm, position_max: 5,000,000mm)

---

## How Sensorless Homing Works

TMC2209 drivers have a **StallGuard** feature that detects motor stalls by monitoring back-EMF. When the carriage hits a mechanical stop, the motor stalls and the driver's DIAG pin goes high. Klipper reads this as a virtual endstop.

### Prerequisites (from Klipper docs)

1. StallGuard-capable TMC driver (**TMC2209 — yes, supported**)
2. UART interface wired to MCU (**yes, already configured**)
3. DIAG pin of TMC driver connected to MCU (**needs hardware verification**)
4. Stepper motors configured and working properly (**yes**)

---

## SKR Pico V1.0 DIAG Pin Mapping

The BTT SKR Pico reference config confirms the DIAG pins **share the same GPIO as the endstop pins**:

| Axis | Physical Endstop Pin | TMC2209 DIAG Pin | Virtual Endstop Name |
|------|---------------------|-------------------|---------------------|
| X | `gpio4` | `gpio4` | `tmc2209_stepper_x:virtual_endstop` |
| Y | `gpio3` | `gpio3` | `tmc2209_stepper_y:virtual_endstop` |
| Z | `gpio25` | `gpio25` | `tmc2209_stepper_z:virtual_endstop` |

**Key hardware detail**: On the SKR Pico, the TMC2209 DIAG pins are hardwired to the endstop connector pins. This means:
- **No additional wiring is needed** for X and Y sensorless homing — the DIAG signals already arrive at `gpio4` and `gpio3`.
- However, you **must remove the physical endstop switches** from those connectors (or they will conflict with the DIAG signal).

---

## Required Configuration Changes

### For X axis sensorless homing:

```ini
[stepper_x]
endstop_pin: tmc2209_stepper_x:virtual_endstop   # was: ^gpio4
homing_retract_dist: 0                             # MUST be 0 for sensorless
homing_speed: 20                                   # reduced from 50, see tuning

[tmc2209 stepper_x]
diag_pin: ^gpio4
driver_SGTHRS: 100                                 # 0-255, tune this (255=most sensitive)
# Remove hold_current if set
# stealthchop_threshold: 999999                    # Klipper auto-switches during homing
```

### For Y axis sensorless homing:

```ini
[stepper_y]
endstop_pin: tmc2209_stepper_y:virtual_endstop   # was: ^gpio3
homing_retract_dist: 0
homing_speed: 20

[tmc2209 stepper_y]
diag_pin: ^gpio3
driver_SGTHRS: 100
```

### Recommended homing macro:

```ini
[gcode_macro SENSORLESS_HOME_X]
gcode:
    {% set HOME_CUR = 0.400 %}
    {% set RUN_CUR = printer.configfile.settings['tmc2209 stepper_x'].run_current %}
    SET_TMC_CURRENT STEPPER=stepper_x CURRENT={HOME_CUR}
    G4 P2000                    # 2s pause to clear stall flag
    G28 X0
    G90
    G1 X5 F1200                 # Move away from endstop
    SET_TMC_CURRENT STEPPER=stepper_x CURRENT={RUN_CUR}

[gcode_macro SENSORLESS_HOME_Y]
gcode:
    {% set HOME_CUR = 0.400 %}
    {% set RUN_CUR = printer.configfile.settings['tmc2209 stepper_y'].run_current %}
    SET_TMC_CURRENT STEPPER=stepper_y CURRENT={HOME_CUR}
    G4 P2000
    G28 Y0
    G90
    G1 Y5 F1200
    SET_TMC_CURRENT STEPPER=stepper_y CURRENT={RUN_CUR}

[homing_override]
axes: xyz
gcode:
    SENSORLESS_HOME_X
    SENSORLESS_HOME_Y
    G28 Z                        # Z still uses physical endstop
```

---

## Potential Problems and Concerns

### 1. **Z Axis — DO NOT use sensorless homing**

This is the most critical concern. The Z axis on the StitchLab drives the **needle/handwheel mechanism**, not a linear rail:

- **rotation_distance: 1.087mm** — very small per rotation, meaning low back-EMF at homing speeds
- **run_current: 1.2A** — high current, but the mechanical load profile is non-standard
- **Homing speed: 5 mm/s** — too slow for reliable stall detection (Klipper docs: "less than 10 RPM" is unreliable)
- **Stall = needle jam**: A stall on Z could mean the needle hit fabric, thread tangled, or mechanism bound — all scenarios that should NOT be interpreted as "home found"
- **Z endstop (`gpio25`) has specific meaning**: needle at physical UP (0°) position

**Recommendation**: Keep the physical endstop on Z. Sensorless homing is not suitable for the needle mechanism.

### 2. **StealthChop vs SpreadCycle mode conflict**

Current config has `stealthchop_threshold: 999999` on X and Y (always in StealthChop mode).

- **Klipper automatically switches to SpreadCycle during sensorless homing** — this is correct and handled internally.
- However, the mode switch can cause a brief audible "click" or jerk during homing.
- After homing, it switches back to StealthChop — this transition can cause the carriage to drift slightly.

**Recommendation**: This is generally fine. Klipper handles the mode switching. No config change needed.

### 3. **Homing speed must be tuned carefully**

- Current X/Y homing speed is **50 mm/s** — this is likely **too fast** for sensorless homing.
- Klipper recommends: `rotation_distance / 2` = **40 / 2 = 20 mm/s** as a starting point.
- Too fast → excessive force on frame when stall is detected (the carriage slams).
- Too slow (<10 RPM) → TMC can't detect stalls reliably.

**Recommendation**: Start at 20 mm/s, tune between 15-25 mm/s.

### 4. **DIAG pin shares GPIO with endstop connector**

On SKR Pico, DIAG and endstop share the same pin. This means:
- **You MUST physically remove/disconnect the endstop switches** from X and Y.
- If a physical switch is still connected, it will pull the pin low and interfere with the DIAG signal.
- Alternatively, you can cut the DIAG jumper traces on the PCB and wire DIAG to separate GPIOs, but this is unnecessary on the SKR Pico since they share pins by design.

**Risk**: If the physical switches are left connected, homing will behave erratically — sometimes triggering from the switch, sometimes from StallGuard.

### 5. **Embroidery-specific frame/hoop force concerns**

Unlike a 3D printer where the carriage meets a hard mechanical stop:
- An embroidery machine's XY frame may have **variable resistance** from the hoop, fabric tension, or thread paths.
- StallGuard sensitivity may need different tuning depending on whether fabric is mounted.
- A heavy hoop could cause **false stalls** during normal moves if sensitivity is too high.
- A loose hoop could allow the carriage to **overshoot** the mechanical limit if sensitivity is too low.

**Recommendation**: Tune StallGuard with the typical load (hoop + fabric) mounted. Retest after material changes.

### 6. **Motor current during homing**

- Current X/Y `run_current: 0.580A` — this is relatively low.
- Klipper docs recommend reducing current during homing for more reliable stall detection.
- Suggested homing current: **0.300–0.500A** (about 50-85% of run current).
- Lower current = more sensitive stall detection, but also less holding force after stall.

**Risk**: If homing current is too low, the motor might stall prematurely from normal rail friction (false trigger). If too high, the carriage will slam hard into the mechanical stop before StallGuard triggers.

### 7. **No second homing pass**

With sensorless homing, `homing_retract_dist` **must** be set to 0 (no retract-and-rehome). This means:
- **Repeatability is lower** than physical switches (~1-2 full steps vs ~0.01mm for good microswitches).
- For embroidery, X/Y positioning accuracy of ±0.1-0.2mm is usually acceptable.
- However, if your designs require very precise registration (multi-color alignment), this could be an issue.

### 8. **UART bus contention (minor)**

All three TMC2209 drivers share a single UART bus (`gpio9`/`gpio8`) with different addresses (0, 1, 2). This works fine normally, but during homing:
- Klipper sends frequent UART queries to read StallGuard status.
- With shared UART, there's slightly higher bus traffic.
- On the RP2040 this is handled well, but watch for `Unable to read tmc uart` errors during homing.

### 9. **`homing_override` must be updated**

The existing `EMBROIDERY_HOME` macro calls `G28 X Y` then `G28 Z`. With sensorless homing:
- Must add a **2-second pause** before each sensorless home to clear the stall flag.
- Must **move the carriage away** from the rail limit after homing before homing the next axis.
- The `EMBROIDERY_HOME` macro will need to be updated to use the sensorless homing macros.

### 10. **Power supply stability**

StallGuard relies on measuring back-EMF, which is affected by supply voltage. If your 12V/24V PSU has sag under load (e.g., when the Z motor is running), StallGuard sensitivity can shift. Ensure a stable power supply.

---

## Tuning Procedure (once implemented)

1. Start with `driver_SGTHRS: 255` (most sensitive).
2. Issue `G28 X0` — axis should NOT move or should stop immediately.
3. Decrease SGTHRS gradually (e.g., 200, 150, 100, 75, 50) until the axis homes cleanly to the mechanical limit in one smooth motion.
4. Find the **highest value that homes successfully** (= maximum_sensitivity).
5. Continue decreasing to find the **lowest value that homes with a single touch** (no banging) (= minimum_sensitivity).
6. Set final value: `minimum_sensitivity + (maximum_sensitivity - minimum_sensitivity) / 3`.
7. Repeat for Y axis independently.

Use `SET_TMC_FIELD STEPPER=stepper_x FIELD=SGTHRS VALUE=<n>` to test without restarting.

---

## Verdict

| Axis | Sensorless Homing? | Confidence | Notes |
|------|--------------------|-----------|-------|
| **X** | **Yes — feasible** | High | Standard linear axis, DIAG pin ready |
| **Y** | **Yes — feasible** | High | Standard linear axis, DIAG pin ready |
| **Z** | **No — not recommended** | Firm | Needle mechanism, too slow, wrong failure mode |

### Benefits for StitchLab
- **Eliminates 2 endstop switches** and their wiring → fewer failure points
- **Cleaner hoop area** — no protruding switch bodies to catch on fabric/thread
- **No switch wear** over time (mechanical switches fatigue after thousands of cycles)

### Risks
- **Less repeatable** than microswitches (±0.1-0.2mm vs ±0.01mm)
- **Requires tuning** per motor load / machine config
- **Sensitive to environment** changes (current, voltage, temperature, hoop weight)
- **EMBROIDERY_HOME macro** must be rewritten

### Recommended approach
1. Keep physical endstop on Z (needle axis) — no change
2. Implement sensorless homing on X and Y only
3. Remove/disconnect X and Y physical endstop switches
4. Create `SENSORLESS_HOME_X` / `SENSORLESS_HOME_Y` macros with current reduction and 2s delay
5. Update `EMBROIDERY_HOME` to use the new macros
6. Tune SGTHRS on live hardware with typical hoop/fabric setup
