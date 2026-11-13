"""A per-player head on the Gen 7 policy net: experience that adjusts the play inference (E9-14).

Gen 9 work in progress (sam, signals).

The net's decoder ends in one 256-vector per suit, d_s, and a linear map to the 13 card logits of that suit (the policy
column of `wd1`, W and b). A head keeps d and changes one player's logits:

    logit'[s, r] = tau * logit[s, r] + d_s . u + c[r] + sum_k a[k] d_s[k] W[k, r]

`tau` scales the net's confidence (what Gen 8's factor does to a likelihood, but normalised), `u` prefers a suit by its
decoder state (which suit to lead or discard), `c` prefers a rank, and `a` reweights each decoder unit's share of the card
logits (win or duck, cover or not, as far as the net's own features tell them apart). The logits are linear in all of
them, so the fit is convex: maximum likelihood on the player's recorded choices with an L2 pull toward no change (tau 1,
the rest 0). Each parameter's penalty is scaled to its typical effect on a logit, so one strength `lam` serves all of
them; `lam` is chosen by cross-validation over the player's boards.

A choice is a set of cards K: the card itself, or the class the signal model reads (spots of one suit), whose
probability is the head's total over K. Hidden hands are never inputs: d comes from the chooser's own view, and the
player's recorded hands are used only as labels, after the board.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .gen7_net import CARD_FEATURES, INPUTS, SEAT_SHOWN, SUIT_SHOWN, features

RANKS = 13
SUITS = 4


def relu(x):
    return np.maximum(x, 0.)


def decoder_state(params, batch, chunk=2048):
    """([n, 4, 256] the decoder's last hidden layer, [n, 52] the net's raw policy logits; illegal cards are -1e9)."""
    if int(np.asarray(params['kind'])) == 0:
        raise ValueError('the head needs the per-suit decoder (net kind 1)')
    n = len(batch['state'])
    W, b = policy_column(params)
    out_d = np.empty((n, SUITS, params['wd0'].shape[1]), np.float32)
    for i in range(0, n, chunk):
        part = {k: batch[k][i:i + chunk] for k in INPUTS}
        m = len(part['state'])
        cards, g = features(part, np)
        shown = np.asarray(part['shown']).astype(np.float32)
        shown = shown.reshape(m, 4, SEAT_SHOWN)[:, :, :SUIT_SHOWN * 4]
        about_suit = np.transpose(shown.reshape(m, 4, SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(m, 4, 4 * SUIT_SHOWN)
        s = np.concatenate([cards.reshape(m, 4, 13 * CARD_FEATURES), about_suit], axis=2)
        s = relu(s @ params['ws0'] + params['bs0'])
        s = relu(s @ params['ws1'] + params['bs1'])
        h = np.concatenate([s.reshape(m, -1), g], axis=1)
        h = relu(h @ params['wt0'] + params['bt0'])
        h = relu(h @ params['wt1'] + params['bt1'])
        slot = np.broadcast_to(np.eye(4, dtype=np.float32)[None], (m, 4, 4))
        d = np.concatenate([s, np.broadcast_to(h[:, None, :], (m, 4, h.shape[1])), slot], axis=2)
        out_d[i:i + chunk] = relu(d @ params['wd0'] + params['bd0'])
    logits = (out_d @ W + b).reshape(n, 52)
    return out_d, np.where(np.asarray(batch['legal']), logits, -1e9)


def policy_column(params):
    """(W [256, 13], b [13]): the decoder's map to card logits (column 0 of each rank's five outputs)."""
    return params['wd1'][:, 0::5].astype(np.float64), params['bd1'][0::5].astype(np.float64)


@dataclass
class PlayHead:
    tau: float
    u: np.ndarray       # [D]
    c: np.ndarray       # [13]
    a: np.ndarray       # [D]
    lam: float = 0.
    decisions: int = 0
    tables: int = 0

    @classmethod
    def identity(cls, dim=256):
        return cls(1., np.zeros(dim), np.zeros(RANKS), np.zeros(dim))

    def vector(self):
        return np.concatenate([[self.tau], self.u, self.c, self.a])

    @classmethod
    def from_vector(cls, v, dim, **kw):
        return cls(float(v[0]), v[1:1 + dim].copy(), v[1 + dim:1 + dim + RANKS].copy(), v[1 + dim + RANKS:].copy(), **kw)

    def to_json(self):
        return dict(tau=self.tau, u=self.u.tolist(), c=self.c.tolist(), a=self.a.tolist(), lam=self.lam,
                    decisions=self.decisions, tables=self.tables)

    @classmethod
    def from_json(cls, j):
        return cls(float(j['tau']), np.array(j['u']), np.array(j['c']), np.array(j['a']), float(j.get('lam', 0.)),
                   int(j.get('decisions', 0)), int(j.get('tables', 0)))

    def logits(self, d, legal, W, b):
        """[n, 52] the head's logits from decoder states [n, 4, D]; illegal cards -inf."""
        d = d.astype(np.float64)
        base = d @ W + b                                                      # [n, 4, 13]
        z = self.tau * base + (d @ self.u)[..., None] + self.c + (d * self.a) @ W
        return np.where(legal, z.reshape(len(d), 52), -np.inf)

    def log_policy(self, d, legal, W, b):
        z = self.logits(d, legal, W, b)
        z = z - z.max(axis=1, keepdims=True)
        return z - np.log(np.exp(z).sum(axis=1, keepdims=True))


def penalty_scales(d, W):
    """Per-parameter scales so that a unit of each parameter moves a typical logit by about one unit."""
    d = d.astype(np.float64)
    md = (d ** 2).mean(axis=(0, 1))                                           # [D]
    va = md * (W ** 2).mean(axis=1)                                           # [D]
    return np.concatenate([[1.], md, np.ones(RANKS), va])


def _objective(v, d, legal, K, W, b, lam, scale, dim, weight):
    """Dense form of the fit's objective and gradient (the reference for `_Entries.objective`)."""
    head = PlayHead.from_vector(v, dim)
    n = len(d)
    base = (d @ W + b)                                                        # [n, 4, 13]
    z = head.tau * base + (d @ head.u)[..., None] + head.c + (d * head.a) @ W
    z = np.where(legal, z.reshape(n, 52), -np.inf)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    total = e.sum(axis=1)
    inK = (e * K).sum(axis=1)
    loglik = np.log(inK) - np.log(total)
    p = e / total[:, None]
    q = e * K / inK[:, None]
    G = ((p - q) * weight[:, None]).reshape(n, SUITS, RANKS)                  # d(-loglik)/d(logit)
    g_tau = (G * base).sum()
    g_u = np.einsum('nsk,ns->k', d, G.sum(axis=2))
    g_c = G.sum(axis=(0, 1))
    g_a = np.einsum('nsk,nsk->k', d, G @ W.T)
    diff = v - _prior(dim)
    f = -(loglik * weight).sum() + lam * (scale * diff ** 2).sum()
    g = np.concatenate([[g_tau], g_u, g_c, g_a]) + 2 * lam * scale * diff
    return f, g


def _prior(dim):
    return np.concatenate([[1.], np.zeros(dim), np.zeros(RANKS), np.zeros(dim)])


class _Entries:
    """The legal cards of many decisions as one list, so that each step of the fit costs O(legal cards x D)."""

    def __init__(self, d, legal, K, W, b):
        n_, s_ = np.nonzero(legal)                                            # row-major: grouped by decision
        self.dim = d.shape[2]
        suit, rank = s_ // RANKS, s_ % RANKS
        self.X = d[n_, suit].astype(np.float64)                               # [E, D]
        self.Z = self.X * W.T[rank]                                           # [E, D]: d_k W[k, r]
        self.L = self.Z.sum(axis=1) + b[rank]                                # the net's logit
        self.rank = rank
        self.inK = K[n_, s_].astype(np.float64)
        self.starts = np.flatnonzero(np.r_[True, n_[1:] != n_[:-1]])
        self.dec = np.repeat(np.arange(len(self.starts)), np.diff(np.r_[self.starts, len(n_)]))
        self.n = len(self.starts)

    def scales(self):
        return np.concatenate([[1.], (self.X ** 2).mean(axis=0), np.ones(RANKS), (self.Z ** 2).mean(axis=0)])

    def objective(self, v, lam, scale):
        dim = self.dim
        tau, u, c, a = v[0], v[1:1 + dim], v[1 + dim:1 + dim + RANKS], v[1 + dim + RANKS:]
        z = tau * self.L + self.X @ u + c[self.rank] + self.Z @ a
        z = z - np.maximum.reduceat(z, self.starts)[self.dec]
        e = np.exp(z)
        total = np.add.reduceat(e, self.starts)
        inK = np.add.reduceat(e * self.inK, self.starts)
        loglik = np.log(inK) - np.log(total)
        G = e / total[self.dec] - e * self.inK / inK[self.dec]               # d(-loglik)/d(logit), per entry
        grad = np.concatenate([[G @ self.L], G @ self.X, np.bincount(self.rank, G, RANKS), G @ self.Z])
        diff = v - _prior(dim)
        return -loglik.sum() + lam * (scale * diff ** 2).sum(), grad + 2 * lam * scale * diff


def fit_head(d, legal, K, W, b, lam, scale=None, start=None, weight=None, maxiter=300, entries=None):
    """The head that maximises the log-likelihood of the choices K (a set of cards per decision) minus lam * penalty."""
    if weight is not None:
        d = d.astype(np.float64)
        dim = d.shape[2]
        scale = penalty_scales(d, W) if scale is None else scale
        v0 = PlayHead.identity(dim).vector() if start is None else start.vector()
        r = minimize(_objective, v0, args=(d, legal, K, W, b, lam, scale, dim, weight), jac=True, method='L-BFGS-B',
                     options=dict(maxiter=maxiter))
        return PlayHead.from_vector(r.x, dim, lam=lam, decisions=len(d))
    ent = _Entries(d, legal, K, W, b) if entries is None else entries
    scale = ent.scales() if scale is None else scale
    v0 = PlayHead.identity(ent.dim).vector() if start is None else start.vector()
    r = minimize(ent.objective, v0, args=(lam, scale), jac=True, method='L-BFGS-B', options=dict(maxiter=maxiter))
    return PlayHead.from_vector(r.x, ent.dim, lam=lam, decisions=ent.n)


def choice_log_likelihood(head, d, legal, K, W, b):
    """[n] log of the head's probability of each choice."""
    lp = head.log_policy(d, legal, W, b)
    return np.log((np.exp(lp) * K).sum(axis=1))


def fit_cv(d, legal, K, groups, W, b, lams=(1., 3., 10., 30., 100., 300., 1000., 3000.), folds=3, seed=0, maxiter=200):
    """(head refitted on all decisions at the best lam, {lam: held-out log-likelihood gain per decision over the net}).

    Folds are by group (a table), so a board's decisions are never split between fitting and checking. Each fold walks
    the lam grid from strong to weak, starting each fit from the last. The penalty's scales come from all decisions."""
    full = _Entries(d, legal, K, W, b)
    scale = full.scales()
    ug = np.unique(groups)
    rng = np.random.default_rng(seed)
    fold_of = dict(zip(ug, rng.permutation(len(ug)) % folds))
    fold = np.array([fold_of[g] for g in groups])
    score = {lam: 0. for lam in lams}
    base = choice_log_likelihood(PlayHead.identity(d.shape[2]), d, legal, K, W, b)
    for k in range(min(folds, len(ug))):
        tr, te = fold != k, fold == k
        if not te.any() or not tr.any():
            continue
        ent = _Entries(d[tr], legal[tr], K[tr], W, b)
        start = None
        for lam in sorted(lams, reverse=True):
            h = fit_head(None, None, None, W, b, lam, scale, start, maxiter=maxiter, entries=ent)
            score[lam] += float(choice_log_likelihood(h, d[te], legal[te], K[te], W, b).sum() - base[te].sum())
            start = h
        del ent
    best = max(lams, key=lambda lam: score[lam])
    start = None
    for lam in sorted(lams, reverse=True):          # the same warm-started path, so the final fit matches the folds'
        if lam < best:
            break
        start = fit_head(None, None, None, W, b, lam, scale, start, maxiter=maxiter, entries=full)
    start.tables = len(ug)
    return start, {lam: s / len(d) for lam, s in score.items()}
