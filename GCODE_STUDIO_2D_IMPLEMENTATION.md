# G-Code Studio 2D Viewer Implementation (Legacy Handibot)

## Status

This document describes the legacy Handibot canvas viewer.
The dev Pi currently runs the Paper.js viewer (`GCodeStudio2D.vue`).
See `docs/components/gcode-studio.md` for the current status and verification steps.

## Overview

Successfully replaced the 3D viewer in G-Code Studio with a dedicated 2D viewer optimized for embroidery and plotter visualization, specifically designed for TurtleStitch G-code format.

## Implementation Date

December 23, 2025

Note: This date is aligned with the documented deployment date in `DEPLOYMENT_SUMMARY.md`.

## What Changed

### 1. Library Integration

**Added Handibot-GCode2DViewer** - A lightweight, pure 2D G-code visualization library
- Location: `src/lib/gcode2dviewer/`
- Files:
  - `gcodetogeometry.min.js` - G-code parser
  - `gcode2dviewer.js` - 2D canvas renderer
  - `index.ts` - TypeScript wrapper and type definitions
  - `README.md` - Documentation

**Why Handibot over alternatives:**
- ✅ Pure 2D (no 3D overhead)
- ✅ Lightweight vanilla JavaScript
- ✅ Perfect for plotter/embroidery style rendering
- ✅ Simple API focused on XY plane
- ✅ No heavy dependencies (vs Three.js in gcode-preview)

### 2. New Component

**Created:** `src/components/gcodestudio/GCodeStudio2DViewer.vue`

A complete 2D viewer component with:
- Canvas-based rendering
- TurtleStitch G-code support
- Multi-color thread visualization
- Frame size presets
- Interactive controls

### 3. Page Update

**Modified:** `src/pages/GCodeStudio.vue`

Changed from using the 3D viewer (`Viewer.vue`) to the new 2D viewer (`GCodeStudio2DViewer.vue`).

### 4. Translation Updates

**Modified:** `src/locales/en.json`

Added translations for new UI elements:
- `TopView`
- `FitToFrame`
- `ShowGrid`
- `ShowAxes`

## Features Implemented

### TurtleStitch G-code Support

**Z-Axis Flattening:**
- TurtleStitch uses Z values as stitch counters (not physical height)
- Preprocessing removes Z parameters to flatten to 2D XY plane
- Example: `G0 X10 Y10 Z5.0` → `G0 X10 Y10`

**Color Parsing:**
- Reads color comments: `; color r:255 g:0 b:0`
- Segments G-code by color changes
- Renders each color segment separately
- Composites multiple layers for full-color visualization

**Stitch Count:**
- Extracts from header: `(STITCH_COUNT:33369)`
- Displays in design info panel

### UI Controls

**Frame Size Presets:**
- 4" x 4" (100mm)
- 5" x 7" (127x178mm)
- 6" x 10" (150x250mm)
- 8" x 8" (200mm)
- 8" x 12" (200x300mm)
- Custom

**Display Options:**
- Grid overlay toggle
- Travel moves visibility toggle
- Customizable stitch color (color picker)
- Customizable travel color (color picker)

**View Controls:**
- Top view reset
- Fit to frame
- Real-time cursor coordinates (XY)

**File Operations:**
- Load local G-code files
- Clear loaded file
- File name display
- Stitch count display

### Multi-Color Rendering

**How it works:**
1. Parse G-code for color comments
2. Split into segments at each color change
3. Render first segment to main canvas
4. Render subsequent segments to temporary canvases
5. Composite all layers onto main canvas

**Result:** Full-color embroidery visualization with proper thread colors

## File Structure

```
mainsail/
├── src/
│   ├── lib/
│   │   └── gcode2dviewer/
│   │       ├── gcodetogeometry.min.js   ← G-code parser
│   │       ├── gcode2dviewer.js         ← 2D renderer
│   │       ├── index.ts                 ← TypeScript wrapper
│   │       └── README.md                ← Documentation
│   ├── components/
│   │   └── gcodestudio/
│   │       ├── GCodeStudio.vue          ← Old advanced component (kept)
│   │       ├── GCodeStudioSimple.vue    ← Old simple component (kept)
│   │       ├── GCodeStudio2D.vue        ← Old 3D-based 2D (kept)
│   │       └── GCodeStudio2DViewer.vue  ← NEW 2D viewer component ⭐
│   ├── pages/
│   │   └── GCodeStudio.vue              ← Updated to use new viewer
│   └── locales/
│       └── en.json                      ← Added translations
```

## Testing

### Test Files Available

TurtleStitch examples in:
```
/Users/boxer/Documents/Projekte/MainsailDev/virtual-klipper-printer/printer_data/gcodes/
├── Zeichnung2.gcode
└── ANNAportfolio.gcode
```

### Standalone Test

Created: `/tmp/test-gcode-viewer.html`

A standalone HTML page for testing the viewer without the full application. Open in browser to test G-code rendering.

## Usage

### Access the Viewer

1. Navigate to the application
2. Click "G-Code Studio" in the navigation (needle icon)
3. Click "Load G-Code" button
4. Select a TurtleStitch `.gcode` file

### Supported Formats

**Primary:** TurtleStitch G-code
- Z values as stitch counters
- Color comments for thread changes
- Metadata headers (STITCH_COUNT, EXTENTS)

**Also works with:** Any standard G-code with G0/G1/G2/G3 commands
- CNC mill paths
- Laser engraving
- Pen plotter drawings

## API Reference

### GCode2DViewer Library

```typescript
import '@/lib/gcode2dviewer/gcodetogeometry.min.js'
import '@/lib/gcode2dviewer/gcode2dviewer.js'

const viewer = (window as any).GCode2DViewer

// Render to canvas
viewer.preview(gcodeString, {
    G0: '#00FF00',   // Travel moves
    G1: '#FF0000',   // Linear moves
    G2G3: '#0000FF'  // Arcs
}, canvasElement)

// Export to image
const dataUrl = viewer.getImage(gcodeString, colors, 800, 600)
```

### Component Integration

```vue
<template>
    <gcode-studio-2d-viewer />
</template>

<script>
import GCodeStudio2DViewer from '@/components/gcodestudio/GCodeStudio2DViewer.vue'

export default {
    components: { GCodeStudio2DViewer }
}
</script>
```

## Known Limitations

1. **Canvas clears on render** - Handibot viewer clears canvas by default, so multi-color rendering uses temporary canvases
2. **No zoom/pan built-in** - Would need to implement custom zoom/pan controls (could use Paper.js)
3. **2D only** - Cannot visualize 3D toolpaths
4. **Color comments required** - For multi-color, TurtleStitch must export with color comments

## Future Enhancements

### Potential Improvements

1. **Paper.js Integration** - For better zoom/pan/transform controls
2. **SVG Export** - Allow saving designs as SVG
3. **Measurement Tools** - Distance and area measurement
4. **Design Manipulation** - Move, rotate, scale designs on canvas
5. **Stitch Simulation** - Animate stitch-by-stitch playback
6. **Color Palette** - Color picker for design recoloring
7. **Design Library** - Save/load favorite designs
8. **Print Preview** - Show design on fabric texture

### Paper.js Benefits

If Paper.js is integrated in future:
- Vector-based rendering (scalable)
- Built-in zoom/pan/transform
- Path manipulation
- Better performance for complex designs
- Export to SVG/PDF

## Routing

The viewer is already accessible at:
- **Path:** `/studio`
- **Route name:** `gcodestudio`
- **Navigation:** Shows in main menu with needle icon
- **Position:** 65 (between G-Code Viewer and History)

## Migration Notes

### What Was Kept

- Old components remain for reference:
  - `GCodeStudio.vue` - Advanced component with tools
  - `GCodeStudioSimple.vue` - Simple test component
  - `GCodeStudio2D.vue` - 3D viewer in 2D mode

### What Changed

- `pages/GCodeStudio.vue` now uses `GCodeStudio2DViewer.vue`
- No breaking changes to routing or navigation
- Users can still access the page the same way

### Rollback Plan

To revert to the 3D viewer:

```vue
<!-- In src/pages/GCodeStudio.vue -->
<template>
    <div class="gcode-studio-page">
        <viewer :embroidery-mode-default="true" />
    </div>
</template>

<script lang="ts">
import Viewer from '@/components/gcodeviewer/Viewer.vue'
// ...
</script>
```

## Performance

### Metrics

- **Initial load:** ~27KB (library files)
- **Render time:** Fast (Canvas-based, hardware accelerated)
- **Memory:** Low (no 3D scene graph)
- **Browser support:** All modern browsers with Canvas API

### Comparison

| Metric | 3D Viewer (Three.js) | 2D Viewer (Handibot) |
|--------|---------------------|----------------------|
| Library size | ~500KB+ | ~27KB |
| Dependencies | Three.js, WebGL | None |
| Render method | WebGL | Canvas 2D |
| Memory usage | High | Low |
| Best for | 3D toolpaths | Embroidery, plotters |

## Credits

- **Original Library:** Handibot-GCode2DViewer by ShopBotTools, Inc.
- **Author:** Alex Canales
- **Integration:** Claude Code (Anthropic)
- **Date:** December 23, 2024

## Resources

- [Handibot GitHub](https://github.com/ShopBotTools/Handibot-GCode2DViewer)
- [TurtleStitch](https://www.turtlestitch.org/)
- [Paper.js](http://paperjs.org/) - For future enhancements
- [Awesome Plotters](https://github.com/beardicus/awesome-plotters) - Community resources

## License

The Handibot-GCode2DViewer library is distributed under its original license.
Integration and component code follows the Mainsail project license.
