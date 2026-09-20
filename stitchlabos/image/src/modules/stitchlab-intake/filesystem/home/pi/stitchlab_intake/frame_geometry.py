"""Calibrated frame geometry assets used by thumbnail rendering."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Optional


_FRAME_FILES = {
    "standard": "stitchlab_standard.json",
    "stitchlab-standard": "stitchlab_standard.json",
    "stitchlab_standard": "stitchlab_standard.json",
}


@lru_cache(maxsize=8)
def load_frame_geometry(name: str) -> Optional[dict]:
    """Return a frame geometry asset by id, or ``None`` if unavailable."""
    key = (name or "").strip().lower()
    filename = _FRAME_FILES.get(key)
    if not filename:
        return None
    try:
        with resources.files(__package__).joinpath("frames", filename).open(
            "r", encoding="utf-8"
        ) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
