"""Honest playouts: every seat plays from its own view, to trick 13, in many layouts at once.

PIMC values a card by solving each layout double dummy, so every later card of all four hands is
chosen with all four hands in view. The Gen 7 tree replaces the first two or three tricks of that
with play from each seat's own view and then solves double dummy again. Here nothing is solved
after the card: the hand is played out, and the value of a card in a layout is the tricks that
play really took. What that play is depends on the `Seat player`:

  NetPlayer      the policy net's card from that seat's view (most probable, or drawn)

A playout is a row. Rows are advanced together, one card each per step, so a batch of rows is one
net evaluation per ply. Rows share the public facts (contract, auction, dummy as first shown) and
the history up to the root; they differ in the hidden hands and in what has been played since.

The arrays the net reads are built here for all rows at once (`inputs`), and must equal
gen7_net.encode on the Observation the game would give that seat; tests/test_plan_rollout.py
checks that on recorded positions.
"""
import numpy as np

from .core import normalize_bid, vulnerable
from .gen7_net import CALL_ID, CALLS, INPUTS, N_CTX

SUIT_OF = np.arange(52) // 13
RANK_OF = np.arange(52) % 13


class Rows:
    """The state of n playouts that share a contract and an auction.

    holder[n, 52]   seat holding the card now, -1 once played
    by[n, 52]       seat that played the card, -1 if unplayed
    order[n, 52]    1 + position of the card in the play, 0 if unplayed
    trick[n, 4]     cards of the trick in progress, in order (first `on_table` are valid)
    leader[n]       seat that led (or leads) the trick in progress
    won[n]          tricks declarer's side has won
    played          cards played so far (the same in every row)
    """

    def __init__(self, o, worlds):
        """Rows at the decision `o`, one per layout. `worlds[i][seat]` are the cards a seat still holds."""
        c = o.contract
        n = len(worlds)
        self.o, self.contract, self.n = o, c, n
        self.declarer, self.dummy, self.trump = c.declarer, c.dummy, c.trump
        self.holder = np.full((n, 52), -1, np.int8)
        for i, w in enumerate(worlds):
            for s in range(4):
                self.holder[i, list(w[s])] = s
        self.by = np.full((n, 52), -1, np.int8)
        self.order = np.zeros((n, 52), np.uint8)
        for k, (seat, x) in enumerate(o.history):
            self.by[:, x] = seat
            self.order[:, x] = k + 1
        if ((self.holder >= 0) & (self.by >= 0)).any() or ((self.holder < 0) & (self.by < 0)).any():
            raise ValueError('A layout does not fit the play so far')
        self.played = len(o.history)
        self.trick = np.full((n, 4), -1, np.int16)
        for k, (_, x) in enumerate(o.trick):
            self.trick[:, k] = x
        self.leader = np.full(n, o.leader, np.int8)
        self.won = np.full(n, o.declarer_tricks, np.int16)

    # ---- who is to play ----------------------------------------------------------------
    @property
    def on_table(self):
        return self.played % 4

    def actor(self):
        return ((self.leader + self.on_table) % 4).astype(np.int8)

    def controller(self):
        a = self.actor()
        return np.where(a == self.dummy, self.declarer, a).astype(np.int8)

    def legal(self):
        """[n, 52] the cards the actor may play."""
        held = self.holder == self.actor()[:, None]
        if self.on_table:
            led = SUIT_OF[self.trick[:, 0]]
            follow = held & (SUIT_OF[None, :] == led[:, None])
            return np.where(follow.any(axis=1)[:, None], follow, held)
        return held

    def copy(self):
        r = object.__new__(Rows)
        r.__dict__.update(self.__dict__)
        for k in ('holder', 'by', 'order', 'trick', 'leader', 'won'):
            setattr(r, k, getattr(self, k).copy())
        return r

    def take(self, index):
        """The rows `index` (repeats allowed) as a new batch."""
        r = object.__new__(Rows)
        r.__dict__.update(self.__dict__)
        for k in ('holder', 'by', 'order', 'trick', 'leader', 'won'):
            setattr(r, k, getattr(self, k)[index].copy())
        r.n = len(r.leader)
        return r

    # ---- playing a card ----------------------------------------------------------------
    def play(self, cards):
        """Every row's actor plays its card (`cards[n]`)."""
        cards = np.asarray(cards, np.int64)
        rows = np.arange(self.n)
        actor = self.actor()
        if not (self.holder[rows, cards] == actor).all():
            raise ValueError('A row was given a card its actor does not hold')
        self.holder[rows, cards] = -1
        self.by[rows, cards] = actor
        self.order[rows, cards] = self.played + 1
        self.trick[:, self.on_table] = cards
        self.played += 1
        if self.played % 4 == 0:
            t = self.trick
            suit, rank = SUIT_OF[t], RANK_OF[t]
            power = np.where(suit == self.trump, 200, np.where(suit == suit[:, :1], 100, 0)) + rank
            self.leader = ((self.leader + power.argmax(axis=1)) % 4).astype(np.int8)
            self.won += self.leader % 2 == self.declarer % 2
            self.trick[:] = -1

    @property
    def done(self):
        return self.played == 52


class Public:
    """The parts of the net's input that depend only on the public facts and on who is choosing."""

    def __init__(self, net, o):
        c = o.contract
        self.net = net
        self.auction = np.zeros((4, 4, len(CALLS)), np.uint8)             # [controller, relative seat, call]
        for controller in range(4):
            for i, call in enumerate(o.auction):
                k = CALL_ID.get(normalize_bid(call))
                if k is not None:
                    self.auction[controller, ((o.dealer + i) - controller) % 4, k] = 1
        self.auction = self.auction.reshape(4, -1)
        seats = net.shown.seats(o.auction, o.dealer, o.vulnerability)       # [4 seats, SEAT_SHOWN]
        self.shown = np.stack([np.concatenate([seats[(controller + r) % 4] for r in range(4)]) for controller in range(4)]).astype(np.float32)
        self.ctx = np.zeros((4, N_CTX), np.float32)                         # the entries that do not change during play
        for controller in range(4):
            x = self.ctx[controller]
            x[c.trump] = 1
            x[5] = c.level / 7
            x[6] = c.doubled / 2
            x[17] = vulnerable(o.vulnerability, controller)
            x[18] = vulnerable(o.vulnerability, (controller + 1) % 4)
            x[19 + (o.dealer - controller) % 4] = 1


def inputs(rows, public):
    """The net's inputs for the choice in hand in every row: gen7_net.encode for each row's controller, batched."""
    n = rows.n
    actor, controller = rows.actor(), rows.controller()
    state = np.zeros((n, 52), np.uint8)
    state[rows.holder == controller[:, None]] = 1
    state[rows.holder == rows.dummy] = 2          # dummy is never the controller, so this never overwrites an own card
    done = rows.by >= 0
    rel = (rows.by - controller[:, None]) % 4
    current = rows.order > rows.played - rows.on_table
    state = np.where(done, np.where(current, 7, 3) + rel, state).astype(np.uint8)
    ctx = public.ctx[controller].copy()
    role = np.where(controller == rows.declarer, (actor == rows.dummy).astype(np.int64),
                    np.where(controller == (rows.declarer + 1) % 4, 2, 3))
    ctx[np.arange(n), 7 + role] = 1
    ctx[:, 11 + rows.on_table] = 1
    ctx[:, 15] = rows.won / 13
    ctx[:, 16] = (rows.played // 4) / 13
    return dict(state=state, order=rows.order, legal=rows.legal(), ctx=ctx, auction=public.auction[controller], shown=public.shown[controller])


class NetPlayer:
    """Every seat's card from the policy net.

    mode       'top'   the most probable card
               'draw'  drawn from the probabilities raised to `power` (and renormalised)
               'blend' the card that maximises log-probability minus `gap_weight` x the gap head
    """

    def __init__(self, net, mode='top', power=1., gap_weight=10., seed=0):
        if mode not in ('top', 'draw', 'blend'):
            raise ValueError('Unknown mode')
        self.net, self.mode, self.power, self.gap_weight = net, mode, power, gap_weight
        self.rng = np.random.default_rng(seed)
        self.net_rows = 0

    def cards(self, rows, public):
        legal = rows.legal()
        count = legal.sum(axis=1)
        out = legal.argmax(axis=1)
        free = np.flatnonzero(count > 1)
        if len(free):
            batch = inputs(rows, public)
            batch = {k: batch[k][free] for k in INPUTS}
            self.net_rows += len(free)
            if self.mode == 'blend':
                logp, gap = self.net.policy_and_gap_arrays(batch)
                score = np.where(legal[free], logp - self.gap_weight * gap, -np.inf)
                out[free] = score.argmax(axis=1)
            else:
                logp = self.net.log_policy_arrays(batch)
                if self.mode == 'top':
                    out[free] = logp.argmax(axis=1)
                else:
                    p = np.exp(self.power * logp.astype(np.float64)) * legal[free]
                    cum = np.cumsum(p, axis=1)
                    ticket = self.rng.random(len(free)) * cum[:, -1]
                    out[free] = (cum < ticket[:, None]).sum(axis=1).clip(max=51)
        return out


def solve_rows(rows, dds):
    """Declarer's final tricks per row with double-dummy play from here. Rows must stand at the start of a trick."""
    if rows.on_table:
        raise ValueError('Rows are solved at the start of a trick')
    if rows.done:
        return rows.won.copy()
    out = rows.won.astype(np.int64).copy()
    remaining = 13 - rows.played // 4
    groups = {}                         # the solver's batch call wants one set of unplayed cards and one leader per batch
    for i in range(rows.n):
        groups.setdefault((int(rows.leader[i]), (rows.holder[i] >= 0).tobytes()), []).append(i)
    for (leader, _), index in groups.items():
        worlds = [tuple(tuple(int(x) for x in np.flatnonzero(rows.holder[i] == s)) for s in range(4)) for i in index]
        for i, (values, _) in zip(index, dds.solve_batch(worlds, rows.trump, leader, ())):
            best = max(values.values())
            out[i] += best if leader % 2 == rows.declarer % 2 else remaining - best
    return out


def play_out(rows, player, public, tricks=0, dds=None):
    """Play every row to the end, or with `tricks` above zero to the end of that many tricks (counting the one in
    progress) and double dummy from there, as the Gen 7 tree does at its horizon. Returns declarer's final tricks
    per row (the rows are consumed)."""
    stop = 52 if not tricks else min(52, (rows.played - 1) // 4 * 4 + 4 * tricks)       # rows.played already counts the root card
    while rows.played < stop:
        rows.play(player.cards(rows, public))
    return rows.won.copy() if rows.done else solve_rows(rows, dds)


def card_values(o, worlds, cards, player, public=None, repeats=1, tricks=0, dds=None):
    """[layout, card] the decider's side's final tricks (negated for the defence, as PIMC counts) when the decider
    plays each of `cards` in each layout and everyone then plays as `player` says. `repeats` playouts are averaged.
    `tricks` above zero stops the playout at the end of that many tricks and solves double dummy from there."""
    public = public or Public(player.net, o)
    base = Rows(o, worlds)
    declaring = o.controller % 2 == o.contract.declarer % 2
    out = np.zeros((len(worlds), len(cards)))
    for _ in range(repeats):
        for j, x in enumerate(cards):
            rows = base.copy()
            rows.play(np.full(rows.n, x))
            won = play_out(rows, player, public, tricks, dds)
            out[:, j] += won if declaring else -won
    return out / repeats
