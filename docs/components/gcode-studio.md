# Component: G-Code Studio

> Two 2D implementations exist in the repo. This page records which is deployed.

## Current Status

| Item                 | Value                                                |
| -------------------- | ---------------------------------------------------- |
| Deployed             | Paper.js: `GCodeStudio2D.vue`                        |
| Route                | `pages/GCodeStudio.vue` mounts `GCodeStudio2D`       |
| Code panel           | `CodemirrorAsync` (reuses the main editor component) |
| StitchLab theme pass | Implemented                                          |
| Legacy               | Handibot viewer in tree but **not routed**           |

## Features

### G-Code Editor (Edit Mode)

The code panel doubles as an interactive G-Code editor. Toggled via the **pencil icon** in the toolbar.

- **Read-only by default** — syntax-highlighted G-Code view with scrubber sync.
- **Edit mode** — full CodeMirror 6 editing (add/delete/modify lines). Canvas re-renders after a 400 ms debounce. Scrub position is preserved (clamped, not reset) during edits.
- **Three visual states** — `source`, `edit`, and `transformed` each get distinct viewer/editor chrome. Edit mode uses Peach accents; transformed preview uses Sapphire chrome with neutral line numbers.
- **G-Code-specific syntax** — commands, line numbers, program numbers, axis word groups, feed/tool/spindle words, variables, and comments are tokenized as G-Code rather than generic code.
- **Sync guards** — `isSyncingEditor` flag and user-event filtering in CodeMirror prevent feedback loops between scrubber and editor.
- **Option A design** — edit mode disables all transforms (offset, rotation, move mode) to avoid bidirectional sync complexity. Users work on raw G-Code; the canvas shows exactly what's in the editor.
- **Dirty tracking** — SHA-256 hash comparison; panel title shows `*` when unsaved.
- **Save actions** — Export (download), Save to Printer (upload), Save & Start (upload + print). Saved files get an `_edited` suffix.
- **Discard dialog** — on exit from edit mode with unsaved changes, offers Discard / Keep Changes / Keep Editing.

### Design Repositioning

Non-destructive offset + rotation transforms with export. See [repositioning-feature-plan.md](gcode-studio/repositioning-feature-plan.md).

### Preview Styling And Defaults

- **Default stitch geometry** — stitch path width defaults to `0.1 mm`; stitch point size defaults to `0.2 mm`.
- **Point size semantics** — the stitch point control is treated as a visible dot diameter, not a radius.
- **Hierarchy** — stitch paths are intentionally finer than embroidery yarn at real scale; travel/jump stitches render thinner, dashed, and lower-opacity than stitch paths.
- **Needle marker** — the crosshair is intentionally thin in both Studio and the small status preview to avoid overpowering the design.
- **Theme-aware palette** — when the StitchLab theme is active, the Paper.js preview and code panel use the shared StitchLab/Catppuccin palette from `variables.ts` and `stitchlab.css`.

## Implementations

### Current: Paper.js

- Component: `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`
- Editor: `mainsail/src/components/inputs/Codemirror.vue` (via `CodemirrorAsync`)
- Syntax parser: `mainsail/src/plugins/StreamParserGcode.ts`
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
