#!/usr/bin/env python3
"""BEN lanes for Gen 9 matches on a box: one BEN server per lane, each in its own network namespace, and
scripts/gen9_match.py with one worker per lane on disjoint deal ranges, merged into one results file.

Why namespaces: a BEN bot's URL (http://127.0.0.1:8087 for BEN 16 in the Gen 7 capture capsule) is part of the
bot's identity, so every lane must reach its own server at that same address. As g7's arena lanes do, each lane
is a namespace with only a loopback device; its BEN server and its match worker both run inside it, as systemd
units with NetworkNamespacePath= (systemd 242 or later; Ubuntu 24.04 has 255). Needs passwordless sudo.

  python3 ops/gen9_ben_lanes.py install --ben ~/work/g9/ben --venv ~/work/g9/ben-venv
  python3 ops/gen9_ben_lanes.py run --pair 9p-32~ben --deals 16 --lanes 2 --seed 91 \
      --source ~/work/g9/capsule/recovery --bots configs/gen9-proto-bots.json --out ~/work/g9/runs/w7-smoke
  python3 ops/gen9_ben_lanes.py status | measure | down [--lanes N]

`run` is `up`, then `play` (start one match unit per lane, wait for them), then `merge`. `merge` refuses lanes
whose manifests name different bots. A finished run leaves results.jsonl (one line per board, sorted by deal
index), summary.json (as scripts/gen8_match.py writes it) and lanes.json (ranges, units, seconds) in --out, and
each lane's own folder as lane-<k>/. Nothing here touches another session's units, namespaces or folders: all
names start with g9 (units g9-ben-<k> and g9-lane-<k>, namespaces g9ben-<k>).

BEN is lorserker/ben at the commit in configs/ben-gen5-16.provenance.json (its models come with that checkout), with
the packages of configs/ben-round5-runtime-requirements.txt; `install` checks every model file against the provenance
hashes. Each server runs exactly as g7's arena lanes run it (lane.sh on transfer/ben-lanes-azure-20261112): from BEN's
root, `src/gameapi.py --config CONF --host 127.0.0.1 --port 8087 --record false`, restarted if it fails. CONF is the
capsule's own `assets/ben-16.conf` when --source has one (the config the capsule's `ben` bot was pinned with), else
configs/ben-gen5-16.conf; both bid neural only (use_bba and consult_bba are False, so the BBA engine is never called).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "configs" / "ben-gen5-16.provenance.json"
CONF = ROOT / "configs" / "ben-gen5-16.conf"
REQUIREMENTS = ROOT / "configs" / "ben-round5-runtime-requirements.txt"
PORT = 8087
THREADS = dict(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TF_NUM_INTRAOP_THREADS="1",
               TF_NUM_INTEROP_THREADS="1", TF_CPP_MIN_LOG_LEVEL="3")
DRY = False  # --dry-run prints the commands instead of running them


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    if DRY:
        print("+ " + " ".join(shlex.quote(c) for c in cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, check=check, text=True, capture_output=capture)


def ns(k: int) -> str:
    return f"g9ben-{k}"


def split(first: int, deals: int, lanes: int) -> list[tuple[int, int]]:
    """Contiguous, disjoint (first, count) ranges covering [first, first + deals), sizes differing by at most one."""
    if lanes < 1 or deals < lanes:
        raise SystemExit(f"need at least one deal per lane ({deals} deals, {lanes} lanes)")
    base, extra = divmod(deals, lanes)
    out, at = [], first
    for k in range(lanes):
        n = base + (1 if k < extra else 0)
        out.append((at, n))
        at += n
    return out


def unit_cmd(unit: str, k: int, workdir: Path, argv: list[str], env: dict, restart: bool = False) -> list[str]:
    cmd = ["sudo", "systemd-run", f"--unit={unit}", f"--uid={getpass.getuser()}", f"--working-directory={workdir}",
           f"--property=NetworkNamespacePath=/run/netns/{ns(k)}", "--property=KillMode=mixed", "--collect"]
    if restart:
        cmd += ["--property=Restart=on-failure", "--property=RestartSec=10"]
    for key, value in sorted(env.items()):
        cmd.append(f"--setenv={key}={value}")
    return cmd + ["--"] + argv


def active(unit: str) -> bool:
    if DRY:
        return False
    return subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0


# ---------------------------------------------------------------- install

def install(ben: Path, venv: Path) -> None:
    prov = json.loads(PROVENANCE.read_text())
    commit = prov["source_commit"]
    if not (ben / ".git").exists():  # only the pinned commit, as g7's ben-install does (2.9 GB with its models)
        run(["git", "init", "-q", str(ben)])
        run(["git", "-C", str(ben), "remote", "add", "origin", "https://github.com/lorserker/ben"])
    head = subprocess.run(["git", "-C", str(ben), "rev-parse", "-q", "--verify", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != commit:
        run(["git", "-C", str(ben), "fetch", "-q", "--depth", "1", "origin", commit])
        run(["git", "-C", str(ben), "checkout", "-q", "FETCH_HEAD"])
    if not (venv / "bin" / "python").exists():
        run([sys.executable, "-m", "venv", str(venv)])
    run([str(venv / "bin" / "python"), "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS)])
    import hashlib
    bad = []
    for name, m in prov["model_sha256"].items():
        path = ben / m["path"]  # relative to BEN's root, where gameapi runs (bridge_harness/loop_runtime.py)
        if DRY:
            continue
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != m["sha256"]:
            bad.append(f"{name} ({m['path']})")
    if bad:
        raise SystemExit("models missing or not matching configs/ben-gen5-16.provenance.json: " + ", ".join(bad))
    print(f"BEN at {commit[:9]} in {ben}, packages in {venv}, {len(prov['model_sha256'])} models checked")


# ---------------------------------------------------------------- lanes

def conf_for(source: str | None) -> Path:
    if source:
        c = Path(source).expanduser() / "assets" / "ben-16.conf"
        if c.exists() or DRY:
            return c
    return CONF


def up(lanes: int, ben: Path, venv: Path, conf: Path, wait: float = 600) -> None:
    env = dict(THREADS, HOME=str(Path.home()), PYTHONUNBUFFERED="1", XDG_CACHE_HOME=str(ben.parent / "ben-cache"))
    for k in range(1, lanes + 1):
        if not DRY and Path(f"/run/netns/{ns(k)}").exists() and active(f"g9-ben-{k}"):
            print(f"lane {k}: BEN already up")
            continue
        run(["sudo", "ip", "netns", "add", ns(k)], check=False)
        run(["sudo", "ip", "-n", ns(k), "link", "set", "lo", "up"])
        # as bridge_harness/loop_runtime.managed_ben starts it: from BEN's root, model paths relative to it
        argv = [str(venv / "bin" / "python"), "src/gameapi.py", "--config", str(conf), "--host", "127.0.0.1",
                "--port", str(PORT), "--record", "false"]
        run(unit_cmd(f"g9-ben-{k}", k, ben, argv, env, restart=True))
    deadline = time.time() + wait
    for k in range(1, lanes + 1):
        while not DRY:
            probe = subprocess.run(["sudo", "ip", "netns", "exec", ns(k), sys.executable, "-c",  # a TCP connect, as lane.sh waits
                                    f"import socket;socket.create_connection(('127.0.0.1',{PORT}),timeout=2).close()"],
                                   capture_output=True)
            if probe.returncode == 0:
                break
            if not active(f"g9-ben-{k}"):
                raise SystemExit(f"lane {k}: BEN exited; journalctl -u g9-ben-{k} -n 50")
            if time.time() > deadline:
                raise SystemExit(f"lane {k}: BEN not ready after {wait:.0f} s")
            time.sleep(2)
        print(f"lane {k}: " + ("(dry run) would wait for BEN" if DRY else "BEN ready") + f" in {ns(k)} at 127.0.0.1:{PORT}")


def play(a, lanes: int) -> list[dict]:
    out = Path(a.out).expanduser().resolve()
    ranges = split(a.first, a.deals, lanes)
    plan = []
    for k, (first, count) in enumerate(ranges, 1):
        lane_out = out / f"lane-{k}"
        argv = [sys.executable if not a.python else a.python, "scripts/gen9_match.py", "--source", str(Path(a.source).expanduser()),
                "--pair", a.pair, "--deals", str(count), "--first", str(first), "--seed", str(a.seed), "--workers", "1",
                "--out", str(lane_out)]
        if a.bots:
            argv += ["--bots", a.bots]
        if a.episodes:
            argv.append("--episodes")
        env = dict(THREADS, BRIDGE_DDS_CACHE=str(out / f"lane-{k}.dds.sqlite"), PYTHONUNBUFFERED="1")
        unit = f"g9-lane-{k}"
        if not DRY:
            lane_out.mkdir(parents=True, exist_ok=True)
        run(unit_cmd(unit, k, ROOT, argv, env))
        plan.append(dict(lane=k, first=first, deals=count, unit=unit, out=str(lane_out), started=time.time()))
    if not DRY:
        out.mkdir(parents=True, exist_ok=True)
        (out / "lanes.json").write_text(json.dumps(plan, indent=1) + "\n")
    peaks = {}
    while not DRY and any(active(p["unit"]) for p in plan):
        for r in measure(lanes):  # units vanish when they exit (--collect), so keep the peaks while they run
            if r["peak_mb"] is not None:
                peaks[r["unit"]] = max(peaks.get(r["unit"], 0), r["peak_mb"])
        for p in plan:
            if "seconds" not in p and not active(p["unit"]):
                p["seconds"] = round(time.time() - p["started"])
        time.sleep(15)
    for p in plan:
        p.setdefault("seconds", round(time.time() - p["started"]))
        p["peak_mb"] = peaks.get(p["unit"])
        p["ben_peak_mb"] = peaks.get(f"g9-ben-{p['lane']}")
        res = Path(p["out"]) / "results.jsonl"
        p["boards"] = sum(1 for l in res.read_text().splitlines() if l.strip()) if res.exists() else 0
        if not DRY and p["boards"] < p["deals"]:
            print(f"lane {p['lane']}: {p['boards']} of {p['deals']} boards; journalctl -u {p['unit']} has the reason", file=sys.stderr)
    if not DRY:
        (out / "lanes.json").write_text(json.dumps(plan, indent=1) + "\n")
    return plan


def merge(out: Path) -> dict:
    """Join the lanes' results into one file and one summary; refuse lanes that played different bots or deals."""
    out = Path(out).expanduser()
    lanes = sorted(out.glob("lane-*/results.jsonl"))
    if not lanes:
        raise SystemExit(f"no lane-*/results.jsonl under {out}")
    identities, seeds, rows, seen = set(), set(), [], set()
    pair = None
    for res in lanes:
        man = json.loads((res.parent / "manifest.json").read_text())
        identities.add(json.dumps({k: v.get("identity") for k, v in sorted(man["bots"].items())}))
        seeds.add(man.get("seed"))
        pair = man.get("pair_schedule", [pair])[0]
        for line in res.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r["index"] in seen:
                    raise SystemExit(f"deal {r['index']} was played in two lanes")
                seen.add(r["index"])
                rows.append(r)
    if len(identities) != 1:
        raise SystemExit("the lanes' manifests name different bots; they cannot be merged")
    if len(seeds) != 1:
        raise SystemExit(f"the lanes used different seeds {sorted(seeds)}")
    rows.sort(key=lambda r: r["index"])
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    a, b = pair.split("~")
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen8_match", ROOT / "scripts" / "gen8_match.py")
    g8 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g8)
    summary = dict(g8.summary(rows, a, b), lanes=len(lanes), seed=seeds.pop())
    plan_file = out / "lanes.json"
    if plan_file.exists():
        plan = json.loads(plan_file.read_text())
        wall = max(p.get("seconds", 0) for p in plan)
        if wall:
            summary["boards_per_hour"] = round(len(rows) / wall * 3600)
            summary["wall_seconds"] = wall
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def measure(lanes: int) -> list[dict]:
    rows = []
    for k in range(1, lanes + 1):
        for unit in (f"g9-ben-{k}", f"g9-lane-{k}"):
            r = subprocess.run(["systemctl", "show", unit, "--property=MemoryCurrent,MemoryPeak,ActiveState"], capture_output=True, text=True)
            props = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
            mb = lambda v: round(int(v) / 2**20) if v and v.isdigit() else None
            rows.append(dict(unit=unit, state=props.get("ActiveState"), memory_mb=mb(props.get("MemoryCurrent")), peak_mb=mb(props.get("MemoryPeak"))))
    return rows


def down(lanes: int) -> None:
    for k in range(1, lanes + 1):
        for unit in (f"g9-lane-{k}", f"g9-ben-{k}"):
            run(["sudo", "systemctl", "stop", unit], check=False)
        run(["sudo", "ip", "netns", "delete", ns(k)], check=False)


def main() -> int:
    global DRY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the commands instead of running them")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("install")
    p.add_argument("--ben", type=Path, default=Path("~/work/g9/ben").expanduser())
    p.add_argument("--venv", type=Path, default=Path("~/work/g9/ben-venv").expanduser())
    for name in ("up", "run", "status", "measure", "down"):
        p = sub.add_parser(name)
        p.add_argument("--lanes", type=int, default=2)
        if name in ("up", "run"):
            p.add_argument("--ben", type=Path, default=Path("~/work/g9/ben").expanduser())
            p.add_argument("--venv", type=Path, default=Path("~/work/g9/ben-venv").expanduser())
            p.add_argument("--conf", type=Path, help="BEN config (default: the capsule's assets/ben-16.conf, else configs/ben-gen5-16.conf)")
        if name == "run":
            p.add_argument("--pair", required=True)
            p.add_argument("--deals", type=int, required=True)
            p.add_argument("--first", type=int, default=0)
            p.add_argument("--seed", type=int, required=True)
            p.add_argument("--source", required=True)
            p.add_argument("--bots")
            p.add_argument("--out", required=True)
            p.add_argument("--episodes", action="store_true")
            p.add_argument("--python", help="interpreter for the match workers (default: this one)")
            p.add_argument("--keep-up", action="store_true", help="leave the BEN servers running afterwards")
    p = sub.add_parser("merge")
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    DRY = a.dry_run
    if a.cmd == "install":
        install(a.ben.expanduser(), a.venv.expanduser())
    elif a.cmd == "up":
        up(a.lanes, a.ben.expanduser(), a.venv.expanduser(), a.conf or CONF)
    elif a.cmd == "run":
        split(a.first, a.deals, a.lanes)  # fail early on a bad split
        up(a.lanes, a.ben.expanduser(), a.venv.expanduser(), a.conf or conf_for(a.source))
        play(a, a.lanes)
        if not DRY:
            print(json.dumps(merge(Path(a.out)), indent=1))
        if not a.keep_up:
            down(a.lanes)
    elif a.cmd == "merge":
        print(json.dumps(merge(Path(a.out)), indent=1))
    elif a.cmd in ("status", "measure"):
        for r in measure(a.lanes):
            print(f"{r['unit']:12} {r['state'] or '':10} now {r['memory_mb']} MB, peak {r['peak_mb']} MB")
    elif a.cmd == "down":
        down(a.lanes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
