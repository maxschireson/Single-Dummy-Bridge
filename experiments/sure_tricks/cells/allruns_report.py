import json, sys, collections
def mean(v):
    v = list(v); return sum(v) / len(v) if v else float('nan')
for fn in sys.argv[1:]:
    R = [json.loads(l) for l in open(fn)]
    if not R: continue
    print('\n== %d cards: %d positions without an outright claim; %.1f runs of unseen cards a position' % (R[0]['cards'], len(R), mean(len(r['runs']) for r in R)))
    base = mean(r['base'] for r in R)
    best_all = [max([x['floor'] for x in r['runs']] + [r['base']]) for r in R]
    best_static = [max([x['floor'] for x in r['runs'] if x['static']] + [r['base']]) for r in R]
    print('   certified probability (scorer weights): shape only %.3f | best of the 3 cards my rule picks %.3f (+%.3f) | best of every run %.3f (+%.3f)' % (
        base, mean(best_static), mean(best_static) - base, mean(best_all), mean(best_all) - base))
    kinds = collections.Counter(); gain = collections.defaultdict(list); bigk = collections.Counter(); n_runs = collections.Counter()
    low_big = 0; big = 0; missed = 0
    for r in R:
        for x in r['runs']:
            n_runs[x['kind']] += 1
            gain[x['kind']].append(x['floor'] - r['base'])
        if not r['runs']: continue
        b = max(r['runs'], key=lambda x: x['floor'])
        g = b['floor'] - r['base']
        if g >= .05:
            big += 1
            bigk[b['kind']] += 1
            if b['card'][1] in '98765432': low_big += 1
            if not b['static'] and max([x['floor'] for x in r['runs'] if x['static']] + [r['base']]) < b['floor'] - .02: missed += 1
    print('   runs by class:', dict(n_runs))
    print('   mean gain when a run of the class is named:', {k: round(mean(v), 4) for k, v in gain.items()})
    print('   share of runs of the class that add 0.05 or more:', {k: round(mean(x >= .05 for x in v), 3) for k, v in gain.items()})
    print('   positions where the best run adds 0.05 or more: %d of %d; class of that run: %s; its card a nine or lower: %d' % (big, len(R), dict(bigk), low_big))
    print('   of those, the 3-card rule misses it by more than 0.02 in %d' % missed)
    # bottom / free runs specifically
    for kind in ('bottom', 'free'):
        pos_big = [r for r in R if any(x['kind'] == kind and x['floor'] - r['base'] >= .05 for x in r['runs'])]
        pos_any = [r for r in R if any(x['kind'] == kind for x in r['runs'])]
        g = [max(x['floor'] - r['base'] for x in r['runs'] if x['kind'] == kind) for r in pos_any]
        print('   %s runs: present in %d positions; best one adds 0.05 or more in %d (%.1f%%), 0.20 or more in %d; mean best gain %.4f' % (
            kind, len(pos_any), len(pos_big), 100 * len(pos_big) / max(1, len(pos_any)), sum(x >= .2 for x in g), mean(g)))
    down = [r for r in R if not r['made']]
    print('   went down: %d; sure on the actual layout: shape level %d, with the best run named %d, with the best of the 3-card rule %d' % (
        len(down), sum(r['true_in_base'] for r in down),
        sum(1 for r in down if r['true_in_base'] or (r['runs'] and max(r['runs'], key=lambda x: x['floor'])['true_in'])),
        sum(1 for r in down if r['true_in_base'] or any(x['static'] and x['true_in'] and x['floor'] == max([y['floor'] for y in r['runs'] if y['static']]) for x in r['runs']))))
    print('   cost in nodes, mean: shape level %d; one run named %d; every run %d' % (mean(r['base_nodes'] for r in R), mean(x['nodes'] for r in R for x in r['runs']), mean(sum(x['nodes'] for x in r['runs']) for r in R)))
