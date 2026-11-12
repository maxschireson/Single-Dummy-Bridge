#!/usr/bin/env python3
"""Two matches on the same deals (same --seed), each candidate against the same opponent: the paired difference.

E9-4 part 2 (sam): candidate A (e.g. the signal reader r9-32) and candidate B (its control 8x-32) each played the
carding bot on the same deals. Per deal index, A's IMPs minus B's; mean and standard error over the deals both
matches played, beside each match's own mean.

  python scripts/gen9_paired_match.py RUN_A/results.jsonl RUN_B/results.jsonl [--regime common|native]
"""
import argparse
import json
import math


def load(path, regime):
    out = {}
    for line in open(path):
        r = json.loads(line)
        out[r['index']] = float(r[regime])
    return out


def mean_se(xs):
    n = len(xs)
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else float('nan')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--regime', default='common')
    args = ap.parse_args()
    a, b = load(args.a, args.regime), load(args.b, args.regime)
    both = sorted(set(a) & set(b))
    ma, sa = mean_se([a[i] for i in both])
    mb, sb = mean_se([b[i] for i in both])
    md, sd = mean_se([a[i] - b[i] for i in both])
    print(f'{len(both)} deals played by both; A {ma:+.3f} ± {sa:.3f}, B {mb:+.3f} ± {sb:.3f} IMPs a board; A minus B {md:+.3f} ± {sd:.3f}')
    print(json.dumps(dict(deals=len(both), a=dict(mean=ma, se=sa), b=dict(mean=mb, se=sb), difference=dict(mean=md, se=sd))))


if __name__ == '__main__':
    main()
