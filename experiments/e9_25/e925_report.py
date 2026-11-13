"""E9-25 report: the registered predictions (team/gen9:experiments/E9-25.md), g9, Gen 9.

Committed line: a position with no outright claim where a weighting's best card has a floor of 0.9 or more. It fails
when the actual layout's cell is outside that card's certified set. 'b' is the scorer's weighting, 'g' Gen 9's.

  (1) BEN defending, 8 and 7 cards pooled: committed lines fail at least 1.5 times as often with 'b' as with 'g'.
  (2) Where only one weighting commits: the scorer-only lines cover the actual layout less often than the Gen 9-only
      lines. Reported two ways, since 'discordant pairs' can be read two ways: Fisher's exact test on those two groups,
      and McNemar's exact test where both commit and exactly one covers.
  (3) Gen 9's failure rate with BEN defending is within 3 points of the house-defended control's.

usage: python3 e925_report.py DIR   (DIR holds ben_defends-8.jsonl, ben_defends-7.jsonl, house_defends-8.jsonl, ...)
"""
import json
import math
from pathlib import Path
import sys

FLOOR = .9


def rows(path):
    if not Path(path).exists():
        return []
    out = []
    for line in open(path):
        r = json.loads(line)
        s = r['shape']
        if s.get('outright') and any(s['outright'].values()):
            continue
        out.append(r)
    return out


def committed(r, key):
    s = r['shape'][key]
    return s['best'] is not None and s['best_floor'] >= FLOOR


def fails(r, key):
    return not r['shape'][key]['true_in_best']


def rate(rs, key):
    c = [r for r in rs if committed(r, key)]
    k = sum(fails(r, key) for r in c)
    n = len(c)
    p = k / n if n else float('nan')
    return k, n, p, math.sqrt(p * (1 - p) / n) if n else float('nan')


def binom_two_sided(k, n):
    """Exact two-sided binomial test of k in n at 1/2."""
    if n == 0:
        return float('nan')
    pk = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return min(1., sum(q for q in pk if q <= pk[k] + 1e-12))


def fisher_less(a, b, c, d):
    """One-sided Fisher exact p that the first row's success share is lower: [[a, b], [c, d]], a and c successes."""
    n1, n2, s = a + b, c + d, a + c
    tot = math.comb(n1 + n2, s)
    return sum(math.comb(n1, i) * math.comb(n2, s - i) for i in range(0, a + 1) if 0 <= s - i <= n2) / tot


def main(d):
    d = Path(d)
    ben = rows(d / 'ben_defends-8.jsonl') + rows(d / 'ben_defends-7.jsonl')
    house = rows(d / 'house_defends-8.jsonl') + rows(d / 'house_defends-7.jsonl')
    readers = sorted({r.get('g_reader', '?') for r in ben})
    print(f'positions without an outright claim: BEN defending {len(ben)}, house defending {len(house)}; Gen 9 reader {readers}')
    for name, rs in (('BEN defending', ben), ('house defending', house)):
        for cards in (8, 7, None):
            sub = [r for r in rs if cards is None or r['cards'] == cards]
            kb, nb, pb, sb = rate(sub, 'b')
            kg, ng, pg, sg = rate(sub, 'g')
            label = f'{cards} cards' if cards else 'pooled'
            print(f'  {name}, {label}: committed lines that fail: scorer {kb}/{nb} = {pb:.3f} +- {sb:.3f}; Gen 9 {kg}/{ng} = {pg:.3f} +- {sg:.3f}')
    kb, nb, pb, sb = rate(ben, 'b')
    kg, ng, pg, sg = rate(ben, 'g')
    if not nb or not ng or (kb == 0 and kg == 0):
        print('\n(1) no committed line failed with either weighting, or none committed: the ratio is undefined')
        ratio = float('nan')
    else:
        ratio = pb / pg if pg else float('inf')
    lr_se = math.sqrt((1 - pb) / kb + (1 - pg) / kg) if kb and kg else float("nan")     # as if independent: the pairs make it wider than needed
    lo, hi = (ratio * math.exp(-1.96 * lr_se), ratio * math.exp(1.96 * lr_se)) if kb and kg else (float('nan'),) * 2
    if ratio == ratio:
        print(f'\n(1) failure ratio scorer / Gen 9, BEN defending: {ratio:.2f} (95% interval {lo:.2f} to {hi:.2f}); prediction: at least 1.5 -> '
              f'{"met" if ratio >= 1.5 else "not met"} on the point estimate')
    only_b = [r for r in ben if committed(r, 'b') and not committed(r, 'g')]
    only_g = [r for r in ben if committed(r, 'g') and not committed(r, 'b')]
    cb, cg = sum(not fails(r, 'b') for r in only_b), sum(not fails(r, 'g') for r in only_g)
    p_f = fisher_less(cb, len(only_b) - cb, cg, len(only_g) - cg) if only_b and only_g else float('nan')
    print(f'(2a) only one weighting commits: scorer-only lines cover {cb}/{len(only_b)}, Gen 9-only lines cover {cg}/{len(only_g)}; '
          f'Fisher one-sided p = {p_f:.4f}')
    both = [r for r in ben if committed(r, 'b') and committed(r, 'g')]
    b01 = sum(fails(r, 'b') and not fails(r, 'g') for r in both)
    b10 = sum(not fails(r, 'b') and fails(r, 'g') for r in both)
    print(f'(2b) both commit ({len(both)}): only Gen 9 covers {b01}, only the scorer covers {b10}; McNemar exact p = {binom_two_sided(min(b01, b10), b01 + b10):.4f}')
    kh, nh, ph, sh = rate(house, 'g')
    if ng and nh:
        print(f'(3) Gen 9 failure rate, BEN defending {pg:.3f} against house defending {ph:.3f}: difference {pg - ph:+.3f} '
              f'+- {math.sqrt(sg ** 2 + sh ** 2):.3f}; prediction: within 0.03 -> {"met" if abs(pg - ph) <= .03 else "not met"} on the point estimate')
    else:
        print('(3) no committed lines in one of the populations')


if __name__ == '__main__':
    main(sys.argv[1])
