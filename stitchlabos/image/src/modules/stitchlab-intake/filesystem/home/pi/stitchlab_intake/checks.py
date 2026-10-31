"""Post-parse checks that depend on external context.

The parser in ``parser.py`` only knows what it can derive from the file
alone. Anything that needs hoop geometry, machine envelope, or Klipper
configuration lives here so the CLI/Moonraker layer can plug it in.

Phase 1 ships hoop-bounds and diagnostic-capping. Macro-existence against
Klipper's gcode_macro list arrives with the Moonraker component (Phase 3).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Optional

from .parser import AnalysisResult, Bounds, Diagnostic


# Cap how many diagnostics of the same code we keep verbatim. Above the
# cap we emit a single summary entry. Keeps the JSON report bounded for
# pathological files (e.g. thousands of LONG_JUMP).
MAX_DIAGNOSTICS_PER_CODE = 25


@dataclass
class HoopSpec:
    """Subset of the full hoop specification needed for Phase-1 checks.

    Mirrors the fields named in the plan under "Benötigte Rahmendaten".
    Phase 1 only consumes the usable area; Phase 3 (machine envelope) will
    add machine_origin and no_go_zones.
    """
    hoop_id: str = "standard"
    usable_width_mm: float = 0.0
    usable_height_mm: float = 0.0
    safe_margin_mm: float = 0.0
    version: str = "preliminary"
    frame_geometry: str = ""
    physical_width_mm: float = 0.0
    physical_height_mm: float = 0.0


def _placement_float(placement: Optional[dict], key: str, default: float) -> float:
    if not placement:
        return default
    try:
        return float(placement.get(key, default))
    except (TypeError, ValueError):
        return default


def placement_adjusted_bounds(bounds: Bounds,
                              hoop: Optional[HoopSpec],
                              placement: Optional[dict]) -> Bounds:
    if not placement or not bounds.is_valid:
        return bounds

    pivot = placement.get("pivot", "design")
    if pivot == "origin":
        pivot_x, pivot_y = 0.0, 0.0
    elif pivot == "frame" and hoop and hoop.usable_width_mm > 0 and hoop.usable_height_mm > 0:
        pivot_x, pivot_y = hoop.usable_width_mm / 2, hoop.usable_height_mm / 2
    else:
        pivot_x = (bounds.min_x + bounds.max_x) / 2
        pivot_y = (bounds.min_y + bounds.max_y) / 2

    scale = _placement_float(placement, "scale", 1.0)
    angle = math.radians(_placement_float(placement, "rotation_deg", 0.0))
    ox = _placement_float(placement, "offset_x", 0.0)
    oy = _placement_float(placement, "offset_y", 0.0)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    adjusted = Bounds()
    for x in (bounds.min_x, bounds.max_x):
        for y in (bounds.min_y, bounds.max_y):
            dx = (x - pivot_x) * scale
            dy = (y - pivot_y) * scale
            adjusted.expand(
                pivot_x + dx * cos_a - dy * sin_a + ox,
                pivot_y + dx * sin_a + dy * cos_a + oy,
            )
    return adjusted


# Rotation and float formatting leave sub-micron noise on bounds that sit
# exactly on the hoop edge; do not block a job over that.
_BOUNDS_EPSILON_MM = 1e-6


def check_hoop_bounds(result: AnalysisResult,
                      hoop: Optional[HoopSpec],
                      bounds: Optional[Bounds] = None) -> None:
    """Compare placed design bounds against the usable hoop area.

    ``bounds`` are the placement-adjusted bounds from
    ``placement_adjusted_bounds``. The usable area spans
    ``[margin, usable - margin]`` on both axes — the same frame the renderer,
    GCode Studio and the machine (position_min 0) use. Size alone is not
    enough: an offset moves a design out of the hoop without changing its
    width or height.
    """
    bounds = bounds or result.bounds
    if hoop is None or not bounds.is_valid:
        return
    if hoop.usable_width_mm <= 0 or hoop.usable_height_mm <= 0:
        return

    margin = hoop.safe_margin_mm
    width_limit = hoop.usable_width_mm - 2 * margin
    height_limit = hoop.usable_height_mm - 2 * margin

    if bounds.width > width_limit:
        result.diagnostics.append(Diagnostic(
            "error", "DESIGN_TOO_WIDE",
            f"Design width {bounds.width:.1f} mm exceeds usable hoop "
            f"width {width_limit:.1f} mm (hoop_id={hoop.hoop_id})",
        ))
    if bounds.height > height_limit:
        result.diagnostics.append(Diagnostic(
            "error", "DESIGN_TOO_TALL",
            f"Design height {bounds.height:.1f} mm exceeds usable hoop "
            f"height {height_limit:.1f} mm (hoop_id={hoop.hoop_id})",
        ))

    # A design that fits by size can still sit outside the hoop. Report the
    # position only where the size fits, so one cause gives one error.
    lo_x, hi_x = margin, hoop.usable_width_mm - margin
    lo_y, hi_y = margin, hoop.usable_height_mm - margin
    outside = []
    if bounds.width <= width_limit:
        if bounds.min_x < lo_x - _BOUNDS_EPSILON_MM:
            outside.append(f"{lo_x - bounds.min_x:.1f} mm past the left edge")
        if bounds.max_x > hi_x + _BOUNDS_EPSILON_MM:
            outside.append(f"{bounds.max_x - hi_x:.1f} mm past the right edge")
    if bounds.height <= height_limit:
        if bounds.min_y < lo_y - _BOUNDS_EPSILON_MM:
            outside.append(f"{lo_y - bounds.min_y:.1f} mm past the bottom edge")
        if bounds.max_y > hi_y + _BOUNDS_EPSILON_MM:
            outside.append(f"{bounds.max_y - hi_y:.1f} mm past the top edge")
    if outside:
        result.diagnostics.append(Diagnostic(
            "error", "DESIGN_OUTSIDE_HOOP",
            f"Design X {bounds.min_x:.1f}..{bounds.max_x:.1f} mm, "
            f"Y {bounds.min_y:.1f}..{bounds.max_y:.1f} mm lies outside the "
            f"usable hoop area X {lo_x:.1f}..{hi_x:.1f} mm, "
            f"Y {lo_y:.1f}..{hi_y:.1f} mm: {', '.join(outside)} "
            f"(hoop_id={hoop.hoop_id})",
        ))


@dataclass(frozen=True)
class MachineLimits:
    """XY travel of the machine Klipper runs, in machine coordinates.

    The single source is Klipper's loaded config (``[stepper_x]`` /
    ``[stepper_y]`` ``position_min``/``position_max`` of the running
    ``printer.cfg``), read through Moonraker at analysis time. The hoop
    (hoops.json) is a property of the frame, not of the machine; a design
    has to fit both. The image's printer.cfg travels X 0..90, Y 0..120,
    the 2026-09-29 hybrid config X 0..80, Y 0..130, the hoop is 80 x 130.
    """
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @classmethod
    def from_klipper_settings(cls, settings: object) -> Optional["MachineLimits"]:
        """Parse Klipper's ``configfile.settings``; None if X/Y travel is missing."""
        if not isinstance(settings, dict):
            return None
        try:
            values = {}
            for axis in ("x", "y"):
                stepper = settings[f"stepper_{axis}"]
                values[f"{axis}_min"] = float(stepper.get("position_min", 0.0))
                values[f"{axis}_max"] = float(stepper["position_max"])
        except (KeyError, TypeError, ValueError, AttributeError):
            return None
        return cls(**values)

    @classmethod
    def from_dict(cls, data: object) -> Optional["MachineLimits"]:
        """Parse the ``{"x": [min, max], "y": [min, max]}`` form of ``as_dict``."""
        if not isinstance(data, dict):
            return None
        try:
            (x_min, x_max), (y_min, y_max) = data["x"], data["y"]
            return cls(float(x_min), float(x_max), float(y_min), float(y_max))
        except (KeyError, TypeError, ValueError):
            return None

    def as_dict(self) -> dict:
        return {"x": [self.x_min, self.x_max], "y": [self.y_min, self.y_max]}


def check_machine_bounds(result: AnalysisResult,
                         machine: Optional[MachineLimits],
                         bounds: Optional[Bounds] = None) -> None:
    """Block a placed design that leaves the machine's XY travel.

    Klipper stops the job with "Move out of range" at the first such move,
    with the needle wherever it is. A workshop design reaching Y 124.6 mm
    passed the 80 x 130 hoop check and failed on a machine that travels
    Y 0..120 (run of 2026-09-29).
    """
    bounds = bounds or result.bounds
    if machine is None or not bounds.is_valid:
        return
    eps = _BOUNDS_EPSILON_MM
    outside = []
    if bounds.min_x < machine.x_min - eps or bounds.max_x > machine.x_max + eps:
        outside.append(f"X {bounds.min_x:.1f}..{bounds.max_x:.1f} mm "
                       f"(machine X {machine.x_min:g}..{machine.x_max:g})")
    if bounds.min_y < machine.y_min - eps or bounds.max_y > machine.y_max + eps:
        outside.append(f"Y {bounds.min_y:.1f}..{bounds.max_y:.1f} mm "
                       f"(machine Y {machine.y_min:g}..{machine.y_max:g})")
    if outside:
        result.diagnostics.append(Diagnostic(
            "error", "DESIGN_OUTSIDE_MACHINE",
            f"Design leaves this machine's travel: {', '.join(outside)}. "
            "Klipper would stop the job (printer.cfg [stepper_x]/[stepper_y])",
        ))


def cap_diagnostics(result: AnalysisResult,
                    per_code: int = MAX_DIAGNOSTICS_PER_CODE) -> None:
    """Reduce per-code diagnostic spam to ``per_code`` entries + one summary.

    Preserves the first N occurrences (most useful for the user — they
    point at concrete line numbers) and appends a synthetic summary
    Diagnostic with the overflow count.
    """
    counts: Counter = Counter()
    kept: list[Diagnostic] = []
    overflow: Counter = Counter()
    overflow_severity: dict[str, str] = {}

    for diag in result.diagnostics:
        counts[diag.code] += 1
        if counts[diag.code] <= per_code:
            kept.append(diag)
        else:
            overflow[diag.code] += 1
            overflow_severity.setdefault(diag.code, diag.severity)

    for code, extra in overflow.items():
        kept.append(Diagnostic(
            severity=overflow_severity[code],
            code=f"{code}__SUMMARY",
            message=f"{extra} additional occurrences of {code} not listed individually",
        ))

    result.diagnostics = kept
