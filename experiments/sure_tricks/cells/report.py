"""Tables from the study's result files (two weightings: 'b' hand-fit scorer, 'u' uniform).

usage: report.py OUT.jsonl [OUT.jsonl ...] [--games | --partscores] [--bots 8s-32,8c-32]
"""
import json
import statistics as st
import sys


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else float('nan')


def mean(v):
    v = list(v)
    return sum(v) / len(v) if v else float('nan')


def sem(v):
    v = list(v)
    return st.pstdev(v) / len(v) ** .5 if len(v) > 1 else float('nan')


def pct(a, b):
    return '%d of %d (%.1f%%)' % (a, b, 100 * a / b if b else float('nan'))


def nodes_row(label, v):
    return '     %-34s %10d %10d %10d %10d %11d' % (label, q(v, .5), mean(v), q(v, .9), q(v, .99), max(v))


def main():
    files = [a for a in sys.argv[1:] if not a.startswith('--') and a.endswith('.jsonl')]
    R = [json.loads(l) for f in files for l in open(f)]
    if '--games' in sys.argv:
        R = [r for r in R if r['game']]
    if '--partscores' in sys.argv:
        R = [r for r in R if not r['game']]
    if '--bots' in sys.argv:
        keep = set(sys.argv[sys.argv.index('--bots') + 1].split(','))
        R = [r for r in R if r['bot'] in keep]
    keys = [k for k in ('b', 'u') if R and k in R[0]['shape']]
    label = {'b': 'scorer weights', 'u': 'uniform weights'}
    for k in sorted({r['cards'] for r in R}):
        A0 = [r for r in R if r['cards'] == k]
        A = [r for r in A0 if not r['shape']['capped'] and r['shape']['outright'] is not None]
        claim = [r for r in A if any(r['shape']['outright'].values())]
        rest = [r for r in A if not any(r['shape']['outright'].values())]
        print('\n==== %d cards left: %d positions (%d more dropped: a question hit the node cap)' % (k, len(A), len(A0) - len(A)))
        print('outright claim (some card guarantees the contract): ' + pct(len(claim), len(A)))
        print('no outright claim: %d' % len(rest))
        S = [r['shape'] for r in rest]
        print('  shapes per position: median %d, 90th pct %d, max %d' % (q([s['cells'] for s in S], .5), q([s['cells'] for s in S], .9), max(s['cells'] for s in S)))
        for key in keys:
            fl = [s[key]['best_floor'] for s in S]
            ce = [s[key]['best_ceiling'] for s in S]
            gap = [c - f for c, f in zip(ce, fl)]
            print('  -- %s, shape level' % label[key])
            print('     heaviest set one line wins (floor): mean %.3f +- %.3f, median %.3f' % (mean(fl), sem(fl), q(fl, .5)))
            print('     floor > 0: %s | >= 0.25: %s | >= 0.5: %s | >= 0.75: %s | >= 0.9: %s' % tuple(
                pct(sum(f >= t for f in fl), len(fl)) for t in (1e-9, .25, .5, .75, .9)))
            print('     ceiling (cells one at a time): mean %.3f; ceiling minus floor: mean %.3f; > 0.01: %s; > 0.10: %s' % (
                mean(ce), mean(gap), pct(sum(g > .01 for g in gap), len(gap)), pct(sum(g > .1 for g in gap), len(gap))))
            whole = [w for s in S for w in s[key]['whole'].values()]
            bw = [s[key]['whole'][s[key]['best']] for s in S if s[key]['best'] is not None]
            print('     joint step settled by its first question: all cards asked %s; best card %s' % (pct(sum(whole), len(whole)), pct(sum(bw), len(bw))))
            print('     cells holding 50%% / 90%% / 95%% / 99%% of the weight, median: %d / %d / %d / %d' % tuple(q([s[key]['mass_cells'][i] for s in S], .5) for i in range(4)))
            T = [r for r in rest if r['shape'][key]['true_in_best'] is not None]
            if T:
                hit = [r['shape'][key]['true_in_best'] for r in T]
                print('     actual layout inside the best card\'s set: %.1f%% +- %.1f; mean floor on the same positions %.1f%% (n = %d)' % (
                    100 * mean(hit), 100 * sem(hit), 100 * mean(r['shape'][key]['best_floor'] for r in T), len(T)))
                for lo, hi in ((0, .25), (.25, .5), (.5, .75), (.75, .9), (.9, 1.01)):
                    B = [r for r in T if lo <= r['shape'][key]['best_floor'] < hi]
                    if B:
                        print('        floor %.2f-%.2f: n %4d, mean floor %.3f, actual layout inside %.3f' % (lo, min(hi, 1), len(B), mean(r['shape'][key]['best_floor'] for r in B), mean(r['shape'][key]['true_in_best'] for r in B)))
            down = [r for r in rest if not r['made']]
            made = [r for r in rest if r['made']]
            sd = [r for r in down if r['shape'][key]['true_in_best']]
            sm = [r for r in made if not r['shape'][key]['true_in_best']]
            print('     went down from here: %d; best card\'s line was sure on the actual layout in %d' % (len(down), len(sd)))
            print('     made from here: %d; actual layout outside the best card\'s set in %d' % (len(made), len(sm)))
            same = [r for r in rest if r['shape'][key]['best'] == r['played']]
            pin = [r for r in rest if r['shape'][key]['true_in_played']]
            print('     bot played the best-floor card in %s; its own card had the actual layout in its set in %d, of which %d went down later' % (
                pct(len(same), len(rest)), len(pin), sum(not r['made'] for r in pin)))
        # cost
        print('  cost in nodes, all %d positions:           median       mean       90th       99th         max' % len(A))
        print(nodes_row('outright question', [r['shape']['outright_nodes'] for r in A]))
        print(nodes_row('one search per shape, all shapes', [r['shape']['single_nodes'] for r in A]))
        print(nodes_row('  per shape', [r['shape']['single_nodes'] / max(1, r['shape']['cells']) for r in A]))
        print(nodes_row('joint step (%s)' % label[keys[0]], [r['shape'][keys[0]]['joint_nodes'] for r in A]))
        print('  cost in nodes, the %d without an outright claim:' % len(rest))
        print(nodes_row('outright question', [r['shape']['outright_nodes'] for r in rest]))
        print(nodes_row('one search per shape, all shapes', [r['shape']['single_nodes'] for r in rest]))
        print(nodes_row('joint step (%s)' % label[keys[0]], [r['shape'][keys[0]]['joint_nodes'] for r in rest]))
        tot = [r['shape']['single_nodes'] + r['shape'][keys[0]]['joint_nodes'] for r in rest]
        print(nodes_row('shape level total', tot))
        if 'b' in keys:
            est = [r['shape']['single_nodes'] * r['shape']['b']['mass_cells'][3] / max(1, r['shape']['cells']) for r in rest]
            print(nodes_row('  searches for 99% of scorer weight*', est))
            est = [r['shape']['single_nodes'] * r['shape']['b']['mass_cells'][2] / max(1, r['shape']['cells']) for r in rest]
            print(nodes_row('  searches for 95% of scorer weight*', est))
            print('     * estimate: all-shape nodes scaled by the share of shapes needed, as if every shape cost the same')
        sec = [r['shape']['single_sec'] + r['shape'][keys[0]]['joint_sec'] for r in rest]
        print('     this solver, shape level: mean %.0f ms, median %.0f, 90th %.0f, 99th %.0f; %.0f ns a node in the per-shape searches, %.0f in the outright question' % (
            1000 * mean(sec), 1000 * q(sec, .5), 1000 * q(sec, .9), 1000 * q(sec, .99),
            1e9 * sum(r['shape']['single_sec'] for r in A) / max(1, sum(r['shape']['single_nodes'] for r in A)),
            1e9 * sum(r['shape']['outright_sec'] for r in A) / max(1, sum(r['shape']['outright_nodes'] for r in A))))
        qs = [r['shape'][keys[0]]['joint_queries'] for r in rest]
        print('     joint questions per position: median %d, mean %.0f, 90th %d' % (q(qs, .5), mean(qs), q(qs, .9)))
        # honours
        H = [r for r in rest if r.get('h1')]
        for key in keys:
            if not H:
                break
            base = [r['shape'][key]['best_floor'] for r in H]
            h1 = [max(h[key]['best_floor'] for h in r['h1']) for r in H]
            first = [r['h1'][0][key]['best_floor'] for r in H]
            print('  -- named honours, %s (%d positions with a candidate)' % (label[key], len(H)))
            print('     shape only %.3f | first candidate %.3f (+%.3f) | best of up to 3 single honours %.3f (+%.3f; +0.05 or more in %.1f%%)' % (
                mean(base), mean(first), mean(first) - mean(base), mean(h1), mean(h1) - mean(base), 100 * mean([a - b >= .05 for a, b in zip(h1, base)])))
            for hk in ('h2', 'h3'):
                HH = [r for r in H if r.get(hk)]
                if HH:
                    b2 = [r['shape'][key]['best_floor'] for r in HH]
                    v = [r[hk][key]['best_floor'] for r in HH]
                    cv = [r[hk][key]['best_ceiling'] for r in HH]
                    print('     %s (%d positions): floor %.3f against shape-only %.3f (+%.3f +- %.3f; +0.05 or more in %.1f%%; +0.20 or more in %.1f%%); ceiling %.3f; cells median %d; dropped weight max %.3f' % (
                        hk, len(HH), mean(v), mean(b2), mean(v) - mean(b2), sem([a - b for a, b in zip(v, b2)]), 100 * mean([a - b >= .05 for a, b in zip(v, b2)]),
                        100 * mean([a - b >= .2 for a, b in zip(v, b2)]), mean(cv), q([r[hk]['cells'] for r in HH], .5), max(r[hk][key]['dropped'] for r in HH)))
                    T = [r for r in HH if r[hk][key]['true_in_best'] is not None]
                    if T:
                        print('        actual layout inside the best set: %.1f%%; mean floor %.1f%% (n = %d)' % (100 * mean(r[hk][key]['true_in_best'] for r in T), 100 * mean(r[hk][key]['best_floor'] for r in T), len(T)))
                    down = [r for r in HH if not r['made']]
                    print('        went down from here: %d; best line sure on the actual layout in %d (shape level, same positions: %d)' % (
                        len(down), sum(1 for r in down if r[hk][key]['true_in_best']), sum(1 for r in down if r['shape'][key]['true_in_best'])))
        if H:
            k0 = keys[0]
            print('  cost in nodes with named honours (mean over the %d): shape level %d | one honour, each candidate %d | h2 %d | h3 %d' % (
                len(H), mean(r['shape']['single_nodes'] + r['shape'][k0]['joint_nodes'] for r in H),
                mean(h['single_nodes'] + h[k0]['joint_nodes'] for r in H for h in r['h1']),
                mean(r['h2']['single_nodes'] + r['h2'][k0]['joint_nodes'] for r in H if r.get('h2')) if any(r.get('h2') for r in H) else float('nan'),
                mean(r['h3']['single_nodes'] + r['h3'][k0]['joint_nodes'] for r in H if r.get('h3')) if any(r.get('h3') for r in H) else float('nan')))
            sf = sum(h['seed_failed'] for r in H for h in r['h1']) + sum(r[k2]['seed_failed'] for r in H for k2 in ('h2', 'h3') if r.get(k2))
            cp = sum(h['capped'] for r in H for h in r['h1']) + sum(r[k2]['capped'] for r in H for k2 in ('h2', 'h3') if r.get(k2))
            print('     refined sets that failed their check: %d; questions capped at the honour levels: %d' % (sf, cp))
        if claim:
            kept = [r for r in claim if r['shape']['outright'].get(r['played'])]
            print('  with an outright claim: bot played a guaranteeing card in %s; went down after having a claim: %d' % (pct(len(kept), len(claim)), sum(not r['made'] for r in claim)))
        print('  wall time per position in this study: mean %.1f s, max %.0f s' % (mean(r['seconds'] for r in A0), max(r['seconds'] for r in A0)))


if __name__ == '__main__':
    main()
