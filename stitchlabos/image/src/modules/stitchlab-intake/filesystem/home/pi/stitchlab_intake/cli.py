"""Command-line entry: ``stitchlab-gcode-intake {analyze,render} <file>``.

Exit codes (analyze):
    0 — valid
    1 — warnings only
    2 — at least one error
    3 — CLI / IO failure (file not found, etc.)

The ``render`` subcommand exits 0 on success, 2 if the file has no
renderable geometry, 3 on IO failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from . import checks, limits
from .parser import AnalysisResult, parse_file
from .report import (
    DEFAULT_PLACEMENT,
    build_analysis_key,
    build_preview_key,
    result_to_json,
)


_STATUS_EXIT = {"valid": 0, "warnings": 1, "blocked": 2}

# Default hoops.json location on the Pi; overridable via --hoops-config.
_DEFAULT_HOOPS_JSON = "/home/pi/stitchlab_intake/hoops.json"


def _hoop_from_args(args: argparse.Namespace) -> Optional[checks.HoopSpec]:
    # Explicit width/height take precedence — keeps the Phase-1 CLI surface
    # working unchanged. Falls back to hoops.json lookup by --hoop id.
    if args.hoop_width_mm and args.hoop_height_mm:
        return checks.HoopSpec(
            hoop_id=args.hoop_id,
            usable_width_mm=args.hoop_width_mm,
            usable_height_mm=args.hoop_height_mm,
            safe_margin_mm=args.hoop_safe_margin_mm,
            version=args.hoop_version,
        )
    if args.hoop and os.path.exists(args.hoops_config):
        spec = limits.load_hoop_spec(args.hoops_config, args.hoop)
        if spec and spec.usable_width_mm > 0 and spec.usable_height_mm > 0:
            return spec
    return None


def _placement_from_args(args: argparse.Namespace,
                         hoop: Optional[checks.HoopSpec]) -> dict:
    placement = dict(DEFAULT_PLACEMENT)
    if getattr(args, "placement_json", None):
        try:
            supplied = json.loads(args.placement_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid --placement-json: {exc}") from exc
        if not isinstance(supplied, dict):
            raise ValueError("--placement-json must decode to an object")
        placement.update(supplied)
    if hoop:
        placement["hoop_id"] = hoop.hoop_id
    else:
        placement["hoop_id"] = placement.get("hoop_id") or args.hoop_id
    for key in ("offset_x", "offset_y", "rotation_deg", "scale"):
        try:
            placement[key] = float(placement.get(key, DEFAULT_PLACEMENT[key]))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid placement field {key}") from exc
    for key in ("frame_width_mm", "frame_height_mm"):
        if key not in placement or placement[key] is None:
            continue
        try:
            placement[key] = float(placement[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid placement field {key}") from exc
    placement["pivot"] = str(placement.get("pivot") or "design")
    return placement


def _progress(args: argparse.Namespace, fraction: float, stage: str) -> None:
    if not getattr(args, "worker_mode", False):
        return
    # Machine-readable line consumed by the Moonraker component's worker
    # subprocess wrapper. One line per stage; fraction in [0, 1].
    fraction = max(0.0, min(1.0, fraction))
    sys.stderr.write(f"PROGRESS {fraction:.3f} {stage}\n")
    sys.stderr.flush()


def _load(path: str) -> AnalysisResult:
    return parse_file(path)


def _cmd_analyze(args: argparse.Namespace) -> int:
    _progress(args, 0.0, "parse")
    try:
        result = _load(args.file)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 3
    except PermissionError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 3

    try:
        hoop = _hoop_from_args(args)
        placement = _placement_from_args(args, hoop)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    bounds_for_check = checks.placement_adjusted_bounds(result.bounds, hoop, placement)
    checks.check_hoop_bounds(result, hoop, bounds=bounds_for_check)
    checks.cap_diagnostics(result)
    _progress(args, 0.5, "checks")

    thumbnail_meta = None
    if args.thumbnail_out:
        thumbnail_meta = _render_or_warn(args.file, result, hoop,
                                         args.thumbnail_out, args.thumbnail_size,
                                         placement=placement)
        _progress(args, 0.9, "render")

    extras = {}
    if thumbnail_meta is not None:
        extras["thumbnail"] = thumbnail_meta.as_dict()
        extras["preview_key"] = build_preview_key(
            analysis_key=build_analysis_key(result.sha256),
            hoop_id=hoop.hoop_id if hoop else "standard",
            hoop_version=hoop.version if hoop else "preliminary",
            placement=placement,
        )

    output = result_to_json(result, placement=placement, **extras)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
    else:
        print(output)

    _progress(args, 1.0, "done")
    return _STATUS_EXIT.get(result.status, 2)


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        result = _load(args.file)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 3
    except PermissionError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 3

    if not result.bounds.is_valid:
        print("error: file has no XY geometry to render", file=sys.stderr)
        return 2

    hoop = _hoop_from_args(args)
    meta = _render_or_warn(args.file, result, hoop, args.output, args.size)
    if meta is None:
        return 2
    print(f"wrote {meta.path} ({meta.width}x{meta.height})", file=sys.stderr)
    return 0


def _render_or_warn(file_path, result, hoop, output_path, size,
                    placement: Optional[dict] = None):
    try:
        from . import renderer
    except ImportError as exc:
        print(f"error: Pillow not installed: {exc}", file=sys.stderr)
        return None
    opts = renderer.RenderOptions(size=size) if size else renderer.RenderOptions()
    try:
        return renderer.render_thumbnail(
            file_path, result, output_path, hoop=hoop,
            placement=placement, options=opts,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def _add_hoop_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--hoop", default=None,
                   help="Hoop id resolved via --hoops-config (overrides --hoop-id when set)")
    p.add_argument("--hoops-config", default=_DEFAULT_HOOPS_JSON,
                   help="Path to hoops.json config")
    p.add_argument("--hoop-id", default="standard")
    p.add_argument("--hoop-version", default="preliminary")
    p.add_argument("--hoop-width-mm", type=float, default=0.0,
                   help="Usable hoop width in mm (omit to skip hoop check)")
    p.add_argument("--hoop-height-mm", type=float, default=0.0,
                   help="Usable hoop height in mm (omit to skip hoop check)")
    p.add_argument("--hoop-safe-margin-mm", type=float, default=0.0)
    p.add_argument("--worker-mode", action="store_true",
                   help="Emit PROGRESS lines on stderr for the Moonraker worker")
    p.add_argument("--placement-json", default=None,
                   help="JSON placement object for preview key and rendering")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stitchlab-gcode-intake",
        description="StitchLab G-Code intake: compatibility check and metadata.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    analyze = sub.add_parser("analyze", help="Analyse a G-code file")
    analyze.add_argument("file", help="Path to the G-code file")
    analyze.add_argument("--output", "-o", help="Write JSON to this path instead of stdout")
    analyze.add_argument("--thumbnail-out",
                         help="Render a thumbnail PNG to this path while analysing")
    analyze.add_argument("--thumbnail-size", type=int, default=0,
                         help="Thumbnail edge length in px (default 768)")
    _add_hoop_args(analyze)
    analyze.set_defaults(func=_cmd_analyze)

    render = sub.add_parser("render", help="Render only the thumbnail PNG")
    render.add_argument("file", help="Path to the G-code file")
    render.add_argument("--output", "-o", required=True, help="PNG output path")
    render.add_argument("--size", type=int, default=0,
                        help="Thumbnail edge length in px (default 768)")
    _add_hoop_args(render)
    render.set_defaults(func=_cmd_render)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
