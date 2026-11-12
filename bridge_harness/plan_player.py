"""Plan player (research prototype): the Gen 7 player with honest playouts where Gen 7 has its tree.

Gen 7's tree values a near-best card again by two or three tricks of play from each seat's own view
and then solves double dummy. Here the card is valued by playing the hand out to trick 13 in every
layout the search solved, each seat playing from its own view (bridge_harness/plan_rollout.py), and
nothing is solved after the card except what a simulated seat solves for its own believed layout.
As with the tree, the result corrects the search's estimate instead of replacing it:

    value = the search's estimate + trust x (playout value - double-dummy value on the same layouts)

Settings live in spec['plan']['playout'], one stage or a list of them (no trick in two stages):

  from_trick, to_trick   tricks at which the stage applies (dummy must be down)
  root_margin            candidates: cards the search rates within this many tricks of its best
  root_cards             at most this many candidates
  trust                  weight on the playouts' correction
  layouts                layouts played out, drawn from the solved ones by weight; 0 = all of them
  seat                   the simulated seat: 'top', 'blend', 'draw' (the policy net's card), 'map', 'bdraw', 'map3'
                         (the solver's card for the seat's believed layout; see plan_rollout.Believer) or 'hyb', 'hyb3'
                         (the solver chooses among the net's three likeliest cards), or 'gen6': the search itself with
                         this spec's Gen 6 settings and no net plays every later card from each seat's own view. That is
                         the bot as its own simulator: far slower, so use it with few `layouts` and late tricks
  repeats                playouts per layout and card (for seats that draw)
  tricks                 0 = to the end; above 0 the playout stops after that many tricks and is solved from there
  wide                   0 = play out the layouts the search solved and correct its estimate, as above. Above 0: play out
                         about this many fresh layouts, drawn as repeated draws of the search's own, and blend instead:
                         value = (1 - trust) x the search's estimate + trust x the playouts' mean. Nothing is solved on
                         the fresh layouts, so the count can be large; the mean over many layouts also carries less of
                         the search's own sampling noise than its 32-layout estimate does.

A spec with engine 'plan' and no playout stage is a Gen 7 player. The spec's own `gen7.tree` should be
absent: the two corrections are alternatives, and if both are present the playouts correct the tree's card.
"""
import copy
from dataclasses import dataclass, fields
import random
import time

import numpy as np

from .core import Board, symbol
from .gen6 import Gen6Player, View, systematic
from .gen7 import Gen7Player, utilities
from .gen7 import player as gen7_player
from .plan_rollout import Believer, NetPlayer, Public, card_values
from .players import Decision
from .runner import play_table

ENGINE = 'plan'


@dataclass(frozen=True)
class PlayoutUse:
    from_trick: int = 3
    to_trick: int = 6
    root_margin: float = .25
    root_cards: int = 3
    trust: float = .5
    layouts: int = 0
    seat: str = 'map'
    repeats: int = 1
    tricks: int = 0
    wide: int = 0

    def __post_init__(self):
        for name in ('from_trick', 'to_trick', 'root_cards', 'layouts', 'repeats', 'tricks', 'wide'):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f'Plan playout {name} must be an integer')
        if not (1 <= self.from_trick <= self.to_trick <= 13 and 0 <= self.root_margin <= 13 and 2 <= self.root_cards <= 13
                and 0 <= self.trust <= 4 and 0 <= self.layouts <= 4096 and 1 <= self.repeats <= 64 and 0 <= self.tricks <= 13
                and 0 <= self.wide <= 8192):
            raise ValueError('Invalid plan playout settings')
        if self.seat != 'gen6':
            seat_player(None, None, self.seat, 0)


def seat_player(net, dds, kind, seed):
    """The simulated seat named by `kind` (see the module docstring)."""
    for name, belief, top in (('map', 'map', 0), ('bdraw', 'draw', 0), ('hyb', 'map', 3)):
        if kind.startswith(name) and (kind[len(name):] or '1').isdigit():
            return Believer(net, dds, belief, layouts=int(kind[len(name):] or 1), seed=seed, top=top)
    if kind in ('top', 'blend', 'draw'):
        return NetPlayer(net, kind, seed=seed)
    raise ValueError(f'Unknown simulated seat {kind!r}')


def playout_stages(block):
    if not block:
        return ()
    stages = []
    for b in [block] if isinstance(block, dict) else list(block):
        try:
            stages.append(PlayoutUse(**b))
        except TypeError as e:
            raise ValueError(f'Unknown plan playout setting: {e}') from None
    tricks = [t for s in stages for t in range(s.from_trick, s.to_trick + 1)]
    if len(tricks) != len(set(tricks)):
        raise ValueError('Plan playout stages overlap')
    return tuple(stages)


class PlanPlayer(Gen7Player):
    """Gen7Player whose near-best cards are valued again by playouts to the end of the hand."""

    def __init__(self, spec, root, reference=None):
        super().__init__(spec, root, reference)
        self.playouts = playout_stages((spec.get('plan') or {}).get('playout'))
        self.root, self.inner = root, None

    def playout_stage(self, o):
        if not o.history or o.known_hands[o.contract.dummy] is None:
            return None
        trick = len(o.history) // 4 + 1
        for s in self.playouts:
            if s.from_trick <= trick <= s.to_trick:
                return s
        return None

    def search_decision(self, o, rng, solved, weights, before, after, info):
        result = super().search_decision(o, rng, solved, weights, before, after, info)
        stage = self.playout_stage(o)
        return result if stage is None else self.playout_decision(o, rng, result, solved, weights, stage)

    def fresh_layouts(self, o, count, seed):
        """About `count` layouts for the playouts, as repeated draws of the search's own (Gen6Player.layouts, so without
        the net's reading), and their weights. A deal list short enough to be solved whole comes back as it is."""
        view = View(o)
        source = self.source(o, view)
        worlds, weights, draws = [], [], 0
        while len(worlds) < count and draws < 256:
            more, w, _ = Gen6Player.layouts(self, o, view, source, np.random.default_rng([seed % (1 << 63), draws]))
            worlds += list(more)
            weights.append(np.asarray(w, np.float64))
            draws += 1
            if source == 'list' and (not self.config.list_solve or view.count() <= self.config.list_solve):
                break
        return worlds, np.concatenate(weights) / draws

    def real_values(self, o, worlds, cards, seed):
        """[layout, card] the decider's tricks when it plays the card and Gen 6 (this spec's search, no net, no playouts)
        plays every later card of all four seats, each from its own view."""
        if self.inner is None:          # this player's own search and files, with Gen 6's methods: no net, tree or playouts
            self.inner = copy.copy(self)
            self.inner.__class__ = Gen6Player
        c = o.contract
        sign = 1 if o.controller % 2 == c.declarer % 2 else -1
        prefix = [dict(card=symbol(x)) for _, x in o.history]
        out = np.zeros((len(worlds), len(cards)))
        for n, world in enumerate(worlds):
            hands = tuple(tuple(sorted(set(world[s]) | {x for seat, x in o.history if seat == s})) for s in range(4))
            board = Board(f'playout/{seed}/{n}', hands, c, o.dealer, o.vulnerability, o.auction)
            for j, x in enumerate(cards):
                t = play_table(board, ['inner'] * 4, {'inner': self.inner}, seed=seed % (1 << 31), prefix=prefix + [dict(card=symbol(x))])
                if t['status'] != 'ok':
                    raise RuntimeError(t.get('error'))
                out[n, j] = sign * t['declarer_tricks']
        return out

    def playout_decision(self, o, rng, result, solved, weights, stage):
        """The search's decision with its near-best cards valued again by playouts. Candidates are chosen as the tree
        chooses them (Gen7Player.tree_decision), and the Decision has the same shape, its note under `gen7_tree`."""
        d, legal = result.details, list(o.legal)
        note = dict(kind='playout', consulted=False)
        w = np.asarray(weights, np.float64)
        w = w / w.sum()
        u = np.array([[row[x] for x in legal] for row in (utilities(o, values) for values, _ in solved)])      # [layout, card]
        groups = {}                 # cards the solves cannot tell apart: same suit, same result in every layout
        for j, x in enumerate(legal):
            groups.setdefault((x // 13, u[:, j].tobytes()), []).append(j)
        groups = list(groups.values())
        value = np.array([float(w @ u[:, g[0]]) for g in groups])
        best = float(value.max())
        near = [i for i in range(len(groups)) if best - value[i] <= stage.root_margin + 1e-9]
        if len(near) < 2:
            return Decision(result.card, dict(d, gen7_tree=dict(note, candidates=len(near))))
        logp = self.net.log_policy([o])[0].astype(np.float64)
        mass = {i: float(np.exp(logp[[legal[j] for j in groups[i]]]).sum()) for i in near}
        near = sorted(near, key=lambda i: (round(best - value[i], 9), -mass[i], legal[groups[i][0]]))[:stage.root_cards]
        searched = [legal[max(groups[i], key=lambda j: (logp[legal[j]], -legal[j]))] for i in near]     # each candidate's likeliest card
        worlds = self.solved_layouts
        if worlds is None or len(worlds) != len(solved):
            raise RuntimeError('The playouts were handed solves without their layouts')
        fork = random.Random()      # the playouts' draws come from a copy: the table's own random stream is as the search left it
        fork.setstate(rng.getstate())
        seed = fork.getrandbits(64)
        k = stage.layouts
        pick, share = systematic(w, k, np.random.default_rng(seed)) if k and len(worlds) > k else (np.arange(len(worlds)), w)
        real = stage.seat == 'gen6'
        who = None if real else seat_player(self.net, self.dds, stage.seat, seed)
        values_of = (lambda layouts: self.real_values(o, layouts, searched, seed)) if real else \
            (lambda layouts: card_values(o, layouts, searched, who, Public(self.net, o), stage.repeats, stage.tricks, self.dds))
        started = time.perf_counter()
        column = {x: j for j, x in enumerate(legal)}
        same = {x: float(share @ u[pick, column[x]]) for x in searched}        # plain double dummy on the solved layouts
        if stage.wide:
            fresh, fresh_w = self.fresh_layouts(o, stage.wide, seed)
            got = values_of(fresh)
            played = {x: float(fresh_w @ got[:, j]) for j, x in enumerate(searched)}
            adjusted = {i: (1 - stage.trust) * float(value[i]) + stage.trust * played[x] for i, x in zip(near, searched)}
            pick = np.arange(len(fresh))
        else:
            got = values_of([worlds[i] for i in pick])
            played = {x: float(share @ got[:, j]) for j, x in enumerate(searched)}
            adjusted = {i: float(value[i]) + stage.trust * (played[x] - same[x]) for i, x in zip(near, searched)}
        seconds = time.perf_counter() - started
        top = max(adjusted.values())
        winners = [i for i in near if top - adjusted[i] <= 1e-9]
        eligible = sorted(legal[j] for i in winners for j in groups[i])
        choice = result.card if result.card in eligible else fork.choice(eligible)
        self.before_tree = result
        note.update(consulted=True, layouts=len(pick), wide=stage.wide, seconds=seconds, net_rows=getattr(who, 'net_rows', 0), solves=getattr(who, 'solves', 0), seat=stage.seat,
                    gen6_cards=sorted(k for k, q in d['behavior_probabilities'].items() if q > 0),
                    candidates=[dict(cards=[symbol(legal[j]) for j in groups[i]], searched=symbol(x), gap=best - float(value[i]),
                                     same_layouts=same[x], tree=played[x], adjusted=adjusted[i], kept=i in winners)
                                for i, x in zip(near, searched)])
        return Decision(choice, dict(d, behavior_probabilities={symbol(x): (1 / len(eligible) if x in eligible else 0.) for x in legal},
                                     selected_probability=1 / len(eligible),
                                     selected_pimc_gap=d['estimates'][symbol(choice)]['gap_to_best'], gen7_tree=note))


PLAN_KEYS = tuple(f.name for f in fields(PlayoutUse))


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: 'plan' specs get this engine, every other spec is as before."""
    if spec.get('engine') == ENGINE:
        return PlanPlayer(spec, root, reference)
    return gen7_player(spec, root, reference)
