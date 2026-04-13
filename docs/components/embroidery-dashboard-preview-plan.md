# Embroidery Dashboard Preview — Implementation Plan

## Problem

The Mainsail Dashboard **Status Panel** shows a static slicer-generated PNG thumbnail (designed for 3D printing). For embroidery this image is meaningless — it doesn't show the stitch pattern, the embroidery frame, or the live needle position.

## Goal

Replace/augment the thumbnail area with a **live 2D embroidery preview** that shows:
1. The stitch design rendered from the loaded G-Code
2. The embroidery frame boundary
3. The current needle position (live, during stitching)
4. Progress — stitches already sewn vs. remaining

Inspired by **GCode Studio 2D** (`GCodeStudio2D.vue`), which already does all of this in a full-page editor context.

---

## Existing Assets to Reuse

| Asset | Location | What it does |
|-------|----------|-------------|
| G-Code parser | `src/lib/gcode2dviewer/gcodetogeometry.min.js` | Parses G-Code → geometry lines with start/end points |
| Stitch detection | `GCodeStudio2D.vue` `buildPathItems()` | Z-only moves = stitch markers; `treatG0AsStitch` fallback |
| Frame presets | `GCodeStudio2D.vue` data | 4×4, 5×7, 6×10, 8×8, 8×12 inch frames |
| Coordinate transform | `GCodeStudio2D.vue` `toDesignPoint()` / `applyDesignTransform()` | Maps G-Code coords → centered canvas coords |
| Vuex settings | `gui.gcodeStudio.*` | `frameWidth`, `frameHeight`, `designOffsetX/Y`, colors |
| Toolhead position | `store.state.printer.toolhead.position` | Live [X, Y, Z, E] from Klipper |
| File position | `store.state.printer.virtual_sdcard.file_position` | Current byte offset in G-Code file |
| Current file metadata | `store.state.printer.current_file` | Filename, thumbnails, etc. |

---

## Architecture

### Option A — Lightweight `<canvas>` component (Recommended)

Create a small, self-contained **`EmbroideryPreview.vue`** that renders to a `<canvas>` element using the native Canvas 2D API (no Paper.js dependency). This keeps the dashboard lightweight and avoids loading the full GCode Studio bundle.

### Option B — Paper.js mini-instance

Reuse Paper.js (already bundled for GCode Studio) in a read-only mode. Heavier, but closer code reuse.

**Recommendation: Option A.** The preview is read-only and small (~200px tall). Canvas 2D is sufficient and avoids the Paper.js overhead. The parsing logic (`GCodeToGeometry`) is the same either way.

---

## Component Design

### New component: `EmbroideryPreview.vue`

**Location:** `src/components/panels/Status/EmbroideryPreview.vue`

```
┌─────────────────────────────────────────┐
│  ╔═══════════════════════╗  ← frame     │
│  ║   ╱╲    ╱╲   ╱╲      ║  ← design    │
│  ║  ╱  ╲  ╱  ╲ ╱  ╲     ║              │
│  ║ ╱    ╲╱    ╳    ╲    ║              │
│  ║        ●              ║  ← needle    │
│  ╚═══════════════════════╝              │
│  Stitch 142 / 380 · 37%                │
└─────────────────────────────────────────┘
```

**Responsibilities:**

1. **On file load** — Fetch the active G-Code file from Moonraker, parse with `GCodeToGeometry`, extract geometry lines
2. **Render (static)** — Draw the frame rectangle and all stitch paths on canvas
3. **Render (live)** — Highlight completed stitches (solid) vs. remaining (faded), draw needle marker at current toolhead X/Y
4. **Reactivity** — Watch `printer.toolhead.position` and `virtual_sdcard.file_position` for live updates; re-render only the progress overlay (not full re-parse)

### Data Flow

```
printer.print_stats.filename (changes)
  → fetch /server/files/gcodes/{filename} (raw G-Code text)
  → GCodeToGeometry.parse(gcode)
  → store parsed geometry in component data
  → initial canvas render (frame + full design in faded color)

printer.virtual_sdcard.file_position (updates every ~250ms)
  → map file_position → move index (binary search on line offsets)
  → re-draw: completed moves in solid color, remaining in faded
  → update stitch counter text

printer.toolhead.position (updates every ~250ms)
  → draw needle marker dot at [X, Y] mapped to canvas coords
```

---

## Implementation Steps

### Phase 1 — Static Preview (MVP)

1. **Extract shared parsing logic** into a utility module  
   `src/lib/embroideryPreview/parseEmbroideryGcode.ts`
   - Import and call `GCodeToGeometry.parse()`
   - Apply `treatG0AsStitch` heuristic (from GCodeStudio2D)
   - Return: `{ lines: GeometryLine[], bounds: {min, max}, stitchCount: number }`

2. **Create `EmbroideryPreview.vue`**
   - `<canvas>` element, height ~200px, responsive width
   - Props: none (reads from Vuex store directly)
   - Computed: `currentFilename` from `printer.print_stats.filename`
   - Watch `currentFilename` → fetch G-Code → parse → render
   - Render pipeline:
     - Calculate scale/translate to fit design + frame in canvas
     - Draw frame rectangle (dashed border, from `gui.gcodeStudio.frameWidth/Height`)
     - Draw stitch paths (colored lines between consecutive XY moves)
     - Draw stitch points (small dots at Z-marked positions)

3. **Integrate into `StatusPanel.vue`**
   - Replace `<status-panel-printstatus-thumbnail />` with conditional:
     - If embroidery mode → `<embroidery-preview />`
     - Else → existing `<status-panel-printstatus-thumbnail />`
   - Detection heuristic: the G-Code file contains embroidery markers (Z-only stitch moves) OR a config flag `gui.gcodeStudio` settings exist

4. **Add l10n keys** to `locales/en.json` under a new `EmbroideryPreview` section

### Phase 2 — Live Progress

5. **Map file position → move index**
   - During parse, record the byte offset of each G-Code line (from parser metadata)
   - On `virtual_sdcard.file_position` change, binary-search to find current move index
   - Split canvas rendering into two layers:
     - Bottom layer: full design in faded/ghost color
     - Top layer: completed stitches in solid color (up to current move)

6. **Needle position marker**
   - Watch `printer.toolhead.position` → extract X, Y
   - Draw a small crosshair / circle at the mapped canvas position
   - Pulse animation optional (CSS or requestAnimationFrame)

7. **Stitch counter overlay**
   - Text below or overlaid on canvas: "Stitch 142 / 380 · 37%"
   - Uses the move-index from step 5 and total stitch count from parse

### Phase 3 — Polish & Settings

8. **User settings** (reuse existing `gui.gcodeStudio` where possible)
   - Frame preset selector (already exists in GCode Studio settings)
   - Show/hide frame border, stitch points, jump stitches
   - Color scheme (completed color, remaining color, frame color)

9. **Performance guard-rails**
   - Throttle canvas redraws to ~4 fps during active stitching
   - For very large designs (>10k stitches), simplify rendering (skip stitch point dots, reduce path segments via Douglas-Peucker)
   - Lazy-load the GCodeToGeometry parser script (already done via dynamic `<script>` in GCodeStudio2D)

10. **Fallback behavior**
    - If G-Code fetch fails or parse returns no geometry → fall back to existing PNG thumbnail
    - If frame dimensions are not configured → show design without frame border + info tooltip

---

## File Changes Summary

| File | Action |
|------|--------|
| `src/lib/embroideryPreview/parseEmbroideryGcode.ts` | **New** — shared parsing utility |
| `src/components/panels/Status/EmbroideryPreview.vue` | **New** — canvas-based preview component |
| `src/components/panels/StatusPanel.vue` | **Edit** — conditionally render EmbroideryPreview |
| `src/components/panels/Status/PrintstatusThumbnail.vue` | **Edit** — minor: add slot/flag for embroidery mode |
| `src/store/gui/gcodeStudio/index.ts` | **Edit** — possibly expose frame settings as getters |
| `src/locales/en.json` | **Edit** — add `EmbroideryPreview.*` keys |

---

## Open Questions

1. **Detection heuristic** — How do we know the loaded file is embroidery vs. 3D printing? Options:
   - (a) Always show embroidery preview on StitchLab theme (`defaultTheme === 'stitchlab'`)
   - (b) Sniff the G-Code for Z-only stitch patterns during parse
   - (c) User toggle in settings
   - **Recommendation:** (a) for now — simplest, and this fork is embroidery-specific

2. **G-Code file size** — Embroidery files can be large. Should we:
   - (a) Fetch full file every time
   - (b) Cache parsed geometry per filename+modified timestamp
   - **Recommendation:** (b) — cache in component data, invalidate on filename change

3. **Frame offset syncing** — Should the dashboard preview reflect `designOffsetX/Y` from GCode Studio? 
   - **Recommendation:** Yes — read from `gui.gcodeStudio` store. This way if the user repositioned in GCode Studio and started the job, the preview matches.

---

## Sketch of Key Rendering Logic

```typescript
// Simplified canvas rendering (Phase 1)
function renderPreview(
  ctx: CanvasRenderingContext2D,
  geometry: ParsedGeometry,
  frame: { width: number; height: number },
  offset: { x: number; y: number },
  canvasSize: { w: number; h: number }
) {
  const { lines, bounds } = geometry
  
  // Calculate scale to fit frame in canvas with padding
  const padding = 16
  const scaleX = (canvasSize.w - padding * 2) / frame.width
  const scaleY = (canvasSize.h - padding * 2) / frame.height
  const scale = Math.min(scaleX, scaleY)
  
  // Center in canvas
  const cx = canvasSize.w / 2
  const cy = canvasSize.h / 2

  // Draw frame
  ctx.strokeStyle = '#666'
  ctx.setLineDash([4, 4])
  ctx.strokeRect(
    cx - (frame.width * scale) / 2,
    cy - (frame.height * scale) / 2,
    frame.width * scale,
    frame.height * scale
  )
  ctx.setLineDash([])

  // Draw stitch paths
  ctx.strokeStyle = '#e53935'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  for (const line of lines) {
    const from = toCanvas(line.start, frame, offset, scale, cx, cy)
    const to = toCanvas(line.end, frame, offset, scale, cx, cy)
    ctx.moveTo(from.x, from.y)
    ctx.lineTo(to.x, to.y)
  }
  ctx.stroke()
}

function toCanvas(
  pt: { x: number; y: number },
  frame: { width: number; height: number },
  offset: { x: number; y: number },
  scale: number, cx: number, cy: number
): { x: number; y: number } {
  // G-Code origin is frame bottom-left → center
  return {
    x: cx + (pt.x + offset.x - frame.width / 2) * scale,
    y: cy - (pt.y + offset.y - frame.height / 2) * scale  // Y inverted
  }
}
```

---

## Effort Estimate (Rough)

| Phase | Scope |
|-------|-------|
| Phase 1 | Static preview with frame + design rendering |
| Phase 2 | Live needle position + stitch progress |
| Phase 3 | Settings UI, performance, polish |

Phases are independently shippable. Phase 1 alone is a significant improvement over the 3D-printing thumbnail.
