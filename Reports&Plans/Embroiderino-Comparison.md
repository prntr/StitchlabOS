# Embroiderino vs StitchLAB: In-Depth Technical Comparison

## Executive Summary

This analysis compares the **Embroiderino** project (markol/embroiderino + Teathimble Firmware) with **StitchLAB**, focusing on handwheel/needle control, XY coordination, and timing synchronization.

| Aspect | Embroiderino/Teathimble | StitchLAB |
|--------|------------------------|-----------|
| **Firmware** | Custom AVR (Teathimble) | Klipper (3D printer firmware) |
| **Needle Control** | DC motor with encoder + optical sensor | Stepper motor (Z-axis) |
| **XY Control** | Custom DDA with CoreXY | Klipper motion planner |
| **Synchronization** | Hardware interrupt-based | G-code sequential + M400 |
| **Needle Detection** | Optical sensor on needle position | Position modulo calculation |

---

## 1. Architecture Overview

### Embroiderino/Teathimble

```
┌─────────────────────────────────────────────────────────┐
│  Python Client (TK GUI)                                 │
│  • CSV file loading (Embroidermodder2 format)          │
│  • G-code generation and streaming                      │
└─────────────────────────────────────────────────────────┘
                    ↓ (Serial 115200 baud)
┌─────────────────────────────────────────────────────────┐
│  Teathimble Firmware (AVR MCU @ 16-20MHz)              │
│  ├─ gcode_parse: G0, G1, G28, G90, G91, M0, M112...   │
│  ├─ motor.c: DDA stepping, acceleration, look-ahead    │
│  ├─ sensors_control.c: Needle detection, DC motor PI   │
│  ├─ timer-avr.c: Interrupt-based step timing           │
│  └─ kinematics.c: CoreXY transformation                │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  Hardware                                               │
│  • 2x NEMA17 steppers (CoreXY for XY movement)         │
│  • Original universal motor (AC/DC capable, DC driven) │
│  • Optical encoder (84 pulses/rev for speed)           │
│  • Optical sensor (INT1 for needle position)           │
└─────────────────────────────────────────────────────────┘
```

### StitchLAB

```
┌─────────────────────────────────────────────────────────┐
│  TurtleStitch + Mainsail Frontend                       │
│  • Visual programming for embroidery                    │
│  • G-code generation with configurable feedrates        │
│  • Embroidery control panel UI                          │
└─────────────────────────────────────────────────────────┘
                    ↓ (WebSocket + HTTP)
┌─────────────────────────────────────────────────────────┐
│  Moonraker → Klipper                                    │
│  ├─ embroidery_macros.cfg: Needle state machine        │
│  ├─ Klipper motion planner: All axis coordination      │
│  └─ G92 position override for logical/physical split   │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  Hardware                                               │
│  • 2x NEMA17 steppers (XY linear rails)                │
│  • 1x NEMA23 stepper (Z-axis = handwheel)              │
│  • Original universal motor removed (Pfaff AC/DC)      │
│  • No needle position sensor (open-loop)               │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Handwheel/Needle Control - Critical Difference

### Embroiderino: Universal Motor with DC Drive and Closed-Loop Feedback

**Hardware:**
- **Original universal motor** is retained (series-wound, can run on AC or DC)
- The motor is driven with **rectified DC + PWM** instead of AC phase control
- **Optical encoder** (84 pulses/revolution) measures motor speed
- **Optical sensor** (INT1 interrupt) detects needle apex position

> **What is a Universal Motor?** Universal motors have carbon brushes and series-wound field coils. They can operate on both AC and DC power. When the current reverses in AC, both the field and armature reverse together, so torque direction stays the same. Running them on DC is actually smoother.

**Speed Control (PI Controller):**
```c
// From sensors_control.c
error = desired_speed - pv_speed;
accumulator += error * ki;  // Integral term
accumulator = CLAMP(accumulator, -ACCUMULATOR_LIMIT, +ACCUMULATOR_LIMIT);
pwm_output = (error * kp + accumulator) / POINT_SHIFT;
```

**Configuration:**
- Min speed: 80 RPM
- Max speed: 800 RPM
- Default: 500 RPM
- KP: 40,000, KI: 2,000

**Needle Position Detection:**
```c
// INT1 interrupt triggers on optical sensor
ISR(INT1_vect) {
    if (direction_encoder() == UPWARD) {
        // Needle at apex - safe to move XY
        dda_start(mb_tail_dda);  // Start queued movement
    } else {
        // Needle going down - handle stop flags
        if (stop_motor_flag == 1) stop_motor_flag = 2;
        else if (stop_motor_flag == 2) motor_stop();
    }
}
```

**Key Insight:** The sewing machine motor runs continuously at controlled speed. XY movements are **triggered by needle position** - they only start when the needle reaches its apex (highest point), ensuring the needle is out of the fabric during hoop movement.

> **Why DC Drive?** Driving a universal motor with DC (rectified mains + PWM) has advantages over AC phase control (triac): smoother operation, simpler control electronics, no zero-crossing detection needed. The Hackster/SpaceForOne project notes the motor runs at ~500Hz PWM switching frequency.

### StitchLAB: Stepper Motor Replaces Universal Motor

**Hardware:**
- **NEMA 23 stepper** replaces the original universal motor
- 15-tooth drive pulley → 69-tooth handwheel (4.6:1 ratio)
- **No position sensor** - relies on stepper motor accuracy

> **Why motor replacement (current approach)?** The old Pfaff Tipmatic/Hobbymatic series (917, 1037, 1019, etc.) have **universal motors** with carbon brushes. StitchLAB currently replaces these with a stepper to integrate with the Klipper/3D printer ecosystem and avoid mains voltage electronics.

> **Alternative: DC Drive (future option)** Since Pfaff universal motors can run on DC, an Embroiderino-style DC drive circuit could potentially retain the original motor. This would enable higher stitch rates and hybrid embroidery/sewing mode with foot pedal control. See Section 8.3.

**Position Model:**
```
1 full handwheel rotation = 5mm Z travel = 1 complete stitch
Z = 0.0mm → Needle UP (0°/360°)
Z = 2.5mm → Needle DOWN (180°)
Z = 5.0mm → Needle UP (360°) - stitch complete
```

**Control Macros:**
```gcode
[gcode_macro STITCH]
gcode:
    {% set feedrate = printer.configfile.settings.printer.max_z_velocity * 60 %}
    {% set current_z = printer.gcode_move.gcode_position.z %}
    G91
    G1 Z5 F{feedrate}  ; One full rotation
    M400               ; Wait for completion
    G90
    G92 Z{current_z}   ; Restore logical position
```

**Key Insight:** StitchLAB has no feedback about actual needle position. Other than the Z endstop for homing. It assumes the stepper moves exactly as commanded. The Z-axis stepper **replaces the DC motor**, giving precise position control but no variable speed within a stitch cycle.

---

## 3. XY-Needle Synchronization - The Critical Timing Problem

### Embroiderino: Hardware Interrupt Synchronization

```
                    Time →
DC Motor:    ───────────────────────────────────
              ↑needle up    ↑needle down    ↑needle up
              │             │               │
              ▼ INT1        │               ▼ INT1
XY Movement: ═════════════  │               ═════════════
             (move during   │               (next move)
              needle up)    │
                           (fabric pierced,
                            NO XY movement)
```

**Mechanism:**
1. G-code commands are parsed and queued in move buffer (8 moves)
2. DC motor runs continuously at set RPM
3. When optical sensor detects needle UP position → INT1 fires
4. ISR calls `dda_start()` to begin next queued XY movement
5. Movement completes while needle is still up
6. Next stitch: wait for next INT1

**"Jump" Handling:**
When the next stitch is too far (>16mm), the DC motor slows down or pauses:
```c
// From config.h
#define MAX_JUMP_LENGTH 16  // mm
#define JUMP_SPEED_DIFFERENCE 80  // RPM slowdown
#define JUMP_SLOWDOWN_DISTANCE 20  // start slowing here
```

### StitchLAB: Sequential G-code Synchronization

```
                    Time →
G-code:      G1 X10 Y20 Z5 → M400 → G4 P80 → G1 X15 Y25 Z10 → ...
             ├──────────────────────────────┤
                    One stitch cycle

Z Movement:  ▁▁▁▂▃▅▇█▇▅▃▂▁▁▁▂▃▅▇█▇▅▃▂▁▁▁
             UP      DOWN    UP      DOWN
```

**Mechanism:**
1. TurtleStitch or InkStich generates G-code with coordinated XY+Z moves
2. Klipper motion planner handles all axes simultaneously
3. `G1 X__ Y__ Z__` moves all three axes in sync
4. `M400` blocks until move complete
5. `G4 P80` dwell allows needle to settle

**From embroider.js:**
```javascript
// Stitch move - all axes coordinated
gcode += `G1 X${x.toFixed(3)} Y${y.toFixed(3)} Z${currentZ.toFixed(3)} F${stitchFeed}\n`;
currentZ += zPerStitchMm;  // Increment Z for next stitch
```

**Key Difference:** StitchLAB moves XY and Z simultaneously in a single coordinated move. There's no "wait for needle up" - instead, the Z motor IS the needle, so moving Z=5mm means completing one stitch.

---

## 4. Z-Axis Usage Comparison

### Embroiderino: No Z-Axis for Needle

- **Z-axis not used for needle control** - the DC motor handles the sewing machine mechanism
- The plotter (Simple_plotter) has XY only
- Needle position is detected, not controlled positionally

### StitchLAB: Z-Axis IS the Handwheel

- **Z-axis directly controls handwheel rotation**
- 5mm Z travel = 1 full handwheel rotation = 1 stitch
- Physical position vs logical position managed via G92
- Stepper precision replaces encoder feedback

**Trade-off:**
| Approach | Pros | Cons |
|----------|------|------|
| **Universal Motor + DC Drive** (Embroiderino) | Retains original motor, variable speed, high stitch rates (800 SPM), foot pedal compatible | Requires mains rectification, PI tuning, can't hold position, needs encoder + needle sensor |
| **Stepper replacing motor** (StitchLAB current) | Avoids mains electronics, precise positioning, holds position, integrates with Klipper | Requires motor replacement, slower stitch rates, no position feedback, needs NEMA 23 for torque |
| **Universal Motor + DC Drive** (StitchLAB future?) | Could retain Pfaff motor, enable hybrid mode, higher speeds | Requires high-voltage electronics, safety considerations, more complex |

---

## 5. Motion Planning

### Embroiderino: Custom DDA with Look-ahead

**Digital Differential Analyzer (DDA):**
```c
// From motor.c
move_state.counter[X] -= dda->delta[X];
if (move_state.counter[X] < 0) {
    x_step();
    move_state.counter[X] += dda->total_steps;
}
```

**Features:**
- True acceleration with ramp-up/ramp-down
- Look-ahead calculates crossing speeds between moves
- CoreXY kinematics transformation
- Maximum 48,000 steps/second on 20MHz
- Integer-only math for CPU efficiency

**Acceleration Formula:**
```c
c0 = (uint32_t)((double)F_CPU / SQRT((double)STEPS_PER_M_X * ACCELERATION / 2000.));
// Step interval: c0 * (1 / (2 * sqrt(n)))
```

### StitchLAB: Klipper Motion Planner

**Delegated to Klipper:**
- No custom motion code needed
- Klipper handles acceleration, jerk, pressure advance
- G-code feedrates control speed:
  - Travel: 6000 mm/min
  - Stitch: 1800 mm/min

**Macro Speed Calculation:**
```gcode
{% set feedrate = printer.configfile.settings.printer.max_z_velocity * 60 %}
```

---

## 6. Timing Architecture

### Embroiderino: Dual Timer System

```
Timer1 (16-bit):
├─ OCR1A: Step timing interrupt (COMPA)
│   └─ Fires when next_step_time reached
│   └─ Executes motor steps
│
└─ OCR1B: System clock (COMPB)
    └─ Fires at TICK_TIME intervals
    └─ Updates control loops, handles planning
```

**Interrupt Priority:**
- COMPA (stepping) > COMPB (system clock)
- `sei()` re-enables interrupts within handlers for nested execution

### StitchLAB: Klipper Real-Time

- Klipper runs on separate MCU (SKR Pico)
- Host (Raspberry Pi) sends G-code commands
- MCU handles real-time stepping independently
- `M400` synchronizes host with MCU motion queue

---

## 7. Configuration Comparison

| Parameter | Embroiderino | StitchLAB |
|-----------|--------------|-----------|
| Steps/mm (XY) | 87,575 (CoreXY) | Configurable in printer.cfg |
| Max Feedrate | 33,000 mm/min | 6,000 mm/min (travel) |
| Acceleration | 2,500 mm/s² | Set in Klipper config |
| Jerk | 400 mm/min | Klipper square_corner_velocity |
| Work Area | 280×280 mm | ~100×100 mm (mounted on machine) |
| Stitch Rate | Up to 800 RPM | Limited by Z stepper speed |

---

## 8. Recommendations for StitchLAB

Based on this analysis, here are potential improvements:

### 8.1 Consider Adding Needle Position Feedback

**Problem:** StitchLAB has no feedback about actual needle position other than the Z endstop
**Solution:** Add an optical sensor similar to Embroiderino

```
┌─────────────────────────────────────────┐
│  Optical sensor on handwheel            │
│  • Detects needle apex (UP position)    │
│  • Feeds back to Klipper via GPIO       │
│  • Enables "stitch verification"        │
└─────────────────────────────────────────┘
```

**Implementation:**
- Mount optical sensor to detect specific handwheel position
- Connect to Klipper as filament sensor or probe input
- Create macro that waits for sensor before continuing

### 8.2 Consider Triggered Movement Mode

**Embroiderino's approach:**
- Queue moves in buffer
- Start each move only when needle detected UP
- Prevents fabric damage from mid-stitch hoop movement

**For StitchLAB:**
```gcode
[gcode_macro WAIT_NEEDLE_UP]
gcode:
    {% if printer["filament_switch_sensor needle_sensor"].filament_detected %}
        ; Needle is up, safe to move
    {% else %}
        G4 P10  ; Wait 10ms
        WAIT_NEEDLE_UP  ; Recursive wait
    {% endif %}
```

### 8.3 Hybrid Motor Control (Future)

From your Praxistest notes, you mentioned:
> "Freihandsticken - Bräuchte ein eigenes Controller Board, um eine Bedienung per Fußpedal zu ermöglichen"

**Key Discovery: Pfaff Motors are Universal Motors**

The Pfaff Tipmatic/Hobbymatic series (917, 1037, 1019, 6085, etc.) use **universal motors** with carbon brushes (4×4×11mm replacement brushes available). Universal motors can run on both AC and DC—they are series-wound, so when current reverses, both field and armature reverse together.

This opens a **third development path** for StitchLAB:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Stepper only** (current) | NEMA 23 replaces original motor | Simple, Klipper-native | No foot pedal, slower |
| **B: Stepper + DC motor** | Add separate DC motor for sewing mode | True hybrid | Two motors, complex |
| **C: DC drive for universal motor** | Embroiderino-style circuit drives original Pfaff motor | Single motor, high speed, foot pedal | High voltage, safety |

**Option C: DC Drive for Pfaff Universal Motor**

Based on the [Hackster/SpaceForOne](https://www.hackster.io/spaceforone/arduino-based-embroidery-machine-2f2f69) and [markol](https://lordovervolt.com/embroidery) projects:

```
┌─────────────────────────────────────────────────────────┐
│  DC Drive Circuit for Universal Motor                   │
│                                                         │
│  230V AC ──► Bridge Rectifier ──► ~300V DC              │
│                                      │                  │
│                                 PWM MOSFET              │
│                                 (IRF840)                │
│                                      │                  │
│  MCU ──► Optocoupler ──────────► Gate Drive            │
│                                      │                  │
│                              Universal Motor            │
│                              (Pfaff original)           │
└─────────────────────────────────────────────────────────┘
```

**Advantages of DC drive:**
- Smoother than AC phase control (no zero-crossing jitter)
- Simple PWM speed control (~500 Hz)
- Works with foot pedal (variable resistance → PWM duty cycle)
- Retains original Pfaff motor mechanics
- Enables 800+ SPM (vs ~200 SPM with stepper)

**Requirements:**
- Mains isolation (optocoupler mandatory)
- High-voltage MOSFET rated for 300V+ DC
- Encoder for speed feedback (PI control)
- Optical sensor for needle position detection
- Safety: proper enclosure, fusing, discharge resistors

**References:**
- [SpaceForOne's DC drive circuit](https://www.hackster.io/spaceforone/arduino-based-embroidery-machine-2f2f69)
- [markol's high-voltage driver](https://lordovervolt.com/embroidery)
- [Bigfoot motor control project](https://hackaday.io/project/193592-bigfoot-sewing-machine-motor-speed-control)

### 8.4 Look-ahead Implementation

Embroiderino's look-ahead calculates crossing speeds between moves. While Klipper has this built-in for G-code moves, the macro-based stitch execution doesn't benefit from it.

**Current StitchLAB:**
```
Move → M400 → Stitch → M400 → Move → M400 → ...
       ↑             ↑
    Full stops between operations
```

**Improvement:**
- Let G-code do coordinated XYZ moves directly
- Minimize macro overhead
- Use Klipper's native motion planning

---

## 9. Key Takeaways

### What Embroiderino Does Well:
1. **True synchronization** - XY moves only during needle-up
2. **Retains original motor** - Variable speed, proven mechanics
3. **Look-ahead planning** - Smooth motion between stitches
4. **Jump detection** - Slows for long travel moves

### What StitchLAB Does Well:
1. **Simpler electronics** - Just steppers, no PI tuning
2. **Klipper ecosystem** - Web UI, remote control, plugins
3. **Precise positioning** - Stepper holds position exactly
4. **Educational focus** - Uses familiar 3D printer concepts

### Critical Architectural Difference:
- **Embroiderino:** "Needle controls movement" (interrupt-driven)
- **StitchLAB:** "Movement controls needle" (sequential G-code)

Both approaches can produce quality embroidery, but Embroiderino's approach is more similar to commercial machines, while StitchLAB's is more accessible for the maker community.

---

## 10. Proposed Handwheel Encoder for StitchLAB

Adding a single encoder to the handwheel would enable Embroiderino-style needle synchronization and unlock hybrid embroidery/sewing functionality.

### Why Add an Encoder?

**Current StitchLAB (open-loop):**
- Stepper drives handwheel → assumes position is correct
- XY and Z move simultaneously via G-code
- No verification that needle is actually UP before hoop moves

**With Handwheel Encoder:**
- Know actual needle position (UP at 0°/360°, DOWN at 180°)
- Enable "move only when needle is up" like Embroiderino
- Support hybrid mode: foot pedal controls needle, encoder tracks position

### Use Cases Enabled

| Mode | Description |
|------|-------------|
| **Synchronized Embroidery** | XY movement waits for encoder to confirm needle UP before moving hoop |
| **Free-Motion Sewing** | User controls needle via foot pedal; encoder tracks position for UI feedback |
| **Hybrid Mode** | Switch between automated embroidery and manual sewing without reconfiguration |

### Hardware Concept

```
┌─────────────────────────────────────────────────────────┐
│  Handwheel with AS5600 Encoder                          │
│                                                         │
│     Magnet on                  AS5600 sensor            │
│     handwheel shaft ─────────► reads angle              │
│                                    │                    │
│                                    ▼                    │
│                            ┌──────────────┐             │
│                            │ 0° = Needle UP             │
│                            │ 180° = Needle DOWN         │
│                            │ (12-bit resolution)        │
│                            └──────────────┘             │
└─────────────────────────────────────────────────────────┘
```

**Components needed:**
- 1× AS5600 magnetic encoder module
- 1× Diametric magnet (6mm × 2mm) on handwheel shaft
- I2C connection to SKR Pico (GPIO0/GPIO1)

### Proposed Integration

**For Embroidery Mode:**
```python
# Wait for needle UP before XY movement
def wait_needle_up():
    while True:
        angle = encoder.read_degrees()
        if angle < 10 or angle > 350:  # Near 0°/360°
            return  # Safe to move XY
        sleep(0.01)  # Poll at 100Hz
```

**For Hybrid/Free-Motion Mode:**
- Foot pedal controls original DC motor (or separate motor controller)
- Encoder provides position feedback to Klipper/UI
- User sees needle position indicator in Mainsail

### Comparison with Embroiderino

| Aspect | Embroiderino | StitchLAB + Encoder |
|--------|--------------|---------------------|
| **Encoder Purpose** | Speed feedback for DC motor PI control | Position feedback for needle sync |
| **Needle Detection** | Separate optical sensor (INT1) | Same encoder (angle threshold) |
| **XY Trigger** | Hardware interrupt when needle UP | Software polling + macro |
| **Motor Control** | DC motor with PWM | Stepper (embroidery) or DC (hybrid) |

### Implementation Options

**Option A: Pure Software (Klipper Macros)**
- Poll encoder in macro, wait for needle UP
- Simple, no firmware changes
- Limited to ~100 Hz polling (Python reactor)

**Option B: Klipper Module (as5600.py)**
- Dedicated module monitors encoder
- Exposes needle state to macros
- Prototype exists on stitchlab04

**Option C: MCU Firmware**
- Hardware timer samples encoder at 500-1000 Hz
- Triggers XY movement via interrupt
- Most similar to Embroiderino, highest performance

### Prototype Status

A prototype AS5600 Klipper module has been developed on `stitchlab04.local`:
- Custom `as5600.py` Klipper extra
- Monitors encoder position via I2C
- Tracks revolutions and absolute angle
- Branch: `as5600-test`

**Note:** The stitchlab04 prototype also explores multi-motor configurations for a sewing machine simulator. For StitchLAB, only the single handwheel encoder is relevant.

### Next Steps

1. **Mount encoder on handwheel** - Attach magnet to shaft, position AS5600 sensor
2. **Calibrate needle angles** - Determine exact degrees for UP/DOWN positions
3. **Create WAIT_NEEDLE_UP macro** - Block XY until encoder confirms safe position
4. **Test synchronized embroidery** - Verify no hoop movement while needle is in fabric
5. **Design hybrid mode** - Integrate foot pedal control with encoder feedback

---

## 11. Open-Source DIY Embroidery Landscape (Selected Projects)

This section surveys other open-source DIY embroidery efforts to map the broader design space around hardware and software strategies beyond Embroiderino and StitchLAB.

### 11.1 Project Comparison

| Project | Hardware strategy | Needle control / sensing | Controller / firmware | Software workflow |
|---------|-------------------|--------------------------|-----------------------|-------------------|
| **OpenEmbroidery (F33RNI)** | XY hoop gantry with NEMA17 steppers (belt drive, 3D printed parts) | Hall sensor for needle position; servo thread tensioner for jump stitches; retains sewing machine motor | Arduino Mega | Python app converts designs to G-code; SD card playback with rotary encoder + I2C LCD |
| **Ink/Stitch self-made machine (jameskolme)** | GT2 belt XY gantry with NEMA17 steppers; stepper + pulley on handwheel | Stepper-driven handwheel (open-loop) | Arduino running GRBL | Inkscape + InkStitch to G-code |
| **OpenBuilds: XY belt + pinion drive** | V-slot belt and pinion XY gantry; type 17 steppers with L298 drivers | Spring steel needle position detector; PIC monitors mains zero crossing and triac motor control (opto-isolated) | PIC16F73 | Android tablet UI via Bluetooth; serial ASCII protocol |
| **DIY Embroidery Machine V2 (OpenBuilds/SausagePaws)** | Belt/pinion XY gantry using 3 wheel plates; standard sewing machine | Retro-reflective needle-up detector; isolated 230 VAC motor controller | Arduino Nano + CNC shield + Bluetooth RS232 | Android tablet interface |
| **Embroidotron (CMU)** | Non-permanent conversion with fabric-positioner/hoop; CAD planned | Not specified in public docs | Arduino + Python communication | Python scripts + sample design files |
| **Arduino-based Embroidery Machine (Hackster, SpaceForOne)** | CoreXY hoop gantry; uses original sewing machine motor | Light barrier needle sensor + rotary encoder speed sensor; DC motor driver | Arduino UNO + CNC shield + A4988; Teathimble firmware | InkStitch -> G-code; Embroiderino control app |
| **Open Source Embroidery Machine (Hackaday)** | Conceptual 3D-printer-like XY bed + needle assembly | Not specified (early-stage) | Open-source electronics/software goal | Early-stage project documentation |

### 11.2 Strategy Patterns and Findings

- **Mechanical base:** Most projects keep the sewing machine head and add an XY hoop gantry. Belt/pinion and CoreXY show up repeatedly, with V-slot extrusions or 3D printed parts for the frame.
- **Needle synchronization:** Two camps dominate: sensor-gated motion (hall/optical/retro-reflective) vs open-loop stepper handwheel control. Sensor gating enables "move only when needle is up" behavior similar to commercial machines.
- **Motor strategy:** Retaining the original motor (with DC/triac control) favors higher stitch rates but demands sensing and electrical isolation; stepper retrofits simplify position control but can reduce speed.
- **Controller stack:** Arduino-class MCUs (UNO/Mega/Nano with GRBL or custom firmware) are the most common; PIC-based control appears in earlier OpenBuilds designs.
- **Workflow and UI:** G-code is the lingua franca, often generated with InkStitch/Inkscape or custom Python tools. Several builds aim for standalone UX using Android tablets over Bluetooth instead of a PC.
- **Documentation depth:** Detailed firmware and build docs exist for a few projects (OpenEmbroidery, OpenBuilds builds), while others remain high-level or early stage.

---

## 12. Source References

### Embroiderino Projects (Two Related Projects)

**markol's Embroiderino** (original):
- Main repo: https://gitlab.com/markol/embroiderino
- Firmware: https://gitlab.com/markol/Teathimble_Firmware
- Plotter CAD: https://gitlab.com/markol/Simple_plotter
- Documentation: https://lordovervolt.com/embroidery
- Motor: Universal motor with rectified DC + PWM via MOSFET (IRF840)

**SpaceForOne's Arduino-based Embroidery Machine** (builds on markol's work):
- Project: https://www.hackster.io/spaceforone/arduino-based-embroidery-machine-2f2f69
- Uses Teathimble firmware from markol
- Detailed DC drive circuit documentation for universal motors
- Machine: BERNINA 730/731/732 (1963 vintage)
- Key insight: Universal motors can be driven with DC for smoother operation

### StitchLAB Files
- [embroidery_macros.cfg](../stitchlabos/config/klipper/embroidery_macros.cfg)
- [EmbroideryControlPanel.vue](../mainsail/src/components/panels/EmbroideryControlPanel.vue)
- [embroider.js](../turtlestitch/src/embroider.js)

### StitchLAB Encoder Development (stitchlab04)
- [AS5600 Klipper Module](../encoder/as5600.py)
- [System Guide](../encoder/SYSTEM_GUIDE.md)
- [Architecture](../encoder/ARCHITECTURE.md)
- [Hardware Wiring](../encoder/HARDWARE_WIRING.md)
- Remote: `pi@stitchlab04.local` (Standardpasswort des Images, siehe README)

### Other DIY Projects
- OpenEmbroidery: https://github.com/F33RNI/OpenEmbroidery
- Ink/Stitch self-made machine: https://inkstitch.org/tutorials/embroidery-machine/
- OpenBuilds belt and pinion build: https://builds.openbuilds.com/builds/embroidery-machine-with-xy-belt-and-pinion-drive.691/
- OpenBuilds DIY Embroidery Machine V2: https://builds.openbuilds.com/builds/diy-embroidery-machine-v2.8630/
- Embroidotron repo: https://github.com/juanluivn/Embroidotron
- Embroidotron project page: https://juanluisvn.com/projects/
- Hackster (Arduino-based Embroidery Machine): https://www.hackster.io/spaceforone/arduino-based-embroidery-machine-2f2f69
- Hackaday (Open Source Embroidery Machine): https://hackaday.io/project/6011-open-source-embroidery-machine
