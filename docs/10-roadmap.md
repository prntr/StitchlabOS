# Development roadmap

> Where StitchLAB is going, and what comes next. Who does what:
> [00-ecosystem.md](00-ecosystem.md).
>
> As of 2026-09-20. The substance comes from
> `Reports&Plans/Development Roadmap.md` and the planning in the `OpenRSS` repo;
> this page puts it in order and states what each milestone has to have
> finished.

## The line

```text
Beta1          Beta2            1.0              Hybrid            OpenRSS
shipped        commissioning    reproducible     sewing + stitch   new core
2026-04-14     ← here           Classic done     same machine      from planning
```

Classic and Hybrid run on Klipper. OpenRSS replaces the core. Classic is not
retired by it — it stays the cheap entry machine and a target for OpenRSS.

---

## Beta1 — shipped (v0.1.0-beta.1, 2026-04-14)

First public image. Klipper, Moonraker, the Mainsail fork, TurtleStitch, AP
mode, `live_jogd`.

The teething problems it exposed:

- `os_list.json` pointed at an asset that was never published — the documented
  Imager route was a 404 for everyone.
- `extract_sha256` was literally the placeholder from the template.
- A freshly flashed system found no MCU: the Pico firmware was not part of the
  image, and a Pi in AP mode has no internet to build it.
- The `stitchlab-intake` module was absent from `MODULES` although
  `moonraker.conf` already referenced it.

## Beta2 — a machine is commissioned without prior knowledge

**The goal:** flash the card, power on, follow one guide, stitch. No second
computer, no toolchain, no knowledge of the repo.

| | Status |
|---|---|
| Pico firmware built in CI and shipped in the image | done |
| `stitchlab-flash-pico` — guided commissioning on the Pi | done |
| Bootloader-free rescue build for bricked boards | done |
| `os_list.json` generated from real checksums and published | done |
| CI fails when a published URL does not resolve | done |
| `stitchlab-intake` and `pico-firmware` in `MODULES` | done |
| `moonraker.asvc` seeded with upstream defaults, not just `live_jogd` | done |
| [11-commissioning.md](11-commissioning.md) as one continuous path | done |
| Commissioning guide attached to each release, matching that image | done |
| **Run on real hardware — someone else's card, someone else's Pico** | **open** |
| Assembly instructions from `Bauplan` joined up with the software path | open |

The last two are the ones that count: Beta2 is finished when somebody other
than the authors gets a machine running with it.

**Acceptance:** one run through steps 1 to 4 of
[11-commissioning.md](11-commissioning.md) on an unused Pi and a factory-fresh
SKR Pico, written up.

## 1.0 — Classic is reproducible

Not more features. Reliability.

- A release build is repeatable: Klipper host and Pico firmware demonstrably
  come from the same state.
- The update path is documented and tested — including "host updated, firmware
  not".
- The open points from the Praxistest are closed: coordinate system and homing
  explained, upper and lower thread documented, TurtleStitch examples present on
  the Pi.
- WiFi control is more than a patch around AccessPopup.
- A list of tested sewing machines, not just the Pfaff 917.

## Hybrid — sewing and stitching in one machine

Still on Klipper; extends Classic with the mechanics and control of sewing.
Details in [hybrid/IMPLEMENTATION_PLAN.md](hybrid/IMPLEMENTATION_PLAN.md).

- Detachable gantry with a latch and pogo connector
- AS5600 encoder on the handwheel as needle phase
- Sewing motor under Klipper, foot pedal through the ESP dongle
- Mode switching with a safety interlock, visible in Mainsail

The bottleneck is the drive: `MKSdrivemini` has to show the closed loop holds
up, and `StitchHEAD` has an unsolved TMC2209 UART problem. Settle both before
promising dates.

## OpenRSS — the new core

Own repo, own planning, own pace. No schedule pressure from Classic.

- **Phase 0** planning baseline — running
- **Phase 1** domain model: vocabulary, machine, process and job models, safety
  model
- **Phase 2** motion core: decide on LinuxCNC as the realtime layer (prototype
  plan exists), otherwise a scheduler of our own
- **Phase 3** backend-neutral service (`stitchlabd`) serving UI and controllers
  and delegating motion to adapters

The dividing line to this repo: **concepts migrate from StitchLabOS, code does
not.** Interaction patterns, the dongle protocol and the lessons from the
Praxistest are inputs to the design. Klipper, Moonraker and Mainsail are not.

---

## What this roadmap does not decide

- Whether there will be kits. Not planned at present.
- Whether StitchLabOS goes into the official Raspberry Pi Imager list. Worth it
  only after a stable 1.0, and with outside review.
- When `RPIcam2Embroidery` becomes part of the image. Standalone so far.
