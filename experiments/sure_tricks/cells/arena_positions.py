"""Declarer-side decisions from recorded arena tables, as cell-solver positions.

usage: arena_positions.py OUT.jsonl CARDS[,CARDS...] BOARDS.json [BOARDS.json ...]

For every distinct played table and every CARDS value: the first decision by declarer or dummy with exactly that many
cards in the hand to play, at least two legal cards, and the contract neither made nor lost yet. The deal is turned so
that the declaring side sits North-South (as bridge_harness/x8_claims.py does). One JSON line per position.
"""
import json
import sys

RANKS = '23456789TJQKA'
SUITS = 'SHDC'
SEATS = 'NESW'


def card(text):
    return 13 * SUITS.index(text[0]) + RANKS.index(text[1])


def hand(text):
    out = []
    for s, part in enumerate(text.split('.')):
        out += [13 * s + RANKS.index(r) for r in part]
    return out


def mask(cards):
    m = 0
    for c in cards:
        m |= 1 << c
    return m


def winner(leader, cards, trump):
    best = 0
    for i in range(1, 4):
        sb, si = cards[best] // 13, cards[i] // 13
        if si == sb:
            if cards[i] > cards[best]:
                best = i
        elif si == trump:
            best = i
    return (leader + best) % 4


def positions(board, table, wanted):
    k = table['contract']
    if not k or k[0] not in '1234567' or table['declarer'] not in SEATS:
        return
    level, strain = int(k[0]), k[1]
    doubled = k.count('X')
    trump = 4 if strain == 'N' else SUITS.index(strain)
    decl = SEATS.index(table['declarer'])
    dummy = (decl + 2) % 4
    side = decl % 2
    rot = (lambda s: s) if side == 0 else (lambda s: (s + 3) % 4)
    hands = [set(hand(h)) for h in board['hands']]
    plays = [(SEATS.index(p[0]), card(p[1:])) for p in table['plays']]
    if len(plays) != 52 or any(c not in hands[s] for s, c in plays):
        return
    target = level + 6
    game = doubled > 0 or level >= {'N': 3, 'S': 4, 'H': 4, 'D': 5, 'C': 5}[strain]
    won = 0
    voids = {s: 0 for s in range(4)}
    done = set()
    leader = plays[0][0]
    trick = []
    for i, (seat, c) in enumerate(plays):
        if not trick:
            leader = seat
        left = len(hands[seat])
        if seat % 2 == side and left in wanted and left not in done:
            need = target - won
            led = trick[0][1] // 13 if trick else None
            legal = [x for x in hands[seat] if led is None or x // 13 == led] or list(hands[seat])
            if 0 < need <= left and len(legal) >= 2:
                done.add(left)
                e_real, w_real = [s for s in range(4) if s % 2 != side and rot(s) == 1][0], [s for s in range(4) if s % 2 != side and rot(s) == 3][0]
                n_real, s_real = [s for s in range(4) if rot(s) == 0][0], [s for s in range(4) if rot(s) == 2][0]
                yield dict(board=board['id'], contract=k, declarer=table['declarer'], bot=table['assignments'][decl], game=game, level=level,
                           doubled=doubled, cards=left, trick_no=i // 4 + 1, trump=trump, leader=rot(leader),
                           hN='%x' % mask(hands[n_real]), hS='%x' % mask(hands[s_real]), pool='%x' % mask(hands[e_real] | hands[w_real]),
                           cE=len(hands[e_real]), cW=len(hands[w_real]), vE=voids[e_real], vW=voids[w_real],
                           trick=[x for _, x in trick], need=need, east='%x' % mask(hands[e_real]), played=c,
                           declarer_tricks=table['declarer_tricks'], made=table['declarer_tricks'] >= target, dummy_plays=seat == dummy,
                           auction=table['auction'], dealer=SEATS.index(board['dealer']), vul=board['vulnerability'], e_real=e_real, w_real=w_real,
                           e_played='%x' % mask(x for s2, x in plays[:i] if s2 == e_real), w_played='%x' % mask(x for s2, x in plays[:i] if s2 == w_real))
        if trick and c // 13 != trick[0][1] // 13:
            voids[seat] |= 1 << (trick[0][1] // 13)
        hands[seat].discard(c)
        trick.append((seat, c))
        if len(trick) == 4:
            w = winner(leader, [x for _, x in trick], trump)
            won += w % 2 == side
            trick = []


def main():
    out, wanted, files = sys.argv[1], {int(x) for x in sys.argv[2].split(',')}, sys.argv[3:]
    seen, n = set(), 0
    with open(out, 'w') as f:
        for fn in files:
            for b in json.load(open(fn)).values():
                for cond in b['conditions'].values():
                    for t in cond['tables']:
                        key = (b['board']['id'], t['contract'], t['declarer'], tuple(t['plays']))
                        if key in seen:
                            continue
                        seen.add(key)
                        for p in positions(b['board'], t, wanted):
                            p['table'] = len(seen) - 1
                            f.write(json.dumps(p) + '\n')
                            n += 1
    print(len(seen), 'tables,', n, 'positions')


if __name__ == '__main__':
    main()
