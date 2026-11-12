"""T7, second part: per-card values of sure_cpp on the positions of bench_lines.json with the built table
(--front 4 --table FILE) against the stand-in table (--front 4). Run from experiments/sure_tricks/ with sure_cpp built -DENDTABLE.
usage: python3 endtable/compare_bench.py TABLE [KEY,KEY,...]"""
import json, subprocess, sys
D = json.load(open('bench_lines.json'))
table = sys.argv[1]
keys = sys.argv[2].split(',') if len(sys.argv) > 2 else list(D)
bad = 0
for k in keys:
    res = {}
    for name, flags in (('stand-in', ['--front', '4']), ('table', ['--front', '4', '--table', table])):
        out = subprocess.run(['./sure_cpp', *flags], input=D[k]['line'] + '\n', capture_output=True, text=True, check=True).stdout
        res[name] = json.loads(out.splitlines()[-1])
    same = res['stand-in']['cards'] == res['table']['cards']
    bad += not same
    print('%-6s per-card values %s; search %.1f ms with the table, %.1f ms with the stand-in (its fill excluded); nodes %d / %d'
          % (k, 'agree' if same else 'DIFFER table %s stand-in %s' % (res['table']['cards'], res['stand-in']['cards']),
             1000 * res['table']['search_seconds'], 1000 * res['stand-in']['search_seconds'],
             res['table']['nodes_above'], res['stand-in']['nodes_above']), flush=True)
print('positions: %d, differing: %d' % (len(keys), bad))
