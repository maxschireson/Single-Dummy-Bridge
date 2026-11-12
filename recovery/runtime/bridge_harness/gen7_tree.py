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
                        reply='search' asks a search from that seat's own view instead (slow; it is
                        the model the net stands in for). reply='dd' is PIMC's own assumption.
  the decider's later   one choice for every layout that looks the same to the decider at that point
  card                  (same cards played so far): the card with the best average over those layouts.
                        Candidates are the net's most probable cards from the decider's own view.
                        With a handful of layouts this is weaker than it sounds: the other seats'
                        cards split the sample, and at the decider's next turn only one or two
                        layouts still look alike (measured: 1.4 of 8, 2.6 of 32, over two tricks),
                        so the choice is made nearly with the layout known. own='search' or
                        own='net' treats the decider's later self like any other seat instead.
  the end of the        each layout is solved double dummy from there.
  horizon

The tree is walked once for all layouts together, carrying for each layout the probability of the
play so far in that layout. That is what makes the decider's later choice a single choice.

Layouts stay together only while the same cards are played in them, and sampled layouts give the
hidden hands different spot cards, so the first low card a hidden hand plays tells them apart.
`plain=1` removes that: the hidden hands' low cards (2-9) are dealt by a fixed rule, the same in
every layout as far as the suit lengths allow, and at every node cards that do the same job count
as one card (touching cards; low cards that do not take the trick; low cards that take it).

`path` above zero turns on the stake rule, and the tree stops being uniform. Every node carries its
share of the search: 1 at each root card, multiplied by the probability of each card on the way
down (the other seats' cards by what the net gives them, the decider's own later cards by what the
net gives those). A node is searched on only while share x stake >= path, and at a node a card is
kept only while the cards before it leave that much uncovered. The stake is what one trick is worth
in IMPs to the decider at this decision: for each of the tree's layouts, the IMPs between declarer's
double-dummy result there and one trick fewer (declaring) or one more (defending), averaged over the
layouts, plus `spread` of their standard deviations. So a line of clear plays keeps its share and
runs deep, a close call splits its share and the tree is wide there but shallower below, and a
decision where a trick is an overtrick gets little search at all. `tricks`, `breadth` and `mass`
are then upper limits. A node cut short is solved double dummy where it stands, mid-trick or not.

With tricks=0 the value of a card is exactly PIMC's (tested). Not supported: the opening lead
(dummy is not yet a public hand).
"""
from dataclasses import dataclass

import numpy as np

from .core import Observation, imps, score, vulnerable, winner
from .gen7_net import INPUTS

SUIT = np.arange(52)[None, :] // 13 == np.arange(4)[:, None]
LOW = 8                     # rank index below which a card is a low card: 2 to 9


def plain_spots(worlds, weights, hidden):
    """(layouts, weights) with the hidden hands' low cards dealt by a fixed rule: in each suit the unseen low cards go
    to the hidden hands in turn from the bottom, as far as each hand's count allows. Honours and every suit length
    stay as they were. Layouts that become the same are merged."""
    merged = {}
    for w, weight in zip(worlds, weights):
        hands = [[c for c in h if not (s in hidden and c % 13 < LOW)] for s, h in enumerate(w)]
        for suit in range(4):
            pool = sorted(c for s in hidden for c in w[s] if c // 13 == suit and c % 13 < LOW)
            need = [sum(1 for c in w[s] if c // 13 == suit and c % 13 < LOW) for s in hidden]
            turn = 0
            for c in pool:
                while not need[turn % len(hidden)]:
                    turn += 1
                hands[hidden[turn % len(hidden)]].append(c)
                need[turn % len(hidden)] -= 1
                turn += 1
        key = tuple(tuple(sorted(h)) for h in hands)
        merged[key] = merged.get(key, 0.) + float(weight)
    return list(merged), list(merged.values())


def swing(contract, vulnerability, declaring, tricks):
    """IMPs one trick is worth to the side deciding when declarer is headed for `tricks`: the trick declarer would
    lose if that side declares, the one declarer would gain if it defends."""
    t = int(round(float(tricks)))
    t = min(max(t, 1), 13) if declaring else min(max(t, 0), 12) + 1
    vul = vulnerable(vulnerability, contract.declarer)
    return abs(imps(score(contract, t, vul) - score(contract, t - 1, vul)))


def stake(contract, vulnerability, declaring, tricks, weights, spread=0.):
    """What a trick is worth at a decision, in IMPs: the swing at declarer's double-dummy result in each layout,
    averaged with the layouts' weights, plus `spread` standard deviations. Layouts that disagree about the contract
    making give a high stake by themselves; `spread` leans further to the high side."""
    w = np.asarray(weights, float)
    w = w / w.sum()
    s = np.array([swing(contract, vulnerability, declaring, t) for t in tricks], float)
    mean = float(w @ s)
    return mean + spread * float(np.sqrt(max(float(w @ (s - mean) ** 2), 0.)))


@dataclass(frozen=True)
class TreeConfig:
    tricks: int = 2             # horizon: the end of this many tricks, counting the one in progress; 0 = plain PIMC
    breadth: int = 2            # most cards kept at a node below the root
    mass: float = .9            # cards are kept until their probabilities add to this
    layouts: int = 8            # layouts carried into the tree
    reply_power: float = 1.     # another seat's probabilities are raised to this power: above 1 trusts its likeliest cards more
    reply_gap: float = 99.      # another seat's cards the net rates this many tricks worse than its best-rated card are dropped
    reply: str = 'net'          # another seat's card: 'net' as above | 'dd' its double-dummy best in each layout, as PIMC assumes
                                # | 'search' what a search from that seat's own view plays (the tree's `replier`)
    own_breadth: int = 0        # most cards considered at the decider's own later turn; 0 = `breadth`
    own: str = 'best'           # the decider's own later card: 'best' the best average over the layouts that still look alike
                                # | 'net' drawn from the net like any other seat | 'search' what the `replier` plays from the decider's view
    plain: int = 0              # 1: hidden low cards dealt by a fixed rule, and cards that do the same job count as one (see above)
    reply_layouts: int = 8      # reply/own 'search': layouts the stand-in searcher solves at each such choice
    reply_pool: int = 64        # ... picked from this many card-fit layouts weighted by the hand-fit scorer
    path: float = 0.            # above 0, the stake rule (see above): search on only while share x stake >= path, in IMPs; 0 = uniform tree
    spread: float = 0.          # the stake is its mean over the layouts plus this many of their standard deviations
    path_solves: int = 0        # with `path`: once a root card's subtree has solved this many layouts, what is left of it is leaves; 0 = no limit

    def __post_init__(self):
        if not (0 <= self.tricks <= 13 and 1 <= self.breadth <= 13 and 0 < self.mass <= 1 and 1 <= self.layouts <= 4096
                and 0 < self.reply_power <= 64 and self.reply_gap >= 0 and self.reply in ('net', 'dd', 'search') and 0 <= self.own_breadth <= 13
                and self.own in ('best', 'net', 'search') and self.plain in (0, 1) and 1 <= self.reply_layouts <= self.reply_pool <= 65536
                and self.path >= 0 and self.spread >= 0 and self.path_solves >= 0):
            raise ValueError('Invalid tree settings')
        for name in ('tricks', 'breadth', 'layouts', 'own_breadth', 'plain', 'reply_layouts', 'reply_pool', 'path_solves'):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f'Tree {name} must be an integer')


class OverBudget(RuntimeError):
    """The search needed more double-dummy solves than its caller allowed."""


def seat_view(o, history, dummy_hand, chooser, seat, hand, declarer_tricks=None):
    """The Observation `chooser` has when choosing a card from `seat` (its own hand, or dummy's for declarer)
    after `history`, holding `hand`. Public facts (contract, auction, dummy) come from `o`."""
    c = o.contract
    start = len(history) - len(history) % 4
    trick = tuple(history[start:])
    if declarer_tricks is None:
        declarer_tricks = sum(winner(history[t:t + 4], c.trump) % 2 == c.declarer % 2 for t in range(0, start, 4))
    known = [None] * 4
    known[chooser] = tuple(sorted(int(x) for x in hand))
    known[c.dummy] = tuple(sorted(int(x) for x in dummy_hand))
    cards = known[seat]
    follow = [x for x in cards if x // 13 == trick[0][1] // 13] if trick else []
    return Observation(chooser, seat, tuple(known), tuple(follow or cards), tuple(history), trick,
                       trick[0][0] if trick else seat, c, o.dealer, o.vulnerability, o.auction, declarer_tricks)


class Tree:
    """One decision's search. `net` is a gen7_net.PolicyNet, `dds` a bridge_harness.dds.DDS."""

    def __init__(self, net, dds, config, replier=None, max_solves=0):
        """`replier(observation) -> {card: probability}` is what reply='search' asks for another seat's card.
        With `max_solves` above zero, `values` raises OverBudget once the search has solved more layouts than that."""
        if replier is None and 'search' in (config.reply, config.own):
            raise ValueError("reply='search' and own='search' need a replier")
        self.net, self.dds, self.config, self.replier, self.max_solves = net, dds, config, replier, max_solves
        self.replies = self.own_nodes = self.own_live = 0
        self.lines = self.net_rows = self.solves = self.nodes = 0
        self.stake = None           # with `path`: IMPs a trick is worth at the decision in hand
        self.flat = None            # with `path` or `plain`: {card: plain double-dummy value on the tree's own layouts}
        self.card_start = 0

    def values(self, o, worlds, weights, cards=None, stake=None):
        """{card: value} for the decider's candidate cards, in PIMCPlayer's units: declarer's final tricks
        if the decider's side declares, else minus them. `worlds` are full layouts of the cards still held.
        With `path`, `stake` replaces the tree's own reading of what a trick is worth here."""
        c = o.contract
        if not o.history or o.known_hands[c.dummy] is None:
            raise ValueError('The tree needs dummy on the table')
        self.o, self.me = o, o.controller
        self.declaring = o.controller % 2 == c.declarer % 2
        self.visible = [s for s, h in enumerate(o.known_hands) if h is not None]
        if self.config.plain:
            worlds, weights = plain_spots(worlds, weights, [s for s, h in enumerate(o.known_hands) if h is None])
        self.member = np.zeros((len(worlds), 4, 52), bool)              # [layout, seat, card] at the root
        for i, w in enumerate(worlds):
            for s in range(4):
                self.member[i, s, list(w[s])] = True
        reach = np.asarray(weights, float) / float(np.sum(weights))
        cards = list(o.legal if cards is None else cards)
        self.flat = self.stake = None
        if self.config.path > 0 or (self.config.plain and self.config.tricks):
            self.flat, each = self.double_dummy(cards, reach)       # also what a caller subtracts to get the tree's correction
            if self.config.path > 0:
                best = max(cards, key=lambda x: (self.flat[x], -x))
                self.stake = float(stake) if stake is not None else self.stake_of(each[best], reach)
        out = {}
        for x in cards:
            self.card_start = self.solves
            out[x] = self.after(tuple(o.history), o.declarer_tricks, np.zeros(52, bool), 0, o.actor, x, reach)
        return out

    # ---- the stake ------------------------------------------------------------------------
    def double_dummy(self, cards, reach):
        """({card: plain double-dummy value on the tree's layouts}, {card: declarer's final tricks in each layout})."""
        o = self.o
        live = np.flatnonzero(reach > 1e-9 * reach.sum())
        flat, each = {}, {}
        for x in cards:
            history, declarer_tricks, gone, _ = self.step(tuple(o.history), o.declarer_tricks, np.zeros(52, bool), 0, o.actor, x)
            tricks = self.leaf_tricks(history, history[len(history) - len(history) % 4:], declarer_tricks, gone, live)
            each[x] = tricks
            flat[x] = float(sum(reach[i] * (t if self.declaring else -t) for i, t in zip(live, tricks)))
        return flat, each

    def swing(self, tricks):
        """IMPs one trick is worth to the decider when declarer is headed for `tricks` (see `swing` above)."""
        return swing(self.o.contract, self.o.vulnerability, self.declaring, tricks)

    def stake_of(self, tricks, reach):
        """The stake from declarer's double-dummy result in each live layout (see `stake` above)."""
        live = np.flatnonzero(reach > 1e-9 * reach.sum())
        return stake(self.o.contract, self.o.vulnerability, self.declaring, tricks, reach[live], self.config.spread)

    # ---- walking the tree ---------------------------------------------------------------
    def step(self, history, declarer_tricks, gone, tricks_done, seat, x):
        """The position after `seat` plays x."""
        c = self.o.contract
        history = history + ((seat, x),)
        gone = gone.copy()
        gone[x] = True
        if len(history) % 4 == 0:
            declarer_tricks += winner(history[-4:], c.trump) % 2 == c.declarer % 2
            tricks_done += 1
        return history, declarer_tricks, gone, tricks_done

    def after(self, history, declarer_tricks, gone, tricks_done, seat, x, reach, effort=1.):
        """Value of the position after `seat` plays x. `effort` is the node's share of the search (the stake rule)."""
        return self.node(*self.step(history, declarer_tricks, gone, tricks_done, seat, x), reach, effort)

    def go(self, history, declarer_tricks, gone, tricks_done, seat, x, reach, effort):
        """`after` from inside the tree; the share of the search is passed on only under the stake rule."""
        if self.config.path > 0:
            return self.after(history, declarer_tricks, gone, tricks_done, seat, x, reach, effort)
        return self.after(history, declarer_tricks, gone, tricks_done, seat, x, reach)

    def node(self, history, declarer_tricks, gone, tricks_done, reach, effort=1.):
        """Sum over layouts of reach times the decider's value, with the play so far given."""
        cfg, c = self.config, self.o.contract
        self.nodes += 1
        trick = history[len(history) - len(history) % 4:]
        if len(history) == 52:
            return float(reach.sum()) * (declarer_tricks if self.declaring else -declarer_tricks)
        if cfg.tricks == 0 or (not trick and tricks_done >= cfg.tricks):
            return self.leaf(history, trick, declarer_tricks, gone, reach)
        if cfg.path > 0 and (effort * self.stake < cfg.path or (cfg.path_solves and self.solves - self.card_start >= cfg.path_solves)):
            return self.leaf(history, trick, declarer_tricks, gone, reach)      # not worth more search: double dummy from here
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
                self.own_nodes += 1                 # how many layouts still look the same to the decider here
                self.own_live += len(live)
                view = seat_view(self.o, history, dummy_hand, chooser, seat, np.flatnonzero(self.member[0, chooser] & ~gone), declarer_tricks)
                mine = self.member[0, seat] & ~gone
                if cfg.own == 'search':             # the decider's later self is a searching player too: its card, not the layout's best
                    share = self.replier(view)
                    self.replies += 1
                    self.spend(cfg.reply_layouts)
                    if cfg.plain:
                        cards, mass = self.same_job(np.array(list(share)), np.array(list(share.values())), mine, trick, seat, gone)
                    else:
                        cards = np.array(sorted(share, key=lambda x: (-share[x], x)))
                        mass = np.array([share[int(x)] for x in cards])
                    kept, part = self.keep(mass, cfg.own_breadth or cfg.breadth, 1., effort)
                    return sum(q * self.go(history, declarer_tricks, gone, tricks_done, seat, int(x), reach, effort * q) for x, q in zip(cards[kept], part))
                logp = self.net.log_policy([view])[0][options]
                self.net_rows += 1
                options, mass = self.same_job(options, np.exp(logp.astype(np.float64)), mine, trick, seat, gone)
                kept, share = self.keep(mass, cfg.own_breadth or cfg.breadth, 1. if cfg.own_breadth else cfg.mass, effort)
                if cfg.own == 'net':
                    return sum(q * self.go(history, declarer_tricks, gone, tricks_done, seat, int(x), reach, effort * q) for x, q in zip(options[kept], share))
                return max(self.go(history, declarer_tricks, gone, tricks_done, seat, int(x), reach, effort * q) for x, q in zip(options[kept], share))
            return max(self.go(history, declarer_tricks, gone, tricks_done, seat, int(x), reach, effort) for x in options)
        if legal.sum(axis=1).max() == 1 and len({int(row.argmax()) for row in legal}) == 1:      # forced, and the same card everywhere
            return self.go(history, declarer_tricks, gone, tricks_done, seat, int(legal[0].argmax()), reach, effort)
        if cfg.reply == 'dd':               # the seat sees every hand, as in PIMC; only the decider's own later cards are made honest
            worlds = [tuple(tuple(int(x) for x in np.flatnonzero(self.member[i, s] & ~gone)) for s in range(4)) for i in live]
            solved = self.dds.solve_batch(worlds, c.trump, trick[0][0] if trick else seat, tuple(trick), fixed_seats=self.visible)
            self.spend(len(live))
            children = {}
            for layout, (values, _) in zip(live, solved):
                best = max(values.values())
                x = min(k for k, v in values.items() if v == best)
                if cfg.plain:
                    x = self.plain(int(x), self.member[layout, seat] & ~gone, trick, seat, gone)
                children.setdefault(int(x), np.zeros(len(reach)))[layout] = reach[layout]
            return self.children(history, declarer_tricks, gone, tricks_done, seat, children, reach, effort)
        if cfg.reply == 'search':           # the seat decides as a searching player would, from its own view alone
            dummy_hand = np.flatnonzero(self.member[0, c.dummy] & ~gone)
            children = {}
            for row, layout in enumerate(live):
                options = np.flatnonzero(legal[row])
                if len(options) == 1:
                    share = {int(options[0]): 1.}
                else:
                    view = seat_view(self.o, history, dummy_hand, chooser, seat, np.flatnonzero(self.member[layout, chooser] & ~gone), declarer_tricks)
                    share = self.replier(view)
                    self.replies += 1
                    self.spend(cfg.reply_layouts)
                    if cfg.plain:
                        cards, mass = self.same_job(np.array(list(share)), np.array(list(share.values())), self.member[layout, seat] & ~gone, trick, seat, gone)
                    else:
                        cards = np.array(sorted(share, key=lambda x: (-share[x], x)))
                        mass = np.array([share[int(x)] for x in cards])
                    kept, part = self.keep(mass, cfg.breadth, 1., effort)
                    share = {int(x): float(q) for x, q in zip(cards[kept], part)}
                for x, q in share.items():
                    children.setdefault(int(x), np.zeros(len(reach)))[layout] = reach[layout] * q
            return self.children(history, declarer_tricks, gone, tricks_done, seat, children, reach, effort)
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
            options, mass = self.same_job(options, p[row, options], held[row], trick, seat, gone)
            kept, share = self.keep(mass, effort=effort)
            for x, q in zip(options[kept], share):
                children.setdefault(int(x), np.zeros(len(reach)))[layout] = reach[layout] * q
        return self.children(history, declarer_tricks, gone, tricks_done, seat, children, reach, effort)

    def children(self, history, declarer_tricks, gone, tricks_done, seat, children, reach, effort):
        """Sum of the children's values; each child's share of the search is the node's times the probability that goes to it."""
        total = float(reach.sum())
        return sum(self.go(history, declarer_tricks, gone, tricks_done, seat, x, r, effort * float(r.sum()) / total) for x, r in children.items())

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

    def plain(self, x, held, trick, seat, gone):
        """The card standing for x among the seat's cards that do the same job now. Touching cards (no card of this
        trick and no unplayed card of another hand between them) are one choice, its lowest. A low card that does not
        take the trick so far stands for the hand's lowest card of the suit; one that takes it, for the cheapest low
        card that also does."""
        suit = SUIT[x // 13]
        mine = np.flatnonzero(held & suit)
        out = ~held & ~gone & suit                                       # unplayed cards of the suit in other hands,
        for _, c in trick:                                               # and the cards of this trick, which still count in it
            out[c] = suit[c]
        i = int(np.searchsorted(mine, x))
        while i > 0 and not out[mine[i - 1] + 1:mine[i]].any():
            i -= 1
        x = int(mine[i])
        if x % 13 >= LOW:
            return x
        lows = mine[mine % 13 < LOW]
        if trick:
            trump = self.o.contract.trump
            takes = lambda c: winner(tuple(trick) + ((seat, int(c)),), trump) == seat
            if takes(x):
                return int(next(c for c in lows if takes(c)))
        return int(lows[0])

    def same_job(self, cards, mass, held, trick, seat, gone):
        """(cards, mass) with cards that do the same job merged into the one that stands for them; unchanged without `plain`."""
        if not self.config.plain:
            return np.asarray(cards), np.asarray(mass, float)
        total = {}
        for x, m in zip(cards, mass):
            y = self.plain(int(x), held, trick, seat, gone)
            total[y] = total.get(y, 0.) + float(m)
        return np.array(list(total)), np.array(list(total.values()))

    def spend(self, solves):
        """Count layouts solved (a searched reply counts the layouts its stand-in searcher solves)."""
        self.solves += solves
        if self.max_solves and self.solves > self.max_solves:
            raise OverBudget(f'{self.solves} solves')

    def keep(self, p, breadth=None, mass=None, effort=None):
        """(indices of the cards kept, their renormalised probabilities): most probable first, at most
        `breadth`, stopping once they add to `mass`. Under the stake rule (`effort` given, the node's share of the
        search) a card after the first is kept only while what the cards before it leave uncovered is still worth it."""
        breadth, mass = breadth or self.config.breadth, mass or self.config.mass
        order = np.argsort(-p, kind='stable')[:breadth]
        total = np.cumsum(p[order]) / max(p.sum(), 1e-300)
        order = order[:int(np.searchsorted(total, mass - 1e-12)) + 1]
        if effort is not None and self.config.path > 0 and len(order) > 1:
            covered = np.concatenate([[0.], np.cumsum(p[order])[:-1]]) / max(p.sum(), 1e-300)
            order = order[:max(1, int(((1. - covered) * effort * self.stake >= self.config.path).sum()))]
        return order, p[order] / max(p[order].sum(), 1e-300)

    def leaf_tricks(self, history, trick, declarer_tricks, gone, live):
        """Declarer's final tricks in each of the `live` layouts with double-dummy play from here."""
        c = self.o.contract
        if len(history) == 52:
            return [declarer_tricks] * len(live)
        worlds = [tuple(tuple(int(x) for x in np.flatnonzero(self.member[i, s] & ~gone)) for s in range(4)) for i in live]
        leader = trick[0][0] if trick else winner(history[-4:], c.trump)
        mover = (leader + len(trick)) % 4
        solved = self.dds.solve_batch(worlds, c.trump, leader, tuple(trick), fixed_seats=self.visible)
        self.spend(len(live))
        remaining = 13 - len(history) // 4
        out = []
        for values, _ in solved:
            best = max(values.values())
            out.append(declarer_tricks + (best if mover % 2 == c.declarer % 2 else remaining - best))
        return out

    def leaf(self, history, trick, declarer_tricks, gone, reach):
        live = np.flatnonzero(reach > 1e-9 * reach.sum())
        self.lines += 1
        total = 0.
        for i, tricks in zip(live, self.leaf_tricks(history, trick, declarer_tricks, gone, live)):
            total += reach[i] * (tricks if self.declaring else -tricks)
        return total
