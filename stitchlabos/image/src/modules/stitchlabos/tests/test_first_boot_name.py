"""Tests for stitchlab-first-boot-name against a fake root (no Pi needed)."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "filesystem/usr/local/sbin/stitchlab-first-boot-name"

KEYFILE = """[connection]
id=AccessPopup
type=wifi

[wifi]
mode=ap
ssid={ssid}

[wifi-security]
key-mgmt=wpa-psk
psk=praxistest
"""


def make_root(tmp_path, hostname="stitchlab", ssid="Stitchlab",
              serial=b"10000000a1b23F2A\x00", machine_id="0123456789abcdef0123456789abcdef"):
    root = tmp_path / "root"
    (root / "etc/NetworkManager/system-connections").mkdir(parents=True)
    (root / "proc/device-tree").mkdir(parents=True)
    (root / "etc/hostname").write_text(hostname + "\n")
    (root / "etc/hosts").write_text("127.0.0.1\tlocalhost\n127.0.1.1\tstitchlab\n")
    if machine_id is not None:
        (root / "etc/machine-id").write_text(machine_id + "\n")
    if serial is not None:
        (root / "proc/device-tree/serial-number").write_bytes(serial)
    keyfile = root / "etc/NetworkManager/system-connections/AccessPopup.nmconnection"
    keyfile.write_text(KEYFILE.format(ssid=ssid))
    keyfile.chmod(0o600)
    return root


def run(root):
    result = subprocess.run(["bash", str(SCRIPT)], env={**os.environ, "STITCHLAB_ROOT": str(root)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return result.stdout


def keyfile(root):
    return root / "etc/NetworkManager/system-connections/AccessPopup.nmconnection"


def test_fresh_card_gets_the_board_suffix(tmp_path):
    root = make_root(tmp_path)
    out = run(root)
    assert (root / "etc/hostname").read_text() == "stitchlab-3f2a\n"
    assert "127.0.1.1\tstitchlab-3f2a\n" in (root / "etc/hosts").read_text()
    assert "127.0.0.1\tlocalhost\n" in (root / "etc/hosts").read_text()
    assert "ssid=Stitchlab-3f2a\n" in keyfile(root).read_text()
    assert "psk=praxistest\n" in keyfile(root).read_text()
    assert stat.S_IMODE(keyfile(root).stat().st_mode) == 0o600
    assert (root / "var/lib/stitchlabos/first-boot-name.done").exists()
    assert "stitchlab-3f2a" in out


def test_name_from_imager_is_kept_but_the_ap_still_gets_its_suffix(tmp_path):
    root = make_root(tmp_path, hostname="stitchlabdev")
    run(root)
    assert (root / "etc/hostname").read_text() == "stitchlabdev\n"
    assert "127.0.1.1\tstitchlab\n" in (root / "etc/hosts").read_text()
    assert "ssid=Stitchlab-3f2a\n" in keyfile(root).read_text()


def test_ssid_changed_in_mainsail_is_kept(tmp_path):
    root = make_root(tmp_path, ssid="Werkstatt-AP")
    run(root)
    assert "ssid=Werkstatt-AP\n" in keyfile(root).read_text()
    assert (root / "etc/hostname").read_text() == "stitchlab-3f2a\n"


def test_machine_id_when_the_board_has_no_serial(tmp_path):
    root = make_root(tmp_path, serial=None)
    run(root)
    assert (root / "etc/hostname").read_text() == "stitchlab-cdef\n"


def test_nothing_to_derive_a_suffix_from(tmp_path):
    root = make_root(tmp_path, serial=None, machine_id=None)
    out = run(root)
    assert (root / "etc/hostname").read_text() == "stitchlab\n"
    assert "ssid=Stitchlab\n" in keyfile(root).read_text()
    assert not (root / "var/lib/stitchlabos/first-boot-name.done").exists()
    assert "keeping the default names" in out


def test_hosts_without_a_127_0_1_1_line(tmp_path):
    root = make_root(tmp_path)
    (root / "etc/hosts").write_text("127.0.0.1\tlocalhost\n")
    run(root)
    assert (root / "etc/hosts").read_text() == "127.0.0.1\tlocalhost\n127.0.1.1\tstitchlab-3f2a\n"


def test_second_run_changes_nothing(tmp_path):
    root = make_root(tmp_path)
    run(root)
    before = {p: p.read_bytes() for p in [root / "etc/hostname", root / "etc/hosts", keyfile(root)]}
    run(root)
    assert {p: p.read_bytes() for p in before} == before
