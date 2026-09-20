"""Parser-level tests against the synthetic fixtures."""

import os

import pytest

from stitchlab_intake import checks, limits
from stitchlab_intake.parser import parse_file


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name: str) -> str:
    return os.path.join(FIXTURES, name)


def codes(result) -> set[str]:
    return {d.code for d in result.diagnostics}


def test_valid_minimal_has_no_errors():
    r = parse_file(fx("valid_minimal.gcode"))
    assert r.status == "valid", [d.as_dict() for d in r.diagnostics]
    assert r.stats.stitch_count == 5
    assert r.bounds.is_valid
    assert r.bounds.width == pytest.approx(20.0)
    assert r.bounds.height == pytest.approx(20.0)
    assert r.units == "mm"
    assert r.units_explicit is True
    assert r.detected_origin == "gcode_studio"
    assert r.stitchlab_meta["HOOP_ID"] == "standard"
    assert r.stitchlab_meta["VERSION"] == "1"


def test_unterminated_paren_is_error():
    r = parse_file(fx("unterminated_paren.gcode"))
    assert "UNTERMINATED_PAREN" in codes(r)
    assert r.status == "blocked"


def test_blocked_temp_command():
    r = parse_file(fx("blocked_temp.gcode"))
    assert "COMMAND_BLOCKED" in codes(r)
    assert r.status == "blocked"


def test_e_axis_forbidden():
    r = parse_file(fx("e_axis.gcode"))
    assert "E_AXIS_FORBIDDEN" in codes(r)
    assert r.status == "blocked"


def test_no_xy_geometry():
    r = parse_file(fx("no_xy.gcode"))
    assert "NO_XY_GEOMETRY" in codes(r)
    assert r.status == "blocked"
    assert not r.bounds.is_valid


def test_inch_units_warning_and_conversion():
    r = parse_file(fx("inch_units.gcode"))
    # Inch mode warning fires, but file itself is otherwise valid.
    assert "UNITS_INCH" in codes(r)
    # Bounds get normalised to mm: 1 inch = 25.4 mm.
    assert r.bounds.width == pytest.approx(25.4)
    assert r.bounds.height == pytest.approx(25.4)
    # Units flag tracks the declared mode, not the normalised representation.
    assert r.units == "inch"
    assert r.units_explicit is True


def test_inkstitch_macros_collected_and_color_change_counted():
    r = parse_file(fx("inkstitch_like.gcode"))
    assert "UNTERMINATED_PAREN" not in codes(r)
    assert r.detected_origin == "inkstitch"
    # STITCH/TRIM/COLOR_CHANGE are known embroidery macros, not "unknown".
    assert r.referenced_unknown_macros == set()
    assert r.stats.color_changes == 1


def test_unknown_macros_are_recorded():
    r = parse_file(fx("unknown_macro.gcode"))
    assert "MY_CUSTOM_MACRO" in r.referenced_unknown_macros
    assert "ANOTHER_THING" in r.referenced_unknown_macros


def test_long_jumps_emit_warning_and_increment_counter():
    r = parse_file(fx("long_jumps.gcode"))
    assert "LONG_JUMP" in codes(r)
    assert r.stats.long_jump_count >= 2


def test_units_not_declared(tmp_path):
    p = tmp_path / "no_units.gcode"
    p.write_text("G90\nG1 X10 Y10 F1500\nG1 X20 Y20\n")
    r = parse_file(str(p))
    assert "UNITS_NOT_DECLARED" in codes(r)


def test_empty_file(tmp_path):
    p = tmp_path / "empty.gcode"
    p.write_text("")
    r = parse_file(str(p))
    assert "EMPTY_FILE" in codes(r)


def test_only_comments(tmp_path):
    p = tmp_path / "only_comments.gcode"
    p.write_text("; just a header\n; nothing to do\n")
    r = parse_file(str(p))
    assert "EMPTY_FILE" in codes(r)


def test_bom_detected(tmp_path):
    p = tmp_path / "bom.gcode"
    p.write_bytes(b"\xef\xbb\xbfG21\nG90\nG1 X10 Y10 F1500\nG1 X20 Y20\n")
    r = parse_file(str(p))
    assert "BOM_DETECTED" in codes(r)
    # BOM is info-only, file should still parse cleanly.
    assert r.bounds.is_valid


def test_binary_data_rejected(tmp_path):
    p = tmp_path / "binary.gcode"
    p.write_bytes(b"G21\n\x00\x01\x02 binary\nG1 X10 Y10\n")
    r = parse_file(str(p))
    assert "BINARY_DATA" in codes(r)


def test_file_too_large(tmp_path, monkeypatch):
    p = tmp_path / "big.gcode"
    p.write_text("G21\nG1 X1 Y1\n")
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 4)
    r = parse_file(str(p))
    assert "FILE_TOO_LARGE" in codes(r)


def test_feedrate_missing_only_warns_once(tmp_path):
    p = tmp_path / "no_feed.gcode"
    p.write_text("G21\nG90\nG1 X1 Y1\nG1 X2 Y2\nG1 X3 Y3\n")
    r = parse_file(str(p))
    feed_warnings = [d for d in r.diagnostics if d.code == "FEEDRATE_MISSING"]
    assert len(feed_warnings) == 1


def test_decimal_comma_normalised(tmp_path):
    p = tmp_path / "comma.gcode"
    p.write_text("G21\nG90\nG1 X1,5 Y2,5 F1500\nG1 X3,5 Y4,5\n")
    r = parse_file(str(p))
    assert r.bounds.max_x == pytest.approx(3.5)
    assert r.bounds.max_y == pytest.approx(4.5)


def test_inline_paren_then_line_comment(tmp_path):
    p = tmp_path / "inline.gcode"
    p.write_text("G21\nG1 X10 (inline ok) Y10 F1500 ; trailing\nG1 X20 Y20\n")
    r = parse_file(str(p))
    assert "UNTERMINATED_PAREN" not in codes(r)
    assert r.bounds.max_x == pytest.approx(20.0)


def test_arc_emits_warning(tmp_path):
    p = tmp_path / "arc.gcode"
    p.write_text("G21\nG90\nG1 X0 Y0 F1500\nG2 X10 Y0 I5 J0\nG1 X20 Y0\n")
    r = parse_file(str(p))
    assert "ARC_FLATTENED" in codes(r)
    # Endpoint must still contribute to bounds.
    assert r.bounds.max_x == pytest.approx(20.0)


def test_relative_mode_info(tmp_path):
    p = tmp_path / "rel.gcode"
    p.write_text("G21\nG91\nG1 X10 Y10 F1500\nG1 X10 Y10\n")
    r = parse_file(str(p))
    assert "RELATIVE_MODE" in codes(r)
    # Two +10/+10 moves from (0,0) -> (10,10) -> (20,20).
    assert r.bounds.max_x == pytest.approx(20.0)
    assert r.bounds.max_y == pytest.approx(20.0)
