# StitchLabOS (MainsailDev) — agent instructions

`AGENTS.md` is the canonical instruction file for **every** agent (Claude Code, Codex,
Mistral). `CLAUDE.md` is a symlink to it — edit `AGENTS.md` only, never the symlink.

<!-- BEGIN _STD:SHARED_REFERENCES -->
## Shared references

Before changing this project, read both shared sources:

- Code layout and house rules: `~/Code/_std/AGENTS.base.md`
- Cross-project delivery pipeline: `~/Code/active/plattform/pipeline.md`

This managed block is checked by `~/Code/_std/bin/agents-doctor`; keep its markers intact.
<!-- END _STD:SHARED_REFERENCES -->

## What this is

A Raspberry Pi OS image that turns a Klipper machine into an embroidery system:
Klipper, Moonraker, a customised Mainsail UI, TurtleStitch, WiFi with AP fallback,
embroidery macros and the SKR Pico's own firmware in one flashable image. This folder
is the meta-repo; the GitHub remote is `prntr/StitchlabOS`.

The folder name is historical. This is not a Mainsail development checkout.

## Where this sits

StitchLAB is more than this repo. [`docs/00-ecosystem.md`](docs/00-ecosystem.md) maps
every related project and says which one a given change belongs in;
[`docs/10-roadmap.md`](docs/10-roadmap.md) says where the whole thing is going —
including `OpenRSS`, the planned replacement for this software stack.

Read those two before proposing work that spans repos.

## Three submodules and one plain clone — check before committing

| Folder | Kind | Upstream | Who owns it |
|---|---|---|---|
| `mainsail/` | **submodule** | mainsail-crew/mainsail | fork, our changes |
| `turtlestitch/` | **submodule** | backface/turtlestitch | fork, our changes |
| `stitchlabos-config/` | **submodule** | prntr | ours |
| `virtual-klipper-printer/` | plain clone, gitignored | mainsail-crew | upstream, for testing |

The three submodules are registered in `.gitmodules` and CI checks them out with
`submodules: recursive`. A commit here records only the submodule *pointer*, never the
content — the actual change has to be committed inside that folder and pushed, or the
next CI build uses the old commit.

`virtual-klipper-printer/` is genuinely outside version control here.

`make status` prints branch and dirty count for all five at once. Commit in the folder
you actually edited.

## Commands

| | |
|---|---|
| `make setup` | `npm ci` in `mainsail/` |
| `make dev` | serve the Mainsail UI locally |
| `make sim` | start the virtual Klipper printer (Docker) |
| `make test` | Mainsail's Cypress E2E suite — slow, needs a browser |
| `make lint` | Mainsail's linter + dead links in `docs/` |
| `make check` | `lint` + `test` — the gate before any commit |
| `make status` | state of all nested repos |

## The image is not built locally

CustomPiOS builds it on GitHub Actions; pushing a `v*` tag produces the `.img.xz`
release artefact plus `os_list.json` and the SKR Pico firmware. Do not attempt a local
image build. Build details: [`docs/08-image-building.md`](docs/08-image-building.md).

## Two things that silently break a release

**Every module must be listed in `MODULES`.** A module directory under
`stitchlabos/image/src/modules/` that is not named in
`stitchlabos/image/src/config` is simply never built. Beta1 shipped a
`moonraker.conf` pointing at a CLI from a module that was not in the list.

**Every published URL must resolve.** Beta1's `os_list.json` referenced an asset
name that was never uploaded. `os_list.json` is now generated per release from
`os_list.template.json`, and the workflow's last step fails the build if any
published URL returns something other than 200. Do not reintroduce a checked-in
`os_list.json`.

**Every tag is a regular release, never a prerelease.** GitHub excludes
prereleases from `/releases/latest/`, and README, docs and `os_list.json` users
depend on `releases/latest/download/os_list.json`. Beta1 was a prerelease and
that URL was a 404 for months. The workflow pins `prerelease: false` on purpose.

## What must NOT happen here

- Do not commit changes to the nested repos from this folder.
- Do not pull upstream into the forks without checking our patches first.
- Do not commit firmware binaries. `firmware/skr-pico/*.config` are the sources;
  CI builds the `.bin`/`.uf2` and `.gitignore` keeps them out.
