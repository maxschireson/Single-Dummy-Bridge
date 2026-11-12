"""NumPy inference for the Gen6 play nets. No TensorFlow, no gradients.

LeadNet     opening leader's belief net ("joint auction belief"): samples the declarer's and
            dummy's hands as tokens (shape, then honours per suit); partner gets the rest and
            spot cards are dealt uniformly. Trained from the leader's seat only.
FitScorer   hand-fit scorer: P(a 13-card hand in a given seat would have made exactly that
            seat's calls). Works from any seat at any trick; the weight of a layout is the
            product over the hidden hands.
BidderState the frozen Gen5 bidder's recurrent features for the leader's own hand, an input
            of LeadNet. It is never applied to a hidden hand.

Card = 13*suit + rank, suits SHDC, ranks 2..A (core.py). Honour bits per suit: bit 0 = ace,
1 = king, 2 = queen, 3 = jack, 4 = ten. Call tokens are bidding_env.CALL_ID minus two
(PASS, X, XX, 1C..7N -> 0..37), placed in slots counted from the dealer and rotated so that
slot 0 belongs to the observing seat.
"""
import io
import math
import zipfile

import numpy as np

from .bidding_env import CALL_ID
from .core import normalize_bid, vulnerable

MAX_SLOTS = 28
N_CALLS = 38
POP = np.array([bin(i).count('1') for i in range(32)])
HON_HCP = np.array([sum(v for j, v in enumerate((4, 3, 2, 1, 0)) if i >> j & 1) for i in range(32)])
EYE14 = np.eye(14, dtype=np.float32)
EYE38 = np.eye(38, dtype=np.float32)
BITS5 = ((np.arange(32)[:, None] >> np.arange(5)[None, :]) & 1).astype(np.float32)
LGAMMA = np.array([math.lgamma(i + 1) for i in range(14)])
# all ways to split 13 cards over four suits (560)
COMP = np.array([(a, b, c, 13 - a - b - c) for a in range(14) for b in range(14 - a) for c in range(14 - a - b)], np.int64)
COMP_ID = np.full((14, 14, 14), -1, np.int64)
COMP_ID[COMP[:, 0], COMP[:, 1], COMP[:, 2]] = np.arange(len(COMP))
# legal honour subsets: MASKH[available bits, suit length, low cards available, subset]
MASKH = np.zeros((32, 14, 9, 32), bool)
for _a in range(32):
    for _sub in range(32):
        if not _sub & ~_a:
            for _l in range(14):
                for _lo in range(9):
                    MASKH[_a, _l, _lo, _sub] = POP[_sub] <= _l and _l - POP[_sub] <= _lo
# bidder input features
CARD_FEAT = np.zeros((52, 24), np.float32)
for _c in range(52):
    CARD_FEAT[_c, (_c // 13) * 6 + min(12 - _c % 13, 5)] = 1
CARD_HCP = np.array([max(0, c % 13 - 8) for c in range(52)], np.float32)
LEN_FEAT = ((np.arange(14).astype(np.float16) - np.float16(3.25)) / np.float16(1.75)).astype(np.float32)


def call_ids(auction):
    return np.array([CALL_ID[normalize_bid(c)] for c in auction], np.int64)


def hand_types(member):
    """Membership (..., 52) -> suit lengths (..., 4), honour bits (..., 4)."""
    m = np.asarray(member).reshape(*np.shape(member)[:-1], 4, 13)
    length = m.sum(-1).astype(np.int64)
    hon = sum((m[..., 12 - j] > 0).astype(np.int64) << j for j in range(5))
    return length, hon


def slot_indices(calls, dealer, seat):
    """Column of each call in the seat-aligned one-hot; calls past the last slot are dropped."""
    pos = (dealer - seat) % 4 + np.arange(len(calls))
    keep = pos < MAX_SLOTS
    return pos[keep] * N_CALLS + calls[keep] - 2


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def _relu(z):
    return np.maximum(z, 0)


def _masked_logp(logits, mask):
    z = np.where(mask, logits.astype(np.float64), -np.inf)
    m = z.max(axis=1, keepdims=True)
    return z - m - np.log(np.exp(z - m).sum(axis=1, keepdims=True))


class BidderState:
    """Third-layer features of the BEN-derived LSTM bidder after a seat's last call."""

    def __init__(self, path):
        import h5py
        with zipfile.ZipFile(path) as z, h5py.File(io.BytesIO(z.read('model.weights.h5')), 'r') as f:
            g = lambda name: np.array(f[name], dtype=np.float32)
            self.lstm = [tuple(g(f'layers/{n}/cell/vars/{i}') for i in range(3)) for n in ('lstm', 'lstm_1', 'lstm_2')]
            self.bn = []
            for n in ('batch_normalization', 'batch_normalization_1', 'batch_normalization_2'):
                gamma, beta, mean, var = (g(f'layers/{n}/vars/{i}') for i in range(4))
                scale = gamma / np.sqrt(var + 1e-3)
                self.bn.append((scale.astype(np.float32), (beta - mean * scale).astype(np.float32)))
        self.w_hand, self.w_ctx = self.lstm[0][0][:33], self.lstm[0][0][33:]

    def final_state(self, hand, seat, dealer, vulnerability, auction):
        calls = call_ids(auction)
        member = np.zeros(52, np.float32)
        member[list(hand)] = 1
        x = np.empty(33, np.float32)
        x[:2] = 1
        x[2], x[3] = vulnerable(vulnerability, seat), vulnerable(vulnerability, (seat + 1) % 4)
        x[4] = (member @ CARD_HCP - 10) / 4
        x[5:9] = LEN_FEAT[member.reshape(4, 13).sum(-1).astype(np.int64)]
        x[9:33] = member @ CARD_FEAT
        gates = x @ self.w_hand
        state, inp = None, None
        for k in range((seat - dealer) % 4, len(calls), 4):
            z = gates.copy()
            for j in range(4):
                z += self.w_ctx[40 * j + (calls[k - 4 + j] if k - 4 + j >= 0 else 0)]
            new = []
            for layer, ((w, u, b), (scale, shift)) in enumerate(zip(self.lstm, self.bn)):
                if layer:
                    z = inp @ w
                z = z + b
                if state is not None:
                    z = z + state[layer][0] @ u
                i, f, o = _sigmoid(z[:256]), _sigmoid(z[256:512]), _sigmoid(z[768:])
                c = i * np.tanh(z[512:768]) if state is None else f * state[layer][1] + i * np.tanh(z[512:768])
                h = o * np.tanh(c)
                new.append((h, c))
                inp = h * scale + shift
            state = new
        if inp is None:
            raise ValueError('Seat made no call')
        return inp


class LeadNet:
    """Opening leader's joint belief over the declarer's and dummy's hands."""

    def __init__(self, path, bidder_state):
        with np.load(path, allow_pickle=False) as z:
            self.p = {k: z[k] for k in z.files}
        self.bidder_state = bidder_state

    @staticmethod
    def fits(auction):
        """The net was trained on auctions whose calls all fit the slot window."""
        return len(auction) + 3 <= MAX_SLOTS

    def context(self, hand, seat, dealer, vulnerability, auction):
        """Everything the net conditions on, for one leader: context vector and counts."""
        member = np.zeros(52, np.float32)
        member[list(hand)] = 1
        length, hon = hand_types(member)
        low = length - POP[hon]
        state = self.bidder_state.final_state(hand, seat, dealer, vulnerability, auction)
        x = np.concatenate([member, member @ CARD_FEAT, [(member @ CARD_HCP - 10) / 4], LEN_FEAT[length],
                            [vulnerable(vulnerability, seat), vulnerable(vulnerability, (seat + 1) % 4)],
                            state.astype(np.float16)]).astype(np.float32)        # stored as float16 in training
        p = self.p
        a = p['Ea'][slot_indices(call_ids(auction), dealer, seat)].sum(axis=0)
        z = _relu(np.concatenate([a, x @ p['Wh']]) + p['b0'])
        z = _relu(z @ p['W1'] + p['b1'])
        ctx = _relu(z @ p['W2'] + p['b2'])
        return dict(ctx=ctx, cg=ctx @ p['Wc'], n=13 - length, avail=31 - hon, low=8 - low)

    def _shape1(self, ctx):
        p = self.p
        return _relu(ctx @ p['Ws1'] + p['bs1']) @ p['Wo1'] + p['bo1']

    def _shape2(self, ctx, type_d):
        p = self.p
        return _relu(np.concatenate([ctx, type_d], axis=1) @ p['Ws2'] + p['bs2']) @ p['Wo2'] + p['bo2']

    def _honours(self, cg, gx):
        p = self.p
        return _relu(np.concatenate([cg, gx], axis=1) @ p['Wg'] + p['bg']) @ p['Wgo'] + p['bgo']

    @staticmethod
    def _honour_input(own_len, prefix, s, other_type, flag, avail_s):
        n = len(own_len)
        suit = np.zeros((n, 4), np.float32)
        suit[:, s] = 1
        return np.concatenate([EYE14[own_len].reshape(n, 56), BITS5[prefix].reshape(n, 20), suit, other_type,
                               np.full((n, 1), flag, np.float32), EYE14[own_len[:, s]], BITS5[avail_s]], axis=1)

    def sample(self, c, n, rng):
        """n draws of (declarer lengths, declarer honours, dummy lengths, dummy honours)."""
        ctx, cg = np.repeat(c['ctx'][None], n, 0), np.repeat(c['cg'][None], n, 0)
        nn, avail, low = (np.repeat(c[k][None], n, 0) for k in ('n', 'avail', 'low'))

        def draw(logits, mask):
            pr = np.exp(_masked_logp(logits, mask))
            k = np.minimum((pr.cumsum(axis=1) < rng.random((n, 1))).sum(axis=1), pr.shape[1] - 1)
            bad = pr[np.arange(n), k] <= 0          # a rounding step onto a masked option
            k[bad] = pr[bad].argmax(axis=1)
            return k

        def honour_tokens(own_len, other_type, flag, av, lo):
            hon = np.zeros((n, 4), np.int64)
            for s in range(4):
                gx = self._honour_input(own_len, hon.copy(), s, other_type, flag, av[:, s])
                hon[:, s] = draw(self._honours(cg, gx), MASKH[av[:, s], own_len[:, s], np.clip(lo[:, s], 0, 8)])
            return hon
        d_len = COMP[draw(self._shape1(ctx), (COMP[None] <= nn[:, None]).all(-1))]
        d_hon = honour_tokens(d_len, np.zeros((n, 76), np.float32), 0., avail, low)
        d_low = d_len - POP[d_hon]
        type_d = np.concatenate([EYE14[d_len].reshape(n, 56), BITS5[d_hon].reshape(n, 20)], axis=1)
        m_len = COMP[draw(self._shape2(ctx, type_d), (COMP[None] <= (nn - d_len)[:, None]).all(-1))]
        m_hon = honour_tokens(m_len, type_d, 1., avail & ~d_hon, low - d_low)
        return d_len, d_hon, m_len, m_hon

    def log_density(self, c, d_len, d_hon, m_len, m_hon):
        """Log-probability of each concrete layout: its hand types, with the spot cards uniform."""
        low = np.repeat(c['low'][None], len(d_len), 0)
        d_low, m_low = d_len - POP[d_hon], m_len - POP[m_hon]
        spots = (LGAMMA[low] - LGAMMA[d_low] - LGAMMA[m_low] - LGAMMA[low - d_low - m_low]).sum(axis=1)
        return self.log_type_prob(c, d_len, d_hon, m_len, m_hon) - spots

    def log_type_prob(self, c, d_len, d_hon, m_len, m_hon):
        """Log-probability of each (declarer type, dummy type): the ten tokens' masked softmaxes."""
        n = len(d_len)
        ctx, cg = np.repeat(c['ctx'][None], n, 0), np.repeat(c['cg'][None], n, 0)
        nn, avail, low = (np.repeat(c[k][None], n, 0) for k in ('n', 'avail', 'low'))
        rows = np.arange(n)

        def honour_logp(own_len, own_hon, other_type, flag, av, lo):
            total = np.zeros(n)
            for s in range(4):
                prefix = np.zeros((n, 4), np.int64)
                prefix[:, :s] = own_hon[:, :s]
                gx = self._honour_input(own_len, prefix, s, other_type, flag, av[:, s])
                mask = MASKH[av[:, s], own_len[:, s], np.clip(lo[:, s], 0, 8)]
                total += _masked_logp(self._honours(cg, gx), mask)[rows, own_hon[:, s]]
            return total
        d_low = d_len - POP[d_hon]
        type_d = np.concatenate([EYE14[d_len].reshape(n, 56), BITS5[d_hon].reshape(n, 20)], axis=1)
        logp = _masked_logp(self._shape1(ctx), (COMP[None] <= nn[:, None]).all(-1))[rows, COMP_ID[d_len[:, 0], d_len[:, 1], d_len[:, 2]]]
        logp = logp + honour_logp(d_len, d_hon, np.zeros((n, 76), np.float32), 0., avail, low)
        logp = logp + _masked_logp(self._shape2(ctx, type_d), (COMP[None] <= (nn - d_len)[:, None]).all(-1))[rows, COMP_ID[m_len[:, 0], m_len[:, 1], m_len[:, 2]]]
        return logp + honour_logp(m_len, m_hon, type_d, 1., avail & ~d_hon, low - d_low)

    @staticmethod
    def deal(leader_hand, types, rng):
        """Concrete (declarer, dummy, partner) hands for sampled types; spot cards uniform."""
        own = set(leader_hand)
        out = []
        d_len, d_hon, m_len, m_hon = types
        for k in range(len(d_len)):
            hands = [[], [], []]
            for s in range(4):
                dh, mh = int(d_hon[k, s]), int(m_hon[k, s])
                for j in range(5):
                    c = 13 * s + 12 - j
                    if c not in own:
                        hands[0 if dh >> j & 1 else 1 if mh >> j & 1 else 2].append(c)
                lows = [13 * s + r for r in range(8) if 13 * s + r not in own]
                rng.shuffle(lows)
                dl, ml = int(d_len[k, s]) - POP[dh], int(m_len[k, s]) - POP[mh]
                hands[0] += lows[:dl]
                hands[1] += lows[dl:dl + ml]
                hands[2] += lows[dl + ml:]
            if any(len(h) != 13 for h in hands):
                raise RuntimeError('Lead net produced an impossible layout')
            out.append(tuple(tuple(sorted(h)) for h in hands))
        return out


class FitScorer:
    """log P(hand fits the calls its seat made). Three ReLU layers over hand type, vulnerability, auction."""

    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.p = {k: z[k] for k in z.files}
        self.cache = {}
        self.types = {}

    def auction_part(self, auction, dealer, seat):
        key = (tuple(auction), dealer, seat)
        if key not in self.cache:
            if len(self.cache) > 256:
                self.cache.clear()
            self.cache[key] = self.p['Wa'][slot_indices(call_ids(auction), dealer, seat)].sum(axis=0) + self.p['b0']
        return self.cache[key]

    def log_score(self, length, hon, own_vul, opp_vul, auction_part, chunk=16384):
        p = self.p
        out = np.empty(len(length), np.float64)
        for s in range(0, len(length), chunk):
            ln, hn = length[s:s + chunk], hon[s:s + chunk]
            n = len(ln)
            v = np.empty((n, 2), np.float32)
            v[:, 0], v[:, 1] = own_vul, opp_vul
            x = np.concatenate([EYE14[ln].reshape(n, 56), BITS5[hn].reshape(n, 20), ((ln - POP[hn]) / 8.0).astype(np.float32),
                                EYE38[HON_HCP[hn].sum(axis=1)], v], axis=1)
            z = _relu(x @ p['Wh'] + auction_part)
            z = _relu(z @ p['W1'] + p['b1'])
            z = _relu(z @ p['W2'] + p['b2'])
            z = (z @ p['Wo'] + p['bo'])[:, 0].astype(np.float64)
            out[s:s + chunk] = -np.logaddexp(0.0, -z)
        return out

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction):
        """log P(fit) for hand types (n,4) lengths and (n,4) honour bits. Each type is scored once
        per seat and auction and remembered, so later decisions of the same deal cost almost nothing."""
        key = (tuple(auction), dealer, vulnerability, seat)
        if key not in self.types:
            if len(self.types) >= 16:
                self.types.clear()
            self.types[key] = (np.zeros(0, np.int64), np.zeros(0))
        keys, vals = self.types[key]
        packed = (length * (14 ** np.arange(4))).sum(axis=1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(axis=1)
        uniq, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
        known = keys[np.searchsorted(keys, uniq).clip(max=len(keys) - 1)] == uniq if len(keys) else np.zeros(len(uniq), bool)
        if not known.all():
            new = first[~known]
            scores = self.log_score(length[new], hon[new], float(vulnerable(vulnerability, seat)),
                                    float(vulnerable(vulnerability, (seat + 1) % 4)), self.auction_part(auction, dealer, seat))
            keys, vals = np.concatenate([keys, uniq[~known]]), np.concatenate([vals, scores])
            order = np.argsort(keys)
            keys, vals = keys[order], vals[order]
            self.types[key] = (keys, vals)
        return vals[np.searchsorted(keys, uniq)][inverse.ravel()]

    def seat_log_score(self, member, seat, dealer, vulnerability, auction):
        """log P(fit) for original hands given as membership rows (n, 52)."""
        length, hon = hand_types(member)
        return self.type_log_score(length, hon, seat, dealer, vulnerability, auction)
