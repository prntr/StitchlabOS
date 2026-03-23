# 09 — Update Strategy

How StitchLabOS components are developed, released, and updated — both for new images and machines already in the field.

---

## Overview

StitchLabOS is built on top of upstream projects (Klipper, Moonraker, Mainsail, TurtleStitch). Each has a different relationship to our fork and therefore a different update path.

```
┌──────────────────┬──────────────┬───────────────────────────────────────┐
│ Component        │ Source       │ Update mechanism                      │
├──────────────────┼──────────────┼───────────────────────────────────────┤
│ Klipper          │ upstream     │ git pull (Klipper3d/klipper)          │
│ Moonraker        │ upstream     │ git pull (Arksine/moonraker)          │
│ Mainsail UI      │ prntr fork   │ GitHub Release zip download           │
│ TurtleStitch     │ prntr fork   │ git pull (prntr/turtlestitch)         │
│ StitchLAB config │ prntr repo   │ git pull (prntr/stitchlabos-config)   │
└──────────────────┴──────────────┴───────────────────────────────────────┘
```

All five rows appear in the Mainsail update panel. The user clicks Update — Moonraker handles the rest.

---

## Component breakdown

### Klipper and Moonraker — no fork, direct upstream

No customizations in either repo. Deployed machines pull directly from upstream.

- Upstream releases a security fix → update appears in Mainsail panel within 168h (the refresh interval)
- User clicks Update → `git pull` + service restart
- **Nothing for the StitchLAB developer to do**

`moonraker.conf` entries (already in place):

```ini
[update_manager klipper]
type: git_repo
path: ~/klipper
origin: https://github.com/Klipper3d/klipper.git
primary_branch: master
env: ~/klippy-env/bin/python
requirements: scripts/klippy-requirements.txt
install_script: scripts/install-klipper.sh
managed_services: klipper

[update_manager moonraker]
type: git_repo
path: ~/moonraker
origin: https://github.com/Arksine/moonraker.git
primary_branch: master
managed_services: moonraker
```

---

### Mainsail — prntr fork, requires CI to publish releases

Our fork (`prntr/mainsail`, branch `stitchlabos/v2.17.0`) has 5 custom commits on top of the upstream tag:

1. `feat: Add StitchlabOS embroidery customizations` — EmbroideryControlPanel, Dashboard registration
2. `feat(wifi): Add WiFi Manager UI` — TheControllerMenu WiFi menu, SettingsWifiTab, Vuex store
3. `feat(gcode-studio): Add GCode Studio 2D embroidery viewer` — /studio route, canvas viewer, WebSocket plugin
4. `chore: update package-lock.json after v2.17.0 rebase`
5. `docs: add fork notice to README`

Because Mainsail is a pre-built Vue app (a static dist/ zip), the update_manager uses `type: web` which downloads a GitHub Release. This means **`prntr/mainsail` must publish GitHub Releases** with the built dist zip.

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

No action needed. Deployed machines pull from upstream directly.

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

Our 5 custom commits sit on top of an upstream version tag. When upstream releases a new version, they must be rebased onto the new base.

```
mainsail-crew/mainsail

  v2.17.0 ──── v2.18.0  (upstream releases new version)
      │              │
      └──[our 5 commits]    need to move here
                     │
                     └──[our 5 commits rebased]
                            │
                     stitchlabos/v2.18.0  (new branch)
```

#### Automated detection (GitHub Action — to implement)

A scheduled workflow runs weekly on `prntr/mainsail`:

```
1. Fetch latest release tags from mainsail-crew/mainsail
2. Compare against the base version encoded in our current branch name
3. If no new version → exit silently
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
2. GitHub Action detects it (within ~1 week)
3a. Clean rebase → CI builds → PR opened → merge → deployed machines updated
3b. Conflicts → PR opened with details → developer resolves (~15 min) → push → CI builds
```

### Releasing a new StitchLabOS image

```
1. All component forks are at the desired versions
2. git tag v1.2.0 on StitchlabOS/main
3. image build CI triggers:
   - Builds prntr/mainsail from submodule source (`npm ci && npm run build`)
   - Clones prntr/turtlestitch
   - Clones prntr/stitchlabos-config
   - Clones Klipper + Moonraker from upstream
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

## What already works today

- Klipper and Moonraker OTA updates via Mainsail panel ✓
- Mainsail OTA pulls from `prntr/mainsail` fork (first release: `v2.17.0-stitchlab.1`) ✓
- TurtleStitch OTA updates via Mainsail panel ✓
- StitchLabOS config OTA updates via `prntr/stitchlabos-config` ✓
- CI on `prntr/mainsail`: auto-builds and publishes GitHub Release on push to `stitchlabos/*` ✓
- Image build CI on StitchlabOS main ✓
- All Moonraker warnings resolved (polkit, dirty repos, untracked files) ✓
- WiFi AP (Stitchlab / praxistest), SSH (pi/lab), UART for SKR Pico ✓
