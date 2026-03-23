# Configuration & Ports

> Single source of truth for all ports, endpoints, and service configuration.

## Ports & Endpoints

| Port | Service | Where Defined | Dev | Pi | Notes |
|------|---------|---------------|:---:|:--:|-------|
| 7125 | Moonraker API | `moonraker.conf` / `docker-compose.yml` | Y | Y | HTTP + WebSocket |
| 8080 | Vite dev server | `mainsail/vite.config.ts` | Y | - | Dev only |
| 8110 | Webcam simulator | `virtual-klipper-printer/docker-compose.yml` | Y | - | MJPG stream |
| 3000 | TurtleStitch offline | `/etc/nginx/sites-available/turtlestitch` | - | Y | Nginx serves static |
| 7150 | live_jogd WebSocket | UI expects it | - | - | **Not implemented** |

## Klipper Macros

Source: `stitchlabos-config/printer_data/config/embroidery_macros.cfg`

| Macro | Parameters | Description |
|-------|------------|-------------|
| `NEEDLE_TOGGLE` | - | Toggle UP/DOWN, restore Z with G92 |
| `STITCH` | - | One rotation (5mm), restore logical Z |
| `LOCK_STITCH` | `COUNT=3` | Multiple stitches to secure thread |
| `ZERO_NEEDLE_POSITION` | - | Move to UP, set Z=0 |
| `EMBROIDERY_HOME` | - | Home XY, then Z, center XY |
| `NEEDLE_ADJUST` | `AMOUNT=0.1` | Fine-tune needle position |
| `EMBROIDERY_STATUS` | - | Display position and stitch count |

### Hybrid Mode Macros (Planned)

These macros will be added for the StitchLAB Hybrid machine:

| Macro | Parameters | Description |
|-------|------------|-------------|
| `_GANTRY_DETACHED` | - | Safety handler: disable XY, switch to sewing mode |
| `_GANTRY_ATTACHED` | - | Handler: switch to embroidery mode, prompt homing |
| `QUERY_MODE` | - | Display current mode and gantry state |
| `_REQUIRE_EMBROIDERY_MODE` | - | Guard: error if not in embroidery mode |
| `SEWING_STATUS` | - | Display sewing mode status and stitch count |
| `RESET_STITCH_COUNTER` | - | Reset stitch counter to 0 |
| `WAIT_NEEDLE_UP` | - | Block until encoder confirms needle UP (requires AS5600) |

See [hybrid/MODE_SWITCHING.md](hybrid/MODE_SWITCHING.md) for full macro definitions.

### Encoder Commands (Requires AS5600 Hardware)

| Command | Parameters | Description |
|---------|------------|-------------|
| `QUERY_AS5600` | `SENSOR=<name>` | Read encoder angle and position |
| `AS5600_STATUS` | `SENSOR=<name>` | Check magnet detection status |
| `AS5600_START_MONITOR` | `RATE=<hz>` | Start continuous monitoring |
| `AS5600_STOP_MONITOR` | `SENSOR=<name>` | Stop monitoring |
| `AS5600_RESET_POSITION` | `SENSOR=<name>` | Reset revolution counter |
| `AS5600_SET_TARGET` | `SENSOR=<name> POSITION=<deg>` | Set hold target position |

See [encoder/README.md](encoder/README.md) for configuration details.

Install (on a deployed machine, macros are symlinked from `~/stitchlabos-config` automatically):
```bash
ln -sf ~/stitchlabos-config/printer_data/config/embroidery_macros.cfg ~/printer_data/config/embroidery_macros.cfg
echo '[include embroidery_macros.cfg]' >> ~/printer_data/config/printer.cfg
sudo systemctl restart klipper
```

## Moonraker WiFi API

Endpoints added by `stitchlabos-config/moonraker/components/wifi_manager.py`:

| Method | Endpoint |
|--------|----------|
| GET | `/server/wifi/status` |
| GET | `/server/wifi/scan` |
| GET | `/server/wifi/profiles` |
| POST | `/server/wifi/connect` |
| POST | `/server/wifi/disconnect` |
| POST | `/server/wifi/ap/enable` |
| POST | `/server/wifi/ap/disable` |

Scripts location: `/home/pi/printer_data/scripts/`

## TurtleStitch Offline Server

| Item | Value |
|------|-------|
| Files | `/home/pi/turtlestitch` |
| Nginx config | `/etc/nginx/sites-available/turtlestitch` |
| Port | 3000 |
| Service | `turtlestitch.service` (disabled, nginx owns port) |
| UI env var | `VITE_TURTLESTITCH_URL` |
| Projects dir | `/home/pi/printer_data/gcodes/turtlestitch_projects` |

Upstream docs: `turtlestitch/OFFLINE.md`

### TurtleStitch Project File Management

TurtleStitch project XML files can be saved to and loaded from the Pi using Moonraker's file API. Projects are stored in `/home/pi/printer_data/gcodes/turtlestitch_projects/`.

See [components/turtlestitch.md](components/turtlestitch.md) for API examples, JavaScript integration, and UI details.

## Mainsail Config

Connection target: `mainsail/public/config.json`

Note: Service worker/PWA caching can make config changes appear to not apply. Hard refresh or clear site data.

## CORS (if needed)

```ini
# moonraker.conf
[authorization]
cors_domains:
    *//localhost:8080
    *//stitchlabdev.local
```
