# The StitchLAB ecosystem — who does what

> A map of every repo that belongs to StitchLAB. This repo is the integration
> point, not the whole project. Where it is all going: [10-roadmap.md](10-roadmap.md).
>
> Paths outside this repo are given relative to `~/Code/active/` and are not
> part of the public repository.

Without this page the workspace reads like a dozen unrelated projects. It is
not: they hang off one machine and one planned replacement.

## Three generations

```text
StitchLAB Classic ──► StitchLAB Hybrid ──► OpenRSS
Embroidery machine    Sewing and stitching  Modular textile robotics,
from a household      in one machine        its own motion core
sewing machine
(shipping)            (in development)      (in planning)
```

**Classic** works. A retired household sewing machine (Pfaff
Tipmatic/Hobbymatic) with a 3D-printed conversion, an SKR Pico and Klipper. Its
software image is StitchLabOS — this repo.

**Hybrid** extends the same machine to actual sewing: detachable gantry,
handwheel encoder, foot pedal, mode switching. Still on Klipper.

**OpenRSS** is the break, not the continuation. It replaces the
Klipper/Moonraker/Mainsail stack with its own process-aware motion core.
OpenRSS' own planning calls today's stack *StitchLAB OS Legacy*: its UX patterns
and lessons carry forward, its implementation does not.

---

## What lives in this repo

`MainsailDev` is a historical folder name; the GitHub remote is
`prntr/StitchlabOS`. Four embedded repos belong to it:

| Folder | What | Kind |
|---|---|---|
| `mainsail/` | Web UI, fork with StitchLAB panels | submodule, `prntr/mainsail` |
| `turtlestitch/` | Offline editor on the Pi | submodule, `prntr/turtlestitch` |
| `stitchlabos-config/` | Moonraker components, macros, WiFi scripts | submodule, `prntr/stitchlabos-config` |
| `virtual-klipper-printer/` | Simulator for testing | plain clone, **not** a submodule |

---

## The other repos

### Machine and firmware

| Project | Role | State |
|---|---|---|
| `StitchHEAD` | Firmware for the SKR Pico as drive head, TMC2209 over UART | **Open problem**: UART configuration of the TMC2209s works under no Arduino framework tried. Read its `PROBLEM_ANALYSIS.md` before building anything there. |
| `MKSdrivemini` | MKS XDrive Mini, BLDC closed loop — groundwork for the sewing motor | Bring-up phase, deliberately minimal |
| `KlipperLiveControl` | ESP-NOW link: handheld → dongle → `live_jogd` → Moonraker | Part of StitchLabOS; `live_jogd` ships in this image |
| `PCBs`, `eez-projects` | Circuit boards and instrumentation; `PCBs/boards/StitchPCB` is the CM5 + RP2350 + CAN controller draft | Supporting work |
| `MotorStudio` | macOS app; its Needle workbench drives the MKS XDrive needle tests | Workbench built, live plots open |
| `SLStudio` | SquareLine/LVGL touch UIs for LilyGo AMOLED (ESP32-S3), incl. a CNC pad | Dormant |

### Model and simulation

| Project | Role | State |
|---|---|---|
| `stitchLABsim` | Thread take-up and stitch formation model after Manoilenko et al. (2024), as a package | Supply side complete, demand side open |
| `stitchlabPROdev` | Exploratory groundwork for the same model, Pfaff cam analysis | Scripts, no package — `stitchLABsim` is the tidied form |
| `StatorTwin` | Motor-side modelling, PCB-stator sizing for the toolhead drives | Standalone, no Git remote |

### From image to stitch

| Project | Role | State |
|---|---|---|
| `IMG2SVG2SITCH` | Raster image → SVG → stitch path / G-code | Two scripts, no package |
| `RPIcam2Embroidery` | Camera image → embroidery file, Flask backend for the Pi | Standalone, not yet in the image |
| `StitchlabAssets` | Graphics pipeline: CAD PDF → SVG/AI, logo, `gcode_to_svg.py` | Tooling; supplies the Imager icon among other things |

### Documentation, teaching, assembly

| Project | Role | State |
|---|---|---|
| `Stitch(x)App` | Source material for the machine (STEP/GLB/STL) plus `PLAN.md` for the planned knowledge platform | Material and a plan, no code yet |
| `Bauplan` | Turns STEP plus a step script into assembly instructions: SVGs, PDF, bill of materials | Reads `Stitch(x)App`, never writes to it |
| `ZeitleisteStitchTexTech` | Interactive timeline for the university course | Web, own GitHub repo |

### The future

| Project | Role | State |
|---|---|---|
| `OpenRSS` | Open Robotic Sewing System — hardware-agnostic sewing and textile robotics platform | Rust core with planner v0.3 and a simulator; Phase 5 started on the simulator track. `README.md`, `roadmap.md`, `docs/adr/`, scope proposal in `docs/system-scope-v0.md` |

OpenRSS is not a renamed Klipper setup. It targets several coordinated actuators
— needle, take-up lever, hook, feed, thread tension, cutters — the needle phase
as a first-class coordinate, and closed-loop drives. Whether LinuxCNC can supply
the realtime core is investigated in
`Reports&Plans/LinuxCNC Motion Kernel Prototype Plan.md`.

Classic stays a first-class target throughout: OpenRSS is meant to run on the
same cheap hardware, with its own motion core instead of Klipper.

The robotic sewing toolhead ("StitchLAB Robot") has no repo of its own. Its
pieces are `StitchHEAD` (firmware), `MKSdrivemini` and `MotorStudio` (BLDC
needle drive), `PCBs/boards/StitchPCB` (controller), `StatorTwin` (motors) and
`stitchlabPROdev` (fly-by-wire concept, Pfaff cam data). OpenRSS collects them
in `docs/system-scope-v0.md`.

Every file outside OpenRSS that OpenRSS reads is listed, with the commit read,
in `OpenRSS/docs/sources.md`. Move or rename such a file only together with that
ledger. Knowledge that several of these repos need belongs in
`~/Code/active/wissen`, not in any one of them.

---

## Which repo does a change belong in

| It is about … | Repo |
|---|---|
| The Pi image, modules, CI, releases | this repo |
| Mainsail panels, UI behaviour | `mainsail/` (submodule) |
| Moonraker components, macros, WiFi scripts | `stitchlabos-config/` (submodule) |
| MCU firmware for the Pico under Klipper | `firmware/skr-pico/` here |
| Standalone Pico firmware without Klipper | `StitchHEAD` |
| Thread physics, stitch geometry | `stitchLABsim` |
| Assembly instructions, exploded views | `Bauplan` (from `Stitch(x)App`) |
| New motion core, machine model | `OpenRSS` |

## House rules

Each of these projects has an `AGENTS.md` with `CLAUDE.md` as a symlink to it,
and points at `~/Code/_std/AGENTS.base.md` and
`~/Code/active/plattform/pipeline.md`. Check the state with:

```bash
~/Code/_std/bin/agents-doctor
```
