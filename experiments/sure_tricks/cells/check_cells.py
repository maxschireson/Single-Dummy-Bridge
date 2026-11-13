"""cells.cpp against the brute-force reference over explicit layouts (celllib.Brute), on random small endings.

usage: check_cells.py K COUNT [--seed N] [--modes all,ends,mid,two] [--pooled DIR]

For each random ending with K cards in each hand (short suits, so touching cards are common), random trump, leader and
show-outs, three kinds of knowledge are compared:
  every   every shape consistent with hand sizes and show-outs, no named cards (the game sure.cpp plays)
  subset  0 to 2 named cards and a random subset of the cells (often a single cell)
  trick   the same after 1 to 3 cards of the next trick, with North or South to play: yes/no per card for each target
With --pooled DIR (a directory holding pooled_ref.py), `every` and single-shape cells are also compared with it.
"""
import random
import sys
import time

from celllib import SUIT, Brute, Solver, bits, cards_of, enumerate_cells, layouts_of, popcount, trick_winner


def random_ending(k, rng):
    ranks = k + rng.choice((0, 1, 2))
    deck = [13 * s + r for s in range(4) for r in rng.sample(range(13), min(13, ranks))]
    while len(deck) < 4 * k:
        deck = [13 * s + r for s in range(4) for r in range(min(13, ranks + 1))]
    cards = rng.sample(deck, 4 * k)
    hands = [bits(cards[i * k:(i + 1) * k]) for i in range(4)]         # N, E, S, W
    return hands


def shown_voids(hands, rng, p=.35):
    vE = vW = 0
    for s in range(4):
        if not (hands[1] | hands[3]) & SUIT[s]:
            continue
        if not hands[1] & SUIT[s] and rng.random() < p:
            vE |= 1 << s
        if not hands[3] & SUIT[s] and rng.random() < p:
            vW |= 1 << s
    return vE, vW


def main():
    k, count = int(sys.argv[1]), int(sys.argv[2])
    seed = int(sys.argv[sys.argv.index('--seed') + 1]) if '--seed' in sys.argv else 1
    modes = sys.argv[sys.argv.index('--modes') + 1].split(',') if '--modes' in sys.argv else ['all', 'ends', 'mid', 'two']
    pooled = None
    if '--pooled' in sys.argv:
        sys.path.insert(0, sys.argv[sys.argv.index('--pooled') + 1])
        import pooled_ref
        pooled = pooled_ref
    rng = random.Random(seed)
    solvers = {m: Solver('./cells', ('--def', m)) for m in modes}
    bad = {m: {'every': 0, 'subset': 0, 'trick': 0} for m in modes}
    done = {'every': 0, 'subset': 0, 'trick': 0, 'pooled': 0}
    bad_pooled = 0
    examples = {m: [] for m in modes}
    started = time.time()
    for it in range(count):
        hands = random_ending(k, rng)
        hN, hE, hS, hW = hands
        pool = hE | hW
        trump, leader = rng.randrange(5), rng.randrange(4)
        vE, vW = shown_voids(hands, rng)
        # ---- every shape
        cells = enumerate_cells(pool, k, k, vE, vW, 0)
        lays = layouts_of([(eu, pin) for eu, pin, _ in cells], pool, 0)
        assert hE in lays
        ref = Brute(trump).value(hN, hS, pool, lays, leader)
        done['every'] += 1
        for m, sv in solvers.items():
            sv.position(trump, leader, hN, hS, pool, 0)
            sv.cells([(eu, pin) for eu, pin, _ in cells])
            got = sv.value()['value']
            if got != ref:
                bad[m]['every'] += 1
                if len(examples[m]) < 5:
                    examples[m].append(('every', trump, leader, hex(hN), hex(hS), hex(pool), vE, vW, 'ref', ref, 'got', got))
        if pooled is not None:
            el = [0 if vE >> s & 1 else (popcount(pool & SUIT[s]) if vW >> s & 1 else None) for s in range(4)]
            pv = pooled.Pooled(trump).value(hN, hS, pool, k, k, tuple(el), leader)
            done['pooled'] += 1
            bad_pooled += pv != ref
            # one whole shape: the true one
            el = [popcount(hE & SUIT[s]) for s in range(4)]
            pv = pooled.Pooled(trump).value(hN, hS, pool, k, k, tuple(el), leader)
            one = [(eu, pin) for eu, pin, _ in cells if list(eu) == el]
            rv = Brute(trump).value(hN, hS, pool, layouts_of(one, pool, 0), leader)
            done['pooled'] += 1
            bad_pooled += pv != rv
        # ---- named cards and a subset of the cells
        pc_cards = cards_of(pool)
        named = bits(rng.sample(pc_cards, rng.choice((0, 1, 1, 2, 2))))
        cells = enumerate_cells(pool, k, k, vE, vW, named)
        how = rng.random()
        if how < .35:
            pick = [rng.randrange(len(cells))]
        elif how < .5:
            pick = list(range(len(cells)))
        else:
            pick = [i for i in range(len(cells)) if rng.random() < rng.choice((.2, .5, .8))] or [rng.randrange(len(cells))]
        lays = layouts_of([(cells[i][0], cells[i][1]) for i in pick], pool, named)
        ref = Brute(trump).value(hN, hS, pool, lays, leader)
        done['subset'] += 1
        for m, sv in solvers.items():
            sv.position(trump, leader, hN, hS, pool, named)
            sv.cells([(eu, pin) for eu, pin, _ in cells])
            got = sv.value(pick)['value']
            if got != ref:
                bad[m]['subset'] += 1
                if len(examples[m]) < 5:
                    examples[m].append(('subset', trump, leader, hex(hN), hex(hS), hex(pool), hex(named), vE, vW, pick, 'ref', ref, 'got', got))
        # ---- inside a trick: play 1 to 3 cards of the true deal at random, stop with North or South to play
        cur = list(hands)
        trick, seat = [], leader
        vE2, vW2 = vE, vW
        steps = rng.choice((1, 2, 3))
        for _ in range(4):
            if len(trick) >= steps and seat % 2 == 0:
                break
            if len(trick) == 3 and seat % 2 == 1:
                trick = None
                break
            h = cur[seat]
            led = trick[0] // 13 if trick else None
            legal = h & SUIT[led] if led is not None and h & SUIT[led] else h
            c = rng.choice(cards_of(legal))
            if led is not None and c // 13 != led:
                if seat == 1:
                    vE2 |= 1 << led
                elif seat == 3:
                    vW2 |= 1 << led
            cur[seat] ^= 1 << c
            trick.append(c)
            seat = (seat + 1) & 3
        if trick is None or seat % 2 == 1 or len(trick) == 0 or len(trick) > 3:
            continue
        pool2 = cur[1] | cur[3]
        named2 = named & pool2
        cells = enumerate_cells(pool2, popcount(cur[1]), popcount(cur[3]), vE2, vW2, named2)
        pick = [i for i in range(len(cells)) if rng.random() < .6] or [rng.randrange(len(cells))]
        lays = layouts_of([(cells[i][0], cells[i][1]) for i in pick], pool2, named2)
        br = Brute(trump)
        h = cur[seat]
        led = trick[0] // 13
        legal = h & SUIT[led] if h & SUIT[led] else h
        refs = {}
        for c in cards_of(legal):
            nN, nS = (cur[0] ^ (1 << c), cur[2]) if seat == 0 else (cur[0], cur[2] ^ (1 << c))
            refs[c] = br._after(nN, nS, pool2, lays, leader, tuple(trick) + (c,))
        left = max(popcount(cur[0]), popcount(cur[2]))
        done['trick'] += 1
        for m, sv in solvers.items():
            sv.position(trump, leader, cur[0], cur[2], pool2, named2, trick)
            sv.cells([(eu, pin) for eu, pin, _ in cells])
            wrong = False
            for need in range(1, left + 1):
                got = sv.query(need, pick)['cards']
                if set(got) != set(refs) or any(got[c] != (refs[c] >= need) for c in refs):
                    wrong = True
            if wrong:
                bad[m]['trick'] += 1
                if len(examples[m]) < 5:
                    examples[m].append(('trick', trump, leader, hex(cur[0]), hex(cur[2]), hex(pool2), hex(named2), trick, pick, refs))
    for sv in solvers.values():
        sv.close()
    print('%d-card endings, seed %d: %d every-shape, %d subset, %d in-trick positions; %.0f s' % (k, seed, done['every'], done['subset'], done['trick'], time.time() - started))
    for m in modes:
        print('  --def %-4s mismatches with brute force: every %d, subset %d, in-trick %d' % (m, bad[m]['every'], bad[m]['subset'], bad[m]['trick']))
        for ex in examples[m][:3]:
            print('      ', ex)
    if pooled is not None:
        print('  pooled_ref.py against brute force (every shape, and the true whole shape): %d compared, %d mismatches' % (done['pooled'], bad_pooled))


if __name__ == '__main__':
    main()
