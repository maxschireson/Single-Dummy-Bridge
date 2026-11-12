"""Gen 7 policy net: one actor's view as arrays, and NumPy inference.

`encode` reads nothing but the Observation, which is the capability boundary: no board,
no hidden card, no seed. Training from recorded games and play at the table go through
this one function, so a view cannot carry more at training time than it will at play.

The auction reaches the net twice. As the raw calls, and as what the hand-fit scorer says
each seat's calls show (`Shown`): expected length and high cards per suit and points, for
all four seats. A few thousand deals cannot teach a net what calls mean from the calls
alone (measured: the first net played the same with the auction blanked); the scorer
learned it from 230,000 deals, so the net is handed the scorer's reading instead.

The net (see scripts/train_gen7_policy.py) has four heads:
  policy   log-probability of the card the search bot actually plays (its behaviour)
  gap      the search's estimated tricks given up by each legal card, relative to its best
  owner    which hidden seat holds each unseen card
  tricks   final tricks for the actor's side
"""
import numpy as np

from .core import normalize_bid, vulnerable
from .gen6_nets import HON_HCP, hand_types

CALLS = ['PASS', 'X', 'XX'] + [f'{level}{strain}' for level in range(1, 8) for strain in 'CDHSN']
CALL_ID = {c: i for i, c in enumerate(CALLS)}
N_STATE = 11        # 0 unseen; 1 own hand; 2 dummy; 3-6 played earlier by relative seat 0-3; 7-10 on the table by seat
N_CTX = 23
N_AUCTION = 4 * len(CALLS)
CARD_FEATURES = N_STATE + 5
SEAT_SHOWN = 19     # per seat: length/5, P(5+), P(0-2), high-card points/4 (each by suit), points/10, their sd/5, effective share of the bank
SUIT_SHOWN = 4      # of those, the first SUIT_SHOWN * 4 are per suit (S H D C within each)
SUIT_INPUT = 13 * CARD_FEATURES + 4 * SUIT_SHOWN    # a suit encoder's input: its thirteen cards, and four seats' showing in that suit
N_SHOWN = 4 * SEAT_SHOWN
N_GLOBAL = N_CTX + N_AUCTION + N_SHOWN
BANK = 4096
ROLES = ('declarer', 'dummy', 'lho', 'rho')     # whose card is being chosen, from the controller's side


def role(o):
    c = o.contract
    if o.controller == c.declarer:
        return 1 if o.actor == c.dummy else 0
    return 2 if o.controller == (c.declarer + 1) % 4 else 3


def make_bank(n=BANK, seed=7, strong=.1, long_suit=.1):
    """Hand types (suit lengths, honour bits) of n random hands and each one's log weight: the sample `Shown` uses.

    Mostly plain random hands. A tenth are drawn from hands with 16+ points and a tenth from hands
    with a six-card suit, so those are about 1.8 and 1.3 times as common as dealt (2.3 for both)
    and ordinary hands 0.8 times; the log weights undo that exactly. The tilt is kept this mild on
    purpose: common auctions matter most and should lose almost none of their sample.
    """
    rng = np.random.default_rng(seed)
    pool = 100 * n
    cards = rng.permuted(np.broadcast_to(np.arange(52), (pool, 52)), axis=1)[:, :13]
    member = np.zeros((pool, 52), np.int8)
    np.put_along_axis(member, cards, 1, axis=1)
    length, hon = hand_types(member)
    is_strong = HON_HCP[hon].sum(axis=1) >= 16
    is_long = length.max(axis=1) >= 6
    n_strong, n_long = int(round(n * strong)), int(round(n * long_suit))
    plain = n - n_strong - n_long
    middle = plain + (pool - plain) // 2
    take = np.concatenate([np.arange(plain), plain + np.flatnonzero(is_strong[plain:middle])[:n_strong],
                           middle + np.flatnonzero(is_long[middle:])[:n_long]])
    if len(take) != n:
        raise ValueError('Bank pool too small')
    density = plain / n + n_strong / n * is_strong[take] / is_strong.mean() + n_long / n * is_long[take] / is_long.mean()
    return length[take].astype(np.int8), hon[take].astype(np.int8), -np.log(density).astype(np.float32)


class Shown:
    """What each seat's calls show, according to the hand-fit scorer.

    The scorer gives P(a hand would have made this seat's calls). Weighting a fixed bank of
    random hands by it is the posterior over that seat's hand given the auction alone (not
    given anyone's cards). The bank travels with the net's weights so play uses the hands
    training used.
    """

    def __init__(self, scorer, length, hon, log_weight):
        self.scorer = scorer
        self.length, self.hon = np.asarray(length, np.int64), np.asarray(hon, np.int64)
        self.log_weight = np.asarray(log_weight, np.float64)
        points = HON_HCP[self.hon]
        self.points = points.sum(axis=1).astype(np.float64)
        self.features = np.concatenate([self.length / 5., self.length >= 5, self.length <= 2, points / 4.,
                                        self.points[:, None] / 10.], axis=1).astype(np.float64)
        self.cache = {}

    def seats(self, auction, dealer, vulnerability):
        """[4 seats N E S W, SEAT_SHOWN]."""
        key = (tuple(auction), dealer, vulnerability)
        if key not in self.cache:
            if len(self.cache) >= 64:
                self.cache.clear()
            out = np.zeros((4, SEAT_SHOWN), np.float32)
            for seat in range(4):
                score = self.scorer.log_score(self.length, self.hon, float(vulnerable(vulnerability, seat)),
                                              float(vulnerable(vulnerability, (seat + 1) % 4)),
                                              self.scorer.auction_part(auction, dealer, seat))
                score = score + self.log_weight
                w = np.exp(score - score.max())
                w /= w.sum()
                mean = w @ self.features
                spread = np.sqrt(max(0., float(w @ (self.points - 10. * mean[-1]) ** 2)))
                out[seat] = [*mean, spread / 5., 1. / float((w ** 2).sum()) / len(w)]
            self.cache[key] = out
        return self.cache[key]

    def view(self, o):
        """N_SHOWN values in the controller's seat order (self, left, across, right)."""
        rows = self.seats(o.auction, o.dealer, o.vulnerability)
        return np.concatenate([rows[(o.controller + r) % 4] for r in range(4)])


def encode(o, shown=None):
    """The decision as compact arrays: state[52], order[52], legal[52], ctx[N_CTX], auction[N_AUCTION], shown[N_SHOWN].

    `shown` is a Shown; without one that part is zero (a net trained with it must be given it).
    """
    c = o.contract
    rel = lambda seat: (seat - o.controller) % 4
    state = np.zeros(52, np.uint8)
    order = np.zeros(52, np.uint8)
    for x in o.known_hands[o.controller]:
        state[x] = 1
    if c.dummy != o.controller and o.known_hands[c.dummy] is not None:
        for x in o.known_hands[c.dummy]:
            state[x] = 2
    on_table = {x for _, x in o.trick}
    for i, (seat, x) in enumerate(o.history):
        state[x] = (7 if x in on_table else 3) + rel(seat)
        order[x] = i + 1
    legal = np.zeros(52, bool)
    legal[list(o.legal)] = True
    ctx = np.zeros(N_CTX, np.float32)
    ctx[c.trump] = 1                                  # 0-3 the trump suit, 4 notrump
    ctx[5] = c.level / 7
    ctx[6] = c.doubled / 2
    ctx[7 + role(o)] = 1
    ctx[11 + len(o.trick)] = 1
    ctx[15] = o.declarer_tricks / 13
    ctx[16] = (len(o.history) // 4) / 13
    ctx[17] = vulnerable(o.vulnerability, o.controller)
    ctx[18] = vulnerable(o.vulnerability, (o.controller + 1) % 4)
    ctx[19 + rel(o.dealer)] = 1
    auction = np.zeros((4, len(CALLS)), np.uint8)
    for i, call in enumerate(o.auction):
        k = CALL_ID.get(normalize_bid(call))
        if k is not None:
            auction[rel((o.dealer + i) % 4), k] = 1
    return dict(state=state, order=order, legal=legal, ctx=ctx, auction=auction.reshape(-1),
                shown=np.zeros(N_SHOWN, np.float32) if shown is None else shown.view(o))


INPUTS = ('state', 'order', 'legal', 'ctx', 'auction', 'shown')
BANK_KEYS = ('bank_length', 'bank_hon', 'bank_log_weight')


def stack(rows):
    return {k: np.stack([r[k] for r in rows]) for k in INPUTS}


def features(batch, xp=np):
    """Per-card features [n, 4 suits, 13 ranks, CARD_FEATURES] and the global vector [n, N_GLOBAL].

    Written against the array module, so training (jax.numpy) and play (numpy) share it.
    """
    state = xp.asarray(batch['state']).astype(xp.int32)
    order = xp.asarray(batch['order']).astype(xp.float32)
    legal = xp.asarray(batch['legal']).astype(xp.float32)
    ctx = xp.asarray(batch['ctx']).astype(xp.float32)
    n = state.shape[0]
    one_hot = (state[:, :, None] == xp.arange(N_STATE)[None, None, :]).astype(xp.float32)
    led = ((order > 0) & (xp.mod(order - 1, 4) == 0)).astype(xp.float32)
    trump = xp.repeat(ctx[:, :4], 13, axis=1)                                   # [n, 52]
    on_table = (state >= 7).astype(xp.float32)
    lead_now = on_table * led                                                   # the card led to this trick
    suit_led = xp.repeat(lead_now.reshape(n, 4, 13).sum(axis=2), 13, axis=1)    # [n, 52]
    cards = xp.concatenate([one_hot, (order / 52.)[:, :, None], led[:, :, None], legal[:, :, None],
                            trump[:, :, None], suit_led[:, :, None]], axis=2)
    globals_ = xp.concatenate([ctx, xp.asarray(batch['auction']).astype(xp.float32),
                               xp.asarray(batch['shown']).astype(xp.float32)], axis=1)
    return cards.reshape(n, 4, 13, CARD_FEATURES), globals_


def relu(x, xp=np):
    return xp.maximum(x, 0)


def forward(params, batch, xp=np, kind=None):
    """All heads for a batch. `params` is a flat dict of arrays (see scripts/train_gen7_policy.py)."""
    cards, g = features(batch, xp)
    n = cards.shape[0]
    kind = int(np.asarray(params['kind'])) if kind is None else kind
    if kind == 0:                                                               # flat MLP
        h = xp.concatenate([cards.reshape(n, -1), g], axis=1)
        for i in range(3):
            h = relu(h @ params[f'w{i}'] + params[f'b{i}'], xp)
        out = h @ params['w_out'] + params['b_out']
        policy, gap, owner = out[:, :52], out[:, 52:104], out[:, 104:260].reshape(n, 52, 3)
        tricks = out[:, 260]
    else:                                                                       # one encoder and decoder shared by the four suits
        # each suit's encoder also gets what the calls show about that suit, seat by seat
        shown = xp.asarray(batch['shown']).astype(xp.float32).reshape(n, 4, SEAT_SHOWN)[:, :, :SUIT_SHOWN * 4]
        about_suit = xp.transpose(shown.reshape(n, 4, SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * SUIT_SHOWN)
        s = xp.concatenate([cards.reshape(n, 4, 13 * CARD_FEATURES), about_suit], axis=2)
        s = relu(s @ params['ws0'] + params['bs0'], xp)
        s = relu(s @ params['ws1'] + params['bs1'], xp)                         # [n, 4, e]
        h = xp.concatenate([s.reshape(n, -1), g], axis=1)
        h = relu(h @ params['wt0'] + params['bt0'], xp)
        h = relu(h @ params['wt1'] + params['bt1'], xp)                         # [n, t]
        slot = xp.broadcast_to(xp.eye(4, dtype=xp.float32)[None], (n, 4, 4))
        d = xp.concatenate([s, xp.broadcast_to(h[:, None, :], (n, 4, h.shape[1])), slot], axis=2)
        d = relu(d @ params['wd0'] + params['bd0'], xp)
        out = (d @ params['wd1'] + params['bd1']).reshape(n, 4, 13, 5)
        policy, gap, owner = out[..., 0].reshape(n, 52), out[..., 1].reshape(n, 52), out[..., 2:].reshape(n, 52, 3)
        tricks = (h @ params['wk'] + params['bk'])[:, 0]
    legal = xp.asarray(batch['legal'])
    policy = xp.where(legal, policy, -1e9)
    return dict(policy=policy, gap=gap, owner=owner, tricks=tricks)


def log_softmax(x):
    x = x - x.max(axis=1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=1, keepdims=True))


class PolicyNet:
    """NumPy inference from an exported .npz. `scorer` is the FitScorer the net's `shown` inputs were made with."""
    def __init__(self, path, scorer):
        with np.load(path) as z:
            self.params = {k: z[k] for k in z.files}
        self.shown = Shown(scorer, *(self.params.pop(k) for k in BANK_KEYS))

    def encode(self, o):
        return encode(o, self.shown)

    def log_policy_arrays(self, batch, chunk=4096):
        """[n, 52] log-probability of each card from stacked inputs; illegal cards are about -1e9."""
        n = len(batch['state'])
        out = np.empty((n, 52), np.float32)
        for i in range(0, n, chunk):
            out[i:i + chunk] = log_softmax(forward(self.params, {k: batch[k][i:i + chunk] for k in INPUTS})['policy'])
        return out

    def policy_and_gap_arrays(self, batch, chunk=4096):
        """([n, 52] log-probability of each card, [n, 52] predicted tricks given up by each card) from stacked inputs."""
        n = len(batch['state'])
        logp, gap = np.empty((n, 52), np.float32), np.empty((n, 52), np.float32)
        for i in range(0, n, chunk):
            out = forward(self.params, {k: batch[k][i:i + chunk] for k in INPUTS})
            logp[i:i + chunk], gap[i:i + chunk] = log_softmax(out['policy']), out['gap']
        return logp, gap

    def log_policy(self, observations):
        if not observations:
            return np.zeros((0, 52), np.float32)
        return self.log_policy_arrays(stack([self.encode(o) for o in observations]))

    def heads(self, observations):
        out = forward(self.params, stack([self.encode(o) for o in observations]))
        return dict(out, policy=log_softmax(out['policy']))
