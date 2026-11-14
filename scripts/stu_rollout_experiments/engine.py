"""Opt-in experiments layered over a pinned Stu runtime; never changes its source.

Recursive search here means one additional own-side information-set replan, with
fresh child posterior samples and flat continuations. It is not a full ISMCTS.
"""
import copy
import hashlib
import random
from dataclasses import replace

import numpy as np

from bridge_harness.core import Observation
from bridge_harness.gen7 import hidden_plays
from bridge_harness import x8_player as xp
from bridge_harness.x8_rollout import Seats


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
        if rows.played - len(rows.o.history) > e.get('window_plies', 8):
            return out, free, logp
        opportunities = []
        for k, i in enumerate(free):
            if rows.controller()[i] % 2 != self.side:
                continue  # first prototype models replanning by our own partnership
            # Private simulator bookkeeping only; never a child input or priority.
            original = np.where(rows.holder[i] >= 0, rows.holder[i], rows.by[i])
            path = (original.tobytes(), int(np.flatnonzero(rows.order[i] == len(rows.o.history) + 1)[0]))
            if path in self.seen_paths:
                continue
            self.seen_paths.add(path)
            o = row_view(rows, int(i))
            seed = view_seed(o)
            lp = sorted((float(logp[k, x]) for x in o.legal), reverse=True)
            # Raw policy uncertainty is a screen, not an established learning frontier.
            uncertain = lp[0] - lp[1] <= e.get('logp_margin', 1.0)
            stats['opportunities'] += 1
            if e.get('recursive') == 'selective' and not uncertain:
                continue
            opportunities.append((seed, int(i), o))
        for seed, i, o in sorted(opportunities, key=lambda q: q[0]):
            if seed in self.owner.recursive_cache:
                out[i] = self.owner.recursive_cache[seed]
                stats['cache_hits'] += 1
                continue
            if stats['calls'] >= e.get('max_calls', 4):
                break
            child = self.owner.child_player()
            factory = xp.Seats
            xp.Seats = Seats  # child continuations are flat; depth is exactly one
            try:
                result = child.choose(o, random.Random(seed))
            finally:
                xp.Seats = factory
            out[i] = result.card
            self.owner.recursive_cache[seed] = result.card
            stats['calls'] += 1
            stats['net_rows'] += result.details.get('x8', {}).get('net_rows', 0)
            stats['changed'] += int(result.card != int(np.argmax(logp[list(free).index(i)])))
        return out, free, logp


class ExperimentalPlayer(xp.X8Player):
    def __init__(self, spec, root, reference=None):
        super().__init__(spec, root, reference)
        self.experiment = dict(spec.get('rollout_experiment') or {})
        self.experiment_root = root
        self.child = None

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
            spec['rollout_experiment'] = dict(reader_identity=self.experiment.get('reader_identity', False))
            x8 = spec['x8']
            layouts = self.experiment.get('inner_layouts', 8)
            for stage in [*x8['stages'], x8['lead']]:
                stage.update(layouts=layouts, first=layouts, cards=2, race=0., horizon=0)
            x8['capture'] = dict(level=0, forks=0, audit='features')
            self.child = ExperimentalPlayer(spec, self.experiment_root)
            self.child.meet(self.opponent_id)
        return self.child

    def choose(self, o, rng):
        self.recursive_stats = dict(opportunities=0, calls=0, cache_hits=0, changed=0, net_rows=0)
        self.recursive_cache = {}
        result = super().choose(o, rng)
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
        super().close()
