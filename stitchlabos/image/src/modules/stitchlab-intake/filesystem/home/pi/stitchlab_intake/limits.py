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
# Anything not in this set and not in EMBROIDERY_MACROS is collected as
# "referenced unknown macro" and reported. Phase 3 will cross-check those
# against Klipper's actual `gcode_macro` definitions.

ALLOWED_G_COMMANDS = frozenset({
    "G0", "G1",          # linear moves
    "G2", "G3",          # arcs (flattened by parser)
    "G4",                # dwell
    "G20", "G21",        # units
    "G90", "G91",        # absolute / relative
    "G92",               # set position
})

ALLOWED_M_COMMANDS = frozenset({
    "M400",              # wait for moves to complete
})

# --- Blocked commands (hard errors) --------------------------------------

BLOCKED_COMMANDS = frozenset({
    "M112",                                        # emergency stop
    "M104", "M109", "M140", "M190",                # hotend / bed temp
    "M18", "M84",                                  # steppers off
    "G28",                                         # homing inside job
    "SAVE_CONFIG", "RUN_SHELL_COMMAND",            # config / shell
})

# --- Soft-warned commands ------------------------------------------------

WARNED_COMMANDS = frozenset({
    "M117", "RESPOND",                             # display / log
})

# --- Embroidery macros known by name -------------------------------------
#
# Listed here so they are *not* flagged as unknown. Whether they are
# actually defined in the running Klipper config is checked in Phase 3.

EMBROIDERY_MACROS = frozenset({
    "STITCH", "LOCK_STITCH",
    "NEEDLE_UP", "NEEDLE_DOWN", "NEEDLE_TOGGLE",
    "TRIM", "COLOR_CHANGE", "STOP_FOR_COLOR_CHANGE",
    "PEN_UP", "PEN_DOWN",
})

# --- Stick-specific thresholds -------------------------------------------

MIN_FEEDRATE = 1.0                # mm/min — F0 is an error
MAX_FEEDRATE = 60000.0            # mm/min — F over this is an error
LONG_JUMP_MM = 30.0               # travel without stitching above this -> trim suggestion

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
