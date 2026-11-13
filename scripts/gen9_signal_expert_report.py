#!/usr/bin/env python3
"""E9-15's tables from scripts/gen9_signal_expert.py's output folder (occasions_report.json, rows.jsonl).

  python scripts/gen9_signal_expert_report.py DIR > tables.md
"""
import json
from pathlib import Path
import sys

import numpy as np

VERSIONS = (('ben', 'BEN 16'), ('ben64', 'BEN 64'))
KEYS = ('partner_lead', 'declarer_lead', 'first_discard', 'trump', 'partner_lead.r2', 'declarer_lead.r2', 'trump.r2')


def clustered(v, groups):
    v = np.asarray(v, float)
    _, inv = np.unique(groups, return_inverse=True)
    tot, cnt = np.bincount(inv, v), np.bincount(inv)
    m = tot.sum() / cnt.sum()
    k = len(cnt)
    return m, (np.sqrt(((tot - m * cnt) ** 2).sum() * k / (k - 1)) / cnt.sum() if k > 1 else float('nan'))


def pm(x, k=3):
    return f'{x[0]:+.{k}f} ± {x[1]:.{k}f}'


def main():
    d = Path(sys.argv[1])
    occ = json.loads((d / 'occasions_report.json').read_text())
    rows = [json.loads(line) for line in open(d / 'rows.jsonl')] if (d / 'rows.jsonl').exists() else []
    print('## 1. Held-out log-likelihood of the spot played, nats an occasion over a uniform choice in its class\n')
    names = ['m0 (E9-7 symmetric)', 'E9-7 tables', 'm1 all', 'm2 all', 'm3 all', 'm3 other version']
    for ben, label in VERSIONS:
        e = occ['loglik'][ben]
        print(f"**{label}**: {e['occasions']:,} occasions on {e['tables']} held-out tables.\n")
        print('| Model | all | ' + ' | '.join(KEYS) + ' |')
        print('| --- |' + ' ---: |' * (len(KEYS) + 1))
        for n in names:
            m = e['models'][n]
            print(f'| {n} | {pm(m["all"])} | ' + ' | '.join(f'{m[k][0]:+.3f}' if k in m else '' for k in KEYS) + ' |')
        print()
    print('Curve over tables of experience (mean of the 5 subsets; all = every fit table), nats an occasion:\n')
    print('| Version | Model | 50 | 200 | 1,000 | all |')
    print('| --- | --- | ---: | ---: | ---: | ---: |')
    for ben, label in VERSIONS:
        e = occ['loglik'][ben]['models']
        for m in ('m1', 'm2', 'm3'):
            cells = []
            for n in ('n50', 'n200', 'n1000'):
                vals = [e[k]['all'][0] for k in e if k.startswith(f'{m} {n}.')]
                cells.append(f'{np.mean(vals):+.3f} (±{np.std(vals):.3f})' if vals else '')
            cells.append(f"{e[f'{m} all']['all'][0]:+.3f}")
            print(f'| {label} | {m} | ' + ' | '.join(cells) + ' |')
    print()
    if rows:
        print("## 2. Reading gain at the house declarer's decisions, tricks 1 to 6: nats a decision\n")
        readers = list(rows[0]['gains'])
        for ben, label in VERSIONS:
            rs = [r for r in rows if r['ben'] == ben]
            if not rs:
                continue
            g = np.array([[r['gains'][k] for k in readers] for r in rs])
            tables = np.array([f"{r['episode']}/{r['table']}" for r in rs])
            ref = readers.index('E9-7 tables')
            gen8 = readers.index('gen8 (net 0.3)')
            print(f'**{label}**: {len(rs):,} decisions on {len(set(tables))} tables.\n')
            print('| Reader | Gain | Against Gen 8 | Against E9-7 tables |')
            print('| --- | ---: | ---: | ---: |')
            for j, k in enumerate(readers):
                print(f'| {k} | {pm(clustered(g[:, j], tables))} | {pm(clustered(g[:, j] - g[:, gen8], tables))} | {pm(clustered(g[:, j] - g[:, ref], tables))} |')
            print()
    print('## 3. BEN\'s effective honesty and the information a signal carries, by situation\n')
    print('Effective honesty: the symmetric honesty with the same information about the parity as the observed rates '
          '(negative: a high card says odd). Bits: I(parity; lowest, highest or middle card), plug-in less the Miller-Madow bias. '
          'Intervals: 90%, resampling tables. Cells with 200 or more occasions.\n')
    for source, title in (('honesty', 'held-out tables'), ('honesty_all_tables', 'all tables (a description; fit tables included)')):
        for ben, label in VERSIONS:
            t = occ.get(source, {}).get(ben, {})
            if not t:
                continue
            print(f'**{label}, {title}**\n')
            print('| Situation | Occasions | P(high \\| even) | P(high \\| odd) | Effective honesty | Bits a signal |')
            print('| --- | ---: | ---: | ---: | ---: | ---: |')
            for cell, c in t.items():
                iv = c['interval'] or [float('nan')] * 2
                print(f"| {cell} | {c['occasions']:,} | {c['p_high_even']:.2f} | {c['p_high_odd']:.2f} | {c['honesty']:+.2f} [{iv[0]:+.2f}, {iv[1]:+.2f}] | "
                      f"{c['bits']:.3f} [{c['bits_interval'][0]:.3f}, {c['bits_interval'][1]:.3f}] |")
            print()
    print('## 4. The house control (their defenders, held-out occasions)\n')
    print('| Version | Occasions | M1 | M2 | M3 | M3 over M1 | Effective honesty by cell |')
    print('| --- | ---: | ---: | ---: | ---: | ---: | --- |')
    for ben, label in VERSIONS:
        h = occ.get('house', {}).get(ben)
        if not h:
            continue
        cells = '; '.join(f"{k} {v['honesty']:+.2f}" for k, v in h['honesty'].items())
        print(f"| {label} | {h['occasions']:,} | {pm(h['m1'])} | {pm(h['m2'])} | {pm(h['m3'])} | {pm(h['m3_over_m1'])} | {cells} |")


if __name__ == '__main__':
    main()
