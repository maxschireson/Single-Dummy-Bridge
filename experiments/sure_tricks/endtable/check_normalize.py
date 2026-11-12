"""The C++ knowledge normalization (endtable.h normalizeKnowledge) against pooled_ref.normalize on every state
`endtable_tool normdump` prints: pools of 0 to 8 cards by suit lengths, every East/West count split (including
impossible ones), every knowledge value from unknown to one past the suit length.
usage: ./endtable_tool normdump | python3 check_normalize.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pooled_ref import normalize

n = bad = 0
for line in sys.stdin:
    left, right = line.split(' -> ')
    v = [int(t) for t in left.split()]
    x, cE, cW, el = v[0:4], v[4], v[5], v[6:10]
    pool = 0
    for s in range(4):
        for r in range(x[s]):
            pool |= 1 << (13 * s + r)
    # the C++ code reads el < 0 as unknown; pooled_ref uses None
    ref = normalize(pool, cE, cW, tuple(None if e < 0 else e for e in el))
    ref = 'none' if ref is None else ' '.join(str(-1 if e is None else e) for e in ref)
    n += 1
    if ref != right.strip():
        bad += 1
        if bad <= 5:
            print('MISMATCH', left, 'C++', right.strip(), 'pooled_ref', ref)
print('normalize: %d states, %d mismatches' % (n, bad))
sys.exit(1 if bad else 0)
