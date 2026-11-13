"""Compare table values with sure_cpp --value on show-out entries (T4).
usage: compare_showout.py EXPECT LINES CPP_OUT [MAX_LIST]
    EXPECT    'slot value' per line (endtable_tool showout)
    LINES     the sure_cpp input lines, same order
    CPP_OUT   sure_cpp --value output, same order
Every disagreement is then solved with pooled_ref.py, to say which side is right."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pooled_ref import Pooled, SUIT

exp, lines, outs = (open(p) for p in sys.argv[1:4])
max_list = int(sys.argv[4]) if len(sys.argv) > 4 else 20
n = 0
diff = []
for e, l, o in zip(exp, lines, outs):
    n += 1
    slot, tv = (int(t) for t in e.split())
    cv = json.loads(o)['value']
    if tv != cv:
        diff.append((slot, l.strip(), tv, cv))
right_table = right_cpp = 0
for slot, l, tv, cv in diff:
    t = l.split()
    trump, leader = int(t[0]), int(t[1])
    hN, hS, pool = (int(x, 16) for x in t[2:5])
    k, vE, vW = int(t[5]), int(t[7]), int(t[8])
    x = [bin(pool & SUIT[s]).count('1') for s in range(4)]
    el = tuple(0 if vE >> s & 1 else x[s] if vW >> s & 1 else None for s in range(4))
    ref = Pooled(trump).value(hN, hS, pool, k, k, el, leader)
    right_table += ref == tv
    right_cpp += ref == cv
print('%d show-out entries compared; %d differ; pooled_ref.py agrees with the table on %d and with sure_cpp on %d of them'
      % (n, len(diff), right_table, right_cpp))
for slot, l, tv, cv in diff[:max_list]:
    print('  slot %d  %s  table %d  sure_cpp %d' % (slot, l, tv, cv))
