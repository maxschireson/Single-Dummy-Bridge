"""Honest playouts: every seat plays from its own view, to trick 13, in many layouts at once.

PIMC values a card by solving each layout double dummy, so every later card of all four hands is
chosen with all four hands in view. The Gen 7 tree replaces the first two or three tricks of that
with play from each seat's own view and then solves double dummy again. Here nothing is solved
after the card: the hand is played out, and the value of a card in a layout is the tricks that
play really took. What that play is depends on the `Seat player`:

  NetPlayer      the policy net's card from that seat's view (most probable, or drawn)
  Believer       the seat's most likely layout of the unseen cards (the net's owner head, from its view), and the
                 solver's card for that layout: a plan for one layout, revised as the play contradicts it

A playout is a row. Rows are advanced together, one card each per step, so a batch of rows is one
net evaluation per ply. Rows share the public facts (contract, auction, dummy as first shown) and
the history up to the root; they differ in the hidden hands and in what has been played since.

The arrays the net reads are built here for all rows at once (`inputs`), and must equal
gen7_net.encode on the Observation the game would give that seat; tests/test_plan_rollout.py
checks that on recorded positions.
"""
import numpy as np

from .core import normalize_bid, vulnerable
from .gen7_net import CALL_ID, CALLS, INPUTS, N_CTX, forward

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
        self.void = np.zeros((n, 4, 4), bool)                               # [row, seat, suit] the seat has shown out of the suit
        for k, (seat, x) in enumerate(o.history):
            led = o.history[k - k % 4][1] // 13
            if x // 13 != led:
                self.void[:, seat, led] = True

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
        for k in ('holder', 'by', 'order', 'trick', 'leader', 'won', 'void'):
            setattr(r, k, getattr(self, k).copy())
        return r

    def take(self, index):
        """The rows `index` (repeats allowed) as a new batch."""
        r = object.__new__(Rows)
        r.__dict__.update(self.__dict__)
        for k in ('holder', 'by', 'order', 'trick', 'leader', 'won', 'void'):
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
        if self.on_table:
            led = SUIT_OF[self.trick[:, 0]]
            out = SUIT_OF[cards] != led
            self.void[rows[out], actor[out], led[out]] = True
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


class Believer:
    """Every seat works out what is going on, then plays the double-dummy card for it.

    At each choice the seat takes one layout of the cards it cannot see and the solver plays that layout; the net's
    policy breaks ties among the solver's best cards. The layout comes from the net's owner head, read from that
    seat's own view (its hand, dummy, the auction, the play so far):

      belief='map'    the most likely layout: the hidden hand to the seat's left gets the cards most likely to be
                      there, as many as it holds; show-outs are respected exactly
      belief='draw'   a layout drawn card by card from the owner probabilities raised to `power`

    So a seat's line is a plan for one layout, revised as the play contradicts it. Guesses are resolved the way the
    seat's own beliefs lean, not the way the layout really is, and that is the difference from double dummy.
    `layouts` above 1 draws that many (the first by `belief`, the rest drawn) and plays the card with the best total.
    With `top` above 0 the solver only chooses among the net's likeliest cards, and is not asked when there is one.
    """

    def __init__(self, net, dds, belief='map', power=1., layouts=1, seed=0, top=0, floor=.05):
        if belief not in ('map', 'draw'):
            raise ValueError('Unknown belief')
        self.net, self.dds, self.belief, self.power, self.layouts = net, dds, belief, power, layouts
        self.top, self.floor = top, floor       # top above 0: the solver chooses only among the net's `top` likeliest cards
        self.rng = np.random.default_rng(seed)  # (those with at least `floor` of the probability); one such card is played unsolved
        self.net_rows = self.solves = 0

    def believed(self, lean, held, cap, void_a, void_b, draw):
        """Cards of the first hidden hand. `lean[c]` is the log-odds that a card is there, `held` the unseen cards,
        `cap` how many of them that hand holds."""
        cards = np.flatnonzero(held)
        score = lean[cards].astype(np.float64)
        if draw:
            score = self.power * score + self.rng.gumbel(size=len(cards)) - self.rng.gumbel(size=len(cards))
        suit = SUIT_OF[cards]
        score = np.where(void_a[suit], -np.inf, np.where(void_b[suit], np.inf, score))
        return cards[np.argsort(-score, kind='stable')[:cap]]

    def cards(self, rows, public):
        legal = rows.legal()
        out = legal.argmax(axis=1)
        free = np.flatnonzero(legal.sum(axis=1) > 1)
        if not len(free):
            return out
        batch = inputs(rows, public)
        heads = forward(self.net.params, {k: batch[k][free] for k in INPUTS})
        self.net_rows += len(free)
        logp, owner = heads['policy'], heads['owner']
        controller = rows.controller()
        for j, i in enumerate(free):
            out[i] = self.row_card(rows, int(i), int(controller[i]), logp[j], owner[j])
        return out

    def row_card(self, rows, i, k, logp, owner):
        """The card for row i, whose chooser is seat k: the solver's best over the believed layout(s), the net's
        log-probabilities `logp` breaking ties. `owner` is the owner head's output for the row."""
        a, b = [s for s in range(4) if s != k and s != rows.dummy]          # the two seats this seat cannot see
        keep = None
        if self.top:                                                        # the net proposes, the solver disposes
            order = np.argsort(-logp, kind='stable')[:self.top]
            share = np.exp(logp[order] - logp[order[0]])
            total_p = np.exp(logp - logp[order[0]])[logp > -1e8].sum()
            keep = {int(x) for x, q in zip(order, share) if q / total_p >= self.floor and logp[x] > -1e8} or {int(order[0])}
            if len(keep) == 1:
                return next(iter(keep))
        held = (rows.holder[i] == a) | (rows.holder[i] == b)
        lean = owner[:, (a - k) % 4 - 1] - owner[:, (b - k) % 4 - 1]
        cap = int((rows.holder[i] == a).sum())
        total = {}
        for n in range(self.layouts):
            first = self.believed(lean, held, cap, rows.void[i, a], rows.void[i, b], draw=self.belief == 'draw' or n > 0)
            for x, v in self.solve(rows, i, k, a, b, first, held).items():
                if keep is None or x in keep:
                    total[x] = total.get(x, 0) + v
        best = max(total.values())
        return max((x for x, v in total.items() if v == best), key=lambda x: (logp[x], -x))

    def solve(self, rows, i, k, a, b, first, held):
        """{card: tricks for the side to play} in the layout where seat a holds `first` of the unseen cards `held`."""
        hands = [None] * 4
        hands[k] = [int(x) for x in np.flatnonzero(rows.holder[i] == k)]
        hands[rows.dummy] = [int(x) for x in np.flatnonzero(rows.holder[i] == rows.dummy)]
        mine = set(int(x) for x in first)
        hands[a] = sorted(mine)
        hands[b] = [int(x) for x in np.flatnonzero(held) if int(x) not in mine]
        trick = [((int(rows.leader[i]) + t) % 4, int(rows.trick[i, t])) for t in range(rows.on_table)]
        values, _ = self.dds.solve(hands, rows.trump, int(rows.leader[i]), trick)
        self.solves += 1
        return values


HONOUR = 8                      # rank index from which a card is named on its own in a plan: ten and up
IS_LOW = RANK_OF < HONOUR
BIT = np.uint64(1) << np.arange(52, dtype=np.uint64)


class Planner(Believer):
    """Playouts in which the decider's side follows a plan and every other seat is a Believer.

    A plan is a layout family to play for. The caller says which family each of the decider's layouts belongs to
    (`family`, for instance the joint values of the decision's key variables: plan_families). While any layout of
    the family still fits the play, the decider's seat (and dummy, when the decider declares) plays the solver's
    card for the likeliest of them that fits, by the weights the search gave the layouts (with `own_layouts` above
    1, the card with the best weighted total over that many of them: a small search inside the plan). When none
    fits, the plan is refuted, and the seat does the same over the layouts of any family that fit.

    "Fits" is judged as a player would judge it, by named cards and counts and not by which low cards turned up:
    no card ten or higher has appeared in the wrong hand, no hand has played more low cards of a suit than the
    layout gives it, and no hand has shown out while the layout still gives it cards of the suit. The layout the
    solver is given has the named cards where the fitting layout has them and the unplayed low cards dealt in turn
    from the bottom, as many to each hand as that layout says.

    So every plan is one consistent strategy: it never uses anything the decider could not know at that point,
    and two rows that look the same to the decider are played alike. Plan -1 is "the likeliest layout that fits"
    from the start: the default line.

    Rows are (first card, plan, true layout); `plan[n]` is set by plan_values.
    """

    def __init__(self, net, dds, o, worlds, weights, family=None, belief='map', seed=0, own_layouts=1):
        super().__init__(net, dds, belief, seed=seed)
        self.own_layouts = own_layouts
        self.me = o.controller
        self.a, self.b = [s for s in range(4) if s != self.me and s != o.contract.dummy]
        self.weights = np.asarray(weights, float)
        n = len(worlds)
        self.family = np.arange(n) if family is None else np.asarray(family, np.int64)
        self.hon = np.zeros((2, n), np.uint64)              # [hidden seat, layout] its named cards at the root, as bits
        self.hon_count = np.zeros((2, n, 4), np.int64)      # ... how many of them in each suit
        self.low = np.zeros((2, n, 4), np.int64)            # ... and how many low cards in each suit
        for t, w in enumerate(worlds):
            for h, seat in enumerate((self.a, self.b)):
                for c in w[seat]:
                    if IS_LOW[c]:
                        self.low[h, t, c // 13] += 1
                    else:
                        self.hon[h, t] |= BIT[c]
                        self.hon_count[h, t, c // 13] += 1
        self.start = len(o.history)
        self.order = np.argsort(-self.weights, kind='stable')
        self.plan = None
        self.refuted = self.own_choices = 0

    def shown(self, rows, i):
        """What the two hidden seats have played in row i since the root: (named cards as bits, their count by suit,
        low cards by suit), each [hidden seat, ...]."""
        since = rows.order[i] > self.start
        bits, named, low = np.zeros(2, np.uint64), np.zeros((2, 4), np.int64), np.zeros((2, 4), np.int64)
        for h, seat in enumerate((self.a, self.b)):
            cards = np.flatnonzero((rows.by[i] == seat) & since)
            for c in cards:
                if IS_LOW[c]:
                    low[h, c // 13] += 1
                else:
                    bits[h] |= BIT[c]
                    named[h, c // 13] += 1
        return bits, named, low

    def fits(self, rows, i, shown):
        """[layouts] which of the decider's layouts' families still fit everything row i's play has shown."""
        bits, named, low = shown
        ok = np.ones(len(self.weights), bool)
        for h, seat in enumerate((self.a, self.b)):
            ok &= (bits[h] & ~self.hon[h]) == 0
            ok &= (self.low[h] >= low[h]).all(axis=1)
            left = self.hon_count[h] - named[h] + self.low[h] - low[h]         # [layout, suit] cards of the suit the family still gives the seat
            for s in range(4):
                if rows.void[i, seat, s]:
                    ok &= left[:, s] == 0
        return ok

    def family_hand(self, rows, i, z, shown):
        """The cards the first hidden seat holds now if the layout is of layout z's family: its named cards not yet
        played, and its share of each suit's unplayed low cards, dealt in turn from the bottom."""
        bits, named, low = shown
        out = [int(c) for c in np.flatnonzero((BIT & (self.hon[0, z] & ~bits[0])) != 0)]
        unseen = (rows.holder[i] == self.a) | (rows.holder[i] == self.b)
        for s in range(4):
            need = [int(self.low[0, z, s] - low[0, s]), int(self.low[1, z, s] - low[1, s])]
            turn = 0
            for c in range(13 * s, 13 * s + HONOUR):
                if unseen[c]:
                    if not need[turn]:
                        turn = 1 - turn
                    if turn == 0:
                        out.append(c)
                    need[turn] -= 1
                    turn = 1 - turn
        return np.array(sorted(out), np.int64)

    def row_card(self, rows, i, k, logp, owner):
        if k != self.me:
            return super().row_card(rows, i, k, logp, owner)
        shown = self.shown(rows, i)
        ok = self.fits(rows, i, shown)
        f = int(self.plan[i])
        self.own_choices += 1
        alive = self.order[ok[self.order]]                  # layouts that fit, likeliest first
        if not len(alive):
            raise RuntimeError('No layout fits the play: the true layout must be among the layouts')
        mine = alive[self.family[alive] == f] if f >= 0 else alive
        if not len(mine):
            self.refuted += 1
            mine = alive
        held = (rows.holder[i] == self.a) | (rows.holder[i] == self.b)
        total, solved = {}, {}
        for z in mine[:self.own_layouts]:                   # the likeliest fitting layouts of the plan, weighted as the search weighted them
            hand = self.family_hand(rows, i, int(z), shown)
            key = hand.tobytes()
            if key not in solved:                           # two layouts of one hand type are one solve
                solved[key] = self.solve(rows, i, k, self.a, self.b, hand, held)
            for x, v in solved[key].items():
                total[x] = total.get(x, 0.) + float(self.weights[z]) * v
        best = max(total.values())
        return max((x for x, v in total.items() if best - v <= 1e-9 * max(1., abs(best))), key=lambda x: (logp[x], -x))


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


def plan_values(o, worlds, weights, cards, plans, net, dds, family=None, public=None, belief='map', seed=0, own_layouts=1):
    """[card, plan, layout] the decider's side's final tricks (negated for the defence) when the decider plays the
    card, its side then follows the plan, and every other seat is a Believer. `plans` are family ids (`family[t]`
    is layout t's; by default every layout is its own family), -1 the default line. Also returns the Planner (for
    its counters)."""
    public = public or Public(net, o)
    who = Planner(net, dds, o, worlds, weights, family, belief, seed, own_layouts)
    n_c, n_z, n_w = len(cards), len(plans), len(worlds)
    base = Rows(o, worlds)
    rows = base.take(np.tile(np.arange(n_w), n_c * n_z))
    who.plan = np.tile(np.repeat(np.asarray(plans, np.int64), n_w), n_c)
    rows.play(np.repeat(np.asarray(cards, np.int64), n_z * n_w))
    won = play_out(rows, who, public).reshape(n_c, n_z, n_w).astype(float)
    return (won if o.controller % 2 == o.contract.declarer % 2 else -won), who
