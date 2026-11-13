"""Random sure_cpp input lines from random deals played out at random to a given number of cards left.

Each line: trump leader hN hS pool cE cW vE vW [cards already in the trick]. North-South declare. The play before the
position is uniformly random among legal cards, so show-outs arise as they do in play; 0 to 3 cards may already be in
the current trick.
usage: gen_play_positions.py N_LEFT COUNT SEED [--trick any|none]"""
import random
import sys


def winner(leader, cards, trump):
    best = 0
    for i in range(1, len(cards)):
        sb, si = cards[best] // 13, cards[i] // 13
        if si == sb:
            if cards[i] > cards[best]:
                best = i
        elif si == trump:
            best = i
    return (leader + best) % 4


def main():
    left, count, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    trick_mode = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == '--trick' else 'any'
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        deck = list(range(52))
        rng.shuffle(deck)
        hands = [set(deck[13 * i:13 * i + 13]) for i in range(4)]
        trump = rng.randrange(5)
        leader = rng.randrange(4)
        voids = [0, 0, 0, 0]
        for _ in range(13 - left):
            trick = []
            for k in range(4):
                seat = (leader + k) % 4
                h = hands[seat]
                legal = [c for c in h if trick and c // 13 == trick[0] // 13] or list(h)
                c = rng.choice(legal)
                if trick and c // 13 != trick[0] // 13:
                    voids[seat] |= 1 << (trick[0] // 13)
                h.discard(c)
                trick.append(c)
            leader = winner(leader, trick, trump)
        in_trick = 0 if trick_mode == 'none' else rng.randrange(4)
        trick = []
        for k in range(in_trick):
            seat = (leader + k) % 4
            h = hands[seat]
            legal = [c for c in h if trick and c // 13 == trick[0] // 13] or list(h)
            c = rng.choice(legal)
            if trick and c // 13 != trick[0] // 13:
                voids[seat] |= 1 << (trick[0] // 13)
            h.discard(c)
            trick.append(c)
        m = [sum(1 << c for c in h) for h in hands]
        line = '%d %d %x %x %x %d %d %d %d' % (trump, leader, m[0], m[2], m[1] | m[3], len(hands[1]), len(hands[3]),
                                               voids[1], voids[3])
        if trick:
            line += ' ' + ' '.join(str(c) for c in trick)
        out.append(line)
    print('\n'.join(out))


main()
