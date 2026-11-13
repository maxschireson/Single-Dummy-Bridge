"""E9-24 report: claimed against realised, by weighting and population (g9, Gen 9).

usage: python3 e924_report.py prec8.jsonl house8.jsonl [prec7.jsonl house7.jsonl]
"""
import json
import math
import sys
from collections import defaultdict

BANDS = [(0, .25), (.25, .5), (.5, .75), (.75, .9), (.9, 1.01)]


def rows(path):
    out = []
    for line in open(path):
        r = json.loads(line)
        s = r['shape']
        if s.get('outright') and any(s['outright'].values()):
            continue                                   # an outright claim: no conditional question
        out.append(r)
    return out


def se_mean(xs):
    n = len(xs)
    if n < 2:
        return float('nan')
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)


def report(path):
    R = rows(path)
    total = sum(1 for _ in open(path))
    kind = R[0]['kind'] if R else '?'
    print(f'\n## {path}: {kind}, {total} positions, {len(R)} without an outright claim')
    for key, label in (('b', 'scorer'), ('g', 'Gen 9')):
        print(f'\n{label}: | floor band | positions | mean floor | true layout inside the best card\'s set |')
        gaps = []
        for lo, hi in BANDS:
            sel = [r for r in R if r['shape'][key]['best'] is not None and lo <= r['shape'][key]['best_floor'] < hi]
            if not sel:
                continue
            mf = sum(r['shape'][key]['best_floor'] for r in sel) / len(sel)
            inside = [1. if r['shape'][key]['true_in_best'] else 0. for r in sel]
            print(f'  | {lo:.2f} to {min(hi, 1):.2f} | {len(sel)} | {mf:.3f} | {sum(inside) / len(sel):.3f} +- {se_mean(inside):.3f} |')
        over = [r['shape'][key]['best_floor'] - (1. if r['shape'][key]['true_in_best'] else 0.)
                for r in R if r['shape'][key]['best'] is not None and r['shape'][key]['best_floor'] >= .25]
        allf = [r['shape'][key]['best_floor'] for r in R if r['shape'][key]['best'] is not None]
        inside_all = [1. if r['shape'][key]['true_in_best'] else 0. for r in R if r['shape'][key]['best'] is not None]
        print(f'  floors of 0.25 or more: {len(over)} positions, floor minus realised {sum(over) / max(len(over), 1):+.3f} +- {se_mean(over):.3f}')
        print(f'  all: mean floor {sum(allf) / max(len(allf), 1):.3f}, realised {sum(inside_all) / max(len(inside_all), 1):.3f} +- {se_mean(inside_all):.3f}')
    # paired: same positions, both weightings
    both = [r for r in R if r['shape']['b']['best'] is not None and r['shape']['g']['best'] is not None]
    diff_card = [r for r in both if r['shape']['b']['best'] != r['shape']['g']['best']]
    d_in = [(1. if r['shape']['g']['true_in_best'] else 0.) - (1. if r['shape']['b']['true_in_best'] else 0.) for r in both]
    print(f'\npaired ({len(both)} positions): best card differs in {len(diff_card)}; true layout inside the best set, Gen 9 minus scorer {sum(d_in) / max(len(d_in), 1):+.3f} +- {se_mean(d_in):.3f}')
    if diff_card:
        dd = [(1. if r['shape']['g']['true_in_best'] else 0.) - (1. if r['shape']['b']['true_in_best'] else 0.) for r in diff_card]
        print(f'  where the best card differs: Gen 9 minus scorer {sum(dd) / len(dd):+.3f} +- {se_mean(dd):.3f}')
    zb = sum(1 for r in R if r.get('true_w_b') is not None and r['true_w_b'] * r['layouts'] < 0.01)
    zg = sum(1 for r in R if r.get('true_w_g') is not None and r['true_w_g'] * r['layouts'] < 0.01)
    print(f'  true layout weighted below 1% of uniform: scorer {zb}, Gen 9 {zg} (of {len(R)})')
    print(f'  effective layouts, median: scorer {sorted(r["eff_b"] for r in R)[len(R) // 2]:.0f}, Gen 9 {sorted(r["eff_g"] for r in R)[len(R) // 2]:.0f}')
    print(f'  seconds a position, mean: weights {sum(r["sec_weights"] for r in R) / len(R):.2f}, solver {sum(r["sec_solver"] for r in R) / len(R):.2f}')


for path in [a for a in sys.argv[1:] if not a.startswith('--') and not a.endswith('n.jsonl')]:
    report(path)


def report_named(path):
    """Two named cards (the study's h2), each weighting choosing its own two runs."""
    R = [json.loads(l) for l in open(path)]
    R = [r for r in R if 'h2_b' in r and 'h2_g' in r]
    print(f'\n## {path}: two named cards, {len(R)} positions without an outright claim')
    for key, label in (('b', 'scorer'), ('g', 'Gen 9')):
        H = [r['h2_' + key][key] for r in R if r['h2_' + key][key]['best'] is not None]
        print(f'\n{label}: | floor band | positions | mean floor | true layout inside |')
        for lo, hi in BANDS:
            sel = [h for h in H if lo <= h['best_floor'] < hi]
            if sel:
                ins = [1. if h['true_in_best'] else 0. for h in sel]
                print(f'  | {lo:.2f} to {min(hi, 1):.2f} | {len(sel)} | {sum(h["best_floor"] for h in sel) / len(sel):.3f} | {sum(ins) / len(sel):.3f} +- {se_mean(ins):.3f} |')
        over = [h['best_floor'] - (1. if h['true_in_best'] else 0.) for h in H if h['best_floor'] >= .25]
        ins = [1. if h['true_in_best'] else 0. for h in H]
        print(f'  floors of 0.25 or more: {len(over)}, floor minus realised {sum(over) / max(len(over), 1):+.3f} +- {se_mean(over):.3f}; '
              f'all: mean floor {sum(h["best_floor"] for h in H) / max(len(H), 1):.3f}, realised {sum(ins) / max(len(ins), 1):.3f} +- {se_mean(ins):.3f}')
    both = [r for r in R if r['h2_b']['b']['best'] is not None and r['h2_g']['g']['best'] is not None]
    d = [(1. if r['h2_g']['g']['true_in_best'] else 0.) - (1. if r['h2_b']['b']['true_in_best'] else 0.) for r in both]
    diff = [r for r in both if (r['h2_g']['g']['best'], tuple(r['h2_g'].get('named', ()))) != (r['h2_b']['b']['best'], tuple(r['h2_b'].get('named', ())))]
    print(f'\npaired ({len(both)}): line (card or named cards) differs in {len(diff)}; true layout inside the best set, Gen 9 minus scorer {sum(d) / max(len(d), 1):+.3f} +- {se_mean(d):.3f}')


if '--named' in sys.argv:
    for path in [a for a in sys.argv[1:] if a.endswith('n.jsonl')]:
        report_named(path)
