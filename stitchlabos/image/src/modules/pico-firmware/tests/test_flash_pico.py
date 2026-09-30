"""Tests for stitchlab-flash-pico's flash-mode flow (no hardware).

The script is sourced into a bash driver that replaces the hardware-facing
functions: the RPI-RP2 drive "appears" after a given number of lookups, and
the operator's answers come from stdin.
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "filesystem/usr/local/bin/stitchlab-flash-pico"
BASH = os.environ.get("TEST_BASH", "bash")

STUBS = r"""
source "$SCRIPT"
sleep() { :; }
is_interactive() { [ "$INTERACTIVE" = 1 ]; }
# Lookups happen in subshells, so the count lives in a file.
find_bootsel_device() {
    local n
    n="$(cat "$COUNTER")"
    echo $((n + 1)) > "$COUNTER"
    if [ "$APPEAR_AFTER" -ge 0 ] && [ "$n" -ge "$APPEAR_AFTER" ]; then
        echo /dev/sda1
    fi
}
BOOTSEL_WAIT=0
BOOTSEL_SETTLE=0
"""


def run(body, *, answers="", interactive=True, appear_after=-1, tmp_path):
    """appear_after: lookups before the drive shows up; -1 means never."""
    counter = tmp_path / "lookups"
    counter.write_text("0")
    env = {
        **os.environ,
        "SCRIPT": str(SCRIPT),
        "COUNTER": str(counter),
        "APPEAR_AFTER": str(appear_after),
        "INTERACTIVE": "1" if interactive else "0",
    }
    return subprocess.run(
        [BASH, "-c", STUBS + body],
        input=answers,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


ACQUIRE = 'rc=0; dev="$(acquire_bootsel {arg})" || rc=$?; echo "rc=$rc dev=$dev"'


def acquire(tmp_path, skip=True, **kwargs):
    result = run(ACQUIRE.format(arg="skip" if skip else ""), tmp_path=tmp_path, **kwargs)
    assert "ERROR:" not in result.stderr, result.stderr
    return result


def test_drive_already_there_asks_nothing(tmp_path):
    result = acquire(tmp_path, appear_after=0)
    assert result.stdout.strip() == "rc=0 dev=/dev/sda1"
    assert "Press Enter" not in result.stderr


def test_enter_then_drive_appears(tmp_path):
    result = acquire(tmp_path, answers="\n", appear_after=1)
    assert result.stdout.strip() == "rc=0 dev=/dev/sda1"


def test_operator_says_katapult_is_on_the_pico(tmp_path):
    result = acquire(tmp_path, answers="u\n")
    assert result.stdout.strip() == "rc=3 dev="


def test_no_drive_after_enter_asks_instead_of_guessing(tmp_path):
    result = acquire(tmp_path, answers="\nq\n")
    assert result.stdout.strip() == "rc=1 dev="
    assert "No RPI-RP2 drive appeared" in result.stderr
    assert "BOOT jumper on when RESET was pressed" in result.stderr


def test_look_again_finds_the_drive(tmp_path):
    # Lookups: the first check, one after Enter, then one after "r".
    result = acquire(tmp_path, answers="\nr\n", appear_after=2)
    assert result.stdout.strip() == "rc=0 dev=/dev/sda1"


def test_uart_after_a_failed_look(tmp_path):
    result = acquire(tmp_path, answers="\nu\n")
    assert result.stdout.strip() == "rc=3 dev="


def test_skip_is_not_offered_outside_auto_mode(tmp_path):
    result = acquire(tmp_path, skip=False, answers="u\n\n", appear_after=1)
    assert result.stdout.strip() == "rc=0 dev=/dev/sda1"
    assert "Please answer with one of: enter" in result.stderr


def test_end_of_input_counts_as_no_drive(tmp_path):
    result = acquire(tmp_path, answers="")
    assert result.stdout.strip() == "rc=1 dev="


def test_not_interactive_waits_then_reports_no_drive(tmp_path):
    result = acquire(tmp_path, interactive=False)
    assert result.stdout.strip() == "rc=1 dev="
    assert "Not interactive" in result.stderr


MAIN = r"""
ensure_sudo() { :; }
release_serial() { :; }
prepare_katapult() { KATAPULT_CLEAN_UF2=/tmp/katapult-clean.uf2; }
flash_via_bootsel() { echo "BOOTSEL $1 $2"; }
flash_via_uart() { echo "UART"; }
verify_mcu() { :; }
MODE=auto
main
"""


def test_auto_without_drive_fails_instead_of_assuming_katapult(tmp_path):
    result = run(MAIN, interactive=False, tmp_path=tmp_path)
    assert result.returncode != 0
    assert "UART" not in result.stdout
    assert "stitchlab-flash-pico --uart" in result.stderr


def test_auto_with_skip_goes_to_the_uart(tmp_path):
    result = run(MAIN, answers="u\n", tmp_path=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "BOOTSEL" not in result.stdout
    assert "UART" in result.stdout


def test_auto_uses_the_drive_it_found_once(tmp_path):
    result = run(MAIN, appear_after=0, tmp_path=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "BOOTSEL /dev/sda1 /tmp/katapult-clean.uf2" in result.stdout
    assert "UART" in result.stdout
    assert (tmp_path / "lookups").read_text().strip() == "1"


@pytest.mark.parametrize("mode", ["bootsel", "standalone"])
def test_flash_mode_only_paths_fail_without_drive(tmp_path, mode):
    result = run(MAIN.replace("MODE=auto", f"MODE={mode}"), answers="\nq\n", tmp_path=tmp_path)
    assert result.returncode != 0
    assert "BOOTSEL" not in result.stdout
    assert "No RPI-RP2 drive found" in result.stderr
