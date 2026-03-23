# Troubleshooting

> Common issues and solutions. See [05-configuration.md](05-configuration.md) for port/endpoint reference.
>
> See also: [AP Mode Troubleshooting](runbooks/ap-troubleshooting.md) | [Image Build Troubleshooting](08-image-building.md#troubleshooting)

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

## Shutdown / Reboot from Mainsail

| Symptom | Cause | Fix |
|---------|-------|-----|
| Shutdown/Reboot buttons do nothing | Polkit rules missing — Moonraker cannot call `systemctl poweroff` | Create `/etc/polkit-1/rules.d/moonraker.rules` (see below) |
| Moonraker log: `Interactive authentication required` | Same — polkit denies `machine.shutdown` | Same fix |

Moonraker needs polkit authorization to manage services and power off the Pi. The `klipper` module installs the rules during image build, but if they're missing:

```bash
# Check
ls /etc/polkit-1/rules.d/moonraker.rules

# Fix — create the rules file
sudo tee /etc/polkit-1/rules.d/moonraker.rules << 'EOF'
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.systemd1.manage-units" ||
         action.id == "org.freedesktop.login1.power-off" ||
         action.id == "org.freedesktop.login1.power-off-multiple-sessions" ||
         action.id == "org.freedesktop.login1.reboot" ||
         action.id == "org.freedesktop.login1.reboot-multiple-sessions" ||
         action.id == "org.freedesktop.packagekit.package-install" ||
         action.id == "org.freedesktop.packagekit.system-update") &&
        subject.user == "pi") {
        return polkit.Result.YES;
    }
});
EOF
sudo systemctl restart polkit
```

## SKR Pico / UART

| Symptom | Check |
|---------|-------|
| `/dev/serial0` missing | `enable_uart=1` + `dtoverlay=disable-bt` missing from `config.txt` |
| Klipper: "Unable to connect" | `console=serial0,115200` in `cmdline.txt` — remove it |
| Klipper: repeated "Serial connection closed" on every boot, manual Pico reset fixes it | Plymouth boot splash sends data to UART — add `plymouth.ignore-serial-consoles` to `cmdline.txt` |
| Klipper connects but no motion | Firmware not flashed to Pico — compile and flash manually |

```bash
ls /dev/serial0                            # must exist after boot
grep 'enable_uart\|disable-bt' /boot/firmware/config.txt
grep 'serial0' /boot/firmware/cmdline.txt  # should return nothing
grep 'plymouth.ignore-serial-consoles' /boot/firmware/cmdline.txt  # must be present
tail -20 /home/pi/printer_data/logs/klippy.log
```

### Plymouth UART corruption

Plymouth (the graphical boot splash) outputs to all consoles by default, including the hardware UART at `/dev/serial0`. This sends garbage data to the SKR Pico during boot, corrupting its serial state. Klipper then fails to establish the MCU handshake — the log shows dozens of `Serial connection closed` errors until the Pico is manually reset.

**Fix:** Add to `/boot/firmware/cmdline.txt` (single line, appended):
```
quiet splash plymouth.ignore-serial-consoles
```

The `stitchlabos` module applies this automatically during the image build.

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
