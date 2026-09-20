"""IntakeCore tests with a fake adapter.

The fake `run_cli` shells into the CLI in-process via ``cli.main`` so the
sidecars and thumbnails are produced exactly as on the Pi — no mock JSON.
That keeps these tests honest about what Moonraker would observe.
"""

from __future__ import annotations

import asyncio
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

    def as_adapter(self) -> Adapter:
        return Adapter(
            run_cli=self._run_cli,
            query_klippy_macros=self._query_macros,
            is_printing=lambda: False,
            emit_event=self._emit,
        )

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
