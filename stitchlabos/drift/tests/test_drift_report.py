"""The drift check's own parsing: sample headers, log noise, MCU signatures.

The full check needs Docker and network (make klipper-drift); these cover
the parts that decide what counts as drift, so wall-clock noise from klippy
batch mode never reads as an upstream change.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
# drift.py runs as a script in the drift container; load it as a module.
spec = importlib.util.spec_from_file_location("drift", HERE.parent / "drift.py")
drift = importlib.util.module_from_spec(spec)
sys.modules["drift"] = drift
spec.loader.exec_module(drift)


def test_every_sample_header_parses():
    samples = [drift.Sample.parse(p) for p in sorted((HERE.parent / "samples").glob("*.gcode"))]
    assert samples
    for s in samples:
        assert s.expect in ("ok", "error"), s.name
        assert set(s.variants) <= {"core", "image", "hybrid"}, s.name
        for line in s.path.read_text().splitlines():
            if "SDCARD_PRINT_FILE" in line:
                job = line.split("FILENAME=")[1].strip()
                assert (HERE.parent / "samples" / "jobs" / job).is_file(), job


LOG = """Args: ['klippy.py']
Git version: 'v0.13.0-786-g461c4e372'
===== Config file =====
[printer]
=======================
Loaded MCU 'mcu' 143 commands (v0.13.0-786-g461c4e372 / gcc)
; drift: expect=ok
Unknown command:"G90 ("
Reactor 3111.711 busy for 0.118 with:
- 'GCodeIO._process_data (gcode.py:437)'
- 'other frame'
DRIFT pos X=20.000 Y=20.000 Z=0.000 absolute=False homed=xyz
"""


def test_responses_drop_build_noise_comments_and_busy_reports():
    assert drift.responses_of(LOG) == [
        'Unknown command:"G90 ("',
        "DRIFT pos X=20.000 Y=20.000 Z=0.000 absolute=False homed=xyz",
    ]


def test_responses_use_the_last_run_of_an_appended_log():
    assert drift.responses_of(LOG + "\n" + LOG.replace("G90", "G91")) == [
        'Unknown command:"G91 ("',
        "DRIFT pos X=20.000 Y=20.000 Z=0.000 absolute=False homed=xyz",
    ]


DUMP_A = """queue_step oid=4 interval=100 count=10 add=0
set_next_step_dir oid=4 dir=1
endstop_home oid=8 clock=0
queue_step oid=4 interval=90 count=5 add=0
queue_digital_out oid=14 clock=900 on_ticks=1
"""
# Same motion, split and ordered differently, a homing move a bit longer and
# one more enable toggle: what two batch runs of one commit look like.
DUMP_B = """set_next_step_dir oid=4 dir=1
queue_step oid=4 interval=100 count=16 add=0
endstop_home oid=8 clock=0
queue_digital_out oid=14 clock=900 on_ticks=1
queue_digital_out oid=14 clock=950 on_ticks=1
"""


def test_mcu_signature_ignores_batch_mode_timing():
    a = drift.mcu_digest(DUMP_A).split()[0]
    b = drift.mcu_digest(DUMP_B).split()[0]
    assert a == b


def test_mcu_signature_sees_a_direction_change():
    changed = DUMP_A + "set_next_step_dir oid=4 dir=0\n"
    assert drift.mcu_digest(changed).split()[0] != drift.mcu_digest(DUMP_A).split()[0]


def test_expectations():
    sample = drift.Sample(name="s", path=HERE, variants=["core"], expect="ok",
                          log=["Unknown command"], nolog=["DRIFT pos X=20"])
    run = drift.Run(exit_code=0, responses=['Unknown command:"M00"'], mcu_lines=0, mcu_digest="x {}")
    assert drift.check_expectations(sample, run) == []
    bad = drift.Run(exit_code=255, responses=["DRIFT pos X=20.000"], mcu_lines=0, mcu_digest="x {}")
    assert len(drift.check_expectations(sample, bad)) == 3


def test_responses_hide_the_checkout_path():
    log = LOG + '  File "/tmp/drift-work/klipper-upstream/klippy/extras/gcode_macro.py", line 70\n'
    assert drift.responses_of(log)[-1] == '  File "<klipper>/klippy/extras/gcode_macro.py", line 70'
