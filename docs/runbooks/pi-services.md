# Runbook: Pi Services

This runbook documents services expected on the dev Pi target (`pi@stitchlabdev.local`).

## Core services

- `nginx`
- `moonraker`
- `klipper`

## StitchLAB services (optional)

### live_jogd

- Purpose: bridge StitchLabDongle (USB) to Moonraker (HTTP).
- Service unit: installed from `KlipperLiveControl/live_jogd/live_jogd.service`.
- Notes: enables dongle WiFi pre-start and disables it on stop.

Commands:

```bash
systemctl status live_jogd
journalctl -u live_jogd -f
```

### TurtleStitch offline server

The workspace includes `turtlestitch-server.py` (port `3000`, directory `/home/pi/turtlestitch`).
Whether it is managed by systemd on the Pi is currently unknown and should be documented after verification.

## Moonraker extension: WiFi manager

StitchLAB provides a Moonraker component for WiFi management (NetworkManager/nmcli based).

- Source: `stitchlabos/config/moonraker/wifi_manager.py`
- Deployment: `stitchlabos/scripts/rpi/deploy_wifi_manager.sh`
- On-Pi scripts written to: `/home/pi/printer_data/scripts/wifi_*.sh`

Validation on Pi:

```bash
curl http://localhost:7125/server/wifi/status
curl http://localhost:7125/server/wifi/scan
curl http://localhost:7125/server/wifi/profiles
```
