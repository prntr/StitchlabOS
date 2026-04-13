# Component: Temperature Panel — Embroidery Mode

When the StitchLab theme is active, the Temperature Panel switches from the standard heater/sensor table to a compact card-based layout showing host CPU and MCU temperatures. The standard temp chart and presets are hidden in this mode.

## Current status

| Item                        | Status          | Notes                                                             |
| --------------------------- | --------------- | ----------------------------------------------------------------- |
| Embroidery temperature list | **Implemented** | `TemperaturePanelEmbroideryList.vue`                              |
| Conditional rendering       | **Implemented** | `isEmbroideryMode` gates display based on `theme === 'stitchlab'` |
| Panel visibility            | **Implemented** | Panel hides entirely if no host stats or MCU data available       |

## How it works

### Mode detection

`TemperaturePanel.vue` checks `this.$store.state.gui.uiSettings?.theme === 'stitchlab'` to toggle between standard and embroidery views:

- **Standard mode** — Full heater/sensor table with presets, settings buttons, and optional temp chart
- **Embroidery mode** — `TemperaturePanelEmbroideryList` showing CPU + MCU temps as progress cards; no chart, no presets

### What the embroidery list displays

Each temperature source renders as a card with:

- Icon + label (thermometer for host CPU, chip icon for MCUs)
- Current temperature with `°C` suffix
- Progress bar (0–100 °C scale)
- Min/max measured temps (when available from Klipper)

### Temperature thresholds

| Threshold | Value    | Colour                          |
| --------- | -------- | ------------------------------- |
| Normal    | < 70 °C  | Primary (blue)                  |
| Warning   | >= 70 °C | Warning (peach)                 |
| Error     | >= 85 °C | Error (red)                     |
| No data   | null     | Grey (icon) / Muted neutral bar |

### Data sources

| Source   | Store path                                | Sensor types                          |
| -------- | ----------------------------------------- | ------------------------------------- |
| Host CPU | `server/getHostStats` → `tempSensor`      | `rpi_temperature`, `temperature_host` |
| MCUs     | `printer/getMcus` → each `mcu.tempSensor` | Built-in MCU temp sensors             |

Host sensor label is derived from the Klipper config section name via `convertName()`, falling back to the localised "CPU" string.

## Files

| File                                                                            | Role                                                             |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `mainsail/src/components/panels/TemperaturePanel.vue`                           | Parent panel — conditionally renders embroidery or standard list |
| `mainsail/src/components/panels/Temperature/TemperaturePanelEmbroideryList.vue` | Embroidery card layout with progress bars                        |

## Related docs

- [mainsail-theme.md](mainsail-theme.md) — StitchLab theme that enables embroidery mode
- [embroidery-dashboard-preview.md](embroidery-dashboard-preview.md) — Status Panel embroidery components
