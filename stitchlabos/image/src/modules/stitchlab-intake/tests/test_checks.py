"""Tests for the post-parse check layer."""

import os

from stitchlab_intake import checks
from stitchlab_intake.parser import Diagnostic, parse_file
from stitchlab_intake.report import result_to_dict


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
    assert doc["analysis_key"].endswith(":v1")
    assert doc["source"]["detected_origin"] == "gcode_studio"
    assert doc["bounds"]["width"] == 20.0
    assert doc["stats"]["stitch_count"] == 5
    assert doc["errors"] == []
