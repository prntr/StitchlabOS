"""Tests for stitchlab-configure-avahi against a copy of trixie's config."""

import configparser
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "filesystem/usr/local/sbin/stitchlab-configure-avahi"
STOCK = Path(__file__).parent / "fixtures/avahi-daemon.conf"


def configure(conf: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT), str(conf)],
                          capture_output=True, text=True, timeout=20)


def read(conf: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(conf.read_text())
    return parser


def test_stock_config_becomes_wlan0_and_ipv4_only(tmp_path):
    conf = tmp_path / "avahi-daemon.conf"
    shutil.copy(STOCK, conf)
    result = configure(conf)
    assert result.returncode == 0, result.stderr
    cfg = read(conf)
    assert cfg["server"]["allow-interfaces"] == "wlan0"
    assert cfg["server"]["use-ipv4"] == "yes"
    assert cfg["server"]["use-ipv6"] == "no"
    # use-ipv6=no alone still publishes the IPv6 address over IPv4.
    assert cfg["publish"]["publish-aaaa-on-ipv4"] == "no"
    assert cfg["publish"]["publish-a-on-ipv6"] == "no"
    assert cfg["reflector"]["enable-reflector"] == "yes"
    # Untouched lines stay, each key appears once.
    assert cfg["publish"]["publish-workstation"] == "no"
    assert cfg["wide-area"]["enable-wide-area"] == "yes"
    assert conf.read_text().count("use-ipv6=") == 1


def test_running_twice_changes_nothing(tmp_path):
    conf = tmp_path / "avahi-daemon.conf"
    shutil.copy(STOCK, conf)
    assert configure(conf).returncode == 0
    first = conf.read_text()
    assert configure(conf).returncode == 0
    assert conf.read_text() == first


def test_missing_keys_are_added_to_their_section(tmp_path):
    conf = tmp_path / "avahi-daemon.conf"
    conf.write_text("[server]\nuse-ipv4=yes\n\n[publish]\n\n[reflector]\n")
    assert configure(conf).returncode == 0
    cfg = read(conf)
    assert cfg["server"]["use-ipv6"] == "no"
    assert cfg["server"]["allow-interfaces"] == "wlan0"
    assert cfg["publish"]["publish-aaaa-on-ipv4"] == "no"


def test_missing_section_fails_and_leaves_the_file(tmp_path):
    conf = tmp_path / "avahi-daemon.conf"
    conf.write_text("[server]\nuse-ipv6=yes\n")
    before = conf.read_text()
    result = configure(conf)
    assert result.returncode != 0
    assert conf.read_text() == before
