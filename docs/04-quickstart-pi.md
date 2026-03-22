# Quickstart (Dev Pi)

> Deploy UI and validate services on `pi@stitchlab.local`.

## Deploy UI

```bash
cd mainsail
npm install
npm run build
rsync -avz --delete dist/ pi@stitchlab.local:/home/pi/mainsail/
ssh pi@stitchlab.local "sudo systemctl restart nginx"
```

## Validate Core Services

```bash
ssh pi@stitchlab.local "systemctl status nginx moonraker klipper"
curl http://stitchlab.local:7125/printer/info
```

## Validate StitchLAB Extras

See [Runbook: Pi Services](runbooks/pi-services.md) for detailed validation commands.

Quick checks:

```bash
# G-Code Studio viewer (Paper.js = current)
ssh pi@stitchlab.local "grep -l 'PaperScope' /home/pi/mainsail/assets/*"

# live_jogd
ssh pi@stitchlab.local "systemctl status live_jogd"

# WiFi manager
curl http://stitchlab.local:7125/server/wifi/status

# TurtleStitch
curl -I http://stitchlab.local:3000

# SKR Pico reachable?
ssh pi@stitchlab.local "ls /dev/serial0 && tail -5 /home/pi/printer_data/logs/klippy.log"
```

See [05-configuration.md](05-configuration.md) for all ports and endpoints.
