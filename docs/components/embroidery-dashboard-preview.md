# Component: Embroidery Dashboard Preview

The Status Panel replaces the standard 3D-printing thumbnail with embroidery-specific components when the StitchLab theme is active. Two components work together: a canvas-based design preview and an embroidery stats bar.

## Current status

| Item | Status | Notes |
|------|--------|-------|
| Static design preview | **Implemented** | Canvas renders frame + stitch paths from parsed G-Code |
| Live needle position | **Implemented** | Crosshair marker tracks toolhead X/Y during printing |
| Stitch progress | **Implemented** | Completed stitches solid, remaining faded; counter overlay |
| Embroidery print stats | **Implemented** | Stitch count, jump count, design dimensions, needle state |
| Shared parsing utility | **Implemented** | `parseEmbroideryGcode.ts` extracts geometry from G-Code |
| Settings reuse | **Implemented** | Reads frame size, offsets, and colours from `gui.gcodeStudio` store |

## Components

### EmbroideryPreview.vue

**Location:** `src/components/panels/Status/EmbroideryPreview.vue`

A canvas-based component that renders the embroidery design inside the Status Panel. Conditionally shown in `StatusPanel.vue` when `isEmbroideryMode && current_filename`.

**What it renders:**

- Dashed frame rectangle (size from `gui.gcodeStudio.frameWidth/Height`)
- Stitch paths parsed from the active G-Code file
- During printing: completed stitches in solid colour, remaining in faded colour
- Needle position as a crosshair dot at current toolhead X/Y
- Overlay bar with filename, stitch counter, and progress percentage

**Data flow:**

```
printer.print_stats.filename (changes)
  -> fetch /server/files/gcodes/{filename}
  -> parseEmbroideryGcode(gcode, stitchColor)
  -> store parsed geometry + share stats via printer/setData
  -> render to canvas

printer.virtual_sdcard.file_position (updates ~250ms)
  -> binary search on moveOffsets -> current move index
  -> re-render: solid up to current move, faded after

printer.toolhead.position (updates ~250ms)
  -> draw needle crosshair at mapped [X, Y]
```

**Performance:**

- Canvas redraws throttled via `requestAnimationFrame`
- `GCodeToGeometry` parser lazy-loaded as a `<script>` tag
- Parsed geometry cached per filename; invalidated on filename change
- `ResizeObserver` handles responsive canvas sizing; cleaned up in `beforeDestroy`

**Naming constraint:** The canvas drawing method is named `drawCanvas()`, not `render()`. In Vue 2 class components, `render` is a reserved method name — Vue's template compiler overwrites it with the component's own render function, so any user-defined `render()` method silently breaks.

### PrintstatusEmbroidery.vue

**Location:** `src/components/panels/Status/PrintstatusEmbroidery.vue`

A stats bar shown below the preview (routed via `Printstatus.vue` based on `isEmbroideryMode`). Displays four columns:

| Column | Source | Notes |
|--------|--------|-------|
| Stitch | `embroidery_stats.stitchPointMoveIndices` | Current / total count with progress tooltip |
| Jumps | `embroidery_stats.jumpCount` | Total jump stitches |
| Design | `embroidery_stats.designWidth/Height` | W x H in mm |
| Needle | `toolhead.position[2]` | Up/Down state from Z position modulo 5mm cycle |

Stats are shared from `EmbroideryPreview` via `printer/setData` → `embroidery_stats`.

## Parsing utility

**Location:** `src/lib/embroideryPreview/parseEmbroideryGcode.ts`

Wraps `GCodeToGeometry.parse()` and returns:

- `renderLines` — geometry lines with colour and type info
- `stitchCount`, `jumpCount` — stitch statistics
- `designWidth`, `designHeight` — bounding box dimensions
- `stitchPointMoveIndices` — indices of Z-marked stitch moves
- `moveOffsets` — byte offsets for file-position-to-move mapping
- `treatG0AsStitch` — heuristic flag (from GCode Studio logic)
- `hasColorChanges` — whether the design uses colour changes

## Integration in StatusPanel.vue

```vue
<embroidery-preview v-if="isEmbroideryMode && current_filename" />
<status-panel-printstatus-thumbnail v-else />
```

Detection uses the theme check: `(this.$store.state.gui.uiSettings?.theme ?? '') === 'stitchlab'`.

## Files

| File | Role |
|------|------|
| `src/components/panels/Status/EmbroideryPreview.vue` | Canvas-based live preview |
| `src/components/panels/Status/PrintstatusEmbroidery.vue` | Stitch/jump/design/needle stats bar |
| `src/components/panels/Status/Printstatus.vue` | Router: selects embroidery or standard print status |
| `src/components/panels/StatusPanel.vue` | Parent: conditionally renders preview vs thumbnail |
| `src/lib/embroideryPreview/parseEmbroideryGcode.ts` | G-Code parsing utility |

## Known pitfalls

- **`render()` is reserved in Vue** — the canvas drawing method must not be named `render`. Use `drawCanvas()` instead.
- **Unit scaling** — `GCodeToGeometry` defaults to `displayInInch: true` when gcode has no G20/G21. Scale by 25.4 only when `displayInInch === false` (matches GCode Studio's logic).

## Remaining work

- [ ] Fallback to PNG thumbnail if G-Code fetch/parse fails
- [ ] Show design without frame border when frame dimensions are unconfigured
- [ ] Settings UI for show/hide frame, stitch points, jump stitches in preview
- [ ] Douglas-Peucker simplification for very large designs (>10k stitches)

## Related docs

- [mainsail-theme.md](mainsail-theme.md) — StitchLab theme that enables embroidery mode
- [temperature-panel.md](temperature-panel.md) — Temperature Panel embroidery mode
- [gcode-studio.md](gcode-studio.md) — Full-page 2D viewer (shares parser and settings)
- [embroidery-dashboard-preview-plan.md](embroidery-dashboard-preview-plan.md) — Original implementation plan
