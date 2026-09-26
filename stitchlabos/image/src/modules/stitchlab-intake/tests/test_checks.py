"""Tests for the post-parse check layer."""

import os

from stitchlab_intake import checks
from stitchlab_intake.parser import Diagnostic, parse_file
from stitchlab_intake.report import result_to_dict
from stitchlab_intake.version import CHECKER_VERSION


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name: str) -> str:
    return os.path.join(FIXTURES, name)


def test_hoop_bounds_design_too_wide():
    r = parse_file(fx("valid_minimal.gcode"))  # 20 x 20 design
    hoop = checks.HoopSpec(usable_width_mm=10.0, usable_height_mm=100.0)
    checks.check_hoop_bounds(r, hoop)
    codes = {d.code for d in r.diagnostics}
    assert "DESIGN_TOO_WIDE" in codes


def test_hoop_bounds_design_too_tall():
    r = parse_file(fx("valid_minimal.gcode"))
    hoop = checks.HoopSpec(usable_width_mm=100.0, usable_height_mm=10.0)
    checks.check_hoop_bounds(r, hoop)
    codes = {d.code for d in r.diagnostics}
    assert "DESIGN_TOO_TALL" in codes


def test_hoop_bounds_within_limits_no_error():
    r = parse_file(fx("valid_minimal.gcode"))
    hoop = checks.HoopSpec(usable_width_mm=100.0, usable_height_mm=100.0)
    checks.check_hoop_bounds(r, hoop)
    codes = {d.code for d in r.diagnostics}
    assert "DESIGN_TOO_WIDE" not in codes
    assert "DESIGN_TOO_TALL" not in codes


def test_safe_margin_tightens_usable_area():
    r = parse_file(fx("valid_minimal.gcode"))  # 20 x 20 design
    # Usable 30 mm but 10 mm safe margin on each side -> effective 10 mm.
    hoop = checks.HoopSpec(usable_width_mm=30.0, usable_height_mm=30.0,
                           safe_margin_mm=10.0)
    checks.check_hoop_bounds(r, hoop)
    codes = {d.code for d in r.diagnostics}
    assert "DESIGN_TOO_WIDE" in codes


def _codes_with_placement(hoop, placement, name="valid_minimal.gcode"):
    r = parse_file(fx(name))
    bounds = checks.placement_adjusted_bounds(r.bounds, hoop, placement)
    checks.check_hoop_bounds(r, hoop, bounds=bounds)
    return [d.code for d in r.diagnostics]


def test_offset_moves_fitting_design_out_of_hoop():
    # 20 x 20 design fits an 80 x 130 hoop by size, but a 70 mm X offset
    # puts it at X 70..90 — 10 mm past the right edge.
    hoop = checks.HoopSpec(usable_width_mm=80.0, usable_height_mm=130.0)
    placement = {"offset_x": 70.0, "offset_y": 0.0, "rotation_deg": 0.0,
                 "scale": 1.0, "pivot": "design"}
    assert _codes_with_placement(hoop, placement) == ["DESIGN_OUTSIDE_HOOP"]


def test_negative_coordinates_are_outside_hoop():
    hoop = checks.HoopSpec(usable_width_mm=80.0, usable_height_mm=130.0)
    placement = {"offset_x": 0.0, "offset_y": -5.0, "rotation_deg": 0.0,
                 "scale": 1.0, "pivot": "design"}
    assert _codes_with_placement(hoop, placement) == ["DESIGN_OUTSIDE_HOOP"]


def test_design_touching_hoop_edges_is_inside():
    # X 60..80 sits exactly on the right edge, rotated by a full turn so
    # the bounds carry floating-point noise.
    hoop = checks.HoopSpec(usable_width_mm=80.0, usable_height_mm=20.0)
    placement = {"offset_x": 60.0, "offset_y": 0.0, "rotation_deg": 360.0,
                 "scale": 1.0, "pivot": "design"}
    assert _codes_with_placement(hoop, placement) == []


def test_safe_margin_applies_to_position():
    # Design at X 0..20 fits a 30 mm hoop with 2 mm margin by size
    # (20 <= 26) but starts inside the left margin.
    hoop = checks.HoopSpec(usable_width_mm=30.0, usable_height_mm=30.0,
                           safe_margin_mm=2.0)
    assert _codes_with_placement(hoop, {"pivot": "design"}) == ["DESIGN_OUTSIDE_HOOP"]


def test_oversized_design_reports_size_not_position():
    # Too wide on X, fine on Y: one size error, no second position error.
    hoop = checks.HoopSpec(usable_width_mm=10.0, usable_height_mm=100.0)
    assert _codes_with_placement(hoop, {"pivot": "design"}) == ["DESIGN_TOO_WIDE"]


def test_cap_diagnostics_summarises_overflow():
    r = parse_file(fx("valid_minimal.gcode"))
    # Inject lots of synthetic LONG_JUMP diagnostics.
    for i in range(60):
        r.diagnostics.append(Diagnostic(
            "warning", "LONG_JUMP", f"synthetic {i}", line_no=i,
        ))
    checks.cap_diagnostics(r, per_code=10)
    long_jumps = [d for d in r.diagnostics if d.code == "LONG_JUMP"]
    summaries = [d for d in r.diagnostics if d.code == "LONG_JUMP__SUMMARY"]
    assert len(long_jumps) == 10
    assert len(summaries) == 1


def test_report_round_trip_has_expected_top_level_keys():
    r = parse_file(fx("valid_minimal.gcode"))
    doc = result_to_dict(r)
    assert doc["schema"] == "stitchlab_intake.v1"
    assert doc["status"] == "valid"
    assert doc["analysis_key"].endswith(f":{CHECKER_VERSION}")
    assert doc["source"]["detected_origin"] == "gcode_studio"
    assert doc["bounds"]["width"] == 20.0
    assert doc["stats"]["stitch_count"] == 5
    assert doc["errors"] == []
