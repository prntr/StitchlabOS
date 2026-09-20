"""End-to-end CLI tests."""

import json
import os

import pytest

from stitchlab_intake import cli


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name: str) -> str:
    return os.path.join(FIXTURES, name)


def test_analyze_valid_file_exit_zero(capsys):
    rc = cli.main(["analyze", fx("valid_minimal.gcode")])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "valid"
    assert doc["errors"] == []


def test_analyze_blocked_file_exit_two(capsys):
    rc = cli.main(["analyze", fx("blocked_temp.gcode")])
    assert rc == 2
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "blocked"
    assert any(e["code"] == "COMMAND_BLOCKED" for e in doc["errors"])


def test_analyze_warning_only_exit_one(capsys):
    rc = cli.main(["analyze", fx("inch_units.gcode")])
    # Inch mode emits warnings (UNITS_INCH, possibly UNITS_NOT_DECLARED-no).
    assert rc == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "warnings"


def test_analyze_missing_file_exit_three(capsys):
    rc = cli.main(["analyze", "/definitely/does/not/exist.gcode"])
    assert rc == 3


def test_analyze_writes_output_file(tmp_path):
    out = tmp_path / "report.json"
    rc = cli.main(["analyze", fx("valid_minimal.gcode"), "-o", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["schema"] == "stitchlab_intake.v1"


def test_analyze_hoop_check_blocks_oversized_design(capsys):
    rc = cli.main([
        "analyze", fx("valid_minimal.gcode"),
        "--hoop-width-mm", "10",
        "--hoop-height-mm", "100",
    ])
    assert rc == 2
    doc = json.loads(capsys.readouterr().out)
    assert any(e["code"] == "DESIGN_TOO_WIDE" for e in doc["errors"])


# --- Phase 2: render subcommand and --thumbnail-out ----------------------

pytest.importorskip("PIL")


def test_render_writes_png_and_exits_zero(tmp_path, capsys):
    out = tmp_path / "thumb.png"
    rc = cli.main(["render", fx("valid_minimal.gcode"), "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_render_without_geometry_exits_two(tmp_path):
    out = tmp_path / "thumb.png"
    rc = cli.main(["render", fx("no_xy.gcode"), "-o", str(out)])
    assert rc == 2
    assert not out.exists()


def test_render_respects_size(tmp_path):
    from PIL import Image
    out = tmp_path / "small.png"
    rc = cli.main([
        "render", fx("valid_minimal.gcode"),
        "-o", str(out), "--size", "128",
    ])
    assert rc == 0
    with Image.open(out) as img:
        assert img.size == (128, 128)


def test_analyze_with_thumbnail_out_writes_both(tmp_path, capsys):
    thumb = tmp_path / "thumb.png"
    rc = cli.main([
        "analyze", fx("valid_minimal.gcode"),
        "--thumbnail-out", str(thumb),
        "--hoop-width-mm", "100",
        "--hoop-height-mm", "100",
    ])
    assert rc == 0
    assert thumb.exists()
    doc = json.loads(capsys.readouterr().out)
    assert doc["thumbnail"]["width"] == 768
    assert doc["preview_key"] is not None
    assert doc["preview_key"].startswith(doc["analysis_key"])
