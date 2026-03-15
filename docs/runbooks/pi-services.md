# Runbook: Pi Services

> Service management for `pi@stitchlabdev.local`. See [05-configuration.md](../05-configuration.md) for ports/endpoints.

## Core Services

| Service | Purpose |
|---------|---------|
| `nginx` | Web server for Mainsail + TurtleStitch |
| `moonraker` | Klipper API |
| `klipper` | Motion control |

```bash
systemctl status nginx moonraker klipper
```

## live_jogd

Bridges StitchLabDongle (USB) to Moonraker (HTTP).

```bash
systemctl status live_jogd
journalctl -u live_jogd -f
```

Install: `KlipperLiveControl/live_jogd/live_jogd.service`

## TurtleStitch Offline

Nginx serves `/home/pi/turtlestitch` on `:3000`.

```bash
curl -I http://localhost:3000
ss -ltnp | grep ':3000'
```

Config: `/etc/nginx/sites-available/turtlestitch`

Note: `turtlestitch.service` exists but is disabled (nginx owns port).

## WiFi Manager

```bash
curl http://localhost:7125/server/wifi/status
```

Deploy: `./stitchlabos/scripts/rpi/deploy_wifi_manager.sh --host pi@stitchlabdev.local`
