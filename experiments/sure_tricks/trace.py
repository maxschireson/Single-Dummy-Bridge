"""Trace why a root card does not win every world: follow the defenders' most damaging replies."""
import sys, json
from exact import *
from fusionlab import *

def trace(ex, state, alive, names, depth=0, maxdepth=14):
    played, trick, leader, need = state
    if need <= 0 or depth > maxdepth:
        return
    seat = (leader + len(trick)) % 4
    worlds = [i for i in range(ex.k) if alive >> i & 1]
    fr = ex.front(played, trick, leader, need, alive)
    tag = lambda m: '{' + ','.join(names[i] for i in range(ex.k) if m >> i & 1) + '}'
    pad = '  ' * depth
    if seat % 2 == ex.side:
        h = ex.hand(worlds[0], seat, played)
        live = ex.all_cards(0) & ~played | bits(c for _, c in trick)
        best = None
        for c in ex.groups(h, ex.legal(h, trick), live):
            u = 0
            for i in worlds:
                if ex.dd(i, played, trick, leader)[c] >= need:
                    u |= 1 << i
            sub = ex.front(*ex.step(played, trick, leader, need, seat, c), u) if u & (u - 1) else (u,)
            w = max(sub, key=ex.weight)
            if best is None or ex.weight(w) > ex.weight(best[1]):
                best = (c, w, u)
        c, w, u = best
        print(pad + '%s plays %s (best; wins %s of %s)' % (SEATS[seat], symbol(c), tag(w), tag(alive)))
        trace(ex, ex.step(played, trick, leader, need, seat, c), u, names, depth + 1, maxdepth)
    else:
        options = {}
        for i in worlds:
            for c in cards_of(ex.legal(ex.hand(i, seat, played), trick)):
                options[c] = options.get(c, 0) | 1 << i
        worst = None
        for c, a in options.items():
            if a & (a - 1) == 0:
                continue
            sub = ex.front(*ex.step(played, trick, leader, need, seat, c), a)
            full = a in sub
            if not full:
                w = max(sub, key=ex.weight)
                if worst is None or ex.weight(a) - ex.weight(w) > worst[3]:
                    worst = (c, a, w, ex.weight(a) - ex.weight(w))
        if worst is None:
            print(pad + '%s: no reply hurts (front %s)' % (SEATS[seat], [tag(m) for m in fr]))
            return
        c, a, w, _ = worst
        print(pad + '%s plays %s, possible in %s; declarer can then win at most %s' % (SEATS[seat], symbol(c), tag(a), tag(w)))
        trace(ex, ex.step(played, trick, leader, need, seat, c), a, names, depth + 1, maxdepth)

if __name__ == '__main__':
    data = json.load(open('fusion_deals.json'))
    sid, prefix, first = sys.argv[1], sys.argv[2].split(), sys.argv[3]
    st = [s for s in data['sets'] if s['id'] == sid][0]
    deals = {d['id']: d for d in data['deals']}
    KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')
    boards = [Board.from_dict({k: deals[i][k] for k in KEYS}) for i in st['deals']]
    ex = Exact.from_boards(boards, [card(c) for c in prefix], weights=[deals[i].get('weight', 1) for i in st['deals']])
    names = [i.split('-')[1] for i in st['deals']]
    seat = (ex.root_leader + len(ex.root_trick)) % 4
    c = card(first)
    print('root: %s plays %s' % (SEATS[seat], first))
    trace(ex, ex.step(0, ex.root_trick, ex.root_leader, ex.root_need, seat, c), (1 << ex.k) - 1, names, 1)
