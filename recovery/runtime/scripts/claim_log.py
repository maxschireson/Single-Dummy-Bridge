#!/usr/bin/env python3
"""The claims logged by plan bots (bridge_harness/plan_player.py, the decision records' `claim`), from episodes.

  python scripts/claim_log.py EPISODE_DIR [--lines 20] [--json OUT]

For every table played to the end (depth 0) whose declaring side logged a first claim: the trick, the declarer, the
tricks the claim guarantees in all (tricks already won + the most any card guaranteed then), the contract's total,
the tricks from that point to trick 13 (the claim point marked *), the declaring side's later cards that did not keep the contract's
guarantee, and the tricks declarer actually took. Prints a summary (claims, the trick they came at, claims thrown
away: fewer tricks than the contract's guarantee, or than the claim's full count) and the first --lines claims.
"""
import argparse
import collections
import glob
import gzip
import json
from pathlib import Path


def claims_of(path):
    d = json.load(gzip.open(path, 'rt'))
    for key, e in d.get('unique_tables', {}).items():
        b = e.get('board') or d.get('board')
        if not b or not b.get('contract'):
            continue
        level = int(str(b['contract'])[0])
        for table in e.get('tables', []):
            if table.get('depth', 0) != 0 or table.get('status', 'ok') != 'ok':
                continue
            acts = table['actions']
            first = next((i for i, a in enumerate(acts) if (a.get('claim') or {}).get('first')), None)
            if first is None:
                continue
            c = acts[first]['claim']
            won = level + 6 - c['need']
            total = won + c['sure'] if c.get('sure') is not None else max(level + 6, won)     # cheap question: the contract
            later = [a for a in acts[first:] if a.get('claim') and a['claim']['state'] in ('guaranteed', 'made')]
            yield dict(file=Path(path).name, table=key, player=acts[first].get('player'), contract=b['contract'], declarer=b.get('declarer'),
                       trick=c['trick'], state=c['state'], won_before=won, claim_total=total, exact=c.get('exact', True), contract_total=level + 6,
                       made=table['declarer_tricks'], line=[' '.join(('*' if i == first else '') + acts[i]['card'] for i in range(4 * t, min(4 * t + 4, len(acts))))
                                                            for t in range(first // 4, (len(acts) + 3) // 4)],
                       dropped=[(a['claim']['trick'], a['card']) for a in later if not a['claim'].get('keeps', True)],
                       dropped_sure=sum(not a['claim'].get('keeps_sure', True) for a in later))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('episodes')
    ap.add_argument('--lines', type=int, default=20)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    rows, tables = [], 0
    for path in sorted(glob.glob(str(Path(a.episodes) / '*.json.gz'))):
        rows += list(claims_of(path))
    by_trick = collections.Counter(r['trick'] for r in rows)
    short = [r for r in rows if r['made'] < min(r['claim_total'], max(r['contract_total'], r['won_before']))]
    short_full = [r for r in rows if r['made'] < r['claim_total']]
    print(f'{len(rows)} claims; first claim by trick: {dict(sorted(by_trick.items()))}')
    print(f'contract thrown after a claim: {len(short)}; fewer tricks than the claim guaranteed: {len(short_full)}; '
          f'claims with a later card that kept less than the most: {sum(r["dropped_sure"] > 0 for r in rows)}')
    for r in rows[:a.lines]:
        print(f"{r['file']} {r['table']} {r['contract']} by {r['declarer']} ({r['player']}): claim at trick {r['trick']} "
              f"for {r['claim_total']} ({r['state']}), took {r['made']}" + (f"; dropped {r['dropped']}" if r['dropped'] else ''))
        print('   ' + ' | '.join(r['line']))
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
