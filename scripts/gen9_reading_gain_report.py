#!/usr/bin/env python3
"""Tables for E9-4 part 1 from rows written by scripts/gen9_reading_gain.py.

Mean gain in nats of the true layout per declarer decision, with standard errors clustered by table,
per cell and reader; and paired differences (same decisions) against Gen 8's reading of an unknown
opponent (`net0.3`) and against the reader that knows the scheme but assumes honesty 0 (`sig*-h0.0`).

  python scripts/gen9_reading_gain_report.py rows.jsonl [--json out.json]
"""
import argparse
from collections import defaultdict
import json

import numpy as np


def clustered(values, tables):
    """(mean, se) of per-decision values, se clustered by table."""
    values, tables = np.asarray(values, float), np.asarray(tables)
    ids = np.unique(tables)
    per = np.array([values[tables == t].sum() for t in ids])
    n = np.array([(tables == t).sum() for t in ids])
    mean = per.sum() / n.sum()
    se = np.sqrt(len(ids) / max(len(ids) - 1, 1) * ((per - mean * n) ** 2).sum()) / n.sum()
    return float(mean), float(se)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rows')
    ap.add_argument('--json')
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.rows)]
    stats = [r for r in rows if r.get('kind') == 'card_stats']
    dropped = [r for r in rows if r.get('dropped')]
    rows = [r for r in rows if 'gains' in r]
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[r['cell']].append(r)
    report = {}
    readers = sorted(rows[0]['gains']) if rows else []
    print(f'{len(rows)} declarer decisions; {len(dropped)} table-cells dropped (a swap could not be undone)')
    for cell in sorted(by_cell):
        rs = by_cell[cell]
        tables = [f"{r['episode']}/{r['table']}" for r in rs]
        swaps = {}
        for r in rs:
            swaps[f"{r['episode']}/{r['table']}"] = (r['swaps'], r['chances'], r['undone'])
        sw = np.array(list(swaps.values()))
        print(f'\n{cell}: {len(rs)} decisions, {len(swaps)} tables; per table {sw[:, 1].mean():.1f} signalling chances, '
              f'{sw[:, 0].mean():.1f} cards changed, {sw[:, 2].mean():.2f} swaps undone')
        out = {}
        for name in readers:
            m, se = clustered([r['gains'][name] for r in rs], tables)
            out[name] = dict(mean=round(m, 4), se=round(se, 4))
        for name in readers:
            line = f"  {name:>14} {out[name]['mean']:+.3f} ± {out[name]['se']:.3f}"
            for ref in ('net0.3', f"sig{name[3:].split('-')[0]}-h0.0" if name.startswith('sig') else None):
                if ref and ref in readers and ref != name:
                    d, dse = clustered([r['gains'][name] - r['gains'][ref] for r in rs], tables)
                    line += f'   vs {ref}: {d:+.3f} ± {dse:.3f}'
                    out[name][f'minus_{ref}'] = dict(mean=round(d, 4), se=round(dse, 4))
            print(line)
        for label, keep in (('tricks 1-4', lambda r: r['trick'] <= 4), ('tricks 5-6', lambda r: r['trick'] >= 5)):
            sub = [r for r in rs if keep(r)]
            if len(sub) > 10:
                t = [f"{r['episode']}/{r['table']}" for r in sub]
                parts = []
                for name in ('net0.3', 'class1', 'sig1-htrue'):
                    if name in readers:
                        parts.append(f"{name} {clustered([r['gains'][name] for r in sub], t)[0]:+.3f}")
                d = clustered([r['gains']['sig1-htrue'] - r['gains']['net0.3'] for r in sub], t) if 'sig1-htrue' in readers else None
                print(f'  {label} ({len(sub)}): ' + ', '.join(parts) + (f'; sig1-htrue minus net0.3 {d[0]:+.3f} ± {d[1]:.3f}' if d else ''))
        report[cell] = dict(decisions=len(rs), tables=len(swaps), readers=out)
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(dict(report=report, card_stats_rows=len(stats)), f, indent=1)


if __name__ == '__main__':
    main()
