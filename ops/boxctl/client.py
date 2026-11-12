#!/usr/bin/env python3
"""boxctl client: queue commands for a box and read its results, through GitHub.

  client.py boxes                                    boxes that have published a status
  client.py status BOX                               heartbeat and recent results
  client.py send BOX (--cmd TEXT | --file PATH) [--slug NAME] [--timeout SECONDS]
  client.py wait BOX ID [--max-wait SECONDS]
  client.py run BOX (--cmd TEXT | --file PATH) [...]  send, then wait for the result
  client.py show BOX ID [--json]                     one result

The remote is $BOXCTL_REPO, default https://github.com/maxschireson/single-dummy-bridge.
Git state lives in a private bare cache ($BOXCTL_CACHE, default ~/.cache/boxctl), so a
source checkout is never touched. $BOXCTL_TRAILERS, if set, is appended to the commit
message of each queued command. Protocol and limits: docs/boxctl.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO = "https://github.com/maxschireson/single-dummy-bridge"
BOX_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
CONTROL_README = """# boxctl control branch for box {box}

Commands queued for the boxctl agent on box `{box}`: one file per command,
`commands/<id>.sh`, each run once in id order. Results appear on branch
`box/{box}/status`. See docs/boxctl.md on the default branch.
"""


class Remote:
    def __init__(self, url: str):
        self.url = url
        cache = Path(os.environ.get("BOXCTL_CACHE", "~/.cache/boxctl")).expanduser()
        self.git_dir = cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".git")
        if not (self.git_dir / "HEAD").exists():
            cache.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "--bare", "-q", str(self.git_dir)], check=True)
        self.git("config", "remote.origin.url", url)

    def git(self, *args: str, input: bytes | None = None, check: bool = True,
            timeout: float = 300) -> subprocess.CompletedProcess:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        for k, v in (("GIT_AUTHOR_NAME", "boxctl client"), ("GIT_AUTHOR_EMAIL", "boxctl-client@invalid"),
                     ("GIT_COMMITTER_NAME", "boxctl client"), ("GIT_COMMITTER_EMAIL", "boxctl-client@invalid")):
            env.setdefault(k, v)
        r = subprocess.run(["git", "--git-dir", str(self.git_dir), *args], input=input,
                           capture_output=True, timeout=timeout, env=env)
        if check and r.returncode != 0:
            raise SystemExit(f"git {args[0]} failed: {r.stderr.decode(errors='replace').strip()}")
        return r

    def out(self, *args: str, **kw) -> str:
        return self.git(*args, **kw).stdout.decode().strip()

    def fetch(self, ref: str, local: str) -> bool:
        """Fetch one branch tip; False if the branch does not exist on the remote."""
        r = self.git("fetch", "--quiet", "--no-tags", "--depth=1", "origin", f"+{ref}:{local}", check=False)
        if r.returncode == 0:
            return True
        err = r.stderr.decode(errors="replace")
        if "couldn't find remote ref" in err or "could not find remote ref" in err:
            self.git("update-ref", "-d", local, check=False)
            return False
        raise SystemExit(f"git fetch {ref} failed: {err.strip()}")

    def blob(self, spec: str) -> bytes | None:
        r = self.git("cat-file", "blob", spec, check=False)
        return r.stdout if r.returncode == 0 else None

    def mktree(self, lines: list[str]) -> str:
        return self.out("mktree", input=("\n".join(lines) + "\n").encode())

    def hash_blob(self, data: bytes) -> str:
        return self.out("hash-object", "-w", "--stdin", input=data)


def refs(box: str, kind: str) -> tuple[str, str]:
    if not BOX_RE.match(box):
        raise SystemExit(f"invalid box name {box!r}")
    return f"refs/heads/box/{box}/{kind}", f"refs/remotes/origin/box/{box}/{kind}"


def new_id(slug: str | None) -> str:
    now = datetime.now(timezone.utc)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slug or "cmd").strip("-._")[:40] or "cmd"
    cid = f"{now:%Y%m%dT%H%M%S}Z-{now.microsecond:06d}-{slug}"
    assert ID_RE.match(cid), cid
    return cid


def send(remote: Remote, box: str, script: bytes, slug: str | None = None,
         timeout: int | None = None) -> str:
    if timeout:
        script = f"# boxctl: timeout={int(timeout)}\n".encode() + script
    ref, local = refs(box, "control")
    cid = new_id(slug)
    message = f"boxctl: queue {cid} for box {box}\n"
    if os.environ.get("BOXCTL_TRAILERS"):
        message += "\n" + os.environ["BOXCTL_TRAILERS"].strip() + "\n"
    for attempt in range(6):
        parents: list[str] = []
        root: list[str] = []
        commands: list[str] = []
        if remote.fetch(ref, local):
            parents = ["-p", remote.out("rev-parse", local)]
            for line in remote.out("ls-tree", local).splitlines():
                if line.endswith("\tcommands"):
                    commands = remote.out("ls-tree", f"{local}:commands").splitlines()
                else:
                    root.append(line)
        else:
            readme = remote.hash_blob(CONTROL_README.format(box=box).encode())
            root.append(f"100644 blob {readme}\tREADME.md")
        commands.append(f"100644 blob {remote.hash_blob(script)}\t{cid}.sh")
        root.append(f"040000 tree {remote.mktree(commands)}\tcommands")
        commit = remote.out("commit-tree", remote.mktree(root), *parents, "-F", "-", input=message.encode())
        r = remote.git("push", "--quiet", "origin", f"{commit}:{ref}", check=False)
        if r.returncode == 0:
            return cid
        err = r.stderr.decode(errors="replace")
        if any(s in err for s in ("rejected", "fetch first", "non-fast-forward", "stale info")):
            time.sleep(1 + attempt)
            continue
        raise SystemExit(f"git push to {ref} failed: {err.strip()}")
    raise SystemExit(f"push to {ref} kept being rejected; try again")


def fetch_status(remote: Remote, box: str) -> str | None:
    ref, local = refs(box, "status")
    return local if remote.fetch(ref, local) else None


def get_result(remote: Remote, local: str, cid: str) -> dict | None:
    data = remote.blob(f"{local}:results/{cid}.json")
    return json.loads(data) if data else None


def wait(remote: Remote, box: str, cid: str, max_wait: float, interval: float = 10) -> dict | None:
    deadline = time.monotonic() + max_wait
    while True:
        local = fetch_status(remote, box)
        if local:
            result = get_result(remote, local, cid)
            if result:
                return result
        if time.monotonic() >= deadline:
            return None
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())) or interval)


def describe(result: dict) -> str:
    if result.get("interrupted"):
        head = "interrupted (the agent stopped while it ran)"
    elif result.get("error"):
        head = f"not run: {result['error']}"
    else:
        head = f"exit {result.get('exit_code')}"
        if result.get("timed_out"):
            head += f" after hitting its {result.get('timeout_s')}s timeout"
        if result.get("duration_s") is not None:
            head += f" in {result['duration_s']}s"
    return head


def print_result(result: dict) -> None:
    print(f"{result['id']} on {result['box']}: {describe(result)}")
    tail = result.get("output_tail") or ""
    if tail:
        print("--- output" + (" (tail)" if result.get("output_bytes", 0) > len(tail.encode()) else "") + " ---")
        print(tail, end="" if tail.endswith("\n") else "\n")


def exit_code(result: dict | None) -> int:
    if result is None:
        return 2
    return 0 if result.get("exit_code") == 0 else 1


def ago(stamp: str) -> str:
    t = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    s = int((datetime.now(timezone.utc) - t).total_seconds())
    return f"{s}s" if s < 120 else f"{s // 60}m" if s < 7200 else f"{s // 3600}h"


def cmd_status(remote: Remote, box: str, recent: int) -> int:
    local = fetch_status(remote, box)
    if not local:
        print(f"box {box}: no status branch yet (agent not installed, or its deploy key not added)")
        return 2
    hb = json.loads(remote.blob(f"{local}:heartbeat.json") or b"{}")
    mem, disk = hb.get("memory_mb") or {}, hb.get("disk") or {}
    disk_text = ", ".join("%s %s/%s GB" % (k, v.get("free_gb"), v.get("total_gb")) for k, v in disk.items())
    print(f"box {box}: heartbeat {hb.get('time')} ({ago(hb['time'])} ago), agent {hb.get('agent_version')}, "
          f"host {hb.get('hostname')}, {hb.get('os', '?')}")
    print(f"  {hb.get('cpus')} CPUs ({hb.get('cpu_model', '?')}), load {hb.get('load')}, "
          f"memory available {mem.get('MemAvailable')}/{mem.get('MemTotal')} MB, disk free {disk_text}")
    print(f"  running: {hb.get('running')}; pending: {len(hb.get('pending') or [])}; "
          f"last fetch: {(hb.get('last_fetch') or {}).get('outcome')}")
    for p in hb.get("top_processes") or []:
        print(f"    {p['name']:<16} pid {p['pid']:<8} {p['user']:<10} cpu {p['cpu_pct']:>5}%  "
              f"mem {p['mem_pct']:>4}%  up {p['elapsed_s']}s")
    names = [n for n in remote.out("ls-tree", "--name-only", f"{local}:results", check=False).splitlines()
             if n.endswith(".json")]
    if names:
        print("  recent results:")
        for n in names[-recent:]:
            r = json.loads(remote.blob(f"{local}:results/{n}") or b"{}")
            print(f"    {r.get('id')}: {describe(r)}")
    return 0


def cmd_boxes(remote: Remote) -> int:
    out = remote.out("ls-remote", "--heads", "origin")
    boxes = sorted({m.group(1) for m in re.finditer(r"refs/heads/box/([a-z0-9-]+)/status$", out, re.M)})
    print("\n".join(boxes) if boxes else "no boxes have published a status yet")
    return 0


def script_from(args: argparse.Namespace) -> bytes:
    if args.file:
        return Path(args.file).read_bytes()
    return (args.cmd if args.cmd.endswith("\n") else args.cmd + "\n").encode()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.environ.get("BOXCTL_REPO", DEFAULT_REPO))
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("boxes")
    p = sub.add_parser("status")
    p.add_argument("box")
    p.add_argument("--recent", type=int, default=10)
    for name in ("send", "run"):
        p = sub.add_parser(name)
        p.add_argument("box")
        src = p.add_mutually_exclusive_group(required=True)
        src.add_argument("--cmd", help="shell text to run with bash")
        src.add_argument("--file", help="script file to run with bash")
        p.add_argument("--slug", help="short name used in the command id")
        p.add_argument("--timeout", type=int, help="seconds before the agent kills it (default 900, max 21600)")
        if name == "run":
            p.add_argument("--max-wait", type=float, default=900, help="seconds to wait for the result")
            p.add_argument("--interval", type=float, default=10, help="seconds between status fetches")
    p = sub.add_parser("wait")
    p.add_argument("box")
    p.add_argument("id")
    p.add_argument("--max-wait", type=float, default=900)
    p.add_argument("--interval", type=float, default=10)
    p = sub.add_parser("show")
    p.add_argument("box")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    remote = Remote(args.repo)

    if args.action == "boxes":
        return cmd_boxes(remote)
    if args.action == "status":
        return cmd_status(remote, args.box, args.recent)
    if args.action in ("send", "run"):
        cid = send(remote, args.box, script_from(args), args.slug, args.timeout)
        print(cid, flush=True)
        if args.action == "send":
            return 0
        result = wait(remote, args.box, cid, args.max_wait, args.interval)
    elif args.action == "wait":
        result = wait(remote, args.box, args.id, args.max_wait, args.interval)
    else:  # show
        local = fetch_status(remote, args.box)
        result = get_result(remote, local, args.id) if local else None
        if result and args.json:
            print(json.dumps(result, indent=1, sort_keys=True))
            return exit_code(result)
    if result is None:
        print(f"no result yet for {getattr(args, 'id', None) or cid}", file=sys.stderr)
        return 2
    print_result(result)
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
