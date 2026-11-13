"""Best-of-n timing of the C++ solver on named benchmark positions (bench_lines.json).
usage: runpos.py KEY[,KEY...] [--reps n] [--contract] [solver flags]"""
import json, subprocess, sys
D = json.load(open('bench_lines.json'))
keys = sys.argv[1].split(',')
args = sys.argv[2:]
reps = 3
if '--reps' in args:
    i = args.index('--reps'); reps = int(args[i + 1]); del args[i:i + 2]
contract = '--contract' in args
if contract:
    args.remove('--contract')
for k in keys:
    a = list(args) + (['--need', str(D[k]['need'])] if contract else [])
    best = None
    for _ in range(reps):
        out = subprocess.run(['./sure_cpp', *a], input=D[k]['line'] + '\n', capture_output=True, text=True, check=True).stdout
        r = json.loads(out.splitlines()[-1])
        if best is None or r['search_seconds'] < best['search_seconds']:
            best = r
    print('%-6s %-34s %8.2f ms  nodes %8d  probes %7d' % (k, ' '.join(args) + (' contract' if contract else ''), 1000 * best['search_seconds'], best['nodes_above'], best['probes']), flush=True)
