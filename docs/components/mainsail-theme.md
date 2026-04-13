# Component: Mainsail Theme — StitchLab

The StitchLab theme is a named built-in Mainsail theme based on the [Catppuccin](https://catppuccin.com) colour system. It ships two palettes that switch automatically with Mainsail's dark/light mode toggle:

| Mode  | Catppuccin Flavour | Primary accent                                        |
| ----- | ------------------ | ----------------------------------------------------- |
| Dark  | **Frappé**         | Selectable Catppuccin accent (default Blue `#8caaee`) |
| Light | **Latte**          | Selectable Catppuccin accent (default Blue `#1e66f5`) |

Colour role assignments follow the official [Catppuccin style guide](https://github.com/catppuccin/catppuccin/blob/main/docs/style-guide.md).

## Current status

| Item                                         | Status                                         | Notes                                                                                         |
| -------------------------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------------------------- |
| StitchLab named Mainsail theme               | **Implemented**                                | Theme entry in `variables.ts`, CSS in `public/css/themes/stitchlab.css`                       |
| StitchLab primary accent selector            | **Implemented**                                | _Settings → UI → Primary_ shows Catppuccin swatches instead of the unrestricted colour picker |
| G-Code Studio + dashboard preview theme pass | **Implemented**                                | Shared StitchLab preview palette, darker preview/code surfaces, G-code-specific editor tokens |
| Runtime theme overrides                      | Available upstream                             | Can still be used on top of the named theme via `~/printer_data/config/.theme/`               |
| Custom favicon / logo                        | Planned                                        | `logo: { show: false }` for now; assets to be added later                                     |
| Deployed UI today                            | StitchLab theme + StitchLAB custom UI features | Embroidery panel, WiFi Manager UI, G-Code Studio, controller menu                             |

## Implementation details

### Files changed

| File                                                                    | Purpose                                                                                                                    |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `mainsail/src/store/variables.ts`                                       | Theme entry, Catppuccin accent palette definitions, accent token helpers, shared G-Code Studio palette                     |
| `mainsail/src/components/settings/SettingsUiSettingsTab.vue`            | Theme-aware primary selector UI; StitchLab uses Catppuccin swatches                                                        |
| `mainsail/src/App.vue`                                                  | Resolves the selected StitchLab accent per mode and pushes it into runtime CSS variables                                   |
| `mainsail/src/store/gui/index.ts` / `mainsail/src/store/gui/actions.ts` | Default/migration handling for stored StitchLab primary accent values                                                      |
| `mainsail/public/css/themes/stitchlab.css`                              | Frappé/Latte palette variables, Vuetify overrides, dynamic primary-accent surfaces, design enhancements, CodeMirror syntax |
| `mainsail/src/components/gcodestudio/GCodeStudio2D.vue`                 | Theme-aware preview/editor mode classes, Studio palette application, Paper.js hierarchy                                    |
| `mainsail/src/components/panels/Status/EmbroideryPreview.vue`           | Theme-aware small preview background, frame colour, stitch palette, needle marker                                          |

### How the theme loads at runtime

1. The user selects **StitchLab** in _Settings → UI → Theme_.
2. The `themeCss` getter in `theme.ts` returns `/css/themes/stitchlab.css` because `css: true`.
3. `App.vue`'s `themeCssChanged` watcher (`immediate: true`) fetches the file and injects it as `<style id="theme-css">`. The `immediate` flag ensures the CSS is loaded on first render, not only on subsequent changes.
4. `App.vue`'s `modeChanged` watcher (`immediate: true`) toggles `html.theme--dark` / `html.theme--light` on the root element, which flips the CSS custom properties between Frappé and Latte palettes. The `immediate` flag ensures the class is present before the first paint — without it, none of the palette selectors match.
5. If the user changes _Settings → UI → Primary_ while StitchLab is active, Mainsail stores a StitchLab accent token (for example `stitchlab:teal`) instead of an arbitrary hex value.
6. `App.vue` resolves that token to the correct Catppuccin hex for the active mode (Frappé in dark mode, Latte in light mode) and publishes it to `--color-primary`, `--v-primary-base`, and `--v-anchor-base`.
7. StitchLab CSS consumes those runtime variables for primary UI surfaces such as primary buttons, active navigation, links, focused inputs, tabs, sliders, and `primary--text` icons.

### CSS architecture

The stylesheet is organised in numbered sections:

| #     | Section              | Description                                                                                 |
| ----- | -------------------- | ------------------------------------------------------------------------------------------- |
| 1     | Palette variables    | All 26 Catppuccin colours under `html.theme--dark` (Frappé) and `html.theme--light` (Latte) |
| 2     | Vuetify variables    | `--v-primary-base`, `--v-anchor-base`                                                       |
| 3–6   | Layout surfaces      | Application bg (Base), sidebar (Crust), cards (Mantle), app bar (Base)                      |
| 7–10  | Interactive controls | Buttons, text inputs, selects/menus, sliders                                                |
| 11–14 | Data display         | Tables, sheets/dialogs/panels, chips/tooltips/snackbars, tabs                               |
| 15–16 | Feedback             | Progress bars, semantic alert colours (Green/Yellow/Red/Teal)                               |
| 17–18 | Chrome               | Scrollbars, text selection (Overlay 2 @ 25%)                                                |
| 19    | Icons                | Semantic icon colour classes                                                                |
| 20–21 | Code editors         | CodeMirror 5 + 6 syntax highlighting per style guide, plus G-code-specific word classes     |
| 22    | System bar / footer  | Crust / Mantle backgrounds                                                                  |

### Catppuccin style guide colour mapping

Background hierarchy (dark → light):

```
Crust  → sidebar, system bar
Mantle → cards, sheets, tables, footer
Base   → main background, app bar
```

StitchLab-specific embroidery surfaces layer on top of that core hierarchy:

- G-Code Studio and the dashboard preview use dedicated darker preview/code surfaces for stitch contrast.
- Editor gutters and edit/transformed chrome use Mantle / Surface / accent combinations rather than the plain page background.

Semantic colours:

| Role                | Colour                                      |
| ------------------- | ------------------------------------------- |
| Primary / Links     | Selectable Catppuccin accent (default Blue) |
| Success             | Green                                       |
| Warning / Not-homed | Peach                                       |
| Error               | Red                                         |
| Info                | Teal                                        |

Code editor tokens:

| Token                  | Colour    |
| ---------------------- | --------- |
| Keywords               | Mauve     |
| Strings                | Green     |
| Atoms / Builtins       | Red       |
| Comments               | Overlay 2 |
| Numbers / Constants    | Peach     |
| Operators              | Sky       |
| Functions / Properties | Blue      |
| Types / Classes        | Yellow    |
| Cursor                 | Rosewater |

For G-code specifically, StitchLab adds an extra semantic layer on top of that base mapping: command words, line/program numbers, axis families, `F`/`S`/`T`, parameter words, and `#` variables get dedicated Catppuccin colours so the editor reads more like a machine-code editor than a generic source editor.

### Design enhancements

Beyond colour, the theme adds subtle visual refinements:

- **Border radii** — 10–12 px on cards, buttons, inputs, menus, expansion panels
- **Hover effects** — cards gain a soft shadow on hover; outlined buttons highlight border
- **Sidebar** — active nav item uses the selected primary accent with Base text; rounded right corners
- **Scrollbars** — thin, rounded, matching Surface 2 / Overlay 0
- **Selection** — Overlay 2 background

## Primary accent selection

When the active theme is **StitchLab**, _Settings → UI → Primary_ no longer exposes the unrestricted Vuetify colour picker. Instead, it shows the Catppuccin accent set used by the theme:

- Rosewater
- Flamingo
- Pink
- Mauve
- Red
- Maroon
- Peach
- Yellow
- Green
- Teal
- Sky
- Sapphire
- Blue
- Lavender

Implementation notes:

- The stored value is a StitchLab token such as `stitchlab:blue`, not a raw hex colour.
- Tokens are mode-aware: the same choice resolves to the Frappé hex in dark mode and the Latte hex in light mode.
- The default StitchLab primary remains **Blue**.
- Other Mainsail themes still use the generic colour picker behavior.

## Remaining work

- [ ] Add StitchLab favicon and sidebar logo (set `logo: { show: true }` once assets exist)
- [ ] Validate StitchLAB-specific surfaces against the theme:
  - `EmbroideryControlPanel`
  - `SettingsWifiTab`
  - `TheControllerMenu`
  - future `GCodeStudio2D` UI changes after larger refactors
- [x] Ship the theme as the default via `public/config.json` (`defaultTheme: "stitchlab"`, `defaultMode: "light"`)
- [ ] Test `.theme/` runtime overrides layered on top of the named theme
- [ ] **StitchLab 2** — second named theme based on [Rosé Pine](https://rosepinetheme.com) (dark: Moon, light: Dawn). Warmer, more muted aesthetic with 6 accent choices (love, gold, rose, pine, foam, iris). Implementation: new `stitchlab2.css` with Rosé Pine palette variables, theme entry in `variables.ts`, accent selector support. See palette at `rose-pine/palette` on GitHub.

## Runtime theme overrides

These still work and can be used to layer additional customisations on top of the named theme:

- `~/printer_data/config/.theme/custom.css`
- `~/printer_data/config/.theme/sidebar-logo.*`
- `~/printer_data/config/.theme/sidebar-background.*`
- `~/printer_data/config/.theme/main-background.*`
- `~/printer_data/config/.theme/navi.json`
- `~/printer_data/config/.theme/default.json`

## Known constraints

- `.theme/default.json` is a seed/reset mechanism for the Moonraker database, not a guaranteed live rollout path for existing machines.
- G-Code Studio uses dedicated StitchLab preview/code variables (`--stitchlab-preview-bg`, `--stitchlab-code-*`) and a shared Studio palette in `variables.ts`, so its surfaces are theme-aware but not limited to only raw `Base`/`Mantle`/`Crust` tokens.
- The StitchLab primary selector only affects UI surfaces wired to the runtime primary variables. Semantic success/warning/error colours remain fixed to Catppuccin Green/Peach/Red.
- Code editor syntax colours follow a static Catppuccin mapping plus G-code-specific semantic word groups; they do not change with the selected primary accent.
- StitchLAB custom panels mostly use Vuetify semantic colours, which should align automatically, but should still be visually checked.

## Related docs

- [../05-configuration.md](../05-configuration.md) — Config paths and Mainsail runtime config
- [../09-update-strategy.md](../09-update-strategy.md) — How source-level theme work ships
- [gcode-studio.md](gcode-studio.md) — Theme-aware Paper.js viewer/editor for embroidery G-code
