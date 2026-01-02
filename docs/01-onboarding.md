# Onboarding

## What is in this workspace?

This workspace combines several projects that together form the StitchLAB system:

- **UI**: `mainsail/` (Vue 2 + Vite + Vuetify). This is the primary UI people use.
- **Simulator**: `virtual-klipper-printer/` (Dockerized Moonraker/Klipper + dummy webcam).
- **TurtleStitch**: `turtlestitch/` (Snap!/TurtleStitch tooling and offline assets).
- **StitchlabOS**: `stitchlabos/` (OS/config/scripts for the target machine / dev Pi target).
- **Live control**: `KlipperLiveControl/` (ESP32 controller & dongle, plus `live_jogd/` daemon).

## What is “ours” (StitchLAB-specific)

The following are StitchLAB-owned extensions/integration (not upstream projects):

- **Needle control UI + macros**
	- UI panel: `mainsail/src/components/panels/EmbroideryControlPanel.vue`
	- Klipper macros: `stitchlabos/config/klipper/embroidery_macros.cfg`

- **WiFi management (Moonraker component + scripts)**
	- Moonraker component: `stitchlabos/config/moonraker/wifi_manager.py`
	- Deploy helper: `stitchlabos/scripts/rpi/deploy_wifi_manager.sh`
	- UI entry point (status/controls): `mainsail/src/components/TheControllerMenu.vue`

- **TurtleStitch offline on the Pi + G-code export path**
	- HTTP server script: `turtlestitch-server.py` (serves `/home/pi/turtlestitch` on port `3000`)
	- systemd unit: `turtlestitch.service`
	- Embroidery/plotter G-code is uploaded/printed via Moonraker from within the UI

## Read this first

There are two common development modes:

1) **Local dev mode (recommended)**
- Run `mainsail` dev server.
- Run simulator (`virtual-klipper-printer`) locally.

2) **Dev Pi mode (`pi@stitchlabdev.local`)**
- UI build is deployed to nginx webroot on the Pi.
- Services (Moonraker/Klipper/nginx + live control daemon + optionally TurtleStitch server) run on the Pi.

Pick one:
- [Quickstart (Local)](03-quickstart-local.md)
- [Quickstart (Dev Pi)](04-quickstart-pi.md)
