#!/usr/bin/env python3
"""boxctl agent: run shell commands queued on a GitHub branch and publish the results.

The agent polls ``refs/heads/box/<box>/control`` for files ``commands/<id>.sh``.
Each new command runs once, in id order, as the agent's user. After each command,
and at least every ``heartbeat_s`` seconds, the agent force-pushes a one-commit
snapshot to ``refs/heads/box/<box>/status`` holding ``heartbeat.json`` and
``results/<id>.json`` for the most recent commands.

Everything on the status branch is as visible as the repository, so commands must
not print secrets. Protocol, setup and limits: docs/boxctl.md.

Standard library only; needs git, bash and Python 3.8+.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0"
ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
BOX_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
TIMEOUT_RE = re.compile(rb"^#\s*boxctl:\s*timeout\s*=\s*([0-9]+)\s*$", re.M)
DEFAULT_TIMEOUT_S = 900
MAX_TIMEOUT_S = 6 * 3600
TAIL_BYTES = 16000
KEEP_RESULTS = 300
KILL_GRACE_S = 10


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"{utcnow()} {msg}", flush=True)


class GitError(RuntimeError):
    pass


class Agent:
    def __init__(self, cfg: dict):
        self.box = str(cfg["box"])
        if not BOX_RE.match(self.box):
            raise SystemExit(f"invalid box name {self.box!r}: lowercase letters, digits and hyphens")
        self.remote = str(cfg["repo"])
        self.poll_s = float(cfg.get("poll_s", 30))
        self.heartbeat_s = float(cfg.get("heartbeat_s", 300))
        self.state_dir = Path(os.path.expanduser(cfg.get("state_dir", "~/.boxctl")))
        self.workdir = Path(os.path.expanduser(cfg.get("workdir", "~")))
        self.ssh_key = cfg.get("ssh_key")
        self.git_dir = self.state_dir / "repo.git"
        self.results_dir = self.state_dir / "results"
        self.logs_dir = self.state_dir / "logs"
        self.scripts_dir = self.state_dir / "scripts"
        self.state_path = self.state_dir / "state.json"
        self.control_ref = f"refs/heads/box/{self.box}/control"
        self.status_ref = f"refs/heads/box/{self.box}/status"
        self.local_control = "refs/remotes/origin/control"
        self.stop = False
        self.dirty = True
        self.started_at = utcnow()
        self.last_fetch: dict | None = None
        self.last_push: dict | None = None
        self.last_publish_mono = 0.0
        self.pending: list[str] = []
        self.state: dict = {}
        self.done: set[str] = set()
        self._lock = None

    # ----------------------------------------------------------------- git
    def git(self, *args: str, input: bytes | None = None, check: bool = True,
            timeout: float = 120) -> subprocess.CompletedProcess:
        ident = f"boxctl {self.box}"
        email = f"boxctl@{self.box}.invalid"
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0",
                   GIT_AUTHOR_NAME=ident, GIT_AUTHOR_EMAIL=email,
                   GIT_COMMITTER_NAME=ident, GIT_COMMITTER_EMAIL=email)
        cmd = ["git", "--git-dir", str(self.git_dir), *args]
        try:
            r = subprocess.run(cmd, input=input, capture_output=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as e:
            raise GitError(f"git {args[0]} timed out after {timeout:g}s") from e
        if check and r.returncode != 0:
            err = r.stderr.decode(errors="replace").strip().splitlines()
            raise GitError(f"git {args[0]} failed: {err[-1] if err else r.returncode}")
        return r

    def hash_blob(self, data: bytes) -> str:
        return self.git("hash-object", "-w", "--stdin", input=data).stdout.decode().strip()

    def mktree(self, lines: list[str]) -> str:
        return self.git("mktree", input=("\n".join(lines) + "\n").encode()).stdout.decode().strip()

    # --------------------------------------------------------------- setup
    def setup(self) -> None:
        for d in (self.state_dir, self.results_dir, self.logs_dir, self.scripts_dir):
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)
        self._lock = open(self.state_dir / "agent.lock", "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(f"another boxctl agent is already running on {self.state_dir}")
        if not (self.git_dir / "HEAD").exists():
            subprocess.run(["git", "init", "--bare", "-q", str(self.git_dir)], check=True)
        self.git("config", "remote.origin.url", self.remote)
        if self.ssh_key:
            key = shlex.quote(os.path.expanduser(str(self.ssh_key)))
            self.git("config", "core.sshCommand",
                     f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
                     "-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20")
        self.load_state()
        self.recover_interrupted()

    def load_state(self) -> None:
        try:
            self.state = json.loads(self.state_path.read_text())
        except FileNotFoundError:
            self.state = {}
        self.state.setdefault("done", [])
        self.state.setdefault("started", [])
        self.done = set(self.state["done"])

    def save_state(self) -> None:
        # Never prune "done": a command id dropped from it would run again.
        self.state["done"] = sorted(self.done)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        os.replace(tmp, self.state_path)

    def recover_interrupted(self) -> None:
        """A command that was running when the agent stopped is reported, never re-run."""
        for cid in self.state.get("started", []):
            if cid in self.done:
                continue
            self.write_result(cid, {
                "received": None, "started": None, "finished": utcnow(), "duration_s": None,
                "exit_code": None, "timed_out": False, "interrupted": True,
                "note": "the agent stopped while this command ran; it may still be running "
                        "and will not be re-run",
            })
            self.done.add(cid)
            log(f"marked {cid} interrupted")
        self.state["started"] = []
        self.save_state()

    # ------------------------------------------------------------- control
    def fetch_control(self) -> str:
        r = self.git("fetch", "--quiet", "--no-tags", "--depth=1", "origin",
                     f"+{self.control_ref}:{self.local_control}", check=False, timeout=180)
        if r.returncode == 0:
            outcome = "ok"
        else:
            err = r.stderr.decode(errors="replace").strip()
            if "couldn't find remote ref" in err or "could not find remote ref" in err:
                self.git("update-ref", "-d", self.local_control, check=False)
                outcome = "no control branch yet"
            else:
                last = err.splitlines()[-1] if err else f"exit {r.returncode}"
                outcome = f"error: {last}"
        if outcome != (self.last_fetch or {}).get("outcome"):
            log(f"fetch {self.control_ref}: {outcome}")
        self.last_fetch = {"time": utcnow(), "outcome": outcome}
        return outcome

    def list_commands(self) -> list[str]:
        r = self.git("ls-tree", "--name-only", self.local_control, "commands/", check=False)
        if r.returncode != 0:
            return []
        ids = []
        for line in r.stdout.decode(errors="replace").splitlines():
            name = line.rsplit("/", 1)[-1]
            if name.endswith(".sh") and ID_RE.match(name[:-3]):
                ids.append(name[:-3])
        return sorted(ids)

    def read_script(self, cid: str) -> bytes:
        return self.git("cat-file", "blob", f"{self.local_control}:commands/{cid}.sh").stdout

    # ------------------------------------------------------------- execute
    def execute(self, cid: str) -> None:
        received = utcnow()
        script = self.read_script(cid)
        m = TIMEOUT_RE.search(script)
        timeout = min(int(m.group(1)), MAX_TIMEOUT_S) if m else DEFAULT_TIMEOUT_S
        path = self.scripts_dir / f"{cid}.sh"
        path.write_bytes(script)
        path.chmod(0o700)
        log_path = self.logs_dir / f"{cid}.log"
        self.state["started"] = [cid]
        self.save_state()
        env = dict(os.environ, BOXCTL_ID=cid, BOXCTL_BOX=self.box)
        env.setdefault("LANG", "C.UTF-8")
        log(f"running {cid} (timeout {timeout}s)")
        started, t0 = utcnow(), time.monotonic()
        timed_out = False
        with open(log_path, "wb") as out:
            p = subprocess.Popen(["bash", "-l", str(path)], stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=subprocess.STDOUT, cwd=str(self.workdir), env=env,
                                 start_new_session=True)
            while True:
                try:
                    rc = p.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if self.stop:
                    log(f"agent stopping while {cid} runs; it is left running")
                    return  # stays in "started"; reported as interrupted on restart
                if not timed_out and time.monotonic() - t0 > timeout:
                    timed_out = True
                    log(f"{cid} exceeded {timeout}s; terminating its process group")
                    self.kill_group(p)
                if time.monotonic() - self.last_publish_mono >= self.heartbeat_s:
                    self.publish(running=cid)
        duration = time.monotonic() - t0
        self.write_result(cid, {
            "received": received, "started": started, "finished": utcnow(),
            "duration_s": round(duration, 1), "exit_code": rc, "timed_out": timed_out,
            "timeout_s": timeout, "script_sha256": hashlib.sha256(script).hexdigest(),
        })
        self.done.add(cid)
        self.state["started"] = []
        self.save_state()
        log(f"finished {cid}: exit {rc}{' after timeout' if timed_out else ''} in {duration:.1f}s")

    @staticmethod
    def kill_group(p: subprocess.Popen) -> None:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            p.wait(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def write_result(self, cid: str, result: dict) -> None:
        log_path = self.logs_dir / f"{cid}.log"
        size = log_path.stat().st_size if log_path.exists() else 0
        tail = b""
        if size:
            with open(log_path, "rb") as f:
                f.seek(max(0, size - TAIL_BYTES))
                tail = f.read()
        text = tail.decode("utf-8", errors="replace")
        if size > len(tail):
            text = f"[... {size - len(tail)} earlier bytes omitted; full log on the box at {log_path} ...]\n" + text
        result.update({"id": cid, "box": self.box, "agent_version": VERSION,
                       "output_bytes": size, "output_tail": text})
        tmp = self.results_dir / f".{cid}.tmp"
        tmp.write_text(json.dumps(result, indent=1, sort_keys=True))
        os.replace(tmp, self.results_dir / f"{cid}.json")
        self.dirty = True

    # ------------------------------------------------------------- publish
    def heartbeat(self, running: str | None) -> dict:
        hb: dict = {
            "box": self.box, "agent_version": VERSION, "time": utcnow(),
            "agent_started": self.started_at, "hostname": socket.gethostname(),
            "running": running, "pending": list(self.pending),
            "last_done": max(self.done) if self.done else None,
            "last_fetch": self.last_fetch, "previous_push": self.last_push,
            "poll_s": self.poll_s, "heartbeat_s": self.heartbeat_s, "cpus": os.cpu_count(),
        }
        try:
            hb["load"] = [round(x, 2) for x in os.getloadavg()]
        except OSError:
            pass
        try:
            mem = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0]) // 1024
            hb["memory_mb"] = {k: mem.get(k) for k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
        except (OSError, ValueError):
            pass
        try:
            hb["uptime_s"] = int(float(Path("/proc/uptime").read_text().split()[0]))
        except (OSError, ValueError):
            pass
        disks = {}
        for label, p in (("root", "/"), ("home", str(Path.home()))):
            try:
                u = shutil.disk_usage(p)
                disks[label] = {"total_gb": round(u.total / 1e9, 1), "free_gb": round(u.free / 1e9, 1)}
            except OSError:
                pass
        hb["disk"] = disks
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    hb["os"] = line.split("=", 1)[1].strip('"')
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.lower().startswith("model name"):
                    hb["cpu_model"] = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
        # Process names only: full command lines can carry secrets and this file is public.
        try:
            out = subprocess.run(["ps", "-eo", "pid=,user=,pcpu=,pmem=,etimes=,comm=", "--sort=-pcpu"],
                                 capture_output=True, text=True, timeout=10).stdout
            top = []
            for line in out.splitlines()[:8]:
                f = line.split(None, 5)
                if len(f) == 6:
                    top.append({"pid": int(f[0]), "user": f[1], "cpu_pct": float(f[2]),
                                "mem_pct": float(f[3]), "elapsed_s": int(f[4]), "name": f[5]})
            hb["top_processes"] = top
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return hb

    def publish(self, running: str | None = None) -> bool:
        try:
            lines = []
            for p in sorted(self.results_dir.glob("*.json"))[-KEEP_RESULTS:]:
                lines.append(f"100644 blob {self.hash_blob(p.read_bytes())}\t{p.name}")
            hb = json.dumps(self.heartbeat(running), indent=1, sort_keys=True).encode()
            root = [f"100644 blob {self.hash_blob(hb)}\theartbeat.json"]
            if lines:
                root.append(f"040000 tree {self.mktree(lines)}\tresults")
            commit = self.git("commit-tree", self.mktree(root), "-m",
                              f"boxctl status {self.box} {utcnow()}").stdout.decode().strip()
            self.git("push", "--quiet", "--force", "origin", f"{commit}:{self.status_ref}", timeout=180)
        except (GitError, OSError) as e:
            if (self.last_push or {}).get("outcome") != f"error: {e}":
                log(f"publish failed: {e}")
            self.last_push = {"time": utcnow(), "outcome": f"error: {e}"}
            return False
        if (self.last_push or {}).get("outcome") != "ok":
            log(f"published {self.status_ref}")
        self.last_push = {"time": utcnow(), "outcome": "ok"}
        self.last_publish_mono = time.monotonic()
        self.dirty = False
        return True

    # ---------------------------------------------------------------- loop
    def poll_once(self) -> None:
        outcome = self.fetch_control()
        ids = self.list_commands() if outcome == "ok" else []
        self.pending = [c for c in ids if c not in self.done]
        while self.pending and not self.stop:
            cid = self.pending.pop(0)
            try:
                self.execute(cid)
            except (GitError, OSError) as e:
                log(f"could not run {cid}: {e}")
                self.write_result(cid, {"received": utcnow(), "exit_code": None, "timed_out": False,
                                        "error": f"agent could not run this command: {e}"})
                self.done.add(cid)
                self.state["started"] = []
                self.save_state()
            if not self.stop:
                self.publish()

    def run_forever(self) -> None:
        log(f"boxctl {VERSION} for box {self.box}: polling {self.control_ref} every {self.poll_s:g}s")
        while not self.stop:
            try:
                self.poll_once()
            except Exception as e:  # keep the agent alive; systemd restarts it if it dies anyway
                log(f"poll failed: {e!r}")
            if self.stop:
                break
            if self.dirty or time.monotonic() - self.last_publish_mono >= self.heartbeat_s:
                self.publish()
            end = time.monotonic() + self.poll_s
            while not self.stop and time.monotonic() < end:
                time.sleep(min(0.5, max(0.0, end - time.monotonic())))
        log("boxctl agent stopped")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run commands queued on a GitHub branch (boxctl agent).")
    ap.add_argument("--config", default="~/.boxctl/config.json")
    ap.add_argument("--once", action="store_true", help="one poll cycle and one publish, then exit")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    cfg = json.loads(Path(os.path.expanduser(args.config)).read_text())
    agent = Agent(cfg)

    def on_signal(signum, _frame):
        agent.stop = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    agent.setup()
    if args.once:
        agent.poll_once()
        return 0 if agent.publish() else 1
    agent.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
