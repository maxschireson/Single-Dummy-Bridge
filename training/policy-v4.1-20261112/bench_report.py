#!/usr/bin/env python3
"""Summaries of the tree bench of 12 November: v4's tree and v4.1's tree on the same fresh fork pairs.

  python bench_report.py ROWS.json[.gz] BOTS.json OUT_DIR

ROWS is what scripts/gen7_bench.py --out wrote; BOTS maps each deal family to [candidate, opponent].
The bench reads every gap fork whose decision carries a search record, and Gen 7's decisions carry
one too. Its yardstick ("A is the card Gen 6 played") only holds where a Gen 6 bot decided, so the
rows are cut down to those decisions first (rows_g6.json). Then: the bench's own summary, and the
bot's rule (margin, trust) for each net's tree with the other as the comparison.
"""
import gzip
import json
from pathlib import Path
import subprocess
import sys

rows_path, bots_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
with (gzip.open(rows_path, 'rt') if rows_path.suffix == '.gz' else open(rows_path)) as f:
    saved = json.load(f)
bots = json.load(open(bots_path))
def decider(r):
    cand, opp = bots[r['family']]
    return cand if r['player'] == 'candidate' else opp
rows = saved['rows']
kept = [r for r in rows if decider(r).startswith('6-')]
by = {}
for r in rows:
    by[decider(r)] = by.get(decider(r), 0) + 1
print(f"{len(rows)} pairs read, by deciding bot {by}; {len(kept)} at a Gen 6 bot's decision; {len({r['family'] for r in kept})} deals; "
      f"{saved['settings']['tables']} Gen 6 sides; bench ran {saved['settings']['seconds']} s")
(out / 'rows_g6.json').write_text(json.dumps(dict(settings=saved['settings'], rows=kept)))
root = Path(__file__).resolve().parents[2]
keys = [k for k in kept[0] if k.startswith('tree_') and k != 'tree_0_plain1']
old = [k for k in keys if '_net2' not in k][0]
new = [k for k in keys if '_net2' in k][0]
summary = subprocess.run([sys.executable, str(root / 'scripts/gen7_bench.py'), '--rows', str(out / 'rows_g6.json')], capture_output=True, text=True)
(out / 'summary.json').write_text(summary.stdout)
if summary.returncode:
    print(summary.stderr[-2000:])
for name, key, other in (('v4', old, new), ('v4.1', new, old)):
    r = subprocess.run([sys.executable, str(root / 'scripts/gen7_sweep.py'), f"{out / 'rows_g6.json'}:{key}", '--other', other, '--label', f"the tree with {name}",
                        '--json', str(out / f'sweep_{name}.json')], capture_output=True, text=True)
    (out / f'sweep_{name}.txt').write_text(r.stdout + r.stderr[-2000:])
print('tree keys:', old, '|', new)
