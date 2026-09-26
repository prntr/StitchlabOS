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

Runtime model:
- Installed on every image, but intentionally not enabled at boot.
- Expected boot state is `static` + `inactive`.
- The Mainsail Controller menu starts/stops it through Moonraker `machine.services.*`.
- Port `7150` only listens while the service is active.

```bash
# Expected before the user clicks Connect Controller
systemctl is-enabled live_jogd       # static
systemctl is-active live_jogd || true # inactive

# Start/stop through Moonraker, same path used by Mainsail
curl -X POST -H 'Content-Type: application/json' \
  -d '{"service":"live_jogd"}' \
  http://localhost:7125/machine/services/start

curl -X POST -H 'Content-Type: application/json' \
  -d '{"service":"live_jogd"}' \
  http://localhost:7125/machine/services/stop

# Runtime diagnostics
systemctl status live_jogd
journalctl -u live_jogd -f
ss -ltnp | grep ':7150'
ls -la /dev/stitchlab-dongle
```

Service-control prerequisites:
- `/home/pi/printer_data/moonraker.asvc` must contain `live_jogd`.
- `live_jogd.service` must be *loaded* when Moonraker starts. Moonraker only lists loaded units, and an inactive `static` unit is loaded only while something references it; without that Moonraker reads `moonraker.asvc` but still answers `Service 'live_jogd' not installed`. The drop-in `/etc/systemd/system/moonraker.service.d/stitchlab-live-jogd.conf` (`Before=live_jogd.service`) provides the reference.
- Moonraker's own files are never patched: `update_manager` refuses to update a modified repo. `git -C /home/pi/moonraker status --porcelain` must print nothing.

```bash
grep -qx live_jogd /home/pi/printer_data/moonraker.asvc && echo allowed
systemctl show -p LoadState --value live_jogd.service   # expected: loaded
git -C /home/pi/moonraker status --porcelain            # expected: no output
sudo systemctl daemon-reload && sudo systemctl restart moonraker
```

Python dependencies are installed into `/home/pi/live_jogd/venv` from `requirements.txt` and include `pyserial`, `aiohttp`, and `websockets`.

Live Control timing:
- `LINK_TIMEOUT_S=0.200` zeroes motion state and blocks movement promptly after a short active-controller frame gap.
- `LIVE_CONTROL_LINK_TIMEOUT_S=2.0` disables the explicit Live Control gate after sustained link loss.
- Serial errors or CRC mismatches can still indicate dongle/controller link noise and should be checked in `journalctl -u live_jogd`.

Install source: `stitchlabos/image/src/modules/live-jogd/`

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
