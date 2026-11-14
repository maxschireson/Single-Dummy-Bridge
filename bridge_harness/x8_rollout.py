"""8X rollouts: every candidate card in every layout, played out from each seat's own view, in one batch.

A rollout is one imagined finish of the hand: one candidate card, one layout of the hidden hands, then one card at
a time, each chosen by the rollout net from what the seat to play could see (plan_rollout.Rows holds the state and
`inputs` builds the net's view). Nothing is solved on the way unless a horizon says so. The value of a card is the
weighted mean over layouts of what its rollouts took.

What this module adds to plan_rollout.card_values:

  one batch       the rows are (card, layout) pairs, advanced together: one net evaluation per ply for all of them
  other nets      the side that is not deciding can be played by another net, drawn per layout (`other`): a
                  population inside the rollouts, so that a card is not valued only against the bot's own habits
  claims          at the start of a trick with few cards left the claim finder is asked what the declaring side can
                  guarantee from its own view in that row (x8_claims.Finder.boundaries). If that covers the contract
                  the row's result is floored at the contract (`floor`); if it covers every trick left the row ends
                  there with those tricks
  horizon         with `horizon` above zero a rollout stops after that many tricks and is solved double dummy
  forks           at a random later turn of a few rows the play is copied twice: one copy plays the card the net
                  chose, the other a different card, and both are then played out by the net. The pair says what
                  that other card was worth at a position only the rollouts reached (`Fork`): training material
  lines           every card of every row, so that a fork's position can be rebuilt

Rows are never merged. Two rows that reach the same cards by different orders of play are different positions: the
order is part of what each seat has seen, and the net reads it. The one answer shared between rows is the claim
finder's, which is a proof from hard facts (cards played, show-outs, hand sizes) and does not depend on the order.
"""
from dataclasses import dataclass, field
import time

import numpy as np

from .gen7_net import INPUTS
from .plan_rollout import Public, Rows, inputs, solve_rows

SUIT_OF = np.arange(52) // 13


class Seats:
    """The simulated seats: nets[0] plays the deciding side, and the other side in rows whose `other` is 0; nets[k]
    plays the other side where `other` is k.

    mode   'top'    the net's most probable card
           'draw'   drawn from its probabilities raised to `power`
           'blend'  the card with the best log-probability minus `gap_weight` x the net's gap head

    who    (the deciding side's bot, the other side's bot) as names in a rollout net's vocabulary, for nets that take
           who is playing (gen7_net.PolicyNet.vocab, rollout net v2 on): each row is told the bot of the side to play
           (`bot_own`) and of the other side (`bot_other`). Names the net does not know are read as unknown.
    seen   the name the OTHER side's seats are told for the deciding side's bot; None: who[0]. ('' = they are told
           nothing about whom they play against.)
    cut    'draw': a card whose probability (after `power`) is under `cut` x the likeliest card's is never drawn: the
           draw stays among the plausible cards. 0 = every legal card can be drawn.
    other  how the seats of the side that is NOT deciding take their cards, where that is to differ from the deciding
           side's: {'mode', 'power', 'cut'}. None: all four seats alike. (What a bot knows of its own partnership's play
           it does not know of its opponents': its own side can play its likeliest card while the others' cards stay drawn.)
    """

    def __init__(self, nets, mode='top', power=1., gap_weight=10., seed=0, who=('', ''), seen=None, cut=0., other=None):
        if mode not in ('top', 'draw', 'blend') or (other is not None and other.get('mode', mode) not in ('top', 'draw', 'blend')):
            raise ValueError(f'Unknown seat mode {mode!r}')
        self.nets, self.mode, self.power, self.gap_weight = list(nets), mode, power, gap_weight
        self.who = tuple(who)
        self.seen, self.cut = seen, cut
        self.other = None if other is None else dict(mode=other.get('mode', mode), power=other.get('power', power), cut=other.get('cut', cut))
        self.rng = np.random.default_rng(seed)
        self.net_rows = 0
        self.side, self.publics = None, None

    def start(self, o):
        self.side = o.controller % 2
        self.publics = [Public(net, o) for net in self.nets]
        return self

    def cards(self, rows, other=None):
        """(card per row, the rows with a choice, [those rows, 52] the net's log-probabilities)."""
        legal = rows.legal()
        out = legal.argmax(axis=1)
        free = np.flatnonzero(legal.sum(axis=1) > 1)
        if not len(free):
            return out, free, np.zeros((0, 52), np.float32)
        batch = inputs(rows, self.publics[0])
        controller = rows.controller()[free]
        use = np.zeros(len(free), np.int64)
        if other is not None and len(self.nets) > 1:
            use = np.where(controller % 2 == self.side, 0, np.asarray(other)[free])
        logp = np.empty((len(free), 52), np.float32)
        score = logp
        blend = self.mode == 'blend' or (self.other is not None and self.other['mode'] == 'blend')
        if blend:
            score = np.empty((len(free), 52), np.float32)
        for k in np.unique(use):
            at = np.flatnonzero(use == k)
            b = {key: batch[key][free[at]] for key in INPUTS}
            if k:
                b['shown'] = self.publics[k].shown[controller[at]]
            net = self.nets[k]
            if getattr(net, 'vocab', None):              # a net that takes who is playing: the side to play's bot, then the other's
                mine = controller[at] % 2 == self.side
                me, them = net.bot_id(self.who[0]), net.bot_id(self.who[1])
                seen = me if self.seen is None else net.bot_id(self.seen)
                b['bot_own'] = np.where(mine, me, them).astype(np.int32)
                b['bot_other'] = np.where(mine, them, seen).astype(np.int32)
            if blend:
                logp[at], gap = self.nets[k].policy_and_gap_arrays(b)
                score[at] = logp[at] - self.gap_weight * gap
            else:
                logp[at] = self.nets[k].log_policy_arrays(b)
            self.net_rows += len(at)
        if self.other is None and self.cut <= 0:                # all four seats alike, every legal card drawable: as it always was
            if self.mode == 'draw':
                p = np.exp(self.power * logp.astype(np.float64)) * legal[free]
                cum = np.cumsum(p, axis=1)
                ticket = self.rng.random(len(free)) * cum[:, -1]
                out[free] = (cum < ticket[:, None]).sum(axis=1).clip(max=51)
            else:
                out[free] = np.where(legal[free], score, -np.inf).argmax(axis=1)
            return out, free, logp
        mine = controller % 2 == self.side
        groups = [(np.arange(len(free)), self.mode, self.power, self.cut)] if self.other is None else \
            [(np.flatnonzero(mine), self.mode, self.power, self.cut),
             (np.flatnonzero(~mine), self.other['mode'], self.other['power'], self.other['cut'])]
        for at, mode, power, cut in groups:
            if not len(at):
                continue
            allowed = legal[free[at]]
            if mode == 'draw':
                p = np.exp(power * logp[at].astype(np.float64)) * allowed
                if cut > 0:
                    p = np.where(p >= cut * p.max(axis=1, keepdims=True), p, 0.)
                cum = np.cumsum(p, axis=1)
                ticket = self.rng.random(len(at)) * cum[:, -1]
                out[free[at]] = (cum < ticket[:, None]).sum(axis=1).clip(max=51)
            else:
                out[free[at]] = np.where(allowed, score[at] if mode == 'blend' else logp[at], -np.inf).argmax(axis=1)
        return out, free, logp


@dataclass
class Fork:
    """One inside-rollout pair. The position: the root, layout `layout`, the root card `first`, then `prefix`."""
    layout: int             # index into the layouts given to `evaluate`
    first: int              # the root card of the rollout
    prefix: tuple           # cards played after it, up to the turn of the fork
    seat: int               # the seat to play at the fork
    main: int               # the card the simulated seat chose there
    other: int              # the card forced in its place
    p_main: float           # the net's probability of each at that turn
    p_other: float
    main_tricks: int        # declarer's final tricks when the rollout goes on from each
    other_tricks: int


@dataclass
class Played:
    tricks: np.ndarray                  # [layout, card] declarer's final tricks as the rollout took them
    floor: np.ndarray                   # [layout, card] the claim finder found the contract guaranteed inside the rollout
    ended: np.ndarray                   # [layout, card] the step at which a claim of every trick left ended the row, or -1
    lines: np.ndarray                   # [card * layouts + layout, step] the cards after the root card (-1 once ended)
    forks: list = field(default_factory=list)
    net_rows: int = 0
    asked: int = 0                      # boundary positions put to the claim finder
    seconds: float = 0.


def runs_with(holder, dead, actor, x):
    """The cards of `actor`'s hand that do the same job as x: same suit, and every card between is in that hand or
    out of play (`dead`: played to an earlier trick)."""
    same = {int(x)}
    for step in (1, -1):
        y = int(x) + step
        while 0 <= y < 52 and y // 13 == x // 13 and (holder[y] == actor or dead[y]):
            if holder[y] == actor:
                same.add(y)
            y += step
    return same


def _finish(rows, seats, other, stop, dds):
    while rows.played < stop and rows.n:
        chosen, _, _ = seats.cards(rows, other)
        rows.play(chosen)
    return rows.won.copy() if rows.done else solve_rows(rows, dds)


def evaluate(o, worlds, cards, seats, *, other=None, horizon=0, dds=None, finder=None, target=None, ask=None, leaf_cards=0,
             leaf_allowance=.5, forks=0, fork_power=.5, rng=None):
    """Roll out each of `cards` in each of `worlds` (worlds[i][seat] = the cards a seat holds at the decision `o`).

    seats        a started Seats
    other        [layout] which of the seats' nets plays the side that is not deciding (None = its first)
    horizon      0 = to the end; above 0 = that many tricks (counting the one in progress), then double dummy (`dds`)
    finder, target, ask, leaf_cards
                 the claim finder is asked at the start of each trick with `leaf_cards` or fewer cards a hand, in rows
                 whose contract (`target` tricks) is still open and where `ask[layout, card]` is true (None = all)
    forks        how many inside-rollout pairs to record
    """
    started = time.perf_counter()
    cards = np.asarray(cards, np.int64)
    n_w, n_c = len(worlds), len(cards)
    rng = rng or np.random.default_rng(0)
    rows = Rows(o, worlds).take(np.tile(np.arange(n_w), n_c))
    rows.play(np.repeat(cards, n_w))
    n = rows.n
    ident = np.arange(n)                                    # the original index of each row still in play
    steps = 52 - rows.played
    stop = 52 if not horizon else min(52, (rows.played - 1) // 4 * 4 + 4 * horizon)
    final = np.full(n, -1, np.int16)
    floor = np.zeros(n, bool)
    ended = np.full(n, -1, np.int16)
    lines = np.full((n, max(steps, 1)), -1, np.int8)
    other_all = None if other is None else np.tile(np.asarray(other, np.int64), n_c)
    asking = np.ones(n, bool) if ask is None else np.asarray(ask, bool).T.reshape(-1)
    net_rows, asked = seats.net_rows, 0
    schedule, copies, found = {}, [], []
    span = min(steps, stop - rows.played) - 4               # a fork is not taken in the last trick: nothing is chosen there
    if forks and span > 0:
        for row in rng.choice(n, size=min(forks, n), replace=False):
            schedule.setdefault(int(rng.integers(span)), []).append(int(row))
    step = 0
    while rows.played < stop and rows.n:
        left = 13 - rows.played // 4
        if finder is not None and rows.on_table == 0 and 0 < left <= leaf_cards:
            need = target - rows.won.astype(np.int64)
            index = np.flatnonzero(asking[ident] & ~floor[ident] & (need > 0) & (need <= left))
            if len(index):
                sure, _ = finder.boundaries(rows, index, leaf_allowance)
                asked += len(index)
                known = sure >= 0
                floor[ident[index[known & (sure >= need[index])]]] = True
                whole = index[known & (sure == left)]
                if len(whole):                              # every trick left is the declaring side's: the row ends here
                    final[ident[whole]] = rows.won[whole] + left
                    ended[ident[whole]] = step
                    keep = np.ones(rows.n, bool)
                    keep[whole] = False
                    rows = rows.take(np.flatnonzero(keep))
                    ident = ident[keep]
                    if not rows.n:
                        break
        chosen, free, logp = seats.cards(rows, None if other_all is None else other_all[ident])
        if step in schedule:
            at_free = {int(r): k for k, r in enumerate(free)}
            dead = (rows.by >= 0) & (rows.order <= rows.played - rows.on_table)
            actor = rows.actor()
            legal = rows.legal()
            take, first = [], []
            for row in schedule.pop(step):
                local = int(np.searchsorted(ident, row))
                if local >= rows.n or ident[local] != row:
                    continue                                # the row has ended
                options = []
                if local in at_free:
                    same = runs_with(rows.holder[local], dead[local], int(actor[local]), int(chosen[local]))
                    options = [int(x) for x in np.flatnonzero(legal[local]) if int(x) not in same]
                if not options:                             # no real choice at this turn: try the next one
                    if step + 1 < span:
                        schedule.setdefault(step + 1, []).append(row)
                    continue
                lp = logp[at_free[local]].astype(np.float64)
                p = np.exp(fork_power * (lp[options] - lp[options].max()))
                x = options[int(rng.choice(len(options), p=p / p.sum()))]
                take += [local, local]
                first += [int(chosen[local]), x]
                found.append(dict(row=row, step=step, seat=int(actor[local]), main=int(chosen[local]), other=x,
                                  p_main=float(np.exp(lp[int(chosen[local])])), p_other=float(np.exp(lp[x]))))
            if take:
                copy = rows.take(np.array(take))
                copy.play(np.array(first))
                copies.append((copy, None if other_all is None else other_all[ident[np.array(take)]], len(take) // 2))
        lines[ident, step] = chosen
        rows.play(chosen)
        step += 1
    if rows.n:
        final[ident] = rows.won if rows.done else solve_rows(rows, dds)
    pairs, k = [], 0
    for copy, copy_other, count in copies:                  # both copies of each fork go on as the rollouts do, without claims
        won = _finish(copy, seats, copy_other, stop, dds)
        for j in range(count):
            f = found[k]
            k += 1
            pairs.append(Fork(layout=f['row'] % n_w, first=int(cards[f['row'] // n_w]), prefix=tuple(int(x) for x in lines[f['row'], :f['step']]),
                              seat=f['seat'], main=f['main'], other=f['other'], p_main=f['p_main'], p_other=f['p_other'],
                              main_tricks=int(won[2 * j]), other_tricks=int(won[2 * j + 1])))
    shape = lambda a: a.reshape(n_c, n_w).T.copy()
    return Played(tricks=shape(final), floor=shape(floor), ended=shape(ended), lines=lines, forks=pairs,
                  net_rows=seats.net_rows - net_rows, asked=asked, seconds=time.perf_counter() - started)
