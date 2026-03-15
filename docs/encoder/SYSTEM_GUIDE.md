# Sewing Machine System Guide

> **Scope:** This guide covers the AS5600 encoder integration developed on stitchlab04. For StitchLAB, only the **single handwheel encoder** is relevant—to enable needle synchronization and hybrid embroidery/sewing mode. Multi-motor content applies to the StitchLABsim/stitchlabprodev simulator project.

## Hardware Components

### SKR Pico Controller (RP2040)
- **MCU:** Dual-core ARM Cortex-M0+ @ 125 MHz
- **RAM:** 264 KB SRAM
- **Flash:** 2 MB
- **Peripherals:** I2C, SPI, UART, PWM, DMA

### AS5600 Magnetic Encoder
- **Resolution:** 12-bit (4096 positions/revolution = 0.088° per step)
- **Interface:** I2C (address 0x36)
- **Supply:** 3.3V or 5V
- **Magnet:** Requires diametric magnet within 3mm
- **Output:** 360° absolute position

### Stepper Motor (E0)
- **Type:** NEMA17
- **Driver:** TMC2209 on SKR Pico
- **Pins:** Step=GPIO11, Dir=GPIO10, Enable=GPIO12
- **Configuration:** 16 microsteps, 200 steps/rev

### Mechanical System
- **Motor Pulley:** 20 teeth GT2
- **Driven Pulley:** 60 teeth GT2
- **Gear Ratio:** 3:1 reduction
- **Rotation Distance:** 40mm (configured)
- **Needle Stroke:** 100mm
- **Motor Revs per Stroke:** 2.5
- **Full Stitch Cycle:** 5 motor revolutions

## Wiring

### I2C Connection (AS5600 to SKR Pico)
```
AS5600          SKR Pico
------          --------
VCC     →       3.3V (Pin 36 or P9-pin1)
GND     →       GND (Pin 38 or P9-pin2)
SDA     →       GPIO0 (P9-pin3)
SCL     →       GPIO1 (P9-pin4)
DIR     →       GND (for CW rotation)
```

**I2C Bus:** i2c0a (hardware I2C peripheral 0, alternate pins)  
**Speed:** 400 kHz (Fast Mode)  
**Pull-ups:** Built-in on AS5600 module

### Motor Connection (E0)
```
SKR Pico        Stepper Driver
--------        --------------
GPIO11  →       STEP
GPIO10  →       DIR
GPIO12  →       ENABLE
```

## Software Architecture

### Klipper Module (as5600.py)

**Location:** `~/klipper/klippy/extras/as5600.py`

**Key Features:**
- Non-blocking I2C communication
- Revolution tracking with wraparound detection
- Configurable monitoring rate (5-100 Hz)
- Multiple modes: monitor, hold, track
- G-code command interface

**Configuration Parameters:**
```ini
i2c_mcu: mcu              # MCU with I2C connection
i2c_bus: i2c0a            # I2C bus name
i2c_address: 54           # AS5600 address (0x36)
i2c_speed: 400000         # Bus speed in Hz
monitor_rate: 100.0       # Sampling frequency in Hz
mode: monitor             # Mode: monitor/hold/track
stepper: manual_stepper e0_motor  # Linked stepper (for hold mode)
```

**Operating Modes:**

1. **monitor** - Read-only position monitoring
   - Tracks angle and revolutions
   - No motor control
   - Lowest CPU overhead

2. **hold** - Active position hold
   - Maintains target position
   - Issues correction moves when error exceeds deadband
   - Proportional control
   - Parameters: deadband, max_correction, correction_speed, control_kp

3. **track** - Position tracking with error logging
   - Follows commanded motor position
   - Logs deviation
   - No corrections applied

### Control Flow

```
Klipper Startup
    ↓
Initialize AS5600
    ↓
Register with I2C bus
    ↓
Start Timer (at monitor_rate Hz)
    ↓
┌─────────────────────────────┐
│  Timer Callback (periodic)  │
│  1. Request I2C read        │
│  2. Process response        │
│  3. Update position         │
│  4. Apply control (if hold) │
│  5. Schedule next timer     │
└─────────────────────────────┘
```

### Position Tracking Algorithm

```python
def update_position(current_raw, last_raw, revolutions):
    # Detect wraparound
    delta = current_raw - last_raw
    
    if delta > 2048:        # Wrapped backward (360° → 0°)
        revolutions -= 1
    elif delta < -2048:     # Wrapped forward (0° → 360°)
        revolutions += 1
    
    # Calculate absolute position
    angle = (current_raw * 360.0) / 4096.0
    absolute_position = (revolutions * 360.0) + angle
    
    return absolute_position, revolutions
```

## System Configuration

### printer.cfg Structure

```ini
[mcu]
serial: /dev/serial/by-id/usb-Klipper_rp2040_...

[printer]
kinematics: none
max_velocity: 1000
max_accel: 1000

[manual_stepper e0_motor]
step_pin: mcu:gpio11
dir_pin: !mcu:gpio10
enable_pin: !mcu:gpio12
microsteps: 16
rotation_distance: 40
velocity: 10
accel: 20

[as5600 e0_encoder]
i2c_mcu: mcu
i2c_bus: i2c0a
i2c_address: 54
i2c_speed: 400000
monitor_rate: 100.0
mode: monitor
```

## Performance Characteristics

### Sample Rate vs Motor Speed

| Monitor Rate | Update Period | Max Safe RPM | Max Safe SPM | Notes |
|--------------|---------------|--------------|--------------|-------|
| 5 Hz | 200 ms | 100 | 20 | Too slow - crashes |
| 20 Hz | 50 ms | 400 | 80 | Minimum stable |
| 50 Hz | 20 ms | 1000 | 200 | Good for testing |
| 100 Hz | 10 ms | 2000 | 400 | Python maximum |
| 500 Hz* | 2 ms | 10000 | 2000 | Requires MCU firmware |
| 1000 Hz* | 1 ms | 20000 | 4000 | Optimal for production |

*MCU firmware implementation (not yet implemented)

### Python vs MCU Sampling

**Current: Python-based (Klipper reactor)**
- ✅ Easy to develop and modify
- ✅ No firmware recompilation needed
- ✅ Good for prototyping
- ⚠ Limited to ~100 Hz due to reactor overhead
- ⚠ Variable latency (2-10ms)
- ❌ Cannot support >300 SPM reliably

**Future: MCU firmware (C)**
- ✅ Hardware timer-driven (deterministic)
- ✅ 500-2000 Hz sampling possible
- ✅ Direct stepper control (no USB latency)
- ✅ Can support 600+ SPM
- ⚠ Requires firmware development
- ⚠ More complex debugging

## StitchLAB Handwheel Integration

For the main StitchLAB project, the encoder serves a different purpose than multi-motor control:

### Needle Position Detection
```
Handwheel Angle    →    Needle State
─────────────────────────────────────
0° / 360°          →    UP (safe to move XY)
180°               →    DOWN (in fabric)
```

### Key Macro Pattern
```gcode
[gcode_macro WAIT_NEEDLE_UP]
gcode:
    {% set encoder = printer["as5600 e0_encoder"] %}
    {% set angle = encoder.angle %}
    {% if angle > 10 and angle < 350 %}
        G4 P50  ; Wait 50ms and retry
        WAIT_NEEDLE_UP
    {% endif %}
```

### Hybrid Mode Support
- **Embroidery Mode:** Stepper drives handwheel, encoder verifies position
- **Sewing Mode:** Foot pedal drives DC motor, encoder provides position feedback to UI

---

## Future Architecture (Multi-Motor) — StitchLABsim Only

> **Note:** This section applies to the multi-motor simulator project (stitchlab04/StitchLABsim), not the main StitchLAB embroidery machine.

### Hardware Requirements
- 1x TCA9548A I2C multiplexer (8 channels)
- 4x AS5600 encoders (one per motor)
- 4x Diametric magnets
- Current SKR Pico (sufficient for all 4 motors)

### Software Approach

**Phase 1:** Python coordination (easier, <300 SPM)
```python
# High-level stitch sequencing in Python
def execute_stitch():
    set_target(needle_encoder, 180°)
    wait_for_position(needle_encoder, 180°)
    set_target(hook_encoder, 360°)
    wait_for_position(hook_encoder, 360°)
    # etc...
```

**Phase 2:** MCU state machine (harder, >600 SPM)
```c
// Firmware-based stitch coordinator
// All 4 encoders sampled at 1kHz
// State transitions in <1ms
// Deterministic multi-motor coordination
```

### Resource Analysis (4 Motors)
- **CPU:** ~70% (44% for encoders, 10% steppers, 10% USB, 6% overhead)
- **RAM:** ~75 KB (5 KB encoders, 50 KB Klipper base, 20 KB queues)
- **Margin:** 30% CPU, 189 KB RAM remaining
- **Conclusion:** Single SKR Pico can handle all 4 motors + closed-loop

## Troubleshooting

### I2C Communication Issues
- **Symptom:** "Unable to read from i2c" errors
- **Causes:** Loose wiring, wrong pins, no pull-ups, bus contention
- **Solutions:**
  1. Verify wiring (GPIO0=SDA, GPIO1=SCL)
  2. Check magnet presence (AGC should be >0)
  3. Test I2C bus: `i2cdetect -y 0` on Pi
  4. Reduce i2c_speed to 100000

### Position Jitter
- **Symptom:** Angle jumps randomly
- **Causes:** Magnet misalignment, vibration, EMI
- **Solutions:**
  1. Center magnet precisely on shaft
  2. Verify <3mm gap to sensor
  3. Add mechanical damping
  4. Check for loose magnet

### Motor Not Holding Position
- **Symptom:** Motor doesn't resist manual turning
- **Causes:** Hold mode not active, stepper disabled, target not set
- **Solutions:**
  1. Verify `mode: hold` in config
  2. Check motor enabled: `MANUAL_STEPPER STEPPER=e0_motor ENABLE=1`
  3. Set target: `AS5600_SET_TARGET SENSOR=e0_encoder`
  4. Increase correction_speed if response too slow

### Reactor Overload / Crashes
- **Symptom:** "Timer too close" errors, Klipper crashes
- **Causes:** monitor_rate too high for motor speed
- **Solutions:**
  1. Reduce motor speed
  2. Lower monitor_rate (try 50 Hz)
  3. Switch to MCU firmware implementation

## Key Insights

### Why This Works
1. **Non-blocking I2C:** Reactor stays responsive
2. **Timer-based sampling:** Consistent update rate
3. **Revolution tracking:** Handles unlimited rotation
4. **Deadband control:** Prevents oscillation
5. **Proven patterns:** Based on mpu9250.py reference

### Design Decisions
- **Standard I2C vs Custom Firmware:** Standard I2C chosen for Phase 1
  - Faster development
  - Easier debugging
  - Sufficient for initial testing (<300 SPM)
  - Clear upgrade path to firmware

- **Manual Stepper vs Regular Stepper:** Manual stepper chosen
  - Allows independent control
  - No need for full kinematics
  - Easier to command from encoder module

- **Proportional vs PID Control:** Start with proportional (P-only)
  - Simpler to tune
  - Sufficient for position hold
  - Can add I and D terms if needed
