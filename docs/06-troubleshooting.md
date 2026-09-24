# Troubleshooting

> Common issues and solutions. See [05-configuration.md](05-configuration.md) for port/endpoint reference.

## Moonraker Connection

| Symptom | Check |
|---------|-------|
| UI doesn't connect | `curl http://localhost:7125/printer/info` |
| Wrong instance | `mainsail/public/config.json` |
| Changes don't apply | Service worker cache - hard refresh or clear site data |
| WS reconnects repeatedly in AP mode | Three-layer fix (brcmfmac + Moonraker ping + frontend keepalive) baked into Beta2 — see [AP runbook Issue 5](runbooks/ap-troubleshooting.md#issue-5-frontend-websocket-reconnects-in-ap-mode) |

## Controller Menu / WebSocket

| Symptom | Cause |
|---------|-------|
| Shows disconnected | `live_jogd` is not running — click **Connect Controller** in the Controller menu to start the service. The daemon is installed but not auto-started. |
| "Service 'live_jogd' not installed" | First verify `/home/pi/printer_data/moonraker.asvc` contains `live_jogd`. If it does and the error persists, the running Moonraker build is rejecting inactive `static` units; verify `stitchlab-moonraker-service-control-patch.service` is enabled, run `/usr/local/bin/stitchlab-moonraker-service-control-patch`, then restart Moonraker. |
| Live Control switches off by itself | A sustained controller-link gap exceeded `LIVE_CONTROL_LINK_TIMEOUT_S` (2.0 s by default), or a service/client reset disabled the safety gate. Check `journalctl -u live_jogd | grep -E 'sustained link timeout|Serial read error|CRC mismatch'`. Short gaps above `LINK_TIMEOUT_S` (200 ms) should only zero/block motion, not flip the Live Control switch off. |
| Motion blocked after enabling Live Control | Check the block-reason text below the Live Control toggle. Common causes: `link_inactive`, no active controller selected, controller type still set to "Unknown", machine not homed, printer busy, or Live Control disabled. |
| WS errors in console | Confirm the service is running and port `7150` is listening; then check `journalctl -u live_jogd -f`. Use CLI diagnostics from `/home/pi/live_jogd`: `./venv/bin/python3 dongle_api.py --query status`. |

## Embroidery Panel

| Symptom | Fix |
|---------|-----|
| Panel not showing | Enable in Settings > Dashboard |
| Buttons don't work | Check browser console (F12) |
| Macros fail | `journalctl -u klipper -f` |

## SKR Pico / UART

| Symptom | Check |
|---------|-------|
| `/dev/serial0` missing | `enable_uart=1` + `dtoverlay=disable-bt` missing from `config.txt` |
| Klipper: "Unable to connect" | `console=serial0,115200` in `cmdline.txt` — remove it |
| Klipper connects but no motion | Firmware not flashed to Pico — compile and flash manually |

```bash
ls /dev/serial0                            # must exist after boot
grep 'enable_uart\|disable-bt' /boot/firmware/config.txt
grep 'serial0' /boot/firmware/cmdline.txt  # should return nothing
tail -20 /home/pi/printer_data/logs/klippy.log
```

## Controller Hardware

```bash
# Check dongle device
ls -la /dev/stitchlab-dongle

# Check live_jogd status
systemctl is-enabled live_jogd       # expected: static
systemctl is-active live_jogd || true # expected: inactive until Controller menu starts it
sudo systemctl status live_jogd
journalctl -u live_jogd -f

# Check Moonraker service-control prerequisites
grep -qx live_jogd /home/pi/printer_data/moonraker.asvc && echo allowed
systemctl is-enabled stitchlab-moonraker-service-control-patch.service
ss -ltnp | grep ':7150'              # only while live_jogd is active

# Query dongle directly
cd /home/pi/live_jogd
./venv/bin/python3 dongle_api.py --query status
```

## G-Code Studio Viewer

Current viewer: **Paper.js** (`GCodeStudio2D.vue`)

Legacy Handibot viewer (`GCodeStudio2DViewer.vue`) is not routed.

If `/home/pi/mainsail/lib/gcode2dviewer/` exists, check built assets for actual references.

See [Components: G-Code Studio](components/gcode-studio.md) for verification.

## WebMCP / AI Agent Integration

| Symptom | Fix |
|---------|-----|
| Blue widget not showing | Only loads in dev mode (`npm run serve`). Check browser console for `[WebMCP]` messages |
| Agent can't see tools | Restart your MCP client after pasting the token. Some clients need a restart to pick up new tools |
| Token expired / rejected | Generate a new token via `npx @jason.today/webmcp --new` |
| Tools return empty data | Ensure Moonraker is connected (check Mainsail shows printer status, not "Connecting...") |
| `Failed to load webmcp.js` | CDN unreachable — check internet connection, or host `webmcp.js` locally in `mainsail/public/lib/` |
