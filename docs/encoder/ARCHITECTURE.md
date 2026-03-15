# System Architecture

> **Scope:** This document describes the encoder architecture developed on stitchlab04. For StitchLAB, only the **single handwheel encoder** (Phase 1) is relevant. Multi-motor phases (3+) apply to StitchLABsim/stitchlabprodev only.

## StitchLAB Handwheel Encoder — Primary Use Case

Adding a single AS5600 encoder to the handwheel enables:

| Mode | How It Works |
|------|--------------|
| **Synchronized Embroidery** | XY movement waits for encoder to confirm needle UP (0°/360°) before moving hoop |
| **Free-Motion Sewing** | Foot pedal drives needle; encoder reports position to UI |
| **Hybrid Mode** | Switch between automated and manual without reconfiguration |

---

## Current Implementation (Phase 1)

### Single Encoder, Python-Based Control

```
┌─────────────────────────────────────────┐
│  Raspberry Pi                           │
│  ┌───────────────────────────────────┐  │
│  │ Klipper (Python)                  │  │
│  │  - as5600.py module               │  │
│  │  - Timer: 20-100 Hz               │  │
│  │  - I2C read via reactor           │  │
│  │  - Position tracking              │  │
│  │  - Control logic (optional)       │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
              │ USB Serial
              ↓
┌─────────────────────────────────────────┐
│  SKR Pico (RP2040)                      │
│  ┌──────────────┐    ┌────────────────┐│
│  │ I2C Bus      │    │ Stepper Driver ││
│  │ (i2c0a)      │    │                ││
│  │ GPIO0/GPIO1  │    │ E0 Motor       ││
│  │              │    │ GPIO11/10/12   ││
│  │  AS5600 ◄────┼────┤                ││
│  │  (0x36)      │    └────────────────┘│
│  └──────────────┘                       │
└─────────────────────────────────────────┘
```

**Characteristics:**
- ✅ Simple, easy to develop/debug
- ✅ No firmware compilation needed
- ⚠ Limited to ~100 Hz (10ms update rate)
- ⚠ Variable latency (reactor overhead)
- ❌ Cannot reliably support >300 SPM

## Future Implementation (Phase 2)

### MCU-Based Sampling (Required for Production Speed)

```
┌─────────────────────────────────────────┐
│  Raspberry Pi                           │
│  ┌───────────────────────────────────┐  │
│  │ Klipper (Python)                  │  │
│  │  - High-level coordination        │  │
│  │  - Stitch sequencing              │  │
│  │  - Parameter configuration        │  │
│  │  - Status monitoring (10-50 Hz)   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
              │ USB (commands + status)
              ↓
┌─────────────────────────────────────────┐
│  SKR Pico (RP2040)                      │
│  ┌───────────────────────────────────┐  │
│  │ Hardware Timer (1 kHz)            │  │
│  │  - Read encoder via DMA           │  │
│  │  - Track position                 │  │
│  │  - Calculate PID                  │  │
│  │  - Direct stepper control         │  │
│  │  - Bulk status to Python          │  │
│  └───────────────────────────────────┘  │
│  ┌──────────────┐    ┌────────────────┐│
│  │ I2C Bus      │    │ Stepper Driver ││
│  │ (DMA)        │    │ (Direct)       ││
│  │              │    │                ││
│  │  AS5600 ◄────┼────┤ E0 Motor       ││
│  │  (0x36)      │    │                ││
│  └──────────────┘    └────────────────┘│
└─────────────────────────────────────────┘
```

**Characteristics:**
- ✅ Deterministic real-time control
- ✅ 500-2000 Hz sampling
- ✅ <1ms position correction latency
- ✅ Can support 600-1200 SPM
- ⚠ Requires firmware development (C)
- ⚠ More complex debugging

## Multi-Motor Architecture (Phase 3) — StitchLABsim Only

> **Note:** This section applies to the multi-motor simulator project only.

### 4 Motors with I2C Multiplexer

```
┌─────────────────────────────────────────────────────────┐
│  SKR Pico                                                │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ I2C Mux (TCA9548A @ 0x70)                         │  │
│  │  ┌─────────┬─────────┬─────────┬─────────┐        │  │
│  │  │ Ch0     │ Ch1     │ Ch2     │ Ch3     │        │  │
│  │  │ AS5600  │ AS5600  │ AS5600  │ AS5600  │        │  │
│  │  │ Needle  │ Hook    │ Takeup  │ Feed    │        │  │
│  │  │ (0x36)  │ (0x36)  │ (0x36)  │ (0x36)  │        │  │
│  │  └────┬────┴────┬────┴────┬────┴────┬────┘        │  │
│  └───────┼─────────┼─────────┼─────────┼─────────────┘  │
│          │         │         │         │                │
│  ┌───────▼─────────▼─────────▼─────────▼─────────────┐  │
│  │ Stepper Drivers                                    │  │
│  │  E0: Needle   E1: Hook   E2: Takeup   E3: Feed    │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Coordination Options:**

### Option A: Python Sequencer (Easier, <300 SPM)
```python
def execute_stitch():
    # Step 1: Needle down
    set_target(needle, 180°)
    wait_position(needle, 180°)
    
    # Step 2: Hook rotates
    set_target(hook, 360°)
    wait_position(hook, 360°)
    
    # Step 3: Needle up
    set_target(needle, 0°)
    wait_position(needle, 0°)
    
    # Step 4: Takeup pull
    set_target(takeup, 90°)
    # etc...
```

**Pros:** Easy to program, flexible, no firmware changes  
**Cons:** 10-50ms latency between steps, limited to 300 SPM

### Option B: MCU State Machine (Harder, >600 SPM)
```c
// Firmware coordination
typedef enum {
    STATE_NEEDLE_DOWN,
    STATE_HOOK_CATCH,
    STATE_NEEDLE_UP,
    STATE_TAKEUP_PULL,
    STATE_FEED_ADVANCE
} StitchState;

// All 4 encoders sampled at 1 kHz
// State transitions in <1ms
// Deterministic timing
```

**Pros:** <1ms state transitions, supports 1200 SPM  
**Cons:** Requires firmware, less flexible

## Resource Analysis

### Single SKR Pico Capacity (4 Encoders + Closed-Loop)

**CPU Load @ 1 kHz MCU Sampling:**
```
Encoder reading (4x):      440 µs / 1000 µs  = 44%
Stepper pulse generation:                      10%
USB communication:                              5%
Other Klipper overhead:                        10%
────────────────────────────────────────────────
TOTAL:                                         69%
MARGIN:                                        31%
```

**Memory Usage:**
```
Encoder structs (4x):        5 KB
Klipper base:               50 KB
Stepper queues:             20 KB
────────────────────────────────
TOTAL:                      75 KB / 264 KB = 28%
MARGIN:                    189 KB (72%)
```

**Conclusion:** ✅ Single SKR Pico can handle all 4 motors with closed-loop control

## Communication Protocol

### Python → MCU Commands (Klipper Standard)
```python
# Register commands
cmd_config = mcu.lookup_command(
    "encoder_monitor_setup oid=%c i2c_oid=%c sample_ticks=%u")

cmd_set_target = mcu.lookup_command(
    "encoder_monitor_set_target oid=%c target=%i")

# Send commands
cmd_config.send([oid, i2c_oid, ticks])
cmd_set_target.send([oid, target_counts])
```

### MCU → Python Responses
```c
// Bulk status updates (every 100ms)
sendf("encoder_status oid=%c position=%i velocity=%i error=%i",
      oid, position, velocity, error);
```

### This is how ALL Klipper modules work:
- Stepper motors
- Temperature sensors
- Endstops
- TMC drivers
- etc.

## Data Flow

### Position Tracking (Real-time)
```
AS5600 registers
    ↓ (I2C read)
Raw angle (12-bit)
    ↓ (wraparound detection)
Revolution count
    ↓ (calculation)
Absolute position (degrees)
    ↓ (conversion)
Linear position (mm)
```

### Control Loop (Hold Mode)
```
Target position (setpoint)
    ↓
Current position (from encoder)
    ↓
Error = target - current
    ↓
PID calculation
    ↓
Correction move (mm)
    ↓
Stepper command
    ↓
Motor moves
    ↓
Position changes
    ↓
(loop continues)
```

## Performance Requirements by Speed

| Target SPM | Motor RPM | Angular Vel | Min Sample Rate | Implementation |
|------------|-----------|-------------|-----------------|----------------|
| 100 | 500 | 3000°/s | 50 Hz | ✅ Python OK |
| 200 | 1000 | 6000°/s | 100 Hz | ✅ Python OK |
| 300 | 1500 | 9000°/s | 200 Hz | ⚠ Python marginal |
| 400 | 2000 | 12000°/s | 500 Hz | ❌ Need MCU firmware |
| 600 | 3000 | 18000°/s | 1000 Hz | ❌ Need MCU firmware |
| 1200 | 6000 | 36000°/s | 2000 Hz | ❌ Need MCU firmware |

**Rule of thumb:** Sample rate should be ≥ (angular velocity / 180°)
- This ensures max 180° travel between samples
- Allows reliable position tracking and control

## Migration Path

### Phase 1: Single Motor, Python Control ✅ **CURRENT**
- Time: 2 days (complete)
- Outcome: Proof of concept, working encoder
- Speed: Up to 200 SPM

### Phase 2: Tune and Characterize ← **NEXT**
- Time: 1 week
- Tasks:
  - [ ] Test position hold at various speeds
  - [ ] Optimize PID parameters
  - [ ] Measure actual sample rate limits
  - [ ] Document performance envelope

### Phase 3: StitchLAB Integration ← **NEXT FOR STITCHLAB**
- Tasks:
  - [ ] Mount encoder on StitchLAB handwheel
  - [ ] Calibrate needle UP/DOWN angles
  - [ ] Create WAIT_NEEDLE_UP macro
  - [ ] Test synchronized embroidery
  - [ ] Design hybrid mode with foot pedal

---

### Phases 4-6: StitchLABsim Only (Multi-Motor)

> **Note:** These phases apply to the simulator project, not the main StitchLAB embroidery machine.

### Phase 4: Add 3 More Encoders (StitchLABsim)
- Tasks:
  - [ ] Install I2C multiplexer
  - [ ] Wire 3 more AS5600 modules
  - [ ] Configure all 4 in Klipper
  - [ ] Test simultaneous monitoring

### Phase 5: Python Multi-Motor Coordination (StitchLABsim)
- Tasks:
  - [ ] Implement stitch state machine (Python)
  - [ ] Coordinate all 4 motors
  - [ ] Test basic stitch patterns
  - [ ] Validate up to 300 SPM

### Phase 6: MCU Firmware (StitchLABsim, If Needed)
- Tasks:
  - [ ] Create firmware timer module (C)
  - [ ] Implement DMA I2C reading
  - [ ] Port PID control to firmware
  - [ ] Add bulk status reporting
  - [ ] Test 500-1000 Hz sampling
  - [ ] Validate 600+ SPM operation

## Key Design Principles

1. **Start Simple, Optimize Later**
   - Python first, firmware if needed
   - Proves concept quickly
   - Clear upgrade path

2. **Non-Blocking Everything**
   - Critical for Klipper stability
   - No busy-wait loops
   - Reactor-friendly design

3. **Proven Patterns**
   - Based on existing Klipper modules
   - Standard I2C usage
   - Follow mpu9250.py example

4. **Incremental Development**
   - 1 motor → 4 motors
   - Python → MCU firmware
   - Monitor → Control
   - Slow → Fast

5. **Measure Before Optimizing**
   - Characterize actual performance
   - Identify real bottlenecks
   - Don't over-engineer prematurely

## Technical Debt / Future Work

- [ ] Add I and D terms to PID (currently P-only)
- [ ] Implement velocity feedforward
- [ ] Add trajectory planning
- [ ] Support for different motor types
- [ ] Auto-tuning of PID parameters
- [ ] Advanced diagnostics and logging
- [ ] Web UI for real-time visualization
- [ ] Configuration wizard
