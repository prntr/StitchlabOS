# Deployment Summary - G-Code Studio 2D Viewer (Legacy Handibot)

## Status

This document describes the legacy Handibot canvas viewer deployment.
The dev Pi currently runs the Paper.js viewer (`GCodeStudio2D.vue`).
See `docs/components/gcode-studio.md` for the current status and verification steps.

## Deployment Date
December 23, 2025

## Target System
- **Host:** stitchlabdev.local
- **User:** pi
- **Directory:** /home/pi/mainsail/
- **Web Server:** nginx

## Deployment Steps Completed

### 1. ✅ Library Integration
- Added Handibot-GCode2DViewer to `public/lib/gcode2dviewer/`
- Files deployed:
  - `gcodetogeometry.min.js` (23KB) - G-code parser
  - `gcode2dviewer.js` (4.9KB) - 2D renderer

### 2. ✅ Component Updates
- Created `GCodeStudio2DViewer.vue` with dynamic script loading
- Updated `pages/GCodeStudio.vue` to use new 2D viewer
- Added translations to `locales/en.json`

### 3. ✅ Build Process
- Built successfully with Vite
- Total bundle size: ~12MB
- Library files copied to public assets

### 4. ✅ Deployment to Pi
- Synced via rsync (3.3MB transferred)
- nginx restarted successfully
- Library files verified accessible at:
  - http://stitchlabdev.local/lib/gcode2dviewer/gcodetogeometry.min.js
  - http://stitchlabdev.local/lib/gcode2dviewer/gcode2dviewer.js

## How to Access

### Via Browser
1. Navigate to: **http://stitchlabdev.local/**
2. Click on **"G-Code Studio"** in the navigation (needle icon)
3. You'll see the new 2D viewer interface

### Test with TurtleStitch Files
Test files available on the Pi:
```
/home/pi/printer_data/gcodes/Zeichnung2.gcode
/home/pi/printer_data/gcodes/ANNAportfolio.gcode
```

Steps to test:
1. Open G-Code Studio
2. Click "Load G-Code" button
3. Select a TurtleStitch .gcode file
4. View the 2D rendering with multi-color support

## Features Available

### Display Options
- **Frame Size Presets:** 4x4", 5x7", 6x10", 8x8", 8x12", custom
- **Grid Toggle:** Show/hide grid overlay
- **Travel Moves:** Toggle visibility of G0 moves
- **Color Pickers:** Customize stitch and travel colors

### TurtleStitch Support
- ✅ Z-axis flattening (Z values = stitch counters)
- ✅ Color comment parsing: `; color r:X g:Y b:Z`
- ✅ Multi-color thread visualization
- ✅ Stitch count display
- ✅ Real-time cursor coordinates

### View Controls
- **Reset View:** Return to top-down view
- **Fit to Frame:** Auto-zoom to fit design
- **Cursor Tracking:** Live XY coordinates

## Technical Details

### Library Loading
The 2D viewer library is loaded dynamically when the component mounts:
1. Check if `GCode2DViewer` already exists
2. Load `gcodetogeometry.min.js` (parser)
3. Load `gcode2dviewer.js` (renderer)
4. Initialize canvas and rendering

### Rendering Pipeline
1. **Load G-code** file via file picker
2. **Preprocess** TurtleStitch format:
   - Strip Z parameters
   - Parse color comments
   - Segment by color changes
3. **Render** each color segment:
   - First segment to main canvas
   - Subsequent segments to temp canvases
   - Composite all layers
4. **Display** final multi-color result

### Performance
- **Canvas-based:** Hardware accelerated 2D rendering
- **Lightweight:** ~27KB library vs 500KB+ for Three.js
- **Fast:** Instant rendering for typical embroidery files

## Verification

### Deployment Checklist
- [x] Build completed without errors
- [x] Files synced to Pi successfully
- [x] nginx restarted
- [x] Library files accessible via HTTP
- [x] Component bundled correctly
- [x] No TypeScript/build errors

### Files Deployed
```
/home/pi/mainsail/
├── assets/
│   ├── GCodeStudio-*.js          ← Component bundle
│   ├── GCodeStudio-*.css         ← Styles
│   └── [other bundles]
├── lib/
│   └── gcode2dviewer/
│       ├── gcodetogeometry.min.js ← Parser
│       └── gcode2dviewer.js       ← Renderer
├── index.html
└── [other static files]
```

## Testing Instructions

### Basic Test
1. Open http://stitchlabdev.local/
2. Navigate to G-Code Studio
3. Verify interface loads without console errors
4. Check that library scripts load (check Network tab)

### File Loading Test
1. Click "Load G-Code"
2. Select `/home/pi/printer_data/gcodes/Zeichnung2.gcode`
3. Verify:
   - File name displays
   - Stitch count shows (should be 33,369)
   - Design renders in canvas
   - No console errors

### Multi-Color Test
1. Load a TurtleStitch file with multiple colors
2. Verify each thread color renders correctly
3. Check color segments are composited properly

### UI Controls Test
1. Toggle grid on/off
2. Toggle travel moves
3. Change stitch color with color picker
4. Change travel color
5. Try different frame size presets
6. Verify cursor coordinates update on mouse move

## Rollback Plan

If issues occur, revert to previous version:

```bash
# On local machine
cd /Users/boxer/Documents/Projekte/MainsailDev/mainsail
git checkout HEAD~1 src/pages/GCodeStudio.vue
npm run build
rsync -avz --delete dist/ pi@stitchlabdev.local:/home/pi/mainsail/
```

Or manually edit `src/pages/GCodeStudio.vue`:
```vue
<template>
    <div class="gcode-studio-page">
        <viewer :embroidery-mode-default="true" />
    </div>
</template>
```

## Known Issues / Limitations

1. **Canvas clears on render** - Multi-color uses temporary canvas compositing
2. **No zoom/pan** - Would need additional implementation
3. **Browser support** - Requires modern browsers with Canvas API
4. **File size** - Very large files (>100K stitches) may be slow

## Future Enhancements

### Possible Improvements
- [ ] Add zoom/pan controls
- [ ] Implement Paper.js for vector rendering
- [ ] Add SVG export
- [ ] Implement measurement tools
- [ ] Add design manipulation (move/rotate/scale)
- [ ] Stitch-by-stitch animation
- [ ] Color palette management
- [ ] Design library/favorites

## Support & Documentation

- Canonical StitchLAB docs entrypoint: `docs/README.md`
- Component status: `docs/components/gcode-studio.md`
- Legacy implementation notes (Handibot viewer): `GCODE_STUDIO_2D_IMPLEMENTATION.md`
- Mainsail feature-level agent notes (Paper.js viewer): `mainsail/src/components/gcodestudio/AGENTS.md`

## Status

🟢 **Deployment Successful**

The new 2D G-code viewer is now live at:
**http://stitchlabdev.local/** → G-Code Studio

Ready for testing with TurtleStitch embroidery files!
