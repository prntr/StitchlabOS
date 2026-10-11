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
