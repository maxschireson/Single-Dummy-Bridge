"""Nested-budget scoring for a future generation; no live collector changes.

The existing PIMC/selector implementation reduces each prefix. Only sampling and
DDS work are shared. A lower-budget selector never receives the larger prefix.
One instance belongs to one worker, as with its underlying DDS context.
"""
from copy import copy
from dataclasses import dataclass
import random

from .players import Decision, PIMCPlayer


@dataclass
class MultiScoreResult:
    decisions: dict
    rng_states: dict
    shared_work: dict


class _PrefixSampler:
    def __init__(self, worlds, end_state):
        self.worlds, self.end_state, self.index = worlds, end_state, 0

    def draw(self, rng):
        world = self.worlds[self.index]
        self.index += 1
        if self.index == len(self.worlds):
            rng.setstate(self.end_state)
        return world


class _SolvedPrefix:
    """Read-only DDS answers: replaying a reduction performs no solver work."""
    def __init__(self, worlds, solved):
        self.worlds, self.solved = worlds, solved

    def cache_stats(self):
        return dict(native_solves=0, hits=0, duplicate_worlds=0)

    def solve_batch(self, worlds, *args, **kwargs):
        if worlds != self.worlds:
            raise ValueError('Prefix replay sampled different worlds')
        return [(dict(values), 0) for values, _ in self.solved]


class MultiScorePlayer:
    """Wrap a batch PIMC-family player, owning its close() lifecycle.

    choose_all returns all budget-specific decisions and post-choice RNG states;
    it advances the caller RNG exactly as standalone active_samples would.
    choose returns that active decision with JSON-safe alternative-score logs.
    Neither method follows alternative trajectories or creates reward labels.
    """
    def __init__(self, player, budgets=(16, 32, 64), active_samples=32):
        budgets = tuple(budgets)
        if not budgets or any(type(n) is not int or n < 1 for n in budgets):
            raise ValueError('Budgets must be positive integers')
        if tuple(sorted(set(budgets))) != budgets:
            raise ValueError('Budgets must be sorted and unique')
        if type(active_samples) is not int or active_samples not in budgets:
            raise ValueError('Active sample count must be a scored budget')
        if not isinstance(player, PIMCPlayer) or not player.batch:
            raise ValueError('Requires a batch PIMC-family player')
        self.player, self.budgets, self.samples = player, budgets, active_samples

    def close(self):
        self.player.close()

    def choose_all(self, o, rng):
        initial = rng.getstate()
        worlds, solved, checkpoints = [], [], {}
        work = dict(dds_calls=0, dds_native_solves=0, dds_cache_hits=0,
                    dds_duplicate_worlds=0, dds_nodes=0)
        if len(o.legal) != 1:
            draws = random.Random(); draws.setstate(initial)
            sampler = self.player.sampler_factory(o)
            for n in range(1, self.budgets[-1] + 1):
                worlds.append(sampler.draw(draws))
                if n in self.budgets:
                    checkpoints[n] = draws.getstate()
            before = self.player.dds.cache_stats()
            solved = self.player.dds.solve_batch(
                worlds, o.contract.trump, o.leader, o.trick,
                fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
            if len(solved) != len(worlds):
                raise ValueError('DDS returned wrong number of worlds')
            after = self.player.dds.cache_stats()
            work = dict(dds_calls=len(worlds),
                        dds_native_solves=after['native_solves']-before['native_solves'],
                        dds_cache_hits=after['hits']-before['hits'],
                        dds_duplicate_worlds=after['duplicate_worlds']-before['duplicate_worlds'],
                        dds_nodes=sum(n for _, n in solved))
        decisions, states = {}, {}
        for n in self.budgets:
            # Copies share read-only weights, but never change the original player.
            branch = copy(self.player); branch.samples = n
            branch.dds = _SolvedPrefix(worlds[:n], solved[:n])
            branch.sampler_factory = lambda observation, n=n: _PrefixSampler(worlds[:n], checkpoints[n])
            local = random.Random(); local.setstate(initial)
            decision = branch.choose(o, local)
            decision.details.update(dds_calls=0, work_accounting='shared-multiscore', scored_budget=n)
            decisions[n], states[n] = decision, local.getstate()
        rng.setstate(states[self.samples])
        return MultiScoreResult(decisions, states, work)

    def choose(self, o, rng):
        result = self.choose_all(o, rng)
        active = result.decisions[self.samples]
        details = dict(active.details)
        details.update(result.shared_work)
        details['work_accounting'] = 'physical-work-once'
        details['multi_score'] = dict(schema='nested-pimc-prefix-v1',
            budgets=list(self.budgets), active_samples=self.samples,
            decisions={str(n): dict(card=d.card, details=d.details) for n, d in result.decisions.items()},
            shared_work=result.shared_work,
            interpretation='Same public state; alternative scores are not completed branches or reward labels.')
        return Decision(active.card, details)


def make_multiscore_player(belief=None, policy=None, belief_kind='public',
                          reference_policy=None, budgets=(16, 32, 64), active_samples=32,
                          near_tie=.125, exploration=0.):
    """Manifest-compatible factory for public/auction belief and IMP/old selectors.

    Artifact paths can use the registry's $artifact: syntax. All budgets use the
    same weights; sample count is passed separately to the auction-aware net.
    """
    import math
    from .mixed_arena import ArenaPlayer
    if belief_kind not in ('public', 'auction'):
        raise ValueError('Unknown belief kind')
    if not math.isfinite(exploration) or not 0 <= exploration <= 1:
        raise ValueError('Exploration must lie in [0,1]')
    spec = dict(id='multiscore', belief=belief, policy=policy,
                belief_kind=belief_kind, samples=active_samples,
                near_tie=near_tie, exploration=exploration)
    reference = dict(policy=reference_policy) if reference_policy else None
    player = ArenaPlayer(spec, '.', reference)
    try:
        return MultiScorePlayer(player, budgets, active_samples)
    except BaseException:
        player.close()
        raise
