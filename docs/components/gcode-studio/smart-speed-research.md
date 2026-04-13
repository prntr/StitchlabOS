# Embroidery Smart Speed Research

## Goal

Investigate how to add source-agnostic "smart speed" and acceleration control for embroidery G-code imported from TurtleStitch and Ink/Stitch.

## Current State In This Repo

### TurtleStitch export

- Current browser-side G-code export uses fixed feeds only:
  - [`turtlestitch/src/embroider.js`](/Users/boxer/Documents/Projekte/MainsailDev/turtlestitch/src/embroider.js:466)
  - Stitch moves are emitted as `G1 X.. Y.. Z.. F<stitchFeed>`
  - Travel moves are emitted as `G0 X.. Y.. F<travelFeed>`
- Defaults are static:
  - `travelFeed: 6000`
  - `stitchFeed: 1800`
  - [`turtlestitch/src/embroider.js`](/Users/boxer/Documents/Projekte/MainsailDev/turtlestitch/src/embroider.js:549)
- Legacy `stitchcode` export is even simpler and has no feed handling:
  - [`turtlestitch/stitchcode/turtleShepherd.js`](/Users/boxer/Documents/Projekte/MainsailDev/turtlestitch/stitchcode/turtleShepherd.js:847)

### Existing "problem detection" in TurtleStitch

- TurtleStitch already tracks two useful heuristics while building the stitch cache:
  - local revisit density
  - overly long stitches
- This is warning-only today and does not affect export:
  - [`turtlestitch/stitchcode/turtleShepherd.js`](/Users/boxer/Documents/Projekte/MainsailDev/turtlestitch/stitchcode/turtleShepherd.js:143)
- Relevant logic:
  - `density[d] += 1`, `densityWarning = true` when count exceeds `densityMax`
  - `tooLongCount += 1` when a stitch exceeds `maxLength`

### G-Code Studio

- G-Code Studio already performs an export-time text transformation pass:
  - [`mainsail/src/components/gcodestudio/GCodeStudio2D.vue`](/Users/boxer/Documents/Projekte/MainsailDev/mainsail/src/components/gcodestudio/GCodeStudio2D.vue:1479)
- That transform currently rewrites only `X/Y/I/J` coordinates.
- This is the best existing insertion point for source-agnostic smart-speed post-processing because it already handles imported TurtleStitch and Ink/Stitch G-code.

### Hybrid roadmap

- The hybrid docs already assume an embroidery G-code post-processor exists or will exist:
  - [`docs/hybrid/IMPLEMENTATION_PLAN.md`](/Users/boxer/Documents/Projekte/MainsailDev/docs/hybrid/IMPLEMENTATION_PLAN.md:179)
- Current planned use is `WAIT_NEEDLE_UP` insertion before XY moves.
- That same post-processing stage is the natural place for smart-speed zoning.

### Printer limits already configured

- Current Klipper config:
  - `max_velocity: 200`
  - `max_accel: 1500`
  - `max_z_velocity: 60`
  - `max_z_accel: 120`
  - [`stitchlabos/image/src/modules/klipper/filesystem/home/pi/printer_data/config/printer.cfg`](/Users/boxer/Documents/Projekte/MainsailDev/stitchlabos/image/src/modules/klipper/filesystem/home/pi/printer_data/config/printer.cfg:77)
- Embroidery macros currently use static Z feed derived from `max_z_velocity`:
  - [`stitchlabos-config/printer_data/config/embroidery_macros.cfg`](/Users/boxer/Documents/Projekte/MainsailDev/stitchlabos-config/printer_data/config/embroidery_macros.cfg:16)

## Relevant External Findings

### Klipper

- `SET_VELOCITY_LIMIT` can change runtime limits for:
  - `VELOCITY`
  - `ACCEL`
  - `MINIMUM_CRUISE_RATIO`
  - `SQUARE_CORNER_VELOCITY`
- Klipper explicitly documents `minimum_cruise_ratio` as helpful for short zigzag moves because it reduces the top speed of short moves and helps reduce vibration.
- `M204` exists, but Klipper documents it as intended for low-level diagnostics/debugging. Prefer `SET_VELOCITY_LIMIT`.

### Ink/Stitch

- Ink/Stitch already solves several "problematic embroidery geometry" cases at stitch-plan time, not machine-control time:
  - minimum stitch length filtering
  - short stitch inset / short stitch distance on satin-style stitches
  - randomization of stitch length/phase in dense curved fills
  - routing improvements
- Ink/Stitch docs also explicitly note that dense inside corners are problematic and can produce holes or poor quality.

## Other Geometry And Analysis Tools

These are not embroidery-specific, but they fit embroidery analysis well.

### Frontend-friendly JavaScript / TypeScript tools

#### RBush

- RBush is a fast 2D spatial index for rectangles and points.
- Good fit for:
  - viewport queries
  - "find all stitches within radius/cell"
  - fast overlap checks between stitch bounding boxes and danger zones
- Practical use here:
  - build a live spatial index for stitch endpoints or segment bounding boxes in `GCodeStudio2D.vue`

#### Turf.js

- Turf provides ready-made geometry predicates and intersection helpers.
- Relevant functions:
  - `lineIntersect`
  - `lineOverlap`
  - `booleanIntersects`
- Good fit for:
  - self-intersection detection
  - overlap detection between stitch segments
  - hoop-boundary / margin checks
- Caveat:
  - it is GIS-oriented, so for high-volume stitch analysis it is less efficient than a custom segment engine plus spatial index

#### d3-delaunay

- Fast Delaunay/Voronoi implementation for 2D point sets.
- Good fit for:
  - local neighborhood analysis
  - nearest-neighbor queries
  - estimating "territory" around each needle penetration
  - visualizing dense regions as Voronoi cells

### Python analysis stack

#### pyembroidery

- Best parser layer for many embroidery formats and also supports `gcode`.
- Good fit for:
  - converting file formats into a common event stream
  - extracting stitch blocks, jump blocks, colors, trims

#### Shapely

- Strong geometry engine for 2D line and polygon work.
- Relevant operations:
  - `STRtree` for spatial indexing
  - `simplify()` using Douglas-Peucker
  - `hausdorff_distance()`
  - `frechet_distance()`
- Good fit for:
  - comparing original vs transformed stitch paths
  - topology-aware simplification experiments
  - collision / containment / overlap checks

#### SciPy spatial

- Relevant tools:
  - `cKDTree`
  - `directed_hausdorff`
  - `Voronoi`
- Good fit for:
  - dense neighborhood counting
  - radius-based local density
  - point-cloud style quality metrics
  - measuring design similarity after simplification or optimization

#### scikit-learn clustering

- `DBSCAN` and `OPTICS` are strong fits for stitch-density clustering.
- Good fit for:
  - finding tight dense stitch clusters
  - separating isolated bad regions from globally dense fills
  - grouping revisit hotspots without hand-written thresholds

#### scikit-image / OpenCV

- Good fit when a raster view is helpful:
  - skeletonization
  - contour analysis
  - curvature / shape descriptors
  - region heatmaps
- Especially useful if you want to compare "needle hit density image" against geometric analysis.

### Exact / heavyweight computational geometry

#### CGAL

- Best choice if exact topology guarantees become important.
- Relevant packages:
  - 2D arrangements
  - topology-preserving polyline simplification
- Good fit for:
  - robust intersection reasoning
  - preserving topology while simplifying or cleaning paths
  - exact geometric preprocessing before export
- Caveat:
  - much heavier than the repo likely needs for a first implementation

## Algorithm Families Worth Considering

### 1. Spatial indexing

Use:

- RBush
- Shapely `STRtree`
- SciPy `cKDTree`

Why:

- any local-density or collision algorithm becomes much cheaper once nearby stitches can be queried quickly

### 2. Density clustering

Use:

- DBSCAN
- OPTICS
- HDBSCAN if variable density matters later

Why:

- dense embroidery trouble usually appears as spatial clusters, not just individual short stitches

### 3. Path simplification

Use:

- Douglas-Peucker (`shapely.simplify`, OpenCV `approxPolyDP`)
- topology-preserving simplification (CGAL)

Why:

- useful for detecting redundant micro-oscillations and for previewing what a cleaned path would look like
- should be used primarily for analysis or advisory tooling, not blindly for stitch deletion

### 4. Curve similarity

Use:

- Hausdorff distance
- Fréchet distance

Why:

- compare original design path against transformed, simplified, or optimized versions
- Fréchet is especially useful when order matters along the curve

### 5. Neighborhood partitioning

Use:

- Voronoi / Delaunay

Why:

- can estimate local spacing quality
- useful for identifying points with unusually little surrounding free space

### 6. Graph-based routing analysis

Use:

- NetworkX shortest-path and graph algorithms

Why:

- if we later analyze object ordering, trim minimization, or travel optimization across stitch blocks, this becomes the right abstraction

### 7. Raster heatmap analysis

Use:

- OpenCV
- scikit-image

Why:

- convert needle penetrations into a density image and then detect hotspots, ridges, narrow bridges, or repeated penetrations using standard image-processing tools

## Recommended Stack By Phase

### Phase A: fast implementation inside this repo

- parser: existing `parseEmbroideryGcode.ts`
- spatial index: RBush or a simple grid hash
- geometry predicates: hand-written segment math first, Turf only where it clearly saves time
- visualization: Paper.js overlays in G-Code Studio

### Phase B: stronger offline analyzer / experimentation

- parser: pyembroidery
- geometry: Shapely
- local neighborhoods: SciPy `cKDTree`
- clustering: scikit-learn `DBSCAN` / `OPTICS`

### Phase C: only if topology cleanup becomes a product feature

- exact geometry backend: CGAL

## Best Non-Embroidery Additions For This Project

If the goal is "find problematic embroidery geometry quickly" rather than "build a CAD kernel", the best additions are:

1. RBush or a grid hash for live local queries in the frontend
2. Shapely + SciPy + scikit-learn for offline metric design and threshold tuning
3. Delaunay/Voronoi only if we want richer visual analytics
4. CGAL only if we later need guaranteed topology-preserving cleanup

## Main Conclusion

The right architecture is two-layered:

1. **Planning-time mitigation**
   - Avoid generating pathological stitch geometry when possible.
   - This is what Ink/Stitch already does better than plain G-code export.

2. **G-code-time speed zoning**
   - Detect locally difficult regions and insert lower motion limits only where needed.
   - This should live in G-Code Studio first, because it can cover both TurtleStitch and Ink/Stitch imports.

## Recommended Implementation Path

### Phase 1: Analyzer only

Add a source-agnostic embroidery analyzer in Mainsail, for example:

- `mainsail/src/lib/embroideryPreview/analyzeEmbroideryGcode.ts`

Inputs:

- original G-code text

Outputs per stitch/move:

- stitch length
- turn angle
- local revisit density
- jump/travel markers
- color-change / trim neighborhood markers
- risk score

### Phase 2: Risk model

Use a small stitched-window heuristic rather than per-line toggling.

Recommended features:

- **Short stitch length**
  - Example: `len_xy < 0.8mm`
- **High turning angle**
  - Example: `angle > 100-130deg`
- **High local density**
  - Count penetrations within a radius or grid cell
- **Repeated backtracking**
  - Alternating near-opposite directions with very small forward progress
- **Problem transitions**
  - lock stitches
  - trims
  - color changes
  - dense jump-to-stitch restarts

Recommended scoring:

- score each stitch
- smooth over a window of `5-12` stitches
- classify into `normal`, `caution`, `dense`
- use hysteresis so speed profiles do not flap on every stitch

### Phase 3: Export-time control strategy

Preferred control method for Klipper:

- Insert zone changes with `SET_VELOCITY_LIMIT`
- Keep the number of changes low by emitting them only on zone transitions

Example:

```gcode
; smart-speed zone=dense score=0.81
SET_VELOCITY_LIMIT VELOCITY=18 ACCEL=80 MINIMUM_CRUISE_RATIO=0.75 SQUARE_CORNER_VELOCITY=0.8
G1 X12.400 Y8.200 Z145.000 F1800
G1 X12.950 Y8.350 Z150.000 F1800
...
; smart-speed zone=normal
SET_VELOCITY_LIMIT VELOCITY=200 ACCEL=1500 MINIMUM_CRUISE_RATIO=0.5 SQUARE_CORNER_VELOCITY=5
```

Notes:

- On stitch moves containing `X/Y/Z` together, changing `VELOCITY` directly changes stitch cycle time and therefore effective stitches-per-minute in dense areas.
- Lowering `ACCEL` can still be useful, but current stitch moves are already strongly constrained by `max_z_accel`, so **velocity adaptation matters more than acceleration adaptation** for the current exporter.
- `minimum_cruise_ratio` is especially relevant for dense zigzag-like motion.
- `square_corner_velocity` should be reduced in dense cornering zones.
- If the roadmap switches to encoder-synced embroidery with `WAIT_NEEDLE_UP` and separate XY motion plus `STITCH`/Z macros, then `SET_VELOCITY_LIMIT` alone will no longer control stitch cadence. In that architecture, emit profile macros instead, for example `EMBROIDERY_PROFILE NAME=dense`, so one command can lower XY motion limits and stitch-cycle feed together.

### Phase 4: UI in G-Code Studio

Add:

- a heatmap or color overlay for risky regions
- per-profile editor:
  - normal
  - caution
  - dense
- toggles:
  - `Preview Smart Speed`
  - `Apply Smart Speed On Export`

This lets users verify why a region was slowed before exporting.

## Heuristic Proposal

Start simple. For stitch `i`:

- `d_prev = distance(stitch[i-1], stitch[i])`
- `d_next = distance(stitch[i], stitch[i+1])`
- `turn = angle(vec(i-1 -> i), vec(i -> i+1))`
- `density = number of stitch endpoints within r=1.0mm`

Suggested initial rules:

- `dense` if:
  - `d_prev < 0.6` and `turn > 110`
  - or `density >= 6`
  - or same cell hit count exceeds threshold
- `caution` if:
  - `d_prev < 1.0`
  - or `turn > 90`
  - or `density >= 4`

Suggested starting profiles:

- `normal`
  - use printer defaults
- `caution`
  - `VELOCITY=24`
  - `ACCEL=100`
  - `MINIMUM_CRUISE_RATIO=0.65`
  - `SQUARE_CORNER_VELOCITY=1.2`
- `dense`
  - `VELOCITY=18`
  - `ACCEL=70`
  - `MINIMUM_CRUISE_RATIO=0.8`
  - `SQUARE_CORNER_VELOCITY=0.6`

These values are conservative starting points and must be tuned on hardware.

## Why G-Code Studio First

Best initial location:

- it already imports both TurtleStitch and Ink/Stitch output
- it already has a transform-and-export pipeline
- it keeps the source generators simpler
- it can surface visual diagnostics before export

Generator-side improvements can still follow later:

- TurtleStitch can expose smarter defaults or warnings at authoring time
- Ink/Stitch-style stitch planning improvements can reduce the need for machine slowdown

## Practical Next Step

Implement in this order:

1. analyzer module in `mainsail/src/lib/embroideryPreview/`
2. preview overlay in `GCodeStudio2D.vue`
3. export-time `SET_VELOCITY_LIMIT` insertion
4. optional printer-side macro wrappers such as `EMBROIDERY_SPEED PROFILE=dense`

## What Speed Changes Actually Make Sense

### First principle

Speed changes should be:

- sparse
- profile-based
- triggered by regions or events, not by every single stitch

What does **not** make sense:

- changing speed on nearly every stitch
- making large acceleration jumps every few moves
- random speed variation without a geometric reason
- using only acceleration changes while leaving stitch feed untouched

### Current exporter: combined `G1 X Y Z`

Today the TurtleStitch export emits stitch moves like:

```gcode
G1 X... Y... Z... F1800
```

With `zPerStitchMm = 5`, feedrate changes directly change effective stitch cadence:

- `F1800` = `30 mm/s` = about `360 spm`
- `F1500` = `25 mm/s` = about `300 spm`
- `F1200` = `20 mm/s` = about `240 spm`
- `F900` = `15 mm/s` = about `180 spm`

For this exporter, the most meaningful knobs are:

1. stitch feedrate `F`
2. optionally `SET_VELOCITY_LIMIT VELOCITY=...`
3. secondarily `ACCEL`

Less impactful than they look in the current format:

- `SQUARE_CORNER_VELOCITY`
- `MINIMUM_CRUISE_RATIO`

Reason:

- every stitch vector includes a constant `+Z` component, so successive 3D move vectors are more parallel than the XY path alone suggests
- that reduces how dramatic corner-junction logic is compared to a pure XY stitch planner

### Future synced architecture: separate XY motion and stitch cycle

If the roadmap moves to:

- `WAIT_NEEDLE_UP`
- separate XY motion
- separate `STITCH` or needle-cycle commands

then the priority changes:

1. stitch-cycle speed
2. XY velocity
3. `SQUARE_CORNER_VELOCITY`
4. `MINIMUM_CRUISE_RATIO`

In that architecture, corner and short-zigzag logic matters much more than it does today.

### Profiles That Make Sense

Use fixed profiles and switch only on zone transitions.

#### `travel`

Use for:

- long jumps
- moves between islands/objects
- repositioning after trims or color changes

Behavior:

- fast XY
- conservative but not extreme acceleration
- no need for stitch slowdown logic

Suggested starting point:

- keep current `G0/G1` travel feed around `5000-6000`

#### `normal`

Use for:

- ordinary running stitch regions
- moderate fill regions
- long smooth contours

Behavior:

- baseline production speed

Suggested current-export baseline:

- `F1500-F1800`

#### `caution`

Use for:

- short stitches
- moderate density clusters
- visible curvature
- restarts after trims/lock stitches

Behavior:

- reduce stitch cadence by about `15-30%`
- optionally reduce motion limits modestly

Suggested current-export starting point:

- `F1200-F1500`

#### `dense`

Use for:

- repeated penetrations in a tight area
- inside corners
- dense satin turns
- very short back-and-forth motion
- tie-in / tie-off / lock-stitch neighborhoods

Behavior:

- reduce stitch cadence by about `35-50%`
- lower motion limits enough to remove jerk and overshoot

Suggested current-export starting point:

- `F900-F1200`

#### `lock`

Use for:

- first few stitches after start
- tie-in / tie-off
- trim restart regions

Behavior:

- shortest deliberate zone
- the slowest profile

Suggested current-export starting point:

- `F700-F900`

### Best Event-Driven Changes

These changes usually make sense even before geometric zoning:

1. slow the first `3-8` stitches after a jump or trim
2. slow tie-in / lock-stitch segments
3. slow the last `3-8` stitches before a trim or color change
4. keep long travel moves fast

This is low-risk and usually gives better reliability immediately.

### Best Geometry-Driven Changes

These are the best next layer:

1. slow regions with many needle hits in a radius
2. slow very short consecutive stitches
3. slow high-curvature or backtracking regions
4. slow dense inside corners more than straight dense fills

### Relative Changes Are Better Than Absolute Changes

Do not bake a single machine-specific number into the algorithm.

Prefer:

- `normal = 100%`
- `caution = 75-85%`
- `dense = 55-70%`
- `lock = 40-55%`

Then map those percentages onto:

- current stitch `F`
- optional Klipper speed profile macro

### Acceleration Changes That Make Sense

Acceleration changes should be smaller and rarer than speed changes.

Good rule:

- speed changes do most of the work
- acceleration changes only soften transitions in dense zones

Suggested policy:

- `normal`: printer default
- `caution`: `70-85%` of default accel
- `dense`: `45-65%` of default accel
- `lock`: `35-50%` of default accel

### Changes That Probably Do Not Pay Off Yet

- per-stitch `SET_VELOCITY_LIMIT`
- per-stitch acceleration tuning
- attempting to infer tension issues only from path geometry
- optimizing `square_corner_velocity` first while using the current combined `XYZ` stitch move format

### Recommended First Production Rollout

If the goal is a practical first version:

1. keep `travel` fast
2. add `lock` slowdown around starts/stops/trims
3. add `dense` slowdown for local hit-density hotspots
4. add `caution` slowdown for short-stitch clusters
5. switch only at zone boundaries, not every stitch

That should produce noticeably better behavior without making export logic fragile.

## Sources

- Local code and docs referenced above
- Klipper docs:
  - https://www.klipper3d.org/G-Codes.html
  - https://www.klipper3d.org/Config_Reference.html
  - https://www.klipper3d.org/Config_Changes.html
- Ink/Stitch docs:
  - https://inkstitch.org/docs/preferences/
  - https://inkstitch.org/docs/stitches/running-stitch/
  - https://inkstitch.org/docs/stitches/zigzag-stitch/
  - https://inkstitch.org/docs/stitches/e-stitch/
- Geometry / algorithm tooling:
  - https://github.com/mourner/rbush
  - https://turfjs.org/docs/api/lineIntersect
  - https://d3js.org/d3-delaunay
  - https://shapely.readthedocs.io/en/latest/reference/shapely.frechet_distance.html
  - https://shapely.readthedocs.io/en/latest/reference/shapely.hausdorff_distance.html
  - https://shapely.readthedocs.io/en/maint-2.0/strtree.html
  - https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html
  - https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.directed_hausdorff.html
  - https://scikit-learn.org/stable/modules/generated/sklearn.cluster.OPTICS.html
  - https://scikit-learn.org/1.5/modules/generated/sklearn.cluster.DBSCAN.html
  - https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
  - https://scikit-image.org/docs/stable/api/skimage.morphology.html
  - https://doc.cgal.org/latest/Polyline_simplification_2/index.html
  - https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.approximation.traveling_salesman.traveling_salesman_problem.html
