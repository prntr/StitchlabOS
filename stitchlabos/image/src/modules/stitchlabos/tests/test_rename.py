"""Tests for stitchlab-rename against a fake root (no Pi needed)."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "filesystem/usr/local/sbin/stitchlab-rename"


def make_root(tmp_path, hosts="127.0.0.1\tlocalhost\n127.0.1.1\tstitchlab-51ad\n"):
    root = tmp_path / "root"
    (root / "etc").mkdir(parents=True)
    (root / "etc/hostname").write_text("stitchlab-51ad\n")
    (root / "etc/hosts").write_text(hosts)
    (root / "etc/hosts").chmod(0o644)
    return root


def rename(root, name):
    return subprocess.run(["bash", str(SCRIPT), name], env={**os.environ, "STITCHLAB_ROOT": str(root)},
                          capture_output=True, text=True, timeout=20)


def test_rename_sets_hostname_and_hosts(tmp_path):
    # stitchlabdev, 2026-10-11: hostnamectl left the 127.0.1.1 line behind.
    root = make_root(tmp_path)
    result = rename(root, "stitchlabdev")
    assert result.returncode == 0, result.stderr
    assert (root / "etc/hostname").read_text() == "stitchlabdev\n"
    assert (root / "etc/hosts").read_text() == "127.0.0.1\tlocalhost\n127.0.1.1\tstitchlabdev\n"
    assert (root / "etc/hosts").stat().st_mode & 0o777 == 0o644
    assert "hostname set to stitchlabdev" in result.stdout


def test_hosts_without_a_127_0_1_1_line_gets_one(tmp_path):
    root = make_root(tmp_path, hosts="127.0.0.1\tlocalhost\n")
    assert rename(root, "stitchlab-03").returncode == 0
    assert (root / "etc/hosts").read_text() == "127.0.0.1\tlocalhost\n127.0.1.1\tstitchlab-03\n"


@pytest.mark.parametrize("name", ["", "StitchLab", "stitch_lab", "-stitchlab", "stitchlab-", "a" * 64, "lab.local"])
def test_invalid_names_change_nothing(tmp_path, name):
    root = make_root(tmp_path)
    before = (root / "etc/hosts").read_text(), (root / "etc/hostname").read_text()
    result = rename(root, name)
    assert result.returncode != 0
    assert "not a valid name" in result.stderr
    assert ((root / "etc/hosts").read_text(), (root / "etc/hostname").read_text()) == before


def test_without_root_it_asks_for_sudo(tmp_path):
    if os.getuid() == 0:
        pytest.skip("runs as root")
    env = {k: v for k, v in os.environ.items() if k != "STITCHLAB_ROOT"}
    result = subprocess.run(["bash", str(SCRIPT), "stitchlabdev"], env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert "needs root: sudo stitchlab-rename stitchlabdev" in result.stderr


# --- the access point follows the name ----------------------------------------

def with_ap(root, ssid):
    keyfile = root / "etc/NetworkManager/system-connections/AccessPopup.nmconnection"
    keyfile.parent.mkdir(parents=True)
    keyfile.write_text(f"[connection]\nid=AccessPopup\n\n[wifi]\nmode=ap\nssid={ssid}\n\n"
                       "[wifi-security]\npsk=praxistest\n")
    keyfile.chmod(0o600)
    return keyfile


@pytest.mark.parametrize("name,ssid", [("stitchlab07", "Stitchlab07"), ("stitchlab-03", "Stitchlab-03")])
def test_board_derived_ssid_follows_the_name(tmp_path, name, ssid):
    # stitchlab07 kept "Stitchlab-51ad" after its rename (2026-10-12).
    root = make_root(tmp_path)
    keyfile = with_ap(root, "Stitchlab-51ad")
    result = rename(root, name)
    assert result.returncode == 0, result.stderr
    assert f"\nssid={ssid}\n" in keyfile.read_text()
    assert "psk=praxistest" in keyfile.read_text()
    assert keyfile.stat().st_mode & 0o777 == 0o600
    assert f"access point SSID set to {ssid}" in result.stdout


def test_image_default_ssid_follows_the_name(tmp_path):
    root = make_root(tmp_path)
    keyfile = with_ap(root, "Stitchlab")
    assert rename(root, "stitchlab07").returncode == 0
    assert "\nssid=Stitchlab07\n" in keyfile.read_text()


@pytest.mark.parametrize("ssid", ["Werkstatt-AP", "Stitchlab-Raum3", "Stitchlab07"])  # hostname is stitchlab-51ad
def test_ssid_set_by_hand_stays(tmp_path, ssid):
    root = make_root(tmp_path)
    keyfile = with_ap(root, ssid)
    result = rename(root, "stitchlab-03")
    assert result.returncode == 0
    assert f"\nssid={ssid}\n" in keyfile.read_text()
    assert "set by hand; leaving it" in result.stdout


def test_no_access_point_profile_is_fine(tmp_path):
    root = make_root(tmp_path)
    result = rename(root, "stitchlab07")
    assert result.returncode == 0
    assert "no access point profile" in result.stdout


def test_a_second_rename_moves_the_ssid_again(tmp_path):
    root = make_root(tmp_path)
    keyfile = with_ap(root, "Stitchlab-51ad")
    assert rename(root, "stitchlab07").returncode == 0
    assert rename(root, "stitchlab-08").returncode == 0
    assert "\nssid=Stitchlab-08\n" in keyfile.read_text()
