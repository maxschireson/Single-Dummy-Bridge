#!/usr/bin/env python3
"""Publish a local test run's records to a transfer branch of its own, and keep it up to date.

  python ops/publish_test_run.py --run RUN --branch transfer/NAME --checkout DIR [--readme FILE]
      [--plan FILE] [--extra FILE ...] [--every 600] [--once] [--remote URL] [--ssh-key PATH]
      [--trailers-file FILE]

One writer per branch: the host that plays the run. Each cycle copies into DIR/<run name>/ the
manifest, state, source indices, corpus, the plan, any --extra files (a preflight report, say) and
every new episode, receipt and failure record, then commits and pushes if anything changed. It never
copies the DDS cache (regenerable) or the run's artifacts (their hashes are in the manifest and the
files are in the repository). Completed episodes are immutable, so a published file is not copied
again unless its size changed.

Without --once it repeats every --every seconds and exits after a cycle that finds the run stopped
(a STOP file) with nothing new to publish.

A test run is not an arena cohort: these branches are not feeds and are never merged into source.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SMALL = ('manifest.json', 'state.json', 'source-indices.json')
ONCE = ('corpus.jsonl',)
RECORDS = ('episodes', 'receipts', 'failures')


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}", flush=True)


def git(checkout: Path, *args: str, input: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    for k, v in (('GIT_AUTHOR_NAME', 'boxctl publisher'), ('GIT_AUTHOR_EMAIL', 'boxctl-publisher@invalid'),
                 ('GIT_COMMITTER_NAME', 'boxctl publisher'), ('GIT_COMMITTER_EMAIL', 'boxctl-publisher@invalid')):
        env.setdefault(k, v)
    r = subprocess.run(['git', '-C', str(checkout), *args], input=input, capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.strip()[-400:]}")
    return r


def setup(checkout: Path, remote: str, branch: str, ssh_key: str | None) -> None:
    if not (checkout / '.git').exists():
        checkout.mkdir(parents=True, exist_ok=True)
        git(checkout, 'init', '-q')
        git(checkout, 'remote', 'add', 'origin', remote)
    else:
        git(checkout, 'remote', 'set-url', 'origin', remote)
    if ssh_key:
        git(checkout, 'config', 'core.sshCommand',
            f'ssh -i {ssh_key} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20')
    if git(checkout, 'rev-parse', '--verify', '-q', 'HEAD', check=False).returncode == 0:
        return
    r = git(checkout, 'fetch', '-q', '--depth=1', 'origin', f'refs/heads/{branch}', check=False)
    if r.returncode == 0:
        git(checkout, 'checkout', '-q', '-B', branch, 'FETCH_HEAD')
    elif "couldn't find remote ref" in r.stderr or 'could not find remote ref' in r.stderr:
        git(checkout, 'checkout', '-q', '--orphan', branch)
    else:
        raise RuntimeError(f"git fetch failed: {r.stderr.strip()[-400:]}")


def copy(src: Path, dst: Path) -> bool:
    if dst.exists() and dst.stat().st_size == src.stat().st_size and dst.read_bytes() == src.read_bytes():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def sync(run: Path, checkout: Path, plan: Path | None, extras: list[Path], readme: Path | None) -> int:
    """Copy what changed; return the number of files written."""
    dest = checkout / run.name
    written = 0
    for name in SMALL:
        if (run / name).exists():
            written += copy(run / name, dest / name)
    for name in ONCE:
        if (run / name).exists() and not (dest / name).exists():
            written += copy(run / name, dest / name)
    if plan:
        written += copy(plan, dest / 'plan.json')
    for extra in extras:
        if extra.exists():
            written += copy(extra, dest / extra.name)
    if readme:
        written += copy(readme, checkout / 'README.md')
    for folder in RECORDS:
        source = run / folder
        if not source.is_dir():
            continue
        for path in sorted(source.iterdir()):
            if path.is_file() and not path.name.startswith('.'):
                target = dest / folder / path.name
                if not target.exists() or target.stat().st_size != path.stat().st_size:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                    written += 1
    return written


def commit_and_push(checkout: Path, run: Path, branch: str, trailers: str) -> bool:
    git(checkout, 'add', '-A')
    if git(checkout, 'diff', '--cached', '--quiet', check=False).returncode == 0:
        return False
    episodes = len(list((checkout / run.name / 'episodes').glob('*.json.gz'))) if (checkout / run.name / 'episodes').exists() else 0
    message = f"pre7-test: {run.name}, {episodes} episodes\n"
    if trailers:
        message += '\n' + trailers.strip() + '\n'
    git(checkout, 'commit', '-q', '-F', '-', input=message)
    for attempt in range(5):
        r = git(checkout, 'push', '-q', 'origin', f'HEAD:refs/heads/{branch}', check=False)
        if r.returncode == 0:
            log(f"pushed {branch}: {episodes} episodes")
            return True
        log(f"push failed (attempt {attempt + 1}): {r.stderr.strip()[-300:]}")
        time.sleep(30 * (attempt + 1))
    raise RuntimeError('push kept failing')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--branch', required=True)
    ap.add_argument('--checkout', type=Path, required=True)
    ap.add_argument('--remote', default='git@github.com:maxschireson/Single-Dummy-Bridge.git')
    ap.add_argument('--ssh-key')
    ap.add_argument('--plan', type=Path)
    ap.add_argument('--extra', type=Path, action='append', default=[])
    ap.add_argument('--readme', type=Path)
    ap.add_argument('--trailers-file', type=Path)
    ap.add_argument('--every', type=float, default=600)
    ap.add_argument('--once', action='store_true')
    a = ap.parse_args(argv)
    if not a.branch.startswith('transfer/'):
        raise SystemExit('test runs publish to transfer/ branches only')
    run = a.run.resolve()
    if not (run / 'manifest.json').exists():
        raise SystemExit(f'{run} has no manifest.json')
    trailers = a.trailers_file.read_text() if a.trailers_file else ''
    setup(a.checkout, a.remote, a.branch, a.ssh_key)
    log(f"publishing {run} to {a.branch} every {a.every:g}s")
    while True:
        try:
            written = sync(run, a.checkout, a.plan, a.extra, a.readme)
            pushed = commit_and_push(a.checkout, run, a.branch, trailers) if written else False
        except Exception as e:  # keep publishing; the next cycle retries
            log(f"cycle failed: {e!r}")
            pushed = written = None
        if a.once:
            return 0 if pushed is not None else 1
        if written == 0 and (run / 'STOP').exists():
            state = json.loads((run / 'state.json').read_text()) if (run / 'state.json').exists() else {}
            log(f"run stopped and fully published ({state.get('completed')} boards); exiting")
            return 0
        time.sleep(a.every)


if __name__ == '__main__':
    sys.exit(main())
