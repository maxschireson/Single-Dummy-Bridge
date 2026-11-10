import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""NumPy inference for the Gen5 bidder (three LSTM-256 layers, BatchNorm, Dense-40).

Used to test whether a hypothetical hand would have made the calls a seat
actually made (greedy, as in the arena). Verified against recorded auctions.
"""
import io
import sys
import zipfile

import h5py
import numpy as np

RUNTIME = RUNTIME
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)
from bridge_harness.bidding_env import CALLS, CALL_ID, legal_mask  # noqa: E402
from bridge_harness.core import normalize_bid, vulnerable  # noqa: E402

CARD_FEAT = np.zeros((52, 24), np.float32)
for _c in range(52):
    CARD_FEAT[_c, (_c // 13) * 6 + min(12 - _c % 13, 5)] = 1
CARD_HCP = np.array([max(0, c % 13 - 8) for c in range(52)], np.float32)
LEN_FEAT = ((np.arange(14).astype(np.float16) - np.float16(3.25)) / np.float16(1.75)).astype(np.float32)


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def membership(hands):
    """(n,13) card ids -> (n,52) float32 one-hot membership."""
    hands = np.asarray(hands)
    m = np.zeros((len(hands), 52), np.float32)
    np.put_along_axis(m, hands, 1.0, axis=1)
    return m


def base_features(hands, seat, vulnerability):
    """The 33 hand/vulnerability features of the bidder input, for a batch of hands."""
    m = membership(hands)
    n = len(m)
    x = np.empty((n, 33), np.float32)
    x[:, :2] = 1
    x[:, 2] = vulnerable(vulnerability, seat)
    x[:, 3] = vulnerable(vulnerability, (seat + 1) % 4)
    x[:, 4] = (m @ CARD_HCP - 10) / 4
    lens = m.reshape(n, 4, 13).sum(-1).astype(np.int64)
    x[:, 5:9] = LEN_FEAT[lens]
    x[:, 9:33] = m @ CARD_FEAT
    return x


class NumpyBidder:
    def __init__(self, path):
        z = zipfile.ZipFile(path)
        f = h5py.File(io.BytesIO(z.read('model.weights.h5')), 'r')
        g = lambda name: np.array(f[name], dtype=np.float32)
        self.lstm, self.bn = [], []
        for n in ('lstm', 'lstm_1', 'lstm_2'):
            self.lstm.append(tuple(g(f'layers/{n}/cell/vars/{i}') for i in range(3)))
        for n in ('batch_normalization', 'batch_normalization_1', 'batch_normalization_2'):
            gamma, beta, mean, var = (g(f'layers/{n}/vars/{i}') for i in range(4))
            scale = gamma / np.sqrt(var + 1e-3)
            self.bn.append((scale.astype(np.float32), (beta - mean * scale).astype(np.float32)))
        self.wd, self.bd = g('layers/dense/vars/0'), g('layers/dense/vars/1')
        self.w_hand = self.lstm[0][0][:33]      # hand features -> gates
        self.w_ctx = self.lstm[0][0][33:]       # 4 x 40 call one-hots -> gates

    def step(self, hand_gates, ctx_gates, state):
        """One own-turn step. hand_gates (n,1024), ctx_gates (1024,), state or None."""
        new = []
        inp = None
        for layer, ((w, u, b), (scale, shift)) in enumerate(zip(self.lstm, self.bn)):
            z = (hand_gates + ctx_gates) if layer == 0 else inp @ w
            z = z + b
            if state is not None:
                h, c = state[layer]
                z = z + h @ u
            i, f, g, o = (z[:, :256], z[:, 256:512], z[:, 512:768], z[:, 768:])
            i, f, o = sigmoid(i), sigmoid(f), sigmoid(o)
            g = np.tanh(g)
            c2 = i * g if state is None else f * state[layer][1] + i * g
            h2 = o * np.tanh(c2)
            new.append((h2, c2))
            inp = h2 * scale + shift
        return inp @ self.wd + self.bd, new


class AuctionModel:
    """Per-seat consistency tests for one completed auction."""

    def __init__(self, bidder, dealer, vulnerability, auction):
        self.b, self.dealer, self.vul = bidder, dealer, vulnerability
        self.calls = tuple(normalize_bid(c) for c in auction)
        self.turns = {}
        for seat in range(4):
            rows = []
            first = (seat - dealer) % 4
            for k in range(first, len(self.calls), 4):
                ctx = np.zeros(1024, np.float32)
                for j in range(4):
                    kk = k - 4 + j
                    token = CALL_ID[self.calls[kk]] if kk >= 0 else 0
                    ctx += bidder.w_ctx[40 * j + token]
                mask = legal_mask(dealer, self.calls[:k])
                rows.append((ctx, mask, CALL_ID[self.calls[k]]))
            self.turns[seat] = rows

    def check(self, seat, hands, chunk=8192, return_logp=False):
        """Boolean per hand: would this hand have made every call the seat made?"""
        hands = np.asarray(hands)
        out = np.zeros(len(hands), bool)
        steps = 0
        for start in range(0, len(hands), chunk):
            h = hands[start:start + chunk]
            gates = base_features(h, seat, self.vul) @ self.b.w_hand
            alive = np.arange(len(h))
            state = None
            for ctx, mask, target in self.turns[seat]:
                if not len(alive):
                    break
                logits, state = self.b.step(gates[alive], ctx, state)
                steps += len(alive)
                ok = np.argmax(np.where(mask, logits, -np.inf), axis=1) == target
                alive = alive[ok]
                state = [(hh[ok], cc[ok]) for hh, cc in state]
            out[start + alive] = True
        self.last_steps = steps
        return out

    def log_likelihood(self, seat, hands):
        """Soft log-probability of the seat's calls (legal-masked softmax), per hand."""
        hands = np.asarray(hands)
        gates = base_features(hands, seat, self.vul) @ self.b.w_hand
        total = np.zeros(len(hands), np.float64)
        state = None
        for ctx, mask, target in self.turns[seat]:
            logits, state = self.b.step(gates, ctx, state)
            z = np.where(mask, logits, -np.inf).astype(np.float64)
            z -= z.max(axis=1, keepdims=True)
            total += z[:, target] - np.log(np.exp(z).sum(axis=1))
        return total
