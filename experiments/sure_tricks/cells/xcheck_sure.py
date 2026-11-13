"""The study's outright answers (cells.cpp, every shape in one set) against sure_cpp on the same recorded positions.
usage: xcheck_sure.py POSITIONS.jsonl SURE_BIN OUT.jsonl [OUT.jsonl ...]"""
import json, subprocess, sys
from pipeline import name, runs_of

pos_file, binary, outs = sys.argv[1], sys.argv[2], sys.argv[3:]
P = {(p['table'], p['cards']): p for p in map(json.loads, open(pos_file))}
R = [json.loads(l) for f in outs for l in open(f)]
R = [r for r in R if r['shape']['outright'] is not None]
lines = []
for r in R:
    p = P[(r['table'], r['cards'])]
    lines.append('N%d %d %d %s %s %s %d %d %d %d %s' % (p['need'], p['trump'], p['leader'], p['hN'], p['hS'], p['pool'], p['cE'], p['cW'], p['vE'], p['vW'], ' '.join(map(str, p['trick']))))
out = subprocess.run([binary], input='\n'.join(lines) + '\n', capture_output=True, text=True).stdout.splitlines()
assert len(out) == len(R), (len(out), len(R))
same = sure_more = cells_more = cards = 0
examples = []
for r, l in zip(R, out):
    got = {name(int(c)): v for c, v in json.loads(l)['cards'].items()}
    p = P[(r['table'], r['cards'])]
    pos = dict(p)
    for k in ('hN', 'hS', 'pool'):
        pos[k] = int(p[k], 16)
    runs = runs_of(pos)
    mine = r['shape']['outright']
    for run in runs:
        a = mine[name(run[0])]
        b = [got[name(c)] for c in run if name(c) in got]
        assert len(b) == 1, (run, got)
        cards += 1
        if a == b[0]:
            same += 1
        elif b[0] > a:
            sure_more += 1
            examples.append((r['table'], r['cards'], name(run[0]), 'sure_cpp yes, cells no'))
        else:
            cells_more += 1
            examples.append((r['table'], r['cards'], name(run[0]), 'cells yes, sure_cpp no'))
print('%d positions, %d card answers: same %d; sure_cpp yes where cells says no %d; cells yes where sure_cpp says no %d' % (len(R), cards, same, sure_more, cells_more))
for e in examples[:10]:
    print('  ', e)
