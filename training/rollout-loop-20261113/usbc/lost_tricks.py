#!/usr/bin/env python3
"""Tricks lost against double dummy, card by card, in the USBC records (harvest.py), for every player.

  python3 lost_tricks.py RECORDS_DIR OUT.jsonl.gz [--workers 2]

TEST DATA ONLY. For every card a player chose (two or more legal cards), the deal as it lay is solved double dummy before
the card: `loss` is the tricks the card gave up against the best card (declarer's own and dummy's cards are declarer's
decisions). With it, how dangerous the position was, for normalizing across boards (Max, 07:12 UTC on 14 November:
"normalize the tricks lost by the volatility of the boards in a way that creates consistency across events"):
  `rand`  the mean loss of a legal card chosen at random,  `max`  the most a card could lose,  `crit`  some card loses.
A claim is one more decision: the claimed total against the double-dummy total at that point. A shortfall is the
claimer's loss; an excess (a generous claim accepted) is the other side's, split between its two players.
One output row per table: its facts and its decisions [trick, seat, role, loss, rand, max, legal]; role is L (opening
lead), D (declarer, own or dummy's card), F (defender), CD/CF (a claim's shortfall/excess, declaring/defending side).
"""
import argparse, glob, gzip, hashlib, json, os, sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import winner                     # noqa: E402

SEATS = 'NESW'
SUITS = 'SHDC'
RANKS = '23456789TJQKA'
STRAIN = {'S': 0, 'H': 1, 'D': 2, 'C': 3, 'N': 4}
_DDS = None


def hand_cards(text):
    """'K432, AK652, K, J65' (spades, hearts, diamonds, clubs) -> cards 0..51 (13 x suit + rank)."""
    out = []
    for suit, ranks in enumerate(text.replace(' ', '').split(',')):
        out += [13 * suit + RANKS.index(r) for r in ranks if r in RANKS]
    return out


def event_card(c):
    """'ES5' -> (seat 1, card): seat letter, suit letter, rank 2..14."""
    return SEATS.index(c[0]), 13 * SUITS.index(c[1]) + int(c[2:]) - 2


def facts(meta, full):
    text = ' '.join(str(meta.get(k) or '') for k in ('namePlus', 'eventName', 'tournamentName', 'name'))
    return dict(event=meta.get('namePlus') or meta.get('name') or full.get('tname'), start=(meta.get('startDateTime') or '')[:10],
                tname=full.get('tname'), room=full.get('room'), text=text)


def one_table(sid, meta, board_hands, t):
    global _DDS
    if _DDS is None:
        from bridge_harness.dds import DDS
        _DDS = DDS()
    ev = t['events']
    full = next((e['payload'] for e in ev if e.get('tt') == 'FULL'), None)
    end = next((e['payload'] for e in ev if e.get('tt') == 'END_AUCTION'), None)
    if not full or not end or end.get('pass') == 't':
        return None
    bd = full.get('bd') or board_hands
    hands = [hand_cards(bd[s]) for s in SEATS]
    if sorted(x for h in hands for x in h) != list(range(52)):
        return None
    dec = SEATS.index(end['dec'])
    trump = STRAIN[end['suit']]
    level = int(end['level'])
    names = {s: (full.get('ps', {}).get(s) or {}).get('name') for s in SEATS}
    pids = {s: (full.get('ps', {}).get(s) or {}).get('playerId') for s in SEATS}
    held = [set(h) for h in hands]
    trick, leader, won, history, rows = [], (dec + 1) % 4, 0, [], []
    claim = None
    for e in ev:
        tt = e.get('tt')
        if tt == 'CLAIM':
            claim = e['payload']
        elif tt == 'PLAY_CARD':
            seat, x = event_card(e['payload']['c'])
            actor = (leader + len(trick)) % 4
            if seat != actor or x not in held[seat]:
                return dict(sid=sid, board=t['board'], error='play out of order')
            hand = held[seat]
            legal = [y for y in hand if trick and y // 13 == trick[0][1] // 13] or sorted(hand)
            if len(legal) > 1:
                values, _ = _DDS.solve([tuple(sorted(h)) for h in held], trump, leader, list(trick))
                best = max(values[y] for y in legal)
                losses = [best - values[y] for y in legal]
                declaring = seat % 2 == dec % 2
                role = 'L' if not history else 'D' if declaring else 'F'
                rows.append([len(history) // 4 + 1, SEATS[seat], role, best - values[x], round(sum(losses) / len(losses), 3), max(losses), len(legal)])
            hand.discard(x)
            trick.append((seat, x))
            history.append((seat, x))
            if len(trick) == 4:
                leader = winner(trick, trump)
                won += leader % 2 == dec % 2
                trick = []
    left = 13 - len(history) // 4
    out = dict(sid=sid, board=t['board'], deal=hashlib.sha1(json.dumps([sorted(h) for h in hands]).encode()).hexdigest()[:16],
               room=full.get('room'), contract=f"{level}{end['suit']}{end.get('mod') or ''}", dec=SEATS[dec],
               names=names, pids=pids, tricks_played=len(history) // 4, decisions=rows, **facts(meta, full))
    if claim is not None and left > 0 and not trick:
        values, _ = _DDS.solve([tuple(sorted(h)) for h in held], trump, leader, [])
        to_move = max(values.values())                          # the side on lead's tricks from here, double dummy
        dd_dec = won + (to_move if leader % 2 == dec % 2 else left - to_move)
        claimer_dec = SEATS.index(claim['dir']) % 2 == dec % 2
        claimed = int(claim['tcount'])                          # the claimer's side's total (USBC records: declarer's total)
        claim_dec = claimed if claimer_dec else 13 - claimed
        diff = dd_dec - claim_dec                               # > 0: declarer's side ends with fewer than double dummy
        out['claim'] = dict(dir=claim['dir'], claimed=claimed, dd_declarer=dd_dec, declarer_after=claim_dec)
        if diff:
            out['decisions'].append([len(history) // 4 + 1, claim['dir'], 'CD' if diff > 0 else 'CF', abs(diff), None, None, None])
    elif claim is not None:
        out['claim'] = dict(dir=claim['dir'], claimed=int(claim['tcount']), note='claimed in mid-trick: not scored')
    return out


def one_file(path):
    d = json.load(gzip.open(path, 'rt'))
    hands = {b['boardNumber']: {k[0]: ', '.join(v) for k, v in b['hands'].items()} for b in d.get('boards', [])}
    out = []
    for t in d.get('tables', []):
        try:
            r = one_table(d['miniSessionId'], d.get('meta') or {}, hands.get(t['board']), t)
        except Exception as e:                                  # one odd record must not end the run
            r = dict(sid=d['miniSessionId'], board=t.get('board'), error=f'{type(e).__name__}: {e}'[:200])
        if r:
            out.append(r)
    return os.path.basename(path), out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('records', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    done = set()
    if a.out.exists():
        with gzip.open(a.out, 'rt') as f:
            done = {json.loads(l)['file'] for l in f if l.startswith('{"file"')}
    files = [f for f in sorted(glob.glob(str(a.records / 'usbc_*.json.gz'))) if os.path.basename(f) not in done]
    with Pool(a.workers) as pool, gzip.open(a.out, 'at') as f:
        for name, rows in pool.imap_unordered(one_file, files):
            f.write(json.dumps(dict(file=name, tables=len(rows))) + '\n')
            for r in rows:
                f.write(json.dumps(r, separators=(',', ':')) + '\n')
            f.flush()
            print(name, len(rows), 'tables', flush=True)


if __name__ == '__main__':
    main()
