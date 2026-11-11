"""Uniform deals conditional on cards, counts and observed voids; no bid inference."""
from functools import lru_cache
from math import factorial


def allocations(total, caps, allowed):
    def rec(i, left, prefix):
        if i == len(caps) - 1:
            if left <= caps[i] and (allowed[i] or left == 0):
                yield prefix + (left,)
            return
        for n in range(min(left, caps[i]) + 1 if allowed[i] else 1):
            yield from rec(i + 1, left - n, prefix + (n,))
    yield from rec(0, total, ())


class Sampler:
    def __init__(self, observation):
        self.o = observation
        self.unknown = tuple(s for s in range(4) if observation.known_hands[s] is None)
        played = {c for _, c in observation.history}
        known = {c for h in observation.known_hands if h is not None for c in h}
        unseen = set(range(52)) - played - known
        self.suits = tuple(tuple(sorted(c for c in unseen if c // 13 == s)) for s in range(4))
        self.caps = tuple(13 - sum(seat == s for seat, _ in observation.history) for s in self.unknown)
        voids = set()
        for i, (seat, c) in enumerate(observation.history):
            led = observation.history[i - i % 4][1] // 13
            if c // 13 != led:
                voids.add((seat, led))
        self.allowed = tuple(tuple((seat, s) not in voids for seat in self.unknown) for s in range(4))

        @lru_cache(None)
        def count(s, caps):
            if s == 4:
                return int(not any(caps))
            result = 0
            for a in allocations(len(self.suits[s]), caps, self.allowed[s]):
                rest = tuple(c - n for c, n in zip(caps, a))
                result += ways(a) * count(s + 1, rest)
            return result
        self.count = count
        self.unconstrained = all(all(a) for a in self.allowed)
        if not self.unconstrained and count(0, self.caps) == 0:
            raise ValueError("No hidden deal is consistent with observation")

    def draw(self, rng):
        hands = [list(h) if h is not None else [] for h in self.o.known_hands]
        if self.unconstrained:
            cards = [c for suit in self.suits for c in suit]
            rng.shuffle(cards)
            offset = 0
            for seat, n in zip(self.unknown, self.caps):
                hands[seat] = cards[offset:offset + n]
                offset += n
        else:
            caps = self.caps
            for s in range(4):
                ticket = rng.randrange(self.count(s, caps))
                for a in allocations(len(self.suits[s]), caps, self.allowed[s]):
                    rest = tuple(c - n for c, n in zip(caps, a))
                    weight = ways(a) * self.count(s + 1, rest)
                    if ticket < weight:
                        break
                    ticket -= weight
                cards = list(self.suits[s])
                rng.shuffle(cards)
                offset = 0
                for seat, n in zip(self.unknown, a):
                    hands[seat].extend(cards[offset:offset + n])
                    offset += n
                caps = rest
        return tuple(tuple(sorted(h)) for h in hands)


def ways(allocation):
    n = factorial(sum(allocation))
    for k in allocation:
        n //= factorial(k)
    return n
