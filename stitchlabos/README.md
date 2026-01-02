# stitchlabos (workspace scaffold)

Umbrella repo idea for a reproducible DIY embroidery machine OS built on **Klipper + Moonraker + Mainsail**.

This workspace currently contains two dev environments:
- `mainsail/`: Vue2 + Vite frontend (custom embroidery UI additions live here)
- `virtual-klipper-printer/`: Dockerized Moonraker/Klipper simulator + dummy webcam (for desktop development)

## Goal
- Use the Raspberry Pi staging system as a **real-hardware dev target**.
- Make every change reproducible: no one-off SSH edits; everything should be applied via **idempotent scripts**.
- Later: ship a flashable Raspberry Pi image.

## Proposed repo structure (target)
- `stitchlabos/` (this umbrella repo)
  - `submodules/mainsail/` (forked Mainsail)
  - `submodules/turtlestitch/` (forked TurtleStitch)
  - `config/klipper/` (machine-safe macros + example configs)
  - `services/` (systemd units, nginx snippets, NetworkManager/hotspot config)
  - `scripts/` (idempotent installers + deploy helpers)
  - `image/` (pi-gen / debos / buildroot tooling later)

## Current deliverables in this scaffold
- `config/klipper/embroidery_macros.cfg`: macros intended to be deployed to a real Klipper install.
- `scripts/rpi/`: helpers to deploy macros and a built Mainsail frontend.

## Next
1) Deploy macros to the Pi (copy + include in `printer.cfg` + restart Klipper).
2) Build and deploy a custom Mainsail dist to the Pi.
3) Move development into forks + submodules and ensure commits go into the correct repos.
