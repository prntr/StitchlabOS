"""Hard limits, command classification tables, and check thresholds.

Kept as plain constants so they are obvious to read in code review and easy
to override per machine model later (Phase 3 may pull these from Moonraker
config). Numbers are conservative defaults for the current standard hoop.
"""

# --- File size / shape limits --------------------------------------------

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_LINE_COUNT = 10_000_000
MAX_LINE_LENGTH = 4096

# --- Whitelisted standard G/M commands -----------------------------------
#
# A macro name in none of the tables below is collected as a "referenced
# unknown macro" and checked against Klipper's `gcode_macro` list before a
# job starts.

ALLOWED_G_COMMANDS = frozenset({
    "G0", "G1",          # linear moves
    "G2", "G3",          # arcs (flattened by parser)
    "G4",                # dwell
    "G21",               # millimetres (Klipper rejects G20; see parser)
    "G90", "G91",        # absolute / relative
    "G92",               # set position
})

ALLOWED_M_COMMANDS = frozenset({
    "M400",              # wait for moves to complete
})

# --- Commands of the StitchLAB G-code contract ---------------------------
#
# The machine side defines these as macros in embroidery_macros.cfg (beta6
# contract between the machine config, the producers and this intake).
# Klipper parses "M00" as its own command, not as "M0", so both are listed.
# The machine starts every job itself (SDCARD_PRINT_FILE -> _STITCH_JOB_START:
# needle up, G90, G92 Z0, G1 F<job_feedrate>).

END_COMMANDS = frozenset({"M2", "M30"})            # end of job: needle up, M400
COLOR_CHANGE_COMMANDS = frozenset({                # pause in place, needle up
    "M0", "M00",                                   # Ink/Stitch writes M00
    "M600",                                        # filament/thread change
    "COLOR_CHANGE",                                # TurtleStitch writes it
})

# Needle and homing macros of the embroidery panel. The machine refuses each
# of them while a job prints, which stops the job; producers must not write
# them (beta6 contract). In a job a stitch is a Z step of +5.
NEEDLE_MACROS = frozenset({
    "NEEDLE_TOGGLE", "STITCH", "LOCK_STITCH", "NEEDLE_ADJUST",
    "ZERO_NEEDLE_POSITION", "EMBROIDERY_HOME",
})

# --- Blocked commands (hard errors) --------------------------------------

BLOCKED_COMMANDS = frozenset({
    "M112",                                        # emergency stop
    "M104", "M109", "M140", "M190",                # hotend / bed temp
    "M18", "M84",                                  # steppers off
    "G28",                                         # homing: refused during a job
    "SAVE_CONFIG", "RUN_SHELL_COMMAND",            # config / shell
})

# --- Soft-warned commands ------------------------------------------------

WARNED_COMMANDS = frozenset({
    "M117", "RESPOND",                             # display / log
})

# --- Stick-specific thresholds -------------------------------------------

MIN_FEEDRATE = 1.0                # mm/min — F0 is an error
MAX_FEEDRATE = 60000.0            # mm/min — F over this is an error
LONG_JUMP_MM = 30.0               # thread between two stitches above this -> trim suggestion

# --- Needle model --------------------------------------------------------
#
# Z is the handwheel: one turn = NEEDLE_PERIOD_MM = one stitch, needle up at
# multiples of it (embroidery_macros.cfg, beta6 contract "one stitch = Z +5").
# The tolerance is the needle-up window NEEDLE_TOGGLE uses (z mod 5 < 0.5).

NEEDLE_PERIOD_MM = 5.0
NEEDLE_UP_TOLERANCE_MM = 0.5

# Stitch density: warn when more than N stitches fall into a circle of
# radius R mm. Tuned conservatively; refined once we have real fixtures.
DENSITY_WINDOW_MM = 1.0
DENSITY_MAX_STITCHES = 12

# --- Inch -> mm conversion -----------------------------------------------

INCH_TO_MM = 25.4


# --- Hoop specs loaded from JSON config ----------------------------------

def load_hoop_spec(hoops_json_path, hoop_id=None):
    """Resolve a HoopSpec by id from a hoops.json config file.

    Returns ``None`` if the file is missing, malformed, or the requested
    hoop id is unknown — callers treat that as "no hoop check". When
    ``hoop_id`` is ``None`` the ``default`` entry from the file is used.
    Kept tolerant on purpose: a busted hoops.json must not break analysis.
    """
    import json
    from .checks import HoopSpec

    try:
        with open(hoops_json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None

    hoops = data.get("hoops") or {}
    if hoop_id is None:
        hoop_id = data.get("default")
    entry = hoops.get(hoop_id) if hoop_id else None
    if not entry:
        return None

    return HoopSpec(
        hoop_id=entry.get("hoop_id", hoop_id or "standard"),
        usable_width_mm=float(entry.get("usable_width_mm", 0.0)),
        usable_height_mm=float(entry.get("usable_height_mm", 0.0)),
        safe_margin_mm=float(entry.get("safe_margin_mm", 0.0)),
        version=entry.get("version", "preliminary"),
        frame_geometry=entry.get("frame_geometry", ""),
        physical_width_mm=float(entry.get("physical_width_mm", 0.0)),
        physical_height_mm=float(entry.get("physical_height_mm", 0.0)),
    )
