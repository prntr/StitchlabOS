# Component: Embroidery Dashboard Preview

The Status Panel replaces the standard 3D-printing thumbnail with embroidery-specific components when the StitchLab theme is active. Two components work together: a canvas-based design preview and an embroidery stats bar.

> **Architecture note (P0-4, v2.17.0):** The dashboard MUST NOT fetch the full active G-Code file or parse stitch paths in the browser. Both components source all data from Moonraker file metadata (`printer.current_file`) and a design thumbnail — no full-file download, no browser-side parser. This is a hard constraint from the Cross-Platform Stability plan; see [../Reports&Plans/Cross-Platform Mainsail Stabilitiy.md](../../Reports&Plans/Cross-Platform%20Mainsail%20Stabilitiy.md) P0-4. `parseEmbroideryGcode.ts` is retained but only used by `GCodeStudio2D.vue`.

## Current status

| Item | Status | Notes |
|------|--------|-------|
| Hoop outline + placement | **Implemented** | Canvas draws frame rect from `gui.gcodeStudio.frameWidth/Height` |
| Design thumbnail | **Implemented** | Fetches best-fit PNG from `current_file.thumbnails`; positioned at design offset |
| Thumbnail placeholder | **Implemented** | When no thumbnail exists, canvas shows hoop outline only — no G-Code fetch |
| Filename / progress overlay | **Implemented** | Filename and `virtual_sdcard.progress` percentage |
| Embroidery print stats | **Implemented** | Stitch count, jump count, design dimensions, needle state — all from `current_file` metadata |
| Intake sidecar metadata | **Partial** | `PrintstatusEmbroidery.vue` reads `current_file.stitchlab_intake.*` when available; falls back to `current_file.stitch_count` / `jump_count` / `design_width` / `design_height` |
| Full G-Code preview / stitch paths | **Removed** | Moved to G-Code Studio (`GCodeStudio2D.vue`) only |
| Live needle crosshair | **Removed** | Not needed for the stable-job-preview contract |
| Stitch-by-stitch progress rendering | **Removed** | `moveOffsets` / `stitchPointMoveIndices` arrays dropped from dashboard Vuex |

## Components

### EmbroideryPreview.vue

**Location:** `src/components/panels/Status/EmbroideryPreview.vue`

A canvas component that renders the embroidery hoop and design thumbnail inside the Status Panel. Conditionally shown in `StatusPanel.vue` when `isEmbroideryMode && current_filename`.

**What it renders:**

- Dashed frame rectangle (size from `gui.gcodeStudio.frameWidth/Height`)
- Design thumbnail PNG from `current_file.thumbnails` (best-fit: first entry with `width >= 200 px`), positioned using `gui.gcodeStudio.designOffsetX/Y`
- Progress/filename overlay bar
- Spinner while the thumbnail image is loading
- Hoop-outline-only placeholder when no thumbnail is available

**Data flow:**

```
printer.current_file.thumbnails (on filename change)
  -> pick best-fit thumbnail by width
  -> build URL: /server/files/gcodes/<path>/<relative_path>
  -> load as HTMLImageElement
  -> drawCanvas()

printer.virtual_sdcard.progress (reactive, ~250 ms)
  -> update progressPercent overlay only — no canvas repaint for progress alone

gui.gcodeStudio.frameWidth/Height/designOffsetX/Y (reactive)
  -> drawCanvas() on change
```

**Naming constraint:** The canvas drawing method is named `drawCanvas()`, not `render()`. In Vue 2 class components, `render` is a reserved method name — Vue's template compiler overwrites it.

**Stability constraints (must not regress):**
- No call to `/server/files/gcodes/<active-file>` to read G-Code content.
- No import or use of `parseEmbroideryGcode.ts` in this component.
- Missing thumbnail → placeholder, not fallback to browser parsing.
- Must not block `guiIsReady` or the dashboard initial render.

### PrintstatusEmbroidery.vue

**Location:** `src/components/panels/Status/PrintstatusEmbroidery.vue`

Stats bar shown below the preview (routed via `Printstatus.vue` based on `isEmbroideryMode`). Displays four columns:

| Column | Source | Notes |
|--------|--------|-------|
| Stitch | `current_file.stitchlab_intake.stitchCount` → `current_file.stitch_count` → 0 | Current = `round(progress × total)` |
| Jumps | `current_file.stitchlab_intake.jumpCount` → `current_file.jump_count` → 0 | Total jump stitches |
| Design | `current_file.stitchlab_intake.designWidth/Height` → `current_file.design_width/height` | W × H in mm; `--` if unavailable |
| Needle | `toolhead.position[2]` | Up/Down from Z modulo 5 mm cycle |

Stats are read directly from `printer.current_file` Vuex state — no shared `embroidery_stats` side-channel from `EmbroideryPreview`.

## Integration in StatusPanel.vue

```vue
<embroidery-preview v-if="isEmbroideryMode && current_filename" />
<status-panel-printstatus-thumbnail v-else />
```

Detection uses: `(this.$store.state.gui.uiSettings?.theme ?? '') === 'stitchlab'`.

## Files

| File | Role |
|------|------|
| `src/components/panels/Status/EmbroideryPreview.vue` | Canvas: hoop outline + thumbnail |
| `src/components/panels/Status/PrintstatusEmbroidery.vue` | Stats bar (metadata from `current_file`) |
| `src/components/panels/Status/Printstatus.vue` | Router: embroidery vs standard print status |
| `src/components/panels/StatusPanel.vue` | Parent: conditional preview vs thumbnail |
| `src/lib/embroideryPreview/parseEmbroideryGcode.ts` | Parser — used by G-Code Studio only |

## Known pitfalls

- **`render()` is reserved in Vue 2** — canvas drawing method must be named `drawCanvas()`.
- **Thumbnail URL construction** — the `relative_path` from `thumbnails[*]` is relative to the directory containing the G-Code file, not the `gcodes/` root. Build the URL as `/server/files/gcodes/<file-dir-prefix>/<relative_path>`.
- **StaleWhileRevalidate PWA cache** — when `config.json` changes, a hard refresh or "Clear site data" is needed.

## Future work

- [x] Intake Phase 3 (Moonraker `stitchlab_intake` component) — shipped. Sidecars land in `gcodes/.stitchlab_meta/*.json` und `gcodes/.stitchlab_thumbs/*.png`; abrufbar über `server.stitchlab_intake.metadata` / `…status`.
- [ ] Intake Phase 4 (Files-UI + Start-Flow) — `PrintstatusEmbroidery.vue` muss `current_file.stitchlab_intake.*` aus dem neuen Endpoint befüllen statt nur aus dem Moonraker-Datei-Metadata-Scanner zu lesen; die Files-UI braucht Status-Badge + "Recheck"-Aktion.
- [ ] Sobald Phase 4 läuft, wird `current_file.stitchlab_intake.thumbnail` Primärquelle; `current_file.thumbnails` bleibt Fallback.
- [ ] Settings UI for frame-border visibility in the preview.
- [ ] Test 13 verification (large embroidery preview end-to-end) hängt an Phase 4.

## Related docs

- [mainsail-theme.md](mainsail-theme.md) — StitchLab theme that activates embroidery mode
- [gcode-studio.md](gcode-studio.md) — Full-page 2D viewer (uses `parseEmbroideryGcode.ts`)
- [embroidery-dashboard-preview-plan.md](embroidery-dashboard-preview-plan.md) — Original implementation plan (describes the old live-parsing approach; superseded)
- [../../Reports&Plans/G-Code Intake Stable Job Preview Plan.md](../../Reports%26Plans/G-Code%20Intake%20Stable%20Job%20Preview%20Plan.md) — Intake plan (producer side)
