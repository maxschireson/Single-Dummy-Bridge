"""C++ per-card values against the Python results already reported for the test-set positions (sure_pos_*.txt)."""
import json, os
from collections import Counter
from bench_cpp import positions, LINES
from csure import line, solve
from fusionlab import symbol

deals = {d['id']: d for d in json.load(open('fusion_deals.json'))['deals']}
py = {}
RES = 'results' if os.path.isdir('results') else '.'
for fn in ('sure_pos_done.txt', 'sure_pos_b.txt', 'sure_pos_a.txt'):
    try:
        for l in open(os.path.join(RES, fn)):
            if l.strip().startswith('{'):
                r = json.loads(l)
                if not r.get('pinned'):
                    py[(r['set'], r['left'])] = r
    except FileNotFoundError:
        pass
bad = 0
for (name, left), r in sorted(py.items()):
    if name not in LINES:
        continue
    for nm, lf, s in positions(deals, name, [left]):
        c = solve([line(s)], '--front', '4')[0]
        got = Counter((symbol(int(k))[0], s.won + v) for k, v in c['cards'].items())
        ref = Counter((k[0], v) for k, v in r['guaranteed'].items())
        same = got == ref
        bad += not same
        print('%s %d cards: Python %.1f s, C++ %.1f ms above a 4-card table; per-card values %s' % (name, left, r['seconds'], 1000 * c['search_seconds'], 'agree' if same else 'DIFFER %s %s' % (dict(got), dict(ref))))
print('positions compared: %d, differing: %d' % (len(py), bad))
