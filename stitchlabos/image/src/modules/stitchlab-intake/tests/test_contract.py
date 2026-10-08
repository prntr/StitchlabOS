"""The beta6 G-code contract as the intake sees it.

Klipper and the intake must agree: one stitch is a Z step of +5 (needle up
at multiples of 5), whatever G0/G1 the producer writes; Klipper has no
``(...)`` comments; M30/M2 end a job and M0/M00/COLOR_CHANGE change colour
on the machine; G20 is an error in Klipper; M84/M18 stay blocked.
"""

import os

import pytest

from stitchlab_intake import checks
from stitchlab_intake.parser import normalise_paren_comments, parse_file


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name: str) -> str:
    return os.path.join(FIXTURES, name)


def codes(result) -> set[str]:
    return {d.code for d in result.diagnostics}


def by_severity(result, severity: str) -> set[str]:
    return {d.code for d in result.diagnostics if d.severity == severity}


def parse_text(tmp_path, text: str, name: str = "job.gcode"):
    p = tmp_path / name
    p.write_text(text)
    return parse_file(str(p))


# --- stitch model -----------------------------------------------------------

def test_inkstitch_g0_moves_with_z_steps_are_stitches():
    r = parse_file(fx("inkstitch_v3.gcode"))
    assert r.stats.stitch_count == 7
    # The move to X0 Y0 before the first stitch and the return after the
    # last one carry no thread.
    assert r.stats.jump_count == 2
    assert r.stats.color_changes == 1          # M00
    assert "NO_STITCHES" not in codes(r)
    assert "COMMAND_UNKNOWN" not in codes(r)   # M00 and M30 are contract commands


def test_turtlestitch_g1_moves_count_by_z_step_not_by_g1():
    r = parse_file(fx("turtlestitch_ui.gcode"))
    assert r.stats.stitch_count == 5
    assert r.stats.jump_count == 2             # first G0 and the G0 jump
    # M84 stays blocked inside jobs (contract); M400 is fine.
    blocked = [d for d in r.diagnostics if d.code == "COMMAND_BLOCKED"]
    assert [d.line_no for d in blocked] == [19]
    assert r.status == "blocked"


def test_both_producers_agree_on_one_model(tmp_path):
    g0 = parse_text(tmp_path, "G21\nG90\nG0 X1 Y1 F600\nG0 Z5\nG0 X2 Y1\nG0 Z10\n", "a.gcode")
    g1 = parse_text(tmp_path, "G21\nG90\nG1 X1 Y1 F600\nG1 Z5\nG1 X2 Y1\nG1 Z10\n", "b.gcode")
    assert g0.stats.as_dict() == g1.stats.as_dict()
    assert g0.stats.stitch_count == 2


def test_relative_z_steps_count_too(tmp_path):
    r = parse_text(tmp_path, "G21\nG90\nG1 X1 Y1 F600\nG91\nG1 Z5\nG90\nG1 X2 Y2\nG91\nG1 Z5\nG90\n")
    assert r.stats.stitch_count == 2
    assert r.status == "valid", [d.as_dict() for d in r.diagnostics]


def test_one_stitch_per_z_only_line_as_the_preview_counts(tmp_path):
    # Mainsail's preview counts Z-only lines; a step other than +5 still
    # counts once, with a warning.
    r = parse_text(tmp_path, "G21\nG90\nG1 X1 Y1 F600\nG1 Z10\nG1 X2 Y2\nG1 Z15\n")
    assert r.stats.stitch_count == 2
    assert [d.line_no for d in r.diagnostics if d.code == "Z_STEP_NOT_ONE_STITCH"] == [4]


def test_turtlestitch_beta6_export_is_valid():
    # Package C's export: '; color' + COLOR_CHANGE, a lone penetration at the
    # start and after jumps and colour changes, M400 at the end, no F.
    r = parse_file(fx("turtlestitch_beta6.gcode"))
    assert r.status == "valid", [d.as_dict() for d in r.diagnostics]
    assert r.stats.stitch_count == 8           # "; Stitches: 8"
    assert r.stats.color_changes == 1
    assert r.stats.jump_count == 0             # every move ends in a penetration
    assert "FEEDRATE_MISSING" in by_severity(r, "info")


@pytest.mark.parametrize("macro", ["NEEDLE_TOGGLE", "STITCH", "LOCK_STITCH COUNT=4",
                                   "NEEDLE_ADJUST AMOUNT=0.1", "ZERO_NEEDLE_POSITION",
                                   "EMBROIDERY_HOME"])
def test_needle_macros_in_a_job_are_blocked(tmp_path, macro):
    # The machine refuses these while a job prints, which stops the job.
    r = parse_text(tmp_path, f"G21\nG90\nG1 X1 Y1 F600\nG1 Z5\n{macro}\nG1 X2 Y2\nG1 Z10\n")
    errors = [d for d in r.diagnostics if d.severity == "error"]
    assert [(d.code, d.line_no) for d in errors] == [("NEEDLE_MACRO_IN_JOB", 5)]
    assert "refuses it while a job runs" in errors[0].message
    assert r.stats.stitch_count == 2           # only the Z steps count
    assert r.referenced_unknown_macros == set()


def test_homing_in_a_job_is_blocked(tmp_path):
    r = parse_text(tmp_path, "G21\nG90\nG28\nG1 X1 Y1 F600\nG1 Z5\n")
    errors = [d for d in r.diagnostics if d.severity == "error"]
    assert [d.code for d in errors] == ["COMMAND_BLOCKED"]
    assert "refused during a job" in errors[0].message


def test_macros_the_machine_does_not_define_are_checked_against_klipper(tmp_path):
    # Legacy names, not contract commands: the start flow checks them
    # against Klipper's gcode_macro list instead of trusting them.
    r = parse_text(tmp_path, "G21\nG90\nG1 X1 Y1 F600\nG1 Z5\nTRIM\nSTOP_FOR_COLOR_CHANGE\n")
    assert r.referenced_unknown_macros == {"TRIM", "STOP_FOR_COLOR_CHANGE"}
    assert r.stats.color_changes == 0


def test_frame_without_needle_warns(tmp_path):
    r = parse_text(tmp_path, "G21\nG90\nG1 X0 Y0 F600\nG1 X10 Y0\nG1 X10 Y10\n")
    assert r.stats.stitch_count == 0
    assert "NO_STITCHES" in by_severity(r, "warning")


def test_alternate_z_from_inkstitch_defaults_is_blocked(tmp_path):
    # Ink/Stitch's default Z mode alternates 0/1: the needle never completes
    # a turn, the frame moves with it part-way down, and Z runs backwards.
    r = parse_text(tmp_path, "G90\nG21\nG0 X1 Y1\nG0 Z1\nG0 X2 Y1\nG0 Z0\nG0 X3 Y1\nG0 Z1\n")
    assert {"XY_MOVE_NEEDLE_NOT_UP", "Z_REVERSE"} <= by_severity(r, "error")
    assert "Z_STEP_NOT_ONE_STITCH" in by_severity(r, "warning")
    assert r.status == "blocked"


def test_xy_and_z_in_one_move_is_blocked_and_not_counted(tmp_path):
    r = parse_text(tmp_path, "G21\nG90\nG1 X0 Y0 F600\nG1 X5 Y0 Z5\n")
    assert "XY_AND_Z_IN_ONE_MOVE" in by_severity(r, "error")
    assert r.stats.stitch_count == 0           # drawn as a stitch point, not counted


def test_needle_down_between_moves_is_blocked(tmp_path):
    r = parse_text(tmp_path, "G21\nG90\nG1 X0 Y0 F600\nG1 Z2.5\nG1 X5 Y0\nG1 Z5\n")
    assert "XY_MOVE_NEEDLE_NOT_UP" in by_severity(r, "error")
    assert r.stats.stitch_count == 2           # two Z-only lines, as in the preview


# --- comments -------------------------------------------------------------

def test_paren_comment_after_a_command_is_an_error_until_normalised():
    r = parse_file(fx("inkstitch_v3.gcode"))
    with_cmd = [d.line_no for d in r.diagnostics if d.code == "PAREN_COMMENT_WITH_COMMAND"]
    assert with_cmd == [9, 10]                 # G90 (...), G21 (...)
    assert "PAREN_COMMENT_LINE" in by_severity(r, "info")
    assert r.status == "blocked"


def test_normalised_inkstitch_file_runs_and_keeps_its_lines(tmp_path):
    src = open(fx("inkstitch_v3.gcode"), encoding="utf-8").read().split("\n")
    out = [normalise_paren_comments(line) for line in src]
    fixed = [o if o is not None else line for o, line in zip(out, src)]
    r = parse_text(tmp_path, "\n".join(fixed))
    assert len(fixed) == len(src)
    assert not codes(r) & {"PAREN_COMMENT_WITH_COMMAND", "PAREN_COMMENT_LINE"}
    assert r.units_explicit                    # G21 is seen
    assert r.stats.stitch_count == 7
    assert r.status == "valid", [d.as_dict() for d in r.diagnostics]


@pytest.mark.parametrize("line, expected", [
    ("G90 (use absolute coordinates)", "G90 ; use absolute coordinates"),
    ("(STITCH_COUNT:578)", "; STITCH_COUNT:578"),
    ("G1 X10 (a) Y10 (b) ; c", "G1 X10  Y10 ; a ; b ; c"),
    ("G0 X1 Y2 ()", "G0 X1 Y2"),
    ("G1 X1 Y2 ; note (kept)", None),
    ("G1 X1 Y2", None),
    ("(STITCH_COUNT: 123", None),              # unterminated: left alone
    ('RESPOND MSG="needle (up)"', None),       # literal inside quotes
])
def test_normalise_paren_comments(line, expected):
    assert normalise_paren_comments(line) == expected


def test_paren_inside_quotes_is_not_a_comment(tmp_path):
    r = parse_text(tmp_path, 'G21\nG90\nRESPOND MSG="needle (up)"\n')
    assert not codes(r) & {"PAREN_COMMENT_WITH_COMMAND", "PAREN_COMMENT_LINE",
                           "UNTERMINATED_PAREN"}


# --- command tables -------------------------------------------------------

@pytest.mark.parametrize("command", ["M0", "M00", "M600", "COLOR_CHANGE"])
def test_colour_change_commands_are_known(tmp_path, command):
    r = parse_text(tmp_path, f"G21\nG90\nG1 X1 Y1 F600\nG1 Z5\n{command}\nG1 X2 Y2\nG1 Z10\n")
    assert r.stats.color_changes == 1
    assert "COMMAND_UNKNOWN" not in codes(r)
    assert r.referenced_unknown_macros == set()


@pytest.mark.parametrize("command", ["M30", "M2"])
def test_end_commands_are_known(tmp_path, command):
    r = parse_text(tmp_path, f"G21\nG90\nG1 X1 Y1 F600\nG1 Z5\n{command}\n")
    assert r.status == "valid", [d.as_dict() for d in r.diagnostics]


def test_commands_after_m30_warn(tmp_path):
    r = parse_text(tmp_path, "G21\nG90\nG1 X1 Y1 F600\nG1 Z5\nM30\nG1 X2 Y2\n")
    assert "COMMANDS_AFTER_END" in by_severity(r, "warning")


def test_g20_is_rejected(tmp_path):
    r = parse_text(tmp_path, "G20\nG90\nG1 X1 Y1 F60\nG1 Z0.19685\n")
    assert "UNITS_INCH" in by_severity(r, "error")


@pytest.mark.parametrize("command", ["M84", "M18"])
def test_motors_off_stays_blocked(tmp_path, command):
    r = parse_text(tmp_path, f"G21\nG90\nG1 X1 Y1 F600\nG1 Z5\n{command}\n")
    assert "COMMAND_BLOCKED" in by_severity(r, "error")


# --- machine travel -------------------------------------------------------

IMAGE_MACHINE = {"stepper_x": {"position_min": 0.0, "position_max": 90.0},
                 "stepper_y": {"position_min": 0.0, "position_max": 120.0}}


def test_machine_limits_parse_from_klipper_settings():
    m = checks.MachineLimits.from_klipper_settings(IMAGE_MACHINE)
    assert (m.x_min, m.x_max, m.y_min, m.y_max) == (0.0, 90.0, 0.0, 120.0)
    assert checks.MachineLimits.from_dict(m.as_dict()) == m
    # position_min defaults to 0 as in Klipper.
    m2 = checks.MachineLimits.from_klipper_settings(
        {"stepper_x": {"position_max": 80}, "stepper_y": {"position_max": 130}})
    assert (m2.x_min, m2.y_max) == (0.0, 130.0)
    assert checks.MachineLimits.from_klipper_settings({"stepper_x": {}}) is None
    assert checks.MachineLimits.from_klipper_settings(None) is None


def test_design_inside_hoop_but_beyond_machine_travel_is_blocked(tmp_path):
    # 80 x 130 hoop, machine Y 0..120: Y 124.6 fits the hoop, not the machine.
    r = parse_text(tmp_path, "G21\nG90\nG1 X10 Y10 F600\nG1 Z5\nG1 X60 Y124.6\nG1 Z10\n")
    hoop = checks.HoopSpec(usable_width_mm=80.0, usable_height_mm=130.0)
    machine = checks.MachineLimits.from_klipper_settings(IMAGE_MACHINE)
    checks.check_hoop_bounds(r, hoop)
    assert by_severity(r, "error") == set()
    checks.check_machine_bounds(r, machine)
    errors = [d for d in r.diagnostics if d.severity == "error"]
    assert [d.code for d in errors] == ["DESIGN_OUTSIDE_MACHINE"]
    assert "124.6" in errors[0].message


def test_design_inside_machine_travel_passes(tmp_path):
    r = parse_file(fx("valid_minimal.gcode"))
    checks.check_machine_bounds(r, checks.MachineLimits.from_klipper_settings(IMAGE_MACHINE))
    assert r.status == "valid"
