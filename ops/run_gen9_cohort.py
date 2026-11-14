"""Run the Gen 9 cohort on a box as one long job (docs/gen9/cohort.md, steps 5 and 6).

On first start: restores the two artifacts, fetches the two pinned family lists over HTTPS, and prepares the run
from the repository's opened plan with fresh deals (ops/prepare_gen7_alpha.py --fresh). On every start: checks
that the run is the one this plan and source make, starts the publisher (ops/publish_gen5.py, every minute, to the
feed branch) and runs the collector (ops/gen5_runtime.py) in the foreground. Resumable: a restart continues the
same run. STOP in the run directory drains the collector; PUBLISH_STOP stops the publisher.

  python ops/run_gen9_cohort.py --run DIR --publication DIR --feed arena-gen9-azure4-feed \
      --source ~/work/capsule-gen7-capture/recovery [--plan configs/round9-cohort.json] [--fresh 10000 --seed 9013] [--workers 8]
      [--exclusions gen8x-v3-exclusions.json]

--exclusions names the training-family list the deals leave out: policy v4.1's (the default, for the cohort), or
for a plan whose bots also play rollout net v1 or a net trained from it (Gen X Stu, configs/round9-genx-stu.json)
the union of v4.1's and v1's. Each list is fetched from its transfer branch and checked against its pin.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.loop_registry import sha  # noqa: E402
from ops.preflight_gen9_cohort import LISTS, RESTORE, fetch_list  # noqa: E402
EXCLUSIONS = {'v41-training-families-union.json': LISTS['v41-training-families-union.json'],
              # v4.1's and rollout net v1's training families, 50,818 (the 8X v3 arena's list)
              'gen8x-v3-exclusions.json': ('transfer/rollout-net-v1-training-families-20261113',
                                           '72fafc4cce9ed62e6427b021103533e62e1bdfedc6acc96bf01c81186a88ee7a')}

import os  # noqa: E402
REMOTE = os.environ.get('BRIDGE_FEED_REMOTE', 'https://github.com/maxschireson/Single-Dummy-Bridge.git')   # a local bare repository in tests


def say(text):
    print(f'[gen9-cohort] {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} {text}', file=sys.stderr, flush=True)


def prepared(run, plan_path, a):
    """The run, prepared on first start; on later starts the same plan and source must have made it."""
    from ops import prepare_gen7_alpha as P
    if (run / 'manifest.json').exists():
        m = json.loads((run / 'manifest.json').read_text())
        if m['plan_sha256'] != sha(plan_path):
            raise SystemExit('The plan changed since this run was prepared: a changed plan is a new run')
        say(f"resuming {m['identity'][:12]}")
        return m
    for script in RESTORE:
        subprocess.run([sys.executable, str(ROOT / script)], cwd=(ROOT / script).parent, check=True, stdout=subprocess.DEVNULL)
    inputs = run.parent / (run.name + '-inputs')
    inputs.mkdir(parents=True, exist_ok=True)
    lists = {name: fetch_list(name, branch, pin, inputs) for name, (branch, pin) in LISTS.items()}
    excluded = lists.get(a.exclusions) or fetch_list(a.exclusions, *EXCLUSIONS[a.exclusions], inputs)
    m = P.prepare(run, a.source, plan_path, exclude_families=excluded,
                  fresh=(a.fresh, a.seed), played=lists['played-families-20261113.json.gz'])
    say(f"prepared {m['identity'][:12]}, {m['target']} deals")
    return m


def publication(path, feed):
    """A checkout whose HEAD is the feed branch (new: an orphan branch), pushing to the repository."""
    if not (path / '.git').exists():
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', REMOTE], check=True)
        exists = subprocess.run(['git', '-C', str(path), 'ls-remote', '--exit-code', '--heads', 'origin', feed], capture_output=True).returncode == 0
        if exists:
            subprocess.run(['git', '-C', str(path), 'fetch', '-q', 'origin', feed], check=True)
            subprocess.run(['git', '-C', str(path), 'checkout', '-q', '-b', feed, 'FETCH_HEAD'], check=True)
        else:
            subprocess.run(['git', '-C', str(path), 'checkout', '-q', '--orphan', feed], check=True)
    for key, value in (('user.name', 'Gen 9 cohort collector (azure4)'), ('user.email', 'noreply@anthropic.com')):
        subprocess.run(['git', '-C', str(path), 'config', key, value], check=True)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--publication', type=Path, required=True)
    ap.add_argument('--feed', required=True)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--plan', type=Path, default=ROOT / 'configs/round9-cohort.json')
    ap.add_argument('--fresh', type=int, default=10000)
    ap.add_argument('--seed', type=int, default=9013)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--exclusions', choices=sorted(EXCLUSIONS), default='v41-training-families-union.json')
    a = ap.parse_args()
    run, pub = a.run.resolve(), a.publication.resolve()
    m = prepared(run, a.plan.resolve(), a)
    publication(pub, a.feed)
    say(f'publisher -> {a.feed}')
    publisher = subprocess.Popen([sys.executable, str(ROOT / 'ops/publish_gen5.py'), '--run', str(run), '--publication', str(pub)])
    try:
        say(f'collector, {a.workers} workers')
        subprocess.run([sys.executable, str(ROOT / 'ops/gen5_runtime.py'), '--run', str(run), '--workers', str(a.workers)], check=True)
    finally:
        if publisher.poll() is None:
            publisher.terminate()
            publisher.wait(timeout=120)
        subprocess.run([sys.executable, str(ROOT / 'ops/publish_gen5.py'), '--run', str(run), '--publication', str(pub), '--once'])
    state = json.loads((run / 'state.json').read_text())
    say(f"collector ended: {state['completed']} of {state['target']}")


if __name__ == '__main__':
    main()
