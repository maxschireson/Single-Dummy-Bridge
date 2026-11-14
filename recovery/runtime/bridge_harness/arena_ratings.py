"""Gen 9 arena statistics: rating table, cells, field score, the betting test and the gain rule.

Gen 9 design in progress (dave, implementing g9's docs/gen9/arena-statistics.md, G9-A4). Used by
no collector. Numbers here decide nothing until the rules version that names them is adopted.

Inputs are per-pair summaries of one bidding condition: for each played pair (i, j) the count,
mean and variance of the per-board IMP difference from i's side. Common and native auctions are
fitted separately by the caller.

  fit(pairs, players, reference)  -> Ratings (strengths, covariance, pair-effect variance t2)
  Ratings.cell(i, j)              -> (estimate, variance) of the pair's own mean
  Ratings.field_score(i, shares)  -> (F, variance, worst cell)
  Ratings.gain(i, j, u, v_ij)     -> drop in the variance of contrast u from one more board on (i, j)
  BettingTest                     -> promotion and futility by betting, valid at every look
  display_radius(t, sd)           -> the always-valid interval shown beside a running test
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

N0 = 50.0            # boards of shrinkage toward the common variance
V0 = 3.8 ** 2        # the common variance of a board
S_PRIOR = 3.0        # weak prior SD on a strength, IMPs a board
T2_CAP = 0.5 ** 2    # cap on the pair-effect variance
T2_MIN_PAIRS = 6     # fewer played pairs: no pair-effect variance
BOUND = 24.0


@dataclass(frozen=True)
class Pair:
    i: str
    j: str
    n: int
    mean: float          # from i's side
    var: float           # sample variance of a board (ddof 1); ignored when n < 2

    def shrunk_var(self, n0=N0, v0=V0):
        v = self.var if self.n > 1 else v0
        return (self.n * v + n0 * v0) / (self.n + n0)

    def se2(self, n0=N0, v0=V0):
        return self.shrunk_var(n0, v0) / self.n


def summarise(results):
    """[(i, j, x), ...] -> [Pair]: per-pair count, mean and variance. A pair keeps the orientation in which it first
    appears; a result given the other way round is folded in with its sign flipped."""
    acc = {}
    for i, j, x in results:
        key, s = ((i, j), 1.0) if (j, i) not in acc else ((j, i), -1.0)
        a = acc.setdefault(key, [0, 0.0, 0.0])
        a[0] += 1; a[1] += s * x; a[2] += x * x
    out = []
    for (i, j), (n, s1, s2) in acc.items():
        m = s1 / n
        out.append(Pair(i, j, n, m, (s2 - n * m * m) / (n - 1) if n > 1 else float('nan')))
    return out


@dataclass
class Ratings:
    players: list
    reference: str
    s: np.ndarray                    # strengths, reference at 0
    C: np.ndarray                    # covariance of s (reference row and column 0)
    t2: float
    pairs: list
    details: dict = field(default_factory=dict)

    def index(self, p):
        return self.players.index(p)

    def strength(self, p):
        k = self.index(p)
        return float(self.s[k]), float(self.C[k, k])

    def _a(self, i, j):
        a = np.zeros(len(self.players)); a[self.index(i)] += 1; a[self.index(j)] -= 1
        return a

    def predict(self, i, j):
        """The model's prediction for the pair's mean (all pairs), and its variance as a predictor of that mean."""
        a = self._a(i, j)
        return float(a @ self.s), float(a @ self.C @ a + self.t2)

    def _direct(self, i, j):
        for p in self.pairs:
            if (p.i, p.j) == (i, j):
                return p, 1.0
            if (p.i, p.j) == (j, i):
                return p, -1.0
        return None, 0.0

    def cell(self, i, j):
        """Precision-weighted mean of the pair's own result and the model's prediction from the other pairs."""
        p, sign = self._direct(i, j)
        if p is None:
            return self.predict(i, j)
        others = [q for q in self.pairs if q is not p]
        loo = fit(others, self.players, self.reference, t2=self.t2)
        pred, vp = loo.predict(i, j)
        e2 = p.se2()
        w_direct, w_model = 1 / e2, 1 / vp
        est = (w_direct * sign * p.mean + w_model * pred) / (w_direct + w_model)
        return float(est), float(1 / (w_direct + w_model))

    def field_score(self, i, shares):
        """F_i = sum_j q_j cell(i, j), with variance q' Cov q over the cells (cells' model parts covary through C;
        a pair's own result is independent of the others), and the worst cell by the upper end of its 95% interval."""
        opp = [j for j in shares if j != i and shares[j] > 0]
        q = np.array([shares[j] for j in opp], float)
        cells = [self.cell(i, j) for j in opp]
        est = np.array([c[0] for c in cells])
        lam, avec = [], []
        for j, (c, vc) in zip(opp, cells):
            p, _ = self._direct(i, j)
            _, vp = self.predict(i, j)
            lam.append(0.0 if p is None else (1 / p.se2()) / (1 / p.se2() + 1 / vp))
            avec.append(self._a(i, j))
        lam = np.array(lam); A = np.array(avec)
        cov = np.outer(1 - lam, 1 - lam) * (A @ self.C @ A.T)
        np.fill_diagonal(cov, [c[1] for c in cells])
        F = float(q @ est)
        varF = float(q @ cov @ q)
        upper = [c[0] + 1.96 * math.sqrt(c[1]) for c in cells]
        k = int(np.argmin(upper))
        return F, varF, dict(opponent=opp[k], estimate=float(est[k]), se=math.sqrt(cells[k][1]))

    def gain(self, i, j, u, v_ij=V0):
        """Drop in the variance of contrast u (a vector over players) from one more board on pair (i, j)."""
        a = self._a(i, j)
        Ca = self.C @ a
        return float((u @ Ca) ** 2 / (v_ij + a @ Ca))


def fit(pairs, players, reference, t2=None, s_prior=S_PRIOR, t2_cap=T2_CAP):
    """Weighted least squares on pair means with a pair-effect variance t2 and a weak prior on strengths."""
    players = list(players)
    P = len(players)
    ref = players.index(reference)
    free = [k for k in range(P) if k != ref]
    pairs = [p for p in pairs if p.n > 0]
    A = np.zeros((len(pairs), P))
    for r, p in enumerate(pairs):
        A[r, players.index(p.i)] += 1; A[r, players.index(p.j)] -= 1
    Af = A[:, free]
    m = np.array([p.mean for p in pairs], float)
    e2 = np.array([p.se2() for p in pairs], float)
    prior = np.eye(len(free)) / s_prior ** 2
    details = {}
    if t2 is None:
        t2 = 0.0
        if len(pairs) >= T2_MIN_PAIRS:
            W0 = 1 / e2
            M = Af.T @ (W0[:, None] * Af) + prior
            s0 = np.linalg.solve(M, Af.T @ (W0 * m))
            resid = m - Af @ s0
            Q = float(np.sum(W0 * resid ** 2))
            df = len(pairs) - np.linalg.matrix_rank(Af)
            denom = float(W0.sum() - np.trace(np.linalg.solve(M, Af.T @ ((W0 ** 2)[:, None] * Af))))
            if df > 0 and denom > 0:
                t2 = min(max((Q - df) / denom, 0.0), t2_cap)
            details.update(Q=Q, df=int(df))
    W = 1 / (e2 + t2)
    M = Af.T @ (W[:, None] * Af) + prior
    Cf = np.linalg.inv(M)
    sf = Cf @ (Af.T @ (W * m))
    s = np.zeros(P); s[free] = sf
    C = np.zeros((P, P)); C[np.ix_(free, free)] = Cf
    return Ratings(players, reference, s, C, float(t2), pairs, details)


# ---- promotion ---------------------------------------------------------------------------------

@dataclass
class BettingTest:
    """Promotion by betting on 'the candidate does not lead', futility by betting on 'it leads by at least d'.

    Board results x in IMPs from the candidate's side, z = x / 24. Capital K multiplies by (1 + b z) with b set from
    earlier boards only (one prior board at 0 with second moment (3/24)^2), promote when K >= 1/alpha. The futility
    capital L does the same on -(z - d/24) and stops at L >= 1/beta. Exact at every look for any bounded distribution."""
    alpha: float = 0.05
    beta: float = 0.10
    d: float = 0.05
    cap: int = 6000
    bet_cap: float = 0.5

    def __post_init__(self):
        self.reset()

    def reset(self):
        self.t = 0
        self.logK = 0.0; self.logL = 0.0
        self._p = [0.0, (3 / 24) ** 2, 1.0]   # sum, sum of squares, count, for the promotion bet
        self._f = [0.0, (3 / 24) ** 2, 1.0]   # the same for the futility bet
        self.decision = None

    @staticmethod
    def _bet(acc, cap):
        s1, s2, c = acc
        m = s1 / c; v = max(s2 / c - m * m, 1e-9)
        return min(max(m / (v + m * m), 0.0), cap)

    def update(self, x):
        """Add one board; returns 'promote', 'futility', 'cap' or None."""
        if self.decision is not None:
            return self.decision
        z = x / BOUND
        y = -(z - self.d / BOUND)
        b = self._bet(self._p, self.bet_cap); c = self._bet(self._f, self.bet_cap)
        self.logK += math.log1p(b * z); self.logL += math.log1p(c * y)
        for acc, val in ((self._p, z), (self._f, y)):
            acc[0] += val; acc[1] += val * val; acc[2] += 1
        self.t += 1
        if self.logK >= math.log(1 / self.alpha):
            self.decision = 'promote'
        elif self.logL >= math.log(1 / self.beta):
            self.decision = 'futility'
        elif self.t >= self.cap:
            self.decision = 'cap'
        return self.decision

    @property
    def K(self):
        return math.exp(self.logK)

    @property
    def L(self):
        return math.exp(self.logL)


def display_radius(t, sd, alpha=0.05, r2=7.94 / 1500):
    """Half-width of the always-valid 95% interval shown beside a running test (asymptotic confidence sequence,
    tightest near 1,500 boards); shown from board 300."""
    return sd * math.sqrt(2 * (t * r2 + 1) / (t * t * r2) * math.log(math.sqrt(t * r2 + 1) / alpha))
