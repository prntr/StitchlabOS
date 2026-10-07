# 09 — Update Strategy

How StitchLabOS components are developed, released, and updated — both for new images and machines already in the field.

---

## Overview

StitchLabOS is built on top of upstream projects (Klipper, Moonraker, Mainsail, TurtleStitch). Each has a different relationship to our fork and therefore a different update path.

| Component | Source | Update mechanism |
|---|---|---|
| Klipper | upstream, **pinned per release** | `git`, `pinned_commit` = the release's commit: no update until a release moves the pin |
| Moonraker | upstream, **pinned per release** | as Klipper |
| Mainsail UI | prntr fork | GitHub Release zip download (`v2.17.0-stitchlab.N`) |
| TurtleStitch | prntr fork | `git`, channel **beta**: tagged commits only |
| StitchLAB config | prntr repo | `git`, channel **beta**: tagged commits only |

All five rows appear in the Mainsail update panel. The user clicks Update — Moonraker handles the rest.
The pins live in [`stitchlabos/image/upstream-pins.conf`](../stitchlabos/image/upstream-pins.conf)
(since beta6; wissen D-072). Parts of the image that the panel does not cover are
listed under [Not update-managed](#not-update-managed).

---

## Component breakdown

### Klipper and Moonraker — no fork, pinned per release

No customizations in either repo. Since beta6 each release ships fixed commits
(`KLIPPER_REF`, `MOONRAKER_REF` in `upstream-pins.conf`): CI builds the SKR Pico
firmware from `KLIPPER_REF`, the image clones both at their pins, and
`moonraker.conf` ends with

```ini
[update_manager klipper]
pinned_commit: <KLIPPER_REF>

[update_manager moonraker]
pinned_commit: <MOONRAKER_REF>
```

so the panel offers no Klipper or Moonraker update until a release moves the pin. A
click on Klipper's update used to move the host off the commit the Pico firmware was
built from. Moving a pin means: run `make klipper-drift` (see
[08-image-building.md](08-image-building.md#release-pins-and-the-drift-check)), change
the commit, and name the Pico re-flash (`stitchlab-flash-pico --uart`) in the release
notes when `KLIPPER_REF` moved. Today a new pin reaches machines with a new image
only; see [Not update-managed](#not-update-managed) for the way without a reflash.

Modern Moonraker auto-detects Klipper and itself; the two sections above only
override `pinned_commit`, which Moonraker allows (as `channel` and `refresh_interval`).

> **Note:** Do not add `type: git_repo` entries for klipper or moonraker. Older Moonraker versions required explicit entries, but current versions auto-detect these components. Adding manual entries causes "Unparsed config option" warnings because the built-in updater ignores `git_repo`-specific options.

### Versions and tags

Moonraker names a `git_repo` version after `git describe --tags`. The image used to
clone shallow without tags, so the panel of the 20260927 image read `v0.0.0-1` for
Klipper, Moonraker, TurtleStitch and stitchlabos. Since beta6
`stitchlab-clone-at-ref` deepens each clone to the nearest version tag of the pinned
commit and fetches that tag (Klipper shows `v0.13.0-786-g461c4e37`, Moonraker
`v0.11.0-3-g9e676eba`), and CI ships TurtleStitch with its nearest version tag.

StitchLAB repos carry the release's tag: before tagging `vX` in this repo, tag
`prntr/stitchlabos-config` and `prntr/turtlestitch` with the same `vX` at the commits
this repo pins (the submodule commits). The image build fails early on a release tag
when one is missing and prints the two commands. The tag must be a version Moonraker
can read: `v0.1.0-beta.6` works, `v2.17.0-stitchlab.16` (the Mainsail scheme) does not
for a `git_repo`. With `channel: beta` only tagged commits reach machines; a fix
between images is a new tag in that repo, for example `v0.1.0-beta.7`.

---

### Mainsail — prntr fork, requires CI to publish releases

Our fork (`prntr/mainsail`, branch `stitchlabos/v2.17.0`) has 6 custom commits on top of the upstream tag:

1. `feat: Add StitchlabOS embroidery customizations` — EmbroideryControlPanel, Dashboard registration
2. `feat(wifi): Add WiFi Manager UI` — TheControllerMenu WiFi menu, SettingsWifiTab, Vuex store
3. `feat(gcode-studio): Add GCode Studio 2D embroidery viewer` — /studio route, canvas viewer, WebSocket plugin
4. `chore: update package-lock.json after v2.17.0 rebase`
5. `docs: add fork notice to README`
6. `feat(theme): add StitchLab theme, embroidery preview, temperature panel updates` — Catppuccin CSS, immediate watcher fixes, embroidery preview, temp panel, icons, fonts, sidebar backgrounds

Because Mainsail is a pre-built Vue app (a static dist/ zip), the update_manager uses `type: web` which downloads a GitHub Release. This means **`prntr/mainsail` must publish GitHub Releases** with the built dist zip.

Theme note: the StitchLab theme is **implemented** (Catppuccin Frappé/Latte). See [components/mainsail-theme.md](components/mainsail-theme.md) for details. Theme changes are source-level fork changes like any other.

`moonraker.conf` entry (to replace current `mainsail-crew/mainsail`):

```ini
[update_manager mainsail]
type: web
path: /home/pi/mainsail
repo: prntr/mainsail
channel: stable
persistent_files:
    config.json
```

#### CI on prntr/mainsail

A GitHub Actions workflow on `prntr/mainsail` triggers on push to any `stitchlabos/*` branch (one branch per upstream version):

1. `npm ci && npm run build` — builds the Vue app
2. Creates a GitHub Release tagged `v<upstream-version>-stitchlab.<build>` (e.g. `v2.17.0-stitchlab.3`) — the build number is auto-incremented by querying existing releases matching the current upstream version
3. Attaches the dist zip as a release asset

Moonraker fetches the GitHub releases API for `prntr/mainsail`, compares the latest tag to the installed version, and surfaces the update in the Mainsail panel.

---

### TurtleStitch — prntr fork, no build step needed

Our fork (`prntr/turtlestitch`, branch `master`) has 2 custom commits. The local dev setup uses two remotes: `origin` → `backface/turtlestitch` (upstream) and `fork` → `prntr/turtlestitch`.

1. `feat: StitchLAB Moonraker integration and Klipper gcode export` — project save/load via Moonraker file API, G-code export for Klipper
2. `docs: add fork notice to README`

TurtleStitch is raw JavaScript served directly — no build step. `type: git_repo` does a simple `git pull`.

`moonraker.conf` entry (to add):

```ini
[update_manager turtlestitch]
type: git_repo
path: ~/turtlestitch
origin: https://github.com/prntr/turtlestitch.git
primary_branch: master
managed_services:                   # empty — static JS served by nginx, no service to restart
```

Push to `prntr/turtlestitch` → deployed machines can update immediately. No CI required.

> **Image build note:** `.github/workflows/build-image.yml` currently removes `.git` after copying TurtleStitch into the module filesystem (`rm -rf .../.git`). This must be removed — `type: git_repo` requires `.git` to be present on the installed image for `git pull` to work. Use `cp -r turtlestitch/. <dest>/` (dot, not glob) to include hidden files like `.git`.

---

### StitchLAB config — new repo `prntr/stitchlabos-config`

Runtime files specific to StitchLabOS that have no other home:

- `moonraker/components/wifi_manager.py` — Moonraker component for WiFi API endpoints
- `printer_data/scripts/wifi_status.sh`, `wifi_scan.sh`, `wifi_profiles.sh` — nmcli wrappers
- `printer_data/config/embroidery_macros.cfg` — Klipper macros for needle control

These currently live inside the image build (`stitchlabos` module) but have no OTA update path. Moving them to a dedicated repo gives deployed machines a clickable update path.

`moonraker.conf` entry (to add):

```ini
[update_manager stitchlabos]
type: git_repo
path: ~/stitchlabos-config
origin: https://github.com/prntr/stitchlabos-config.git
primary_branch: main
managed_services: moonraker
```

After update, Moonraker restarts to pick up any changes to `wifi_manager.py`.

#### Setup steps for prntr/stitchlabos-config

> **Status:** `prntr/stitchlabos-config` has been created on GitHub (empty). Steps 2–4 are pending.

1. ~~Create the repo on GitHub as `prntr/stitchlabos-config`~~ ✓ done
2. Move files into it (keeping the same relative paths used on the Pi)
3. Update the image build to clone this repo and symlink files to their expected locations (see below)
4. Add the `[update_manager stitchlabos]` entry to `moonraker.conf`

#### Image build integration detail

The image build (`.github/workflows/build-image.yml`) should clone `prntr/stitchlabos-config` **with `.git` intact** so Moonraker's update_manager can do `git pull` on the installed image. The cloned directory goes to `~/stitchlabos-config`.

Because Moonraker loads components from `~/moonraker/moonraker/components/`, `wifi_manager.py` must be accessible there. Use a symlink — do not copy:

```bash
# In start_chroot_script (stitchlabos module)
ln -sf /home/pi/stitchlabos-config/moonraker/components/wifi_manager.py \
    /home/pi/moonraker/moonraker/components/wifi_manager.py
ln -sf /home/pi/stitchlabos-config/printer_data/config/embroidery_macros.cfg \
    /home/pi/printer_data/config/embroidery_macros.cfg
for script in wifi_status.sh wifi_scan.sh wifi_profiles.sh; do
    ln -sf /home/pi/stitchlabos-config/printer_data/scripts/$script \
        /home/pi/printer_data/scripts/$script
done
```

The symlink at `~/moonraker/moonraker/components/wifi_manager.py` appears as an untracked file in the moonraker git tree — keep the existing `.git/info/exclude` entry for it. Git pull on moonraker leaves untracked symlinks alone, so the link survives moonraker updates.

`wifi_manager.py` does not use `__file__` or any path relative to its own location, so Python's symlink-following has no functional impact.

---

## Upstream sync — how upstream changes reach the prntr forks

### Moonraker and Klipper

Nothing reaches deployed machines by itself (pinned). The weekly drift check
(`.github/workflows/klipper-drift.yml`, also on every release tag) runs our configs
and sample jobs at the pin and at upstream master and lists the upstream commits
that touch the G-code path; read its report before moving a pin.

### TurtleStitch

Upstream (`backface/turtlestitch`) changes infrequently. When an update is needed:

```bash
cd turtlestitch
git fetch origin          # origin = backface/turtlestitch
git rebase origin/master  # replay our 2 commits on top of latest upstream
git push fork master      # fork = prntr/turtlestitch
```

Conflict risk is medium — upstream may touch `src/gui.js` where our Moonraker integration lives. Typically a 15–30 minute job.

### Mainsail — the main process

Our 6 custom commits sit on top of an upstream version tag. When upstream releases a new version, they must be rebased onto the new base.

```
mainsail-crew/mainsail

  v2.17.0 ──── v2.18.0  (upstream releases new version)
      │              │
      └──[our 6 commits]    need to move here
                     │
                     └──[our 6 commits rebased]
                            │
                     stitchlabos/v2.18.0  (new branch)
```

#### Upstream detection (GitHub Action — to implement)

Detection is **not** scheduled. It runs on demand — triggered when the developer manually dispatches the workflow or when a new image build is started. The workflow on `prntr/mainsail`:

```
1. Fetch latest release tags from mainsail-crew/mainsail
2. Compare against the base version encoded in our current branch name
3. If no new version → continue with the current branch as-is
4. If new version found (e.g. v2.18.0):
   a. Create branch stitchlabos/v2.18.0 from upstream v2.18.0 tag
   b. Attempt: git rebase --onto v2.18.0 v2.17.0 stitchlabos/v2.17.0
   c. Clean rebase → push branch, CI builds, open auto-merge PR
      Conflict    → open PR with conflict details and resolution instructions
```

#### Conflict likelihood

| Upstream change | Conflict risk | Typical cause |
|----------------|---------------|---------------|
| Security patch (v2.17.0 → v2.17.1) | Low | Touches auth, API, deps — rarely our files |
| Minor feature release (v2.17.x → v2.18.0) | Medium | New UI may touch Dashboard.vue, locales, store |
| Major version (v2.x → v3.0) | High | Could restructure the codebase |

**High-conflict files** (our changes overlap with files upstream actively develops):

- `src/pages/Dashboard.vue` — we registered EmbroideryControlPanel here
- `src/components/TheControllerMenu.vue` — we added the WiFi menu here
- `src/locales/en.json` — we added translation strings here

For a typical security patch, these files are rarely touched. The rebase is clean ~80% of the time.

#### Manual conflict resolution (the 20%)

```bash
# GitHub Action opened a PR with conflicts — check it out locally
git fetch fork
git checkout stitchlabos/v2.18.0

# Rebase our commits onto the new upstream base
git rebase upstream/v2.18.0

# Fix any conflicts (usually 1-2 files, ~15 min for a security patch)
# ... edit conflicted files ...
git add <resolved files>
git rebase --continue

# Push — CI picks it up, builds, creates GitHub Release
git push fork stitchlabos/v2.18.0
```

Once pushed, CI builds the dist, creates a GitHub Release, and deployed machines see the update in their Mainsail panel.

---

## Full development + deployment cycle

### Making a StitchLAB-specific change (e.g. fixing the WiFi Manager UI)

```
1. Edit code in prntr/mainsail (src/components/settings/SettingsWifiTab.vue etc.)
2. git push → prntr/mainsail (branch: stitchlabos/v2.17.0)
3. CI builds Vue app (~5 min)
4. CI creates GitHub Release v2.17.0-stitchlab.N
          │
          ├─ Deployed machines: update appears in Mainsail panel
          │  User clicks Update → Moonraker downloads zip → done
          │
          └─ New images: pick up the change on next image build (tag push)
```

### Pulling an upstream Mainsail security fix

```
1. Upstream releases v2.17.1
2. Developer triggers the upstream-check workflow (manual dispatch or as part of an image build)
3a. Clean rebase → CI builds → PR opened → merge → deployed machines updated
3b. Conflicts → PR opened with details → developer resolves (~15 min) → push → CI builds
```

### Releasing a new StitchLabOS image

```
1. All component forks are at the desired versions; run make klipper-drift
2. Tag prntr/stitchlabos-config and prntr/turtlestitch with v1.2.0 at the pinned
   submodule commits, push both tags
3. git tag v1.2.0 on StitchlabOS/main
3. image build CI triggers:
   - Builds prntr/mainsail from submodule source (`npm ci && npm run build`)
   - Clones prntr/turtlestitch
   - Clones prntr/stitchlabos-config
   - Clones Klipper + Moonraker at the pins in upstream-pins.conf
   - Packages into StitchLabOS-v1.2.0.img.xz
4. GitHub Release created with image artifact
```

---

## Implementation checklist

These items enable the full OTA update path:

- [x] **CI on `prntr/mainsail`** — GitHub Actions workflow that builds the Vue app and publishes a GitHub Release on push to `stitchlabos/*` branch (`stitchlab-release.yml`)
- [x] **Fix `moonraker.conf`** — changed `repo: mainsail-crew/mainsail` → `repo: prntr/mainsail` so deployed machines pull from our fork
- [x] **Add TurtleStitch update_manager entry** to `moonraker.conf`
- [x] **Add stitchlabos-config update_manager entry** to `moonraker.conf`; image build clones `prntr/stitchlabos-config` and creates symlinks
- [x] **Upstream sync GitHub Action** — weekly check on `prntr/mainsail` for new upstream Mainsail releases; auto-opens rebase PR (`upstream-sync.yml`)
- [x] **Update image build CI** — TurtleStitch `.git` preserved for update_manager; stitchlabos module clones `stitchlabos-config` in chroot

### Optional: upstream sync secret

- [ ] **Add `PAT` secret to `prntr/mainsail`** — the `upstream-sync.yml` workflow needs a Personal Access Token to push new branches (e.g. `stitchlabos/v2.18.0`). Without it, the weekly upstream check runs but fails at the push step. Everything else (release builds, OTA updates) works without it. To set up later: GitHub → Settings → Developer settings → Fine-grained tokens → scope to `prntr/mainsail` with Contents read/write → add as repo secret named `PAT` at `prntr/mainsail/settings/secrets/actions`.

---

## Not update-managed

What the image installs outside the five panel rows, and the proposed path
(status beta6, 2026-10-07; nothing in this table moves with an update today):

| Part | Where on the Pi | Proposed path |
|---|---|---|
| G-code intake (core, CLI, venv) | `/home/pi/stitchlab_intake`, `/usr/local/bin/stitchlab-gcode-intake` | Move into `stitchlabos-config` next to its Moonraker wrapper, venv via the update_manager `virtualenv`/`requirements` options. Today a config update can change the wrapper while the core stays at the image's version |
| `stitchlab_ws_tuning.py` (Moonraker component) | `/usr/local/lib/stitchlabos/moonraker/` | Move into `stitchlabos-config/moonraker/components/`, like `wifi_manager.py` |
| `live_jogd` (daemon, venv, unit, udev rule) | `/home/pi/live_jogd`, `/etc/systemd/system/live_jogd.service` | Own repo or `stitchlabos-config` subfolder with `managed_services: live_jogd` (already in `moonraker.asvc`); unit and udev rule stay image files |
| Pico tools `stitchlab-flash-pico`, `stitchlab-uf2-clear-app` | `/usr/local/bin` | Into `stitchlabos-config/bin`, linked like the Wi-Fi scripts |
| SKR Pico firmware | `/home/pi/firmware/` | Changes only when `KLIPPER_REF` moves. Moving the pin without a reflash needs the firmware too: a `zip`-type update_manager entry on this repo's release assets, or pins only move with images (today) |
| Klipper/Moonraker pins | `moonraker.conf` (image seed) | Move the two `[update_manager …] pinned_commit` sections into an include from `stitchlabos-config`, so a tagged config release can move the pin (with the firmware above) |
| `mainsail-config` (`mainsail.cfg`) | `/home/pi/mainsail-config`, pinned `MAINSAIL_CONFIG_REF` | Keep pinned: the machine's PAUSE/RESUME replace its macros. Optionally an update_manager row with `pinned_commit` to show its version |
| Image scripts and system files (Avahi, sshd, nginx sites, sysctl, systemd drop-ins, sudoers, `stitchlab-first-boot-name`, `stitchlab-configure-avahi`, `stitchlab-clone-at-ref`) | `/etc`, `/usr/local` | Stay image-only: they need root or run once at build or first boot |
| `printer.cfg`, `moonraker.conf` | `~/printer_data/config` | User-owned seeds; the variant part of `printer.cfg` is wissen D-073 |
| KIAUH, AccessPopup | `/home/pi/kiauh`, `/home/pi/AccessPopup` | Leave as is |

`[update_manager stitchlabos]` has `managed_services:` empty, so a config update loads
new macros and Moonraker components only after the next Klipper or Moonraker
restart. `managed_services: klipper moonraker` would restart both after an update;
check on a machine that Moonraker refuses the update while a job runs before
changing it.

## What already works today

- Klipper and Moonraker in the Mainsail panel with real versions, pinned to the release (beta6) ✓
- Mainsail OTA pulls from `prntr/mainsail` fork (latest release: `v2.17.0-stitchlab.2`) ✓
- TurtleStitch OTA updates via Mainsail panel, tagged releases only (channel beta) ✓
- StitchLabOS config OTA updates via `prntr/stitchlabos-config`, tagged releases only (channel beta) ✓
- CI on `prntr/mainsail`: auto-builds and publishes GitHub Release on push to `stitchlabos/*` ✓
- Image build CI on StitchlabOS main ✓
- All Moonraker warnings resolved (polkit, dirty repos, untracked files) ✓
- WiFi AP (Stitchlab / praxistest), SSH (pi/lab), UART for SKR Pico ✓
