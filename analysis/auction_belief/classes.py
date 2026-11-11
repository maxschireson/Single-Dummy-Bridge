import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Hand-type classes: auction posteriors after the opening lead without listing layouts.

The bidder and the hand-fit scorer see a hand as A,K,Q,J,T per suit plus a count of low
cards (2-9). Layouts of the two hidden hands that give seat A the same unseen honours and
the same number of unseen low cards in each suit are interchangeable for the bidding. Such
a set is a class; its multiplicity is the number of layouts in it. Weighting classes instead
of layouts gives the same posterior as listing every layout, at any trick.
"""
import math

import numpy as np

from gen import POP

LOGC = np.array([[math.log(math.comb(n, k)) if k <= n else -np.inf for k in range(9)] for n in range(9)])


def suit_options(hon_cards, n_low, void_a, void_b):
    """Ways to split one suit's unseen cards: honour subset for A (bit mask over hon_cards) and A's low count."""
    h = len(hon_cards)
    bit = [1 << (12 - c % 13) for c in hon_cards]
    sub = np.arange(1 << h)
    hon_a_of = np.array([sum(bit[j] for j in range(h) if m >> j & 1) for m in sub], np.int64)
    M = np.repeat(sub, n_low + 1)
    N = np.tile(np.arange(n_low + 1), 1 << h)
    keep = np.ones(len(M), bool)
    if void_a:
        keep &= (M == 0) & (N == 0)
    if void_b:
        keep &= (M == (1 << h) - 1) & (N == n_low)
    M, N = M[keep], N[keep]
    return dict(mask=M, n=N, cnt=POP[M] + N, hon_a=hon_a_of[M], hon_b=sum(bit) - hon_a_of[M], logmult=LOGC[n_low, N])


def join(cnt, ka):
    """All combinations of one option per suit in which A receives ka cards. Returns (n,4) option indices."""
    def pair(x, y):
        i = np.repeat(np.arange(len(x)), len(y))
        j = np.tile(np.arange(len(y)), len(x))
        return i, j, x[i] + y[j]
    i0, i1, s01 = pair(cnt[0], cnt[1])
    i2, i3, s23 = pair(cnt[2], cnt[3])
    o01, o23 = np.argsort(s01, kind='stable'), np.argsort(s23, kind='stable')
    b01 = np.searchsorted(s01[o01], np.arange(ka + 2))
    b23 = np.searchsorted(s23[o23], np.arange(ka + 2))
    L, R = [], []
    for t in range(ka + 1):
        l, r = o01[b01[t]:b01[t + 1]], o23[b23[ka - t]:b23[ka - t + 1]]
        if len(l) and len(r):
            L.append(np.repeat(l, len(r)))
            R.append(np.tile(r, len(l)))
    if not L:
        return np.zeros((0, 4), np.int64)
    L, R = np.concatenate(L), np.concatenate(R)
    return np.stack([i0[L], i1[L], i2[R], i3[R]], axis=1)


def pack(length, hon):
    key = np.zeros(len(length), np.int64)
    for s in range(4):
        key |= (length[:, s].astype(np.int64) | (hon[:, s].astype(np.int64) << 4)) << (9 * s)
    return key


def unpack(key):
    part = np.stack([(key >> (9 * s)) & 511 for s in range(4)], axis=1)
    return part & 15, part >> 4


def rep_hands(length, hon):
    """One 13-card hand per type: its honours plus the lowest low cards."""
    n = len(length)
    mem = np.zeros((n, 52), bool)
    for s in range(4):
        for j in range(5):
            mem[:, 13 * s + 12 - j] = (hon[:, s] >> j) & 1
        low = length[:, s] - POP[hon[:, s]]
        mem[:, 13 * s:13 * s + 8] = np.arange(8)[None, :] < low[:, None]
    assert (mem.sum(axis=1) == 13).all()
    return np.nonzero(mem)[1].reshape(n, 13)


class TypeCache:
    """Memo of a per-type function for one seat in one auction."""

    def __init__(self, fn, dtype):
        self.fn, self.keys, self.vals, self.evaluated = fn, np.zeros(0, np.int64), np.zeros(0, dtype), 0

    def get(self, length, hon):
        uniq, inv = np.unique(pack(length, hon), return_inverse=True)
        if len(self.keys):
            hit = self.keys[np.searchsorted(self.keys, uniq).clip(max=len(self.keys) - 1)] == uniq
        else:
            hit = np.zeros(len(uniq), bool)
        if not hit.all():
            new = uniq[~hit]
            vals = np.asarray(self.fn(*unpack(new)))
            keys = np.concatenate([self.keys, new])
            vals = np.concatenate([self.vals, vals.astype(self.vals.dtype)])
            order = np.argsort(keys)
            self.keys, self.vals = keys[order], vals[order]
            self.evaluated += len(new)
        return self.vals[np.searchsorted(self.keys, uniq)][inv.ravel()]


class ClassView:
    """Every class of hidden-hand layouts that fits the cards one player has seen."""

    def __init__(self, o, st):
        self.hidden = a, b = [s for s in range(4) if o.known_hands[s] is None]
        hist = o.history
        played = {s: [c for seat, c in hist if seat == s] for s in (a, b)}
        voids = set()
        for i, (seat, c) in enumerate(hist):
            led = hist[i - i % 4][1] // 13
            if c // 13 != led and seat in (a, b):
                voids.add((seat, led))
        unseen = sorted(st['rem'][a] + st['rem'][b])
        self.ka = ka = len(st['rem'][a])
        self.hon = [[c for c in unseen if c // 13 == s and c % 13 >= 8] for s in range(4)]
        self.low = [[c for c in unseen if c // 13 == s and c % 13 < 8] for s in range(4)]
        self.opts = opts = [suit_options(self.hon[s], len(self.low[s]), (a, s) in voids, (b, s) in voids) for s in range(4)]
        self.idx = idx = join([op['cnt'] for op in opts], ka)
        pl_len = {s: np.bincount([c // 13 for c in played[s]], minlength=4) for s in (a, b)}
        pl_hon = {s: [sum(1 << (12 - c % 13) for c in played[s] if c // 13 == u and c % 13 >= 8) for u in range(4)] for s in (a, b)}
        tot = [len(self.hon[s]) + len(self.low[s]) for s in range(4)]
        self.len_a = np.stack([opts[s]['cnt'][idx[:, s]] + pl_len[a][s] for s in range(4)], axis=1)
        self.hon_a = np.stack([opts[s]['hon_a'][idx[:, s]] | pl_hon[a][s] for s in range(4)], axis=1)
        self.len_b = np.stack([tot[s] - opts[s]['cnt'][idx[:, s]] + pl_len[b][s] for s in range(4)], axis=1)
        self.hon_b = np.stack([opts[s]['hon_b'][idx[:, s]] | pl_hon[b][s] for s in range(4)], axis=1)
        self.logmult = sum(opts[s]['logmult'][idx[:, s]] for s in range(4))
        assert (self.len_a.sum(axis=1) == 13).all() and (self.len_b.sum(axis=1) == 13).all()
        ra = set(st['rem'][a])
        want = []
        for s in range(4):
            m = sum(1 << j for j, c in enumerate(self.hon[s]) if c in ra)
            nl = sum(c in ra for c in self.low[s])
            want.append(int(np.flatnonzero((opts[s]['mask'] == m) & (opts[s]['n'] == nl))[0]))
        self.true = int(np.flatnonzero((idx == np.array(want)).all(axis=1))[0])

    def worlds(self, picks, st, nrng):
        """One layout per picked class; the low cards are dealt at random within the class."""
        a, b = self.hidden
        out = []
        for i in picks:
            ha, hb = [], []
            for s in range(4):
                op, j = self.opts[s], self.idx[i, s]
                m, nl = int(op['mask'][j]), int(op['n'][j])
                for t, c in enumerate(self.hon[s]):
                    (ha if m >> t & 1 else hb).append(c)
                low = self.low[s]
                if low:
                    perm = nrng.permutation(len(low))
                    ha += [low[t] for t in perm[:nl]]
                    hb += [low[t] for t in perm[nl:]]
            hands = [st['rem'][s] for s in range(4)]
            hands[a], hands[b] = tuple(sorted(ha)), tuple(sorted(hb))
            out.append(tuple(hands))
        return out


def logsumexp(x):
    m = x.max()
    return m + math.log(np.exp(x - m).sum())


def systematic(logw, m, u):
    """m class picks in proportion to exp(logw), evenly spaced through the cumulative weight."""
    p = np.exp(logw - logw.max())
    c = np.cumsum(p)
    return np.searchsorted(c / c[-1], (u + np.arange(m)) / m, side='left').clip(max=len(p) - 1)
