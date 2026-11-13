import json, sys
def q(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))] if v else float('nan')
def mean(v):
    v = list(v); return sum(v) / len(v) if v else float('nan')
for fn in sys.argv[1:]:
    R = [json.loads(l) for l in open(fn)]
    ok = [r for r in R if not r.get('capped')]
    if not ok:
        continue
    k = ok[0]['cards']
    print('\n== %d cards: %d positions (%d capped)' % (k, len(ok), len(R) - len(ok)))
    def upto(r, share):
        t, n = 0., 0
        for x in r['weights']:
            if t >= share - 1e-9: break
            t += x; n += 1
        return n
    rows = [('outright question', [r['outright']['nodes'] for r in ok], [r['outright']['nodes'] - r['outright']['low'] + r['outright']['b4'] for r in ok])]
    for share, lab in ((1.01, 'per-shape searches, every shape'), (.99, 'per-shape searches, 99% of scorer weight'), (.95, 'per-shape searches, 95% of scorer weight')):
        full, tab = [], []
        for r in ok:
            n = upto(r, share)
            full.append(sum(r['single_nodes'][:n]))
            tab.append(sum(a - l + b for a, l, b in zip(r['single_nodes'][:n], r['single_low'][:n], r['single_b4'][:n])))
        rows.append((lab, full, tab))
    rows.append(('  one card only, every shape', [sum(r['one_card_nodes']) for r in ok], None))
    rows.append(('  one card only, 99% of weight', [sum(r['one_card_nodes'][:upto(r, .99)]) for r in ok], None))
    rows.append(('joint step, best card', [r['joint']['nodes'] for r in ok], [r['joint']['nodes'] - r['joint']['low'] + r['joint']['b4'] for r in ok]))
    print('   %-44s %9s %9s %9s %9s | above a 4-card table (nodes + lookups): %9s %9s %9s' % ('nodes', 'median', 'mean', '90th', '99th', 'median', 'mean', '90th'))
    for lab, full, tab in rows:
        line = '   %-44s %9d %9d %9d %9d' % (lab, q(full, .5), mean(full), q(full, .9), q(full, .99))
        if tab is not None:
            line += ' | %48d %9d %9d' % (q(tab, .5), mean(tab), q(tab, .9))
        print(line)
    print('   shapes: median %d, mean %.0f; for 99%% of scorer weight: median %d, mean %.0f; for 95%%: median %d, mean %.0f' % (
        q([r['shapes'] for r in ok], .5), mean(r['shapes'] for r in ok), q([upto(r, .99) for r in ok], .5), mean(upto(r, .99) for r in ok), q([upto(r, .95) for r in ok], .5), mean(upto(r, .95) for r in ok)))
    print('   legal runs: mean %.1f; all cards / one card, per-shape nodes: %.1f' % (mean(r['runs'] for r in ok), sum(sum(r['single_nodes']) for r in ok) / max(1, sum(sum(r['one_card_nodes']) for r in ok))))
    nc = [r for r in ok if not r['outright']['claim']]
    print('   without an outright claim (%d): per-shape searches for 99%% of weight: mean %d nodes, median %d; joint mean %d' % (
        len(nc), mean(sum(r['single_nodes'][:upto(r, .99)]) for r in nc), q([sum(r['single_nodes'][:upto(r, .99)]) for r in nc], .5), mean(r['joint']['nodes'] for r in nc)))
    print('   time in this solver: per-shape searches %.0f ms mean; whole position %.1f s mean' % (1000 * mean(r['single_sec'] for r in ok), mean(r['seconds'] for r in ok)))
