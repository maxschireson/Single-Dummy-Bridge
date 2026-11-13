"""Hand features and call predicates for compiled convention cards (Gen 9 WIP).

Every feature is a function of the hand type the hand-fit scorer already uses: four suit
lengths (S, H, D, C as in core.py) and four 5-bit honour masks (bit 0 = ace .. bit 4 = ten,
as in gen6_nets). So a predicate can be evaluated over a whole layout pool at once.

A predicate is a disjunction of clauses. A clause is a conjunction of interval constraints
on named features plus length relations between suits. ``dist`` is zero exactly when the
hand satisfies the predicate, and otherwise grows with how far it is from the nearest clause
(points of HCP, cards of length, ...), which is what the noisy-rule likelihood needs.
"""
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

SUITS = 'SHDC'                      # suit index as in core.py
STRAINS = 'CDHSN'                   # bid strain order
SUIT_OF_STRAIN = {'C': 3, 'D': 2, 'H': 1, 'S': 0}
MAJORS, MINORS = ('S', 'H'), ('D', 'C')

POP = np.array([bin(i).count('1') for i in range(32)])
HCP5 = np.array([sum(v for j, v in enumerate((4, 3, 2, 1, 0)) if i >> j & 1) for i in range(32)])
TOP3 = np.array([bin(i & 7).count('1') for i in range(32)])
CTRL5 = np.array([(2 if i & 1 else 0) + (1 if i & 2 else 0) for i in range(32)])
ACE, KING, QUEEN, JACK = 1, 2, 4, 8

# cost per unit of violation, by feature family
WEIGHTS = {'hcp': 1.0, 'len': 1.25, 'shape': 2.0, 'stop': 1.5, 'top': 0.75,
           'ctrl': 0.75, 'ltc': 1.0, 'count': 1.25, 'rel': 1.25}


def family_of(name):
    if name in ('hcp', 'tp', 'r20', 'r15'):
        return 'hcp'
    if name in SUITS or name in ('longest', 'short', 'second'):
        return 'len'
    if name in ('bal', 'semibal', 'unbal'):
        return 'shape'
    if name.startswith('stop'):
        return 'stop'
    if name.startswith('top'):
        return 'top'
    if name in ('ctrl', 'aces', 'kings') or name[:2] == 'kc' or (len(name) == 2 and name[0] in 'KQ' and name[1] in SUITS):
        return 'ctrl'
    if name == 'ltc':
        return 'ltc'
    if name in ('n4', 'n5', 'nshort'):
        return 'count'
    raise KeyError(f'unknown feature {name!r}')


def hand_features(length, hon):
    """Feature arrays (n,) from lengths (n,4) and honour bits (n,4)."""
    length = np.asarray(length, np.int64).reshape(-1, 4)
    hon = np.asarray(hon, np.int64).reshape(-1, 4)
    f = {'_length': length, '_hon': hon}
    hcp = HCP5[hon].sum(1)
    f['hcp'] = hcp
    for s, name in enumerate(SUITS):
        f[name] = length[:, s]
    srt = np.sort(length, axis=1)
    f['longest'], f['second'], f['short'] = srt[:, 3], srt[:, 2], srt[:, 0]
    doubletons = (length == 2).sum(1)
    f['bal'] = ((srt[:, 0] >= 2) & (doubletons <= 1) & (srt[:, 3] <= 5)).astype(np.int64)       # 4333 4432 5332
    f['semibal'] = ((srt[:, 0] >= 2) & (srt[:, 3] <= 6) & ~((srt[:, 3] == 6) & (srt[:, 2] >= 4))).astype(np.int64)
    f['unbal'] = 1 - f['bal']
    f['n4'] = (length >= 4).sum(1)
    f['n5'] = (length >= 5).sum(1)
    f['nshort'] = (length <= 1).sum(1)
    # total points for a suit contract: HCP plus 1 per card over four in the longest suit
    f['tp'] = hcp + np.maximum(srt[:, 3] - 4, 0)
    f['r20'] = hcp + srt[:, 3] + srt[:, 2]           # rule of 20
    f['r15'] = hcp + length[:, 0]                      # rule of 15 (fourth seat)
    ctrl = CTRL5[hon]
    f['ctrl'] = ctrl.sum(1)
    f['aces'] = (hon & ACE > 0).sum(1)
    f['kings'] = (hon & KING > 0).sum(1)
    ltc = np.zeros(len(length), np.int64)
    for s, name in enumerate(SUITS):
        n, h = length[:, s], hon[:, s]
        f['top3' + name] = TOP3[h]
        f['K' + name] = ((h & KING) > 0).astype(np.int64)
        f['Q' + name] = ((h & QUEEN) > 0).astype(np.int64)
        f['top5' + name] = POP[h]
        f['stop' + name] = (((h & ACE) > 0) | (((h & KING) > 0) & (n >= 2)) | (((h & QUEEN) > 0) & (n >= 3))
                            | (((h & JACK) > 0) & (n >= 4)) | (n >= 5)).astype(np.int64)
        win = ((h & ACE) > 0).astype(np.int64) + (((h & KING) > 0) & (n >= 2)) + (((h & QUEEN) > 0) & (n >= 3))
        ltc += np.minimum(n, 3) - np.minimum(win, np.minimum(n, 3))
    f['ltc'] = ltc
    for name in SUITS:
        f['kc' + name] = f['aces'] + f['K' + name]       # key cards with this suit as trumps
    return f


def features_of_hands(hands):
    """Features from concrete hands, a sequence of 13-card id sequences."""
    m = np.zeros((len(hands), 52), np.int64)
    for i, h in enumerate(hands):
        m[i, list(h)] = 1
    m = m.reshape(-1, 4, 13)
    length = m.sum(-1)
    hon = sum((m[..., 12 - j] > 0).astype(np.int64) << j for j in range(5))
    return hand_features(length, hon)


@dataclass(frozen=True)
class Clause:
    """Intervals {feature: (lo, hi)} and relations ((a, b, k): len a - len b >= k)."""
    bounds: tuple = ()
    rel: tuple = ()

    @staticmethod
    def of(rel=(), **bounds):
        b = []
        for k, v in sorted(bounds.items()):
            family_of(k)
            if isinstance(v, (int, np.integer)):
                v = (int(v), int(v))
            lo, hi = v
            b.append((k, -99 if lo is None else int(lo), 99 if hi is None else int(hi)))
        for a, c, k in rel:
            if a not in SUITS or c not in SUITS:
                raise KeyError(f'relations are between suits: {a!r}, {c!r}')
        return Clause(tuple(b), tuple((a, c, int(k)) for a, c, k in rel))

    def bound(self, name):
        for k, lo, hi in self.bounds:
            if k == name:
                return lo, hi
        return None

    def dist(self, f, weights=WEIGHTS):
        n = len(f['hcp'])
        d = np.zeros(n)
        for k, lo, hi in self.bounds:
            v = f[k]
            d += weights[family_of(k)] * (np.maximum(lo - v, 0) + np.maximum(v - hi, 0))
        for a, c, k in self.rel:
            d += weights['rel'] * np.maximum(k - (f[a] - f[c]), 0)
        return d

    def describe(self):
        parts = []
        for k, lo, hi in self.bounds:
            if lo == hi:
                parts.append(f'{k}={lo}')
            elif lo <= -99:
                parts.append(f'{k}<={hi}')
            elif hi >= 99:
                parts.append(f'{k}>={lo}')
            else:
                parts.append(f'{k} {lo}-{hi}')
        for a, c, k in self.rel:
            parts.append(f'{a}{">" if k > 0 else ">="}{c}' + (f'+{k - 1}' if k > 1 else ''))
        return ' & '.join(parts) or 'any'


@dataclass(frozen=True)
class Pred:
    clauses: tuple

    @staticmethod
    def of(*clauses):
        out = []
        for c in clauses:
            out.extend(c.clauses if isinstance(c, Pred) else (c,))
        return Pred(tuple(out))

    def dist(self, f, weights=WEIGHTS):
        return np.min(np.stack([c.dist(f, weights) for c in self.clauses]), axis=0)

    def sat(self, f):
        return self.dist(f) == 0

    def __and__(self, other):
        """Conjunction, distributed over the clauses (bounds intersected)."""
        out = []
        for a in self.clauses:
            for b in other.clauses:
                bounds = {k: (lo, hi) for k, lo, hi in a.bounds}
                for k, lo, hi in b.bounds:
                    if k in bounds:
                        lo0, hi0 = bounds[k]
                        bounds[k] = (max(lo, lo0), min(hi, hi0))
                    else:
                        bounds[k] = (lo, hi)
                out.append(Clause(tuple((k, lo, hi) for k, (lo, hi) in sorted(bounds.items())), tuple(sorted(set(a.rel + b.rel)))))
        return Pred(tuple(out))

    def __or__(self, other):
        return Pred(self.clauses + other.clauses)

    def range(self, name):
        """Loosest (lo, hi) of a feature over the clauses; None if some clause leaves it free."""
        lo, hi = 99, -99
        for c in self.clauses:
            b = c.bound(name)
            if b is None:
                return None
            lo, hi = min(lo, b[0]), max(hi, b[1])
        return lo, hi

    def describe(self):
        return ' | '.join(f'({c.describe()})' if len(self.clauses) > 1 else c.describe() for c in self.clauses)


def C(rel=(), **bounds):
    """A one-clause predicate."""
    return Pred((Clause.of(rel, **bounds),))


ANY = C()


@dataclass(frozen=True)
class Rule:
    """One call's meaning in one context. Rules of a context are tried in priority order."""
    call: str
    pred: Pred
    family: str
    label: str = ''
    forcing: int = 0               # 0 not forcing, 1 one round, 2 game, 3 slam try / ask
    artificial: bool = False
    shows: Mapping = field(default_factory=dict)  # extra meaning for the natural tracker, e.g. {'fit': 'H'}
