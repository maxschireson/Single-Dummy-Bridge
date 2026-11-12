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
        fl2 = fl.split()
        binary = './sure_cpp'
        if fl2 and fl2[0].startswith('@'):          # name=@binary flags: run another build
            binary, fl2 = fl2[0][1:], fl2[1:]
        out = subprocess.run([binary, '--front', '4', '--warm', *fl2], input=inp, capture_output=True, text=True, check=True).stdout
        for k, l in zip(keys, out.splitlines()):
            j = json.loads(l)
            T[(k, n)].append(1000 * j['search_seconds'])
            m = (j['nodes_above'], j['probes'], json.dumps(j['cards'], sort_keys=True))
            meta.setdefault((k, n), m)
            assert meta[(k, n)] == m, (k, n, 'search differs between runs of one configuration')
            assert json.loads(m[2]) == json.loads(meta.setdefault((k, 'cards'), m)[2]), (k, n, 'card values differ between builds')
            assert j['cell_misses'] == 0 and j['replay_left'] == 0, (k, n, j)
for k in keys:
    print(json.dumps(dict(pos=k, nodes={n: meta[(k, n)][0] for n, _ in cfgs}, probes={n: meta[(k, n)][1] for n, _ in cfgs}, **{n: dict(min=round(min(T[(k, n)]), 3), med=round(statistics.median(T[(k, n)]), 3)) for n, _ in cfgs})), flush=True)
