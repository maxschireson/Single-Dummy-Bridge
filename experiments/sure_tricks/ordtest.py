"""Node and lookup totals for a set of solver flags, on three corpora: the benchmark positions (contract question),
random 7-card and random 8-card positions (position value). Deterministic, so variants can be compared exactly.
usage: ordtest.py "flags" ["flags" ...]"""
import json, random, subprocess, sys
from gen_table_positions import gen
D = json.load(open('bench_lines.json'))
bench = ''.join('N%d %s\n' % (D[k]['need'], D[k]['line']) for k in sorted(D) if int(k.split('_')[1]) in (7, 8, 9, 10))
rng = random.Random(77)
r7 = ''.join(gen(rng, 7) + '\n' for _ in range(300))
r8 = ''.join(gen(rng, 8) + '\n' for _ in range(120))
def run(inp, flags):
    out = subprocess.run(['./sure_cpp', '--front', '4', *flags], input=inp, capture_output=True, text=True, check=True).stdout
    rs = [json.loads(l) for l in out.splitlines()]
    return sum(r['nodes_above'] for r in rs), sum(r['probes'] for r in rs), [r.get('value', r.get('cards')) for r in rs]
base = None
for fl in sys.argv[1:]:
    f = fl.split()
    a = run(bench, f); b = run(r7, f + ['--value']); c = run(r8, f + ['--value'])
    res = (a[2], b[2], c[2])
    if base is None:
        base = res
    print('%-28s bench nodes %8d lookups %8d | 7-card nodes %8d lookups %8d | 8-card nodes %9d lookups %8d | results %s'
          % (fl or '(default)', a[0], a[1], b[0], b[1], c[0], c[1], 'same' if res == base else 'DIFFER'), flush=True)
