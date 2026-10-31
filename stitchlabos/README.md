# stitchlabos

The image and its tooling. The meta repo's [`AGENTS.md`](../AGENTS.md) and
[`docs/08-image-building.md`](../docs/08-image-building.md) describe the whole.

| Path | Content |
|---|---|
| `image/` | CustomPiOS modules, `upstream-pins.conf` (the Klipper, Katapult, Moonraker and mainsail-config commits a release ships), `os_list.template.json` |
| `drift/` | `make klipper-drift`: our configs and sample jobs through klippy batch mode at the pins and at upstream master |
| `scripts/ci/` | helpers for `.github/workflows/build-image.yml` |
| `scripts/rpi/deploy_mainsail_dist.sh` | build the Mainsail fork and copy its `dist/` to a Pi, for UI development |

## Macros, Wi-Fi manager and intake glue live in `stitchlabos-config`

`embroidery_macros.cfg`, `wifi_manager.py`, the Wi-Fi scripts and the intake's
Moonraker wrapper live only in the `stitchlabos-config` submodule
(`prntr/stitchlabos-config`). On an image they are symlinks into
`~/stitchlabos-config`, a git checkout that Mainsail's Update Manager updates from
tagged releases.

This folder used to carry older copies (`config/klipper/embroidery_macros.cfg`,
`config/moonraker/wifi_manager.py`) and two scripts that copied them onto a Pi
(`deploy_macros.sh`, `deploy_wifi_manager.sh`). They were removed for beta6: the
copies predated the needle and homing guards, and the scripts wrote regular files
over the symlinks, which froze that machine on the copy for every later update.
Ways to get a change onto a machine now:

- **Released:** tag `stitchlabos-config` and update it in Mainsail's Update Manager
  ([`docs/09-update-strategy.md`](../docs/09-update-strategy.md)).
- **Before a release, on a test machine:** check the branch out in the machine's own
  clone, `git -C ~/stitchlabos-config fetch origin <branch> && git -C
  ~/stitchlabos-config checkout --detach FETCH_HEAD`, then restart Klipper or
  Moonraker. The Update Manager reports the detached checkout until
  `git -C ~/stitchlabos-config checkout main` puts it back.
- **Without a machine:** `stitchlabos-config`'s `sim/run.sh` (virtual printer) and
  `make klipper-drift` with `KLIPPER_DRIFT_MACROS=<path>` (klippy batch mode).
