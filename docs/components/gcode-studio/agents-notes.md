# GCode Studio 2D (Paper.js) - Agent Notes

Purpose

- This file documents the 2D G-Code Studio implementation so other AI/devs can navigate and extend it quickly.

Scope

- Primary component: `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`
- Code panel / editor: `mainsail/src/components/inputs/Codemirror.vue` (via `CodemirrorAsync`)
- G-Code syntax parser: `mainsail/src/plugins/StreamParserGcode.ts`
- Routes/page wrapper: `mainsail/src/pages/GCodeStudio.vue`
- Note: `CodeStream.vue` is still used by the 3D Viewer (`/viewer`), not by Studio.

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
- G-Code panel / editor:
  - Uses `CodemirrorAsync` (lazy-loaded `Codemirror.vue`) with GCode syntax highlighting.
  - Read-only by default; becomes editable when edit mode is toggled (pencil icon).
  - Mode classes split the panel into `source`, `edit`, and `transformed` states.
    `edit` uses Peach chrome; `transformed` uses Sapphire chrome but keeps line
    numbers neutral (`Overlay1`) so the gutter does not compete with syntax colors.
  - `gcodePanelDocument` computed returns: editedGcode in edit mode, transformed in
    transform mode, or raw original otherwise.
  - `:key="editMode ? 'edit' : 'view'"` forces component remount on mode toggle
    to ensure CodeMirror readOnly state is fresh.
  - Scrub position syncs to editor via `scrollEditorToScrubPosition()` calling `gotoLine()`.
    Uses `panelLineBreakOffsets` + `gcodePanelPosition` for correct line mapping.
    Sets `isSyncingEditor` flag to prevent feedback loops.
  - Editor line clicks sync back via `onEditorLineChange()` → maps line number to
    byte offset via `panelLineBreakOffsets`, then uses `gcodePanelPosition` setter
    for transform-aware scrub position update. Guarded by `isSyncingEditor`.
  - `Codemirror.vue` only emits `lineChange` for user-initiated selections
    (`tr.isUserEvent()`) and only emits `input` when `update.docChanged`.
  - `StreamParserGcode.ts` now emits G-code-specific token groups:
    - `G`/`M` commands
    - `N` line numbers and `O` program numbers
    - axis families (`X/U/A/I`, `Y/V/B/J`, `Z/W/C/K`, `E`)
    - feed/tool/spindle words (`F`, `T`, `S`)
    - parameter words (`P/Q/R/H/L/D`)
    - `#` variables
    - `;` and `(...)` comments
  - Edit mode disables transforms (Option A) to avoid bidirectional sync.
  - `gcodePanelPosition` getter/setter short-circuits in edit mode.
  - Edits trigger debounced re-parse (400 ms) updating the Paper.js canvas.
    Scrub position is clamped (`Math.min`) instead of reset to end.
  - Dirty state tracked via SHA-256 hash of original vs edited content.
- Theme / visual hierarchy:
  - StitchLab theme uses a dedicated Studio palette from `variables.ts`.
  - Main preview background and small status preview background are intentionally
    darker than the surrounding cards to improve stitch contrast.
  - Default stitch geometry is fine: `lineWidth = 0.1 mm`, `stitchPointSize = 0.2 mm`.
  - Stitch point size is interpreted as dot diameter, not radius.
  - Travel/jump stitches render thinner, dashed, and semi-transparent.
  - Needle crosshairs are intentionally thin in both Studio and status preview.
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
  - `lineWidth`, `stitchPointSize` (defaults: `0.1`, `0.2`)
  - `frameWidth`, `frameHeight`, `framePreset`
  - `designOffsetX`, `designOffsetY`, `moveMode`, `editMode`
  - `rotationDeg`, `rotationPivot`
  - `showTransformedGcode`
  - `backgroundColor`, `gridColor`, `frameColor`
  - `stitchColors` (first entry used as default)
- `gui.gcodeViewer.showGCode` controls the code panel toggle.

UI layout

- Current layout: `Canvas | G-Code | Settings`.
- Panels are visually aligned to 500px height.
- Code panel uses CodemirrorAsync (read-only by default, editable in edit mode).
- Settings panel background now uses the theme background color.
- Edit mode adds an "Edit G-Code" expansion panel with save/export buttons.
- Transform controls collapse to full-width fields in the narrow two-column settings layout to avoid clipped values.

Recent changes

- Replaced CodeStream with CodemirrorAsync for the code panel.
- Added edit mode (pencil icon toggle) with full CodeMirror editing.
  - Edit mode disables transforms (Option A design).
  - Debounced re-parse + re-render on edits (400 ms).
  - Save actions: Export Edited, Save to Printer, Save & Start.
  - Dirty state via SHA-256, discard dialog on exit.
- Added `readonly` prop to `Codemirror.vue` for toggling read-only mode.
- Added scrubber-to-editor scroll sync via `scrollEditorToScrubPosition()`.
- Added G-code-specific syntax highlighting in `StreamParserGcode.ts` with CM6 `HighlightStyle` classes.
- Added editor/viewer mode accents for source vs edit vs transformed states.
- Fixed scrubber/editor sync bugs (jump-to-end issues):
  - `Codemirror.vue`: `lineChange` only emits on user events; `input` only on `docChanged`.
  - `isSyncingEditor` flag prevents feedback loop between scrubber and editor.
  - `onEditorLineChange` maps via `panelLineBreakOffsets` (not `moveOffsets` index).
  - `gcodePanelPosition` getter/setter short-circuits in edit mode.
  - `debouncedReparse` clamps scrub position instead of resetting to file end.
- Added transformed export actions:
  - Export (download)
  - Save to Printer (upload to `gcodes/`)
  - Save & Start (upload and `printer.print.start`)
- Added reset offsets button and "Show Transformed G-Code" toggle.
- Added rotation input + pivot selector (Design Center, Frame Center, Origin).
- G-code export now rotates XY and arc I/J, and inserts missing X/Y when rotating.
- Added StitchLab theme-aware preview/code backgrounds and shared Studio palette.
- Reduced stitch point and cursor-marker visual weight; defaults now target embroidery-scale lines and dots.

Common gotchas

- G-Code parser output units: scale by 25.4 when `displayInInch === false`.
- Path and point visibility depend on scrub position (move index).
- Avoid resetting view center on resize; use scheduled auto-fit.
- Keep labels and spacing compact for the settings panel.
- Editor ↔ scrubber sync: `moveOffsets[]` is indexed by move index (skips comments/
  blanks/Z-only lines), while editor line numbers count all lines. Never use editor
  line numbers as direct indices into `moveOffsets`. Use `panelLineBreakOffsets` to
  convert line numbers to byte offsets, then `gcodePanelPosition` for transform mapping.
- Programmatic `gotoLine()` fires CM `updateListener` with `selectionSet`. Always
  gate `lineChange` emission on `isUserEvent()` to prevent feedback loops.
- When reparsing after edits, clamp `scrubPosition` instead of resetting to `scrubFileSize`
  to avoid jumping the canvas/slider to the end on every keystroke.
- `stitchPointSize` is a visible diameter in mm, not a Paper.js radius. If dots look
  too large, check the conversion before changing defaults.
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
- Toggle edit mode: verify readonly disables, syntax highlighting shows, typing works.
- In StitchLab theme, verify source/edit/transformed states have distinct chrome and neutral transformed line numbers.
- Check G-code-specific syntax colors: commands, axis families, `F/S/T`, line numbers, and comments.
- Edit a coordinate, confirm canvas re-renders after ~400 ms.
- Verify default stitch path/point sizes feel fine-grained rather than chunky.
- Verify scrubber play scrolls the editor in both read-only and edit modes.
- Export edited G-Code and verify content matches edits.
- Toggle edit mode off with dirty state — confirm discard dialog appears.

Development outlook

- Phase 2 editing: click stitch on canvas → jump to that line in editor (canvas→editor sync).
- Phase 3 editing: drag stitch points on canvas → update coordinates in editor (bidirectional).
- Unified undo/redo across text edits and canvas transforms.
- GCode line validation (highlight invalid commands).
- Multi-object workflow: load multiple drawings, per-object transforms, hide/remove.
- Accordion G-code panels per drawing with per-object scrub.
- Combined export with ordering, validation (G90/G91/G92), and bounds checks.
- Stitch-level editing (delete/trim) with undo/redo.
