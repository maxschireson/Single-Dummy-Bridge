"""Tables where the bot's card at 8 cards left the actual layout inside a certified set and the contract still went
down: where was the line dropped, and would today's outright-claim logic have caught it there?

usage: lost_lines.py DD_OUT.jsonl [DD_OUT.jsonl ...] -- BOARDS.json [BOARDS.json ...]

The cell followed is the actual shape plus the actual holders of the two cards named at the 8-card decision. At each
later turn of declarer or dummy: which cards keep a guarantee in that cell. The first turn where some card keeps it
and the card played does not is where the line was dropped. There: cards left, and whether some card guaranteed
the contract outright (every shape, nothing named), which is what the 8X claim logic already asks.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arena_positions import SEATS, SUITS, card, hand, mask, winner
from celllib import Solver, popcount, SUIT, enumerate_cells
from pipeline import name

args = sys.argv[1:]
dd_files, board_files = args[:args.index('--')], args[args.index('--') + 1:]
RK = '23456789TJQKA'
def parse(n): return 13 * 'SHDC'.index(n[0]) + RK.index(n[1])
want = {}
for f in dd_files:
    for l in open(f):
        r = json.loads(l)
        if r['claim'] or r['made']:
            continue
        i = r['cards_list'].index(r['played'])
        a0, a2 = r['in0'][i], bool(r['in2'] and r['in2'][i])
        if a0 or a2:
            want[r['table']] = dict(shape=a0, named=[parse(x) for x in (r['named'] or [])] if a2 and not a0 else [], contract=r['contract'], game=r['game'], cards=r['cards'])
sv = Solver('./cells', ('--def', 'ends'))
seen, rows = set(), []
for fn in board_files:
    for b in json.load(open(fn)).values():
        for cond in b['conditions'].values():
            for t in cond['tables']:
                key = (b['board']['id'], t['contract'], t['declarer'], tuple(t['plays']))
                if key in seen:
                    continue
                seen.add(key)
                ti = len(seen) - 1
                if ti not in want:
                    continue
                w = want[ti]
                k = t['contract']
                level, strain = int(k[0]), k[1]
                trump = 4 if strain == 'N' else SUITS.index(strain)
                decl = SEATS.index(t['declarer'])
                side = decl % 2
                rot = (lambda s: s) if side == 0 else (lambda s: (s + 3) % 4)
                hands = [set(hand(h)) for h in b['board']['hands']]
                plays = [(SEATS.index(p[0]), card(p[1:])) for p in t['plays']]
                target = level + 6
                e_real = [s for s in range(4) if s % 2 != side and rot(s) == 1][0]
                w_real = [s for s in range(4) if s % 2 != side and rot(s) == 3][0]
                n_real = [s for s in range(4) if rot(s) == 0][0]
                s_real = [s for s in range(4) if rot(s) == 2][0]
                won, trick, leader = 0, [], plays[0][0]
                voids = {s: 0 for s in range(4)}
                started, found = False, None
                for i, (seat, c) in enumerate(plays):
                    if not trick:
                        leader = seat
                    left = len(hands[seat])
                    if seat % 2 == side and left <= w['cards'] and found is None:
                        need = target - won
                        if 0 < need <= left:
                            pool = mask(hands[e_real] | hands[w_real])
                            east = mask(hands[e_real])
                            nm = mask(x for x in w['named'] if pool >> x & 1)
                            eu = tuple(popcount(east & ~nm & SUIT[s]) for s in range(4))
                            sv.position(trump, rot(leader), mask(hands[n_real]), mask(hands[s_real]), pool, nm, [x for _, x in trick])
                            sv.cells([(eu, east & nm)])
                            r = sv.query(need)['cards']
                            holds, keeps = any(r.values()), bool(r[c])
                            if holds:
                                started = True
                            if started and holds and not keeps:
                                cells = enumerate_cells(pool, len(hands[e_real]), len(hands[w_real]), voids[e_real], voids[w_real], 0)
                                sv.position(trump, rot(leader), mask(hands[n_real]), mask(hands[s_real]), pool, 0, [x for _, x in trick])
                                sv.cells([(e, p) for e, p, _ in cells])
                                o = sv.query(need)['cards']
                                found = dict(table=ti, contract=k, game=w['game'], level_of_set='shape' if w['shape'] else 'two named', cards_left=left,
                                             trick=i // 4 + 1, played=name(c), keepers=[name(x) for x, v in r.items() if v],
                                             outright=any(o.values()), outright_cards=[name(x) for x, v in o.items() if v], shapes=len(cells))
                    if trick and c // 13 != trick[0][1] // 13:
                        voids[seat] |= 1 << (trick[0][1] // 13)
                    hands[seat].discard(c)
                    trick.append((seat, c))
                    if len(trick) == 4:
                        wn = winner(leader, [x for _, x in trick], trump)
                        won += wn % 2 == side
                        trick = []
                rows.append(found or dict(table=ti, contract=k, none=True, level_of_set='shape' if w['shape'] else 'two named', game=w['game']))
sv.close()
for r in sorted(rows, key=lambda r: r['table']):
    if r.get('none'):
        print('table %4d %-4s %-9s  no turn found where the card played dropped a kept guarantee' % (r['table'], r['contract'], r['level_of_set']))
    else:
        print('table %4d %-4s %-9s  dropped at trick %2d with %d cards left: played %s, keeping cards %s; outright claim there: %s (%d shapes still open)' % (
            r['table'], r['contract'], r['level_of_set'], r['trick'], r['cards_left'], r['played'], ' '.join(r['keepers']), 'yes' if r['outright'] else 'no', r['shapes']))
ok = [r for r in rows if not r.get('none')]
for lev in ('shape', 'two named'):
    s = [r for r in ok if r['level_of_set'] == lev]
    print('%s-level sets: %d tables; outright claim available where the line was dropped: %d; only the conditional line: %d' % (lev, len(s), sum(r['outright'] for r in s), sum(not r['outright'] for r in s)))
import collections
print('cards left where dropped:', dict(sorted(collections.Counter(r['cards_left'] for r in ok).items(), reverse=True)), '| games, slams, doubled:', sum(r['game'] for r in ok), 'of', len(ok))
