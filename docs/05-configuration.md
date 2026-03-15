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

Source: `stitchlabos/config/klipper/embroidery_macros.cfg`

| Macro | Parameters | Description |
|-------|------------|-------------|
| `NEEDLE_TOGGLE` | - | Toggle UP/DOWN, restore Z with G92 |
| `STITCH` | - | One rotation (5mm), restore logical Z |
| `LOCK_STITCH` | `COUNT=3` | Multiple stitches to secure thread |
| `ZERO_NEEDLE_POSITION` | - | Move to UP, set Z=0 |
| `EMBROIDERY_HOME` | - | Home XY, then Z, center XY |
| `NEEDLE_ADJUST` | `AMOUNT=0.1` | Fine-tune needle position |
| `EMBROIDERY_STATUS` | - | Display position and stitch count |

Install:
```bash
cp stitchlabos/config/klipper/embroidery_macros.cfg ~/printer_data/config/
echo '[include embroidery_macros.cfg]' >> ~/printer_data/config/printer.cfg
sudo systemctl restart klipper
```

## Moonraker WiFi API

Endpoints added by `stitchlabos/config/moonraker/wifi_manager.py`:

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

TurtleStitch project XML files can be saved to and loaded from the Pi using Moonraker's file API.

**Save project to Pi:**
```javascript
// In TurtleStitch, use Moonraker API to save
const formData = new FormData();
formData.append('file', xmlBlob, 'myproject.xml');
formData.append('root', 'gcodes');
formData.append('path', 'turtlestitch_projects');

fetch('http://stitchlabdev.local:7125/server/files/upload', {
  method: 'POST',
  body: formData
});
```

**List projects:**
```bash
curl 'http://stitchlabdev.local:7125/server/files/directory?path=gcodes/turtlestitch_projects' | \
  jq '.result.files'
```

**Download project:**
```bash
curl 'http://stitchlabdev.local:7125/server/files/gcodes/turtlestitch_projects/myproject.xml'
```

**Delete project:**
```bash
curl -X DELETE 'http://stitchlabdev.local:7125/server/files/gcodes/turtlestitch_projects/myproject.xml'
```

See [components/turtlestitch.md](components/turtlestitch.md) for integration details.

Future (planned): Add nginx reverse proxy to upstream TurtleStitch cloud (e.g. `/turtlestitch-cloud/`) and update `turtlestitch/index.html` `snap-cloud-domain` meta to enable cloud login/save from the Pi UI.

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
