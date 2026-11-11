"""Exact legal-deal sampling from factorized bidding weights.

The neural marginal scores define an approximation, not an exact Bayesian
posterior. Dynamic programming conditions their product on every visible card,
remaining hand capacity and observed void. No rejection/MCMC or extra DDS solves.
"""
from functools import lru_cache
import math
import numpy as np

from .auction_belief import encode_auction
from .sampling import Sampler


class AuctionWeights:
    """NumPy inference for the frozen small model, exported/checked against Keras."""
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.weights = [z[f"w{i}"] for i in range(8)]
        self.cache = {}

    def predict(self, x):
        ce, se, w0, b0, w1, b1, w2, b2 = self.weights
        n = len(x['state'])
        h = np.concatenate([x['state'], ce[x['calls']].reshape(n, -1),
                            se[x['seats']].reshape(n, -1)], axis=1)
        h = np.maximum(h @ w0 + b0, 0)
        h = np.maximum(h @ w1 + b1, 0)
        return (h @ w2 + b2).reshape(n, 52, 4)

    def logits(self, o):
        # Reconstruct ONLY our visible original hand from remaining/public cards.
        hand = o.original_hand(o.controller)
        key = (hand, o.controller, o.dealer, o.vulnerability, o.auction)
        if key not in self.cache:
            x, _ = encode_auction(hand, o.controller, o.dealer, o.vulnerability, o.auction)
            relative = self.predict({k: v[None] for k, v in x.items()})[0]
            absolute = relative[:, [(s-o.controller) % 4 for s in range(4)]]
            if not np.isfinite(absolute).all(): raise ValueError('Nonfinite neural scores')
            if len(self.cache) > 128: self.cache.clear()
            self.cache[key] = absolute
        return self.cache[key]


class WeightedSampler:
    def __init__(self, observation, logits=None, strength=1.):
        if not math.isfinite(strength) or strength < 0: raise ValueError('Invalid strength')
        self.o = observation
        base = Sampler(observation)
        self.unknown, self.caps = base.unknown, base.caps
        self.cards = tuple(c for suit in base.suits for c in suit)
        self.allowed = tuple(base.allowed[c // 13] for c in self.cards)
        scores = np.zeros((52, 4)) if logits is None else np.asarray(logits)
        if scores.shape != (52, 4) or not np.isfinite(scores).all():
            raise ValueError('Expected finite 52x4 log weights')
        self.weights = tuple(tuple(float(strength*scores[c, s]) for s in self.unknown) for c in self.cards)
        n = len(self.cards)

        @lru_cache(None)
        def partition(i, caps):
            if i == n: return 0. if not any(caps) else -math.inf
            terms = []
            for j in range(len(caps)):
                if caps[j] and self.allowed[i][j]:
                    rest = caps[:j] + (caps[j]-1,) + caps[j+1:]
                    tail = partition(i+1, rest)
                    if tail != -math.inf: terms.append(self.weights[i][j]+tail)
            if not terms: return -math.inf
            m = max(terms)
            return m + math.log(sum(math.exp(x-m) for x in terms))
        self.partition = partition
        if partition(0, self.caps) == -math.inf: raise ValueError('No feasible legal deal')

    def choices(self, i, caps):
        z = self.partition(i, caps)
        for j in range(len(caps)):
            if caps[j] and self.allowed[i][j]:
                rest = caps[:j] + (caps[j]-1,) + caps[j+1:]
                tail = self.partition(i+1, rest)
                if tail != -math.inf:
                    yield j, rest, math.exp(self.weights[i][j]+tail-z)

    def draw(self, rng):
        hands = [list(h) if h is not None else [] for h in self.o.known_hands]
        caps = self.caps
        for i, card in enumerate(self.cards):
            ticket = rng.random(); chosen = None
            for j, rest, p in self.choices(i, caps):
                chosen = (j, rest)
                ticket -= p
                if ticket <= 0: break
            if chosen is None: raise ValueError('No feasible conditional assignment')
            j, caps = chosen
            hands[self.unknown[j]].append(card)
        return tuple(tuple(sorted(h)) for h in hands)

    def marginals(self):
        result = np.zeros((52, 4), np.float64)
        for s, hand in enumerate(self.o.known_hands):
            if hand is not None: result[list(hand), s] = 1.
        states = {self.caps: 1.}
        for i, card in enumerate(self.cards):
            following = {}
            for caps, mass in states.items():
                for j, rest, p in self.choices(i, caps):
                    probability = mass*p
                    result[card, self.unknown[j]] += probability
                    following[rest] = following.get(rest, 0.) + probability
            states = following
        return result
