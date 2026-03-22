# Runbook: Pi Services

> Service management for `pi@stitchlab.local`. See [05-configuration.md](../05-configuration.md) for ports/endpoints.

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

## AccessPopup

Runs on a systemd timer every 2 minutes. Creates "Stitchlab" AP (password: `praxistest`, IP: `192.168.50.5`) when no known WiFi is in range.

```bash
systemctl status AccessPopup.timer
journalctl -u AccessPopup.service -n 30
```

> **Known conflict:** Do NOT install standalone `dnsmasq` — it conflicts with NetworkManager's internal dnsmasq for AP shared mode. See [ap-troubleshooting.md](ap-troubleshooting.md).

## WiFi Manager

```bash
curl http://localhost:7125/server/wifi/status
```

The `wifi_manager.py` Moonraker component lives in `/home/pi/moonraker/moonraker/components/`. It uses `nmcli` for all WiFi operations (requires `pi ALL=(ALL) NOPASSWD: ALL` in sudoers).

## SKR Pico (UART)

Klipper connects via `/dev/serial0` (hardware UART, GPIO14/15). Requires `enable_uart=1` and `dtoverlay=disable-bt` in `/boot/firmware/config.txt`, and no `console=serial0` in `cmdline.txt`.

```bash
ls /dev/serial0                   # must exist
tail -20 /home/pi/printer_data/logs/klippy.log
systemctl status klipper
```
