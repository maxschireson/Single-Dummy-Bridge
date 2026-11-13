"""How the card each rule picks fared on the actual layout, and what double-dummy-making but uncertified layouts
convert to in recorded play.   usage: ddrules_report.py OUT.jsonl [OUT.jsonl ...]"""
import json, sys, collections
def mean(v):
    v = list(v); return sum(v) / len(v) if v else float('nan')
R = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
nc = [r for r in R if not r['claim']]
print('%d positions, %d without an outright claim' % (len(R), len(nc)))
bad = sum(1 for r in nc for a, t in zip(r['in0'], r['dd_true']) if a and not t) + sum(1 for r in nc if r['in2'] for a, t in zip(r['in2'], r['dd_true']) if a and not t)
print('certified on the actual layout but not double-dummy making there (must be 0): %d' % bad)

def idx(r): return r['cards_list'].index(r['played'])
def cls(r, i, lev):
    cert = r['in0'][i] if lev == 0 or r['in2'] is None else r['in2'][i]
    return 'cert' if cert else 'dd' if r['dd_true'][i] else 'lost'

# ---- the bot's own card: what each class converts to
for lev, lab in ((0, 'shape level'), (2, 'two named cards')):
    C = collections.defaultdict(list)
    for r in nc:
        C[cls(r, idx(r), lev)].append(r['made'])
    print('\nthe card the bot played, by what the actual layout was for it (%s):' % lab)
    for k, t in (('cert', 'inside its certified set'), ('dd', 'double-dummy making, not certified'), ('lost', 'not double-dummy making')):
        v = C[k]
        se = (mean(v) * (1 - mean(v)) / len(v)) ** .5 if v else float('nan')
        print('   %-38s %4d positions, made %5.1f%% +- %.1f' % (t, len(v), 100 * mean(v), 100 * se))
    rates = {k: mean(C[k]) for k in C}
    if lev == 0: rates0 = rates
    else: rates2 = rates
print('   overall made: %.1f%%' % (100 * mean(r['made'] for r in nc)))

# ---- double-dummy value of the bot's card against what happened
print('\nthe bot\'s card by its double-dummy value D (share of 256 sampled layouts in which it makes):')
for lo, hi in ((.999, 1.01), (.9, .999), (.75, .9), (.5, .75), (.25, .5), (0, .25)):
    B = [r for r in nc if lo <= r['D'][idx(r)] < hi]
    if B:
        print('   D %.2f-%.2f: %4d positions, mean D %.3f, made %.3f | mean certified (shape) %.3f, (two named) %.3f' % (
            max(lo, 0), min(hi, 1), len(B), mean(r['D'][idx(r)] for r in B), mean(r['made'] for r in B), mean(r['F0'][idx(r)] for r in B),
            mean((r['F2'] or r['F0'])[idx(r)] for r in B)))
print('the bot\'s card with D of 0.999 or more, by its certified probability (shape level):')
for lo, hi in ((.9, 1.01), (.5, .9), (.0001, .5), (-1, .0001)):
    B = [r for r in nc if r['D'][idx(r)] >= .999 and lo <= r['F0'][idx(r)] < hi]
    if B:
        print('   certified %.2f-%.2f: %4d positions, made %.3f' % (max(lo, 0), min(hi, 1), len(B), mean(r['made'] for r in B)))
print('the same with two named cards:')
for lo, hi in ((.9, 1.01), (.5, .9), (.0001, .5), (-1, .0001)):
    B = [r for r in nc if r['D'][idx(r)] >= .999 and lo <= (r['F2'] or r['F0'])[idx(r)] < hi]
    if B:
        print('   certified %.2f-%.2f: %4d positions, made %.3f' % (max(lo, 0), min(hi, 1), len(B), mean(r['made'] for r in B)))

# ---- rules
def pick(r, score, tie=None):
    s = [score(r, i) for i in range(len(r['cards_list']))]
    m = max(s)
    best = [i for i, x in enumerate(s) if x >= m - 1e-9]
    if tie is not None and len(best) > 1:
        t = [tie(r, i) for i in best]
        mt = max(t)
        best = [i for i, x in zip(best, t) if x >= mt - 1e-9]
    return best
def F(lev):
    return (lambda r, i: r['F0'][i]) if lev == 0 else (lambda r, i: (r['F2'] or r['F0'])[i])
Dv = lambda r, i: r['D'][i]
def mix(lev, k):
    f = F(lev)
    return lambda r, i: f(r, i) + k * (max(r['D'][i], f(r, i)) - f(r, i))
rules = [('the bot (as played)', None, None, 0)]
for lev, tag in ((0, 'shape'), (2, '2 named')):
    rules += [('DD value; ties at random', Dv, None, lev), ('DD value; ties by certified (%s)' % tag, Dv, F(lev), lev),
              ('certified only (%s); ties by DD' % tag, F(lev), Dv, lev)]
    rules += [('certified + %.2f x (DD - certified) (%s)' % (k, tag), mix(lev, k), None, lev) for k in (.25, .5, .75)]
for lev in (0, 2):
    rates = rates0 if lev == 0 else rates2
    print('\nwhat the card each rule picks was on the actual layout (%s sets); n = %d' % ('shape-level' if lev == 0 else 'two-named', len(nc)))
    print('   %-52s %9s %9s %9s | makes expected: line kept / as these bots convert' % ('rule', 'certified', 'DD only', 'DD-lost'))
    for name_, score, tie, rl in rules:
        if rl != lev and score is not None:
            continue
        tot = collections.Counter()
        for r in nc:
            best = [idx(r)] if score is None else pick(r, score, tie)
            for i in best:
                tot[cls(r, i, lev)] += 1 / len(best)
        e_keep = tot['cert'] * 1.0 + tot['dd'] * rates['dd'] + tot['lost'] * rates['lost']
        e_bots = tot['cert'] * rates['cert'] + tot['dd'] * rates['dd'] + tot['lost'] * rates['lost']
        print('   %-52s %9.1f %9.1f %9.1f | %6.1f / %6.1f' % (name_, tot['cert'], tot['dd'], tot['lost'], e_keep, e_bots))
print('\n(the bot actually made %d of these %d)' % (sum(r['made'] for r in nc), len(nc)))

# ---- where the certified rule and the DD rule part
for lev, tag in ((0, 'shape'), (2, 'two named')):
    J = collections.Counter(); n = 0
    for r in nc:
        a = pick(r, F(lev), Dv); b = pick(r, Dv, F(lev))
        if set(a) == set(b):
            continue
        n += 1
        for i in a:
            for j in b:
                J[(cls(r, i, lev), cls(r, j, lev))] += 1 / (len(a) * len(b))
    print('\ncertified-first and DD-first pick different cards in %d positions (%s). Their cards on the actual layout (certified-first / DD-first):' % (n, tag))
    for k in sorted(J, key=lambda k: -J[k]):
        print('   %-5s / %-5s %7.1f' % (k[0], k[1], J[k]))
# ---- ties
t = [r for r in nc if len(pick(r, Dv)) > 1]
t2 = [r for r in t if max(r['F0'][i] for i in pick(r, Dv)) - min(r['F0'][i] for i in pick(r, Dv)) > .05]
print('\nDD value ties at the top between two or more cards: %d of %d; of these the tied cards differ by more than 0.05 in certified probability (shape): %d' % (len(t), len(nc), len(t2)))
top = [r for r in nc if max(r['D']) >= .999]
print('some card has D of 0.999 or more: %d; the best certified probability there: mean %.3f (shape), %.3f (two named); made %.1f%%' % (
    len(top), mean(max(r['F0']) for r in top), mean(max(r['F2'] or r['F0']) for r in top), 100 * mean(r['made'] for r in top)))
