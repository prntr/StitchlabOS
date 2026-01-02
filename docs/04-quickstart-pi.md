# Quickstart (Dev Pi: stitchlabdev.local)

Target: `pi@stitchlabdev.local`

This doc is a **runbook** for deploying the UI and validating services on the dev Pi.

## Deploy UI build

From `mainsail/`:

```bash
npm install
npm run build
rsync -avz --delete dist/ pi@stitchlabdev.local:/home/pi/mainsail/
```

Then on the Pi:

```bash
sudo systemctl restart nginx
```

## Validate core services

On the Pi:

```bash
systemctl status nginx
systemctl status moonraker
systemctl status klipper
```

Moonraker quick check:

```bash
curl http://localhost:7125/printer/info
```

## Validate StitchLAB extras (if installed)

### live control daemon

```bash
systemctl status live_jogd
journalctl -u live_jogd -n 100 --no-pager
```

Note: the UI expects a WebSocket control channel on `:7150`, but in the current codebase this is **not implemented** in `live_jogd` yet; management is CLI-only.

### WiFi manager (Moonraker component)

If you deploy the StitchLAB WiFi manager, Moonraker exposes endpoints like:

```bash
curl http://localhost:7125/server/wifi/status
```

Deployment is scripted via:

```bash
./stitchlabos/scripts/rpi/deploy_wifi_manager.sh --host pi@stitchlabdev.local
```

### TurtleStitch offline server

The workspace includes `turtlestitch-server.py` which serves TurtleStitch from `/home/pi/turtlestitch` on port `3000`.
How that is exposed via nginx on the Pi still needs to be documented/confirmed.

## Known unknowns (needs confirmation on Pi)

- nginx site configuration path and reverse-proxy rules
- whether TurtleStitch is reverse proxied under the same host
- Moonraker `cors_domains` and `trusted_clients` policy in the dev setup
