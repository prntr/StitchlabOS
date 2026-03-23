# Foot Pedal — Fly-by-Wire Sewing Control

> In sewing mode, the needle is driven by a foot pedal. The pedal signal is transmitted wirelessly via the ESP32-C3 dongle (the same dongle used for joystick control in embroidery mode). This document covers the hardware interface, protocol extension, and motor speed mapping.

## Architecture

```
┌───────────┐    ┌───────────────────┐    ┌──────────────┐    ┌───────────┐
│ Foot Pedal│    │ StitchLab         │    │ StitchLab    │    │ Raspberry │
│ (analog)  │───▶│ Controller (ESP32)│═══▶│ Dongle       │───▶│ Pi        │
│           │    │ ADC input         │    │ USB serial   │    │ live_jogd │
│ 0-3.3V   │    │ ESP-NOW TX        │    │ ESP-NOW RX   │    │ → Klipper │
└───────────┘    └───────────────────┘    └──────────────┘    └───────────┘
                                                                    │
                                                               ┌────▼────┐
                                                               │ SKR Pico│
                                                               │ Z motor │
                                                               │ (needle)│
                                                               └─────────┘
```

## What Already Exists

The dongle/controller system is already built for joystick control:

| Component | Status | Notes |
|-----------|--------|-------|
| ESP32-C3 dongle firmware | Done | USB serial + ESP-NOW receiver |
| StitchLab Controller firmware | Done | Joystick + buttons + ESP-NOW transmitter |
| `live_jogd.py` daemon | Done | Serial → Moonraker bridge, WebSocket :7150 |
| Controller WebSocket plugin | Done | `mainsail/src/plugins/controllerWebSocket.ts` |
| Controller Vuex store | Done | `mainsail/src/store/server/controller/` |

## What Needs to Be Built

### 1. Controller Firmware: Pedal ADC Input

The StitchLab Controller (ESP32) needs a new input channel for the pedal.

**Hardware connection:**
```
Foot Pedal                   ESP32 Controller
──────────                   ────────────────
Wiper (signal) ──────────▶   ADC pin (GPIO<N>)
VCC            ──────────▶   3.3V
GND            ──────────▶   GND
```

**Pedal types:**
| Type | Signal | Notes |
|------|--------|-------|
| Resistive (most common) | Variable resistance → voltage divider | 0V=idle, 3.3V=full |
| Hall effect | Analog voltage proportional to travel | More linear, more expensive |
| Switch (basic) | On/off only | No speed control, not recommended |

**ADC reading in controller firmware:**
```c
// New field in the ESP-NOW transmit frame
typedef struct {
    int16_t vx;          // Joystick X (existing)
    int16_t vy;          // Joystick Y (existing)
    uint8_t deadman;     // Deadman switch (existing)
    uint8_t buttons;     // Button bitmask (existing)
    uint16_t pedal;      // NEW: foot pedal 0-4095 (12-bit ADC)
    uint8_t pedal_dir;   // NEW: 0=forward, 1=reverse
} controller_frame_t;
```

### 2. Dongle Firmware: Forward Pedal Data

The dongle receives ESP-NOW frames and forwards to Pi via USB serial. The existing binary protocol needs extension:

```
Existing frame: [0xAA] [type] [vx_h] [vx_l] [vy_h] [vy_l] [deadman] [buttons] [checksum]
Extended frame: [0xAA] [type] [vx_h] [vx_l] [vy_h] [vy_l] [deadman] [buttons] [pedal_h] [pedal_l] [pedal_dir] [checksum]
```

**Alternative:** New message type for pedal-only updates (if pedal rate differs from joystick rate):
```
Pedal frame:    [0xAA] [0x02] [pedal_h] [pedal_l] [pedal_dir] [checksum]
```

### 3. live_jogd.py: Pedal → Motor Speed Mapping

`live_jogd.py` already reads serial frames and sends Moonraker commands. Add pedal handling:

```python
# In live_jogd.py — new handler

class PedalController:
    def __init__(self, moonraker_url):
        self.moonraker = moonraker_url
        self.dead_zone = 50         # ADC counts (out of 4095)
        self.max_spm = 200          # Maximum stitches per minute
        self.min_spm = 30           # Minimum (slowest useful speed)
        self.current_speed = 0
        self.direction = 1          # 1=forward, -1=reverse
        self.active = False

    def update(self, pedal_value, pedal_dir):
        """Called on each pedal frame from dongle"""
        if pedal_value < self.dead_zone:
            if self.active:
                self.stop_needle()
            return

        # Map ADC to speed (non-linear for fine control at low speeds)
        normalized = (pedal_value - self.dead_zone) / (4095 - self.dead_zone)
        # Quadratic curve: gentle start, strong finish
        speed_factor = normalized ** 2
        target_spm = self.min_spm + (self.max_spm - self.min_spm) * speed_factor

        self.direction = -1 if pedal_dir else 1
        self.set_needle_speed(target_spm)

    def set_needle_speed(self, spm):
        """Convert SPM to Z velocity and send to Klipper"""
        # 1 stitch = 5mm Z = 1 revolution
        # SPM → mm/min → mm/s
        mm_per_min = spm * 5.0
        mm_per_sec = mm_per_min / 60.0

        # Use MANUAL_STEPPER for continuous velocity
        # Or G1 with feedrate for discrete moves
        gcode = f"G91\nG1 Z{5.0 * self.direction} F{mm_per_min}\nG90"
        self.send_gcode(gcode)
        self.active = True

    def stop_needle(self):
        """Stop needle movement"""
        self.send_gcode("M400")  # Wait for moves to finish
        self.active = False
```

### 4. Speed Curve

The pedal-to-speed mapping uses a quadratic curve for fine control at low speeds:

```
Speed (SPM)
200 ┤                                          ╱
    │                                        ╱
    │                                      ╱
150 ┤                                   ╱
    │                                ╱
    │                            ╱
100 ┤                        ╱
    │                    ╱
    │               ╱╱
 50 ┤          ╱╱
    │     ╱╱
 30 ┤╱╱
    │
  0 ┤─dead─┬──────┬──────┬──────┬──────┤
    0%    10%    25%    50%    75%   100%
                 Pedal Travel
```

### 5. WebSocket Extension for UI

`live_jogd.py` already broadcasts joystick state over WebSocket. Add pedal state:

```json
{
    "type": "pedal_update",
    "pedal_value": 2048,
    "pedal_percent": 50,
    "pedal_direction": "forward",
    "needle_spm": 95,
    "active": true
}
```

The Mainsail store can receive this via the existing `controllerWebSocket.ts` plugin.

### 6. Frontend: SewingControlPanel

New Vue component for sewing mode:

```
┌─────────────────────────────────────┐
│  SEWING MODE                   🟢   │
├─────────────────────────────────────┤
│                                     │
│  Pedal: ████████░░░░░░░░░  48%     │
│  Speed: 95 SPM                      │
│  Direction: FORWARD ▶               │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  Stitch Counter:  1,247    │    │
│  │  [Reset]                    │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  Needle: ● UP (5°)         │    │  ← if encoder present
│  │  ◐ ○ ● ○ ◑                 │    │  ← visual indicator
│  └─────────────────────────────┘    │
│                                     │
│  [Needle Toggle]  [Single Stitch]   │
│                                     │
│  Max Speed: [━━━━━━━━━━○━━] 200 SPM│
│                                     │
└─────────────────────────────────────┘
```

## Safety Considerations

### Pedal Safety

| Concern | Mitigation |
|---------|------------|
| Pedal stuck at full speed | Watchdog in live_jogd — if no pedal update for 500ms, stop needle |
| Mode switch with pedal pressed | `_GANTRY_ATTACHED` macro checks pedal=0 before enabling embroidery |
| Runaway motor | Klipper velocity limits enforced in `printer.cfg` |
| Communication loss (dongle disconnect) | live_jogd detects USB disconnect → sends stop command |

### Latency Budget

```
Pedal press → ADC sample:           ~1ms (ESP32 ADC)
ESP-NOW transmit:                    ~5ms
USB serial forwarding:               ~2ms
live_jogd processing:                ~1ms
Moonraker → Klipper:                ~5ms
Klipper → stepper:                   ~1ms
─────────────────────────────────────────
Total pedal-to-motor latency:       ~15ms
```

This is well within the 50ms threshold for "responsive" feel.

## Configuration

### live_jogd Config (New Section)

```ini
# ~/printer_data/config/live_jogd.conf (or equivalent)
[pedal]
enabled = true
dead_zone = 50          # ADC counts (0-4095)
min_spm = 30            # Minimum speed when pedal barely pressed
max_spm = 200           # Maximum speed at full pedal
curve = quadratic       # linear | quadratic | custom
watchdog_timeout = 500  # ms — stop if no pedal update
```

### printer.cfg Additions for Sewing Mode

```ini
# Z velocity limits for sewing (mm/s)
# 200 SPM = 200 * 5mm / 60s = 16.7 mm/s
[printer]
max_z_velocity: 20      # Allows up to 240 SPM
max_z_accel: 100        # Smooth start/stop
```

## Testing Checklist

- [ ] Pedal at 0% → no needle movement
- [ ] Pedal at 50% → ~95 SPM
- [ ] Pedal at 100% → ~200 SPM (or configured max)
- [ ] Pedal release → needle stops within 1 stitch
- [ ] Reverse direction works
- [ ] Dongle disconnect → needle stops immediately
- [ ] UI shows pedal percentage and SPM in real-time
- [ ] Mode switch blocked while pedal is pressed
- [ ] Max SPM slider adjustable from UI
- [ ] Stitch counter increments correctly
