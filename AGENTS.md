# StitchLabOS (MainsailDev) — agent instructions

`AGENTS.md` is the canonical instruction file for **every** agent (Claude Code, Codex,
Mistral). `CLAUDE.md` is a symlink to it — edit `AGENTS.md` only, never the symlink.
House rules (git discipline, environments, what never goes in a repo):
see `~/Code/_std/AGENTS.base.md`.

## What this is

A Raspberry Pi OS image that turns a Klipper machine into an embroidery system:
Klipper, Moonraker, a customised Mainsail UI, TurtleStitch, WiFi with AP fallback and
embroidery macros in one flashable image. This folder is the meta-repo.

## Four nested repos — read this before committing

`mainsail/`, `turtlestitch/`, `stitchlabos-config/` and `virtual-klipper-printer/` are
**their own git repositories**, not submodules. A commit here does not capture a change
in them, and `git status` in this folder will not show it.

| Folder | Upstream | Who owns it |
|---|---|---|
| `mainsail/` | mainsail-crew/mainsail | fork, our changes |
| `turtlestitch/` | backface/turtlestitch | fork, our changes |
| `virtual-klipper-printer/` | mainsail-crew | upstream, for testing |
| `stitchlabos-config/` | prntr | ours |

`make status` prints branch and dirty count for all five at once. Commit in the folder
you actually edited.

## Commands

| | |
|---|---|
| `make setup` | `npm ci` in `mainsail/` |
| `make dev` | serve the Mainsail UI locally |
| `make sim` | start the virtual Klipper printer (Docker) |
| `make test` / `make lint` | Mainsail's own test and lint targets |
| `make status` | state of all nested repos |

## The image is not built locally

CustomPiOS builds it on GitHub Actions; pushing a `v*` tag produces the `.img.xz`
release artefact. Do not attempt a local image build.

## What must NOT happen here

- Do not commit changes to the nested repos from this folder.
- Do not pull upstream into the forks without checking our patches first.
