#!/usr/bin/env python3
"""USBC tables as training episodes for one experiment (Max, 09:25 UTC on 14 November): train a net on the experts' cards and
play it against a net trained on as many bot boards. Adult events (Open, Senior, Mixed, Women's) of 2021 to 2023 only; 2025
and the juniors stay test data. One table a deal: the first, in a seeded random order, whose every call the common bidder
gives at least --min-call (an auction familiar to our bidder).

  python3 human_episodes.py RECORDS_DIR OUT_DIR --source CAPSULE [--min-call 0.05] [--limit N]

OUT_DIR/<n>.json.gz: one episode file a table in the format gen8_match writes (candidate and opponent 'usbc', North-South
the candidate), the humans' auction and cards, `declarer_tricks` the result (a claim's count where the play was claimed).
scripts/gen7_build_dataset.py --policy-only turns them into rows whose target is the card the human played.

--all-tables: every table of every deal, in OUT_DIR/fit/ (an auction our bidder knows) or OUT_DIR/unfit/ (any other), for
the experiment's second part: is every expert table worth having, and are the unfamiliar auctions? --part K/N: the deals
whose place in the sorted list is K mod N (to run N at once; the files carry the part in their names).
"""
import argparse, collections, gzip, hashlib, json, random, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import make_tests as mt                                         # noqa: E402
from analyze import SCREENS_2025, category                      # noqa: E402
from lost_tricks import event_card, hand_cards                  # noqa: E402
from bridge_harness.core import SEATS, hand_text, symbol        # noqa: E402

ADULT = ('Open', 'Senior', 'Mixed', "Women's")


def tables(records):
    """(deal key, record) for every adult 2021-2023 table with a finished auction, a contract and legal hands."""
    for path in sorted(records.glob('usbc_*.json.gz')):
        d = json.load(gzip.open(path, 'rt'))
        sid = d['miniSessionId']
        meta = d.get('meta') or {}
        start = (meta.get('startDateTime') or '')[:4]
        if sid.split('_')[1] in SCREENS_2025 or start not in ('2021', '2022', '2023'):
            continue
        text = ' '.join(str(meta.get(k) or '') for k in ('namePlus', 'eventName', 'tournamentName', 'name'))
        if category(meta.get('namePlus') or meta.get('name') or '', text) not in ADULT:
            continue
        boards = {x['boardNumber']: x for x in d.get('boards', [])}
        for t in d.get('tables', []):
            ev = t['events']
            full = next((e['payload'] for e in ev if e.get('tt') == 'FULL'), None)
            end = next((e['payload'] for e in ev if e.get('tt') == 'END_AUCTION'), None)
            bx = boards.get(t['board'])
            if not full or not end or not bx or not full.get('bg') or end.get('pass') == 't':
                continue
            hands = [sorted(hand_cards(full['bd'][s])) for s in SEATS] if full.get('bd') else None
            if not hands or sorted(c for h in hands for c in h) != list(range(52)):
                continue
            try:
                calls = [mt.call(x['bv']) for x in full['bg']]
            except ValueError:
                continue
            if not (len(calls) >= 4 and calls[-3:] == ['PASS'] * 3):
                continue
            dealer = SEATS.index(full['bg'][0]['d']) if full['bg'][0].get('d') in SEATS else SEATS.index(bx['dealer'][0])
            vul = mt.VUL.get(bx.get('vulnerability', 'NONE'), 'None')
            key = hashlib.sha1(json.dumps(hands).encode()).hexdigest()[:16]
            yield key, dict(sid=sid, board=t['board'], room=full.get('room'), hands=hands, dealer=dealer, vul=vul, calls=calls, end=end, events=ev)


def episode(r, n):
    """The table as a gen8_match episode; None where the cards do not fit the contract's play."""
    end = r['end']
    dec = SEATS.index(end['dec'])
    strain = end['suit'] if end['suit'] != 'NT' else 'N'
    doubled = {'D': 1, 'X': 1, 'R': 2, 'XX': 2}.get(end.get('mod') or '', 0)
    contract = f"{int(end['level'])}{strain}{'X' * doubled}"
    actions, claim, trick, leader, won, ply = [], None, [], (dec + 1) % 4, 0, 0
    held = [set(h) for h in r['hands']]
    from bridge_harness.core import winner
    trump = 'SHDCN'.index(strain)
    for e in r['events']:
        if e.get('tt') == 'CLAIM':
            claim = e['payload']
            break
        if e.get('tt') != 'PLAY_CARD':
            continue
        seat, x = event_card(e['payload']['c'])
        if seat != (leader + len(trick)) % 4 or x not in held[seat]:
            return None
        held[seat].discard(x)
        actions.append(dict(card=symbol(x), player='candidate' if seat % 2 == 0 else 'opponent', ply=ply))
        ply += 1
        trick.append((seat, x))
        if len(trick) == 4:
            leader = winner(trick, trump)
            won += leader % 2 == dec % 2
            trick = []
    if claim is not None:
        tricks = int(claim['tcount'])                           # declarer's total, whoever claims
    elif ply == 52:
        tricks = won
    else:
        return None                                             # the record stops without a claim
    family = hashlib.sha1(json.dumps(r['hands']).encode()).hexdigest()
    board = dict(id=f"{r['sid']}:{r['board']}:{r['room']}", hands=[hand_text(h) for h in r['hands']], contract=contract,
                 declarer=SEATS[dec], dealer=SEATS[r['dealer']], vulnerability=r['vul'], auction=r['calls'],
                 auction_source='usbc', family=family, opening_lead=None)
    table = dict(actions=actions, declarer_tricks=tricks, depth=0)
    return dict(candidate='usbc', opponent='usbc', family=family, board_index=n, source='usbc',
                unique_tables={'0': dict(board=board, tables=[table])})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('records', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--source', required=True)
    ap.add_argument('--bots', default=str(ROOT / 'configs/loop-bots.json'))
    ap.add_argument('--min-call', type=float, default=.05)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--seed', type=int, default=20261114)
    ap.add_argument('--all-tables', action='store_true')
    ap.add_argument('--part', default='0/1')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    b, name = mt.bidder(a.source, a.bots)
    by = collections.defaultdict(list)
    for key, r in tables(a.records):
        by[key].append(r)
    if a.all_tables:
        k, n_parts = (int(x) for x in a.part.split('/'))
        (a.out / 'fit').mkdir(exist_ok=True)
        (a.out / 'unfit').mkdir(exist_ok=True)
        count = collections.Counter()
        for j, key in enumerate(sorted(by)):
            if j % n_parts != k:
                continue
            for r in by[key]:
                where = 'fit' if min(mt.fit(b, r['hands'], r['dealer'], r['vul'], r['calls'])) >= a.min_call else 'unfit'
                ep = episode(r, count[where])
                if ep is None:
                    count['play not usable'] += 1
                    continue
                with gzip.open(a.out / where / f'{k}_{count[where]:06d}.json.gz', 'wt') as f:
                    json.dump(ep, f)
                count[where] += 1
        print(f'part {a.part}: {dict(count)}; common bidder {name}')
        return
    rng = random.Random(a.seed)
    keys = sorted(by)
    rng.shuffle(keys)
    n, tried, stats = 0, 0, collections.Counter()
    for key in keys:
        rs = by[key]
        rng.shuffle(rs)
        for r in rs:
            tried += 1
            probs = mt.fit(b, r['hands'], r['dealer'], r['vul'], r['calls'])
            if min(probs) < a.min_call:
                stats['auction not familiar'] += 1
                continue
            ep = episode(r, n)
            if ep is None:
                stats['play not usable'] += 1
                continue
            with gzip.open(a.out / f'{n:06d}.json.gz', 'wt') as f:
                json.dump(ep, f)
            n += 1
            break
        else:
            stats['deal without a familiar table'] += 1
        if a.limit and n >= a.limit:
            break
    print(f'{len(by)} adult 2021-2023 deals; {n} episodes (one table a deal) from {tried} tables tried; common bidder {name}; {dict(stats)}')


if __name__ == '__main__':
    main()
