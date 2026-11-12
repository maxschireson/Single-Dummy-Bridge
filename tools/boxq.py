#!/usr/bin/env python3
"""boxq: the Gen 9 box job queue. Jobs are files on the team channel; a box pulls them, runs them, reports back.

A lead submits a job with `workq.py job submit FILE` (or by any change that writes `boxq/<box>/<id>.json` on
team/gen9). The box's `boxq.py serve` (a systemd unit, `g9-boxq`) fetches the channel every 30 seconds and:

- runs the waiting jobs that fit its cores, highest priority first (1 is highest), then by submission time; a job
  that does not fit is passed over for smaller ones, so cores do not sit idle while anything waits;
- stops a running job of lower priority when a higher one needs its cores, if that job is `preemptible` (resumable:
  scripts/gen8_match.py and gen9_match.py skip boards already in results.jsonl); it is restarted when cores free up;
- counts each job's boards from its results files, with boards an hour over the last 30 minutes and the expected
  finish, and writes `boxq/<box>/status.json` to the channel (STATUS.md shows it) when something changes and at
  least every 5 minutes;
- pushes each job's result files to `transfer/gen9-<id>-<box>-<yyyymmdd>` every 10 minutes and when it ends.

A job runs as the unit `g9-job-<id>`, in a checkout of its `source` commit under ~/work/g9/src/, with one thread per
process and the solver cache off (BRIDGE_DDS_CACHE empty) unless its `env` says otherwise. Its exit code is written to
`<out>/.exit`. In `argv`, `{python}`, `{src}`, `{out}` and `{work}` are replaced by the box's Python, the checkout, the
job's output folder, ~/work/g9 and the home folder
(the Gen 7 capture capsule is at {home}/work/capsule-gen7-capture/recovery on the Azure boxes).

Job file (JSON):

    {"id": "e9-0", "box": "azure4", "experiment": "E9-0", "owner": "g9", "priority": 1, "cores": 4,
     "source": {"branch": "feature/gen9", "commit": "1a89446"},
     "argv": ["{python}", "scripts/gen9_match.py", "--source", "{work}/capsule/recovery", "--bots", "configs/gen9-proto-bots.json",
              "--pair", "9t1-32~8p-32", "--deals", "800", "--seed", "91", "--workers", "4", "--out", "{out}"],
     "progress": {"results": "results.jsonl", "target": 800},
     "preemptible": true, "publish": ["results.jsonl", "summary.json", "manifest.json"], "state": "queued"}

`state` is `queued` or `cancelled` (the owner or g9 cancels with `workq.py job cancel ID`); everything else the box
reports in its status file. Commands on the box:

    python3 boxq.py serve --box azure4 [--cores 8]      the loop (normally run by the g9-boxq unit)
    python3 boxq.py install --box azure4                 write and start the g9-boxq unit
    python3 boxq.py once --box azure4                    one pass of the loop, for checking by hand
"""
from __future__ import annotations

import argparse
import fnmatch
import getpass
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("workq", HERE / "workq.py")
wq = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("workq", wq)
_spec.loader.exec_module(wq)

JOB_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
FINAL = ("done", "failed", "cancelled")
DEFAULT_ENV = dict(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TF_NUM_INTRAOP_THREADS="1",
                   TF_NUM_INTEROP_THREADS="1", TF_CPP_MIN_LOG_LEVEL="3", PYTHONUNBUFFERED="1", BRIDGE_DDS_CACHE="")
RATE_WINDOW = timedelta(minutes=30)
STATUS_EVERY = timedelta(minutes=5)
PUBLISH_EVERY = timedelta(minutes=10)
MAX_RESTARTS = 2


def utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- jobs

def validate(job: dict, box: str | None = None, cores: int | None = None) -> dict:
    def need(cond, why):
        if not cond:
            raise ValueError(f"job {job.get('id')!r}: {why}")
    need(isinstance(job.get("id"), str) and JOB_RE.match(job["id"]), "id is lower case letters, digits and dashes")
    need(isinstance(job.get("box"), str) and (box is None or job["box"] == box), f"box is {box}")
    need(isinstance(job.get("owner"), str) and wq.NAME_RE.match(job["owner"]), "owner is a roster name")
    need(isinstance(job.get("priority"), int) and 1 <= job["priority"] <= 99, "priority is an integer from 1 (highest) to 99")
    need(isinstance(job.get("cores"), int) and 1 <= job["cores"] <= (cores or 64), f"cores is an integer from 1 to {cores or 64}")
    src = job.get("source") or {}
    need(isinstance(src.get("branch"), str) and isinstance(src.get("commit"), str) and re.match(r"^[0-9a-f]{7,40}$", src["commit"]),
         "source has a branch and a commit (7 to 40 hex digits)")
    need(isinstance(job.get("argv"), list) and job["argv"] and all(isinstance(x, str) for x in job["argv"]), "argv is a list of strings")
    prog = job.get("progress") or {}
    need(isinstance(prog.get("results"), str) and isinstance(prog.get("target"), int) and prog["target"] > 0,
         "progress has results (a file or glob under the job's folder) and target (boards)")
    need(job.get("state", "queued") in ("queued", "cancelled"), "state is queued or cancelled")
    need(isinstance(job.get("preemptible", True), bool), "preemptible is true or false")
    need(isinstance(job.get("env", {}), dict), "env is an object")
    need(isinstance(job.get("publish", []), list), "publish is a list of file patterns")
    for key in ("experiment", "task"):
        if job.get(key):
            need(isinstance(job[key], str) and wq.ID_RE.match(job[key]), f"{key} is an id like E9-0 or G9-D6")
    return job


def plan(jobs: dict[str, dict], status: dict[str, dict], cores: int) -> tuple[list[str], list[str]]:
    """Which jobs to start and which to stop. Pure: jobs as submitted, status as the box last saw it."""
    running = {j for j, s in status.items() if s.get("state") == "running"}
    stop = [j for j in running if j not in jobs or jobs[j].get("state") == "cancelled"]
    live = {j: d for j, d in jobs.items() if d.get("state") != "cancelled" and status.get(j, {}).get("state") not in FINAL}
    desired, free = set(), cores
    for j in sorted(running - set(stop)):  # a job that cannot be resumed keeps its cores
        if not live.get(j, {}).get("preemptible", True):
            desired.add(j)
            free -= live[j]["cores"]
    order = sorted((j for j in live if j not in desired), key=lambda j: (live[j]["priority"], live[j].get("submitted", ""), j))
    for j in order:
        if live[j]["cores"] <= free:
            desired.add(j)
            free -= live[j]["cores"]
    stop += [j for j in running if j not in desired and j not in stop]
    start = [j for j in order if j in desired and j not in running]
    # start only into cores that are free now: a job waits until the jobs stopped for it have gone
    busy = sum(jobs[j]["cores"] for j in running if j in jobs)  # a job being stopped holds its cores until it has gone
    really, free_now = [], cores - busy
    for j in start:
        if live[j]["cores"] <= free_now:
            really.append(j)
            free_now -= live[j]["cores"]
    return really, sorted(stop)


def count_boards(out: Path, pattern: str) -> int:
    n = 0
    for f in sorted(out.glob(pattern)):
        try:
            n += sum(1 for line in f.read_text(errors="replace").splitlines() if line.strip())
        except OSError:
            pass
    return n


def rate_and_eta(samples: list[list], boards: int, target: int, now: datetime) -> tuple[float | None, str | None]:
    """Boards an hour over the last 30 minutes of running, and the finish that rate gives."""
    recent = [s for s in samples if now - parse(s[0]) <= RATE_WINDOW]
    if len(recent) < 2:
        return None, None
    (t0, b0), (t1, b1) = recent[0], recent[-1]
    hours = (parse(t1) - parse(t0)).total_seconds() / 3600
    if hours <= 0 or b1 <= b0:
        return (0.0 if hours > 0 else None), None
    rate = (b1 - b0) / hours
    return round(rate, 1), stamp(now + timedelta(hours=max(target - boards, 0) / rate))


# ---------------------------------------------------------------- running units

class Systemd:
    def start(self, jid: str, workdir: Path, argv: list[str], env: dict, exit_file: Path) -> None:
        exit_file.unlink(missing_ok=True)
        script = " ".join(_q(a) for a in argv) + f"; echo $? > {_q(str(exit_file))}"
        cmd = ["sudo", "systemd-run", "--quiet", f"--unit=g9-job-{jid}", f"--uid={getpass.getuser()}", f"--working-directory={workdir}",
               "--collect", "--property=TimeoutStopSec=120"]  # stop signals every process of the job, workers included
        cmd += [f"--setenv={k}={v}" for k, v in sorted(env.items())]
        subprocess.run(cmd + ["--", "/bin/bash", "-c", script], check=True)

    def active(self, jid: str) -> bool:
        return subprocess.run(["systemctl", "is-active", "--quiet", f"g9-job-{jid}"]).returncode == 0

    def stop(self, jid: str) -> None:
        subprocess.run(["sudo", "systemctl", "stop", f"g9-job-{jid}"], check=False)


class Local:
    """For tests and dry runs: the same contract with plain processes."""
    def __init__(self):
        self.procs = {}

    def start(self, jid, workdir, argv, env, exit_file):
        exit_file.unlink(missing_ok=True)
        script = " ".join(_q(a) for a in argv) + f"; echo $? > {_q(str(exit_file))}"
        self.procs[jid] = subprocess.Popen(["/bin/bash", "-c", script], cwd=workdir, env=dict(os.environ, **env), start_new_session=True)

    def active(self, jid):
        p = self.procs.get(jid)
        return p is not None and p.poll() is None

    def stop(self, jid):
        p = self.procs.get(jid)
        if p and p.poll() is None:
            os.killpg(p.pid, 15)
            p.wait(timeout=30)


def _q(s: str) -> str:
    import shlex
    return shlex.quote(s)


# ---------------------------------------------------------------- the box

class Box:
    def __init__(self, box: str, cores: int, work: Path, executor=None, python: str | None = None,
                 repo_url: str | None = None, channel: str | None = None, clock=utc, source_url: str | None = None):
        self.box, self.cores, self.work, self.clock = box, cores, work, clock
        self.exec = executor or Systemd()
        self.python = python or (str(Path.home() / "work" / "venv" / "bin" / "python")
                                 if (Path.home() / "work" / "venv" / "bin" / "python").exists() else sys.executable)
        self.url = repo_url or os.environ.get("WORKQ_REPO", wq.DEFAULT_REPO)
        self.source_url = source_url or self.url
        self.lg = wq.Ledger(self.url, channel, agent=box)
        self.lg.clock = lambda: self.clock().replace(second=0)
        self.state_file = work / "boxq" / "status.json"
        self.status = json.loads(self.state_file.read_text()) if self.state_file.exists() else dict(box=box, cores=cores, jobs={})
        self.last_write = None

    # sources
    def source(self, job: dict) -> Path:
        commit = job["source"]["commit"]
        dest = self.work / "src" / commit[:12]
        if not (dest / ".git").exists() and not (dest / "bridge_harness").exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "-q", str(dest)], check=True)
            subprocess.run(["git", "-C", str(dest), "remote", "add", "origin", self.source_url], check=True)
            subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "50", "origin", job["source"]["branch"]], check=True)
            r = subprocess.run(["git", "-C", str(dest), "checkout", "-q", commit], capture_output=True, text=True)
            if r.returncode != 0:  # a commit older than 50 back on its branch
                subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", "origin", commit], check=True)
                subprocess.run(["git", "-C", str(dest), "checkout", "-q", commit], check=True)
        self.prepare(dest)
        return dest

    def prepare(self, dest: Path) -> None:
        """Once per checkout: build DDS, and rebuild the nets git keeps as parts (bill, 09:03: a fresh checkout has
        models/bidding/*/bidder.keras only as parts). Uses scripts/run_tests.py's idempotent restore when the
        checkout has it, else runs every restore script."""
        marker = dest / ".boxq-prepared"
        if marker.exists():
            return
        lib = dest / "bridge_harness" / "libbridge_dds.so"
        if (dest / "scripts" / "build_dds.py").exists() and not lib.exists():
            subprocess.run([self.python, "scripts/build_dds.py"], cwd=dest, check=True, capture_output=True)
        rt = dest / "scripts" / "run_tests.py"
        if rt.exists() and "def restore_models" in rt.read_text(errors="replace"):
            code = ("import importlib.util, json; s = importlib.util.spec_from_file_location('rt', 'scripts/run_tests.py'); "
                    "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); r = m.restore_models(); "
                    "bad = [x['script'] for x in r if not x['ok']]; print(json.dumps(bad)); raise SystemExit(1 if bad else 0)")
            subprocess.run([self.python, "-c", code], cwd=dest, check=True, capture_output=True)
        else:
            for script in sorted(dest.glob("models/**/restore*.py")):
                subprocess.run([self.python, "-I", script.name], cwd=script.parent, check=True, capture_output=True)
        marker.write_text(stamp(self.clock()) + "\n")

    def out_dir(self, job: dict) -> Path:
        return self.work / "runs" / job["id"]

    def argv(self, job: dict, src: Path) -> list[str]:
        subs = {"{python}": self.python, "{src}": str(src), "{out}": str(self.out_dir(job)), "{work}": str(self.work), "{home}": str(Path.home())}
        out = []
        for a in job["argv"]:
            for k, v in subs.items():
                a = a.replace(k, v)
            out.append(a)
        return out

    # one pass
    def jobs(self) -> tuple[dict, list[str]]:
        st = self.lg.snapshot()
        jobs, bad = {}, []
        for p in st.paths(f"boxq/{self.box}/"):
            if not p.endswith(".json") or p.endswith("/status.json"):
                continue
            try:
                j = validate(json.loads(st.get(p)), self.box, self.cores)
                jobs[j["id"]] = j
            except (ValueError, json.JSONDecodeError) as e:
                bad.append(f"{p}: {e}")
        return jobs, bad

    def once(self) -> dict:
        now = self.clock()
        jobs, bad = self.jobs()
        S = self.status.setdefault("jobs", {})
        changed = []
        for jid, j in jobs.items():
            s = S.setdefault(jid, dict(state="waiting", owner=j["owner"], experiment=j.get("experiment") or j.get("task"), boards=0,
                                       target=j["progress"]["target"], restarts=0, samples=[], submitted=j.get("submitted")))
            s["target"], s["priority"], s["cores"] = j["progress"]["target"], j["priority"], j["cores"]
            if j.get("state") == "cancelled" and s["state"] in ("waiting", "paused"):
                s["state"] = "cancelled"; changed.append((jid, "cancelled"))
        # what finished since the last pass
        for jid, s in S.items():
            if s["state"] == "running" and not self.exec.active(jid):
                j = jobs.get(jid)
                ef = (self.out_dir(j) if j else self.work / "runs" / jid) / ".exit"
                code = int(ef.read_text().strip() or -1) if ef.exists() else None
                s["boards"] = count_boards(self.out_dir(j), j["progress"]["results"]) if j else s["boards"]
                if s.get("stopping"):
                    s["state"] = "cancelled" if (not j or j.get("state") == "cancelled") else "paused"
                elif code == 0:
                    s["state"] = "done"
                    s["short"] = s["boards"] < s["target"]
                elif s["restarts"] < MAX_RESTARTS:
                    s["restarts"] += 1; s["state"] = "waiting"; s["last_exit"] = code
                else:
                    s["state"] = "failed"; s["last_exit"] = code
                s.pop("stopping", None)
                s["ended"] = stamp(now)
                changed.append((jid, s["state"]))
                if s["state"] in ("done", "failed", "cancelled") and j and j.get("publish"):
                    self.publish(j, s, now)
        start, stop = plan(jobs, S, self.cores)
        for jid in stop:
            if S[jid]["state"] == "running":
                self.exec.stop(jid)
                S[jid]["stopping"] = True
                changed.append((jid, "stopping"))
        for jid in start:
            j = jobs[jid]
            try:
                src = self.source(j)
            except subprocess.CalledProcessError as e:
                S[jid].update(state="failed", detail=f"source checkout failed: {e}")
                changed.append((jid, "failed")); continue
            out = self.out_dir(j); out.mkdir(parents=True, exist_ok=True)
            env = dict(DEFAULT_ENV, HOME=str(Path.home()), **{k: str(v) for k, v in j.get("env", {}).items()})
            self.exec.start(jid, src, self.argv(j, src), env, out / ".exit")
            S[jid].update(state="running", started=S[jid].get("started") or stamp(now), resumed=stamp(now), source=str(src))
            changed.append((jid, "running"))
        # progress
        for jid, s in S.items():
            j = jobs.get(jid)
            if s["state"] == "running" and j:
                s["boards"] = count_boards(self.out_dir(j), j["progress"]["results"])
                s["samples"] = [x for x in s.get("samples", []) if now - parse(x[0]) <= RATE_WINDOW] + [[stamp(now), s["boards"]]]
                s["rate_per_hour"], s["eta"] = rate_and_eta(s["samples"], s["boards"], s["target"], now)
                if j.get("publish") and (not s.get("published_at") or now - parse(s["published_at"]) >= PUBLISH_EVERY):
                    self.publish(j, s, now)
        self.status.update(box=self.box, cores=self.cores, updated=stamp(now), bad_jobs=bad,
                           cores_busy=sum(s["cores"] for s in S.values() if s["state"] == "running" and "cores" in s))
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.status, indent=1) + "\n")
        if changed or not self.last_write or now - self.last_write >= STATUS_EVERY:
            self.write_status(changed)
            self.last_write = now
        return self.status

    def write_status(self, changed: list) -> None:
        snapshot = json.loads(json.dumps(self.status))
        for s in snapshot.get("jobs", {}).values():
            s.pop("samples", None)

        def fn(st):
            st.save(f"boxq/{self.box}/status.json", snapshot)
            for jid, state in changed:
                st.event("job", f"{self.box}/{jid}", state)
        try:
            self.lg.mutate(f"boxq: {self.box} status" + (f" ({', '.join(f'{j} {s}' for j, s in changed)})" if changed else ""), fn)
        except SystemExit as e:  # the channel unreachable is not a reason to stop running jobs
            print(f"status not written: {e}", file=sys.stderr)

    def publish(self, job: dict, s: dict, now: datetime) -> None:
        out = self.out_dir(job)
        files = {}
        for pat in job.get("publish", []):
            for f in sorted(out.rglob("*")):
                rel = str(f.relative_to(out))
                if f.is_file() and fnmatch.fnmatch(rel, pat) and f.stat().st_size < 90 * 2**20:
                    files[rel] = f.read_bytes()
        if not files:
            return
        day = (s.get("started") or stamp(now))[:10].replace("-", "")
        branch = f"transfer/gen9-{job['id']}-{self.box}-{day}"
        store = wq.Store(self.url, branch)
        readme = (f"# {job['id']} on {self.box}\n\nResults of box job `{job['id']}` ({job.get('experiment') or job.get('task') or 'no experiment'}, owner "
                  f"{job['owner']}), published by tools/boxq.py on team/gen9. Source `{job['source']['branch']}` at "
                  f"`{job['source']['commit']}`. A transfer branch: never merged into source.\n\n"
                  f"Last published {stamp(now)}: {s.get('boards')} of {s.get('target')} boards, state {s.get('state')}.\n")
        files["README.md"] = readme.encode()
        files["job.json"] = (json.dumps(job, indent=1) + "\n").encode()
        for attempt in range(6):
            tip = store.fetch()
            old = store.read(tip)
            changes = {p: b for p, b in files.items() if old.get(p) != b}
            if not changes:
                break
            sha = store.commit(tip, changes, f"{self.box}: {job['id']} results, {s.get('boards')} boards\n", f"{self.box} (boxq)")
            if store.push(sha):
                s.update(published_at=stamp(now), published=f"{branch}@{sha[:9]}")
                break
            time.sleep(1 + attempt)

    def serve(self, interval: float = 30) -> None:
        while True:
            try:
                self.once()
            except Exception as e:  # keep serving; the next pass retries
                print(f"{stamp(self.clock())} pass failed: {e!r}", file=sys.stderr, flush=True)
            time.sleep(interval)


def box_git_env() -> None:
    """On a box, reach GitHub the way the boxctl agent does (~/.boxctl/config.json)."""
    cfg = Path.home() / ".boxctl" / "config.json"
    if cfg.exists():
        c = json.loads(cfg.read_text())
        os.environ.setdefault("WORKQ_REPO", c.get("repo_url", wq.DEFAULT_REPO))
        if c.get("ssh_key"):
            key = os.path.expanduser(c["ssh_key"])
            os.environ.setdefault("GIT_SSH_COMMAND", f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("serve", "once", "install"):
        p = sub.add_parser(name)
        p.add_argument("--box", required=True)
        p.add_argument("--cores", type=int, default=os.cpu_count())
        p.add_argument("--work", type=Path, default=Path.home() / "work" / "g9")
    a = ap.parse_args()
    box_git_env()
    if a.cmd == "install":
        me = Path(__file__).resolve()
        subprocess.run(["sudo", "systemd-run", "--quiet", "--unit=g9-boxq", f"--uid={getpass.getuser()}", f"--working-directory={me.parent}",
                        "--property=Restart=always", "--property=RestartSec=30", f"--setenv=HOME={Path.home()}",
                        f"--setenv=WORKQ_REPO={os.environ.get('WORKQ_REPO', wq.DEFAULT_REPO)}",
                        f"--setenv=GIT_SSH_COMMAND={os.environ.get('GIT_SSH_COMMAND', '')}",
                        f"--setenv=WORKQ_TRAILERS={os.environ.get('WORKQ_TRAILERS', '')}", "--setenv=WORKQ_ISSUE=0",
                        "--", sys.executable, "-u", str(me), "serve", "--box", a.box, "--cores", str(a.cores), "--work", str(a.work)], check=True)
        print("g9-boxq started")
        return 0
    b = Box(a.box, a.cores, a.work)
    if a.cmd == "once":
        print(json.dumps(b.once(), indent=1))
        return 0
    b.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
