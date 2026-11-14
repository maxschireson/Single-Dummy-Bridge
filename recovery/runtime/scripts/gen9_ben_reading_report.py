#!/usr/bin/env python3
"""Tables for E9-7 from rows written by scripts/gen9_ben_reading.py: per BEN version and role, each reader's mean gain
(nats of the true layout per house decision) and its paired difference from Gen 8's reading (`net0.3` for BEN's
defenders; factor 0.3 on BEN's declarer play), standard errors clustered by table.

  python scripts/gen9_ben_reading_report.py rows.jsonl [--json out.json]
"""
import argparse
from collections import defaultdict
import json

from gen9_reading_gain_report import clustered


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rows')
    ap.add_argument('--json')
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.rows)]
    groups = defaultdict(list)
    for r in rows:
        groups[(r['ben'], r['role'])].append(r)
    out = {}
    for (ben, role), rs in sorted(groups.items()):
        t = [f"{r['feed']}/{r['episode']}/{r['table']}" for r in rs]
        ref = 'net0.3' if role == 'declarer' else 'decl0.3'
        entry = {}
        print(f'\n{ben}, house {role} ({len(rs)} decisions, {len(set(t))} tables); reference {ref}')
        for name in rs[0]['gains']:
            m, se = clustered([r['gains'][name] for r in rs], t)
            d, dse = clustered([r['gains'][name] - r['gains'][ref] for r in rs], t)
            entry[name] = dict(mean=round(m, 4), se=round(se, 4), minus_ref=dict(mean=round(d, 4), se=round(dse, 4)))
            print(f'  {name:>12} {m:+.3f} ± {se:.3f}   minus {ref}: {d:+.3f} ± {dse:.3f}')
        out[f'{ben}|{role}'] = dict(decisions=len(rs), tables=len(set(t)), reference=ref, readers=entry)
    if args.json:
        json.dump(out, open(args.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
