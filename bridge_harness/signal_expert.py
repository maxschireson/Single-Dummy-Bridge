"""Signal experts for a known opponent (E9-15): how a player chooses among equivalent spots, by situation and hand.

Gen 9 work in progress (sam, signals).

An occasion is a defender's play of one of two or more spots (2 to 9) of a suit it holds (E9-3's class rule), in a
situation with a key: signals.situation's keys (partner's lead, declarer's lead, first discard, trumps; the opening lead
is left to the lead table) and three new ones for the second round of a suit the defender followed to on the first
round (`partner_lead.r2`, `declarer_lead.r2`, `trump.r2`), where the first card's position is a feature.

What is modelled is the position of the card in its class: the lowest, the highest, or one of the middle cards (shared
evenly), as in SignalModel.emitted. Every quantity that depends on the defender's hand (its length and honours in the
suit, its points, how many spots it held, the first card's position, whether it could win the trick) is computed per
layout from the layout's hand, so the same function serves fitting (the recorded hand, one layout) and reading (every
layout of a pool). Hidden hands are labels at fitting time only.

Models of P(position | occasion):
  M1  one emission row per key and count message (E9-7's tables); second-round keys: uniform (today's reader ignores them).
  M2  a finer table: key x length (2, 3, 4, 5+) x spots held (2, 3, 4+) x an honour in the suit, each cell's counts
      shrunk toward its M1 row by `alpha` pseudo-occasions. Additive counts: it can live in the experience store.
  M3  multinomial logistic on one-hot features, with log M1 as offset and an L2 penalty: the expert.
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from .signals import SPOT, SPOT_MASK, situation

KEYS = ('partner_lead', 'declarer_lead', 'first_discard', 'trump', 'partner_lead.r2', 'declarer_lead.r2', 'trump.r2')
POSITIONS = ('low', 'high', 'mid')
HCP = np.zeros(52)
for _s in range(4):
    HCP[_s * 13 + 9:_s * 13 + 13] = (1, 2, 3, 4)            # J Q K A
NO_TRUMP = 4


def occasion_key(history, i, c):
    """(key, suit, first-round index or None) for play i, or None."""
    seat, x = history[i]
    if seat in (c.declarer, c.dummy) or x % 13 > SPOT:
        return None
    sit = situation(history, i, c)
    if sit is not None:
        return None if sit[0] == 'lead.opening' else (sit[0], sit[1], None)
    start = i - i % 4
    if i == start:
        return None
    led_suit = history[start][1] // 13
    if x // 13 != led_suit:
        return None
    rounds = [t for t in range(0, start, 4) if history[t][1] // 13 == led_suit]
    if len(rounds) != 1:
        return None
    r1 = rounds[0]
    j = next((t for t in range(r1, r1 + 4) if history[t][0] == seat), None)
    if j is None or j == r1 or history[j][1] // 13 != led_suit:
        return None
    first = situation(history, j, c)
    if first is None or first[0] not in ('partner_lead', 'declarer_lead', 'trump'):
        return None
    return (first[0] + '.r2', led_suit, j)


def _position(K, card):
    """[n] 0 lowest, 1 highest, 2 middle of `card` in each row's class K (rows where it is absent: -1)."""
    idx = np.arange(52)
    low = np.where(K, idx, 99).min(axis=1)
    high = np.where(K, idx, -1).max(axis=1)
    pos = np.where(card == low, 0, np.where(card == high, 1, 2))
    return np.where(K[:, card], pos, -1)


@dataclass
class Occasion:
    """One play read as a signal, in n layouts: public facts (scalars) and the hand's facts (arrays [n])."""
    key: str
    suit: int
    played: int
    public: dict
    K: np.ndarray                   # [n, 52] the class
    n: np.ndarray                   # [n] its size
    pos: np.ndarray                 # [n] position of the card played
    hand: dict = field(default_factory=dict)


def occasion(history, i, c, dummy_original, original):
    """The Occasion of play i, or None. `original` [n, 52] bool: the chooser's thirteen cards in each layout;
    `dummy_original` the dummy's thirteen cards (public after the opening lead)."""
    got = occasion_key(history, i, c)
    if got is None:
        return None
    key, suit, j = got
    seat, played = history[i]
    original = np.asarray(original, bool)
    n_l = len(original)
    gone = np.zeros(52, bool)
    gone[[x for s, x in history[:i] if s == seat]] = True
    held = original & ~gone[None, :]
    K = held & SPOT_MASK[suit][None, :]
    if not K[:, played].all():
        raise ValueError('the card played is not in its class in every layout')
    n = K.sum(axis=1)
    start = i - i % 4
    led_seat, led = history[start]
    trick = history[start:i]
    trump = c.trump
    led_suit = led // 13
    # who is winning the trick when the signaller plays, and could the signaller beat it with a card it holds
    best = None
    for s, y in trick:
        if best is None or (y // 13 == best[1] // 13 and y > best[1]) or (trump != NO_TRUMP and y // 13 == trump and best[1] // 13 != trump):
            best = (s, y)
    if trump != NO_TRUMP and best[1] // 13 == trump and led_suit != trump:
        can_win = np.zeros(n_l, bool) if played // 13 == led_suit else (held[:, trump * 13:trump * 13 + 13] & (np.arange(13) > best[1] % 13)).any(axis=1)
    elif played // 13 == led_suit:
        can_win = (held[:, led_suit * 13:led_suit * 13 + 13] & (np.arange(13) > best[1] % 13)[None, :]).any(axis=1)
    elif trump != NO_TRUMP:                                  # void in the suit led: it could have ruffed
        can_win = held[:, trump * 13:trump * 13 + 13].any(axis=1)
    else:
        can_win = np.zeros(n_l, bool)
    dummy = np.zeros(52, bool)
    dummy[list(dummy_original)] = True
    dummy_now = dummy.copy()
    dummy_now[[x for s, x in history[:i] if s == c.dummy]] = False
    side = [t for t in range(4) if t != suit and t != trump]
    dummy_len = int(dummy[suit * 13:suit * 13 + 13].sum())
    entry = any(dummy[t * 13 + 11] or dummy[t * 13 + 12] for t in range(4) if t != suit)
    public = dict(nt=trump == NO_TRUMP, trumpsuit=trump != NO_TRUMP and suit == trump,
                  leader=0 if led_seat == c.declarer else 1 if led_seat == c.dummy else 2 if led_seat == (seat + 2) % 4 else 3,
                  position=i % 4, trick=i // 4 + 1, dummy_now=int(dummy_now[suit * 13:suit * 13 + 13].sum()),
                  dummy_long_no_entry=bool(dummy_len >= 5 and not entry), side=len(side))
    length = original[:, suit * 13:suit * 13 + 13].sum(axis=1)
    honour = original[:, suit * 13 + 10:suit * 13 + 13].any(axis=1)
    hcp = (original * HCP[None, :]).sum(axis=1)
    hand = dict(length=length, parity=(length % 2 == 0), honour=honour, hcp=hcp, decided=~can_win)
    if j is not None:                                        # the first card's position in its class, layout by layout
        gone_j = np.zeros(52, bool)
        gone_j[[x for s, x in history[:j] if s == seat]] = True
        K1 = (original & ~gone_j[None, :]) & SPOT_MASK[suit][None, :]
        first = history[j][1]
        p1 = _position(K1, first) if first % 13 <= SPOT else np.full(n_l, 3)
        hand['first'] = np.where(K1.sum(axis=1) < 2, 4, np.where(p1 < 0, 3, p1))     # 0 low 1 high 2 mid 3 honour 4 forced
    else:
        hand['first'] = np.full(n_l, 5)
    return Occasion(key, suit, played, public, K, n, _position(K, played), hand)


# ---- the models ---------------------------------------------------------------------------------------------------------

EPS = .05                   # every model is mixed with this much of a uniform choice in the class (the reader's eps)


def card_probability(pos_probs, oc, eps=EPS):
    """[n] P(card) from [n, 3] probabilities of (low, high, mid): mid shared among the n - 2 middle cards; with two cards
    low and high renormalised; a class of one card is certain. Mixed with eps of a uniform choice."""
    n, pos = oc.n, oc.pos
    w = pos_probs[np.arange(len(pos)), np.clip(pos, 0, 2)]
    total = np.where(n >= 3, pos_probs.sum(axis=1), pos_probs[:, 0] + pos_probs[:, 1])
    size = np.where(pos == 2, np.maximum(n - 2, 1), 1)
    p = w / np.maximum(total, 1e-300) / size
    return np.where(n < 2, 1., (1 - eps) * p + eps / np.maximum(n, 1))


def uniform_rows(n):
    """[n, 3] position probabilities that make every card of the class equally likely."""
    n = np.asarray(n, float)
    rows = np.stack([np.ones_like(n), np.ones_like(n), np.maximum(n - 2, 0)], axis=1)
    return rows / rows.sum(axis=1, keepdims=True)


def length_bucket(length):
    return np.clip(np.asarray(length) - 2, 0, 3)               # 2, 3, 4, 5+


def spots_bucket(n):
    return np.clip(np.asarray(n) - 2, 0, 2)                    # 2, 3, 4+


class M1:
    """Emission rows per key and count message (signals.facts: 0 an even length, 1 odd): {key: [[low, high, mid] if even,
    [...] if odd]}, as E9-7's tables; keys without a row: every card of the class equally likely."""

    def __init__(self, table):
        self.table = {k: np.asarray(v, float) for k, v in table.items()}

    def positions(self, oc):
        t = self.table.get(oc.key)
        if t is None:
            return uniform_rows(oc.n)
        return t[oc.hand['length'] % 2]

    def probability(self, oc):
        t = self.table.get(oc.key)
        if t is None:
            return np.where(oc.n < 2, 1., 1. / np.maximum(oc.n, 1))
        return card_probability(self.positions(oc), oc)

    @staticmethod
    def fit(occasions, alpha=10.):
        """Rows from counts, shrunk toward the key's pooled positions by alpha (as signal_experience.emission)."""
        counts = {}
        for oc in occasions:
            if oc.key.endswith('.r2') or oc.n[0] < 2:
                continue
            c = counts.setdefault(oc.key, np.zeros((2, 3)))
            c[int(oc.hand['length'][0]) % 2, oc.pos[0]] += 1
        table = {}
        for k, c in counts.items():
            pooled = (c.sum(axis=0) + 1.) / (c.sum() + 3.)
            table[k] = ((c + alpha * pooled) / (c.sum(axis=1, keepdims=True) + alpha)).tolist()
        return M1(table)


class M2:
    """Cells key x length x spots x honour, shrunk toward M1's row (second-round keys: toward the key's pooled positions).
    counts: {key: [4, 3, 2, 3] array of (length bucket, spots bucket, honour, position)}."""

    def __init__(self, counts, base, alpha):
        self.counts = {k: np.asarray(v, float) for k, v in counts.items()}
        self.base, self.alpha = base, alpha

    @staticmethod
    def cell(oc):
        return length_bucket(oc.hand['length']), spots_bucket(oc.n), oc.hand['honour'].astype(int)

    def prior(self, oc):
        if oc.key in self.base.table:
            return self.base.positions(oc)
        c = self.counts.get(oc.key)
        row = (c.sum(axis=(0, 1, 2)) + 1.) / (c.sum() + 3.) if c is not None else np.ones(3) / 3
        return np.tile(row, (len(oc.n), 1))

    def positions(self, oc):
        prior = self.prior(oc)
        c = self.counts.get(oc.key)
        if c is None:
            return prior
        lb, sb, hb = self.cell(oc)
        cells = c[lb, sb, hb]                                                   # [n, 3]
        return (cells + self.alpha * prior) / (cells.sum(axis=1, keepdims=True) + self.alpha)

    def probability(self, oc):
        return card_probability(self.positions(oc), oc)

    def to_json(self):
        return dict(alpha=self.alpha, counts={k: v.tolist() for k, v in self.counts.items()})

    @staticmethod
    def fit(occasions, base, alpha):
        counts = {}
        for oc in occasions:
            if oc.n[0] < 2:
                continue
            c = counts.setdefault(oc.key, np.zeros((4, 3, 2, 3)))
            lb, sb, hb = M2.cell(oc)
            c[lb[0], sb[0], hb[0], oc.pos[0]] += 1
        return M2(counts, base, alpha)


# features of the expert: one-hot blocks, built the same way for one layout or many
def design(oc):
    """[n, F] one-hot features of an occasion, layout by layout."""
    n_l = len(oc.n)
    cols = []

    def onehot(values, size):
        v = np.asarray(values, int)
        out = np.zeros((n_l, size))
        out[np.arange(n_l), np.broadcast_to(v, (n_l,))] = 1.
        return out

    k = KEYS.index(oc.key)
    key = onehot(k, len(KEYS))
    pub = oc.public
    h = oc.hand
    cols += [key]
    cols += [key * h['parity'][:, None]]                                       # parity by key
    lb = onehot(length_bucket(h['length']), 4)
    cols += [(key[:, :, None] * lb[:, None, :]).reshape(n_l, -1)]              # length by key
    cols += [onehot(spots_bucket(oc.n), 3)]
    cols += [key * h['honour'][:, None]]
    cols += [onehot(np.clip(h['hcp'] // 4, 0, 3), 4)]
    cols += [onehot(int(pub['nt']), 2), onehot(int(pub['trumpsuit']), 2), onehot(pub['leader'], 4), onehot(pub['position'], 4)]
    cols += [onehot(min(3, [0, 0, 1, 1, 2, 2, 2][min(pub['trick'], 6)] if pub['trick'] <= 6 else 3), 4)]
    cols += [onehot(min(pub['dummy_now'], 5), 6), onehot(int(pub['dummy_long_no_entry']), 2)]
    cols += [key * h['decided'][:, None]]
    cols += [onehot(h['first'], 6)]
    return np.concatenate(cols, axis=1)


class M3:
    """P(position) = softmax(log prior + [0, x.w_high, x.w_mid]) over the positions the class has."""

    def __init__(self, w, base):
        self.w, self.base = w, base                                            # w: [F, 2]

    def prior(self, oc):
        return self.base.positions(oc)

    def positions(self, oc):
        z = np.log(np.maximum(self.prior(oc), 1e-300))
        X = design(oc)
        z = z + np.concatenate([np.zeros((len(X), 1)), X @ self.w], axis=1)
        z = np.where((oc.n >= 3)[:, None] | (np.arange(3) < 2)[None, :], z, -np.inf)
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def probability(self, oc):
        return card_probability(self.positions(oc), oc)

    @staticmethod
    def fit(occasions, base, lam, w0=None):
        rows = [(design(oc)[0], np.log(np.maximum(base.positions(oc)[0], 1e-300)), int(oc.pos[0]), oc.n[0] >= 3) for oc in occasions if oc.n[0] >= 2]
        X = np.array([r[0] for r in rows])
        off = np.array([r[1] for r in rows])
        y = np.array([r[2] for r in rows])
        has_mid = np.array([r[3] for r in rows])
        F = X.shape[1]
        mask = np.where(has_mid[:, None], 0., np.array([0., 0., -np.inf])[None, :])

        def f(v):
            w = v.reshape(F, 2)
            z = off + np.concatenate([np.zeros((len(X), 1)), X @ w], axis=1) + mask
            z = z - z.max(axis=1, keepdims=True)
            e = np.exp(z)
            p = e / e.sum(axis=1, keepdims=True)
            ll = np.log(p[np.arange(len(y)), y])
            G = p.copy()
            G[np.arange(len(y)), y] -= 1.
            g = X.T @ G[:, 1:]
            return -ll.sum() + lam * (v ** 2).sum(), g.ravel() + 2 * lam * v

        v0 = np.zeros(F * 2) if w0 is None else w0.w.ravel()
        r = minimize(f, v0, jac=True, method='L-BFGS-B', options=dict(maxiter=500))
        return M3(r.x.reshape(F, 2), base)


class Symmetric:
    """M0: one symmetric honesty per key (the reader's default model), through SignalModel; second rounds uniform."""

    def __init__(self, model):
        self.model = model

    def probability(self, oc, contract, led_suit, original):
        if oc.key.endswith('.r2'):
            return np.where(oc.n < 2, 1., 1. / np.maximum(oc.n, 1))
        kind = self.model.signal(oc.key)
        return self.model.probabilities(oc.key, kind, oc.played, oc.K, original, oc.suit, contract.trump, led_suit, contract.trump == NO_TRUMP)


def effective_honesty(p_high_even, p_high_odd, prior_even):
    """The symmetric honesty h (P(high | even) = (1 + h) / 2, P(high | odd) = (1 - h) / 2) whose information about the
    parity equals that of the observed rates, signed by the direction of the observed difference."""
    def info(a, b, q):
        pa = q * a + (1 - q) * b
        out = 0.
        for x, px in ((a, q), (b, 1 - q)):
            for y, py in ((x, pa), (1 - x, 1 - pa)):
                if y > 0 and py > 0:
                    out += px * y * np.log(y / py)
        return out
    target = info(p_high_even, p_high_odd, prior_even)
    lo, hi = 0., 1.
    for _ in range(60):
        mid = (lo + hi) / 2
        if info((1 + mid) / 2, (1 - mid) / 2, prior_even) < target:
            lo = mid
        else:
            hi = mid
    return float(np.sign(p_high_even - p_high_odd) * (lo + hi) / 2)
