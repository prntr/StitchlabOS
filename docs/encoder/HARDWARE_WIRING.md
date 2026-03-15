# AS5600 Encoder Wiring Reference

## Overview

This document covers the **SKR Pico + AS5600** encoder setup for handwheel position feedback in StitchLAB.

---

## SKR Pico - AS5600 Encoder Setup

### AS5600 to SKR Pico

### Pin Connections
```
AS5600 Module          SKR Pico Board
─────────────          ──────────────
VCC (3.3V)      →      P9 Pin 1 (3.3V) or Pin 36
GND             →      P9 Pin 2 (GND) or Pin 38
SDA             →      P9 Pin 3 (GPIO0)
SCL             →      P9 Pin 4 (GPIO1)
DIR             →      GND (for clockwise rotation)
```

### P9 Connector Location
Located near the center of the SKR Pico board, labeled "P9"

**Pinout (4-pin connector):**
```
   [3.3V] 1  2 [GND]
   [SDA ] 3  4 [SCL]
```

### I2C Bus Configuration
- **Bus name:** i2c0a (hardware I2C0, alternate pins)
- **Speed:** 400 kHz (Fast Mode)
- **Address:** 0x36 (54 decimal) - AS5600 fixed address
- **Pull-ups:** Built-in on AS5600 module (4.7kΩ typical)

## Motor Wiring (E0)

### SKR Pico to Stepper Driver
```
SKR Pico GPIO          E0 Driver Pins
─────────────          ──────────────
GPIO11          →      STEP
GPIO10          →      DIR
GPIO12          →      ENABLE
```

### Motor Power
- **Driver:** TMC2209 (built-in to SKR Pico)
- **Motor Power:** 12V or 24V (via main power input)
- **Current:** Set via `run_current` in printer.cfg

## Magnet Installation

### Magnet Specifications
- **Type:** Diametric (N-S poles across diameter)
- **Size:** 6mm diameter × 2-3mm thick (typical)
- **Strength:** Neodymium recommended

### Positioning
```
     Encoder IC
         │
         │ <-- Gap: 0.5-3mm optimal
         │
    ┌────┴────┐
    │    N    │  Diametric magnet
    │    ↓    │  (N-S across diameter)
    │    S    │
    └─────────┘
         │
      Motor shaft
```

**Critical Points:**
- Gap: 0.5-3mm from sensor surface
- Alignment: Magnet center aligned with sensor center
- Rotation: Must be centered on shaft (no wobble)
- Clearance: Magnet should not contact sensor

### Verification
Check AGC (Automatic Gain Control) value:
- AGC = 0: No magnet detected
- AGC = 128 (typical): Good positioning
- AGC = 255: Magnet too strong or too close

## I2C Multiplexer (For 4 Encoders)

### TCA9548A Wiring
```
TCA9548A              SKR Pico P9
────────              ───────────
VCC         →         3.3V (Pin 1)
GND         →         GND (Pin 2)
SDA         →         GPIO0 (Pin 3)
SCL         →         GPIO1 (Pin 4)
A0, A1, A2  →         GND (address 0x70)

Channel Outputs:
SD0/SC0     →         AS5600 #1 (Needle)
SD1/SC1     →         AS5600 #2 (Hook)
SD2/SC2     →         AS5600 #3 (Takeup)
SD3/SC3     →         AS5600 #4 (Feed)
```

### Why Multiplexer?
All AS5600 modules use the same I2C address (0x36). The multiplexer allows selecting which encoder to communicate with.

## Wiring Tips

### Cable Management
- Keep I2C wires short (<30cm ideal, <1m max)
- Twist SDA/SCL wires together to reduce noise
- Route away from motor power wires
- Use shielded cable in noisy environments

### Common Issues
1. **No I2C communication:**
   - Check SDA/SCL not swapped
   - Verify 3.3V power present
   - Check ground connection

2. **Intermittent readings:**
   - Check for loose connections
   - Verify cable length reasonable
   - Test for EMI from motors

3. **Wrong values:**
   - Verify magnet polarity (DIR pin)
   - Check magnet alignment
   - Ensure magnet not loose

## Testing Wiring

### Voltage Check
```bash
# With multimeter:
# - AS5600 VCC pin: Should read 3.3V
# - AS5600 GND pin: Should read 0V
# - No shorts between VCC and GND
```

### I2C Bus Scan (If available)
```bash
# From Raspberry Pi (if I2C exposed):
i2cdetect -y 0

# Should show device at 0x36
```

### Klipper Test
```gcode
# In Mainsail console:
QUERY_AS5600 SENSOR=e0_encoder

# Should return angle reading
# If error: Check logs for I2C errors
```

## Pin Reference Tables

### SKR Pico GPIO Assignments
| Function | GPIO | Physical Pin | Notes |
|----------|------|--------------|-------|
| I2C0 SDA | GPIO0 | P9-3 | Hardware I2C |
| I2C0 SCL | GPIO1 | P9-4 | Hardware I2C |
| E0 Step | GPIO11 | E0 header | Built-in driver |
| E0 Dir | GPIO10 | E0 header | Built-in driver |
| E0 Enable | GPIO12 | E0 header | Built-in driver |

### AS5600 Registers (For Reference)
| Register | Address | Description |
|----------|---------|-------------|
| ZMCO | 0x00 | Programming count |
| ZPOS | 0x01-0x02 | Zero position |
| MPOS | 0x03-0x04 | Max position |
| MANG | 0x05-0x06 | Max angle |
| CONF | 0x07-0x08 | Configuration |
| RAW_ANGLE | 0x0C-0x0D | Unscaled angle (12-bit) |
| ANGLE | 0x0E-0x0F | Scaled angle (12-bit) |
| STATUS | 0x0B | Magnet detect status |
| AGC | 0x1A | Automatic gain |
| MAGNITUDE | 0x1B-0x1C | Magnetic field strength |

## Power Considerations

### Current Draw
- **AS5600:** <10 mA typical
- **4x AS5600:** <40 mA total
- **SKR Pico 3.3V output:** 500 mA typical
- **Margin:** Plenty of headroom

### Power Sequencing
1. SKR Pico powers up
2. 3.3V rail stabilizes
3. AS5600 initializes (~50ms)
4. Klipper starts reading

No special sequencing needed.

## Mechanical Mounting

### AS5600 Module
- Mount securely (no vibration)
- Maintain precise gap to magnet
- Allow for thermal expansion
- Consider enclosure for protection

### Magnet
- Press-fit to shaft or use setscrew
- Verify no wobble during rotation
- Balance if high-speed operation
- Use thread-lock on setscrew

## Troubleshooting Matrix

| Symptom | Check | Solution |
|---------|-------|----------|
| No reading | Wiring | Verify SDA/SCL, power, ground |
| | Magnet | Check magnet present, <3mm gap |
| | Config | Verify i2c_bus, i2c_address |
| Jittery | Magnet | Center on shaft, check gap |
| | EMI | Route cables away from motors |
| | Mechanical | Secure mounting, no vibration |
| Wrong direction | Config | Flip dir_pin in motor config |
| | Magnet | Check DIR pin grounded |
| Intermittent | Cables | Check for loose connections |
| | Temperature | Verify not overheating |
| | Power | Check voltage stable |

## Multi-Motor Wiring Diagram

```
                SKR Pico
                   │
           ┌───────┴───────┐
           │    P9 (I2C)   │
           └───────┬───────┘
                   │
         ┌─────────▼─────────┐
         │  TCA9548A (0x70)  │
         └─┬────┬────┬────┬──┘
           │    │    │    │
       Ch0 │ Ch1│ Ch2│ Ch3│
           │    │    │    │
      ┌────▼┐ ┌─▼──┐┌─▼──┐┌▼───┐
      │AS5600│AS5600│AS5600│AS5600│
      │Needle│Hook  │Takup│Feed  │
      └──────┘└─────┘└────┘└─────┘
         │      │      │      │
      ┌──▼──┐┌──▼──┐┌─▼───┐┌▼────┐
      │Motor││Motor││Motor││Motor│
      │  E0 ││  E1 ││  E2 ││  E3 │
      └─────┘└─────┘└─────┘└─────┘
```

## Bill of Materials

### Current (1 Motor)
- [x] 1× SKR Pico board
- [x] 1× AS5600 module (Tinytronics or similar)
- [x] 1× Diametric magnet (6mm × 2mm)
- [x] 1× NEMA17 stepper motor
- [x] 4× Dupont wires (for I2C connection)

### For 4 Motors
- [ ] 1× TCA9548A I2C multiplexer
- [ ] 3× Additional AS5600 modules
- [ ] 3× Additional diametric magnets
- [ ] 3× Additional NEMA17 steppers
- [ ] 12× Additional Dupont wires

### Optional
- [ ] Shielded I2C cable
- [ ] Connector housings
- [ ] Heat shrink tubing
- [ ] Cable ties
- [ ] Mounting hardware
