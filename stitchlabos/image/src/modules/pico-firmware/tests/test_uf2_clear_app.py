"""Tests for stitchlab-uf2-clear-app (no hardware, synthetic UF2 input)."""

import importlib.util
import struct
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

TOOL = Path(__file__).parent.parent / "filesystem/usr/local/bin/stitchlab-uf2-clear-app"
_loader = SourceFileLoader("uf2_clear_app", str(TOOL))
uf2 = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(uf2)

RP2040_FAMILY = 0xE48BFF56
FLAG_FAMILY = 0x00002000
APP = 0x10004000


def make_uf2(addresses):
    out = bytearray()
    for n, addr in enumerate(addresses):
        body = bytes([n + 1]) * 256 + bytes(476 - 256)
        out += struct.pack("<8I", uf2.MAGIC_START0, uf2.MAGIC_START1, FLAG_FAMILY,
                           addr, 256, n, len(addresses), RP2040_FAMILY)
        out += body + struct.pack("<I", uf2.MAGIC_END)
    return bytes(out)


def test_appends_one_erase_block_and_renumbers():
    katapult = make_uf2([0x10000000, 0x10000100, 0x10000200])
    result = uf2.clear_app(katapult, APP)
    blocks = uf2.read_blocks(result)

    assert len(blocks) == 4
    assert [f[5] for f, _ in blocks] == [0, 1, 2, 3]
    assert {f[6] for f, _ in blocks} == {4}
    # Katapult's own blocks are unchanged apart from the block count.
    for (f, body), (f0, body0) in zip(blocks[:3], uf2.read_blocks(katapult)):
        assert body == body0 and f[:5] == f0[:5] and f[7] == f0[7]
    last, body = blocks[-1]
    assert last[3] == APP and last[4] == 256
    assert last[2] == FLAG_FAMILY and last[7] == RP2040_FAMILY
    assert body[:256] == b"\xff" * 256


def test_refuses_input_that_already_writes_the_app_sector():
    with pytest.raises(ValueError, match="inside the sector"):
        uf2.clear_app(make_uf2([0x10000000, APP + 0x100]), APP)


def test_refuses_non_uf2():
    with pytest.raises(ValueError, match="not a UF2"):
        uf2.clear_app(b"\x00" * 100, APP)
    with pytest.raises(ValueError, match="magic"):
        uf2.clear_app(b"\x00" * 512, APP)


def test_cli_writes_output(tmp_path):
    src, dst = tmp_path / "katapult.uf2", tmp_path / "out.uf2"
    src.write_bytes(make_uf2([0x10000000]))
    assert uf2.main([str(src), str(dst)]) == 0
    assert len(uf2.read_blocks(dst.read_bytes())) == 2
