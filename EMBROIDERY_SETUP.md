# StitchLab Embroidery Machine - Mainsail Integration

This document describes the Mainsail modifications and integration with the StitchLab live control system for a DIY CNC embroidery machine.

## System Overview

The StitchLab system consists of:

1. **Mainsail Frontend** - Modified Vue.js UI with embroidery-specific panels
2. **Klipper/Moonraker** - Motion control and API backend
3. **StitchLabController** - Wireless handheld controller (ESP32-S3 + LVGL)
4. **StitchLabDongle** - USB bridge (ESP32-C3) connecting controller to Pi
5. **live_jogd** - Python daemon bridging dongle to Moonraker

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MAINSAIL FRONTEND                                │
│                                                                          │
│  ┌──────────────────────────┐    ┌────────────────────────────────────┐ │
│  │  EmbroideryControlPanel  │    │  TheControllerMenu                 │ │
│  │                          │    │                                    │ │
│  │  • Needle Toggle         │    │  • Dongle status                   │ │
│  │  • Stitch / Lock Stitch  │    │  • Controller pairing              │ │
│  │  • Zero Position         │    │  • WiFi controls                   │ │
│  └────────────┬─────────────┘    └─────────────────┬──────────────────┘ │
│               │ G-code via Moonraker               │ WebSocket :7150    │
└───────────────┼────────────────────────────────────┼────────────────────┘
                │                                    │ (not yet connected)
                ▼                                    ▼
┌───────────────────────────┐        ┌────────────────────────────────────┐
│  Moonraker (Port 7125)    │◄───────│  live_jogd.py                      │
│                           │  HTTP  │                                    │
│  Klipper                  │        │  USB Serial ↔ Binary Protocol     │
│  embroidery_macros.cfg    │        └─────────────────┬──────────────────┘
└───────────────────────────┘                          │
                                                       ▼
                                     ┌────────────────────────────────────┐
                                     │  StitchLabDongle (ESP32-C3)        │
                                     │                                    │
                                     │  ESP-NOW ↔ StitchLabController     │
                                     └────────────────────────────────────┘
```

For full live control system documentation, see:
**KlipperLiveControl/project.md** (in this workspace)

Canonical StitchLAB docs entrypoint:
- `docs/README.md`

---

## Machine Specifications

- **XY Gantry**: CoreXY or similar (like Prusa Mini / Bambu A1 Mini)
- **Z-Axis**: Controls handwheel/needle position
- **Stitch Length**: 5mm Z travel = 1 full rotation = 1 stitch
- **Z Endstop**: Triggers when needle is at highest position (UP)
- **Operation**: During stitching, Z only moves in positive direction

### Needle Position Model

```
1 full handwheel rotation = 5mm Z travel = 1 complete stitch

Z=0.0mm    → Needle UP (0°)     - After homing
Z=2.5mm    → Needle DOWN (180°) - Needle in fabric
Z=5.0mm    → Needle UP (360°)   - 1 stitch complete
Z=7.5mm    → Needle DOWN
Z=10.0mm   → Needle UP          - 2 stitches complete
...
```

---

## Mainsail Components

### 1. EmbroideryControlPanel

**Location**: `src/components/panels/EmbroideryControlPanel.vue`

A dashboard panel for manual needle control:

| Button | Macro | Description |
|--------|-------|-------------|
| Needle Toggle | `NEEDLE_TOGGLE` | Toggle UP/DOWN for maintenance (restores Z with G92) |
| Stitch | `STITCH` | One complete rotation, no logical Z change |
| Lock Stitch | `LOCK_STITCH` | 3 rapid stitches to secure thread |
| Zero Position | `ZERO_NEEDLE_POSITION` | Set current position as Z=0 |

The panel tracks physical needle state locally because macros use `G92` to hide physical movement from the logical Z position.

### 2. TheControllerMenu

**Location**: `src/components/TheControllerMenu.vue`

A toolbar menu (gamepad icon) for wireless controller management:

- Dongle connection status
- Paired controller list
- WiFi on/off toggle
- Pairing mode toggle
- Service start/stop/restart (via Moonraker)

**Note**: This UI expects a WebSocket server on port 7150, which is not yet implemented in live_jogd. Currently, dongle control is CLI-only via `dongle_api.py`.

### 3. Controller Store Module

**Location**: `src/store/server/controller/`

Vuex store for controller state:

```typescript
interface ServerControllerState {
    dongle_connected: boolean
    dongle_info: ControllerDongleInfo
    dongle_status: ControllerDongleStatus
    peers: ControllerPeerInfo[]
    joystick: ControllerJoystickState
    websocket_connected: boolean
}
```

### 4. WebSocket Client

**Location**: `src/plugins/controllerWebSocket.ts`

Client for connecting to live_jogd WebSocket server (port 7150).
Features auto-reconnect with exponential backoff.

---

## Klipper Macros

**Source of truth**: `stitchlabos/config/klipper/embroidery_macros.cfg`

### Core Macros

| Macro | Parameters | Description |
|-------|------------|-------------|
| `NEEDLE_TOGGLE` | - | Toggle needle UP↔DOWN, restore Z with G92 |
| `STITCH` | - | One rotation (5mm), restore logical Z |
| `LOCK_STITCH` | `COUNT=3` | Multiple stitches to secure thread |
| `ZERO_NEEDLE_POSITION` | - | Move to UP, set Z=0 |
| `EMBROIDERY_HOME` | - | Home XY, then Z, center XY |
| `NEEDLE_ADJUST` | `AMOUNT=0.1` | Fine-tune needle ±X mm |
| `EMBROIDERY_STATUS` | - | Display position and stitch count |

### Installation

1. Copy macros to Klipper config:
   ```bash
   cp stitchlabos/config/klipper/embroidery_macros.cfg ~/printer_data/config/
   ```

2. Add to `printer.cfg`:
   ```ini
   [include embroidery_macros.cfg]
   ```

3. Restart Klipper:
   ```bash
   sudo systemctl restart klipper
   ```

---

## Live Control System

The wireless controller system is documented in the KlipperLiveControl project.

### Quick Reference

**Dongle CLI** (`live_jogd/dongle_api.py`):
```bash
# Query status
python dongle_api.py --query status --watch 0.5

# Pairing workflow
python dongle_api.py --clear-peers
python dongle_api.py --pairing on
# (Power on controller, move joystick)
python dongle_api.py --pairing off

# WiFi control
python dongle_api.py --wifi off --save
python dongle_api.py --wifi on
```

**Service management**:
```bash
sudo systemctl status live_jogd
sudo systemctl restart live_jogd
journalctl -u live_jogd -f
```

### Controller Button Mapping

| Button | Action |
|--------|--------|
| Joystick | XY jog movement |
| A (held) | Z+ step |
| Y (held) | Z- step |
| B | STITCH macro |
| X | HOME XYZ |
| SELECT | Emergency Stop |
| Deadman | Required for XY movement |

---

## Installation

### Prerequisites

- Raspberry Pi with Klipper/Moonraker/Mainsail
- StitchLabDongle (ESP32-C3) connected via USB
- StitchLabController (ESP32-S3) paired with dongle

### 1. Mainsail Build

```bash
cd mainsail
npm ci
npm run build
# Deploy dist/ to /home/pi/mainsail/ or your webroot
```

### 2. Klipper Macros

```bash
cp stitchlabos/config/klipper/embroidery_macros.cfg ~/printer_data/config/
echo '[include embroidery_macros.cfg]' >> ~/printer_data/config/printer.cfg
sudo systemctl restart klipper
```

### 3. live_jogd Service

```bash
cd /path/to/KlipperLiveControl/live_jogd

# udev rule for stable device path
sudo cp 99-stitchlab-dongle.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules

# Python dependencies
pip install -r requirements.txt

# systemd service
sudo cp live_jogd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable live_jogd
sudo systemctl start live_jogd
```

### 4. Moonraker CORS (if needed)

```ini
# moonraker.conf
[authorization]
cors_domains:
    *//localhost:8080
    *//stitchlabdev.local
```

---

## Dashboard Configuration

1. Open Mainsail: `http://stitchlabdev.local`
2. Go to **Settings > Dashboard**
3. Enable "Embroidery Control" panel
4. Position as desired for each layout (Mobile/Tablet/Desktop)

---

## Usage Workflow

### Initial Setup

1. Power on the machine
2. Run `EMBROIDERY_HOME` to home all axes
3. Power on the controller (if using wireless control)
4. Verify dongle LED is green, then blue flash on connection

### Manual Control (Web UI)

- Use **Needle Toggle** for threading/maintenance
- Use **Stitch** to test needle movement
- Use **Lock Stitch** to secure thread ends
- Use **Zero Position** to reset stitch counter

### Wireless Control

- Hold **Deadman** and use **Joystick** to move XY
- Press **B** for stitch
- Press **X** to home
- Position display updates at ~10 Hz

---

## Troubleshooting

### Panel Not Showing
- Verify Mainsail was rebuilt with embroidery components
- Check browser console for errors (F12)
- Enable panel in Dashboard settings

### Controller Not Connecting
```bash
# Check dongle device
ls -la /dev/stitchlab-dongle

# Check live_jogd status
sudo systemctl status live_jogd
journalctl -u live_jogd -f

# Query dongle directly
python dongle_api.py --query status
```

### Macros Not Working
```bash
# Verify macros loaded
EMBROIDERY_STATUS

# Check Klipper logs
journalctl -u klipper -f
```

### WebSocket Not Connecting (TheControllerMenu)
This is expected - WebSocket server on port 7150 is not yet implemented.
Use CLI tools or physical controller for dongle management.

---

## Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| EmbroideryControlPanel | ✅ Complete | Works via Moonraker |
| Klipper Macros | ✅ Complete | All macros functional |
| live_jogd daemon | ✅ Complete | Serial + HTTP working |
| StitchLabDongle | ✅ Complete | ESP-NOW + Serial API |
| StitchLabController | ✅ Complete | LVGL UI + joystick |
| TheControllerMenu UI | ⚠️ Partial | UI done, needs WebSocket backend |
| Browser ↔ live_jogd | ❌ Missing | WebSocket :7150 not implemented |

---

## Related Documentation

- [KlipperLiveControl/project.md](../../../PlatformIO/Projects/KlipperLiveControl/project.md) - Full protocol and hardware docs
- [Mainsail Docs](https://docs.mainsail.xyz) - Official Mainsail documentation
- [Klipper Docs](https://www.klipper3d.org) - Klipper configuration reference
