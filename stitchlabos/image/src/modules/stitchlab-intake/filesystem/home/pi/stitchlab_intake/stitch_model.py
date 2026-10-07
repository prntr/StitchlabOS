"""The embroidery stitch model, shared by the parser and the renderer.

Pure functions of Z positions and commands: no file access. Contract
(beta6): one stitch is one handwheel turn, a Z step of +5 mm, with the
needle up at multiples of 5 (``embroidery_macros.cfg``).
"""

from __future__ import annotations

import re
from typing import Optional

from . import limits


# --- Needle model --------------------------------------------------------
#
# One stitch is one Z-only move up, a Z step of +NEEDLE_PERIOD_MM (one
# handwheel turn). Ink/Stitch writes `G0 X Y` then `G0 Z+5`; TurtleStitch
# `G1 X Y` then `G1 Z+5`. G0 versus G1 says nothing about stitches. The
# Mainsail preview (parseEmbroideryGcode.ts, beta6) counts the same way:
# one stitch per Z-only line; a combined X/Y/Z move is drawn as a stitch
# point but not counted (the intake blocks it).

# Float noise in exported coordinates; a real Z step is never this small.
Z_EPSILON_MM = 1e-3
# How far a Z step may differ from one turn before the intake says so.
Z_STEP_TOLERANCE_MM = 0.01


def is_needle_up(z: float) -> bool:
    period = limits.NEEDLE_PERIOD_MM
    return abs(z - period * round(z / period)) <= limits.NEEDLE_UP_TOLERANCE_MM


def is_stitch_step(z_from: float, z_to: float) -> bool:
    """Whether a move from ``z_from`` to ``z_to`` turns the needle forward."""
    return z_to > z_from + Z_EPSILON_MM


def is_one_turn(z_from: float, z_to: float) -> bool:
    """Whether a Z step is exactly one stitch (+NEEDLE_PERIOD_MM)."""
    return abs((z_to - z_from) - limits.NEEDLE_PERIOD_MM) <= Z_STEP_TOLERANCE_MM


_COUNT_PARAM_RE = re.compile(r"\bCOUNT\s*=\s*(\d+)", re.IGNORECASE)


def macro_stitches(head: str, command_text: str) -> int:
    """Stitches made by the embroidery macros that turn the handwheel."""
    if head == "STITCH":
        return 1
    if head == "LOCK_STITCH":
        m = _COUNT_PARAM_RE.search(command_text)
        return int(m.group(1)) if m else limits.LOCK_STITCH_DEFAULT_COUNT
    return 0


class StitchSequence:
    """Settles every XY move as a stitch segment or a jump.

    Shared by the parser (counts) and the renderer (drawing), so both see
    the same model. An XY move that a stitch follows carries thread; one
    that another XY move or the end of the file follows is a jump. Each
    call returns ``(kind, payload)`` for the move it settled, or ``None``;
    ``kind`` is ``"stitch"`` or ``"travel"`` and ``payload`` is whatever the
    caller passed with that move.
    """

    def __init__(self) -> None:
        self._pending: Optional[tuple[object]] = None

    def move(self, payload: object) -> Optional[tuple[str, object]]:
        settled = ("travel", self._pending[0]) if self._pending else None
        self._pending = (payload,)
        return settled

    def stitch(self) -> Optional[tuple[str, object]]:
        settled = ("stitch", self._pending[0]) if self._pending else None
        self._pending = None
        return settled

    def finish(self) -> Optional[tuple[str, object]]:
        settled = ("travel", self._pending[0]) if self._pending else None
        self._pending = None
        return settled
