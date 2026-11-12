#!/usr/bin/env python3
"""Prepare an environment and run the repository's tests, reporting every pass, failure and skip with its reason.

    python3 scripts/run_tests.py --prepare            # build DDS, install what is missing, restore nets, run all tests
    python3 scripts/run_tests.py                      # run the tests only
    python3 scripts/run_tests.py --set gen9           # the Gen 9 set (Gen 9, Gen 8 and Gen 7 engine, systems, rule bidder)
    python3 scripts/run_tests.py --files test_gen9_player_model.py test_rule_bidder.py
    python3 scripts/run_tests.py --prepare --with tensorflow,jax    # also install the heavy optional packages

Each test file runs in its own process with a time limit, `--jobs` at a time (default: the CPU count).
A test that unittest skips is reported with its reason; a file that cannot be imported because an
optional package is missing (TensorFlow, jax, h5py, ...) is reported as "not run" with the package
named, never as a pass. Anything else that goes wrong is a failure. The report (markdown, `--report`)
and the raw results (`--json`) say what ran, on what, and how long it took.

`--prepare` is idempotent: it builds `bridge_harness/libbridge_dds.so` only when it is missing or
older than its sources, installs numpy and scipy only when they are missing, and restores a net
only when its file is missing. It needs a C++20 compiler and, for installs, pip with network access
to PyPI. Standard library only; Python 3.11 or later (the project's own floor).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "bridge_harness" / ("libbridge_dds.dylib" if platform.system() == "Darwin" else "libbridge_dds.so")
OPTIONAL = {"tensorflow": "tensorflow-cpu" if platform.system() == "Linux" and platform.machine() == "x86_64" else "tensorflow", "jax": "jax[cpu]", "jaxlib": "jax[cpu]", "optax": "optax", "h5py": "h5py",
            "flax": "flax", "torch": "torch", "keras": "tensorflow-cpu" if platform.system() == "Linux" and platform.machine() == "x86_64" else "tensorflow"}
BASE_PACKAGES = {"numpy": "numpy>=1.24", "scipy": "scipy>=1.10"}
SETS = {
    "gen9": r"^test_(gen9.*|gen8.*|gen7.*|rule_bidder|bidding_systems|system|selfplay|layout_.*|boxctl)\.py$",
    "core": r"^test_(system|rule_bidder|layout_.*|boxctl|dds_cache)\.py$",
}

RUNNER = r'''
import json, re, sys, time, traceback, unittest
name, optional = sys.argv[1], set(json.loads(sys.argv[2]))
out = dict(file=name, tests=[], import_error=None)
suite = unittest.defaultTestLoader.discover("tests", pattern=name, top_level_dir="tests")
class R(unittest.TestResult):
    def _add(self, test, outcome, detail=""):
        out["tests"].append(dict(id=test.id(), outcome=outcome, detail=detail, seconds=round(time.time() - self._t, 3)))
    def startTest(self, test):
        self._t = time.time(); super().startTest(test)
    def addSuccess(self, test): self._add(test, "passed")
    def addFailure(self, test, err): self._add(test, "failed", self._exc_info_to_string(err, test))
    def addError(self, test, err):
        text = self._exc_info_to_string(err, test)
        if test.__class__.__name__ == "_FailedTest":  # discover's stand-in for a module that would not import
            out["import_error"] = text
        m = re.search(r"ModuleNotFoundError: No module named '([A-Za-z0-9_]+)", text)
        if m and m.group(1) in optional and issubclass(err[0], ImportError):
            self._add(test, "not run", "needs " + m.group(1))  # an optional package is missing: not a failure
            return
        self._add(test, "error", text)
    def addSkip(self, test, reason): self._add(test, "skipped", reason)
    def addExpectedFailure(self, test, err): self._add(test, "passed", "expected failure")
    def addUnexpectedSuccess(self, test): self._add(test, "failed", "unexpected success")
    def addSubTest(self, test, subtest, err):
        if err is not None:
            (self.addFailure if issubclass(err[0], test.failureException) else self.addError)(subtest, err)
r = R()
suite.run(r)
print("@@RESULT@@" + json.dumps(out))
'''


def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def missing_module(name: str) -> bool:
    return importlib.util.find_spec(name) is None


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- prepare

def pip_install(specs: list[str]) -> dict:
    if not specs:
        return dict(ok=True, installed=[])
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", *specs]
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv:
        cmd.insert(4, "--break-system-packages")  # a sandbox's system Python is marked externally managed
    t = time.time()
    r = sh(cmd, timeout=3600)
    return dict(ok=r.returncode == 0, installed=specs, seconds=round(time.time() - t, 1),
                error=(r.stderr or r.stdout)[-1500:] if r.returncode else "")


def build_dds(force: bool) -> dict:
    sources = sorted((ROOT / "vendor/dds/library/src").rglob("*.cpp")) + sorted((ROOT / "native").glob("*.cpp"))
    sources += sorted((ROOT / "vendor/dds/library/src").rglob("*.h"))
    newest = max(p.stat().st_mtime for p in sources)
    if LIB.exists() and LIB.stat().st_mtime >= newest and not force:
        return dict(built=False, reason="up to date", sha256=hashlib.sha256(LIB.read_bytes()).hexdigest())
    t = time.time()
    r = sh([sys.executable, "scripts/build_dds.py"], timeout=7200)
    out = dict(built=r.returncode == 0, seconds=round(time.time() - t, 1))
    if r.returncode:
        out["error"] = (r.stderr or r.stdout)[-2000:]
    else:
        out["sha256"] = hashlib.sha256(LIB.read_bytes()).hexdigest()
    return out


def restore_models() -> list[dict]:
    rows = []
    for script in sorted(ROOT.glob("models/**/restore*.py")):
        rel = script.relative_to(ROOT)
        manifest = script.parent / "manifest.json"
        target = None
        if manifest.exists():
            try:
                target = script.parent / json.loads(manifest.read_text()).get("output", "")
            except (ValueError, OSError):
                target = None
        if target is not None and target.is_file():
            rows.append(dict(script=str(rel), ok=True, note="already restored"))
            continue
        t = time.time()
        r = subprocess.run([sys.executable, "-I", script.name], cwd=script.parent, capture_output=True, text=True, timeout=1800)
        rows.append(dict(script=str(rel), ok=r.returncode == 0, seconds=round(time.time() - t, 1),
                         note=(r.stdout.strip().splitlines() or [""])[-1][:200] if r.returncode == 0 else (r.stderr or r.stdout).strip()[-400:]))
    return rows


def prepare(with_heavy: list[str], force_build: bool) -> dict:
    report = {}
    v = sys.version_info
    if v < (3, 11):
        raise SystemExit(f"Python {v.major}.{v.minor}: the project needs 3.11 or later")
    need = [spec for mod, spec in BASE_PACKAGES.items() if missing_module(mod)]
    if missing_module("pytest") and any(pytest_style(p.name) for p in (ROOT / "tests").glob("test_*.py")):
        need.append("pytest")
    for mod in with_heavy:
        spec = OPTIONAL.get(mod, mod)
        if missing_module(mod) and spec not in need:
            need.append(spec)
    log(f"prepare: installing {', '.join(need) if need else 'nothing (all present)'}")
    report["pip"] = pip_install(need)
    if not report["pip"]["ok"]:
        log("prepare: pip failed; continuing, and the tests that need those packages will say so")
    log("prepare: building DDS if needed")
    report["dds"] = build_dds(force_build)
    log(f"prepare: DDS {report['dds']}")
    log("prepare: restoring nets")
    report["models"] = restore_models()
    bad = [m for m in report["models"] if not m["ok"]]
    log(f"prepare: {len(report['models']) - len(bad)} of {len(report['models'])} restore scripts ok")
    return report


# ---------------------------------------------------------------- run

def pytest_style(name: str) -> bool:
    """A file of plain test functions (or one that imports pytest) is invisible to unittest discovery."""
    src = (ROOT / "tests" / name).read_text(errors="replace")
    return bool(re.search(r"^import pytest|^from pytest", src, re.M)) or (
        bool(re.search(r"^def test_", src, re.M)) and "unittest.TestCase" not in src and "(TestCase)" not in src)


def run_pytest(name: str, timeout: int, env: dict) -> dict:
    t = time.time()
    if missing_module("pytest"):
        return dict(file=name, tests=[], status="not run", needs="pytest", seconds=0.0)
    with tempfile.TemporaryDirectory() as d:
        xml = Path(d) / "junit.xml"
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", f"tests/{name}"],
                               cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return dict(file=name, tests=[], status="timeout", seconds=round(time.time() - t, 1), detail=f"no result after {timeout} s")
        if not xml.exists():
            return dict(file=name, tests=[], status="crashed", seconds=round(time.time() - t, 1),
                        detail=f"pytest exit {r.returncode}", stderr=(r.stdout + r.stderr)[-2000:])
        tests = []
        for case in ET.parse(xml).getroot().iter("testcase"):
            tid = f"{case.get('classname')}.{case.get('name')}"
            fail = case.find("failure") if case.find("failure") is not None else case.find("error")
            skip = case.find("skipped")
            if fail is not None:
                text = (fail.get("message") or "") + "\n" + (fail.text or "")
                m = re.search(r"No module named '([A-Za-z0-9_]+)", text)
                if m and m.group(1) in OPTIONAL:
                    tests.append(dict(id=tid, outcome="not run", detail="needs " + m.group(1)))
                else:
                    tests.append(dict(id=tid, outcome="failed", detail=text.strip()[-3000:]))
            elif skip is not None:
                tests.append(dict(id=tid, outcome="skipped", detail=skip.get("message") or "skipped"))
            else:
                tests.append(dict(id=tid, outcome="passed", detail=""))
    res = dict(file=name, tests=tests, import_error=None, runner="pytest", seconds=round(time.time() - t, 1))
    if not tests and r.returncode not in (0, 5):
        err = r.stdout + r.stderr
        res["import_error"] = err[-3000:]
    res["status"] = classify(res)
    return res


def run_file(name: str, timeout: int, env: dict) -> dict:
    if pytest_style(name):
        return run_pytest(name, timeout, env)
    t = time.time()
    try:
        r = subprocess.run([sys.executable, "-c", RUNNER, name, json.dumps(sorted(OPTIONAL))], cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as e:
        return dict(file=name, tests=[], status="timeout", seconds=round(time.time() - t, 1),
                    detail=f"no result after {timeout} s", stderr=(e.stderr or b"")[-1500:].decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")[-1500:])
    marker = [l for l in r.stdout.splitlines() if l.startswith("@@RESULT@@")]
    if not marker:
        return dict(file=name, tests=[], status="crashed", seconds=round(time.time() - t, 1),
                    detail=f"exit {r.returncode} with no result", stderr=(r.stderr or r.stdout)[-2000:])
    res = json.loads(marker[-1][len("@@RESULT@@"):])
    res["seconds"] = round(time.time() - t, 1)
    res["status"] = classify(res)
    return res


def classify(res: dict) -> str:
    err = res.get("import_error") or ""
    if err:
        m = re.search(r"No module named '([A-Za-z0-9_]+)", err)
        if m and m.group(1) in OPTIONAL:
            res["needs"] = m.group(1)
            res["tests"] = []
            return "not run"
        return "import error"
    outcomes = [t["outcome"] for t in res["tests"]]
    if any(o in ("failed", "error") for o in outcomes):
        return "failed"
    if "not run" in outcomes:
        res["needs"] = ", ".join(sorted({t["detail"][6:] for t in res["tests"] if t["outcome"] == "not run"}))
        return "partly not run" if "passed" in outcomes else "not run"
    if outcomes and all(o == "skipped" for o in outcomes):
        return "skipped"
    return "passed" if outcomes else "no tests"


def first_line(text: str) -> str:
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1].strip()[:220] if lines else ""


def render(results: list[dict], meta: dict) -> str:
    totals = {k: 0 for k in ("passed", "failed", "error", "skipped", "not run")}
    for r in results:
        for t in r["tests"]:
            totals[t["outcome"]] += 1
    by_status = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r["file"])
    L = [f"# Test run, {meta['finished']}", "",
         f"Source `{meta['commit']}` ({meta['branch']}); Python {meta['python']}, {meta['cpus']} CPUs, {meta['platform']}; "
         f"wall time {meta['wall_seconds']} s for {len(results)} files, {meta['jobs']} at a time"
         + (f", plus {meta['prepare_seconds']} s to prepare" if meta.get("prepare_seconds") is not None else "") + ".", "",
         f"**Tests:** {totals['passed']} passed, {totals['failed']} failed, {totals['error']} errors, {totals['skipped']} skipped, "
         f"{totals['not run']} not run for a missing optional package (plus any in files that could not be imported). "
         f"**Files:** " + ", ".join(f"{len(v)} {k}" for k, v in sorted(by_status.items())) + ".", ""]
    if meta.get("prepare"):
        p = meta["prepare"]
        d = p.get("dds", {})
        L += ["## Preparation", "",
              f"- pip: {'nothing needed' if not p['pip'].get('installed') else ('installed ' + ', '.join(p['pip']['installed']) if p['pip']['ok'] else 'FAILED: ' + first_line(p['pip'].get('error', '')))}",
              f"- DDS: {'built in ' + str(d.get('seconds')) + ' s' if d.get('built') else d.get('reason', 'FAILED: ' + first_line(d.get('error', '')))}"
              + (f", sha256 `{d['sha256'][:16]}`" if d.get("sha256") else ""),
              f"- Nets: " + "; ".join(f"`{Path(m['script']).parent.name}` {'ok' if m['ok'] else 'FAILED: ' + first_line(m['note'])}" for m in p["models"]), ""]
    L += ["## By file", "", "| File | Status | Passed | Failed/errors | Skipped | Not run | Seconds | Note |",
          "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    order = {"failed": 0, "import error": 1, "crashed": 2, "timeout": 3, "not run": 4, "partly not run": 5, "skipped": 6, "no tests": 7, "passed": 8}
    for r in sorted(results, key=lambda r: (order.get(r["status"], 9), r["file"])):
        c = {k: sum(1 for t in r["tests"] if t["outcome"] == k) for k in ("passed", "failed", "error", "skipped", "not run")}
        note = ""
        if r["status"] == "no tests":
            note = "no test found: check how this file defines its tests"
        if r["status"] in ("not run", "partly not run"):
            note = f"needs `{r['needs']}`"
        elif r["status"] in ("import error", "crashed", "timeout"):
            note = first_line(r.get("import_error") or r.get("stderr") or r.get("detail", "")).replace("|", "/")
        elif c["skipped"]:
            reasons = sorted({t["detail"] for t in r["tests"] if t["outcome"] == "skipped"})
            note = "skips: " + "; ".join(x[:90] for x in reasons[:3]).replace("|", "/")
        if c["skipped"] and r["status"] != "skipped" and not note.startswith("skips"):
            note += ("; " if note else "") + "skips: " + "; ".join(sorted({t["detail"][:90] for t in r["tests"] if t["outcome"] == "skipped"})[:3])
        L.append(f"| {r['file']} | {r['status']} | {c['passed']} | {c['failed'] + c['error']} | {c['skipped']} | {c['not run']} | {r['seconds']} | {note} |")
    L.append("")
    fails = [(r["file"], t) for r in results for t in r["tests"] if t["outcome"] in ("failed", "error")]
    if fails:
        L += ["## Failures", ""]
        for f, t in fails[:60]:
            L += [f"- `{t['id']}`: {first_line(t['detail'])}"]
        L.append("")
    skips = {}
    for r in results:
        for t in r["tests"]:
            if t["outcome"] in ("skipped", "not run"):
                skips.setdefault(t["detail"], []).append(t["id"])
        if r["status"] == "not run":
            skips.setdefault(f"file not run: needs {r['needs']}", []).append(r["file"])
    if skips:
        L += ["## Skipped, with reasons", "", "| Reason | Count | Example |", "| --- | ---: | --- |"]
        for reason, ids in sorted(skips.items(), key=lambda x: -len(x[1])):
            L.append(f"| {reason[:160].replace('|', '/')} | {len(ids)} | `{ids[0]}` |")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prepare", action="store_true", help="build DDS, install missing packages, restore nets first")
    ap.add_argument("--with", dest="heavy", default="", help="also install these optional packages, comma separated (tensorflow, jax, h5py)")
    ap.add_argument("--rebuild-dds", action="store_true")
    ap.add_argument("--set", choices=["all", *SETS], default="all")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per test file")
    ap.add_argument("--report", type=Path, help="write the markdown report here")
    ap.add_argument("--json", type=Path, help="write the raw results here")
    a = ap.parse_args()
    started = time.time()
    meta = dict(commit=sh(["git", "rev-parse", "--short", "HEAD"]).stdout.strip() or "unknown",
                branch=sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "unknown",
                python=platform.python_version(), cpus=os.cpu_count(), platform=f"{platform.system()} {platform.machine()}",
                jobs=a.jobs)
    if a.prepare:
        meta["prepare"] = prepare([x.strip() for x in a.heavy.split(",") if x.strip()], a.rebuild_dds)
        meta["prepare_seconds"] = round(time.time() - started, 1)
    files = a.files or sorted(p.name for p in (ROOT / "tests").glob("test_*.py"))
    if a.set != "all" and not a.files:
        files = [f for f in files if re.match(SETS[a.set], f)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if LIB.exists():
        env.setdefault("BRIDGE_DDS_LIBRARY", str(LIB))  # one test runs only when this is set
    env.setdefault("BRIDGE_DDS_CACHE", "")  # no persistent solver cache from test runs
    log(f"running {len(files)} test files, {a.jobs} at a time, {a.timeout} s limit each")
    t_run = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        futures = {pool.submit(run_file, f, a.timeout, env): f for f in files}
        for fut in cf.as_completed(futures):
            r = fut.result()
            results.append(r)
            n = len(r["tests"])
            log(f"  {r['file']}: {r['status']} ({n} tests, {r['seconds']} s)" + (f", needs {r['needs']}" if r.get("needs") else ""))
    meta["wall_seconds"] = round(time.time() - t_run, 1)
    meta["finished"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = render(results, meta)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(text + "\n")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(dict(meta=meta, results=results), indent=1) + "\n")
    print("\n" + text.split("## By file")[0].strip())
    bad = [r for r in results if r["status"] in ("failed", "import error", "crashed", "timeout")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
