"""Where the search time goes: free lookups, lookups in an in-cache table, lookups in a cold large table.
Configurations are run round-robin so that slow drift of the machine hits them alike; min and median over reps.
usage: split.py KEY[,KEY...] reps name=flags [name=flags ...]"""
import json, statistics, subprocess, sys
D = json.load(open('bench_lines.json'))
keys = sys.argv[1].split(',')
reps = int(sys.argv[2])
cfgs = [a.split('=', 1) for a in sys.argv[3:]]
inp = ''.join('N%d %s\n' % (D[k]['need'], D[k]['line']) for k in keys)
T = {(k, n): [] for k in keys for n, _ in cfgs}
meta = {}
for r in range(reps):
    for n, fl in cfgs:
        out = subprocess.run(['./sure_cpp', '--front', '4', '--warm', *fl.split()], input=inp, capture_output=True, text=True, check=True).stdout
        for k, l in zip(keys, out.splitlines()):
            j = json.loads(l)
            T[(k, n)].append(1000 * j['search_seconds'])
            m = (j['nodes_above'], j['probes'], json.dumps(j['cards'], sort_keys=True))
            assert meta.setdefault(k, m) == m, (k, n, 'search differs between configurations')
            assert j['cell_misses'] == 0 and j['replay_left'] == 0, (k, n, j)
for k in keys:
    print(json.dumps(dict(pos=k, nodes=meta[k][0], probes=meta[k][1], **{n: dict(min=round(min(T[(k, n)]), 3), med=round(statistics.median(T[(k, n)]), 3)) for n, _ in cfgs})), flush=True)
