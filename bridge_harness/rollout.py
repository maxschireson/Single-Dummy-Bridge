# SPDX-License-Identifier: Apache-2.0
"""Executable policy search under fixed, information-limited defender models.

All policy calls receive Observation only. Each simulated defender constructs its
own perspective; South's particles are never handed to West as West's beliefs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
import random
import time

from .core import Board, Game, Observation, vulnerable
from .players import Decision, GreedyPlayer, PIMCPlayer
from .sampling import Sampler
from .strategy import AlphaMu, Position, SearchLimit, validate_worlds


def observation_at(p, history, template):
    c = template.contract
    actor = p.actor
    controller = c.declarer if actor == c.dummy else actor
    known = [None] * 4
    known[controller] = p.hands[controller]
    if history:
        known[c.dummy] = p.hands[c.dummy]
    return Observation(controller, actor, tuple(known), p.legal(), history, p.trick,
                       p.leader, c, template.dealer, template.vulnerability,
                       template.auction, p.tricks)


class ViewPolicy:
    """Deterministic given an allowed view and an independent policy seed."""
    def __init__(self, spec="greedy", samples=2, objective="score", seed=1):
        if spec not in ("greedy", "pimc"):
            raise ValueError("Supported continuation/model policies: greedy, pimc")
        self.spec, self.seed = spec, seed
        self.player = GreedyPlayer() if spec == "greedy" else PIMCPlayer(samples, objective)
        self.cache = {}
        self.calls = self.dds_calls = 0

    def choose(self, o):
        if o not in self.cache:
            # In particular, the seed contains no world ID, hidden hand, or outer
            # sampled layout. Same view => same action, even in different worlds.
            seed = int.from_bytes(hashlib.sha256(repr((self.seed, o)).encode()).digest(), "big")
            d = self.player.choose(o, random.Random(seed))
            self.cache[o] = d.card
            self.calls += 1
            self.dds_calls += d.details.get("dds_calls", 0)
        return self.cache[o]

    def close(self):
        if hasattr(self.player, 'close'):
            self.player.close()


@dataclass
class ContingentPlan:
    actions: dict[Observation, int]
    fallback: ViewPolicy
    value: float
    estimates: dict[int, float]
    stats: dict

    def choose(self, o):
        return self.actions[o] if o in self.actions else self.fallback.choose(o)


def execute_plan(plan, world, root, defenders, utility):
    """Realize the exact advertised policy including its unsearched tail."""
    p, history = world, root.history
    while not p.done:
        o = observation_at(p, history, root)
        c = plan.choose(o) if p.actor % 2 == root.contract.declarer % 2 else defenders.choose(o)
        history += ((p.actor, c),)
        p = p.play(c, root.contract.trump, root.contract.declarer)
    return utility(p.tricks)


class PolicyPlanner:
    """Finite declarer decision prefix; full legal rollouts beyond its horizon.

    Fixed deterministic opponents make scalar conditional expectations sufficient.
    This is separate from adversarial alpha-mu's Pareto backups. It optimizes the
    supplied finite sample/model, not all possible deals or opponents.
    """
    def __init__(self, fallback, defenders, decisions=2, max_nodes=100_000):
        if decisions < 1 or max_nodes < 1:
            raise ValueError("Invalid planner budget")
        self.fallback, self.defenders = fallback, defenders
        self.decisions, self.max_nodes = decisions, max_nodes

    def plan(self, o, worlds, weights=None, objective="score"):
        if o.controller != o.contract.declarer:
            raise ValueError("Policy planner currently supports declarer only")
        worlds = tuple(worlds)
        worlds, weights = validate_worlds(worlds, weights if weights is not None else [1] * len(worlds), o.contract.declarer)
        for p in worlds:
            # Validate the entire public history, including earlier voids. These
            # are hypothetical layouts, never the simulator's actual board.
            original = tuple(tuple(sorted(p.hands[s] + tuple(c for seat, c in o.history if seat == s))) for s in range(4))
            game = Game(Board("hypothesis", original, o.contract, o.dealer, o.vulnerability, o.auction))
            for seat, c in o.history:
                if game.actor != seat:
                    raise ValueError("Invalid public history seating")
                game.play(c)
            if game.observation() != o or observation_at(p, o.history, o) != o:
                raise ValueError("World inconsistent with root observation")
        utility = AlphaMu(o.contract, objective, vulnerable(o.vulnerability, o.contract.declarer)).utility
        stats = dict(nodes=0, rollouts=0, policy_nodes=0)
        started = time.perf_counter()
        calls_before = self.fallback.calls + self.defenders.calls
        dds_before = self.fallback.dds_calls + self.defenders.dds_calls
        root_estimates = {}

        def search(rows, history, left):
            stats['nodes'] += 1
            if stats['nodes'] > self.max_nodes:
                raise SearchLimit("Policy planner budget exhausted")
            p = rows[0][1]
            if p.done:
                return sum(w * utility(s.tricks) for w, s in rows), {}
            current = observation_at(p, history, o)
            if p.actor % 2 == o.contract.declarer % 2:
                if left == 0:
                    tail = ContingentPlan({}, self.fallback, 0, {}, {})
                    stats['rollouts'] += len(rows)
                    return sum(w * execute_plan(tail, s, replace(o, history=history), self.defenders, utility)
                               for w, s in rows), {}
                best = None
                for c in p.legal():
                    next_rows = tuple((w, s.play(c, o.contract.trump, o.contract.declarer)) for w, s in rows)
                    val, actions = search(next_rows, history + ((p.actor, c),), left - int(len(p.legal()) > 1))
                    if history == o.history:
                        root_estimates[c] = val
                    if best is None or val > best[0]:
                        best = val, {**actions, current: c}
                return best
            groups = defaultdict(list)
            for w, s in rows:
                c = self.defenders.choose(observation_at(s, history, o))
                groups[c].append((w, s.play(c, o.contract.trump, o.contract.declarer)))
            value, actions = 0, {}
            for c, next_rows in sorted(groups.items()):
                val, branch = search(tuple(next_rows), history + ((p.actor, c),), left)
                value += val
                actions.update(branch)
            return value, actions

        value, actions = search(tuple(zip(weights, worlds)), o.history, self.decisions)
        stats.update(seconds=time.perf_counter() - started, policy_nodes=len(actions),
                     worlds=len(worlds), decisions=self.decisions,
                     continuation=self.fallback.spec, defender_model=self.defenders.spec,
                     policy_calls=self.fallback.calls + self.defenders.calls - calls_before,
                     dds_calls=self.fallback.dds_calls + self.defenders.dds_calls - dds_before)
        return ContingentPlan(actions, self.fallback, value, root_estimates, stats)


class StrategyPlayer:
    """Plan once at first nonforced declarer choice and execute it to completion.

    No silent replanning: unseen observations use the specified fallback. A table
    reset starts a new plan. This keeps advertised values tied to executed policy.
    """
    def __init__(self, samples=32, objective="score", decisions=2, continuation="greedy", model="greedy", policy_samples=2):
        if samples < 1:
            raise ValueError("Need at least one sample")
        self.samples, self.objective, self.decisions = samples, objective, decisions
        self.fallback = ViewPolicy(continuation, policy_samples, objective, seed=91)
        self.defenders = ViewPolicy(model, policy_samples, objective, seed=92)
        self.reset()

    def reset(self):
        self.plan = None
        self.fallback.cache.clear()
        self.defenders.cache.clear()

    def close(self):
        self.fallback.close()
        self.defenders.close()

    def choose(self, o, rng):
        if o.controller != o.contract.declarer:
            raise ValueError("strategy is declarer-only; use another common defender")
        if self.plan is None and len(o.legal) == 1:
            return Decision(o.legal[0], dict(forced=True))
        details = {}
        dds_before = self.fallback.dds_calls + self.defenders.dds_calls
        if self.plan is None:
            sampler = Sampler(o)
            worlds = [Position(sampler.draw(rng), o.leader, o.trick, o.declarer_tricks) for _ in range(self.samples)]
            self.plan = PolicyPlanner(self.fallback, self.defenders, self.decisions).plan(o, worlds, objective=self.objective)
            from .core import symbol
            details = dict(samples=self.samples, strategy_value=self.plan.value,
                           strategy_estimates={symbol(c): v for c, v in self.plan.estimates.items()},
                           strategy_search=self.plan.stats, value_kind="executable_policy_against_fixed_model")
        details['strategy_action'] = "searched" if o in self.plan.actions else "continuation"
        c = self.plan.choose(o)
        details["dds_calls"] = self.fallback.dds_calls + self.defenders.dds_calls - dds_before
        return Decision(c, details)


class AlphaMuPlayer:
    """PIMC earlier; exact, committed alpha-mu policies in small sampled endings."""
    rng_stream = "pimc"  # couple earlier sampling/ties to the PIMC ablation

    def __init__(self, samples=32, objective="score", ending_cards=3, seconds=2.0):
        self.pimc = PIMCPlayer(samples, objective)
        self.samples, self.objective, self.ending_cards, self.seconds = samples, objective, ending_cards, seconds
        self.reset()

    def reset(self):
        self.policy = None
        self.cursor = ()
        self.disabled = False

    def close(self):
        self.pimc.close()

    def choose(self, o, rng):
        if o.controller != o.contract.declarer:
            raise ValueError("alphamu is declarer-only")
        details = {}
        if self.policy is not None:
            try:
                if o.history[:len(self.cursor)] != self.cursor:
                    raise ValueError("History changed")
                for _, c in o.history[len(self.cursor):]:
                    if self.policy.kind == "action" and c != self.policy.card:
                        raise ValueError("Policy action changed")
                    self.policy = self.policy.child(c)
                self.cursor = o.history
                if self.policy.kind != "action" or self.policy.card not in o.legal:
                    raise ValueError("Policy outside supported state")
                return Decision(self.policy.card, dict(strategy_action="alpha_mu_policy"))
            except ValueError:
                self.policy = None
                details['alpha_mu_fallback'] = "observation_outside_sample_support"
        if len(o.legal) > 1 and max(13 - sum(s == seat for s, _ in o.history) for seat in range(4)) <= self.ending_cards and not self.disabled:
            rng_state = rng.getstate()
            sampler = Sampler(o)
            worlds = [Position(sampler.draw(rng), o.leader, o.trick, o.declarer_tricks) for _ in range(self.samples)]
            solver = AlphaMu(o.contract, self.objective, vulnerable(o.vulnerability, o.contract.declarer),
                             max_nodes=100_000, seconds=self.seconds)
            try:
                result = solver.solve(worlds)
                self.policy, self.cursor = result.best.policy, o.history
                return Decision(self.policy.card, dict(**details, strategy_value=result.value,
                    strategy_search=result.stats, value_kind="exact_sample_omniscient_defence",
                    strategy_action="alpha_mu_plan"))
            except SearchLimit:
                rng.setstate(rng_state)
                self.disabled = True
                details['alpha_mu_fallback'] = "budget_exhausted"
        d = self.pimc.choose(o, rng)
        return Decision(d.card, {**d.details, **details})


class ContinuationPlayer:
    """Matched control: execute exactly the strategy planner's fallback policy."""
    def __init__(self, spec="greedy", samples=2, objective="score"):
        self.policy = ViewPolicy(spec, samples, objective, seed=91)

    def reset(self):
        self.policy.cache.clear()

    def close(self):
        self.policy.close()

    def choose(self, o, rng):
        before = self.policy.dds_calls
        c = self.policy.choose(o)
        return Decision(c, dict(continuation_control=self.policy.spec, dds_calls=self.policy.dds_calls - before))
