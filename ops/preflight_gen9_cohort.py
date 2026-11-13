"""Preflight of the Gen 9 cohort on a box (docs/gen9/cohort.md, step 4), as one job.

Restores the two artifacts, fetches the two family lists from their transfer branches (checked against their
pins), prepares an opened copy of the plan with fresh deals from a drained source run (which supplies only the
bots and artifacts), and plays --deals deals of every pair through ops/smoke_gen7.py. Starts no collector,
writes no feed and leaves the repository's plan closed.

  python ops/preflight_gen9_cohort.py --source ~/work/capsule-gen7-capture/recovery --out OUT [--fresh 10000] [--seed 9013] [--deals 2]
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

PLAN = ROOT / 'configs/round9-cohort.json'
LISTS = {
    'v41-training-families-union.json': ('transfer/v41-training-families-union-20261112',
                                          '0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2'),
    'played-families-20261113.json.gz': ('transfer/gen9-cohort-inputs-20261113',
                                         'ac5243e11112bf68fbc6a8c8700cf6b36ab829a2348f5925c5fcf721c567333c'),
}
RESTORE = ('models/cardplay/gen7-policy-v4.1-2026-11-12/restore.py', 'models/cardplay/gen8-system-scorer-v1-2026-11-12/restore_model.py')


def fetch_list(name, branch, pin, out):
    path = out / name
    if not path.exists():
        subprocess.run(['git', 'fetch', '--quiet', 'origin', f'+refs/heads/{branch}:refs/remotes/origin/{branch}'], cwd=ROOT, check=True)
        blob = subprocess.run(['git', 'show', f'origin/{branch}:{name}'], cwd=ROOT, check=True, capture_output=True).stdout
        path.write_bytes(blob)
    if sha(path) != pin:
        raise ValueError(f'{name} does not match its pin')
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fresh', type=int, default=10000)
    ap.add_argument('--seed', type=int, default=9013)
    ap.add_argument('--deals', type=int, default=2)
    a = ap.parse_args()
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    for script in RESTORE:
        subprocess.run([sys.executable, str(ROOT / script)], cwd=(ROOT / script).parent, check=True, stdout=subprocess.DEVNULL)
    lists = {name: fetch_list(name, branch, pin, out) for name, (branch, pin) in LISTS.items()}
    plan = json.loads(PLAN.read_text())
    plan.update(launch_enabled=True, pending=[])
    plan['notes'] = plan['notes'] + ['PREFLIGHT COPY, opened only to prepare a run for ops/smoke_gen7.py; the repository plan stays closed.']
    opened = out / 'round9-cohort-preflight.json'
    opened.write_text(json.dumps(plan, indent=1) + '\n')
    from ops import prepare_gen7_alpha as P
    from ops import smoke_gen7 as S
    m = P.prepare(out / 'run', a.source, opened, exclude_families=lists['v41-training-families-union.json'],
                  fresh=(a.fresh, a.seed), played=lists['played-families-20261113.json.gz'])
    prepared = time.time()
    S.smoke(out / 'run', out / 'smoke.json', deals=a.deals)
    report = json.loads((out / 'smoke.json').read_text())
    summary = dict(manifest=m['identity'], target=m['target'], fresh_deals=m['fresh_deals'],
                   bots={k: m['bots'][k]['identity'] for k in plan['gen7_bots']}, source_generation=m['source_generation'],
                   source_commit=m.get('source_commit'), deals=[{k: d[k] for k in ('index', 'pair', 'seconds', 'imps', 'decisions', 'consulted', 'over_budget')}
                                                               for d in report['deals']],
                   prepare_seconds=round(prepared - started, 1), smoke_seconds=round(time.time() - prepared, 1), ok=True)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
