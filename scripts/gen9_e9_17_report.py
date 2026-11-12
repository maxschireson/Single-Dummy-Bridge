#!/usr/bin/env python3
"""E9-17's numbers: each reader against each stand-in, and the paired differences between readers on the same deals.

Reads RUNS/<reader>~<stand-in>/results.jsonl (scripts/gen9_match.py output, seed 917, deals 0..399) and writes a JSON
summary and a markdown table. IMPs a board from the reader's side; standard errors by deal; paired differences over
the deals both matches played.

    python scripts/gen9_e9_17_report.py --runs ~/e917runs --out reports/gen9-e9-17-2026-11-12
"""
import argparse
import json
import math
from pathlib import Path

READERS = ('r9t-32', '8x-32', '8p-32')
STANDINS = ('t-high', 't-low', 't-random')
PAIRS = (('r9t-32', '8x-32'), ('r9t-32', '8p-32'), ('8x-32', '8p-32'))


def stats(xs):
    n = len(xs)
    if n == 0:
        return dict(n=0, mean=None, se=None)
    m = sum(xs) / n
    se = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else None
    return dict(n=n, mean=round(m, 4), se=None if se is None else round(se, 4))


def load(runs, reader, standin):
    path = Path(runs) / f'{reader}~{standin}' / 'results.jsonl'
    if not path.exists():
        return {}
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    return {r['index']: r for r in rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = dict(schema='gen9-e9-17-v1', seed=917, matches={}, paired={})
    L = ['| Stand-in | Reader | Boards | Native IMPs a board (SE) | Common (SE) |', '| --- | --- | ---: | --- | --- |']
    P = ['| Stand-in | Difference | Deals | Native (SE) | Common (SE) |', '| --- | --- | ---: | --- | --- |']
    f = lambda s: '—' if s['mean'] is None else f"{s['mean']:+.3f}" + (f" ({s['se']:.3f})" if s['se'] is not None else '')
    for t in STANDINS:
        rows = {r: load(a.runs, r, t) for r in READERS}
        for r in READERS:
            if not rows[r]:
                continue
            nat = stats([x['native'] for x in rows[r].values() if x.get('native') is not None])
            com = stats([x['common'] for x in rows[r].values() if x.get('common') is not None])
            out['matches'][f'{r}~{t}'] = dict(native=nat, common=com, boards=len(rows[r]),
                                             cpu=round(sum(x.get('cpu', 0) for x in rows[r].values()) / max(len(rows[r]), 1), 2))
            L.append(f'| {t} | `{r}` | {len(rows[r])} | {f(nat)} | {f(com)} |')
        for x, y in PAIRS:
            both = sorted(set(rows[x]) & set(rows[y]))
            if not both:
                continue
            nat = stats([rows[x][i]['native'] - rows[y][i]['native'] for i in both
                         if rows[x][i].get('native') is not None and rows[y][i].get('native') is not None])
            com = stats([rows[x][i]['common'] - rows[y][i]['common'] for i in both
                         if rows[x][i].get('common') is not None and rows[y][i].get('common') is not None])
            same = sum(1 for i in both if rows[x][i].get('auction_len') == rows[y][i].get('auction_len') and rows[x][i].get('contract') == rows[y][i].get('contract'))
            out['paired'][f'{x}-{y}~{t}'] = dict(native=nat, common=com, deals=len(both), same_contract=same)
            P.append(f'| {t} | `{x}` minus `{y}` | {len(both)} | {f(nat)} | {f(com)} |')
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'result.json').write_text(json.dumps(out, indent=1) + '\n')
    text = '\n'.join(['# E9-17: each reader against each stand-in (seed 917, the same deals)', '', *L, '', '## Paired by deal', '', *P, ''])
    (a.out / 'tables.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
