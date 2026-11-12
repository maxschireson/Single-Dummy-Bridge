"""Layout families: the few hidden variables a decision swings on.

A layout, from the decider's seat, is how the unseen cards lie in the two hidden hands. Players do
not think in layouts; they think in a handful of variables (who holds the king, how the suit
splits) and in the families those variables cut the layouts into. This module finds such variables
for one decision and gives each family its exact weight.

  variables(view)            every candidate variable, as a yes/no question about the first hidden hand:
                               "holds X" for each unseen card ten or higher, and "has at least k of suit s"
  Features(view).of(worlds)  the answers for given layouts;  .of_classes(classes) for Gen 6's hand-type classes
  split(...)                 the best few variables for a set of outcomes: a small tree grown greedily
                               on the weighted variance of the outcomes it leaves unexplained
  family weights             Gen 6's class posterior is exact (gen6.Classes), and every variable here is a function
                               of the class, so a family's weight is a sum of class weights: no sampling

Outcomes are whatever the caller wants explained, one row per layout: double-dummy tricks of each
candidate card, the gap between two cards, or what a playout really took.
"""
from dataclasses import dataclass

import numpy as np

HONOUR = 8                      # rank index from which a card is named on its own: ten and up
NAMES = 'SHDC'
RANKS = '23456789TJQKA'


class Features:
    """Yes/no variables about the first hidden hand (view.hidden[0]); the other hidden hand holds the rest."""

    def __init__(self, view):
        self.view = view
        unseen = [int(c) for c in view.unseen]
        self.seat = view.hidden[0]
        self.cards = [c for c in unseen if c % 13 >= HONOUR]
        self.suit_total = [sum(1 for c in unseen if c // 13 == s) for s in range(4)]
        self.names, self.kind = [], []
        for c in self.cards:
            self.names.append(f'{NAMES[c // 13]}{RANKS[c % 13]}')
            self.kind.append(('card', c))
        for s in range(4):
            for k in range(1, self.suit_total[s] + 1):
                self.names.append(f'{NAMES[s]}>={k}')
                self.kind.append(('length', s, k))

    def __len__(self):
        return len(self.names)

    def of(self, worlds):
        """[layouts, variables] 0/1."""
        held = np.zeros((len(worlds), 52), bool)
        for i, w in enumerate(worlds):
            held[i, list(w[self.seat])] = True
        return self._answers(held[:, self.cards] if self.cards else np.zeros((len(worlds), 0), bool),
                             np.stack([held[:, 13 * s:13 * s + 13].sum(axis=1) for s in range(4)], axis=1))

    def of_classes(self, classes):
        """[classes, variables] 0/1 for gen6.Classes built on the same view."""
        n = len(classes)
        holds = np.zeros((n, len(self.cards)), bool)
        count = np.zeros((n, 4), np.int64)
        for s in range(4):
            op, j = classes.options[s], classes.index[:, s]
            count[:, s] = op['cnt'][j]
            for t, c in enumerate(classes.honours[s]):
                holds[:, self.cards.index(c)] = (op['mask'][j] >> t) & 1
        return self._answers(holds, count)

    def _answers(self, holds, count):
        out = [holds]
        for s in range(4):
            if self.suit_total[s]:
                out.append(count[:, s:s + 1] >= np.arange(1, self.suit_total[s] + 1)[None, :])
        return np.concatenate(out, axis=1).astype(np.int8)


def spread(y, w):
    """Weighted sum of squares of the rows of y about their weighted mean (total over columns)."""
    total = w.sum()
    if total <= 0:
        return 0.
    mean = (w[:, None] * y).sum(axis=0) / total
    return float((w[:, None] * (y - mean) ** 2).sum())


@dataclass
class Key:
    """The key variables of one decision, in the order chosen, and what they explain."""
    variables: list             # indices into the Features' variables
    explained: list             # share of the outcomes' spread explained by the first 1, 2, ... of them

    def families(self, x, most=None):
        """Family index of layouts with answers x[n, variables]: the joint values of the first `most` key variables."""
        code = np.zeros(len(x), np.int64)
        for i, v in enumerate(self.variables[:most]):
            code |= x[:, v].astype(np.int64) << i
        return code


def key_variables(x, y, w, most=3, least=0.02):
    """The few variables that best explain outcomes y[n, m] over layouts with answers x[n, f] and weights w[n].

    Greedy: each step adds the variable whose joint families with those already chosen leave the least weighted
    spread. k variables give up to 2^k families, the joint values, which is how a player would name them. Stops
    early when the best next variable explains less than `least` of the total spread."""
    y = np.asarray(y, float)
    if y.ndim == 1:
        y = y[:, None]
    w = np.asarray(w, float)
    x = np.asarray(x)
    total = spread(y, w)
    key = Key([], [])
    if total <= 1e-12 or not len(y):
        return key
    code = np.zeros(len(y), np.int64)
    left = total
    varies = [v for v in range(x.shape[1]) if 0 < x[:, v].sum() < len(x)]
    for step in range(most):
        best = (left, None)
        groups = [code == f for f in np.unique(code)]
        for v in varies:
            if v in key.variables:
                continue
            on = x[:, v] == 1
            after = 0.
            for m in groups:
                a, b = m & on, m & ~on
                after += (spread(y[a], w[a]) if a.any() else 0.) + (spread(y[b], w[b]) if b.any() else 0.)
                if after >= best[0]:
                    break
            if after < best[0] - 1e-12:
                best = (after, v)
        after, v = best
        if v is None or left - after < least * total:
            break
        key.variables.append(v)
        code |= x[:, v].astype(np.int64) << step
        left = after
        key.explained.append(1 - left / total)
    return key


def held_out(x, y, w, most=3, least=0.02, folds=2, seed=0):
    """Share of the spread of y explained on layouts the variables were not chosen on, for 0, 1, ..., `most` key
    variables: chosen and averaged within families on the other folds, scored here. Position 0 is no variable."""
    y = np.asarray(y, float)
    if y.ndim == 1:
        y = y[:, None]
    w = np.asarray(w, float)
    part = np.random.default_rng(seed).permutation(len(y)) % folds
    left, total = np.zeros(most + 1), 0.
    for f in range(folds):
        test, train = part == f, part != f
        key = key_variables(x[train], y[train], w[train], most, least)
        total += spread(y[test], w[test])
        overall = (w[train][:, None] * y[train]).sum(axis=0) / max(w[train].sum(), 1e-300)
        for depth in range(most + 1):
            d = min(depth, len(key.variables))
            fam_train, fam_test = key.families(x[train], d), key.families(x[test], d)
            for g in np.unique(fam_test):
                tr, te = fam_train == g, fam_test == g
                mass = w[train][tr].sum()
                mean = (w[train][tr][:, None] * y[train][tr]).sum(axis=0) / mass if mass > 0 else overall
                left[depth] += float((w[test][te][:, None] * (y[test][te] - mean) ** 2).sum())
    return [] if total <= 1e-12 else list(1 - left / total)
