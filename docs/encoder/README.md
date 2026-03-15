# StitchLAB Handwheel Encoder Integration

This directory contains documentation and source code for adding an AS5600 magnetic encoder to the StitchLAB handwheel. The goal is to enable **Embroiderino-style needle synchronization** and **hybrid embroidery/sewing mode**.

## Overview

Adding a single encoder to the handwheel enables:
- **Synchronized Embroidery:** XY movement waits for encoder to confirm needle is UP before moving hoop
- **Free-Motion Sewing:** User controls needle via foot pedal; encoder tracks position for UI feedback
- **Hybrid Mode:** Switch between automated embroidery and manual sewing without reconfiguration

The prototype was developed on stitchlab04.local (multi-motor simulator), but for StitchLAB only the **single handwheel encoder** is relevant.

## Key Files

| File | Description |
|------|-------------|
| [as5600.py](as5600.py) | Custom Klipper module for AS5600 encoder (Python) |
| [SYSTEM_GUIDE.md](SYSTEM_GUIDE.md) | Complete system guide - architecture, configuration, troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Multi-phase development roadmap and technical architecture |
| [HARDWARE_WIRING.md](HARDWARE_WIRING.md) | Wiring diagrams for SKR Pico + AS5600 |

## Hardware Setup

### Components
- **MCU:** SKR Pico (RP2040)
- **Encoder:** AS5600 magnetic rotary encoder (12-bit, 4096 positions/rev)
- **Interface:** I2C on i2c0a bus (GPIO0/GPIO1)
- **Address:** 0x36 (54 decimal)

### Wiring (AS5600 to SKR Pico P9 Header)
```
AS5600    →    SKR Pico
VCC       →    3.3V (Pin 1)
GND       →    GND (Pin 2)
SDA       →    GPIO0 (Pin 3)
SCL       →    GPIO1 (Pin 4)
DIR       →    GND (CW rotation)
```

## Software Configuration

### printer.cfg
```ini
[as5600 e0_encoder]
i2c_mcu: mcu
i2c_bus: i2c0a
i2c_address: 54
monitor_rate: 5.0          # Hz (increase for faster operation)
mode: hold                  # monitor | hold | track
stepper: manual_stepper e0_motor
position_tolerance: 2.0     # degrees
deadband: 3.0              # degrees
max_correction: 10.0       # degrees per cycle
correction_speed: 8.0      # mm/s
control_kp: 0.5
```

### G-code Commands
```gcode
QUERY_AS5600 SENSOR=e0_encoder      # Read position
AS5600_STATUS SENSOR=e0_encoder      # Check magnet
AS5600_START_MONITOR RATE=50         # Start monitoring
AS5600_STOP_MONITOR                  # Stop monitoring
AS5600_RESET_POSITION                # Reset revolution counter
AS5600_SET_TARGET POSITION=180       # Set hold target
AS5600_SET_TARGET CLEAR=1            # Disable hold
```

## Comparison: Embroiderino vs StitchLAB

| Aspect | Embroiderino | StitchLAB (AS5600) |
|--------|--------------|-------------------|
| **Sensor** | Optical (84 pulses/rev) | Magnetic (4096/rev) |
| **Resolution** | ~4.3° per pulse | 0.088° (12-bit) |
| **Interface** | Direct interrupt | I2C polling |
| **Control** | PI speed control (DC motor) | Position tracking (stepper) |
| **Needle Detection** | Separate optical sensor (INT1) | Same encoder (angle threshold) |
| **Max Rate** | Hardware interrupt | ~100 Hz (Python) |

## Use Case: Needle Position Detection

The encoder detects needle position by angle:
- **0°/360° = Needle UP** (safe to move XY)
- **180° = Needle DOWN** (in fabric)

This enables the `WAIT_NEEDLE_UP` macro pattern:
```python
def wait_needle_up():
    while True:
        angle = encoder.read_degrees()
        if angle < 10 or angle > 350:  # Near 0°/360°
            return  # Safe to move XY
        sleep(0.01)  # Poll at 100Hz
```

## Development Status

### Phase 1: Prototype ✅ Complete (on stitchlab04)
- Python-based AS5600 Klipper module
- Position monitoring and hold mode
- Up to 200 SPM demonstrated

### Phase 2: Integration ← Next
- Mount encoder on StitchLAB handwheel
- Calibrate needle UP/DOWN angles
- Create WAIT_NEEDLE_UP macro
- Test synchronized embroidery

### Phase 3: Hybrid Mode
- Integrate foot pedal control
- UI feedback for needle position
- Switch between embroidery and sewing modes

## Performance Limits

| Monitor Rate | Max Safe SPM | Implementation |
|--------------|--------------|----------------|
| 50 Hz | 200 | Python OK |
| 100 Hz | 300 | Python marginal |
| 500 Hz | 600 | MCU firmware needed |
| 1000 Hz | 1200 | MCU firmware needed |

## Testing

### Query Current Position
```bash
curl -X POST "http://stitchlab04.local:7125/printer/gcode/script" \
  -H "Content-Type: application/json" \
  -d '{"script": "QUERY_AS5600 SENSOR=e0_encoder"}'
```

### Monitor Live Data
```bash
curl -s "http://stitchlab04.local:7125/printer/objects/query?as5600%20e0_encoder" | python3 -m json.tool
```

## Remote Access

```bash
# SSH
ssh pi@stitchlab04.local  # password: lab

# Mainsail UI
http://stitchlab04.local

# Moonraker API
http://stitchlab04.local:7125
```

## Source Locations on stitchlab04

```
/home/pi/klipper/klippy/extras/as5600.py    # Klipper module
/home/pi/sewing_project/                     # Documentation
/home/pi/printer_data/config/printer.cfg    # Configuration
```

## Related Documentation

- [Embroiderino Comparison](../Reports/Embroiderino-Comparison.md) - Detailed comparison with markol's project
- [StitchLAB Architecture](../02-architecture.md) - Overall system architecture
