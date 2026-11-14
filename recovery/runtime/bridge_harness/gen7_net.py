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

A student of the exact line finder (experiments/sid_loop/SPEC.md, Part B; scripts/train_rollout_net.py with a set
that carries `sid`) has more outputs, present when the weights `wd1s` and `wk14` are:
  guar, cert, single   [n, 52, 3] logits per card and target (one down, the contract, an overtrick). For the declaring
                       side: the card guarantees the target outright / the true layout is in the card's certified
                       set / the card wins the true layout's shape taken alone. For a defender, guar and cert say the
                       same of the declaring side once the card is played (single is not trained there).
  tricks14             [n, 14] logits for the actor's side's final tricks, 0 to 13
A net without those weights behaves as before.
"""
import os

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
SID_HEADS = ('guar', 'cert', 'single')      # the per-card outputs of a line-finder student, in the order of `wd1s`
BANK_KEYS = ('bank_length', 'bank_hon', 'bank_log_weight')
WHO = ('bot_own', 'bot_other')     # optional inputs of rollout nets: the bots' rows in the net's `bot_vocab`


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


def dense(x, w):
    """x [..., k] @ w [k, m] as one 2-D matrix product. numpy's matmul on a 3-D x runs one small product per leading
    index; flattening first gives BLAS one large product (about 3x faster for the suit net, same numbers)."""
    shape = x.shape
    return (x.reshape(-1, shape[-1]) @ w).reshape(shape[:-1] + (w.shape[1],))


def forward(params, batch, xp=np, kind=None):
    """All heads for a batch. `params` is a flat dict of arrays (see scripts/train_gen7_policy.py)."""
    cards, g = features(batch, xp)
    n = cards.shape[0]
    kind = int(np.asarray(params['kind'])) if kind is None else kind
    more = {}
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
        s = relu(dense(s, params['ws0']) + params['bs0'], xp)
        s = relu(dense(s, params['ws1']) + params['bs1'], xp)                         # [n, 4, e]
        h = xp.concatenate([s.reshape(n, -1), g], axis=1)
        h = h @ params['wt0'] + params['bt0']
        if 'emb_own' in params:             # rollout nets: who is playing, as learned vectors (row 0: unknown)
            for key in ('own', 'other'):
                ids = batch.get('bot_' + key)
                h = h + params['emb_' + key][xp.zeros(n, xp.int32) if ids is None else xp.asarray(ids).astype(xp.int32)]
        h = relu(h, xp)
        h = relu(h @ params['wt1'] + params['bt1'], xp)                         # [n, t]
        # the decoder's input is [suit encoding, trunk, one-hot slot]; its first layer is split by those parts so the
        # trunk's share is computed once a row rather than once a suit (same sum as concatenating, fewer products)
        e, t, wd0 = s.shape[2], h.shape[1], params['wd0']
        d = dense(s, wd0[:e]) + (h @ wd0[e:e + t])[:, None, :] + wd0[e + t:e + t + 4][None, :, :]
        d = relu(d + params['bd0'], xp)
        out = (dense(d, params['wd1']) + params['bd1']).reshape(n, 4, 13, 5)
        policy, gap, owner = out[..., 0].reshape(n, 52), out[..., 1].reshape(n, 52), out[..., 2:].reshape(n, 52, 3)
        tricks = (h @ params['wk'] + params['bk'])[:, 0]
        if 'wd1s' in params:                # a student of the line finder: three labels a card, three targets each
            sid = (dense(d, params['wd1s']) + params['bd1s']).reshape(n, 4, 13, len(SID_HEADS), 3)
            more = {k: sid[..., i, :].reshape(n, 52, 3) for i, k in enumerate(SID_HEADS)}
        if 'wk14' in params:
            more['tricks14'] = h @ params['wk14'] + params['bk14']
    legal = xp.asarray(batch['legal'])
    policy = xp.where(legal, policy, -1e9)
    return dict(policy=policy, gap=gap, owner=owner, tricks=tricks, **more)


def log_softmax(x):
    x = x - x.max(axis=1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=1, keepdims=True))


class Bf16Forward:
    """`forward` for a suit-shared net with every matrix product in bf16 through torch's CPU kernels (oneDNN, which use
    the AVX512_BF16 instructions where the CPU has them): weights and activations rounded to bf16, sums kept in fp32
    inside each product, outputs returned as fp32 NumPy. On the Zen 4 boxes about 2x the fp32 NumPy forward on one core
    (rollout net v2: 15,765 -> 33,486 rows/s at 512 rows a call), with the first card unchanged on 99.7% of held-out rows
    and the tricks it gives up unchanged (training/rollout-loop-20261113/bench/bf16.py). Not for nets with the line
    finder's label heads, nor flat nets: `make` returns None for those, and for any net when torch is missing."""
    KEYS = ('ws0', 'bs0', 'ws1', 'bs1', 'wt0', 'bt0', 'wt1', 'bt1', 'wd0', 'bd0', 'wd1', 'bd1', 'wk', 'bk', 'emb_own', 'emb_other')

    @classmethod
    def make(cls, params):
        if int(np.asarray(params['kind'])) == 0 or 'wd1s' in params or 'wk14' in params:
            return None
        try:
            import torch
        except ImportError:
            return None
        return cls(params, torch)

    def __init__(self, params, torch):
        self.torch = torch
        threads = int(os.environ.get('OMP_NUM_THREADS') or 0)
        if threads:
            torch.set_num_threads(threads)
        self.t = {k: torch.from_numpy(np.ascontiguousarray(np.asarray(params[k], np.float32))).to(torch.bfloat16)
                  for k in self.KEYS if k in params}

    def __call__(self, batch):
        torch, T = self.torch, self.t
        cards, g = features(batch)
        n = cards.shape[0]
        shown = np.asarray(batch['shown']).astype(np.float32).reshape(n, 4, SEAT_SHOWN)[:, :, :SUIT_SHOWN * 4]
        about = np.transpose(shown.reshape(n, 4, SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * SUIT_SHOWN)
        x = np.concatenate([cards.reshape(n, 4, 13 * CARD_FEATURES), about], axis=2).reshape(n * 4, -1)
        with torch.inference_mode():
            s = torch.from_numpy(np.ascontiguousarray(x)).to(torch.bfloat16)
            s = torch.relu(s @ T['ws0'] + T['bs0'])
            s = torch.relu(s @ T['ws1'] + T['bs1'])
            e = s.shape[1]
            h = torch.cat([s.reshape(n, 4 * e), torch.from_numpy(np.ascontiguousarray(g)).to(torch.bfloat16)], dim=1) @ T['wt0'] + T['bt0']
            if 'emb_own' in T:
                for key in ('own', 'other'):
                    ids = batch.get('bot_' + key)
                    h = h + T['emb_' + key][torch.zeros(n, dtype=torch.long) if ids is None else torch.from_numpy(np.asarray(ids).astype(np.int64))]
            h = torch.relu(h)
            h = torch.relu(h @ T['wt1'] + T['bt1'])
            t, wd0 = h.shape[1], T['wd0']
            d = (s @ wd0[:e]).reshape(n, 4, -1) + (h @ wd0[e:e + t])[:, None, :] + wd0[e + t:e + t + 4][None, :, :] + T['bd0']
            d = torch.relu(d).reshape(n * 4, -1)
            out = (d @ T['wd1'] + T['bd1']).float().reshape(n, 4, 13, 5).numpy()
            tricks = (h @ T['wk'] + T['bk']).float().numpy()[:, 0]
        policy, gap, owner = out[..., 0].reshape(n, 52), out[..., 1].reshape(n, 52), out[..., 2:].reshape(n, 52, 3)
        return dict(policy=np.where(np.asarray(batch['legal']), policy, -1e9), gap=gap, owner=owner, tricks=tricks)


class PolicyNet:
    """NumPy inference from an exported .npz. `scorer` is the FitScorer the net's `shown` inputs were made with.

    A rollout net (one with `bot_vocab`) also takes who is playing: `bot_id(name)` is a bot's row (0 for a bot it was
    not trained on), and a batch may carry `bot_own` (the deciding side's bot) and `bot_other` (the other side's);
    either missing is read as unknown. `self.who = (own, other)` sets the names used by log_policy and heads."""
    def __init__(self, path, scorer):
        with np.load(path) as z:
            self.params = {k: z[k] for k in z.files}
        self.shown = Shown(scorer, *(self.params.pop(k) for k in BANK_KEYS))
        vocab = self.params.pop('bot_vocab', None)
        self.vocab = {str(x): i for i, x in enumerate(vocab)} if vocab is not None else {}
        self.who = ('', '')
        # BRIDGE_NET_BF16=1: the forward pass in bf16 where it can be (Bf16Forward); otherwise, and by default, fp32 NumPy
        fast = Bf16Forward.make(self.params) if os.environ.get('BRIDGE_NET_BF16') == '1' else None
        self.run = fast if fast is not None else (lambda batch: forward(self.params, batch))
        self.precision = 'bf16' if fast is not None else 'fp32'

    def bot_id(self, name):
        return self.vocab.get(name or '', 0)

    def tag(self, batch, n):
        if not self.vocab:
            return batch
        own, other = self.who
        return dict(batch, bot_own=np.full(n, self.bot_id(own), np.int32), bot_other=np.full(n, self.bot_id(other), np.int32))

    def encode(self, o):
        return encode(o, self.shown)

    def log_policy_arrays(self, batch, chunk=4096):
        """[n, 52] log-probability of each card from stacked inputs; illegal cards are about -1e9."""
        n = len(batch['state'])
        batch = batch if 'bot_own' in batch else self.tag(batch, n)
        out = np.empty((n, 52), np.float32)
        for i in range(0, n, chunk):
            out[i:i + chunk] = log_softmax(self.run({k: batch[k][i:i + chunk] for k in INPUTS + WHO if k in batch})['policy'])
        return out

    def policy_and_gap_arrays(self, batch, chunk=4096):
        """([n, 52] log-probability of each card, [n, 52] predicted tricks given up by each card) from stacked inputs."""
        n = len(batch['state'])
        batch = batch if 'bot_own' in batch else self.tag(batch, n)
        logp, gap = np.empty((n, 52), np.float32), np.empty((n, 52), np.float32)
        for i in range(0, n, chunk):
            out = self.run({k: batch[k][i:i + chunk] for k in INPUTS + WHO if k in batch})
            logp[i:i + chunk], gap[i:i + chunk] = log_softmax(out['policy']), out['gap']
        return logp, gap

    def log_policy(self, observations):
        if not observations:
            return np.zeros((0, 52), np.float32)
        return self.log_policy_arrays(self.tag(stack([self.encode(o) for o in observations]), len(observations)))

    def heads(self, observations):
        out = self.run(self.tag(stack([self.encode(o) for o in observations]), len(observations)))
        return dict(out, policy=log_softmax(out['policy']))
