"""IntakeCore tests with a fake adapter.

The fake `run_cli` shells into the CLI in-process via ``cli.main`` so the
sidecars and thumbnails are produced exactly as on the Pi — no mock JSON.
That keeps these tests honest about what Moonraker would observe.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional

import pytest

from stitchlab_intake import cli
from stitchlab_intake.component import (
    Adapter,
    CliResult,
    IntakeConfig,
    IntakeCore,
    META_SUBDIR,
    THUMB_SUBDIR,
)

pytest.importorskip("PIL")  # render path runs end-to-end

FIXTURES = Path(__file__).parent / "fixtures"


# --- harness ----------------------------------------------------------------

class FakeAdapter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.macros: Optional[set] = set()  # set() == klippy ready, empty config
        self.cli_calls: int = 0
        self.cli_gate: Optional[asyncio.Event] = None  # if set, run_cli waits
        # Klipper's configfile.settings; None = an older wrapper without the hook.
        self.settings: Optional[dict] = None

    def as_adapter(self) -> Adapter:
        return Adapter(
            run_cli=self._run_cli,
            query_klippy_macros=self._query_macros,
            is_printing=lambda: False,
            emit_event=self._emit,
            query_klippy_settings=self._query_settings if self.settings is not None else None,
        )

    async def _query_settings(self) -> Optional[dict]:
        return self.settings

    async def _run_cli(self, args: list, timeout: float) -> CliResult:
        self.cli_calls += 1
        if self.cli_gate is not None:
            await self.cli_gate.wait()
        # args[0] is the cli_path; drop it and call cli.main directly.
        argv = args[1:]
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            rc = cli.main(argv)
        return CliResult(rc, buf_out.getvalue(), buf_err.getvalue())

    async def _query_macros(self) -> Optional[set]:
        return self.macros

    def _emit(self, name: str, payload: dict) -> None:
        self.events.append((name, payload))


def _make_core(tmp_path: Path, adapter: FakeAdapter,
               max_queue: int = 32) -> IntakeCore:
    gcodes = tmp_path / "gcodes"
    gcodes.mkdir()
    shutil.copy(FIXTURES / "valid_minimal.gcode", gcodes / "design.gcode")
    cfg = IntakeConfig(
        gcodes_root=gcodes,
        cli_path="stitchlab-gcode-intake",  # placeholder; fake adapter ignores
        hoops_config=str(tmp_path / "hoops.json"),
        max_queue=max_queue,
        thumbnail_size=128,  # smaller -> faster
    )
    (tmp_path / "hoops.json").write_text(json.dumps({
        "default": "standard",
        "hoops": {"standard": {"hoop_id": "standard",
                               "usable_width_mm": 0,
                               "usable_height_mm": 0}},
    }))
    return IntakeCore(cfg, adapter.as_adapter())


def _run(coro):
    return asyncio.run(coro)


# --- tests ------------------------------------------------------------------

def test_analyze_runs_cli_and_caches(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        core.start()
        await core.enqueue_analyze("design.gcode")
        # Wait until the task future completes.
        # The index entry is removed on completion, so poll the events.
        for _ in range(200):
            if any(e[1].get("state") == "valid" for e in fa.events):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError(f"valid not reached: {fa.events}")

        meta_dir = core.cfg.gcodes_root / META_SUBDIR
        thumb_dir = core.cfg.gcodes_root / THUMB_SUBDIR
        metas = list(meta_dir.glob("design.gcode.*.json"))
        thumbs = list(thumb_dir.glob("design.gcode.*.png"))
        assert metas and thumbs
        first_calls = fa.cli_calls

        # Second analyze is a cache hit -> no new CLI subprocess.
        await core.enqueue_analyze("design.gcode")
        await asyncio.sleep(0.05)  # let the worker pick it up
        # Worker re-runs the CLI even on cache hit? No — _run_analysis
        # short-circuits when meta_target exists. So cli_calls unchanged.
        # Give the worker a beat to actually run the second task.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if fa.cli_calls > first_calls:
                break
        assert fa.cli_calls == first_calls

        await core.stop()

    _run(go())


def test_queue_is_single_worker(tmp_path):
    fa = FakeAdapter()
    fa.cli_gate = None  # gate gets created inside the loop
    core = _make_core(tmp_path, fa)
    # second file under a different name so they don't collapse on cache.
    shutil.copy(FIXTURES / "long_jumps.gcode",
                core.cfg.gcodes_root / "second.gcode")

    async def go():
        fa.cli_gate = asyncio.Event()
        # Track concurrent invocations.
        in_flight = {"n": 0, "max": 0}

        original = fa._run_cli
        async def gated(args, timeout):
            in_flight["n"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["n"])
            try:
                await fa.cli_gate.wait()
                return await original(args, timeout)
            finally:
                in_flight["n"] -= 1
        fa._run_cli = gated  # type: ignore
        # Rebuild adapter with the patched callable.
        core.adapter = Adapter(
            run_cli=gated,
            query_klippy_macros=fa._query_macros,
            is_printing=lambda: False,
            emit_event=fa._emit,
        )

        core.start()
        await core.enqueue_analyze("design.gcode")
        await core.enqueue_analyze("second.gcode")
        # Let both reach the worker stage. Only ONE may be in flight.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if in_flight["n"] >= 1:
                break
        assert in_flight["max"] == 1
        fa.cli_gate.set()
        # Drain
        terminal = {"valid", "warnings", "blocked", "error"}
        for _ in range(200):
            await asyncio.sleep(0.01)
            done = sum(1 for e in fa.events if e[1].get("state") in terminal)
            if done >= 2:
                break
        else:
            raise AssertionError(f"queue didn't drain: {fa.events}")
        assert in_flight["max"] == 1
        await core.stop()

    _run(go())


def test_print_gating_pauses_queue(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        core.start()
        core.set_printing(True)
        await core.enqueue_analyze("design.gcode")
        await asyncio.sleep(0.1)
        # Worker is waiting on can_run -> no CLI invocation yet.
        assert fa.cli_calls == 0
        core.set_printing(False)
        for _ in range(200):
            await asyncio.sleep(0.01)
            if fa.cli_calls >= 1:
                break
        assert fa.cli_calls == 1
        await core.stop()

    _run(go())


def test_macro_diagnostic_missing(tmp_path):
    fa = FakeAdapter()
    fa.macros = {"STITCH"}  # klippy reports only STITCH defined
    core = _make_core(tmp_path, fa)

    async def go():
        result = await core._macro_diagnostic(["STITCH", "TRIM"])
        assert result["state"] == "missing"
        assert result["missing"] == ["TRIM"]
        assert result["checked"] is True

    _run(go())


def test_macro_diagnostic_offline(tmp_path):
    fa = FakeAdapter()
    fa.macros = None  # klippy offline
    core = _make_core(tmp_path, fa)

    async def go():
        result = await core._macro_diagnostic(["TRIM"])
        assert result["state"] == "offline"
        assert result["checked"] is False

    _run(go())


def test_macro_diagnostic_empty_passthrough(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        result = await core._macro_diagnostic([])
        assert result["state"] == "ok"
        assert result["missing"] == []

    _run(go())


def test_recheck_invalidates_cache(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        core.start()
        await core.enqueue_analyze("design.gcode")
        for _ in range(200):
            await asyncio.sleep(0.01)
            if fa.cli_calls >= 1:
                break
        # Wait for completion
        for _ in range(200):
            await asyncio.sleep(0.01)
            if any(e[1].get("state") == "valid" for e in fa.events):
                break
        first_calls = fa.cli_calls
        await core.recheck("design.gcode")
        for _ in range(200):
            await asyncio.sleep(0.01)
            if fa.cli_calls > first_calls:
                break
        assert fa.cli_calls > first_calls
        await core.stop()

    _run(go())


def test_upload_and_recheck_keep_out_of_hoop_design_blocked(tmp_path):
    # Found on hardware with beta.4: a square at X 70..90 in the 80 mm hoop
    # was blocked by prepare, but upload and recheck (no hoop given) called
    # it valid because the CLI then skipped the hoop check.
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)
    (tmp_path / "hoops.json").write_text(json.dumps({
        "default": "standard",
        "hoops": {"standard": {"hoop_id": "standard",
                               "usable_width_mm": 80,
                               "usable_height_mm": 130}},
    }))
    (core.cfg.gcodes_root / "outside.gcode").write_text(
        "G21\nG90\nG1 X70 Y22 F1500\nG1 X90 Y22\nG1 X90 Y42\nG1 X70 Y42\n"
        "G1 X70 Y22\n"
    )

    def verdicts() -> list:
        return [e[1]["state"] for e in fa.events
                if e[1].get("filename") == "outside.gcode"
                and e[1].get("state") not in ("queued", "running")]

    async def wait_for_verdicts(n: int) -> None:
        for _ in range(500):
            if len(verdicts()) >= n:
                return
            await asyncio.sleep(0.01)
        raise AssertionError(f"no verdict: {fa.events}")

    async def go():
        core.start()
        await core.enqueue_analyze("outside.gcode")
        await wait_for_verdicts(1)
        await core.recheck("outside.gcode")
        await wait_for_verdicts(2)
        assert verdicts() == ["blocked", "blocked"]
        meta = await core.metadata("outside.gcode")
        assert [d["code"] for d in meta["errors"]] == ["DESIGN_OUTSIDE_HOOP"]
        await core.stop()

    _run(go())


def test_cancel_queued_task(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        # Do not start the worker -> task stays queued.
        await core.enqueue_analyze("design.gcode")
        res = await core.cancel("design.gcode")
        assert res["state"] == "cancelled"
        assert fa.cli_calls == 0

    _run(go())


def test_path_escape_rejected(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        with pytest.raises(ValueError):
            await core._run_analysis("../etc/passwd", hoop_id=None, timeout=5)

    _run(go())


def test_prepare_uses_cache_on_repeat(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        r1 = await core.prepare("design.gcode")
        assert r1["status"] == "valid"
        calls_after_first = fa.cli_calls
        r2 = await core.prepare("design.gcode")
        assert r2["analysis_key"] == r1["analysis_key"]
        # No new subprocess on the cache hit.
        assert fa.cli_calls == calls_after_first

    _run(go())


def test_status_hashes_off_the_event_loop_and_caches(tmp_path, monkeypatch):
    # status() runs inside Moonraker's event loop for every listed file.
    # Hashing must happen on another thread, and only once per unchanged file.
    from stitchlab_intake import component

    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)
    real_hash = component._sha256_of_file
    hashed_on: list[int] = []

    def recording_hash(path):
        import threading
        hashed_on.append(threading.get_ident())
        return real_hash(path)

    monkeypatch.setattr(component, "_sha256_of_file", recording_hash)

    async def go():
        import threading
        loop_thread = threading.get_ident()
        await core.status("design.gcode")
        await core.status("design.gcode")
        await core.metadata("design.gcode")
        assert len(hashed_on) == 1, hashed_on
        assert hashed_on[0] != loop_thread

        # An upload over the file changes size/mtime: hash again.
        gcode = core.cfg.gcodes_root / "design.gcode"
        gcode.write_text(gcode.read_text() + "G1 X1 Y1\n")
        await core.status("design.gcode")
        assert len(hashed_on) == 2

    _run(go())


def test_changed_file_is_not_served_a_stale_analysis(tmp_path):
    # The digest cache must not let a rewritten file keep the old report.
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)

    async def go():
        first = await core.prepare("design.gcode")
        gcode = core.cfg.gcodes_root / "design.gcode"
        gcode.write_text(gcode.read_text().replace("G1 X20 Y20", "G1 X25 Y20"))
        second = await core.prepare("design.gcode")
        assert second["analysis_key"] != first["analysis_key"]
        assert second["bounds"]["width"] == 25.0

    _run(go())


# --- thumbnails when two analyses of one file overlap ------------------------

class RacingAdapter(FakeAdapter):
    """After the CLI renders, its temp PNG is gone: what the second of two
    overlapping analyses saw in the 2026-09-28 run, when the worker (after
    the upload) and prepare (Save & Start) analysed one file at once."""

    async def _run_cli(self, args: list, timeout: float) -> CliResult:
        result = await super()._run_cli(args, timeout)
        tmp_thumb = Path(args[args.index("--thumbnail-out") + 1])
        tmp_thumb.unlink()
        return result


def _no_temp_paths(report: dict) -> None:
    assert ".tmp" not in json.dumps(report)


def test_overlapping_analysis_points_at_the_finished_thumbnail(tmp_path):
    first = _make_core(tmp_path, FakeAdapter())
    report = _run(first._run_analysis("design.gcode", hoop_id=None, timeout=30))
    rel = report["thumbnail"]["relative_path"]
    assert rel.startswith(f"{THUMB_SUBDIR}/") and not rel.startswith("/")

    # Same file, same digests, but this run's temp PNG was taken by the other.
    shutil.rmtree(first.cfg.gcodes_root / META_SUBDIR)
    racing = IntakeCore(first.cfg, RacingAdapter().as_adapter())
    report = _run(racing._run_analysis("design.gcode", hoop_id=None, timeout=30))
    _no_temp_paths(report)
    assert report["thumbnail"]["relative_path"] == rel


def test_analysis_without_a_thumbnail_reports_none(tmp_path):
    core = _make_core(tmp_path, RacingAdapter())
    report = _run(core._run_analysis("design.gcode", hoop_id=None, timeout=30))
    _no_temp_paths(report)
    assert "thumbnail" not in report
    leftovers = list((core.cfg.gcodes_root / THUMB_SUBDIR).glob("*.tmp*"))
    leftovers += list((core.cfg.gcodes_root / META_SUBDIR).glob("*.tmp*"))
    assert leftovers == []


# --- beta6: comments Klipper can run, machine travel -------------------------

def test_prepare_rewrites_paren_comments_before_hashing(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)
    target = core.cfg.gcodes_root / "ink.gcode"
    shutil.copy(FIXTURES / "inkstitch_v3.gcode", target)
    before = target.read_text().split("\n")

    async def go():
        r1 = await core.prepare("ink.gcode")
        after = target.read_text().split("\n")
        assert len(after) == len(before)
        assert "(" not in target.read_text()
        assert "G90 ; use absolute coordinates" in after
        # The key describes the rewritten file, the bytes Klipper reads.
        assert r1["source"]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
        assert r1["state"] == "valid"
        assert r1["errors"] == [] and r1["warnings"] == []
        assert any(d["code"] == "PAREN_COMMENTS_NORMALISED" for d in r1["info"])
        calls = fa.cli_calls
        r2 = await core.prepare("ink.gcode")
        assert r2["analysis_key"] == r1["analysis_key"]
        assert fa.cli_calls == calls

    _run(go())


def test_rewrite_keeps_bom_and_crlf(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)
    target = core.cfg.gcodes_root / "crlf.gcode"
    target.write_bytes(b"\xef\xbb\xbfG90 (abs)\r\nG21\r\nG1 X1 Y1 F600\r\nG1 Z5\r\n")

    async def go():
        await core.prepare("crlf.gcode")
        assert target.read_bytes() == (
            b"\xef\xbb\xbfG90 ; abs\r\nG21\r\nG1 X1 Y1 F600\r\nG1 Z5\r\n")

    _run(go())


def test_unterminated_paren_file_is_left_untouched_and_blocked(tmp_path):
    fa = FakeAdapter()
    core = _make_core(tmp_path, fa)
    target = core.cfg.gcodes_root / "open.gcode"
    shutil.copy(FIXTURES / "unterminated_paren.gcode", target)
    original = target.read_bytes()

    async def go():
        report = await core.prepare("open.gcode")
        assert target.read_bytes() == original
        assert report["state"] == "blocked"
        assert "UNTERMINATED_PAREN" in [d["code"] for d in report["errors"]]

    _run(go())


TALL = "G21\nG90\nG1 X10 Y10 F600\nG1 Z5\nG1 X10 Y40\nG1 Z10\nG1 X10 Y70\nG1 Z15\n" \
       "G1 X10 Y100\nG1 Z20\nG1 X10 Y124.6\nG1 Z25\n"


def _settings(y_max: float) -> dict:
    return {"stepper_x": {"position_min": 0.0, "position_max": 90.0},
            "stepper_y": {"position_min": 0.0, "position_max": y_max}}


def test_machine_travel_from_klipper_blocks_and_rechecks_when_config_changes(tmp_path):
    fa = FakeAdapter()
    fa.settings = _settings(120.0)            # the image's printer.cfg
    core = _make_core(tmp_path, fa)
    (core.cfg.gcodes_root / "tall.gcode").write_text(TALL)

    async def go():
        r1 = await core.prepare("tall.gcode")
        assert r1["state"] == "blocked"
        assert [d["code"] for d in r1["errors"]] == ["DESIGN_OUTSIDE_MACHINE"]
        assert r1["machine_limits"] == {"x": [0.0, 90.0], "y": [0.0, 120.0]}
        calls = fa.cli_calls
        fa.settings = _settings(130.0)        # hybrid printer.cfg: re-check
        r2 = await core.prepare("tall.gcode")
        assert fa.cli_calls == calls + 1
        assert r2["errors"] == []
        fa.settings = {}                      # Klippy not ready: keep the last verdict
        r3 = await core.prepare("tall.gcode")
        assert fa.cli_calls == calls + 1
        assert r3["analysis_key"] == r2["analysis_key"]

    _run(go())


def test_wrapper_without_settings_hook_checks_the_hoop_only(tmp_path):
    fa = FakeAdapter()                        # settings None: hook absent
    core = _make_core(tmp_path, fa)
    (core.cfg.gcodes_root / "tall.gcode").write_text(TALL)

    async def go():
        report = await core.prepare("tall.gcode")
        assert report["machine_limits"] is None
        assert report["errors"] == []

    _run(go())
