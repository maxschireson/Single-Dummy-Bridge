#!/usr/bin/env python3
"""Tricks lost against double dummy, card by card, in the USBC records (harvest.py), for every player.

  python3 lost_tricks.py RECORDS_DIR OUT_DIR [--workers 2]

TEST DATA ONLY. For every card a player chose (two or more legal cards), the deal as it lay is solved double dummy before
the card: `loss` is the tricks the card gave up against the best card (declarer's own and dummy's cards are declarer's
decisions). With it, how dangerous the position was, for normalizing across boards (Max, 07:12 UTC on 14 November:
"normalize the tricks lost by the volatility of the boards in a way that creates consistency across events"):
  `rand`  the mean loss of a legal card chosen at random,  `max`  the most a card could lose,  `crit`  some card loses.
A claim is one more decision: the claimed total against the double-dummy total at that point. A shortfall is the
claimer's loss; an excess (a generous claim accepted) is the other side's, split between its two players.
One file a session (OUT_DIR/<session>.lt2.json.gz), one row per table: its facts and its decisions
[trick, seat, role, loss, rand, max, legal, imp, turned]; role is L (opening lead), D (declarer, own or dummy's card), F
(defender), CD/CF (a claim's shortfall/excess, declaring/defending side). Max, 07:51 UTC: at IMPs a risky lead or a safety
play can be right while losing a trick double dummy, so with the tricks: `imp`, the card's double-dummy cost in IMPs at the
contract and vulnerability (an overtrick about 1, a contract many), and `turned`, 1 where the card changed make or set.
"""
import argparse, glob, gzip, hashlib, json, os, sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Contract, imps, score, vulnerable, winner     # noqa: E402

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
                tname=full.get('tname'), text=text)


VULS = {'NONE': 'None', 'NORTH_SOUTH': 'NS', 'EAST_WEST': 'EW', 'BOTH': 'Both', 'ALL': 'Both'}


def one_table(sid, meta, board_hands, t, vul='None'):
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
    contract = Contract(level, end['suit'], dec, {'D': 1, 'X': 1, 'R': 2, 'XX': 2}.get(end.get('mod') or '', 0))
    dvul = vulnerable(vul, dec)
    target = level + 6
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
                remaining = 13 - len(history) // 4
                final = lambda v: won + (v if declaring else remaining - v)          # declarer's tricks at the end, double dummy
                worth = lambda v: score(contract, final(v), dvul) * (1 if declaring else -1)   # to the side deciding
                imp = imps(worth(best) - worth(values[x]))                         # the card's cost in IMPs, double dummy
                made_best, made_got = final(best) >= target, final(values[x]) >= target
                turned = int(made_best != made_got)                                # the card changed make or set
                rows.append([len(history) // 4 + 1, SEATS[seat], role, best - values[x], round(sum(losses) / len(losses), 3), max(losses), len(legal),
                             imp, turned])
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
    if claim is not None and left > 0:
        # a claim, between tricks or mid-trick: the double-dummy total from here, for the side to move, over its legal cards
        mover = (leader + len(trick)) % 4
        values, _ = _DDS.solve([tuple(sorted(h)) for h in held], trump, leader, list(trick))
        hand = held[mover]
        legal = [y for y in hand if trick and y // 13 == trick[0][1] // 13] or sorted(hand)
        to_move = max(values[y] for y in legal)                 # the mover's side's tricks from here (this trick included)
        dd_dec = won + (to_move if mover % 2 == dec % 2 else left - to_move)
        claimed = int(claim['tcount'])                          # declarer's total, whoever claims (527 of 534 defender claims
        claim_dec = claimed                                     # match double dummy read this way; fixed 14 Nov, 09:20 UTC)
        diff = dd_dec - claim_dec                               # > 0: declarer's side ends with fewer than double dummy
        out['claim'] = dict(dir=claim['dir'], claimed=claimed, dd_declarer=dd_dec, declarer_after=claim_dec, mid_trick=bool(trick))
        if diff:
            imp = abs(imps(score(contract, dd_dec, dvul) - score(contract, claim_dec, dvul)))
            turned = int((dd_dec >= target) != (claim_dec >= target))
            out['decisions'].append([len(history) // 4 + 1, claim['dir'], 'CD' if diff > 0 else 'CF', abs(diff), None, None, None, imp, turned])
        # Max, 09:10 UTC 14 Nov: a claim counts as the remaining cards played without error by all four players. Play them
        # out along a double-dummy line (each player's lowest best card), adding each card's danger at no loss; a wrong
        # claim keeps its own row above. These rows end with 'claim'.
        n = 0
        while any(held):
            mover = (leader + len(trick)) % 4
            hand = held[mover]
            legal = [y for y in hand if trick and y // 13 == trick[0][1] // 13] or sorted(hand)
            if len(legal) > 1:
                values, _ = _DDS.solve([tuple(sorted(h)) for h in held], trump, leader, list(trick))
                best = max(values[y] for y in legal)
                losses = [best - values[y] for y in legal]
                x = min((y for y in legal if values[y] == best), key=lambda y: (y % 13, y // 13))
                role = 'L' if not history else 'D' if mover % 2 == dec % 2 else 'F'
                out['decisions'].append([len(history) // 4 + 1, SEATS[mover], role, 0, round(sum(losses) / len(losses), 3), max(losses),
                                         len(legal), 0, 0, 'claim'])
                n += 1
            else:
                x = legal[0]
            hand.discard(x)
            trick.append((mover, x))
            history.append((mover, x))
            if len(trick) == 4:
                leader = winner(trick, trump)
                won += leader % 2 == dec % 2
                trick = []
        out['claim']['played_out'] = n
    return out


def one_file(path):
    d = json.load(gzip.open(path, 'rt'))
    hands = {b['boardNumber']: {k[0]: ', '.join(v) for k, v in b['hands'].items()} for b in d.get('boards', [])}
    vuls = {b['boardNumber']: VULS.get(str(b.get('vulnerability', 'NONE')).upper(), 'None') for b in d.get('boards', [])}
    out = []
    for t in d.get('tables', []):
        try:
            r = one_table(d['miniSessionId'], d.get('meta') or {}, hands.get(t['board']), t, vuls.get(t['board'], 'None'))
        except Exception as e:                                  # one odd record must not end the run
            r = dict(sid=d['miniSessionId'], board=t.get('board'), error=f'{type(e).__name__}: {e}'[:200])
        if r:
            out.append(r)
    return os.path.basename(path), out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('records', type=Path)
    p.add_argument('out', type=Path, help='a folder: one OUT/<session>.lt.json.gz a session, written once')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--suffix', default='lt3', help='lt3: claims played out (14 Nov); lt2: the first scoring')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    files = [f for f in sorted(glob.glob(str(a.records / 'usbc_*.json.gz')))
             if not (a.out / os.path.basename(f).replace('.json.gz', f'.{a.suffix}.json.gz')).exists()]
    with Pool(a.workers) as pool:
        for name, rows in pool.imap_unordered(one_file, files):
            path = a.out / name.replace('.json.gz', f'.{a.suffix}.json.gz')
            with gzip.open(str(path) + '.tmp', 'wt') as f:
                for r in rows:
                    f.write(json.dumps(r, separators=(',', ':')) + '\n')
            os.replace(str(path) + '.tmp', path)
            print(name, len(rows), 'tables', flush=True)


if __name__ == '__main__':
    main()
