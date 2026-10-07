"""Klipper drift check: our configs and sample jobs at the pin and at upstream.

Runs inside the drift container (see run.sh). For each side (the release's
pin and an upstream ref, master by default) it checks out Klipper, builds
the SKR Pico's data dictionary from firmware/skr-pico/klipper.config, and
runs every sample through klippy in batch mode
(`klippy.py <cfg> -i <gcode> -o <out> -d <dict>`, as Klipper's own
scripts/test_klippy.py does) for each config variant. It compares exit
status, Klipper's responses and the MCU command stream between the sides,
checks each sample's expectations, and lists the upstream commits since the
pin that touch the G-code path, homing, pause/resume and the config parser.

Exit status: 0 when every expectation holds at the pin, 1 otherwise. Drift
against upstream is reported, never fatal.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Upstream files whose changes can alter how our jobs and macros run.
WATCHED_KLIPPER_FILES = (
    "klippy/gcode.py",
    "klippy/extras/gcode_move.py",
    "klippy/extras/virtual_sdcard.py",
    "klippy/extras/homing.py",
    "klippy/extras/homing_override.py",
    "klippy/extras/pause_resume.py",
    "klippy/extras/gcode_macro.py",
    "klippy/configfile.py",
)
CONFIG_CHANGES = "docs/Config_Changes.md"

# Log lines that differ between Klipper builds without saying anything
# about behaviour (versions, build tools, timing of the run).
NOISE_PREFIXES = (
    "Loaded MCU", "MCU 'mcu' config:", "MCU 'mcu' kconfig:", "Sending MCU",
    "Configured MCU", "Running full garbage collection", "Unfreezing garbage",
)
CONFIG_DUMP_END = "======================="


@dataclass
class Sample:
    name: str
    path: Path
    variants: list[str]
    expect: str                      # "ok" | "error"
    log: list[str] = field(default_factory=list)
    nolog: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, path: Path) -> "Sample":
        meta: dict[str, list[str]] = {}
        for line in path.read_text().splitlines():
            if line.startswith("; drift:"):
                key, _, value = line[len("; drift:"):].strip().partition("=")
                meta.setdefault(key.strip(), []).append(value.strip())
        return cls(
            name=path.stem,
            path=path,
            variants=[v for v in ",".join(meta.get("variants", ["image"])).split(",") if v],
            expect=(meta.get("expect") or ["ok"])[0],
            log=meta.get("log", []),
            nolog=meta.get("nolog", []),
        )


@dataclass
class Run:
    exit_code: int
    responses: list[str]
    mcu_lines: int
    mcu_digest: str          # "<signature sha256> <step totals per oid as JSON>"

    def as_dict(self) -> dict:
        signature, _, steps = self.mcu_digest.partition(" ")
        return {"exit": self.exit_code, "responses": self.responses,
                "mcu_lines": self.mcu_lines, "mcu_signature": signature,
                "mcu_steps": json.loads(steps)}


def sh(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-2000:] + result.stderr[-2000:])
        raise SystemExit(f"failed ({result.returncode}): {' '.join(args)}")
    return result.stdout


def checkout(mirror: Path, ref: str, dest: Path) -> str:
    if not dest.exists():
        sh("git", "clone", "--quiet", str(mirror), str(dest))
    sh("git", "-C", str(dest), "checkout", "--quiet", "--force", ref)
    return sh("git", "-C", str(dest), "rev-parse", "HEAD").strip()


def build_dictionary(klipper: Path, commit: str, fw_config: Path, cache: Path) -> Path:
    """The rp2040 data dictionary for this commit and firmware config."""
    key = hashlib.sha256(commit.encode() + fw_config.read_bytes()).hexdigest()[:16]
    target = cache / f"klipper-{commit[:12]}-{key}.dict"
    if target.exists():
        return target
    shutil.copy(fw_config, klipper / ".config")
    sh("make", "-C", str(klipper), "olddefconfig")
    sh("make", "-C", str(klipper), f"-j{os.cpu_count() or 2}")
    shutil.copy(klipper / "out" / "klipper.dict", target)
    return target


def python_env(klipper: Path, cache: Path) -> Path:
    """A venv with klippy's requirements, shared by commits that agree on them."""
    reqs = klipper / "scripts" / "klippy-requirements.txt"
    env = cache / f"env-{hashlib.sha256(reqs.read_bytes()).hexdigest()[:16]}"
    if not (env / "bin" / "python").exists():
        sh("uv", "venv", "--quiet", "--python", "/usr/bin/python3", str(env))
        subprocess.run(["uv", "pip", "install", "--quiet", "--python", str(env / "bin" / "python"),
                        "-r", str(reqs)], check=True)
    return env / "bin" / "python"


def responses_of(log_text: str) -> list[str]:
    """What Klipper said after loading the config, without noise.

    Dropped: build and version lines, the input's own comment lines (echoed
    at debug level) and the reactor's wall-clock "busy" reports with their
    stack lines.
    """
    lines = log_text.splitlines()
    if CONFIG_DUMP_END in lines:
        last = len(lines) - 1 - lines[::-1].index(CONFIG_DUMP_END)
        lines = lines[last + 1:]
    kept = []
    in_busy_report = False
    for line in lines:
        if line.startswith("Reactor ") and " busy for " in line:
            in_busy_report = True
            continue
        if in_busy_report and line.startswith("- '"):
            continue
        in_busy_report = False
        if line.strip() and not line.startswith(NOISE_PREFIXES) and not line.startswith(";"):
            kept.append(line.rstrip())
    return kept


def mcu_digest(dump: str) -> str:
    """Digest of what the MCU commands make the machine do.

    Batch mode schedules by wall clock, so how Klipper splits steps into
    queue_step commands, where an endstop_home lands, how often an enable pin
    toggles at the end and even the length of a homing move (about 1 % of
    Z steps) differ from run to run of the same commit. Kept: per stepper
    the sequence of directions, and which other commands occur. Positions
    are compared exactly through the responses (_DRIFT_POS); the step
    totals go to summary.json for a closer look.
    """
    steps: dict[str, int] = {}
    dirs: dict[str, list[str]] = {}
    other: set[str] = set()
    for line in dump.splitlines():
        words = line.split()
        if not words:
            continue
        fields = dict(w.split("=", 1) for w in words[1:] if "=" in w)
        oid = fields.get("oid", "")
        if words[0] == "queue_step":
            steps[oid] = steps.get(oid, 0) + int(fields.get("count", "0"))
        elif words[0] == "set_next_step_dir":
            seq = dirs.setdefault(oid, [])
            if not seq or seq[-1] != fields.get("dir"):
                seq.append(fields.get("dir", ""))
        else:
            other.add(words[0])
    signature = json.dumps({"dirs": dirs, "other": sorted(other)}, sort_keys=True)
    return hashlib.sha256(signature.encode()).hexdigest() + " " + json.dumps(steps, sort_keys=True)


def run_sample(python: Path, klipper: Path, dictionary: Path, cfg: Path,
               sample: Sample, jobs: Path, outdir: Path) -> Run:
    shutil.rmtree(outdir, ignore_errors=True)   # klippy appends to an old log
    outdir.mkdir(parents=True)
    gcodes = Path("/tmp/drift-gcodes")   # virtual_sdcard path set in sim.cfg
    shutil.rmtree(gcodes, ignore_errors=True)
    shutil.copytree(jobs, gcodes)
    serial = outdir / "out.serial"
    log = outdir / "klippy.log"
    result = subprocess.run(
        [str(python), str(klipper / "klippy" / "klippy.py"), str(cfg),
         "-i", str(sample.path), "-o", str(serial), "-v", "-d", str(dictionary),
         "-l", str(log)],
        cwd=klipper, capture_output=True, text=True, timeout=600)
    dump = ""
    if serial.exists():
        dump = subprocess.run([str(python), str(klipper / "klippy" / "parsedump.py"),
                               str(dictionary), str(serial)],
                              capture_output=True, text=True, timeout=600).stdout
        serial.unlink()
    (outdir / "mcu.txt").write_text(dump)
    log_text = log.read_text(errors="replace") if log.exists() else result.stderr
    run = Run(exit_code=result.returncode, responses=responses_of(log_text),
              mcu_lines=dump.count("\n"),
              mcu_digest=mcu_digest(dump))
    (outdir / "responses.txt").write_text("\n".join(run.responses) + "\n")
    return run


def check_expectations(sample: Sample, run: Run) -> list[str]:
    failures = []
    ok = run.exit_code == 0
    if (sample.expect == "ok") != ok:
        failures.append(f"expected {sample.expect}, klippy exited {run.exit_code}")
    text = "\n".join(run.responses)
    failures += [f"missing in log: {s}" for s in sample.log if s not in text]
    failures += [f"unexpected in log: {s}" for s in sample.nolog if s in text]
    return failures


def variant_configs(inputs: Path, variants_dir: Path, sim: Path, work: Path) -> dict[str, Path]:
    """One top-level config per variant; printer.cfg includes mainsail.cfg and
    embroidery_macros.cfg from its own directory, later includes override."""
    configs = {}
    base = work / "machine"
    core = work / "core"
    for d in (base, core):
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(inputs, d)
        shutil.copy(sim, d / "drift-sim.cfg")
        for extra in variants_dir.glob("*.cfg"):
            shutil.copy(extra, d / f"variant-{extra.name}")
    # core: Klipper and mainsail.cfg only, no StitchLAB macros.
    (core / "embroidery_macros.cfg").write_text("# drift check: no StitchLAB macros\n")
    (core / "drift-core.cfg").write_text("[include printer.cfg]\n[include drift-sim.cfg]\n")
    configs["core"] = core / "drift-core.cfg"
    (base / "drift-image.cfg").write_text("[include printer.cfg]\n[include drift-sim.cfg]\n")
    configs["image"] = base / "drift-image.cfg"
    for extra in sorted(variants_dir.glob("*.cfg")):
        name = extra.stem.split("-")[0]
        top = base / f"drift-{name}.cfg"
        top.write_text(f"[include printer.cfg]\n[include variant-{extra.name}]\n"
                       "[include drift-sim.cfg]\n")
        configs[name] = top
    for extra in sorted((inputs / "extra").glob("*/printer.cfg")) if (inputs / "extra").is_dir() else []:
        d = work / f"extra-{extra.parent.name}"
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(extra.parent, d)
        for name in ("mainsail.cfg", "embroidery_macros.cfg"):
            if not (d / name).exists():
                shutil.copy(inputs / name, d / name)
        shutil.copy(sim, d / "drift-sim.cfg")
        (d / "drift-extra.cfg").write_text("[include printer.cfg]\n[include drift-sim.cfg]\n")
        configs[f"extra-{extra.parent.name}"] = d / "drift-extra.cfg"
    return configs


def upstream_changes(mirror: Path, pin: str, compare: str) -> dict:
    fmt = "--format=%h %ad %s"
    commits = sh("git", "-C", str(mirror), "log", fmt, "--date=short", f"{pin}..{compare}").splitlines()
    watched = sh("git", "-C", str(mirror), "log", fmt, "--date=short", f"{pin}..{compare}",
                 "--", *WATCHED_KLIPPER_FILES).splitlines()
    diff = sh("git", "-C", str(mirror), "diff", f"{pin}..{compare}", "--", CONFIG_CHANGES)
    added = [line[1:] for line in diff.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    return {"commits": len(commits), "watched": watched, "config_changes": added}


def mainsail_config_changes(mirror: Path, pin: str, compare: str) -> list[str]:
    return sh("git", "-C", str(mirror), "log", "--format=%h %ad %s", "--date=short",
              f"{pin}..{compare}").splitlines()


def compare_runs(pin: Run, other: Run) -> list[str]:
    notes = []
    if pin.exit_code != other.exit_code:
        notes.append(f"exit {pin.exit_code} -> {other.exit_code}")
    if pin.responses != other.responses:
        diff = difflib.unified_diff(pin.responses, other.responses, "pin", "upstream",
                                    lineterm="", n=1)
        notes.append("responses differ:\n" + "\n".join(list(diff)[:40]))
    if pin.mcu_digest.split()[0] != other.mcu_digest.split()[0]:
        notes.append(f"MCU commands differ: stepper directions or command kinds "
                     f"({pin.mcu_lines} -> {other.mcu_lines} lines; see runs/*/mcu.txt)")
    return notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--klipper-mirror", type=Path, required=True)
    ap.add_argument("--mainsail-config-mirror", type=Path, required=True)
    ap.add_argument("--pin", required=True, help="Klipper commit of the release")
    ap.add_argument("--compare", default="master", help="upstream Klipper ref to compare with")
    ap.add_argument("--mainsail-config-pin", required=True)
    ap.add_argument("--mainsail-config-compare", default="master")
    ap.add_argument("--inputs", type=Path, required=True,
                    help="dir with pin/ and compare/ config sets (printer.cfg, mainsail.cfg, ...)")
    ap.add_argument("--drift-dir", type=Path, required=True, help="stitchlabos/drift")
    ap.add_argument("--firmware-config", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    args.cache.mkdir(parents=True, exist_ok=True)
    work = Path("/tmp/drift-work")
    samples = [Sample.parse(p) for p in sorted((args.drift_dir / "samples").glob("*.gcode"))]
    sides = {"pin": args.pin, "upstream": args.compare}
    results: dict[str, dict[str, dict[str, Run]]] = {}
    commits: dict[str, str] = {}

    for side, ref in sides.items():
        klipper = work / f"klipper-{side}"
        commit = checkout(args.klipper_mirror, ref, klipper)
        commits[side] = commit
        version = sh("git", "-C", str(klipper), "describe", "--tags", "--long", "--always").strip()
        print(f"[{side}] Klipper {version} ({commit[:12]})", flush=True)
        dictionary = build_dictionary(klipper, commit, args.firmware_config, args.cache)
        python = python_env(klipper, args.cache)
        configs = variant_configs(args.inputs / ("pin" if side == "pin" else "compare"),
                                  args.drift_dir / "variants", args.drift_dir / "sim.cfg",
                                  work / f"cfg-{side}")
        results[side] = {}
        for sample in samples:
            for variant in sample.variants + [v for v in configs if v.startswith("extra-")
                                              and "image" in sample.variants]:
                if variant not in configs:
                    continue
                run = run_sample(python, klipper, dictionary, configs[variant], sample,
                                 args.drift_dir / "samples" / "jobs",
                                 args.out / "runs" / side / variant / sample.name)
                results[side].setdefault(variant, {})[sample.name] = run
                print(f"[{side}] {variant:<12} {sample.name:<24} exit {run.exit_code}", flush=True)

    sample_by_name = {s.name: s for s in samples}
    pin_failures: dict[str, list[str]] = {}
    upstream_failures: dict[str, list[str]] = {}
    drift: dict[str, list[str]] = {}
    for variant, runs in results["pin"].items():
        for name, run in runs.items():
            key = f"{variant}/{name}"
            fails = check_expectations(sample_by_name[name], run)
            if fails:
                pin_failures[key] = fails
            other = results["upstream"].get(variant, {}).get(name)
            if other is None:
                continue
            ufails = check_expectations(sample_by_name[name], other)
            if ufails:
                upstream_failures[key] = ufails
            notes = compare_runs(run, other)
            if notes:
                drift[key] = notes

    changes = upstream_changes(args.klipper_mirror, commits["pin"], commits["upstream"])
    ms_changes = mainsail_config_changes(args.mainsail_config_mirror, args.mainsail_config_pin,
                                         args.mainsail_config_compare)
    summary = {
        "klipper": {"pin": commits["pin"], "upstream": commits["upstream"], **changes},
        "mainsail_config": {"pin": args.mainsail_config_pin, "commits": ms_changes},
        "pin_failures": pin_failures,
        "upstream_failures": upstream_failures,
        "drift": drift,
        "runs": {side: {v: {n: r.as_dict() for n, r in runs.items()}
                        for v, runs in by_variant.items()}
                 for side, by_variant in results.items()},
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out / "report.md").write_text(report(summary, args.compare))
    print((args.out / "report.md").read_text())
    return 1 if pin_failures else 0


def report(s: dict, compare: str) -> str:
    k = s["klipper"]
    out = ["# Klipper drift check", "",
           f"- Pin: Klipper `{k['pin'][:12]}`; upstream `{compare}`: `{k['upstream'][:12]}`, "
           f"{k['commits']} commit(s) since the pin",
           f"- mainsail-config pin `{s['mainsail_config']['pin'][:12]}`: "
           f"{len(s['mainsail_config']['commits'])} upstream commit(s) since", ""]
    out += ["## Expectations at the pin", ""]
    if s["pin_failures"]:
        for key, fails in sorted(s["pin_failures"].items()):
            out += [f"- **{key}**: " + "; ".join(fails)]
    else:
        out.append("All samples behave as expected.")
    out += ["", "## Drift: pin vs upstream", ""]
    if not s["drift"] and not s["upstream_failures"]:
        out.append("No difference in exit status, responses or MCU commands.")
    for key, fails in sorted(s["upstream_failures"].items()):
        out.append(f"- **{key}** at upstream: " + "; ".join(fails))
    for key, notes in sorted(s["drift"].items()):
        out.append(f"- **{key}**:")
        for note in notes:
            out += ["", "```", note, "```", ""] if "\n" in note else [f"  - {note}"]
    out += ["", "## Upstream commits since the pin touching the G-code path", ""]
    out += [f"- {c}" for c in k["watched"]] or ["None."]
    out += ["", "## New lines in docs/Config_Changes.md", ""]
    added = [line for line in k["config_changes"] if line.strip()]
    out += [f"> {line}" for line in added] or ["None."]
    out += ["", "## mainsail-config commits since the pin", ""]
    out += [f"- {c}" for c in s["mainsail_config"]["commits"]] or ["None."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
