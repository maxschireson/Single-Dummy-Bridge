#!/usr/bin/env python3
"""Tables for E9-6 part 1 from rows written by scripts/gen9_signal_pair_gain.py.

Per cell and role, mean gain in nats of the true layout per decision for each reading, and the paired
differences (same decisions) against today's reading (recorded spots, house net), clustered by table.

  python scripts/gen9_signal_pair_report.py rows.jsonl [--json out.json]
"""
import argparse
from collections import defaultdict
import json

from gen9_reading_gain_report import clustered

NAMES = dict(recorded_house='recorded spots, house net (today)', scheme_read='scheme spots, read by the scheme',
             scheme_house='scheme spots, read by the house net')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rows')
    ap.add_argument('--json')
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.rows)]
    rows = [r for r in rows if 'gains' in r]
    groups = defaultdict(list)
    for r in rows:
        groups[(r['cell'], r['role'])].append(r)
    out = {}
    for (cell, role), rs in sorted(groups.items()):
        t = [f"{r['episode']}/{r['table']}" for r in rs]
        entry = {}
        line = f'{cell:>9} {role:>9} n={len(rs):5d}'
        for k in NAMES:
            m, se = clustered([r['gains'][k] for r in rs], t)
            entry[k] = dict(mean=round(m, 4), se=round(se, 4))
        for k in ('scheme_read', 'scheme_house'):
            d, dse = clustered([r['gains'][k] - r['gains']['recorded_house'] for r in rs], t)
            entry[f'{k}_minus_today'] = dict(mean=round(d, 4), se=round(dse, 4))
            line += f'   {k} - today {d:+.3f} ± {dse:.3f}'
        early = [r for r in rs if r['trick'] <= 3]
        if early:
            te = [f"{r['episode']}/{r['table']}" for r in early]
            d, dse = clustered([r['gains']['scheme_read'] - r['gains']['recorded_house'] for r in early], te)
            entry['scheme_read_minus_today_tricks_1_3'] = dict(mean=round(d, 4), se=round(dse, 4), n=len(early))
            line += f'   (tricks 1-3: {d:+.3f} ± {dse:.3f})'
        out[f'{cell}|{role}'] = dict(decisions=len(rs), tables=len(set(t)), **entry)
        print(line)
    if args.json:
        json.dump(out, open(args.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
