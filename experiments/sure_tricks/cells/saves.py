"""What following the best-floor card's certified line would have changed, from the recorded results.
usage: saves.py KEY(b|u) OUT8... -- OUT7...   (files for one card count before --, another after)"""
import json, sys
key = sys.argv[1]
args = sys.argv[2:]
groups = [args[:args.index('--')], args[args.index('--') + 1:]] if '--' in args else [args]
tables = {}
for files in groups:
    R = [json.loads(l) for f in files for l in open(f)]
    k = R[0]['cards']
    rest = [r for r in R if r['shape']['outright'] is not None and not any(r['shape']['outright'].values())]
    claim = [r for r in R if r['shape']['outright'] is not None and any(r['shape']['outright'].values())]
    print('\n== %d cards: %d positions, %d without an outright claim' % (k, len(R), len(rest)))
    lost_claim = [r for r in claim if not r['made']]
    print('   outright claim then went down: %d (games/slams/doubled: %d)' % (len(lost_claim), sum(r['game'] for r in lost_claim)))
    for r in lost_claim:
        tables.setdefault(r['table'], set()).add('claim')
    for lev in ('shape', 'h2'):
        X = [r for r in rest if r.get(lev)]
        def L(r): return r[lev][key]
        same = [r for r in X if L(r)['best'] == r['played']]
        diff = [r for r in X if L(r)['best'] is not None and L(r)['best'] != r['played']]
        none = [r for r in X if L(r)['best'] is None]
        print('   -- level %s (%d positions; no card has a set in %d)' % (lev, len(X), len(none)))
        a = [r for r in diff if not r['made'] and L(r)['true_in_best']]
        b = [r for r in diff if r['made'] and not L(r)['true_in_best']]
        c = [r for r in diff if r['made'] and L(r)['true_in_best']]
        d = [r for r in diff if not r['made'] and not L(r)['true_in_best']]
        print('      bot played another card than the best-floor card: %d' % len(diff))
        print('         went down, best line sure on the actual layout (would have made): %d (games etc: %d)' % (len(a), sum(r['game'] for r in a)))
        print('         made, actual layout outside the best set (result after switching unknown): %d (games etc: %d)' % (len(b), sum(r['game'] for r in b)))
        print('         made, actual layout inside the best set (no change): %d' % len(c))
        print('         went down, actual layout outside the best set (unknown, probably down): %d' % len(d))
        e = [r for r in same if not r['made'] and L(r)['true_in_best']]
        print('      bot played the best-floor card: %d; of these went down although its line was sure on the actual layout (later deviation): %d (games etc: %d)' % (len(same), len(e), sum(r['game'] for r in e)))
        g = [r for r in X if not r['made'] and L(r)['true_in_played'] and not (L(r)['best'] == r['played'])]
        print('      bot played another card whose own set held the actual layout, then went down: %d' % len(g))
        # by floor threshold
        for t in (.5, .75, .9):
            aa = [r for r in a if L(r)['best_floor'] >= t]
            bb = [r for r in b if L(r)['best_floor'] >= t]
            dd = [r for r in diff if L(r)['best_floor'] >= t]
            print('         best floor >= %.2f: other card played %d; would have made %d; made with layout outside the set %d' % (t, len(dd), len(aa), len(bb)))
        if lev == 'h2':
            for r in a + e:
                tables.setdefault(r['table'], set()).add('h2-%d' % k)
        else:
            for r in a + e:
                tables.setdefault(r['table'], set()).add('shape-%d' % k)
print('\ntables with a sure make that went down, by where it shows:')
import collections
print('  any outright claim lost (8 or 7 cards):', sum(1 for v in tables.values() if 'claim' in v))
print('  shape-level line (8 or 7 cards), not counting tables already in the line above:', sum(1 for v in tables.values() if 'claim' not in v and any(x.startswith('shape') for x in v)))
print('  two-honour line only:', sum(1 for v in tables.values() if 'claim' not in v and not any(x.startswith('shape') for x in v)))
print('  all:', len(tables))
