# Troubleshooting

> Common issues and solutions. See [05-configuration.md](05-configuration.md) for port/endpoint reference.

## Moonraker Connection

| Symptom | Check |
|---------|-------|
| UI doesn't connect | `curl http://localhost:7125/printer/info` |
| Wrong instance | `mainsail/public/config.json` |
| Changes don't apply | Service worker cache - hard refresh or clear site data |

## Controller Menu / WebSocket

| Symptom | Cause |
|---------|-------|
| Shows disconnected | Expected: WebSocket :7150 not implemented yet |
| WS errors in console | Use CLI: `KlipperLiveControl/live_jogd/dongle_api.py` |

## Embroidery Panel

| Symptom | Fix |
|---------|-----|
| Panel not showing | Enable in Settings > Dashboard |
| Buttons don't work | Check browser console (F12) |
| Macros fail | `journalctl -u klipper -f` |

## Controller Hardware

```bash
# Check dongle device
ls -la /dev/stitchlab-dongle

# Check live_jogd status
sudo systemctl status live_jogd
journalctl -u live_jogd -f

# Query dongle directly
python dongle_api.py --query status
```

## G-Code Studio Viewer

Current viewer: **Paper.js** (`GCodeStudio2D.vue`)

Legacy Handibot viewer (`GCodeStudio2DViewer.vue`) is not routed.

If `/home/pi/mainsail/lib/gcode2dviewer/` exists, check built assets for actual references.

See [Components: G-Code Studio](components/gcode-studio.md) for verification.
