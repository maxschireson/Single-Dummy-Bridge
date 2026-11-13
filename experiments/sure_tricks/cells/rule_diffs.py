"""Choice rules compared pair by pair on the ddrules.py output: expected makes of the card each rule picks, against
"double-dummy value, ties by certified probability". A card's expected make is 1 if the actual layout is in its
certified set (the line kept), else the recorded conversion rate of its class (double-dummy making / not).
Errors take the deal as the unit and treat the conversion rates as given.   usage: rule_diffs.py OUT.jsonl [...]"""
import json, sys, collections
def idx(r): return r['cards_list'].index(r['played'])
def cls(r, i, lev):
    cert = r['in0'][i] if lev == 0 or r['in2'] is None else r['in2'][i]
    return 'cert' if cert else 'dd' if r['dd_true'][i] else 'lost'
def pick(r, score, tie=None):
    s = [score(r, i) for i in range(len(r['cards_list']))]; m = max(s)
    best = [i for i, x in enumerate(s) if x >= m - 1e-9]
    if tie is not None and len(best) > 1:
        t = [tie(r, i) for i in best]; mt = max(t)
        best = [i for i, x in zip(best, t) if x >= mt - 1e-9]
    return best
def F(lev): return (lambda r, i: r['F0'][i]) if lev == 0 else (lambda r, i: (r['F2'] or r['F0'])[i])
Dv = lambda r, i: r['D'][i]
def mix(lev, k):
    f = F(lev); return lambda r, i: f(r, i) + k * (max(r['D'][i], f(r, i)) - f(r, i))
def clustered(rows, vals):
    by, cnt = collections.defaultdict(float), collections.Counter()
    for r, v in zip(rows, vals):
        by[r['board']] += v; cnt[r['board']] += 1
    n, g, tot = len(rows), len(by), sum(vals)
    m = tot / n
    return tot, (sum((by[b] - m * cnt[b]) ** 2 for b in by) * g / (g - 1)) ** .5
nc = [r for f in sys.argv[1:] for r in map(json.loads, open(f)) if not r['claim']]
k = nc[0]['cards']
for lev, tag in ((0, 'shape-level sets'), (2, 'sets with two named cards')):
    C = collections.defaultdict(list)
    for r in nc: C[cls(r, idx(r), lev)].append(r['made'])
    conv = dict(cert=1.0, dd=sum(C['dd']) / len(C['dd']), lost=sum(C['lost']) / len(C['lost']))
    def ev(r, best): return sum(conv[cls(r, i, lev)] for i in best) / len(best)
    base = [ev(r, pick(r, Dv, F(lev))) for r in nc]
    print('%d cards, %s, %d positions without an outright claim; conversion of double-dummy making but uncertified layouts %.3f, of the rest %.3f' % (k, tag, len(nc), conv['dd'], conv['lost']))
    print('   expected makes minus those of "double-dummy value, ties by certified probability" (%.1f):' % sum(base))
    for lab, score, tie in (('certified probability only, ties by double-dummy value', F(lev), Dv), ('certified + 0.25 x (DD - certified)', mix(lev, .25), None),
                            ('certified + 0.50 x (DD - certified)', mix(lev, .5), None), ('certified + 0.75 x (DD - certified)', mix(lev, .75), None),
                            ('double-dummy value, ties at random', Dv, None)):
        tot, se = clustered(nc, [ev(r, pick(r, score, tie)) - b for r, b in zip(nc, base)])
        print('      %-58s %+6.1f +- %.1f' % (lab, tot, se))
    print('   certified-only minus the same baseline, by the best certified probability in the position:')
    for lo, hi in ((.9, 1.01), (.75, .9), (.5, .75), (.25, .5), (1e-9, .25), (-1, 1e-9)):
        B = [r for r in nc if lo <= max(F(lev)(r, i) for i in range(len(r['cards_list']))) < hi]
        if not B: continue
        d = [ev(r, pick(r, F(lev), Dv)) - ev(r, pick(r, Dv, F(lev))) for r in B]
        differ = sum(1 for r in B if set(pick(r, F(lev), Dv)) != set(pick(r, Dv, F(lev))))
        print('      best certified %.2f to %.2f: %4d positions, the two rules differ in %3d, makes %+5.1f' % (max(lo, 0), min(hi, 1), len(B), differ, sum(d)))
