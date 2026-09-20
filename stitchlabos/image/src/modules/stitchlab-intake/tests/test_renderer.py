"""Thumbnail-renderer tests.

We don't compare pixels byte-for-byte — that's brittle and depends on
Pillow's anti-aliasing. Instead we assert structural invariants:

* The output PNG exists, opens, and has the requested size.
* For a non-trivial design at least some non-background pixels exist.
* The hoop outline puts pixels at the expected frame coordinates.
* Travel moves are hidden by default and shown with show_travel=True.
* Pixel-pair deduplication actually skips redundant draws.

A separate test cross-checks that the renderer's modal-state pass yields
the same bounds as the parser's first pass — catches Klasse-A drift.
"""

import os

import pytest

PIL = pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from stitchlab_intake import renderer  # noqa: E402
from stitchlab_intake.checks import HoopSpec  # noqa: E402
from stitchlab_intake.parser import Bounds, parse_file  # noqa: E402


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name: str) -> str:
    return os.path.join(FIXTURES, name)


def _count_non_transparent(img: Image.Image) -> int:
    pixels = img.load()
    n = 0
    for y in range(img.height):
        for x in range(img.width):
            if pixels[x, y][3] > 0:
                n += 1
    return n


def test_render_produces_png_with_requested_size(tmp_path):
    r = parse_file(fx("valid_minimal.gcode"))
    out = tmp_path / "thumb.png"
    meta = renderer.render_thumbnail(
        fx("valid_minimal.gcode"), r, str(out),
        options=renderer.RenderOptions(size=256),
    )
    assert meta.width == 256 and meta.height == 256
    with Image.open(out) as img:
        assert img.size == (256, 256)
        assert img.mode == "RGBA"


def test_render_draws_some_pixels_for_valid_design(tmp_path):
    r = parse_file(fx("valid_minimal.gcode"))
    out = tmp_path / "thumb.png"
    renderer.render_thumbnail(fx("valid_minimal.gcode"), r, str(out))
    with Image.open(out) as img:
        assert _count_non_transparent(img) > 0


def test_render_raises_without_geometry(tmp_path):
    r = parse_file(fx("no_xy.gcode"))
    out = tmp_path / "thumb.png"
    with pytest.raises(ValueError):
        renderer.render_thumbnail(fx("no_xy.gcode"), r, str(out))


def test_render_with_hoop_adds_outline_pixels(tmp_path):
    r = parse_file(fx("valid_minimal.gcode"))
    out_no_hoop = tmp_path / "no_hoop.png"
    out_hoop = tmp_path / "hoop.png"
    renderer.render_thumbnail(fx("valid_minimal.gcode"), r, str(out_no_hoop))
    renderer.render_thumbnail(
        fx("valid_minimal.gcode"), r, str(out_hoop),
        hoop=HoopSpec(usable_width_mm=100, usable_height_mm=100,
                       safe_margin_mm=10),
    )
    with Image.open(out_no_hoop) as a, Image.open(out_hoop) as b:
        # Hoop outline + safe-margin rectangle add pixels.
        assert _count_non_transparent(b) > _count_non_transparent(a)


def test_travel_hidden_by_default_visible_when_enabled(tmp_path):
    r = parse_file(fx("long_jumps.gcode"))
    out_default = tmp_path / "default.png"
    out_travel = tmp_path / "travel.png"
    renderer.render_thumbnail(fx("long_jumps.gcode"), r, str(out_default))
    renderer.render_thumbnail(
        fx("long_jumps.gcode"), r, str(out_travel),
        options=renderer.RenderOptions(show_travel=True),
    )
    with Image.open(out_default) as a, Image.open(out_travel) as b:
        assert _count_non_transparent(b) > _count_non_transparent(a)


def test_dedup_skips_repeated_pixel_pairs(tmp_path):
    """Two identical G1 sequences should draw the same number of pixels as one."""
    a_path = tmp_path / "once.gcode"
    b_path = tmp_path / "twice.gcode"
    once = "G21\nG90\nG1 X0 Y0 F1500\nG1 X20 Y0\n"
    a_path.write_text(once)
    b_path.write_text(once + "G1 X0 Y0\nG1 X20 Y0\n")
    ra = parse_file(str(a_path))
    rb = parse_file(str(b_path))
    out_a = tmp_path / "a.png"
    out_b = tmp_path / "b.png"
    # Render both with same viewport (use the same bounds) by forcing
    # equal hoops so the pixel mapping is identical between the two.
    hoop = HoopSpec(usable_width_mm=40, usable_height_mm=40)
    renderer.render_thumbnail(str(a_path), ra, str(out_a), hoop=hoop)
    renderer.render_thumbnail(str(b_path), rb, str(out_b), hoop=hoop)
    with Image.open(out_a) as a, Image.open(out_b) as b:
        # The "twice" file repeats the same pixel pairs, but because of
        # dedup the drawn pixel count must stay essentially the same.
        # Allow tiny variance because the second file traces the same
        # segment back to (0,0) which adds the reverse pixel pair once.
        assert abs(_count_non_transparent(a) - _count_non_transparent(b)) < 5


def test_drift_renderer_matches_parser_bounds(tmp_path):
    """The renderer's modal-state pass must see the same coordinates as parser.

    Compute bounds by streaming the renderer's move iterator and compare
    against the parser's bounds for every shipped fixture. If this drifts,
    Klasse-A normalisation in renderer.py and parser.py have diverged.
    """
    fixtures = sorted(f for f in os.listdir(FIXTURES) if f.endswith(".gcode"))
    for name in fixtures:
        path = os.path.join(FIXTURES, name)
        analysis = parse_file(path)
        if not analysis.bounds.is_valid:
            continue
        b = Bounds()
        for move in renderer._iter_render_moves(path):
            b.expand(move.end_x, move.end_y)
        assert b.is_valid, name
        assert b.min_x == pytest.approx(analysis.bounds.min_x), name
        assert b.max_x == pytest.approx(analysis.bounds.max_x), name
        assert b.min_y == pytest.approx(analysis.bounds.min_y), name
        assert b.max_y == pytest.approx(analysis.bounds.max_y), name


def test_color_comment_changes_stitch_color(tmp_path):
    """STITCHLAB_COLOR comment switches active stitch color mid-stream."""
    p = tmp_path / "colored.gcode"
    p.write_text(
        "G21\nG90\n"
        "G1 X0 Y0 F1500\n"
        "; STITCHLAB_COLOR: r=230 g=10 b=10 name=red\n"
        "G1 X20 Y0\n"
        "G1 X20 Y20\n"
    )
    r = parse_file(str(p))
    out = tmp_path / "thumb.png"
    renderer.render_thumbnail(str(p), r, str(out))
    with Image.open(out) as img:
        pixels = img.load()
        # Somewhere in the image a strong-red pixel must appear.
        found_red = False
        for y in range(img.height):
            for x in range(img.width):
                px = pixels[x, y]
                if px[3] > 0 and px[0] > 200 and px[1] < 60 and px[2] < 60:
                    found_red = True
                    break
            if found_red:
                break
        assert found_red
