"""Queryable bidders: anything that can say which call a hand would make next.

Work in progress (Gen 8 system layer, not the final form, used by no arena bot): docs/gen8_systems.md.

Training a reader for a system needs only this interface, so a neural bidder, a rule engine
or a compiled set of system notes plugs in the same way:

  bidder.sha256                             identity, as pinned in the system's package
  bidder.session(hands, seat, dealer, vul)  hands (n,13) card ids; seat, dealer (n,) 0..3;
                                            vul (n,) index into VUL_NAMES
  session.act(rows, calls, turn, legal)     the call each of `rows` makes at its turn.
                                            calls (len(rows), T) tokens of that row's auction,
                                            turn (len(rows),) the index of the call to make,
                                            legal (len(rows), 40). A session is asked once per
                                            turn of a row, in order.

Tokens are bidding_env.CALL_ID values: 2 PASS, 3 X, 4 XX, 5.. 1C..7N.
"""
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import zipfile

import numpy as np

from .gen6_nets import CARD_FEAT, CARD_HCP, LEN_FEAT

VUL_NAMES = ('None', 'NS', 'EW', 'Both')
VUL_NS = np.array([0, 1, 0, 1])
VUL_EW = np.array([0, 0, 1, 1])
PASS, DOUBLE, REDOUBLE = 2, 3, 4


def bid(level, strain):
    return 5 + 5 * (level - 1) + 'CDHSN'.index(strain)


def membership(hands):
    """(n,13) card ids -> (n,52) float32 membership."""
    hands = np.asarray(hands)
    m = np.zeros((len(hands), 52), np.float32)
    np.put_along_axis(m, hands, 1.0, axis=1)
    return m


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def options_sha256(kind, options):
    """Identity of a bidder that is defined by its options and not by a weights file."""
    return hashlib.sha256(json.dumps({'kind': kind, 'options': options}, sort_keys=True).encode()).hexdigest()


def _sigmoid(z):
    with np.errstate(over='ignore'):                    # exp overflows to inf for very negative z; the result, 0, is right
        return 1.0 / (1.0 + np.exp(-z))


class BenLstmBidder:
    """A BEN-format LSTM bidder (193 features in, 40 calls out) run greedily in NumPy.

    Each seat takes one recurrent step per own turn; the step sees the hand and the four
    calls before the turn. This is the network of every house bidder so far.
    """
    kind = 'ben-lstm-keras'

    def __init__(self, path):
        import h5py
        self.sha256 = file_sha256(path)
        with zipfile.ZipFile(path) as z, h5py.File(io.BytesIO(z.read('model.weights.h5')), 'r') as f:
            g = lambda name: np.array(f[name], dtype=np.float32)
            self.lstm = [tuple(g(f'layers/{n}/cell/vars/{i}') for i in range(3)) for n in ('lstm', 'lstm_1', 'lstm_2')]
            self.bn = []
            for n in ('batch_normalization', 'batch_normalization_1', 'batch_normalization_2'):
                gamma, beta, mean, var = (g(f'layers/{n}/vars/{i}') for i in range(4))
                scale = gamma / np.sqrt(var + 1e-3)
                self.bn.append((scale.astype(np.float32), (beta - mean * scale).astype(np.float32)))
            self.wd, self.bd = g('layers/dense/vars/0'), g('layers/dense/vars/1')
        self.w_hand, self.w_ctx = self.lstm[0][0][:33], self.lstm[0][0][33:]
        self.units = self.lstm[0][1].shape[0]

    def session(self, hands, seat, dealer, vul):
        return _LstmSession(self, np.asarray(hands), np.asarray(seat), np.asarray(vul))


class _LstmSession:
    def __init__(self, b, hands, seat, vul):
        n = len(hands)
        m = membership(hands)
        x = np.empty((n, 33), np.float32)
        x[:, :2] = 1
        x[:, 2] = np.where(seat % 2 == 0, VUL_NS[vul], VUL_EW[vul])
        x[:, 3] = np.where(seat % 2 == 0, VUL_EW[vul], VUL_NS[vul])
        x[:, 4] = (m @ CARD_HCP - 10) / 4
        x[:, 5:9] = LEN_FEAT[m.reshape(n, 4, 13).sum(-1).astype(np.int64)]
        x[:, 9:33] = m @ CARD_FEAT
        self.b, self.gates = b, x @ b.w_hand
        self.h = np.zeros((n, 3, b.units), np.float32)
        self.c = np.zeros((n, 3, b.units), np.float32)
        self.features = np.zeros((n, b.units), np.float32)      # third-layer output after the latest own call

    def act(self, rows, calls, turn, legal):
        b, u = self.b, self.b.units
        ar = np.arange(len(rows))
        z = self.gates[rows].copy()
        for back in range(4):
            pos = turn - 4 + back
            z += b.w_ctx[40 * back + np.where(pos >= 0, calls[ar, np.maximum(pos, 0)], 0)]
        inp = None
        for layer, ((w, rec, bias), (scale, shift)) in enumerate(zip(b.lstm, b.bn)):
            if layer:
                z = inp @ w
            z = z + bias + self.h[rows, layer] @ rec
            c = _sigmoid(z[:, u:2 * u]) * self.c[rows, layer] + _sigmoid(z[:, :u]) * np.tanh(z[:, 2 * u:3 * u])
            h = _sigmoid(z[:, 3 * u:]) * np.tanh(c)
            self.h[rows, layer], self.c[rows, layer] = h, c
            inp = h * scale + shift
        self.features[rows] = inp
        return np.argmax(np.where(legal, inp @ b.wd + b.bd, -np.inf), axis=1)


class NumpyPolicy:
    """A BEN-format bidder with bidding_ppo.Policy's predict(), without TensorFlow: for gen5_arena.auction.

    x is (batch, turns, 193) as bidding_env.encode writes it; the answer is the logits after each row's last turn."""

    def __init__(self, path):
        self.b = BenLstmBidder(path)
        self.sha256 = self.b.sha256

    def predict(self, x, lengths):
        b, u = self.b, self.b.units
        x = np.asarray(x, np.float32)
        n = len(x)
        h, c = np.zeros((n, 3, u), np.float32), np.zeros((n, 3, u), np.float32)
        out = np.zeros((n, b.wd.shape[1]), np.float32)
        for t in range(x.shape[1]):
            inp = x[:, t]
            for layer, ((w, rec, bias), (scale, shift)) in enumerate(zip(b.lstm, b.bn)):
                z = inp @ w + bias + h[:, layer] @ rec
                c[:, layer] = _sigmoid(z[:, u:2 * u]) * c[:, layer] + _sigmoid(z[:, :u]) * np.tanh(z[:, 2 * u:3 * u])
                h[:, layer] = _sigmoid(z[:, 3 * u:]) * np.tanh(c[:, layer])
                inp = h[:, layer] * scale + shift
            last = np.asarray(lengths) == t + 1
            out[last] = inp[last] @ b.wd + b.bd
        return out, np.zeros(n, np.float32)


class RuleBidder:
    """A stateless bidder: the call is a function of the hand, the position and the auction
    so far. Subclasses implement choose(); an engine without batch calls loops over rows there.
    A chosen call that is not legal becomes a pass."""
    kind = 'rule'
    sha256 = None

    def session(self, hands, seat, dealer, vul):
        return _RuleSession(self, np.asarray(hands), np.asarray(seat), np.asarray(dealer), np.asarray(vul))

    def choose(self, hands, seat, dealer, vul, calls, turn, legal):
        raise NotImplementedError

    def call(self, hand, seat, dealer, vul, calls):
        """One hand's next call (a token) after `calls` (tokens): for bidding a table call by call."""
        row = np.array([list(calls) + [-1]], np.int64)
        return int(self.choose(np.array([hand]), np.array([seat]), np.array([dealer]), np.array([vul]), row, np.array([len(calls)]), None)[0])


class _RuleSession:
    def __init__(self, b, hands, seat, dealer, vul):
        self.b, self.hands, self.seat, self.dealer, self.vul = b, hands, seat, dealer, vul

    def act(self, rows, calls, turn, legal):
        seen = np.where(np.arange(calls.shape[1])[None, :] < turn[:, None], calls, -1)     # nothing from the turn on is visible
        want = np.asarray(self.b.choose(self.hands[rows], self.seat[rows], self.dealer[rows], self.vul[rows], seen, turn, legal))
        return np.where(legal[np.arange(len(rows)), want], want, PASS)


class ToyBidder(RuleBidder):
    """A few natural rules with adjustable agreements: openings, one response, simple
    overcalls, then pass. A fixture for tests and pipeline checks, not a bridge system."""
    kind = 'toy'

    def __init__(self, nt=(15, 17), major=5, strong_club=None):
        self.nt, self.major, self.strong_club = (int(nt[0]), int(nt[1])), int(major), strong_club
        self.sha256 = options_sha256(self.kind, dict(nt=list(self.nt), major=self.major, strong_club=strong_club))

    def choose(self, hands, seat, dealer, vul, calls, turn, legal):
        n = len(hands)
        m = membership(hands).reshape(n, 4, 13)
        length = m.sum(-1).astype(np.int64)                                # spades, hearts, diamonds, clubs
        hcp = (m[:, :, 9:] * np.arange(1, 5)).sum((1, 2)).astype(np.int64)
        bids = calls >= 5
        made = bids.sum(1)
        first = bids.argmax(1)
        opened = calls[np.arange(n), first]
        undoubled = ~((calls == DOUBLE) | (calls == REDOUBLE)).any(1)
        who = (turn - first) % 4                                           # 2 = partner opened, 1 or 3 = an opponent
        out = np.where(made == 0, self._opening(hcp, length), PASS)
        one = (made == 1) & undoubled
        out = np.where(one & (who == 2), self._response(opened, hcp, length), out)
        return np.where(one & (who % 2 == 1), self._overcall(opened, hcp, length), out)

    def _opening(self, hcp, length):
        s, h, d, c = length.T
        strong = self.strong_club
        natural = (hcp >= 12) & (hcp < (strong or 99))
        balanced = (length.min(1) >= 2) & ((length == 2).sum(1) <= 1) & (s < 5) & (h < 5)
        out = np.full(len(hcp), PASS)
        for strain, n in (('D', d), ('H', h), ('S', s)):
            out = np.where((hcp >= 6) & (hcp <= 10) & (n >= 6), bid(2, strain), out)
        out = np.where(natural, bid(1, 'D') if strong else np.where(d >= c, bid(1, 'D'), bid(1, 'C')), out)
        out = np.where(natural & (h >= self.major), bid(1, 'H'), out)
        out = np.where(natural & (s >= self.major) & (s >= h), bid(1, 'S'), out)
        out = np.where(natural & balanced & (hcp >= self.nt[0]) & (hcp <= self.nt[1]), bid(1, 'N'), out)
        return np.where(hcp >= strong, bid(1, 'C'), out) if strong else out

    def _response(self, opened, hcp, length):
        s, h, d, c = length.T
        out = np.full(len(hcp), PASS)
        out = np.where((opened == bid(1, 'N')) & (hcp + self.nt[0] >= 25), bid(3, 'N'), out)
        for strain, n in (('H', h), ('S', s)):
            raised = np.where(hcp >= 13, bid(4, strain), np.where(hcp >= 10, bid(3, strain), bid(2, strain)))
            answer = np.where(hcp < 6, PASS, np.where(n >= (3 if self.major == 5 else 4), raised, bid(1, 'N')))
            out = np.where(opened == bid(1, strain), answer, out)
        minor = (opened == bid(1, 'D')) | ((opened == bid(1, 'C')) & (not self.strong_club))
        out = np.where(minor, np.where(hcp < 6, PASS, np.where(h >= 4, bid(1, 'H'), np.where(s >= 4, bid(1, 'S'), bid(1, 'N')))), out)
        if self.strong_club:
            out = np.where(opened == bid(1, 'C'), np.where(hcp <= 7, bid(1, 'D'), bid(1, 'N')), out)
        return out

    def _overcall(self, opened, hcp, length):
        strain = np.array([3, 2, 1, 0])[length.argmax(1)]                  # longest suit, as an index into CDHSN
        cheapest = np.where(5 + strain > opened, 5 + strain, np.where(10 + strain > opened, 10 + strain, PASS))
        return np.where((hcp >= 10) & (hcp <= 16) & (length.max(1) >= 5), cheapest, PASS)


def make_bidder(generator, root='.', external_root=None):
    """Build the bidder a package's generator entry describes, and check its identity.

    kinds: 'ben-lstm-keras' (path to a .keras file; `external` paths are relative to
    external_root), 'toy' (options for ToyBidder), 'python' (factory 'module:callable' called
    with options; the hook for engines kept outside this repository).
    """
    kind, options = generator['kind'], dict(generator.get('options') or {})
    if kind == 'ben-lstm-keras':
        if generator.get('external') and external_root is None:
            raise ValueError('this generator is external: give the folder that holds it')
        path = Path(external_root if generator.get('external') else root) / generator['path']
        if not path.exists():
            hint = f'; run python {generator["restore"]}' if generator.get('restore') else ''
            raise FileNotFoundError(f'{path} is missing{hint}')
        bidder = BenLstmBidder(path)
    elif kind == 'toy':
        bidder = ToyBidder(**options)
    elif kind == 'python':
        module, _, name = generator['factory'].partition(':')
        options = {k: os.path.expanduser(os.path.expandvars(v)) if isinstance(v, str) else v for k, v in options.items()}
        bidder = getattr(importlib.import_module(module), name)(**options)
    else:
        raise ValueError(f'no bidder adapter for generator kind {kind!r}')
    pinned = generator.get('sha256')
    if pinned and bidder.sha256 != pinned:
        raise ValueError(f'{kind} bidder identity {str(bidder.sha256)[:12]} differs from the pinned {pinned[:12]}')
    return bidder
