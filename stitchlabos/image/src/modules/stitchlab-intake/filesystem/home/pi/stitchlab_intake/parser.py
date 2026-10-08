"""Streaming G-Code parser with modal state.

Single pass over the file. Holds no full arrays of moves in memory: bounds
and stats are accumulated incrementally. Comment scanning tracks
parenthesis state per line so inline `(...)` blocks and trailing `;`
comments are both handled correctly.

Public entry point: ``parse_file(path)`` -> ``AnalysisResult``.

The parser only emits diagnostics it can derive from the file alone.
Placement, hoop, machine-envelope and macro-existence checks live in
``checks.py`` because they depend on external context (hoop spec, Klipper
config) that the CLI/Moonraker layer supplies.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

from . import limits
from .stitch_model import (
    Z_EPSILON_MM,
    StitchSequence,
    is_needle_up,
    is_one_turn,
    is_stitch_step,
)


# --- Public data types ---------------------------------------------------


@dataclass
class Diagnostic:
    severity: str           # "error" | "warning" | "info"
    code: str               # short stable token, e.g. "UNTERMINATED_PAREN"
    message: str
    line_no: Optional[int] = None

    def as_dict(self) -> dict:
        d = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.line_no is not None:
            d["line_no"] = self.line_no
        return d


@dataclass
class Bounds:
    min_x: float = math.inf
    min_y: float = math.inf
    max_x: float = -math.inf
    max_y: float = -math.inf

    @property
    def is_valid(self) -> bool:
        return math.isfinite(self.min_x) and math.isfinite(self.max_x)

    @property
    def width(self) -> float:
        return (self.max_x - self.min_x) if self.is_valid else 0.0

    @property
    def height(self) -> float:
        return (self.max_y - self.min_y) if self.is_valid else 0.0

    def expand(self, x: float, y: float) -> None:
        if x < self.min_x:
            self.min_x = x
        if x > self.max_x:
            self.max_x = x
        if y < self.min_y:
            self.min_y = y
        if y > self.max_y:
            self.max_y = y

    def as_dict(self) -> dict:
        if not self.is_valid:
            return {"min_x": None, "min_y": None, "max_x": None,
                    "max_y": None, "width": 0.0, "height": 0.0}
        return {
            "min_x": round(self.min_x, 4),
            "min_y": round(self.min_y, 4),
            "max_x": round(self.max_x, 4),
            "max_y": round(self.max_y, 4),
            "width": round(self.width, 4),
            "height": round(self.height, 4),
        }


@dataclass
class Stats:
    stitch_count: int = 0
    jump_count: int = 0
    long_jump_count: int = 0
    color_changes: int = 0
    segment_count: int = 0
    command_count: int = 0

    def as_dict(self) -> dict:
        return {
            "stitch_count": self.stitch_count,
            "jump_count": self.jump_count,
            "long_jump_count": self.long_jump_count,
            "color_changes": self.color_changes,
            "segment_count": self.segment_count,
            "command_count": self.command_count,
        }


@dataclass
class AnalysisResult:
    file_path: str
    file_size: int
    file_modified: float
    sha256: str
    detected_origin: str = "unknown"
    units: str = "mm"
    units_explicit: bool = False
    bounds: Bounds = field(default_factory=Bounds)
    stats: Stats = field(default_factory=Stats)
    stitchlab_meta: dict = field(default_factory=dict)
    referenced_unknown_macros: set = field(default_factory=set)
    diagnostics: list = field(default_factory=list)

    @property
    def status(self) -> str:
        for d in self.diagnostics:
            if d.severity == "error":
                return "blocked"
        for d in self.diagnostics:
            if d.severity == "warning":
                return "warnings"
        return "valid"


# --- Modal state ---------------------------------------------------------


@dataclass
class ModalState:
    units_mm: bool = True              # default per plan: assume mm if unspecified
    units_explicit: bool = False
    absolute: bool = True              # G90 default
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    feedrate: Optional[float] = None
    color: Optional[str] = None


# --- Tokenizer -----------------------------------------------------------
#
# Strips comments from a raw line and returns:
#   (command_text, line_comment_text, paren_comments, paren_open_unterminated)
#
# Both `;...` (rest of line) and inline `(...)` are recognised. Multi-line
# parens are flagged as unterminated and treated as ending at EOL.
#
# Klipper itself knows only `;`, and cuts there even inside quotes. It has
# no `(...)` comments at all, so `G90 (abs)` reaches it as the unknown
# command "G90 (" and never runs. A `(` inside double quotes is a literal
# (`RESPOND MSG="a (b)"` works in Klipper), so it opens no comment here.

_COMMENT_TOKEN_PAREN = "("
_COMMENT_TOKEN_LINE = ";"


def _split_line(raw: str) -> tuple[str, str, list[str], bool]:
    out_parts: list[str] = []
    paren_parts: list[str] = []
    line_comment = ""
    i = 0
    n = len(raw)
    paren_depth = 0
    in_quote = False
    paren_buf: list[str] = []
    while i < n:
        ch = raw[i]
        if paren_depth == 0 and ch == _COMMENT_TOKEN_LINE:
            line_comment = raw[i + 1:].rstrip()
            break
        if paren_depth == 0 and ch == '"':
            in_quote = not in_quote
            out_parts.append(ch)
        elif in_quote:
            out_parts.append(ch)
        elif ch == _COMMENT_TOKEN_PAREN:
            paren_depth += 1
            paren_buf = []
        elif ch == ")" and paren_depth > 0:
            paren_depth -= 1
            paren_parts.append("".join(paren_buf))
            paren_buf = []
        elif paren_depth > 0:
            paren_buf.append(ch)
        else:
            out_parts.append(ch)
        i += 1
    unterminated = paren_depth > 0
    if unterminated and paren_buf:
        paren_parts.append("".join(paren_buf))
    return ("".join(out_parts).strip(), line_comment.strip(), paren_parts, unterminated)


def normalise_paren_comments(raw: str) -> Optional[str]:
    """Rewrite a line's ``(...)`` comments as one trailing ``;`` comment.

    ``G90 (use absolute coordinates)`` becomes
    ``G90 ; use absolute coordinates``, which Klipper runs. Comments move
    behind the command so no parameter ends up inside a ``;`` comment.
    Returns ``None`` when the line has no paren comment, or an unterminated
    one: whether that swallows the following lines is ambiguous, so such a
    file stays as it is and UNTERMINATED_PAREN blocks it.
    """
    command, line_comment, parens, unterminated = _split_line(raw)
    if unterminated or not parens:
        return None
    comments = [c.strip() for c in parens if c.strip()]
    if line_comment:
        comments.append(line_comment)
    if not comments:
        return command
    tail = "; " + " ; ".join(comments)
    return f"{command} {tail}" if command else tail


# Token like `X12.5`, `Y-3`, `F1500`, `E0.4`.
_PARAM_RE = re.compile(r"([A-Za-z])(-?\d+(?:[.,]\d+)?)")
# A bare command at the start, e.g. `G1`, `M104`, `STITCH`, `RUN_SHELL_COMMAND`.
_COMMAND_HEAD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)")
# STITCHLAB_KEY:VALUE — case-insensitive on key.
_STITCHLAB_RE = re.compile(r"STITCHLAB_([A-Z0-9_]+)\s*[:=]\s*(.*)", re.IGNORECASE)


def _parse_command(command_text: str) -> tuple[Optional[str], dict[str, str]]:
    if not command_text:
        return None, {}
    head_match = _COMMAND_HEAD_RE.match(command_text)
    if not head_match:
        return None, {}
    head = head_match.group(1).upper()
    rest = command_text[head_match.end():]
    params: dict[str, str] = {}
    for letter, value in _PARAM_RE.findall(rest):
        params[letter.upper()] = value.replace(",", ".")
    return head, params


def _float_or_none(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --- Origin detection ----------------------------------------------------


_ORIGIN_HINTS = (
    ("inkstitch", ("ink/stitch", "inkstitch")),
    ("turtlestitch", ("turtlestitch",)),
    ("gcode_studio", ("gcode studio", "gcode_studio", "stitchlab studio")),
)


def _detect_origin_from_comment(comment: str, current: str) -> str:
    if current != "unknown":
        return current
    text = comment.lower()
    for origin, needles in _ORIGIN_HINTS:
        for needle in needles:
            if needle in text:
                return origin
    return current


# --- Streaming entry point -----------------------------------------------


def parse_file(path: str) -> AnalysisResult:
    """Stream a G-code file end-to-end and return an AnalysisResult."""
    import hashlib

    st = os.stat(path)
    if st.st_size > limits.MAX_FILE_BYTES:
        result = AnalysisResult(
            file_path=path,
            file_size=st.st_size,
            file_modified=st.st_mtime,
            sha256="",
        )
        result.diagnostics.append(Diagnostic(
            "error", "FILE_TOO_LARGE",
            f"File exceeds maximum size of {limits.MAX_FILE_BYTES} bytes",
        ))
        return result

    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(64 * 1024)
            if not chunk:
                break
            hasher.update(chunk)

    result = AnalysisResult(
        file_path=path,
        file_size=st.st_size,
        file_modified=st.st_mtime,
        sha256=hasher.hexdigest(),
    )

    # Open in binary mode first to detect BOM and encoding issues; then
    # iterate as decoded text. We deliberately avoid `errors='replace'` on
    # the first attempt so we can flag encoding problems.
    encoding, has_bom, encoding_diag = _sniff_encoding(path)
    if encoding_diag is not None:
        result.diagnostics.append(encoding_diag)
    if has_bom:
        result.diagnostics.append(Diagnostic(
            "info", "BOM_DETECTED",
            f"File starts with a {encoding} BOM; stripped for parsing",
        ))

    try:
        line_iter = _iter_lines(path, encoding)
        _consume(line_iter, result)
    except UnicodeDecodeError as exc:
        result.diagnostics.append(Diagnostic(
            "error", "ENCODING_UNREADABLE",
            f"File cannot be decoded as {encoding}: {exc}",
        ))

    return result


def _sniff_encoding(path: str) -> tuple[str, bool, Optional[Diagnostic]]:
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", True, None
    if head.startswith(b"\xff\xfe") or head.startswith(b"\xfe\xff"):
        return "utf-16", True, None
    # Quick NUL-byte detection on a larger prefix to catch true binary.
    with open(path, "rb") as fh:
        probe = fh.read(8192)
    if b"\x00" in probe:
        return "utf-8", False, Diagnostic(
            "error", "BINARY_DATA",
            "File contains NUL bytes; not a valid text G-code file",
        )
    return "utf-8", False, None


def _iter_lines(path: str, encoding: str) -> Iterator[tuple[int, str]]:
    with open(path, "r", encoding=encoding, errors="strict", newline="") as fh:
        # newline="" so we see raw line endings; we then split manually so
        # the parser can flag mixed CR/LF without normalising silently.
        line_no = 0
        for raw in fh:
            line_no += 1
            # Strip exactly one trailing line terminator; keep the rest as
            # content. `splitlines(False)` would lose multi-terminator
            # information we want to detect.
            stripped = raw.rstrip("\r\n")
            yield line_no, stripped


def _consume(lines: Iterable[tuple[int, str]], result: AnalysisResult) -> None:
    state = ModalState()
    ctx = _ParseContext()
    line_count = 0

    for line_no, line in lines:
        line_count += 1
        if line_count > limits.MAX_LINE_COUNT:
            result.diagnostics.append(Diagnostic(
                "error", "TOO_MANY_LINES",
                f"File exceeds maximum line count of {limits.MAX_LINE_COUNT}",
                line_no=line_no,
            ))
            break
        if len(line) > limits.MAX_LINE_LENGTH:
            result.diagnostics.append(Diagnostic(
                "warning", "LINE_TOO_LONG",
                f"Line length {len(line)} exceeds {limits.MAX_LINE_LENGTH}",
                line_no=line_no,
            ))

        command_text, line_comment, paren_comments, unterminated = _split_line(line)

        if unterminated:
            result.diagnostics.append(Diagnostic(
                "error", "UNTERMINATED_PAREN",
                "Comment opened with '(' but never closed on the same line",
                line_no=line_no,
            ))
        elif paren_comments and command_text:
            result.diagnostics.append(Diagnostic(
                "error", "PAREN_COMMENT_WITH_COMMAND",
                "Klipper has no '(...)' comments: the command on this line "
                "would not run or would fail. Use ';' comments",
                line_no=line_no,
            ))
        elif paren_comments:
            result.diagnostics.append(Diagnostic(
                "info", "PAREN_COMMENT_LINE",
                "Klipper reports '(...)' comment lines as unknown commands",
                line_no=line_no,
            ))

        for comment in (line_comment, *paren_comments):
            if not comment:
                continue
            result.detected_origin = _detect_origin_from_comment(
                comment, result.detected_origin,
            )
            _absorb_stitchlab_meta(comment, result, line_no)

        if not command_text:
            continue

        head, params = _parse_command(command_text)
        if head is None:
            continue
        result.stats.command_count += 1
        _apply_command(head, params, state, result, ctx, line_no)

    _settle(ctx.sequence.finish(), result)

    if result.bounds.is_valid and result.stats.stitch_count == 0:
        result.diagnostics.append(Diagnostic(
            "warning", "NO_STITCHES",
            "The file moves the frame but never turns the needle: a stitch "
            f"is a Z step of +{limits.NEEDLE_PERIOD_MM:g} mm",
        ))

    if not state.units_explicit:
        result.diagnostics.append(Diagnostic(
            "warning", "UNITS_NOT_DECLARED",
            "No explicit G20/G21 found; defaulted to mm",
        ))

    if result.stats.command_count == 0:
        result.diagnostics.append(Diagnostic(
            "error", "EMPTY_FILE",
            "File contains no executable commands",
        ))
    elif not result.bounds.is_valid:
        result.diagnostics.append(Diagnostic(
            "error", "NO_XY_GEOMETRY",
            "File contains no XY movement; not a stickable job",
        ))

    result.units = "mm" if state.units_mm else "inch"
    result.units_explicit = state.units_explicit


@dataclass
class _ParseContext:
    """Per-file scratch state: one-shot diagnostics and the stitch model."""
    feedrate_missing_warned: bool = False
    sequence: StitchSequence = field(default_factory=StitchSequence)
    # XY where the needle last went through the fabric; None before the first.
    last_stitch_xy: Optional[tuple[float, float]] = None
    end_line_no: Optional[int] = None      # line of the first M30/M2
    after_end_warned: bool = False


def _settle(settled: Optional[tuple[str, object]], result: AnalysisResult) -> None:
    if settled is not None and settled[0] == "travel":
        result.stats.jump_count += 1


def _record_stitches(count: int, state: ModalState, result: AnalysisResult,
                     ctx: _ParseContext, line_no: int) -> None:
    """Book ``count`` needle cycles at the current XY position."""
    if count <= 0:
        return
    result.stats.stitch_count += count
    _settle(ctx.sequence.stitch(), result)
    if state.x is None or state.y is None:
        return
    here = (state.x, state.y)
    if ctx.last_stitch_xy is not None:
        thread = math.hypot(here[0] - ctx.last_stitch_xy[0], here[1] - ctx.last_stitch_xy[1])
        if thread > limits.LONG_JUMP_MM:
            result.stats.long_jump_count += 1
            result.diagnostics.append(Diagnostic(
                "warning", "LONG_JUMP",
                f"{thread:.1f} mm of thread between two stitches (over "
                f"{limits.LONG_JUMP_MM:g} mm); consider a trim",
                line_no=line_no,
            ))
    ctx.last_stitch_xy = here


# --- STITCHLAB_* metadata absorption -------------------------------------


def _absorb_stitchlab_meta(comment: str, result: AnalysisResult, line_no: int) -> None:
    m = _STITCHLAB_RE.search(comment)
    if not m:
        return
    key = m.group(1).upper()
    value = m.group(2).strip()
    # Don't overwrite a previously-seen value silently; first occurrence
    # wins, later ones are flagged so the user notices conflicts.
    if key in result.stitchlab_meta and result.stitchlab_meta[key] != value:
        result.diagnostics.append(Diagnostic(
            "warning", "STITCHLAB_META_CONFLICT",
            f"STITCHLAB_{key} declared multiple times with different values",
            line_no=line_no,
        ))
        return
    result.stitchlab_meta.setdefault(key, value)


# --- Command application -------------------------------------------------


def _apply_command(head: str, params: dict, state: ModalState,
                   result: AnalysisResult, ctx: "_ParseContext",
                   line_no: int) -> None:
    # Klipper does not stop at M30/M2: everything after it still runs.
    if ctx.end_line_no is not None and not ctx.after_end_warned:
        ctx.after_end_warned = True
        result.diagnostics.append(Diagnostic(
            "warning", "COMMANDS_AFTER_END",
            f"Commands after the end of job (M30/M2, line {ctx.end_line_no}) "
            "still run: Klipper does not stop there",
            line_no=line_no,
        ))
    if head in limits.END_COMMANDS and ctx.end_line_no is None:
        ctx.end_line_no = line_no

    # E-axis usage is a print-only concept; flag immediately.
    if "E" in params:
        result.diagnostics.append(Diagnostic(
            "error", "E_AXIS_FORBIDDEN",
            "Extruder (E) axis movement is not allowed in stick jobs",
            line_no=line_no,
        ))

    # Classification
    if head in limits.NEEDLE_MACROS:
        result.diagnostics.append(Diagnostic(
            "error", "NEEDLE_MACRO_IN_JOB",
            f"{head} is a panel macro: the machine refuses it while a job "
            "runs, which stops the job. In a job file a stitch is a Z step "
            f"of +{limits.NEEDLE_PERIOD_MM:g} mm",
            line_no=line_no,
        ))
        return
    if head in limits.BLOCKED_COMMANDS:
        result.diagnostics.append(Diagnostic(
            "error", "COMMAND_BLOCKED",
            "G28 (homing) is refused during a job: the machine homes before "
            "the job starts" if head == "G28" else
            f"Command {head} is blocked from stick jobs",
            line_no=line_no,
        ))
        return
    if head in limits.WARNED_COMMANDS:
        result.diagnostics.append(Diagnostic(
            "warning", "COMMAND_WARNED",
            f"Command {head} should be reviewed before running",
            line_no=line_no,
        ))

    # Modal commands
    if head == "G20":
        # Klipper answers G20 with an error, which ends the job. Keep the
        # inch reading for bounds and the preview, but block the file.
        state.units_mm = False
        state.units_explicit = True
        result.diagnostics.append(Diagnostic(
            "error", "UNITS_INCH",
            "G20 (inches): Klipper rejects G20 and stops the job; export in millimetres (G21)",
            line_no=line_no,
        ))
        return
    if head == "G21":
        state.units_mm = True
        state.units_explicit = True
        return
    if head == "G90":
        state.absolute = True
        return
    if head == "G91":
        state.absolute = False
        result.diagnostics.append(Diagnostic(
            "info", "RELATIVE_MODE",
            "G91 (relative positioning) entered",
            line_no=line_no,
        ))
        return
    if head == "G92":
        result.diagnostics.append(Diagnostic(
            "warning", "G92_ORIGIN_RESET",
            "G92 origin reset; can shift placement and bounds",
            line_no=line_no,
        ))
        # Apply the reset to modal state if axes given.
        for axis in ("X", "Y", "Z"):
            val = _float_or_none(params.get(axis))
            if val is None:
                continue
            mm = _to_mm(val, state.units_mm)
            if axis == "X":
                state.x = mm
            elif axis == "Y":
                state.y = mm
            else:
                state.z = mm
        return

    if head in ("G2", "G3"):
        result.diagnostics.append(Diagnostic(
            "warning", "ARC_FLATTENED",
            f"{head} arc encountered; thumbnail uses flattened approximation",
            line_no=line_no,
        ))
        # Bounds-update for arcs is approximated by the endpoint only in
        # Phase 1. Phase 2 thumbnail render does the full flattening.
        _update_move(state, params, result, ctx, line_no)
        return

    if head in ("G0", "G1"):
        _update_move(state, params, result, ctx, line_no)
        return

    if head == "G4":
        return  # dwell, no geometric effect

    if head in limits.ALLOWED_G_COMMANDS or head in limits.ALLOWED_M_COMMANDS:
        return

    # Contract commands: the machine defines them (end of job, colour change).
    if head in limits.COLOR_CHANGE_COMMANDS:
        result.stats.color_changes += 1
        return
    if head in limits.END_COMMANDS:
        return

    # G/M/T standard commands not in our allowlist -> unknown-but-likely
    # standard. Macros (no leading digit-style code) get tracked for the
    # Phase-3 cross-check against Klipper's gcode_macro list.
    if head[0] in ("G", "M", "T") and head[1:].isdigit():
        result.diagnostics.append(Diagnostic(
            "warning", "COMMAND_UNKNOWN",
            f"Unrecognised standard command {head}",
            line_no=line_no,
        ))
    else:
        result.referenced_unknown_macros.add(head)


def _to_mm(value: float, units_mm: bool) -> float:
    return value if units_mm else value * limits.INCH_TO_MM


# Renderer (and any other second-pass consumer) imports these helpers so
# unit conversion, comment stripping and coordinate resolution stay in one
# place. A drift test in the renderer tests verifies the two passes agree.
to_mm = _to_mm
split_line = _split_line
parse_command = _parse_command
sniff_encoding = _sniff_encoding
iter_lines = _iter_lines


def _compute_new_xy(state: ModalState,
                    params: dict) -> Optional[tuple[float, float]]:
    """Resolve the target XY position for a G0/G1 given current modal state.

    Returns None when neither X nor Y is given (Z-only move) or values are
    unparseable. Coordinates returned are in mm.
    """
    raw_x = _float_or_none(params.get("X"))
    raw_y = _float_or_none(params.get("Y"))
    if raw_x is None and raw_y is None:
        return None
    cur_x = state.x if state.x is not None else 0.0
    cur_y = state.y if state.y is not None else 0.0
    if state.absolute:
        new_x = _to_mm(raw_x, state.units_mm) if raw_x is not None else cur_x
        new_y = _to_mm(raw_y, state.units_mm) if raw_y is not None else cur_y
    else:
        new_x = cur_x + (_to_mm(raw_x, state.units_mm) if raw_x is not None else 0.0)
        new_y = cur_y + (_to_mm(raw_y, state.units_mm) if raw_y is not None else 0.0)
    return new_x, new_y


def _compute_new_z(state: ModalState, params: dict) -> Optional[float]:
    """Resolve the target Z (mm) of a move, or None when it has no Z."""
    raw_z = _float_or_none(params.get("Z"))
    if raw_z is None:
        return None
    dz = _to_mm(raw_z, state.units_mm)
    if state.absolute:
        return dz
    return (state.z if state.z is not None else 0.0) + dz


compute_new_z = _compute_new_z


def _update_move(state: ModalState, params: dict, result: AnalysisResult,
                 ctx: "_ParseContext", line_no: int) -> None:
    feed = _float_or_none(params.get("F"))
    if feed is not None:
        if feed < limits.MIN_FEEDRATE:
            result.diagnostics.append(Diagnostic(
                "error", "FEEDRATE_TOO_LOW",
                f"Feedrate {feed} is below {limits.MIN_FEEDRATE}",
                line_no=line_no,
            ))
        elif feed > limits.MAX_FEEDRATE:
            result.diagnostics.append(Diagnostic(
                "error", "FEEDRATE_TOO_HIGH",
                f"Feedrate {feed} exceeds {limits.MAX_FEEDRATE}",
                line_no=line_no,
            ))
        state.feedrate = feed

    if state.feedrate is None and not ctx.feedrate_missing_warned:
        # Info, not a warning: the machine sets a defined F when a job
        # starts (beta6 contract, embroidery_macros.cfg _STITCH_JOB_START),
        # and neither Ink/Stitch nor TurtleStitch writes one.
        result.diagnostics.append(Diagnostic(
            "info", "FEEDRATE_MISSING",
            "No feedrate before the first move; the machine's job start sets it",
            line_no=line_no,
        ))
        ctx.feedrate_missing_warned = True

    new_xy = _compute_new_xy(state, params)
    new_z = _compute_new_z(state, params)
    # A job starts with the needle up at logical Z 0: the machine's job start
    # (_STITCH_JOB_START) does needle up and G92 Z0, and Ink/Stitch and
    # TurtleStitch both write absolute Z counted up from 0.
    cur_z = state.z if state.z is not None else 0.0
    z_changes = new_z is not None and abs(new_z - cur_z) > Z_EPSILON_MM

    if new_xy is not None:
        if z_changes:
            result.diagnostics.append(Diagnostic(
                "error", "XY_AND_Z_IN_ONE_MOVE",
                "X/Y and Z change in one move: the frame would move while the "
                "needle goes through the fabric. Move X/Y first, then Z",
                line_no=line_no,
            ))
        elif not is_needle_up(cur_z):
            result.diagnostics.append(Diagnostic(
                "error", "XY_MOVE_NEEDLE_NOT_UP",
                f"The frame moves while the needle is not up (Z {cur_z:.2f} is "
                f"not a multiple of {limits.NEEDLE_PERIOD_MM:g}). Ink/Stitch: "
                f"set Z travel per stitch to {limits.NEEDLE_PERIOD_MM:g}, not alternate",
                line_no=line_no,
            ))
        result.bounds.expand(*new_xy)
        result.stats.segment_count += 1
        _settle(ctx.sequence.move(None), result)
        state.x, state.y = new_xy

    if new_z is not None:
        if new_z < cur_z - Z_EPSILON_MM:
            result.diagnostics.append(Diagnostic(
                "error", "Z_REVERSE",
                f"Z goes back from {cur_z:.2f} to {new_z:.2f}: the handwheel "
                "would turn backwards. Z only ever increases in a job",
                line_no=line_no,
            ))
        state.z = new_z
        if new_xy is not None:
            if z_changes:
                # A stitch point, as the preview draws it; not counted.
                _settle(ctx.sequence.stitch(), result)
        elif is_stitch_step(cur_z, new_z):
            if not is_one_turn(cur_z, new_z):
                result.diagnostics.append(Diagnostic(
                    "warning", "Z_STEP_NOT_ONE_STITCH",
                    f"Z step of {new_z - cur_z:+.2f} mm counted as one stitch; "
                    f"one stitch is +{limits.NEEDLE_PERIOD_MM:g} mm",
                    line_no=line_no,
                ))
            _record_stitches(1, state, result, ctx, line_no)
