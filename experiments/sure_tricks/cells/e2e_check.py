"""End-to-end check on recorded play: a whole-shape guarantee, once held and kept, must hold to the end.

usage: e2e_check.py CARDS BOARDS.json [BOARDS.json ...]

For every played table and every turn of declarer or dummy with CARDS or fewer cards: the cell is the ACTUAL shape of
the hidden hands at that moment (one cell, no named card), and the solver says which legal cards guarantee the
contract in that cell. If the card played is one of them, then at the declaring side's next turn some card must
again guarantee it, whatever the defenders did in between, and a table that keeps to such cards to the end must make
its contract. A violation is a bug in the solver or in the position encoding.
Also checks the replay itself: tricks counted here against the record's declarer_tricks.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))      # the scripts' own folder (for python -I)
from arena_positions import SEATS, SUITS, card, hand, mask, winner
from celllib import Solver, popcount, SUIT

maxcards, files = int(sys.argv[1]), sys.argv[2:]
sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '50000000'))
tables = turns = held = kept = violations = end_viol = replay_bad = capped = 0
made_after_kept = 0
seen = set()
examples = []
for fn in files:
    for b in json.load(open(fn)).values():
        for cond in b['conditions'].values():
            for t in cond['tables']:
                key = (b['board']['id'], t['contract'], t['declarer'], tuple(t['plays']))
                if key in seen:
                    continue
                seen.add(key)
                k = t['contract']
                if not k or k[0] not in '1234567' or t['declarer'] not in SEATS:
                    continue
                level, strain = int(k[0]), k[1]
                trump = 4 if strain == 'N' else SUITS.index(strain)
                decl = SEATS.index(t['declarer'])
                side = decl % 2
                rot = (lambda s: s) if side == 0 else (lambda s: (s + 3) % 4)
                hands = [set(hand(h)) for h in b['board']['hands']]
                plays = [(SEATS.index(p[0]), card(p[1:])) for p in t['plays']]
                if len(plays) != 52:
                    continue
                tables += 1
                target = level + 6
                e_real = [s for s in range(4) if s % 2 != side and rot(s) == 1][0]
                w_real = [s for s in range(4) if s % 2 != side and rot(s) == 3][0]
                n_real = [s for s in range(4) if rot(s) == 0][0]
                s_real = [s for s in range(4) if rot(s) == 2][0]
                won, trick, leader = 0, [], plays[0][0]
                pending = False          # the declaring side's last card kept a whole-shape guarantee
                for i, (seat, c) in enumerate(plays):
                    if not trick:
                        leader = seat
                    left = len(hands[seat])
                    if seat % 2 == side and left <= maxcards:
                        need = target - won
                        if need <= 0:
                            keeps, holds = True, True
                        elif need > left:
                            keeps, holds = False, False
                        else:
                            pool = mask(hands[e_real] | hands[w_real])
                            east = mask(hands[e_real])
                            eu = tuple(popcount(east & SUIT[s]) for s in range(4))
                            sv.position(trump, rot(leader), mask(hands[n_real]), mask(hands[s_real]), pool, 0, [x for _, x in trick])
                            sv.cells([(eu, 0)])
                            r = sv.query(need)
                            if 'capped' in r:
                                capped += 1
                                pending = False
                                keeps = holds = None
                            else:
                                holds = any(r['cards'].values())
                                keeps = bool(r['cards'][c])
                        if holds is not None:
                            turns += 1
                            held += bool(holds)
                            if pending and not holds:
                                violations += 1
                                if len(examples) < 5:
                                    examples.append((b['board']['id'][-12:], k, t['declarer'], 'play', i))
                            kept += bool(keeps)
                            pending = bool(keeps)
                    hands[seat].discard(c)
                    trick.append((seat, c))
                    if len(trick) == 4:
                        w = winner(leader, [x for _, x in trick], trump)
                        won += w % 2 == side
                        trick = []
                replay_bad += won != t['declarer_tricks']
                if pending:
                    made_after_kept += 1
                    if won < target:
                        end_viol += 1
                        if len(examples) < 5:
                            examples.append((b['board']['id'][-12:], k, t['declarer'], 'end'))
sv.close()
print('%d tables; tricks counted in the replay differ from the record in %d' % (tables, replay_bad))
print('declaring-side turns with %d or fewer cards: %d; a whole-shape guarantee held at %d; the card played kept it at %d' % (maxcards, turns, held, kept))
print('guarantee kept by the card played but gone at the declaring side\'s next turn: %d' % violations)
print('tables whose last declaring-side card kept a guarantee: %d; of these not made: %d' % (made_after_kept, end_viol))
print('questions capped:', capped)
for e in examples:
    print('  ', e)
