"""PNG thumbnail renderer for stickable G-code files.

Streams the file once, maps coordinates from design-space mm into image
pixels, and draws each G1 stitch segment with Pillow. Travel moves (G0)
are hidden by default. G2/G3 arcs are approximated as chords in Phase 2;
proper arc flattening is a follow-up.

The renderer consumes ``AnalysisResult.bounds`` to know where the design
lives; it does not re-compute geometry. A drift test in the renderer
tests verifies the second pass sees the same coordinates as the parser.

Public entry point: ``render_thumbnail(path, analysis, output_path, ...)``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
import math
from typing import Iterator, Optional

from .parser import (
    AnalysisResult,
    ModalState,
    _compute_new_xy,
    _float_or_none,
    iter_lines,
    parse_command,
    sniff_encoding,
    split_line,
    to_mm,
)
from .checks import HoopSpec
from .frame_geometry import load_frame_geometry


# --- Rendering options ---------------------------------------------------


@dataclass
class RenderOptions:
    size: int = 768
    margin_px: int = 24
    background: tuple = (255, 255, 255, 0)        # transparent
    stitch_color: tuple = (40, 40, 40, 255)
    hoop_outline_color: tuple = (180, 180, 180, 255)
    usable_outline_color: tuple = (210, 210, 210, 255)
    travel_color: tuple = (220, 220, 220, 100)
    show_travel: bool = False
    line_width: int = 1


@dataclass
class ThumbnailMeta:
    path: str
    width: int
    height: int

    def as_dict(self, relative_to: Optional[str] = None) -> dict:
        import os
        rel = self.path
        if relative_to:
            try:
                rel = os.path.relpath(self.path, relative_to)
            except ValueError:
                rel = self.path
        return {"relative_path": rel, "width": self.width, "height": self.height}


# --- Move stream (renderer-internal) -------------------------------------
#
# This mirrors the modal-state handling in parser.py without producing
# diagnostics. Shared helpers (split_line, parse_command, _compute_new_xy,
# to_mm) keep Klasse-A-Normalisierung in lockstep between the two passes;
# a drift test catches accidental divergence.


@dataclass
class _MoveEvent:
    kind: str                                     # "stitch" | "travel" | "arc"
    end_x: float
    end_y: float
    color: Optional[tuple]                        # (r, g, b) or None


_COLOR_STITCHLAB_RE = re.compile(
    r"STITCHLAB_COLOR\s*[:=]\s*r\s*=\s*(\d+)\s+g\s*=\s*(\d+)\s+b\s*=\s*(\d+)",
    re.IGNORECASE,
)
_COLOR_GENERIC_RE = re.compile(
    r"\bcolor\s+r\s*[:=]\s*(\d+)\s+g\s*[:=]\s*(\d+)\s+b\s*[:=]\s*(\d+)",
    re.IGNORECASE,
)


def _parse_color_comment(comment: str) -> Optional[tuple]:
    if not comment:
        return None
    for rx in (_COLOR_STITCHLAB_RE, _COLOR_GENERIC_RE):
        m = rx.search(comment)
        if m:
            return tuple(max(0, min(255, int(g))) for g in m.groups())
    return None


def _iter_render_moves(path: str) -> Iterator[_MoveEvent]:
    encoding, _, _ = sniff_encoding(path)
    state = ModalState()
    current_color: Optional[tuple] = None
    try:
        for _line_no, raw in iter_lines(path, encoding):
            command_text, line_comment, paren_comments, _ = split_line(raw)
            for c in (line_comment, *paren_comments):
                col = _parse_color_comment(c)
                if col is not None:
                    current_color = col
            if not command_text:
                continue
            head, params = parse_command(command_text)
            if head is None:
                continue
            if head == "G20":
                state.units_mm = False
                state.units_explicit = True
                continue
            if head == "G21":
                state.units_mm = True
                state.units_explicit = True
                continue
            if head == "G90":
                state.absolute = True
                continue
            if head == "G91":
                state.absolute = False
                continue
            if head == "G92":
                for axis in ("X", "Y", "Z"):
                    v = _float_or_none(params.get(axis))
                    if v is None:
                        continue
                    mm = to_mm(v, state.units_mm)
                    if axis == "X":
                        state.x = mm
                    elif axis == "Y":
                        state.y = mm
                    else:
                        state.z = mm
                continue
            if head not in ("G0", "G1", "G2", "G3"):
                continue
            new_xy = _compute_new_xy(state, params)
            if new_xy is None:
                continue
            kind = {"G0": "travel", "G1": "stitch"}.get(head, "arc")
            yield _MoveEvent(kind, new_xy[0], new_xy[1], current_color)
            state.x, state.y = new_xy
    except UnicodeDecodeError:
        return


# --- Public entry point --------------------------------------------------


def render_thumbnail(
    file_path: str,
    analysis: AnalysisResult,
    output_path: str,
    *,
    hoop: Optional[HoopSpec] = None,
    placement: Optional[dict] = None,
    options: Optional[RenderOptions] = None,
) -> ThumbnailMeta:
    """Render a PNG thumbnail to ``output_path`` and return its meta.

    Raises ``ValueError`` if the analysis indicates no usable geometry —
    callers should gate on ``analysis.bounds.is_valid`` first.
    """
    from PIL import Image, ImageDraw

    opts = options or RenderOptions()
    if not analysis.bounds.is_valid:
        raise ValueError("Cannot render thumbnail: no XY geometry in source")

    bounds = analysis.bounds
    placed_bounds = _placed_bounds(bounds, hoop, placement)
    view_min_x, view_min_y, view_w, view_h = _viewport(placed_bounds, hoop, placement)

    inner = opts.size - 2 * opts.margin_px
    if inner <= 0:
        raise ValueError("margin_px too large for size")
    scale = min(inner / view_w, inner / view_h)
    used_w_px = view_w * scale
    used_h_px = view_h * scale
    off_x = (opts.size - used_w_px) / 2
    off_y = (opts.size - used_h_px) / 2

    def to_px(x_mm: float, y_mm: float) -> tuple[int, int]:
        px = off_x + (x_mm - view_min_x) * scale
        py = off_y + used_h_px - (y_mm - view_min_y) * scale
        return int(round(px)), int(round(py))

    img = Image.new("RGBA", (opts.size, opts.size), opts.background)
    draw = ImageDraw.Draw(img)

    if hoop and hoop.usable_width_mm > 0 and hoop.usable_height_mm > 0:
        _draw_hoop(draw, to_px, hoop, opts, bounds, placement)

    last_pixel: Optional[tuple[int, int]] = None
    last_drawn_pair: Optional[tuple[tuple[int, int], tuple[int, int]]] = None

    for move in _iter_render_moves(file_path):
        placed = _apply_placement(move.end_x, move.end_y, bounds, hoop, placement)
        end_px = to_px(placed[0], placed[1])
        if last_pixel is None:
            last_pixel = end_px
            continue
        if move.kind == "travel" and not opts.show_travel:
            last_pixel = end_px
            continue

        pair = (last_pixel, end_px)
        if pair == last_drawn_pair or last_pixel == end_px:
            last_pixel = end_px
            continue

        if move.kind == "travel":
            color = opts.travel_color
        elif move.color is not None:
            color = (*move.color, 255)
        else:
            color = opts.stitch_color

        draw.line([last_pixel, end_px], fill=color, width=opts.line_width)
        last_drawn_pair = pair
        last_pixel = end_px

    img.save(output_path, "PNG", optimize=True)
    return ThumbnailMeta(path=output_path, width=opts.size, height=opts.size)


# --- Helpers -------------------------------------------------------------


def _float_from_placement(placement: Optional[dict], key: str, default: float) -> float:
    if not placement:
        return default
    try:
        return float(placement.get(key, default))
    except (TypeError, ValueError):
        return default


def _pivot(bounds, hoop: Optional[HoopSpec], placement: Optional[dict]) -> tuple[float, float]:
    pivot = (placement or {}).get("pivot", "design")
    if pivot == "origin":
        return 0.0, 0.0
    if pivot == "frame" and hoop and hoop.usable_width_mm > 0 and hoop.usable_height_mm > 0:
        return hoop.usable_width_mm / 2, hoop.usable_height_mm / 2
    return (bounds.min_x + bounds.max_x) / 2, (bounds.min_y + bounds.max_y) / 2


def _apply_placement(
    x_mm: float,
    y_mm: float,
    bounds,
    hoop: Optional[HoopSpec],
    placement: Optional[dict],
) -> tuple[float, float]:
    if not placement:
        return x_mm, y_mm
    scale = _float_from_placement(placement, "scale", 1.0)
    angle = math.radians(_float_from_placement(placement, "rotation_deg", 0.0))
    ox = _float_from_placement(placement, "offset_x", 0.0)
    oy = _float_from_placement(placement, "offset_y", 0.0)
    px, py = _pivot(bounds, hoop, placement)
    dx = (x_mm - px) * scale
    dy = (y_mm - py) * scale
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return px + dx * cos_a - dy * sin_a + ox, py + dx * sin_a + dy * cos_a + oy


def _placed_bounds(bounds, hoop: Optional[HoopSpec], placement: Optional[dict]):
    if not placement:
        return bounds
    from .parser import Bounds

    placed = Bounds()
    for x in (bounds.min_x, bounds.max_x):
        for y in (bounds.min_y, bounds.max_y):
            tx, ty = _apply_placement(x, y, bounds, hoop, placement)
            placed.expand(tx, ty)
    return placed


def _viewport(bounds, hoop: Optional[HoopSpec], placement: Optional[dict] = None) -> tuple[float, float, float, float]:
    view_w = max(bounds.width, 1.0)
    view_h = max(bounds.height, 1.0)
    view_min_x = bounds.min_x
    view_min_y = bounds.min_y
    frame_bounds = _frame_geometry_bounds(bounds, hoop, placement)
    if frame_bounds is not None:
        min_x, min_y, max_x, max_y = _union_rect(
            (view_min_x, view_min_y, view_min_x + view_w, view_min_y + view_h),
            frame_bounds,
        )
        return min_x, min_y, max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)
    if hoop and hoop.usable_width_mm > 0 and hoop.usable_height_mm > 0:
        if placement:
            return 0.0, 0.0, hoop.usable_width_mm, hoop.usable_height_mm
        cx = (bounds.min_x + bounds.max_x) / 2
        cy = (bounds.min_y + bounds.max_y) / 2
        view_w = max(view_w, hoop.usable_width_mm)
        view_h = max(view_h, hoop.usable_height_mm)
        view_min_x = cx - view_w / 2
        view_min_y = cy - view_h / 2
    return view_min_x, view_min_y, view_w, view_h


def _draw_hoop(draw, to_px, hoop: HoopSpec, opts: RenderOptions, design_bounds, placement: Optional[dict]) -> None:
    geometry = load_frame_geometry(hoop.frame_geometry)
    if geometry:
        _draw_frame_geometry(draw, to_px, geometry, hoop, opts, design_bounds, placement)
        return

    if placement:
        cx = hoop.usable_width_mm / 2
        cy = hoop.usable_height_mm / 2
    else:
        cx = (design_bounds.min_x + design_bounds.max_x) / 2
        cy = (design_bounds.min_y + design_bounds.max_y) / 2
    half_w = hoop.usable_width_mm / 2
    half_h = hoop.usable_height_mm / 2
    nw = to_px(cx - half_w, cy + half_h)
    se = to_px(cx + half_w, cy - half_h)
    draw.rectangle([nw, se], outline=opts.hoop_outline_color, width=1)
    if hoop.safe_margin_mm > 0:
        m = hoop.safe_margin_mm
        nw2 = to_px(cx - half_w + m, cy + half_h - m)
        se2 = to_px(cx + half_w - m, cy - half_h + m)
        draw.rectangle([nw2, se2], outline=opts.usable_outline_color, width=1)


def _frame_center(bounds, hoop: Optional[HoopSpec], placement: Optional[dict]) -> tuple[float, float]:
    if placement and hoop and hoop.usable_width_mm > 0 and hoop.usable_height_mm > 0:
        return hoop.usable_width_mm / 2, hoop.usable_height_mm / 2
    return (bounds.min_x + bounds.max_x) / 2, (bounds.min_y + bounds.max_y) / 2


def _frame_geometry_bounds(bounds, hoop: Optional[HoopSpec],
                           placement: Optional[dict]) -> Optional[tuple[float, float, float, float]]:
    if not hoop or not hoop.frame_geometry:
        return None
    geometry = load_frame_geometry(hoop.frame_geometry)
    if not geometry:
        return None
    b = geometry.get("bounds_mm") or {}
    try:
        min_x = float(b["min_x"])
        min_y = float(b["min_y"])
        max_x = float(b["max_x"])
        max_y = float(b["max_y"])
    except (KeyError, TypeError, ValueError):
        return None
    cx, cy = _frame_center(bounds, hoop, placement)
    return min_x + cx, min_y + cy, max_x + cx, max_y + cy


def _union_rect(a: tuple[float, float, float, float],
                b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _draw_frame_geometry(draw, to_px, geometry: dict, hoop: HoopSpec,
                         opts: RenderOptions, design_bounds, placement: Optional[dict]) -> None:
    cx, cy = _frame_center(design_bounds, hoop, placement)

    def placed(poly):
        return [to_px(float(x) + cx, float(y) + cy) for x, y in poly]

    for poly in geometry.get("outline") or []:
        if len(poly) < 2:
            continue
        draw.line(placed(poly), fill=opts.hoop_outline_color, width=1)

    for poly in geometry.get("stitch_area") or []:
        if len(poly) < 2:
            continue
        _draw_dashed_polyline(draw, placed(poly), fill=opts.usable_outline_color, width=1)


def _draw_dashed_polyline(draw, points, fill, width=1, dash_px=8, gap_px=6) -> None:
    for start, end in zip(points, points[1:]):
        _draw_dashed_segment(draw, start, end, fill=fill, width=width,
                             dash_px=dash_px, gap_px=gap_px)


def _draw_dashed_segment(draw, start, end, fill, width=1, dash_px=8, gap_px=6) -> None:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= 0:
        return
    step = dash_px + gap_px
    distance = 0.0
    while distance < length:
        dash_end = min(distance + dash_px, length)
        a = distance / length
        b = dash_end / length
        draw.line(
            [
                (x1 + dx * a, y1 + dy * a),
                (x1 + dx * b, y1 + dy * b),
            ],
            fill=fill,
            width=width,
        )
        distance += step
