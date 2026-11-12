"""How much of the sure-trick search lies at or below a 4-card (or 5-card) ending: node counts with and
without a perfect lookup at that frontier. Usage: lookup_gain.py fusion_deals.json name"""
import json, sys, time, collections
from sure import Sure
from sure_positions import P
from fusionlab import Board, card, SEATS


class Counted(Sure):
    def _can(self, need, ha, hb, pool, cnt, void, known, trick, leader):
        key = (need, ha, hb, pool, cnt, void, known, trick, leader)
        new = key not in self.memo
        r = super()._can(need, ha, hb, pool, cnt, void, known, trick, leader)
        if new and key in self.memo:
            total = bin(ha).count('1') + bin(hb).count('1') + bin(pool).count('1')
            self.by[total] += 1
            if total in (16, 20):
                self.states[total].add(key[1:])
        return r


if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    deals = {d['id']: d for d in data['deals']}
    KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')
    for name in sys.argv[2:]:
        st, did, prefix, pins, note = P[name]
        b = Board.from_dict({k: deals[did][k] for k in KEYS})
        known = {SEATS.index(s): [card(c) for c in cs.split()] for s, cs in pins.items()}
        s = Counted.from_game(b, [card(c) for c in prefix.split()], known)
        s.by, s.states = collections.Counter(), {16: set(), 20: set()}
        t = time.time()
        left = 13 - len(prefix.split()) // 4
        s.root_cards(left)
        total = sum(s.by.values())
        out = dict(name=name, cards_left=left, nodes=total, seconds=round(time.time() - t, 1))
        for k, lab in ((16, '4'), (20, '5')):
            above = sum(n for tot, n in s.by.items() if tot > k)
            probes = len(s.states[k])
            out['lookup_%s_card' % lab] = dict(nodes_above=above, distinct_frontier_positions=probes,
                                             work_with_table=above + probes, ratio=round(total / max(1, above + probes), 1))
        print(json.dumps(out), flush=True)
