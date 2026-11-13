"""Families of every board in the arena feeds rollout net v1 was trained on, read at the tips its fetch recorded
(transfer/rollout-net-v1-20261113:fetch.json). Partial fetches: only the replay board files' blobs are read."""
import json, subprocess, sys
from pathlib import Path

repo = Path(sys.argv[1]); fetch = json.load(open(sys.argv[2])); out = Path(sys.argv[3])
def git(*a, **k):
    return subprocess.run(['git', '-C', str(repo), *a], check=True, capture_output=True, text=True, **k).stdout
fams, report = set(), {}
for name, info in fetch['branches'].items():
    tip = info['tip']
    try:
        git('fetch', '-q', '--filter=blob:none', '--depth', '1', 'origin', tip)
    except subprocess.CalledProcessError as e:
        report[name] = dict(error=e.stderr[-200:]); print(name, 'FETCH FAILED', flush=True); continue
    files = [f for f in git('ls-tree', '-r', '--name-only', tip).splitlines() if '/boards-' in f and f.endswith('.json')]
    n, here = 0, set()
    for f in files:
        d = json.loads(git('cat-file', '-p', f'{tip}:{f}'))
        for row in d.values():
            here.add(row['family']); n += 1
    fams |= here
    report[name] = dict(tip=tip, boards=n, families=len(here), recorded_episodes=info.get('episodes'))
    print(name, n, len(here), info.get('episodes'), flush=True)
out.write_text(json.dumps(dict(source='transfer/rollout-net-v1-20261113:fetch.json', families=sorted(fams), feeds=report), indent=0))
print('total families', len(fams))
