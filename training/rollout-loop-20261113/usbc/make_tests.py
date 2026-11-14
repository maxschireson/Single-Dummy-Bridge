#!/usr/bin/env python3
"""The USBC's deals and auctions as bot tests (TEST DATA ONLY, never trained on).

  python3 make_tests.py RECORDS_DIR OUT_DIR --source CAPSULE/recovery [--bots configs/loop-bots.json] [--min-call 0.05]

Writes, over every human table of the harvested sessions (harvest.py), in one order:
  OUT_DIR/deals.json.gz   the deals (scripts/gen8_match.py --deals-file): table k is index k
  OUT_DIR/book.json.gz    the humans' auctions (gen8_match --book), systems 'usbc'
  OUT_DIR/tables.jsonl    per table: session, event, start, board, room, contract, the auction, and how well it fits our
                          bidding: under the common bidder (the one every bot of the loop bids with), the probability of each
                          call the humans made; `min_call` the least of them, `logp` their sum.
Max, 07:22 UTC on 14 November: "find auctions that fit the distribution of our bidding as well as you can to test the bots on.
Don't make them play against divergent systems." The tables whose every call our bidder gives at least --min-call are
written again alone, renumbered from 0 (fit_deals.json.gz, fit_book.json.gz, fit_tables.jsonl), for gen8_match runs.
"""
import argparse, glob, gzip, json, math, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.bidding_env import CALL_ID, BidObservation, deal_key, encode, legal_mask, pack_inputs   # noqa: E402

SEATS = 'NESW'
RANKS = '23456789TJQKA'
VUL = {'NONE': 'None', 'NORTH_SOUTH': 'NS', 'EAST_WEST': 'EW', 'BOTH': 'Both', 'ALL': 'Both'}
DOUBLE = {'X': 'X', 'D': 'X', 'DBL': 'X', 'XX': 'XX', 'R': 'XX', 'RDBL': 'XX', 'RE': 'XX'}


def hand_cards(text):
    out = []
    for suit, ranks in enumerate(text.replace(' ', '').split(',')):
        out += [13 * suit + RANKS.index(r) for r in ranks if r in RANKS]
    return sorted(out)


def call(bv):
    """LoveBridge's call ('H1' = 1H, 'N2' = 2NT, 'P', a double or redouble) in the loop's notation."""
    bv = bv.upper()
    if bv in ('P', 'PASS'):
        return 'PASS'
    if bv in DOUBLE:
        return DOUBLE[bv]
    if len(bv) == 2 and bv[0] in 'CDHSN' and bv[1] in '1234567':
        return bv[1] + bv[0]
    raise ValueError(f'unknown call {bv!r}')


def bidder(source, bots):
    import gen8_match
    from bridge_harness.system_bidders import NumpyPolicy, make_bidder
    m = gen8_match.build_manifest(Path(source), bots, '6-32~6-32', 1)
    spec = m['bots'][m['common_bidder']]
    entry = spec.get('bidder')
    return make_bidder(entry, ROOT) if entry else NumpyPolicy(str((Path(source) / spec['bidding']).resolve())), m['common_bidder']


def fit(b, hands, dealer, vul, calls):
    """The common bidder's probability of each call of the auction, in turn."""
    probs = []
    for k, c in enumerate(calls):
        seat = (dealer + k) % 4
        mask = legal_mask(dealer, calls[:k])
        xs, lengths = pack_inputs([encode(BidObservation(hands[seat], seat, dealer, vul, tuple(calls[:k])))])
        p = np.asarray(b.predict(xs, lengths)[0][0], float)
        p = np.where(mask, p, 0.)
        if p.min() < 0 or p.sum() <= 0 or abs(p[mask].sum() - 1) > .2:      # scores rather than probabilities: softmax over legal calls
            q = np.asarray(b.predict(xs, lengths)[0][0], float)
            q = np.where(mask, np.exp(q - q[mask].max()), 0.)
            p = q
        p = p / p.sum()
        probs.append(float(p[CALL_ID[c]]))
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('records', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--source', required=True)
    ap.add_argument('--bots', default=str(ROOT / 'configs/loop-bots.json'))
    ap.add_argument('--min-call', type=float, default=.05)
    ap.add_argument('--sample', type=int, default=0, help='also a sample of this many fitting tables, by category in turn (sample_*)')
    ap.add_argument('--seed', type=int, default=14)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    b, name = bidder(a.source, a.bots)
    deals, keys, auctions, rows, unknown = [], [], [], [], {}
    for path in sorted(glob.glob(str(a.records / 'usbc_*.json.gz'))):
        d = json.load(gzip.open(path, 'rt'))
        boards = {x['boardNumber']: x for x in d.get('boards', [])}
        meta = d.get('meta') or {}
        for t in d.get('tables', []):
            full = next((e['payload'] for e in t['events'] if e.get('tt') == 'FULL'), None)
            bx = boards.get(t['board'])
            if not full or not bx or not full.get('bg'):
                continue
            hands = [hand_cards(full['bd'][s]) for s in SEATS] if full.get('bd') else [sorted(hand_cards(', '.join(bx['hands'][k]))) for k in ('NORTH', 'EAST', 'SOUTH', 'WEST')]
            if sorted(c for h in hands for c in h) != list(range(52)):
                continue
            try:
                calls = [call(x['bv']) for x in full['bg']]
            except ValueError as e:
                unknown[str(e)] = unknown.get(str(e), 0) + 1
                continue
            dealer = SEATS.index(full['bg'][0]['d']) if full['bg'][0].get('d') in SEATS else 'NESW'.index(bx['dealer'][0])
            vul = VUL.get(bx.get('vulnerability', 'NONE'), 'None')
            if calls[-4:] != ['PASS'] * 4 and not (len(calls) >= 4 and calls[-3:] == ['PASS'] * 3):
                continue                                            # an auction not finished in the record
            probs = fit(b, hands, dealer, vul, calls)
            k = len(deals)
            deals.append(dict(hands=hands, dealer=dealer, vul=vul, name=f"{d['miniSessionId']}:{t['board']}:{full.get('room')}"))
            keys.append(deal_key(hands))
            auctions.append(calls)
            rows.append(dict(index=k, sid=d['miniSessionId'], event=meta.get('namePlus') or meta.get('name'), start=(meta.get('startDateTime') or '')[:10],
                             board=t['board'], room=full.get('room'), calls=calls, min_call=round(min(probs), 4),
                             logp=round(sum(math.log(max(p, 1e-9)) for p in probs), 3)))
    with gzip.open(a.out / 'deals.json.gz', 'wt') as f:
        json.dump(dict(first=0, deals=deals), f)
    with gzip.open(a.out / 'book.json.gz', 'wt') as f:
        json.dump(dict(seed=20260414, first=0, tables=[['usbc', 'usbc']], keys=keys, table_of=[0] * len(keys), auctions=auctions), f)
    with open(a.out / 'tables.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    keep = [r['index'] for r in rows if r['min_call'] >= a.min_call]
    with gzip.open(a.out / 'fit_deals.json.gz', 'wt') as f:          # the fitting tables alone, renumbered 0..: gen8_match plays ranges
        json.dump(dict(first=0, deals=[deals[k] for k in keep]), f)
    with gzip.open(a.out / 'fit_book.json.gz', 'wt') as f:
        json.dump(dict(seed=20260414, first=0, tables=[['usbc', 'usbc']], keys=[keys[k] for k in keep], table_of=[0] * len(keep),
                       auctions=[auctions[k] for k in keep]), f)
    with open(a.out / 'fit_tables.jsonl', 'w') as f:
        for j, k in enumerate(keep):
            f.write(json.dumps(dict(rows[k], fit_index=j)) + '\n')
    if a.sample:                                                     # a sample of the fitting tables, taking the categories in turn
        import random, re
        rng = random.Random(a.seed)
        cat = lambda r: next((n for n, p in (('Junior', r'Junior|U2\d|U16|RONA'), ("Women's", r'Women|Palmer'), ('Senior', r'Senior'),
                                             ('Mixed', r'Mixed'), ('Open', r'.')) if re.search(p, r.get('event') or '')), 'Open')
        pools = {}
        for k in keep:
            pools.setdefault(cat(rows[k]), []).append(k)
        for v in pools.values():
            rng.shuffle(v)
        pick, order = [], sorted(pools)
        while len(pick) < a.sample and any(pools.values()):
            for c in order:
                if pools[c] and len(pick) < a.sample:
                    pick.append(pools[c].pop())
        with gzip.open(a.out / 'sample_deals.json.gz', 'wt') as f:
            json.dump(dict(first=0, deals=[deals[k] for k in pick]), f)
        with gzip.open(a.out / 'sample_book.json.gz', 'wt') as f:
            json.dump(dict(seed=20260414, first=0, tables=[['usbc', 'usbc']], keys=[keys[k] for k in pick], table_of=[0] * len(pick),
                           auctions=[auctions[k] for k in pick]), f)
        with open(a.out / 'sample_tables.jsonl', 'w') as f:
            for j, k in enumerate(pick):
                f.write(json.dumps(dict(rows[k], sample_index=j, category=cat(rows[k]))) + '\n')
        import collections
        print('sample:', len(pick), dict(collections.Counter(cat(rows[k]) for k in pick)))
    mins = np.array([r['min_call'] for r in rows])
    print(f'{len(rows)} tables; common bidder {name}; calls not understood: {unknown}')
    for t in (.01, .02, .05, .1, .2):
        print(f'  every call at least {t}: {int((mins >= t).sum())} tables ({100 * (mins >= t).mean():.0f}%)')
    print(f'kept at {a.min_call}: {len(keep)} -> {a.out}/fit_*')


if __name__ == '__main__':
    main()
