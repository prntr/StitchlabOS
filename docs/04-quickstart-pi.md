# Quickstart (Dev Pi)

> Deploy UI and validate services on `pi@stitchlabdev.local`.

## Deploy UI

```bash
cd mainsail
npm install
npm run build
rsync -avz --delete dist/ pi@stitchlabdev.local:/home/pi/mainsail/
ssh pi@stitchlabdev.local "sudo systemctl restart nginx"
```

## Validate Core Services

```bash
ssh pi@stitchlabdev.local "systemctl status nginx moonraker klipper"
curl http://stitchlabdev.local:7125/printer/info
```

## Validate StitchLAB Extras

See [Runbook: Pi Services](runbooks/pi-services.md) for detailed validation commands.

Quick checks:

```bash
# G-Code Studio viewer (Paper.js = current)
ssh pi@stitchlabdev.local "grep -l 'PaperScope' /home/pi/mainsail/assets/*"

# live_jogd
ssh pi@stitchlabdev.local "systemctl status live_jogd"

# WiFi manager
curl http://stitchlabdev.local:7125/server/wifi/status

# TurtleStitch
curl -I http://stitchlabdev.local:3000
```

See [05-configuration.md](05-configuration.md) for all ports and endpoints.
