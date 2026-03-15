# Component: G-Code Studio

> Two 2D implementations exist in the repo. This page records which is deployed.

## Current Status

| Item | Value |
|------|-------|
| Deployed | Paper.js: `GCodeStudio2D.vue` |
| Route | `pages/GCodeStudio.vue` mounts `GCodeStudio2D` |
| Legacy | Handibot viewer in tree but **not routed** |

## Implementations

### Current: Paper.js

- Component: `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`
- Docs:
  - [agents-notes.md](gcode-studio/agents-notes.md)
  - [repositioning-feature-plan.md](gcode-studio/repositioning-feature-plan.md)

### Legacy: Handibot

- Component: `mainsail/src/components/gcodestudio/GCodeStudio2DViewer.vue`
- Library: `mainsail/public/lib/gcode2dviewer/`
- Status: Not routed, not deployed

## Verify on Pi

```bash
# Paper.js = current (should match)
ssh pi@stitchlabdev.local "grep -l 'PaperScope' /home/pi/mainsail/assets/*"

# Handibot = legacy (should NOT match)
ssh pi@stitchlabdev.local "grep -l 'gcode2dviewer.js' /home/pi/mainsail/assets/*"
```

Note: `gcodetogeometry.min.js` is shared by both viewers (parser).
