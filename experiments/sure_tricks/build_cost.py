"""Cost of solving one k-card table entry, on random entries (gen_table_positions.py): from scratch, and from a
(k-1)-card table (stand-in map; its fill time is excluded). usage: build_cost.py k count"""
import json, subprocess, sys
from gen_table_positions import gen
import random
k, count = int(sys.argv[1]), int(sys.argv[2])
rng = random.Random(11)
inp = ''.join(gen(rng, k) + '\n' for _ in range(count))
for name, flags in (('from scratch', []), ('from the %d-card table' % (k - 1), ['--front', str(k - 1)])):
    out = subprocess.run(['./sure_cpp', '--value', '--keep', '--ttbits', '22', *flags], input=inp, capture_output=True, text=True, check=True).stdout
    n = 0; ts = 0.0; nodes = probes = 0; vals = [0] * (k + 1)
    for l in out.splitlines():
        r = json.loads(l); n += 1; ts += r['search_seconds']; nodes += r['nodes_above']; probes += r['probes']; vals[r['value']] += 1
    print(json.dumps(dict(cards=k, entries=n, how=name, us_per_entry=round(1e6 * ts / n, 2), nodes_per_entry=round(nodes / n, 1), lookups_per_entry=round(probes / n, 1), values=vals)), flush=True)
