"""Phase-3 intake queue, cache, and job-gating — Moonraker-independent.

The actual Moonraker glue lives in
``stitchlabos-config/moonraker/components/stitchlab_intake.py`` and is
loaded into Moonraker's components/ directory via symlink at image-build
time (same pattern as wifi_manager.py). That wrapper instantiates
``IntakeCore`` with a small adapter so this module stays import-clean
without Moonraker installed and can be unit-tested with a fake adapter.

Caches live next to the user's gcodes:

    <gcodes_root>/.stitchlab_meta/<basename>.<analysis_digest>.json
    <gcodes_root>/.stitchlab_thumbs/<basename>.<preview_digest>.png

The digests are sha1[:16] of the full analysis_key / preview_key strings.
Full keys are stored *inside* the JSON so a digest collision (unlikely)
is detectable rather than silently served.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from .report import DEFAULT_PLACEMENT
from .version import CHECKER_VERSION


log = logging.getLogger(__name__)


META_SUBDIR = ".stitchlab_meta"
THUMB_SUBDIR = ".stitchlab_thumbs"

# Upper bound for remembered file digests; far above a realistic gcodes
# folder, only there so a pathological one cannot grow memory unbounded.
_SHA_CACHE_MAX = 4096


@dataclass
class CliResult:
    """Outcome of one CLI subprocess invocation."""
    returncode: int
    stdout: str
    stderr: str


@dataclass
class IntakeConfig:
    gcodes_root: Path
    cli_path: str = "/usr/local/bin/stitchlab-gcode-intake"
    hoops_config: str = "/home/pi/stitchlab_intake/hoops.json"
    default_hoop: str = "standard"
    analyze_timeout: float = 60.0
    prepare_timeout: float = 30.0
    thumbnail_size: int = 768
    max_queue: int = 32


@dataclass
class Adapter:
    """Indirection to everything outside this module's control.

    Production glue fills these in with Moonraker calls; tests pass an
    in-memory fake. All methods are awaited even when trivially sync, so
    the core can drive either implementation uniformly.
    """
    run_cli: Callable[[list[str], float], Awaitable[CliResult]]
    query_klippy_macros: Callable[[], Awaitable[Optional[set[str]]]]
    is_printing: Callable[[], bool]
    emit_event: Callable[[str, dict], None]


@dataclass
class Task:
    filename: str
    kind: str  # "analyze" | "prepare" | "recheck"
    placement: Optional[dict] = None
    hoop_id: Optional[str] = None
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_running_loop().create_future())
    cancelled: bool = False


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _digest(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _meta_path(root: Path, basename: str, analysis_digest: str) -> Path:
    return root / META_SUBDIR / f"{basename}.{analysis_digest}.json"


def _thumb_path(root: Path, basename: str, preview_digest: str) -> Path:
    return root / THUMB_SUBDIR / f"{basename}.{preview_digest}.png"


def _normalise_placement(placement: Optional[dict],
                         hoop_id: Optional[str]) -> Optional[dict]:
    if placement is None and hoop_id is None:
        return None
    p = dict(DEFAULT_PLACEMENT)
    if isinstance(placement, dict):
        p.update(placement)
    if hoop_id:
        p["hoop_id"] = hoop_id
    p["hoop_id"] = str(p.get("hoop_id") or DEFAULT_PLACEMENT["hoop_id"])
    for key in ("offset_x", "offset_y", "rotation_deg", "scale"):
        try:
            p[key] = float(p.get(key, DEFAULT_PLACEMENT[key]))
        except (TypeError, ValueError):
            p[key] = float(DEFAULT_PLACEMENT[key])
    for key in ("frame_width_mm", "frame_height_mm"):
        if p.get(key) is None:
            p.pop(key, None)
            continue
        try:
            p[key] = float(p[key])
        except (TypeError, ValueError):
            p.pop(key, None)
    p["pivot"] = str(p.get("pivot") or DEFAULT_PLACEMENT["pivot"])
    return p


class IntakeCore:
    """Queue + cache + gating. One asyncio worker per instance."""

    def __init__(self, cfg: IntakeConfig, adapter: Adapter) -> None:
        self.cfg = cfg
        self.adapter = adapter
        self._queue: asyncio.Queue[Task] = asyncio.Queue(maxsize=cfg.max_queue)
        self._can_run = asyncio.Event()
        self._can_run.set()  # default: klippy not printing
        self._active: Optional[Task] = None
        self._worker: Optional[asyncio.Task] = None
        # Index by filename so duplicate analyze requests collapse.
        self._index: dict[str, Task] = {}
        # path -> ((inode, size, mtime_ns), sha256); see _file_sha256.
        self._sha_cache: dict[Path, tuple[tuple[int, int, int], str]] = {}

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    # --- gating ----------------------------------------------------------

    def set_printing(self, printing: bool) -> None:
        """Toggle the queue's run-permit; in-flight tasks finish."""
        if printing:
            self._can_run.clear()
        else:
            self._can_run.set()

    # --- public API used by the Moonraker wrapper ------------------------

    async def enqueue_analyze(self, filename: str, hoop_id: Optional[str] = None
                              ) -> dict:
        existing = self._index.get(filename)
        if existing and not existing.future.done():
            return {"filename": filename, "state": "queued", "duplicate": True}
        task = Task(filename=filename, kind="analyze", hoop_id=hoop_id)
        self._index[filename] = task
        await self._queue.put(task)
        self._emit(filename, "queued", queue_size=self._queue.qsize())
        return {"filename": filename, "state": "queued", "duplicate": False}

    async def recheck(self, filename: str, hoop_id: Optional[str] = None) -> dict:
        self._invalidate_caches(filename)
        return await self.enqueue_analyze(filename, hoop_id=hoop_id)

    async def cancel(self, filename: str) -> dict:
        task = self._index.get(filename)
        if not task:
            return {"filename": filename, "state": "unknown"}
        task.cancelled = True
        if self._active is task:
            # Worker checks `cancelled` after CLI returns; we cannot kill
            # the subprocess from here without holding its handle. Tests
            # cover the queued-cancel path; subprocess termination is a
            # later refinement once we know real timings on the Pi.
            return {"filename": filename, "state": "cancelling"}
        if not task.future.done():
            task.future.cancel()
        self._index.pop(filename, None)
        self._emit(filename, "cancelled")
        return {"filename": filename, "state": "cancelled"}

    async def status(self, filename: str) -> dict:
        task = self._index.get(filename)
        cached = await self._load_cached_meta(filename)
        if cached:
            macros = await self._macro_diagnostic(cached.get("referenced_unknown_macros") or [])
            return {
                "filename": filename,
                "state": cached.get("status", "unknown"),
                "analysis_key": cached.get("analysis_key"),
                "preview_key": cached.get("preview_key"),
                "macros": macros,
                "in_queue": bool(task and not task.future.done()),
            }
        if task and not task.future.done():
            return {"filename": filename, "state": "queued", "in_queue": True}
        return {"filename": filename, "state": "unchecked", "in_queue": False}

    async def metadata(self, filename: str) -> dict:
        task = self._index.get(filename)
        cached = await self._load_cached_meta(filename)
        if cached:
            report = dict(cached)
            report["filename"] = filename
            report["state"] = cached.get("status", "unknown")
            report["macros"] = await self._macro_diagnostic(
                cached.get("referenced_unknown_macros") or []
            )
            report["in_queue"] = bool(task and not task.future.done())
            return report
        return await self.status(filename)

    async def prepare(self, filename: str, placement: Optional[dict] = None,
                      hoop_id: Optional[str] = None) -> dict:
        """Synchronous start-flow path: ensure analysis exists, return report.

        Bypasses queue order — the start flow blocks on this. Job-gating
        does NOT apply here because prepare is invoked before the print
        actually starts.
        """
        placement = _normalise_placement(placement, hoop_id)
        hoop_id = (placement or {}).get("hoop_id") or hoop_id or self.cfg.default_hoop
        cached = await self._load_cached_meta(filename)
        if cached is not None and placement is not None:
            cached_raw_placement = cached.get("placement") or {}
            cached_placement = _normalise_placement(
                cached_raw_placement, cached_raw_placement.get("hoop_id")
            )
            if cached_placement != placement:
                cached = None
        if cached is None:
            cached = await self._run_analysis(filename, hoop_id=hoop_id,
                                              timeout=self.cfg.prepare_timeout,
                                              placement=placement)
        macros = await self._macro_diagnostic(cached.get("referenced_unknown_macros") or [])
        report = dict(cached)
        report["filename"] = filename
        report["state"] = cached.get("status")
        report["macros"] = macros
        return report

    # --- worker loop -----------------------------------------------------

    async def _worker_loop(self) -> None:
        while True:
            task = await self._queue.get()
            try:
                if task.cancelled:
                    self._index.pop(task.filename, None)
                    continue
                await self._can_run.wait()
                self._active = task
                self._emit(task.filename, "running")
                try:
                    report = await self._run_analysis(
                        task.filename, hoop_id=task.hoop_id,
                        timeout=self.cfg.analyze_timeout,
                    )
                    self._emit(task.filename, report.get("status", "unknown"),
                               analysis_key=report.get("analysis_key"))
                    if not task.future.done():
                        task.future.set_result(report)
                except Exception as exc:  # noqa: BLE001
                    log.exception("intake: analyze failed for %s", task.filename)
                    self._emit(task.filename, "error", error=str(exc))
                    if not task.future.done():
                        task.future.set_exception(exc)
                finally:
                    self._active = None
                    self._index.pop(task.filename, None)
            finally:
                self._queue.task_done()

    # --- analysis ---------------------------------------------------------

    async def _run_analysis(self, filename: str, hoop_id: Optional[str],
                            timeout: float,
                            placement: Optional[dict] = None) -> dict:
        gcode_path = self._resolve(filename)
        if not gcode_path.is_file():
            raise FileNotFoundError(filename)

        sha = await self._file_sha256(gcode_path)
        analysis_key = f"{sha}:{CHECKER_VERSION}"
        analysis_digest = _digest(analysis_key)
        basename = gcode_path.name
        meta_root = self.cfg.gcodes_root / META_SUBDIR
        thumb_root = self.cfg.gcodes_root / THUMB_SUBDIR
        meta_root.mkdir(parents=True, exist_ok=True)
        thumb_root.mkdir(parents=True, exist_ok=True)

        meta_target = _meta_path(self.cfg.gcodes_root, basename, analysis_digest)
        placement = _normalise_placement(placement, hoop_id)
        if meta_target.is_file():
            try:
                existing = json.loads(meta_target.read_text())
                if (
                    existing.get("analysis_key") == analysis_key
                    and (
                        placement is None
                        or _normalise_placement(
                            existing.get("placement"),
                            (existing.get("placement") or {}).get("hoop_id"),
                        ) == placement
                    )
                ):
                    return existing
            except (OSError, ValueError):
                pass  # rebuild

        tmp_meta = meta_target.with_suffix(".json.tmp")
        # Preview path: we want the final filename keyed by preview_key,
        # but the CLI doesn't know the digest yet. Render to a tmp PNG,
        # parse the meta to discover preview_key, then rename.
        tmp_thumb = thumb_root / f"{basename}.{analysis_digest}.tmp.png"

        cli_args = [
            self.cfg.cli_path, "analyze", str(gcode_path),
            "--output", str(tmp_meta),
            "--thumbnail-out", str(tmp_thumb),
            "--thumbnail-size", str(self.cfg.thumbnail_size),
            "--hoops-config", self.cfg.hoops_config,
            "--worker-mode",
        ]
        if placement:
            cli_args += ["--placement-json", json.dumps(placement)]
            frame_width = placement.get("frame_width_mm")
            frame_height = placement.get("frame_height_mm")
            if frame_width and frame_height:
                cli_args += [
                    "--hoop-id", str(placement.get("hoop_id") or hoop_id or self.cfg.default_hoop),
                    "--hoop-width-mm", str(frame_width),
                    "--hoop-height-mm", str(frame_height),
                ]
            elif placement.get("hoop_id"):
                cli_args += ["--hoop", str(placement["hoop_id"])]
        elif hoop_id:
            cli_args += ["--hoop", hoop_id]

        result = await self.adapter.run_cli(cli_args, timeout)
        if result.returncode == 3:
            raise RuntimeError(f"CLI failure: {result.stderr.strip()}")

        try:
            report = json.loads(tmp_meta.read_text())
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"CLI produced no JSON: {exc}") from exc

        preview_key = report.get("preview_key")
        if preview_key and tmp_thumb.is_file():
            preview_digest = _digest(preview_key)
            thumb_target = _thumb_path(self.cfg.gcodes_root, basename, preview_digest)
            tmp_thumb.replace(thumb_target)
            report["thumbnail"] = {
                "relative_path": f"{THUMB_SUBDIR}/{thumb_target.name}",
                "width": (report.get("thumbnail") or {}).get("width", self.cfg.thumbnail_size),
                "height": (report.get("thumbnail") or {}).get("height", self.cfg.thumbnail_size),
            }
        elif tmp_thumb.is_file():
            tmp_thumb.unlink()  # no preview_key — orphan, drop it

        tmp_meta.replace(meta_target)
        # Best-effort write-back with possibly updated thumbnail entry.
        meta_target.write_text(json.dumps(report, indent=2, sort_keys=False))
        return report

    # --- macros ----------------------------------------------------------

    async def _macro_diagnostic(self, referenced_unknown: list[str]) -> dict:
        if not referenced_unknown:
            return {"state": "ok", "missing": []}
        defined = await self.adapter.query_klippy_macros()
        if defined is None:
            return {"state": "offline", "missing": [], "checked": False}
        missing = sorted(m for m in referenced_unknown if m.upper() not in defined)
        return {
            "state": "missing" if missing else "ok",
            "missing": missing,
            "checked": True,
        }

    # --- cache helpers ---------------------------------------------------

    def _invalidate_caches(self, filename: str) -> None:
        basename = Path(filename).name
        for sub, suffix in ((META_SUBDIR, ".json"), (THUMB_SUBDIR, ".png")):
            d = self.cfg.gcodes_root / sub
            if not d.is_dir():
                continue
            for p in d.glob(f"{basename}.*{suffix}"):
                try:
                    p.unlink()
                except OSError:
                    pass

    async def _file_sha256(self, path: Path) -> str:
        """SHA-256 of a G-code file, hashed off the event loop and cached.

        This code runs inside Moonraker's event loop, and Mainsail asks
        status() for every listed file: hashing multi-MB files from an SD
        card there stalls websocket traffic and Klippy updates. The digest
        is reused while inode, size and mtime are unchanged; an upload
        replaces or rewrites the file, which changes them. The key is taken
        before hashing, so a file changed mid-hash is hashed again next time.
        """
        st = path.stat()
        key = (st.st_ino, st.st_size, st.st_mtime_ns)
        hit = self._sha_cache.get(path)
        if hit is not None and hit[0] == key:
            return hit[1]
        sha = await asyncio.get_running_loop().run_in_executor(
            None, _sha256_of_file, path)
        if len(self._sha_cache) >= _SHA_CACHE_MAX:
            self._sha_cache.clear()
        self._sha_cache[path] = (key, sha)
        return sha

    async def _load_cached_meta(self, filename: str) -> Optional[dict]:
        gcode_path = self._resolve(filename)
        if not gcode_path.is_file():
            return None
        try:
            sha = await self._file_sha256(gcode_path)
        except OSError:
            return None
        analysis_key = f"{sha}:{CHECKER_VERSION}"
        meta = _meta_path(self.cfg.gcodes_root, gcode_path.name, _digest(analysis_key))
        if not meta.is_file():
            return None
        try:
            data = json.loads(meta.read_text())
        except (OSError, ValueError):
            return None
        if data.get("analysis_key") != analysis_key:
            return None
        return data

    def _resolve(self, filename: str) -> Path:
        # Accept both bare and "gcodes/"-prefixed paths; reject escapes.
        rel = filename
        if rel.startswith("gcodes/"):
            rel = rel[len("gcodes/"):]
        p = (self.cfg.gcodes_root / rel).resolve()
        root = self.cfg.gcodes_root.resolve()
        if root not in p.parents and p != root:
            raise ValueError(f"path escapes gcodes root: {filename}")
        return p

    def _emit(self, filename: str, state: str, **extra: Any) -> None:
        payload = {"filename": filename, "state": state}
        payload.update(extra)
        try:
            self.adapter.emit_event("stitchlab_intake:status", payload)
        except Exception:  # noqa: BLE001
            log.exception("intake: emit_event failed")
