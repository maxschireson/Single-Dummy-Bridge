"""sure_cpp input lines for every position of real play in arena episodes, from the declaring side's view.

For each table (main and fork tables) of each episode: before every card with at most MAXLEFT cards in the hand of the
player to move, the line the claim finder would build (declaring side's hands known, the defenders' remaining cards one
pool, hand sizes and show-outs from the play so far, the current trick). Lines are de-duplicated. Output columns:
need<TAB>left<TAB>side_to_move(d/x)<TAB>line, where need is the tricks the contract still needs.
usage: episode_positions.py MAXLEFT EPISODE.json.gz ..."""
import gzip
import json
import sys

SUITS = 'SHDC'
RANKS = '23456789TJQKA'
SEATS = 'NESW'


def card(s):
    return 13 * SUITS.index(s[0]) + RANKS.index(s[1])


def hand(pbn):
    return {13 * i + RANKS.index(r) for i, part in enumerate(pbn.split('.')) for r in part}


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


def rot(seat, side):
    return seat if side == 0 else (seat + 3) % 4


def positions(board, actions, maxleft):
    hands = [hand(h) for h in board['hands']]
    level, strain = int(board['contract'][0]), board['contract'][1:].rstrip('X')
    trump = 4 if strain in ('N', 'NT') else SUITS.index(strain)
    decl = SEATS.index(board['declarer'])
    side = decl % 2
    dummy = (decl + 2) % 4
    leader = (decl + 1) % 4
    voids = [0, 0, 0, 0]
    won = 0
    trick = []
    for a in sorted(actions, key=lambda a: a['ply']):
        seat = SEATS.index(a['seat'])
        assert seat == (leader + len(trick)) % 4, 'seat order'
        left = len(hands[seat])
        need = level + 6 - won
        if left <= maxleft and a['ply'] >= 1:
            pool = 0
            for s in range(4):
                if s % 2 != side:
                    for c in hands[s]:
                        pool |= 1 << c
            north = sum(1 << c for c in hands[decl if rot(decl, side) == 0 else dummy])
            south = sum(1 << c for c in hands[decl if rot(decl, side) == 2 else dummy])
            de = [s for s in range(4) if s % 2 != side]
            e = [s for s in de if rot(s, side) == 1][0]
            w = [s for s in de if rot(s, side) == 3][0]
            line = '%d %d %x %x %x %d %d %d %d' % (trump, rot(leader, side), north, south, pool, len(hands[e]), len(hands[w]),
                                                   voids[e], voids[w])
            if trick:
                line += ' ' + ' '.join(str(c) for c in trick)
            yield need, left, 'd' if seat % 2 == side else 'x', line
        c = card(a['card'])
        assert c in hands[seat], 'card not in hand'
        if trick and c // 13 != trick[0] // 13:
            voids[seat] |= 1 << (trick[0] // 13)
        hands[seat].discard(c)
        trick.append(c)
        if len(trick) == 4:
            leader = winner(leader, trick, trump)
            won += leader % 2 == side
            trick = []


def main():
    maxleft = int(sys.argv[1])
    seen = set()
    for path in sys.argv[2:]:
        d = json.load(gzip.open(path))
        for t in d.get('unique_tables', {}).values():
            if t.get('status') != 'ok':
                continue
            for tab in t.get('tables', []):
                if tab.get('status') != 'ok' or len(tab.get('actions', [])) != 52:
                    continue
                for need, left, who, line in positions(t['board'], tab['actions'], maxleft):
                    if line in seen:
                        continue
                    seen.add(line)
                    print('%d\t%d\t%s\t%s' % (need, left, who, line))


main()
