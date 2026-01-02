# Troubleshooting

## UI doesn’t connect to Moonraker

- Verify Moonraker is reachable: `curl http://localhost:7125/printer/info`
- Check `mainsail/public/config.json`
- Beware service worker caching (hard refresh, or clear site data)

## Controller menu shows disconnected / WS errors

- Expected today: the UI side expects a WebSocket on `:7150` but `live_jogd` doesn’t provide it yet.
- Use the CLI tooling from `KlipperLiveControl/live_jogd/dongle_api.py`.

## G-Code Studio viewer confusion (2D)

Current deployed viewer is **Paper.js** (`mainsail/src/components/gcodestudio/GCodeStudio2D.vue`).
The Handibot canvas viewer (`mainsail/src/components/gcodestudio/GCodeStudio2DViewer.vue`) is legacy and not routed.

If `/home/pi/mainsail/lib/gcode2dviewer/` exists on the Pi, that does not mean it is active.
Check for `gcode2dviewer.js` references in the built assets if you need to confirm.

See [Components: G-Code Studio](components/gcode-studio.md) for details and verification commands.
