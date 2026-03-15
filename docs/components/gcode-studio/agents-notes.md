# GCode Studio 2D (Paper.js) - Agent Notes

Purpose
- This file documents the 2D G-Code Studio implementation so other AI/devs can navigate and extend it quickly.

Scope
- Primary component: `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`
- Related code panel: `mainsail/src/components/gcodeviewer/CodeStream.vue`
- Routes/page wrapper: `mainsail/src/pages/GCodeStudio.vue`

Key flows
- Load file:
  - Local file input -> `loadGcode(text)`
  - Server files via Moonraker -> `loadFile('gcodes/...')`
- Parser:
  - `gcodeToGeometryUrl` script is loaded at runtime.
  - `window.GCodeToGeometry.parse()` returns geometry in inches unless `displayInInch === false`.
  - Normalize line endings + decimal commas.
  - Strip Z on XY moves for geometry, but record Z-only or XY+Z as stitch markers.
- Transform pipeline (preview + export):
  - Preview transforms use `applyDesignTransform()` and `toDesignPoint()`.
  - Export uses `transformGcode()` (offset + rotation, including I/J rotation).
  - Cursor readout is "untransformed" via `reverseDesignTransform()`.
- Rendering:
  - Paper.js layers: grid, frame, path, points, markers.
  - `renderLines` holds parsed line geometry + color.
  - `buildPathItems()` creates Paper.js paths.
  - `updateItemVisibility()` clips to scrub position.
  - `renderStitchPoints()` only draws points for moves marked by Z.
- Playback:
  - Scrub slider uses file offsets for accurate move count.
  - `updatePlaybackPosition()` feeds the toolhead marker during scrub.
  - Left/right arrow steps one move when paused.
- G-Code panel:
  - `CodeStream` is read-only and receives `gcodePanelDocument`.
  - Toggle `showTransformedGcode` switches between original and transformed text.
  - Scrub highlighting is mapped by line index between original/transformed text.
- View fitting:
  - `autoFitView()` fits to the larger of frame/design.
  - Resize uses delayed `scheduleResizeAutoFit()` to avoid jitter.

G-Code conventions used here
- TurtleStitch:
  - Uses Z as stitch markers (not height).
  - Many files use only G0 or only G1.
- Logic:
  - If no G1 moves and some G0 moves, treat G0 as stitches (`treatG0AsStitch`).
  - Stitch points are rendered only at moves followed by Z (or Z-only lines).

Settings keys (store)
- `gui.gcodeStudio.*`
  - `showGrid`, `gridSpacing`, `showJumpStitches`, `showFrameBorder`
  - `showStitchPoints`, `showColorChanges`, `showNeedlePosition`
  - `lineWidth`, `stitchPointSize`
  - `frameWidth`, `frameHeight`, `framePreset`
  - `designOffsetX`, `designOffsetY`, `moveMode`
  - `rotationDeg`, `rotationPivot`
  - `showTransformedGcode`
  - `backgroundColor`, `gridColor`, `frameColor`
  - `stitchColors` (first entry used as default)
- `gui.gcodeViewer.showGCode` controls the code panel toggle.

UI layout
- Current layout: `Canvas | G-Code | Settings`.
- Panels are visually aligned to 500px height.
- Code panel uses CodeMirror read-only mode.
- Settings panel background now uses the theme background color.

Recent changes
- Added transformed export actions:
  - Export (download)
  - Save to Printer (upload to `gcodes/`)
  - Save & Start (upload and `printer.print.start`)
- Added reset offsets button and "Show Transformed G-Code" toggle.
- Added rotation input + pivot selector (Design Center, Frame Center, Origin).
- G-code export now rotates XY and arc I/J, and inserts missing X/Y when rotating.

Common gotchas
- G-Code parser output units: scale by 25.4 when `displayInInch === false`.
- Path and point visibility depend on scrub position (move index).
- Avoid resetting view center on resize; use scheduled auto-fit.
- Keep labels and spacing compact for the settings panel.
- Coordinate system: GCodeStudio2D uses a frame-centered view, but the G-code
  origin is treated as the frame's bottom-left corner. `toDesignPoint` maps
  `(x, y)` from that origin into centered Paper.js coords, with the Y axis
  inverted for display. Drag offsets and cursor readouts are in machine
  coordinates (X right +, Y up +).
- Rotation export assumes absolute XY; it inserts missing axes based on last
  known values (initial default is 0,0).
- I/J rotation is applied for G2/G3; R arcs remain unchanged.

Suggested verification
- Load TurtleStitch and Ink/Stitch files.
- Verify stitch points only appear after Z moves.
- Check scrub play/pause and arrow-key stepping.
- Confirm auto-fit on resize and panel toggles.

Development outlook
- Multi-object workflow: load multiple drawings, per-object transforms, hide/remove.
- Accordion G-code panels per drawing with per-object scrub.
- Combined export with ordering, validation (G90/G91/G92), and bounds checks.
- Stitch-level editing (delete/trim) with undo/redo.
