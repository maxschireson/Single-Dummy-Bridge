# SPDX-License-Identifier: Apache-2.0
"""Information-consistent declarer search, inspired by Cazenave & Ventos' alpha-mu.

Independent implementation of published algorithmic ideas; no upstream alpha-mu
source copied. See CREDITS.md and docs/consistent_strategies.md. DDS keeps its own
Apache-2.0 notices. Perfect-information defence is an explicit model assumption.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import inf, isfinite
import time

from .core import Contract, score, winner


@dataclass(frozen=True)
class Position:
    hands: tuple[tuple[int, ...], ...]
    leader: int
    trick: tuple[tuple[int, int], ...] = ()
    tricks: int = 0  # tricks already won by declarer

    @property
    def actor(self):
        return (self.leader + len(self.trick)) % 4

    @property
    def done(self):
        return not any(self.hands)

    @property
    def remaining_tricks(self):
        return (sum(map(len, self.hands)) + len(self.trick)) // 4

    def legal(self):
        hand = self.hands[self.actor]
        return tuple(c for c in hand if self.trick and c // 13 == self.trick[0][1] // 13) or hand

    def play(self, c, trump, declarer):
        if c not in self.legal():
            raise ValueError("Illegal strategy action")
        hands = list(self.hands)
        hands[self.actor] = tuple(x for x in hands[self.actor] if x != c)
        trick = self.trick + ((self.actor, c),)
        if len(trick) == 4:
            lead = winner(trick, trump)
            return Position(tuple(hands), lead, (), self.tricks + int(lead % 2 == declarer % 2))
        return Position(tuple(hands), self.leader, trick, self.tricks)


def validate_worlds(worlds, weights, declarer):
    """Validate before any search; duplicates of whole worlds are allowed particles."""
    worlds, weights = tuple(worlds), tuple(weights)
    if not worlds or len(worlds) != len(weights) or declarer not in range(4):
        raise ValueError("Need worlds, matching weights and a valid declarer")
    if any(not isfinite(w) or w < 0 for w in weights) or not isfinite(sum(weights)) or sum(weights) <= 0:
        raise ValueError("Weights must be finite, nonnegative and have positive finite sum")
    first = worlds[0]
    pool = set(sum(first.hands, ()))
    for p in worlds:
        if len(p.hands) != 4 or p.leader not in range(4) or not 0 <= len(p.trick) <= 3:
            raise ValueError("Invalid position structure")
        cards = sum(p.hands, ()) + tuple(c for _, c in p.trick)
        if any(type(c) is not int or not 0 <= c < 52 for c in cards) or len(set(cards)) != len(cards):
            raise ValueError("Duplicated or invalid cards")
        if any(tuple(sorted(h)) != h for h in p.hands):
            raise ValueError("Hands must be sorted tuples")
        if any(s != (p.leader + i) % 4 for i, (s, _) in enumerate(p.trick)):
            raise ValueError("Incorrect current-trick seating")
        counts = [len(p.hands[s]) + sum(t == s for t, _ in p.trick) for s in range(4)]
        if len(set(counts)) != 1 or not 0 <= counts[0] <= 13:
            raise ValueError("Incorrect remaining hand counts")
        if type(p.tricks) is not int or not 0 <= p.tricks <= 13 - counts[0]:
            raise ValueError("Invalid accumulated trick count")
        for seat, c in p.trick[1:]:
            if c // 13 != p.trick[0][1] // 13 and any(x // 13 == p.trick[0][1] // 13 for x in p.hands[seat]):
                raise ValueError("Revoke in current trick")
        if (p.leader, p.trick, p.tricks) != (first.leader, first.trick, first.tricks) or set(sum(p.hands, ())) != pool:
            raise ValueError("Worlds must share public state and remaining card pool")
        if any(p.hands[s] != first.hands[s] for s in range(4) if s % 2 == declarer % 2):
            raise ValueError("Declarer and dummy must be fixed across worlds")
    # Merge identical hypotheses without losing their probability mass.
    merged = {}
    for p, w in zip(worlds, weights):
        if w:
            merged[p] = merged.get(p, 0.0) + w
    total = sum(merged.values())
    return tuple(merged), tuple(w / total for w in merged.values())


@dataclass(frozen=True)
class Policy:
    kind: str  # action, observe, terminal, dd_leaf
    card: int | None = None
    children: tuple[tuple[int, 'Policy'], ...] = ()

    def child(self, card):
        for c, p in self.children:
            if c == card:
                return p
        raise ValueError("Observation outside this policy's world support")

    def to_dict(self):
        from .core import symbol
        return dict(kind=self.kind, card=symbol(self.card) if self.card is not None else None,
                    children={symbol(c): p.to_dict() for c, p in self.children})


@dataclass(frozen=True)
class Entry:
    values: tuple[float, ...]
    policy: Policy


def pareto(entries):
    """Same support at each call. Inactive coordinates are neutral +infinity."""
    kept = []
    for e in entries:
        if any(all(a >= b for a, b in zip(k.values, e.values)) for k in kept):
            continue
        kept = [k for k in kept if not all(a >= b for a, b in zip(e.values, k.values))]
        kept.append(e)
    return tuple(kept)


class SearchLimit(RuntimeError):
    pass


@dataclass
class SearchResult:
    front: tuple[Entry, ...]
    best: Entry
    value: float
    worlds: tuple[Position, ...]
    weights: tuple[float, ...]
    executable: bool
    stats: dict


class AlphaMu:
    """Pareto-front vector search against omniscient, adversarial defenders.

    max_plies counts declarer/dummy card plays, not tricks. None searches to
    terminal. A DDS horizon is explicitly NON-executable and strategy-fused
    beyond the horizon. Budget exhaustion raises; no guessed 'exact' result.
    """
    def __init__(self, contract: Contract, objective="make", vul=False, dds=None,
                 max_nodes=500_000, max_products=2_000_000, seconds=None):
        if objective not in ("make", "tricks", "score"):
            raise ValueError("Invalid objective")
        if max_nodes < 1 or max_products < 1 or (seconds is not None and seconds <= 0):
            raise ValueError("Invalid search budget")
        self.contract, self.objective, self.vul, self.dds = contract, objective, vul, dds
        self.max_nodes, self.max_products, self.seconds = max_nodes, max_products, seconds

    def utility(self, tricks):
        if self.objective == "tricks":
            return tricks
        if self.objective == "make":
            return int(tricks >= 6 + self.contract.level)
        return score(self.contract, tricks, self.vul)

    def solve(self, worlds, weights=None, max_plies=None):
        if max_plies is not None and (type(max_plies) is not int or max_plies < 0):
            raise ValueError("max_plies must be a nonnegative integer or None")
        worlds = tuple(worlds)
        worlds, weights = validate_worlds(worlds, weights if weights is not None else [1] * len(worlds), self.contract.declarer)
        n, start = len(worlds), time.perf_counter()
        stats = dict(nodes=0, products=0, max_front=0, dds_calls=0, dds_nodes=0)
        terminal = Policy("terminal")

        def check():
            if stats['nodes'] > self.max_nodes or stats['products'] > self.max_products or (self.seconds is not None and time.perf_counter() - start > self.seconds):
                raise SearchLimit("Alpha-mu budget exhausted; no exact result returned")

        @lru_cache(None)
        def search(active, depth):
            stats['nodes'] += 1
            check()
            p = active[0][1]
            if p.done:
                v = [inf] * n
                for i, pos in active:
                    v[i] = self.utility(pos.tricks)
                return (Entry(tuple(v), terminal),)
            declaring = p.actor % 2 == self.contract.declarer % 2
            if depth == 0:
                if self.dds is None:
                    raise ValueError("A finite horizon requires a DDS evaluator")
                v = [inf] * n
                for i, pos in active:
                    scores, nodes = self.dds.solve(pos.hands, self.contract.trump, pos.leader, pos.trick)
                    stats['dds_calls'] += 1
                    stats['dds_nodes'] += nodes
                    t = max(scores.values())
                    total = pos.tricks + (t if declaring else pos.remaining_tricks - t)
                    v[i] = self.utility(total)
                return (Entry(tuple(v), Policy("dd_leaf")),)
            if declaring:
                front = ()
                for c in p.legal():
                    child = tuple((i, pos.play(c, self.contract.trump, self.contract.declarer)) for i, pos in active)
                    f = search(child, None if depth is None else depth - 1)
                    front = pareto((*front, *(Entry(e.values, Policy("action", c, ((c, e.policy),))) for e in f)))
            else:
                # One continuation per OBSERVED defender card. A world may permit
                # several such cards: worst response is taken separately in it.
                front = (Entry((inf,) * n, Policy("observe")),)
                moves = sorted({c for _, pos in active for c in pos.legal()})
                for c in moves:
                    child = tuple((i, pos.play(c, self.contract.trump, self.contract.declarer))
                                  for i, pos in active if c in pos.legal())
                    f = search(child, depth)
                    combined = []
                    for a in front:
                        for b in f:
                            stats['products'] += 1
                            check()
                            combined.append(Entry(tuple(min(x, y) for x, y in zip(a.values, b.values)),
                                                  Policy("observe", children=a.policy.children + ((c, b.policy),))))
                    front = pareto(combined)
            stats['max_front'] = max(stats['max_front'], len(front))
            return front

        try:
            front = search(tuple(enumerate(worlds)), max_plies)
            value = lambda e: sum(w * v for w, v in zip(weights, e.values))
            best = max(front, key=value)
            def complete(p):
                return p.kind != "dd_leaf" and all(complete(c) for _, c in p.children)
            stats.update(cache_hits=search.cache_info().hits, seconds=time.perf_counter() - start,
                         worlds=n, root_front=len(front))
            result = SearchResult(front, best, value(best), worlds, weights, complete(best.policy), stats)
            return result
        finally:
            search.cache_clear()


def evaluate_policy(position, policy, contract, utility):
    """Execute a policy against ALL legal defender replies, with no DDS tail."""
    if position.done:
        return utility(position.tricks)
    if position.actor % 2 == contract.declarer % 2:
        if policy.kind != "action":
            raise ValueError("Policy has no executable declarer continuation")
        return evaluate_policy(position.play(policy.card, contract.trump, contract.declarer),
                               policy.child(policy.card), contract, utility)
    if policy.kind != "observe":
        raise ValueError("Policy has no executable defensive branches")
    return min(evaluate_policy(position.play(c, contract.trump, contract.declarer),
                               policy.child(c), contract, utility) for c in position.legal())
