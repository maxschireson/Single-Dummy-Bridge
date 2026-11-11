"""Gen7 tree search (prototype): a few tricks of play from each seat's own view, then double dummy.

Plain PIMC values a card by solving each layout double dummy from the next card on, so every
later card of all four hands is chosen with all four hands in view. Here the next `tricks`
tricks are played out first:

  another seat's card   its policy-net probabilities given only what that seat sees in the layout
                        (its hand there, dummy, the play so far). The most probable cards are kept,
                        up to `breadth` of them or until their probabilities add to `mass`, and the
                        node is their weighted average. A card enters the tree only by being likely
                        from that seat's own view; no double-dummy reply is ever added.
                        The net is unsure where Gen 6 is not, and that doubt would be read as the
                        seat making mistakes; `reply_power` and `reply_gap` sharpen its choice.
  the decider's later   one choice for every layout that looks the same to the decider at that point
  card                  (same cards played so far): the card with the best average over those layouts.
                        Candidates are the net's most probable cards from the decider's own view.
  the end of the        each layout is solved double dummy from there.
  horizon

The tree is walked once for all layouts together, carrying for each layout the probability of the
play so far in that layout. That is what makes the decider's later choice a single choice.

With tricks=0 the value of a card is exactly PIMC's (tested). Not supported: the opening lead
(dummy is not yet a public hand).
"""
from dataclasses import dataclass

import numpy as np

from .core import Observation, winner
from .gen7_net import INPUTS

SUIT = np.arange(52)[None, :] // 13 == np.arange(4)[:, None]


@dataclass(frozen=True)
class TreeConfig:
    tricks: int = 2             # horizon: the end of this many tricks, counting the one in progress; 0 = plain PIMC
    breadth: int = 2            # most cards kept at a node below the root
    mass: float = .9            # cards are kept until their probabilities add to this
    layouts: int = 8            # layouts carried into the tree
    reply_power: float = 1.     # another seat's probabilities are raised to this power: above 1 trusts its likeliest cards more
    reply_gap: float = 99.      # another seat's cards the net rates this many tricks worse than its best-rated card are dropped
    reply: str = 'net'          # another seat's card: 'net' as above | 'dd' its double-dummy best in each layout, as PIMC assumes
    own_breadth: int = 0        # most cards considered at the decider's own later turn; 0 = `breadth`

    def __post_init__(self):
        if not (0 <= self.tricks <= 13 and 1 <= self.breadth <= 13 and 0 < self.mass <= 1 and 1 <= self.layouts <= 4096
                and 0 < self.reply_power <= 64 and self.reply_gap >= 0 and self.reply in ('net', 'dd') and 0 <= self.own_breadth <= 13):
            raise ValueError('Invalid tree settings')


def seat_view(o, history, dummy_hand, chooser, seat, hand, declarer_tricks=None):
    """The Observation `chooser` has when choosing a card from `seat` (its own hand, or dummy's for declarer)
    after `history`, holding `hand`. Public facts (contract, auction, dummy) come from `o`."""
    c = o.contract
    start = len(history) - len(history) % 4
    trick = tuple(history[start:])
    if declarer_tricks is None:
        declarer_tricks = sum(winner(history[t:t + 4], c.trump) % 2 == c.declarer % 2 for t in range(0, start, 4))
    known = [None] * 4
    known[chooser] = tuple(sorted(hand))
    known[c.dummy] = tuple(sorted(dummy_hand))
    cards = known[seat]
    follow = [x for x in cards if x // 13 == trick[0][1] // 13] if trick else []
    return Observation(chooser, seat, tuple(known), tuple(follow or cards), tuple(history), trick,
                       trick[0][0] if trick else seat, c, o.dealer, o.vulnerability, o.auction, declarer_tricks)


class Tree:
    """One decision's search. `net` is a gen7_net.PolicyNet, `dds` a bridge_harness.dds.DDS."""

    def __init__(self, net, dds, config):
        self.net, self.dds, self.config = net, dds, config
        self.lines = self.net_rows = self.solves = self.nodes = 0

    def values(self, o, worlds, weights, cards=None):
        """{card: value} for the decider's candidate cards, in PIMCPlayer's units: declarer's final tricks
        if the decider's side declares, else minus them. `worlds` are full layouts of the cards still held."""
        c = o.contract
        if not o.history or o.known_hands[c.dummy] is None:
            raise ValueError('The tree needs dummy on the table')
        self.o, self.me = o, o.controller
        self.declaring = o.controller % 2 == c.declarer % 2
        self.visible = [s for s, h in enumerate(o.known_hands) if h is not None]
        self.member = np.zeros((len(worlds), 4, 52), bool)              # [layout, seat, card] at the root
        for i, w in enumerate(worlds):
            for s in range(4):
                self.member[i, s, list(w[s])] = True
        reach = np.asarray(weights, float) / float(np.sum(weights))
        out = {}
        for x in (o.legal if cards is None else cards):
            out[x] = self.after(tuple(o.history), o.declarer_tricks, np.zeros(52, bool), 0, o.actor, x, reach)
        return out

    # ---- walking the tree ---------------------------------------------------------------
    def after(self, history, declarer_tricks, gone, tricks_done, seat, x, reach):
        """Value of the position after `seat` plays x."""
        c = self.o.contract
        history = history + ((seat, x),)
        gone = gone.copy()
        gone[x] = True
        if len(history) % 4 == 0:
            declarer_tricks += winner(history[-4:], c.trump) % 2 == c.declarer % 2
            tricks_done += 1
        return self.node(history, declarer_tricks, gone, tricks_done, reach)

    def node(self, history, declarer_tricks, gone, tricks_done, reach):
        """Sum over layouts of reach times the decider's value, with the play so far given."""
        cfg, c = self.config, self.o.contract
        self.nodes += 1
        trick = history[len(history) - len(history) % 4:]
        if len(history) == 52:
            return float(reach.sum()) * (declarer_tricks if self.declaring else -declarer_tricks)
        if cfg.tricks == 0 or (not trick and tricks_done >= cfg.tricks):
            return self.leaf(history, trick, declarer_tricks, gone, reach)
        seat = (winner(history[-4:], c.trump) if not trick else (trick[0][0] + len(trick)) % 4)
        chooser = c.declarer if seat == c.dummy else seat
        live = np.flatnonzero(reach > 1e-9 * reach.sum())
        held = self.member[live][:, seat] & ~gone                       # the seat's cards, layout by layout
        if trick:
            in_suit = held & SUIT[trick[0][1] // 13]
            legal = np.where(in_suit.any(axis=1)[:, None], in_suit, held)
        else:
            legal = held
        dummy_hand = np.flatnonzero(self.member[0, c.dummy] & ~gone)
        if chooser == self.me:                                           # the decider's own later card: one choice for all layouts
            options = np.flatnonzero(legal[0])
            if len(options) > 1:
                view = seat_view(self.o, history, dummy_hand, chooser, seat, np.flatnonzero(self.member[0, chooser] & ~gone), declarer_tricks)
                logp = self.net.log_policy([view])[0][options]
                self.net_rows += 1
                options = options[self.keep(np.exp(logp.astype(np.float64)), cfg.own_breadth or cfg.breadth, 1. if cfg.own_breadth else cfg.mass)[0]]
            return max(self.after(history, declarer_tricks, gone, tricks_done, seat, int(x), reach) for x in options)
        if legal.sum(axis=1).max() == 1 and len({int(row.argmax()) for row in legal}) == 1:      # forced, and the same card everywhere
            return self.after(history, declarer_tricks, gone, tricks_done, seat, int(legal[0].argmax()), reach)
        if cfg.reply == 'dd':               # the seat sees every hand, as in PIMC; only the decider's own later cards are made honest
            worlds = [tuple(tuple(int(x) for x in np.flatnonzero(self.member[i, s] & ~gone)) for s in range(4)) for i in live]
            solved = self.dds.solve_batch(worlds, c.trump, trick[0][0] if trick else seat, tuple(trick), fixed_seats=self.visible)
            self.solves += len(live)
            children = {}
            for layout, (values, _) in zip(live, solved):
                best = max(values.values())
                x = min(k for k, v in values.items() if v == best)
                children.setdefault(int(x), np.zeros(len(reach)))[layout] = reach[layout]
            return sum(self.after(history, declarer_tricks, gone, tricks_done, seat, x, r) for x, r in children.items())
        batch = self.reply_inputs(history, declarer_tricks, gone, seat, chooser, live, legal)
        logp, gap = self.net.policy_and_gap_arrays(batch)
        p = np.exp(cfg.reply_power * logp.astype(np.float64)) * legal
        if cfg.reply_gap < 99:                                           # drop what the net itself rates a clear mistake
            rated = np.where(legal, gap, np.inf)
            p = p * (rated <= rated.min(axis=1, keepdims=True) + cfg.reply_gap)
        self.net_rows += len(live)
        children = {}
        for row, layout in enumerate(live):
            options = np.flatnonzero(legal[row])
            kept, share = self.keep(p[row, options])
            for x, q in zip(options[kept], share):
                children.setdefault(int(x), np.zeros(len(reach)))[layout] = reach[layout] * q
        return sum(self.after(history, declarer_tricks, gone, tricks_done, seat, x, r) for x, r in children.items())

    def reply_inputs(self, history, declarer_tricks, gone, seat, chooser, live, legal):
        """Net inputs for another seat's choice, one row per live layout: what `chooser` sees there."""
        dummy_hand = np.flatnonzero(self.member[0, self.o.contract.dummy] & ~gone)
        base = self.net.encode(seat_view(self.o, history, dummy_hand, chooser, seat, (), declarer_tricks))
        batch = {k: np.broadcast_to(base[k], (len(live), *base[k].shape)) for k in INPUTS}
        state = batch['state'].copy()
        state[self.member[live][:, chooser] & ~gone] = 1                 # the chooser's own cards as it sees them
        batch['state'] = state
        if seat == chooser:
            batch['legal'] = legal
        return batch

    def keep(self, p, breadth=None, mass=None):
        """(indices of the cards kept, their renormalised probabilities): most probable first, at most
        `breadth`, stopping once they add to `mass`."""
        breadth, mass = breadth or self.config.breadth, mass or self.config.mass
        order = np.argsort(-p, kind='stable')[:breadth]
        total = np.cumsum(p[order]) / max(p.sum(), 1e-300)
        order = order[:int(np.searchsorted(total, mass - 1e-12)) + 1]
        return order, p[order] / max(p[order].sum(), 1e-300)

    def leaf(self, history, trick, declarer_tricks, gone, reach):
        c = self.o.contract
        live = np.flatnonzero(reach > 1e-9 * reach.sum())
        self.lines += 1
        worlds = [tuple(tuple(int(x) for x in np.flatnonzero(self.member[i, s] & ~gone)) for s in range(4)) for i in live]
        leader = trick[0][0] if trick else winner(history[-4:], c.trump)
        mover = (leader + len(trick)) % 4
        solved = self.dds.solve_batch(worlds, c.trump, leader, tuple(trick), fixed_seats=self.visible)
        self.solves += len(live)
        remaining = 13 - len(history) // 4
        total = 0.
        for i, (values, _) in zip(live, solved):
            best = max(values.values())
            tricks = declarer_tricks + (best if mover % 2 == c.declarer % 2 else remaining - best)
            total += reach[i] * (tricks if self.declaring else -tricks)
        return total
