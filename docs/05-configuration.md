# Configuration & Ports

## Ports / endpoints

| Component | Default | Where defined | Notes |
|---|---:|---|---|
| Mainsail dev server | 8080 | `mainsail/vite.config.ts` | Vite on `0.0.0.0:8080` |
| Moonraker (simulator) | 7125 | `virtual-klipper-printer/docker-compose.yml` | Local API endpoint |
| Dummy webcam (simulator) | 8110 | `virtual-klipper-printer/docker-compose.yml` | MJPG stream |
| TurtleStitch offline server | 3000 | `turtlestitch-server.py` | Serves `/home/pi/turtlestitch` |
| live control WebSocket | 7150 | UI expects it | **Not implemented in `live_jogd` yet** |

## Moonraker WiFi API (StitchLAB)

If deployed, the StitchLAB WiFi manager adds Moonraker endpoints such as:

- `GET /server/wifi/status`
- `GET /server/wifi/scan`
- `GET /server/wifi/profiles`
- `POST /server/wifi/connect`
- `POST /server/wifi/disconnect`
- `POST /server/wifi/ap/enable`
- `POST /server/wifi/ap/disable`

Implementation lives in `stitchlabos/config/moonraker/wifi_manager.py` and runs scripts from `/home/pi/printer_data/scripts/`.

## Mainsail instance configuration

Mainsail reads its initial connection target from `mainsail/public/config.json`.

Important: service worker/PWA caching can make `config.json` changes look like they did not apply.

## Live control reality (important)

Docs currently describe a UX that expects `:7150` WebSocket communication.
As of now, the daemon side is CLI-controlled via `KlipperLiveControl/live_jogd/dongle_api.py`.

If you update the UI to use WebSocket later, this document should become the single source of truth.
