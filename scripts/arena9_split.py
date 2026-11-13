#!/usr/bin/env python3
"""Where a floor difference comes from: two bots against the same guest on the same deals, table by table.

Reads re-created records (scripts/arena9_records.py) of two floor pairs, BOT~GUEST and CONTROL~GUEST, and compares
the two bots' tables room by room in each regime (common, native): the same seats, and auctions that should be
identical (both bots bid with the same net). For every table it records the bot's side, whether it declared,
the opening lead, the bot's tricks and its score, then reports BOT minus CONTROL split by regime, by
declaring or defending, and, when the bot's side made the opening lead, by whether the two bots led the same card.

    python scripts/arena9_split.py --records DIR --epochs 5 --bot 9a-32 --control 8p-32 --guest guest-b --out split.json

IMPs per table are imps(score of BOT's table - score of CONTROL's table), as if the two tables were a team match;
standard errors are by deal.
"""
import argparse
import gzip
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import imps  # noqa: E402

SEATS = 'NESW'


def read(path):
    out = {}
    try:
        with gzip.open(path, 'rt') as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    break
                out[r['_index']] = r
    except (EOFError, FileNotFoundError):
        pass
    return out


def table_facts(record, key, bot):
    b = record['bidding'].get(key)
    if b is None:
        return None
    e = record['unique_tables'][b['table']]
    role = 'candidate' if record['candidate'] == bot else 'opponent'
    side = next(s for s in range(4) if e['assignments'][s] == role) % 2
    board = e['board']
    main = next((t for t in e['tables'] if t.get('depth', 0) == 0), e['tables'][0])
    if board.get('contract') in (None, 'PASS') or board.get('declarer') is None:
        return dict(auction=tuple(board.get('auction') or ()), passed=True, score=0, tricks=None, declaring=None, lead=None, bot_leads=None)
    declarer = SEATS.index(board['declarer'])
    ns = main.get('ns_score') or 0
    tricks = main.get('declarer_tricks')
    declaring = declarer % 2 == side
    actions = main['actions']
    return dict(auction=tuple(board.get('auction') or ()), contract=board['contract'], passed=False, declaring=declaring,
                score=ns if side == 0 else -ns, tricks=None if tricks is None else (tricks if declaring else 13 - tricks),
                lead=actions[0]['card'] if actions else None, bot_leads=not declaring)


def stats(xs):
    n = len(xs)
    if not n:
        return dict(n=0, mean=None, se=None)
    m = sum(xs) / n
    return dict(n=n, mean=round(m, 4), se=round(math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n), 4) if n > 1 else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--records', type=Path, required=True)
    ap.add_argument('--epochs', type=int, nargs='+', required=True)
    ap.add_argument('--bot', default='9a-32')
    ap.add_argument('--control', default='8p-32')
    ap.add_argument('--guest', required=True)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    tables = []
    for ep in a.epochs:
        A = read(a.records / f'e{ep}-{a.bot}~{a.guest}.jsonl.gz')
        B = read(a.records / f'e{ep}-{a.control}~{a.guest}.jsonl.gz')
        for i in sorted(set(A) & set(B)):
            for regime in ('common', 'native'):
                for room in (0, 1):
                    key = f'{regime}/{room}'
                    x, y = table_facts(A[i], key, a.bot), table_facts(B[i], key, a.control)
                    if x is None or y is None:
                        continue
                    tables.append(dict(epoch=ep, deal=i, regime=regime, room=room, same_auction=x['auction'] == y['auction'],
                                       declaring=x['declaring'] if x['declaring'] == y['declaring'] else 'mixed',
                                       same_lead=(x['lead'] == y['lead']) if x['bot_leads'] and y['bot_leads'] else None,
                                       imps=imps(x['score'] - y['score']),
                                       tricks=None if x['tricks'] is None or y['tricks'] is None else x['tricks'] - y['tricks']))

    def group(name, keep):
        rows = [t for t in tables if keep(t)]
        per = {}
        for t in rows:
            per.setdefault((t['epoch'], t['deal']), []).append(t)
        imp = [sum(t['imps'] for t in v) for v in per.values()]
        tr = [sum(t['tricks'] for t in v if t['tricks'] is not None) for v in per.values()]
        return dict(group=name, tables=len(rows), deals=len(per), imps=stats(imp), tricks=stats(tr))

    deals = len({(t['epoch'], t['deal']) for t in tables})
    groups = []
    for regime in ('native', 'common'):
        groups.append(group(f'{regime}: all tables', lambda t, r=regime: t['regime'] == r))
        groups.append(group(f'{regime}: the bot declares', lambda t, r=regime: t['regime'] == r and t['declaring'] is True))
        groups.append(group(f'{regime}: the bot defends', lambda t, r=regime: t['regime'] == r and t['declaring'] is False))
        groups.append(group(f'{regime}: defends, same opening lead', lambda t, r=regime: t['regime'] == r and t['declaring'] is False and t['same_lead'] is True))
        groups.append(group(f'{regime}: defends, a different opening lead', lambda t, r=regime: t['regime'] == r and t['declaring'] is False and t['same_lead'] is False))
    checks = dict(deals=deals, tables=len(tables), auctions_differ=sum(1 for t in tables if not t['same_auction']),
                  declarer_side_differs=sum(1 for t in tables if t['declaring'] == 'mixed'))
    out = dict(schema='arena9-split-v1', bot=a.bot, control=a.control, guest=a.guest, epochs=a.epochs, checks=checks, groups=groups)
    text = json.dumps(out, indent=1)
    if a.out:
        a.out.write_text(text + '\n')
    print(json.dumps(checks))
    for g in groups:
        i, t = g['imps'], g['tricks']
        fmt = lambda s: '—' if s['mean'] is None else f"{s['mean']:+.3f} ({s['se'] if s['se'] is not None else '—'})"
        print(f"{g['group']:<45} tables {g['tables']:5d} deals {g['deals']:4d}  IMPs a deal {fmt(i):>18}  tricks a deal {fmt(t):>18}")


if __name__ == '__main__':
    main()
