"""Compare the cards played in two runs' episodes, board by board."""
import os, sys
REPO = os.environ.get('REPO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
HERE = os.path.dirname(os.path.abspath(__file__))
import gzip, json, glob, os, sys
def plays(run):
    out = {}
    for f in sorted(glob.glob(os.path.join(os.environ.get('RUNS', 'runs'), run, 'episodes', '*.json.gz'))):
        tb = json.load(gzip.open(f))['unique_tables']['table-0']['tables'][0]
        cards = [(a.get('seat'), a.get('card')) for a in tb['actions'] if a.get('card') is not None]
        out[os.path.basename(f)] = (cards, tb['declarer_tricks'])
    return out
a, b = plays(sys.argv[1]), plays(sys.argv[2])
same = 0
for k in sorted(set(a) & set(b)):
    ca, cb = a[k][0], b[k][0]
    if ca == cb: same += 1
    else:
        i = next((i for i, (x, y) in enumerate(zip(ca, cb)) if x != y), min(len(ca), len(cb)))
        print(k, 'differs at card', i, 'of', len(ca), 'tricks', a[k][1], b[k][1])
print('identical', same, 'of', len(set(a) & set(b)), '; cards per board', [len(v[0]) for v in a.values()][:6])
