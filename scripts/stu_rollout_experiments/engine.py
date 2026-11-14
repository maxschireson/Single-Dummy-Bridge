"""Opt-in experiments layered over a pinned Stu runtime; never changes its source.

Recursive search here means one additional own-side information-set replan, with
fresh child posterior samples and flat continuations. It is not a full ISMCTS.
"""
import copy
import hashlib
import random
import time
from pathlib import Path

import numpy as np

from bridge_harness.core import Observation
from bridge_harness.gen7 import hidden_plays
from bridge_harness import x8_player as xp
from bridge_harness.x8_rollout import Seats
from accounting import isolated_finder, solver_totals


def row_view(rows, i):
    """Observation boundary: return only the acting controller's hand and dummy."""
    actor, controller = int(rows.actor()[i]), int(rows.controller()[i])
    known = [None] * 4
    for seat in {controller, rows.dummy}:
        known[seat] = tuple(map(int, np.flatnonzero(rows.holder[i] == seat)))
    played = np.flatnonzero(rows.order[i])
    ordered = played[np.argsort(rows.order[i, played])]
    history = tuple((int(rows.by[i, x]), int(x)) for x in ordered)
    trick = history[-rows.on_table:] if rows.on_table else ()
    o = rows.o
    return Observation(controller, actor, tuple(known), tuple(map(int, np.flatnonzero(rows.legal()[i]))),
                       history, trick, int(rows.leader[i]), rows.contract, o.dealer,
                       o.vulnerability, o.auction, int(rows.won[i]))


def view_seed(o):
    return int.from_bytes(hashlib.sha256(repr(o).encode()).digest()[:8], 'big')


class ReplanningSeats(Seats):
    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.seen_paths = set()

    def cards(self, rows, other=None):
        out, free, logp = super().cards(rows, other)
        e, stats = self.owner.experiment, self.owner.recursive_stats
        groups = {}
        for k, i in enumerate(free):
            if rows.controller()[i] % 2 != self.side:
                continue
            o = row_view(rows, int(i))
            seed = view_seed(o)
            lp = sorted((float(logp[k, x]) for x in o.legal), reverse=True)
            stats['opportunities'] += 1
            group = groups.setdefault(seed, dict(o=o, rows=[], gap=lp[0] - lp[1]))
            if group['o'] != o:
                raise RuntimeError('Observation hash collision')
            group['rows'].append((int(i), k))
        for seed, group in sorted(groups.items()):
            o, members = group['o'], group['rows']
            if seed in self.owner.recursive_cache:
                card = self.owner.recursive_cache[seed]
                stats['cache_hits'] += len(members)
            else:
                # Eligibility is an information-set property, never a hidden-layout
                # path mark. Rejected early nodes cannot consume later opportunity.
                if rows.played - len(rows.o.history) > e.get('window_plies', 8):
                    continue
                if e.get('recursive') == 'selective' and group['gap'] > e.get('logp_margin', 1.):
                    stats['gate_rejected'] = stats.get('gate_rejected', 0) + 1
                    continue
                if stats['calls'] >= e.get('max_calls', 4):
                    stats['budget_rejected'] = stats.get('budget_rejected', 0) + 1
                    continue  # cached groups later in this batch still apply
                child = self.owner.child_player()
                factory = xp.Seats
                xp.Seats = Seats  # child continuations are flat; depth is exactly one
                started = time.perf_counter()
                try:
                    result = child.choose(o, random.Random(seed))
                finally:
                    xp.Seats = factory
                card = result.card
                if card not in o.legal:
                    raise RuntimeError('Child returned an illegal card')
                self.owner.recursive_cache[seed] = card
                stats['calls'] += 1
                stats['net_rows'] += result.details.get('x8', {}).get('net_rows', 0)
                stats['child_wall_seconds'] = stats.get('child_wall_seconds', 0.) + time.perf_counter() - started
                stats.setdefault('nodes', []).append(dict(key=str(seed), ply=rows.played-len(rows.o.history),
                    rows=len(members), gap=group['gap']))
            for i, k in members:
                stats['changed'] += int(card != int(out[i]))
                stats['argmax_different'] = stats.get('argmax_different', 0) + int(card != int(np.argmax(logp[k])))
                stats['applied_rows'] = stats.get('applied_rows', 0) + 1
                out[i] = card
        return out, free, logp


class ExperimentalPlayer(xp.X8Player):
    def __init__(self, spec, root, reference=None):
        started = time.perf_counter()
        e = spec.get('rollout_experiment') or {}
        expected = e.get('implementation_sha256')
        if expected and expected != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise ValueError('Experiment implementation hash mismatch')
        super().__init__(spec, root, reference)
        self.experiment = dict(e)
        self.experiment_root = root
        self.child = None
        self.last_history_length = -1
        self.retired_solver_work = {}
        self.owns_finder = bool(e.get('isolate_claims') and self.finder is not None)
        if self.owns_finder:
            self.finder = isolated_finder(self.finder.binary, self.x8.claims.each_ms / 1000)
        self.initialization_seconds = time.perf_counter() - started

    def play_log_probabilities(self, o, view, assign, plays=None):
        if not self.experiment.get('reader_identity') or not getattr(self.net, 'vocab', None):
            return super().play_log_probabilities(o, view, assign, plays)
        plays = hidden_plays(o, self.g7.play_lead) if plays is None else plays
        logp = np.zeros((len(plays), len(assign)))
        options = np.ones(logp.shape, np.int64)
        names = self.x8.names
        own = names.get('self', '')
        other = names.get(self.opponent_id or '', names.get('*', ''))
        original = self.net.who
        try:
            for mine in (True, False):
                at = [i for i, (_, _, chooser) in enumerate(plays) if (chooser % 2 == o.controller % 2) == mine]
                if not at:
                    continue
                self.net.who = (own, other) if mine else (other, names.get('they_see', own))
                lp, op = super().play_log_probabilities(o, view, assign, [plays[i] for i in at])
                logp[at], options[at] = lp, op
        finally:
            self.net.who = original
        return logp, options

    def child_player(self):
        if self.child is None:
            spec = copy.deepcopy(self.spec)
            spec['id'] += '-inner'
            spec['rollout_experiment'] = {k: v for k, v in self.experiment.items()
                                          if k in ('reader_identity', 'isolate_claims', 'implementation_sha256', 'version')}
            spec['rollout_experiment']['child_search'] = True
            x8 = spec['x8']
            layouts = self.experiment.get('inner_layouts', 8)
            for stage in [*x8['stages'], x8['lead']]:
                stage.update(layouts=layouts, first=layouts, cards=2, race=0., horizon=0)
            x8['capture'] = dict(level=0, forks=0, audit='features')
            self.child = ExperimentalPlayer(spec, self.experiment_root)
            self.child.meet(self.opponent_id)
        return self.child

    def choose(self, o, rng):
        # Reset at each actual room's opening lead, preventing cross-room warming.
        started = time.perf_counter()
        if self.owns_finder and (len(o.history) <= self.last_history_length or self.experiment.get('child_search')):
            self.finder.close()
            if self.child is not None:
                self.child.close()
            self.retired_solver_work = solver_totals(self)
            self.finder = isolated_finder(self.finder.binary, self.x8.claims.each_ms / 1000)
            if self.child is not None:
                self.child = None
        self.last_history_length = len(o.history)
        self.recursive_stats = dict(opportunities=0, calls=0, cache_hits=0, changed=0, net_rows=0)
        self.recursive_cache = {}
        before = solver_totals(self)
        wall, cpu = started, time.process_time()
        result = super().choose(o, rng)
        elapsed, worker = time.perf_counter() - wall, time.process_time() - cpu
        after = solver_totals(self)
        work = {k: after[k] - before[k] for k in after}
        work.update(wall_seconds=elapsed, worker_cpu_seconds=worker,
                    inclusive_cpu_seconds=worker + work['solver_cpu_seconds'],
                    initialization_seconds=self.initialization_seconds,
                    precision=getattr(self.net, 'precision', 'unknown'),
                    rollout_precision=getattr(self.rollout_net, 'precision', 'unknown'))
        self.initialization_seconds = 0.
        result.details['experiment_work'] = work
        if self.experiment.get('recursive'):
            result.details['recursive'] = dict(self.recursive_stats)
        return result

    def roll(self, *args, **kwargs):
        if not self.experiment.get('recursive'):
            return super().roll(*args, **kwargs)
        before = xp.Seats
        xp.Seats = lambda *a, **kw: ReplanningSeats(*a, owner=self, **kw)
        try:
            return super().roll(*args, **kwargs)
        finally:
            xp.Seats = before

    def close(self):
        if self.child is not None:
            self.child.close()
        if self.owns_finder:
            self.finder.close()
        super().close()
