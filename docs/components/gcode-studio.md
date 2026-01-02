# Component: G-Code Studio

## Why this doc exists

There are **two different 2D implementations** in the repository.
This page records which one is currently deployed and how to verify it.

## Current status (verified on dev Pi)

- **Deployed viewer:** Paper.js-based `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`
- **Route wiring:** `mainsail/src/pages/GCodeStudio.vue` mounts `GCodeStudio2D`
- The Handibot canvas viewer remains in tree but is **not** routed
- `/home/pi/mainsail/lib/gcode2dviewer/` may exist on the Pi, but the current bundle does not reference it

## Implementations in tree

### Current: Paper.js based viewer

- Component: `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`
- Notes: see `mainsail/src/components/gcodestudio/AGENTS.md`

### Legacy: Handibot canvas viewer

- Component: `mainsail/src/components/gcodestudio/GCodeStudio2DViewer.vue`
- Library: Handibot-GCode2DViewer in `mainsail/public/lib/gcode2dviewer/` (deployed to Pi in earlier work)

## How to verify on the Pi

The Paper.js build includes PaperScope and does **not** include the Handibot script path.
Run from your local machine:

```bash
ssh pi@stitchlabdev.local "grep -R --line-number --fixed-strings 'PaperScope' /home/pi/mainsail/assets | head -n 1"
ssh pi@stitchlabdev.local "grep -R --line-number --fixed-strings 'gcode2dviewer.js' /home/pi/mainsail/assets | head -n 1"
```

Notes:
- `gcodetogeometry.min.js` is used as a parser by the Paper.js viewer, so its presence alone does not indicate the Handibot viewer is active.
- `gcode2dviewer.js` references in the built assets are the indicator for the Handibot viewer.

## Dates

Some docs list different dates for the same integration. Canonical date should be the actual deployment date.
