"""JSON report serialisation for the stitchlab_intake.v1 schema.

The schema mirrors the structure documented in
``Reports&Plans/G-Code Intake Stable Job Preview Plan.md`` under
"Metadata-Schema". Anything that requires placement context (final
thumbnail, placement-adjusted bounds) is filled in later phases.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .parser import AnalysisResult
from .version import CHECKER_VERSION, SCHEMA_VERSION


def build_analysis_key(sha256: str) -> str:
    """Cache key for the file-only analysis (no placement, no hoop)."""
    return f"{sha256}:{CHECKER_VERSION}"


# Identity placement: no offset, no rotation, no scale, design pivot.
DEFAULT_PLACEMENT = {
    "hoop_id": "standard",
    "offset_x": 0.0,
    "offset_y": 0.0,
    "rotation_deg": 0.0,
    "scale": 1.0,
    "pivot": "design",
}


def build_preview_key(analysis_key: str,
                      hoop_id: str = "standard",
                      hoop_version: str = "preliminary",
                      placement: Optional[dict] = None) -> str:
    """Cache key for a placement-applied thumbnail.

    Mirrors the formula in the plan: placement-only changes (offset, scale,
    rotation, pivot) invalidate the thumbnail without re-running parser
    analysis. Phase 2 renders without placement transforms, so the typical
    preview_key is just ``analysis_key + hoop_id + hoop_version``; future
    phases hand in a real placement dict.
    """
    p = placement or DEFAULT_PLACEMENT
    parts = [
        analysis_key,
        f"hoop={hoop_id}",
        f"hv={hoop_version}",
        f"ox={p.get('offset_x', 0):.3f}",
        f"oy={p.get('offset_y', 0):.3f}",
        f"rot={p.get('rotation_deg', 0):.2f}",
        f"sc={p.get('scale', 1):.4f}",
        f"pv={p.get('pivot', 'design')}",
    ]
    if p.get("frame_width_mm") is not None:
        parts.append(f"fw={p.get('frame_width_mm', 0):.3f}")
    if p.get("frame_height_mm") is not None:
        parts.append(f"fh={p.get('frame_height_mm', 0):.3f}")
    return "|".join(parts)


def result_to_dict(result: AnalysisResult,
                   placement: Optional[dict] = None,
                   thumbnail: Optional[dict] = None,
                   preview_key: Optional[str] = None) -> dict:
    diagnostics = [d.as_dict() for d in result.diagnostics]
    errors = [d for d in diagnostics if d["severity"] == "error"]
    warnings = [d for d in diagnostics if d["severity"] == "warning"]
    infos = [d for d in diagnostics if d["severity"] == "info"]

    return {
        "schema": SCHEMA_VERSION,
        "status": result.status,
        "analysis_key": build_analysis_key(result.sha256),
        "preview_key": preview_key,
        "source": {
            "filename": os.path.basename(result.file_path),
            "size": result.file_size,
            "modified": result.file_modified,
            "sha256": result.sha256,
            "detected_origin": result.detected_origin,
        },
        "units": result.units,
        "units_explicit": result.units_explicit,
        "bounds": result.bounds.as_dict(),
        "stats": result.stats.as_dict(),
        "stitchlab_meta": result.stitchlab_meta,
        "referenced_unknown_macros": sorted(result.referenced_unknown_macros),
        "placement": placement,
        "thumbnail": thumbnail,
        "errors": errors,
        "warnings": warnings,
        "info": infos,
    }


def result_to_json(result: AnalysisResult, **kwargs) -> str:
    return json.dumps(result_to_dict(result, **kwargs), indent=2, sort_keys=False)
