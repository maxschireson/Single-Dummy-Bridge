"""Reading the auction for the analysis: Sid's hand-fit scorer weights the layouts it cannot see, and the cell game
(cells.py driving native/cells) turns those weights into chances of making against best defence.

- `Weights`: every card-fit layout of the two hands the declaring side cannot see, each weighted by the scorer's fit of
  each hidden seat's thirteen cards to the calls that seat made (as experiments/sure_tricks/cells/belief.py does, after
  bridge_harness/gen6.py). The auction only: the reading of the play beyond show-outs is not included.
- `AuctionReader.declaring`: at a decision of the declaring side, for each card, the auction weight of a set of cells
  that ONE line starting with that card wins against every defence (the cell game's floor: a lower bound on the chance
  of making, with no strategy fusion). Cells fix East's length in each suit and, at the named levels, who holds the top
  card of up to two runs of unseen honours, so that a finesse counts in the half where it wins. Only floors are
  reported: a cell's ceiling is not an upper bound on the chance, since a line can win part of a cell. `after` gives
  declarer's best floor after a defender's card.
- `AuctionReader.marginals` and `layout_logw`: where the auction puts an unseen card, and how likely the auction makes a
  layout, for the exchange explanations.

The scorer is the bundle's (Sid's own reading: `spec['scorer']`); the bidder Sid bids with is deterministic, so this
reads Sid's calls as precisely as the scorer fits them. A human's calls are read as if made in Sid's system.
"""
from __future__ import annotations

from itertools import combinations
import math
import os
from pathlib import Path
import random
import time

import numpy as np

from . import cells as C


def default_binary():
    return os.environ.get('SIDPLAY_CELLS_BIN') or str(Path(__file__).resolve().parents[1] / 'native' / 'cells')


def _mask(cards):
    m = 0
    for c in cards:
        m |= 1 << c
    return m


class Weights:
    """Layouts of the two hidden hands (East's hand in the rotated frame as rows of `east`), scorer-weighted."""

    def __init__(self, reader, pos, seats, played, ctx, limit):
        self.cards = C.cards_of(pos['pool'])
        pool = self.cards
        forced = np.full(len(pool), -1, np.int8)            # 0 East, 1 West
        for i, c in enumerate(pool):
            if pos['vE'] >> (c // 13) & 1:
                forced[i] = 1
            elif pos['vW'] >> (c // 13) & 1:
                forced[i] = 0
        free = np.flatnonzero(forced < 0)
        need_e = pos['cE'] - int((forced == 0).sum())
        self.ok = 0 <= need_e <= len(free) and math.comb(len(free), need_e) <= limit
        if not self.ok:
            return
        combos = (np.fromiter((i for c in combinations(range(len(free)), need_e) for i in c), np.int32).reshape(-1, need_e)
                  if need_e else np.zeros((1, 0), np.int32))
        east = np.zeros((len(combos), len(pool)), bool)
        east[:, forced == 0] = True
        if need_e:
            east[np.repeat(np.arange(len(combos)), need_e), free[combos.ravel()]] = True
        self.east = east
        logw = np.zeros(len(east))
        for is_east, seat in ((True, seats[0]), (False, seats[1])):
            member = np.zeros((len(east), 52), np.int8)
            member[:, pool] = east if is_east else ~east
            member[:, list(played[seat])] = 1
            logw += reader.seat_logw(member, seat, ctx)
        w = np.exp(logw - logw.max())
        self.w = w / w.sum()

    def cell_weights(self, named=0):
        """{(eu, pin): weight} for the cells of a level with these named cards (belief.py's cell_weights)."""
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


class AuctionReader:
    """One per board (one cells process, whose tables stay valid across positions of the board)."""

    def __init__(self, scorer_path, binary=None, maxnodes=3_000_000, layout_limit=200_000, named=2):
        from bridge_harness.gen6_nets import FitScorer, hand_types
        self.scorer, self.hand_types = FitScorer(scorer_path), hand_types
        self.binary = binary or default_binary()
        self.maxnodes, self.layout_limit, self.named = maxnodes, layout_limit, named
        self.sv = None
        self.seconds = 0.
        self.capped = 0

    def available(self):
        return Path(self.binary).is_file() and os.access(self.binary, os.X_OK)

    def close(self):
        if self.sv is not None:
            self.sv.close()
            self.sv = None

    # ---- scorer ----------------------------------------------------------------------------------
    def seat_logw(self, member, seat, ctx):
        """log fit of each row's thirteen cards (membership rows, n x 52) to the calls `seat` made."""
        length, hon = self.hand_types(member)
        return self.scorer.type_log_score(length, hon, seat, ctx['dealer'], ctx['vul'], ctx['calls'])

    def layout_logw(self, hands, seats, played, ctx):
        """log weight of one layout: the hidden seats' remaining cards (hands[seat]) plus what they have played."""
        total = 0.
        for s in seats:
            member = np.zeros((1, 52), np.int8)
            member[0, list(hands[s] | played[s])] = 1
            total += float(self.seat_logw(member, s, ctx)[0])
        return total

    def marginals(self, st, seats, played, ctx, samples=6000, seed=0):
        """{card: {seat: P(seat holds it)}} for the cards the hidden seats hold, by the auction: uniform card-fit
        deals (sizes, show-outs) importance-weighted by the scorer."""
        pool = sorted(set().union(*(st.hands[s] for s in seats)))
        sizes = [len(st.hands[s]) for s in seats]
        rng = random.Random(seed)
        rows, tries = [], 0
        while len(rows) < samples and tries < samples * 20:
            tries += 1
            deck = pool[:]
            rng.shuffle(deck)
            deal, k, ok = [], 0, True
            for s, n in zip(seats, sizes):
                part = deck[k:k + n]
                k += n
                if any(c // 13 in st.voids[s] for c in part):
                    ok = False
                    break
                deal.append(part)
            if ok:
                rows.append(deal)
        if not rows:
            return None
        logw = np.zeros(len(rows))
        for j, s in enumerate(seats):
            member = np.zeros((len(rows), 52), np.int8)
            for i, deal in enumerate(rows):
                member[i, deal[j]] = 1
            member[:, list(played[s])] = 1
            logw += self.seat_logw(member, s, ctx)
        w = np.exp(logw - logw.max())
        w /= w.sum()
        out = {c: {s: 0. for s in seats} for c in pool}
        for i, deal in enumerate(rows):
            for j, s in enumerate(seats):
                for c in deal[j]:
                    out[c][s] += w[i]
        return out

    # ---- the cell game -------------------------------------------------------------------------
    def _solver(self):
        if self.sv is None or self.sv.proc.poll() is not None:
            self.sv = C.Solver(self.binary, ('--maxnodes', str(self.maxnodes)))
        return self.sv

    def _frame(self, st):
        """The position from the declaring side's view, rotated so it sits North-South, as cells.py wants it."""
        r = st.declarer % 2
        real = lambda f: (f + r) % 4
        voids = lambda s: sum(1 << x for x in st.voids[s])
        e, w = real(1), real(3)
        pos = dict(trump=st.trump, leader=(st.leader - r) % 4, hN=_mask(st.hands[real(0)]), hS=_mask(st.hands[real(2)]),
                   pool=_mask(st.hands[e] | st.hands[w]), cE=len(st.hands[e]), cW=len(st.hands[w]),
                   vE=voids(e), vW=voids(w), trick=[c for _, c in st.trick])
        return pos, (e, w)

    def _levels(self, st, need, played, ctx, must=None):
        """Floors for the declaring side's cards (one per run) at this position: the shape level, then up to
        `self.named` levels that also fix who holds the top card of the most promising runs of unseen honours
        (cells.honour_runs order), each built on the one before as pipeline.py does. Returns (floors {rep: floor},
        runs, outright) or None when the layouts are too many."""
        pos, seats = self._frame(st)
        pos['need'] = need - st.decl_won
        wts = Weights(self, pos, seats, played, ctx, self.layout_limit)
        if not wts.ok:
            return None
        sv = self._solver()
        must = list(must or [])
        level = C.Level(sv, pos)
        level.add_weights('a', wts.cell_weights(0))
        out = level.outright()
        sure = {r for r in level.reps if out and out.get(r)}
        if sure and all(r in sure for r in must):
            return {r: (1. if r in sure else None) for r in level.reps}, level.runs, True
        level.singles()
        floors = {r: f['floor'] for r, f in level.floors('a', must=must).items()}
        floors.update({r: 1. for r in sure})
        self.capped += level.stats['capped']
        named = 0
        for run in C.honour_runs(pos)[:self.named]:
            if min([max(floors.values() or [0.])] + [floors.get(r, 0.) for r in must]) >= 0.999:
                break
            named |= 1 << run['card']
            level = C.Level(sv, pos, named=named, parent=level)
            level.add_weights('a', wts.cell_weights(named))
            level.singles()
            for r, f in level.floors('a', must=must).items():
                floors[r] = max(floors.get(r, 0.), f['floor'])
            self.capped += level.stats['capped']
        return floors, level.runs, bool(sure)

    def declaring(self, st, need, played, ctx, card):
        """The declaring side to move: the best floor among its cards and the floor of `card` (the card played), each
        the auction weight of layouts one line starting with that card provably wins against every defence.
        None if the layouts are too many."""
        k = need - st.decl_won
        legal = st.legal()
        if k <= 0 or k > st.remaining:
            v = 1. if k <= 0 else 0.
            return dict(chances={c: v for c in legal}, best=v, played=v, trivial=True)
        t0 = time.perf_counter()
        pos, _ = self._frame(st)
        pos['need'] = k
        rep = {c: r[0] for r in C.runs_of(pos) for c in r}
        got = self._levels(st, need, played, ctx, must=[rep[card]])
        self.seconds += time.perf_counter() - t0
        if got is None:
            return None
        floors, runs, outright = got
        chances = {c: floors.get(rep[c]) for c in legal}
        if chances[card] is None:
            chances[card] = 0. if outright else chances[card]
        best = max([v for v in chances.values() if v is not None] or [0.])
        return dict(chances=chances, best=best, played=chances[card] or 0.)

    def after(self, st, card, need, played, ctx):
        """Declarer's best floor after the mover (a defender) plays `card`. None if a defender would be on play next
        (the cell game's questions need the declaring side to play) or if the layouts are too many."""
        nxt = st.copy()
        nxt.play(card)
        nplayed = [set(p) for p in played]
        nplayed[st.mover].add(card)
        if nxt.done_tricks == 13:
            return 1. if nxt.decl_won >= need else 0.
        k = need - nxt.decl_won
        if k <= 0 or k > nxt.remaining:
            return 1. if k <= 0 else 0.
        if nxt.mover % 2 != nxt.declarer % 2:
            return None
        t0 = time.perf_counter()
        got = self._levels(nxt, need, nplayed, ctx)
        self.seconds += time.perf_counter() - t0
        if got is None:
            return None
        floors, _, _ = got
        return max([v for v in floors.values() if v is not None] or [0.])
