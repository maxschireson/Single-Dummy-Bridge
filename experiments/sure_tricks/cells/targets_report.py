import json, sys
def mean(v):
    v = list(v); return sum(v) / len(v) if v else float('nan')
R = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
R = [r for r in R if all(r['targets'][k] is not None for k in ('-1', '0', '1'))]
print('%d positions at %d cards' % (len(R), R[0]['cards']))
T = lambda r, d: r['targets'][str(d)]
claim = [r for r in R if T(r, 0)['outright']]
rest = [r for r in R if not T(r, 0)['outright']]
print('contract guaranteed outright: %d' % len(claim))
print('   of these, an overtrick is also guaranteed outright: %d; otherwise its best certified probability (shape): mean %.3f, 0.5 or more in %d, none in %d' % (
    sum(T(r, 1)['outright'] for r in claim), mean(T(r, 1)['floor'] for r in claim if not T(r, 1)['outright']),
    sum(T(r, 1)['floor'] >= .5 for r in claim if not T(r, 1)['outright']), sum(T(r, 1)['floor'] <= 1e-9 for r in claim if not T(r, 1)['outright'])))
print('   overtrick impossible by count (needs more tricks than cards left): %d' % sum(bool(T(r, 1).get('trivial')) for r in claim))
print('no outright claim: %d' % len(rest))
print('   one down guaranteed outright: %d (%.1f%%)' % (sum(T(r, -1)['outright'] for r in rest), 100 * mean(T(r, -1)['outright'] for r in rest)))
none = [r for r in rest if T(r, 0)['floor'] <= 1e-9]
some = [r for r in rest if T(r, 0)['floor'] > 1e-9]
for lab, S in (('nothing certified at the contract', none), ('something certified at the contract', some)):
    if not S: continue
    f1 = [1. if T(r, -1)['outright'] else T(r, -1)['floor'] for r in S]
    print('   %s: %d positions; one down: outright in %d, certified probability mean %.3f, 0.9 or more in %d, 0.5 or more in %d, none in %d' % (
        lab, len(S), sum(T(r, -1)['outright'] for r in S), mean(f1), sum(x >= .9 for x in f1), sum(x >= .5 for x in f1), sum(x <= 1e-9 for x in f1)))
print('   mean certified probability: contract %.3f, one down %.3f, overtrick %.3f' % (mean(T(r, 0)['floor'] for r in rest), mean(1. if T(r, -1)['outright'] else T(r, -1)['floor'] for r in rest), mean(T(r, 1)['floor'] for r in rest)))
same = [r for r in rest if T(r, 0)['best'] and T(r, -1)['best'] and not T(r, -1)['outright']]
print('   best card for the contract and best card for one down are the same in %d of %d positions where both have one' % (sum(T(r, 0)['best'] == T(r, -1)['best'] for r in same), len(same)))
# actual results
down = [r for r in rest if not r['made']]
by = {}
for r in down:
    short = r['level'] + 6 - r['declarer_tricks']
    by[short] = by.get(short, 0) + 1
print('   went down: %d; by how many: %s' % (len(down), dict(sorted(by.items()))))
d2 = [r for r in down if r['level'] + 6 - r['declarer_tricks'] >= 2]
print('   down two or more: %d; of these one down was guaranteed outright in %d, and the actual layout was inside the best one-down set without that in %d' % (
    len(d2), sum(T(r, -1)['outright'] for r in d2), sum(T(r, -1)['true_in'] and not T(r, -1)['outright'] for r in d2)))
# what the recorded play took of the other targets
over = lambda r: r['declarer_tricks'] - (r['level'] + 6)
poss = [r for r in claim if not T(r, 1).get('trivial')]
for lab, S in (('overtrick guaranteed outright', [r for r in poss if T(r, 1)['outright']]),
               ('actual layout inside the best overtrick set', [r for r in poss if not T(r, 1)['outright'] and T(r, 1)['true_in']]),
               ('actual layout outside it', [r for r in poss if not T(r, 1)['outright'] and not T(r, 1)['true_in']])):
    print('   contract outright, %s: %d; the bot made an overtrick in %d, the contract exactly in %d, went down in %d' % (
        lab, len(S), sum(over(r) >= 1 for r in S), sum(over(r) == 0 for r in S), sum(over(r) < 0 for r in S)))
r1 = [r for r in rest if T(r, -1)['outright']]
print('   no outright claim, one down guaranteed outright: %d; the bot made in %d, went one down in %d, two or more down in %d' % (
    len(r1), sum(r['made'] for r in r1), sum(over(r) == -1 for r in r1), sum(over(r) <= -2 for r in r1)))
cost = [T(r, -1).get('nodes', 0) + T(r, 1).get('nodes', 0) for r in R]
base = [T(r, 0).get('nodes', 0) for r in R]
print('nodes, mean: contract target %d; the two other targets together %d' % (mean(base), mean(cost)))
