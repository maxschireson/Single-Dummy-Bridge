"""Layout weights from the arena's hand-fit scorer (the auction only; the bots' reading of the play is not included).

For a recorded position (arena_positions.py), every card-fit layout of the two hidden hands is listed and weighted by
the scorer's value for each hidden seat's original thirteen cards, as bridge_harness/gen6.py does from trick 6.
"""
import sys
from itertools import combinations

import numpy as np

from celllib import SUIT, cards_of, popcount


class Belief:
    def __init__(self, repo, scorer_path):
        sys.path.insert(0, repo)
        from bridge_harness.gen6_nets import FitScorer, hand_types
        self.scorer, self.hand_types = FitScorer(scorer_path), hand_types

    def prepare(self, p, pos):
        """List the layouts of position `pos` (ints) / record `p` and weigh them. Sets self.cards, self.east, self.w."""
        pool = cards_of(pos['pool'])
        self.cards = pool
        forced = np.full(len(pool), -1, np.int8)            # 0 East, 1 West
        for i, c in enumerate(pool):
            if pos['vE'] >> (c // 13) & 1:
                forced[i] = 1
            elif pos['vW'] >> (c // 13) & 1:
                forced[i] = 0
        free = np.flatnonzero(forced < 0)
        need_e = pos['cE'] - int((forced == 0).sum())
        combos = np.fromiter((i for c in combinations(range(len(free)), need_e) for i in c), np.int32).reshape(-1, need_e) if need_e else np.zeros((1, 0), np.int32)
        east = np.zeros((len(combos), len(pool)), bool)
        east[:, forced == 0] = True
        if need_e:
            rows = np.repeat(np.arange(len(combos)), need_e)
            east[rows, free[combos.ravel()]] = True
        self.east = east
        logw = np.zeros(len(east))
        for is_east, seat, played in ((True, p['e_real'], int(p['e_played'], 16)), (False, p['w_real'], int(p['w_played'], 16))):
            member = np.zeros((len(east), 52), np.int8)
            member[:, pool] = east if is_east else ~east
            member[:, cards_of(played)] = 1
            assert (member.sum(axis=1) == 13).all()
            length, hon = self.hand_types(member)
            logw += self.scorer.type_log_score(length, hon, seat, p['dealer'], p['vul'], p['auction'])
        w = np.exp(logw - logw.max())
        self.w = w / w.sum()
        self.effective = 1. / float((self.w ** 2).sum())
        return self

    def cell_weights(self, named):
        """{(eu, pin): weight} for the cells of a level with these named cards."""
        cols = np.array(self.cards)
        is_named = np.array([(named >> c) & 1 for c in self.cards], bool)
        key = np.zeros(len(self.east), np.int64)
        for s in range(4):
            m = (cols // 13 == s) & ~is_named
            key = key * 16 + self.east[:, m].sum(axis=1)
        named_cols = np.flatnonzero(is_named)
        pinbits = np.zeros(len(self.east), np.int64)
        for j, col in enumerate(named_cols):
            pinbits |= self.east[:, col].astype(np.int64) << j
        full = key * (1 << len(named_cols)) + pinbits
        uniq, inv = np.unique(full, return_inverse=True)
        sums = np.bincount(inv.ravel(), weights=self.w, minlength=len(uniq))
        out = {}
        for u, wsum in zip(uniq, sums):
            pb, k = int(u) % (1 << len(named_cols)), int(u) >> len(named_cols)
            eu = ((k >> 12) & 15, (k >> 8) & 15, (k >> 4) & 15, k & 15)
            pin = 0
            for j, col in enumerate(named_cols):
                if pb >> j & 1:
                    pin |= 1 << self.cards[col]
            out[(eu, pin)] = float(wsum)
        return out

    def layout_weight(self, east_hand):
        row = np.array([(east_hand >> c) & 1 for c in self.cards], bool)
        hit = np.flatnonzero((self.east == row).all(axis=1))
        return float(self.w[hit[0]]) if len(hit) else None
