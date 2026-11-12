"""Gen7 card play (prototype): the Gen6 search, reading the Gen7 policy net.

Everything Gen6 does with the auction is unchanged: layouts still come from the lead net, the
hand-fit scorer and the deal list, and DDS still ranks the cards. The policy net (gen7_net.py,
trained to predict Gen6's own card from one seat's view) is read in three places:

  1. Play weights.  From the trick where every card-fit layout is listed, each layout's scorer
     weight is multiplied by how likely the hidden seats' plays so far were if that layout were
     true: the product, over every past card chosen by a seat the decider cannot see, of the
     net's probability of that card given what that seat saw in that layout (its own hand,
     dummy, the play to that point), raised to `play_weight`. A defender's hidden choosers are
     partner and declarer (declarer also chose dummy's cards); declarer's are both defenders.
     The list holds every layout, so this is the exact posterior under the net, tempered.
  2. Ties.          Among exactly tied cards the net's most probable card is played, in place
                    of the Gen5 policy net.
  3. No search.     Tricks before `search_from_trick` are played from the net alone. Meant for
                    fast data tables (the opening lead and tricks 1-2 are about 90% of Gen6's
                    search time); those cards carry no search estimates and are not training
                    examples.

  4. Tree search.   From the tricks named in `tree`, the cards the search rates within
                    `root_margin` of its best are valued again by a few tricks of play from
                    each seat's own view (gen7_tree.py), on a few of the same layouts. A card's
                    value becomes the search's estimate plus `trust` times what the tree changed
                    on those layouts (tree value minus plain double dummy on them), and the best
                    of those cards is played. Cards the solves cannot tell apart (same suit, same
                    result in every layout) are one candidate. Every number is a setting; with no
                    `tree` entry the tree is never consulted.
                    With `tree_audit`, an audited bot names as its reference card the card it
                    would have played without the tree, so the collector's ordinary audit forks
                    (fork_audit.collect_board) play that card out from the same position whenever
                    the two differ: the tree's choices are scored by real play, table against table.

With play_weight 0, tie_break 'gen5', search_from_trick 1 and no tree the player is Gen6, card for
card and draw for draw (tested). So it is with a tree whose `trust` is 0 or whose horizon is 0.

A hypothetical seat's view is built from the decider's Observation and the layout only
(`past_view`); the test suite checks it against the Observation the game itself would have
given that seat.
"""
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
import random
import time

import numpy as np

from .core import Observation, card, symbol, winner
from .gen6 import POLICY_SAMPLE_RANGE, Gen6Player, View, _effective, systematic
from .gen6 import player as gen6_player
from .gen7_net import INPUTS, PolicyNet
from .gen7_tree import OverBudget, Tree, TreeConfig, stake as trick_stake
from .players import Decision

ENGINE = 'gen7'
BIT = np.uint64(1) << np.arange(52, dtype=np.uint64)
SUIT = np.arange(52)[None, :] // 13 == np.arange(4)[:, None]


@dataclass(frozen=True)
class Gen7Config:
    play_weight: float = .5         # exponent on the net's probability of each observed play; 0 = Gen6's weights
    play_floor: float = .05         # each play's probability is mixed with this share of uniform over the legal cards
    play_max_layouts: int = 1024    # a longer deal list is resampled by scorer weight to this many before the net scores it
    play_lead: bool = True          # the opening lead counts as a play
    tie_break: str = 'net'          # among exactly tied cards: 'net' | 'gen5' (the spec's policy net, as Gen6)
    search_from_trick: int = 1      # earlier tricks are played from the net without search; 1 = always search
    net_sample: bool = False        # unsearched cards: draw from the net's policy instead of taking its top card
    tree_audit: bool = True         # where the tree was consulted, the audit's reference card is the card played without it

    def __post_init__(self):
        if self.tie_break not in ('net', 'gen5') or not 0 <= self.play_weight <= 4 or not 0 <= self.play_floor < 1 \
                or not 1 <= self.search_from_trick <= 14 or not 1 <= self.play_max_layouts <= 100000:
            raise ValueError('Invalid Gen7 settings')


@dataclass(frozen=True)
class TreeUse:
    """One stage of spec['gen7']['tree']: at which tricks the tree search is consulted and how its answer is used.
    Every other key of a stage is a setting of the search itself (gen7_tree.TreeConfig: tricks, breadth, mass,
    layouts, reply, own, ...)."""
    from_trick: int = 3         # first trick at which this stage applies; the tree needs dummy, so never the opening lead
    to_trick: int = 13          # last trick at which it applies
    root_margin: float = .125   # candidates: cards the Gen6 search rates within this many tricks of its best
    root_cards: int = 3         # at most this many candidates, best-rated first (level ones: the net's likeliest first)
    trust: float = 1.           # value = the search's estimate + trust x (tree value - double-dummy value on the tree's layouts)
    max_solves: int = 0         # a decision whose tree needs more layout solves than this keeps the search's card; 0 = no limit
    search: TreeConfig = field(default_factory=TreeConfig)

    def __post_init__(self):
        for name in ('from_trick', 'to_trick', 'root_cards', 'max_solves'):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f'Gen7 tree {name} must be an integer')
        if not (1 <= self.from_trick <= self.to_trick <= 13 and 0 <= self.root_margin <= 13 and 2 <= self.root_cards <= 13
                and 0 <= self.trust <= 4 and self.max_solves >= 0):
            raise ValueError('Invalid Gen7 tree settings')


USE_KEYS = tuple(f.name for f in fields(TreeUse) if f.name != 'search')


def tree_stages(block):
    """spec['gen7']['tree'] -> (TreeUse, ...). One stage (a dict) or a list of them; none when absent or empty.
    No trick may belong to two stages."""
    if not block:
        return ()
    stages = []
    for b in [block] if isinstance(block, dict) else list(block):
        if not isinstance(b, dict):
            raise ValueError('A Gen7 tree stage is a mapping of settings')
        try:
            stages.append(TreeUse(**{k: v for k, v in b.items() if k in USE_KEYS},
                                  search=TreeConfig(**{k: v for k, v in b.items() if k not in USE_KEYS})))
        except TypeError as e:
            raise ValueError(f'Unknown Gen7 tree setting: {e}') from None
    tricks = [t for s in stages for t in range(s.from_trick, s.to_trick + 1)]
    if len(tricks) != len(set(tricks)):
        raise ValueError('Gen7 tree stages overlap')
    return tuple(stages)


def gen7_settings(block):
    """spec['gen7'] -> (Gen7Config, tree stages)."""
    block = dict(block or {})
    tree = block.pop('tree', None)
    return Gen7Config(**block), tree_stages(tree)


def resolved(block):
    """spec['gen7'] with every setting written out, defaults included: what a manifest should pin."""
    config, stages = gen7_settings(block)
    out = asdict(config)
    if stages:
        out['tree'] = [dict({k: getattr(s, k) for k in USE_KEYS}, **asdict(s.search)) for s in stages]
    return out


def utilities(o, values):
    """Per legal card, the deciding side's final tricks (negated for the defence), from one layout's solve."""
    declaring = o.actor % 2 == o.contract.declarer % 2
    remaining = 13 - len(o.history) // 4
    out = {}
    for c, t in values.items():
        total = o.declarer_tricks + (t if declaring else remaining - t)
        out[c] = total if declaring else -total
    return out


def hidden_plays(o, lead=True):
    """Past plays chosen by a seat whose hand the controller cannot see: (history index, seat, chooser)."""
    c = o.contract
    out = []
    for i, (seat, _) in enumerate(o.history):
        chooser = c.declarer if seat == c.dummy else seat
        if chooser != o.controller and (i or lead):
            out.append((i, seat, chooser))
    return out


def floored(logp, options, floor):
    """log of the probability mixed with `floor` of uniform over the legal cards; 0 where the card was forced."""
    return np.where(options > 1, np.log((1 - floor) * np.exp(logp) + floor / np.maximum(options, 1)), 0.)


def past_view(o, i, hand=()):
    """The Observation the chooser of play i had, if it then held `hand`.

    Everything else is public and comes from `o`: the play before i, dummy as it then was, the
    auction. With hand=() it is the part of that view which is the same in every layout.
    """
    c = o.contract
    seat = o.history[i][0]
    chooser = c.declarer if seat == c.dummy else seat
    start = i - i % 4
    trick = tuple(o.history[start:i])
    won = sum(winner(o.history[t:t + 4], c.trump) % 2 == c.declarer % 2 for t in range(0, start, 4))
    known = [None] * 4
    known[chooser] = tuple(sorted(hand))
    if i:                                           # dummy goes down after the opening lead
        known[c.dummy] = tuple(sorted(set(o.known_hands[c.dummy]) | {x for s, x in o.history[i:] if s == c.dummy}))
    cards = known[seat]
    follow = [x for x in cards if x // 13 == trick[0][1] // 13] if trick else []
    return Observation(chooser, seat, tuple(known), tuple(follow or cards), tuple(o.history[:i]), trick,
                       trick[0][0] if trick else seat, c, o.dealer, o.vulnerability, o.auction, won)


class Gen7Player(Gen6Player):
    """Gen6Player whose deal-list weights, tie-breaks and (optionally) early tricks read the Gen7 net."""

    def __init__(self, spec, root, reference=None):
        super().__init__(spec, root, reference)
        self.g7, self.stages = gen7_settings(spec.get('gen7'))
        self.net = PolicyNet(Path(root) / spec['gen7_policy'], self.scorer)
        self.play_cache = (None, {})
        self.net_rows = 0
        self.solved_layouts = None      # the layouts of the decision in hand, for the tree
        self.before_tree = None         # the search's own decision, when the tree was consulted on it
        self.repliers = {}

    # ---- how likely was the play so far, layout by layout --------------------------------
    def held_then(self, o, view, assign, i, chooser):
        """[layouts, 52] the cards `chooser` held just before play i: its cards in the layout plus what it has played since."""
        held = np.zeros((len(assign), 52), bool)
        held[:, view.unseen] = assign == view.hidden.index(chooser)
        held[:, [x for s, x in o.history[i:] if s == chooser]] = True
        return held

    def play_arrays(self, o, i, seat, chooser, held):
        """Net inputs for the chooser's view at play i in each layout (one row per row of `held`)."""
        base = self.net.encode(past_view(o, i))
        n = len(held)
        batch = {k: np.broadcast_to(base[k], (n, *base[k].shape)) for k in INPUTS}
        state = batch['state'].copy()
        state[held] = 1
        batch['state'] = state
        if seat == chooser:                         # a card from the hidden hand itself: follow suit if it could
            if i % 4:
                in_suit = held & SUIT[o.history[i - i % 4][1] // 13]
                batch['legal'] = np.where(in_suit.any(axis=1)[:, None], in_suit, held)
            else:
                batch['legal'] = held
        return batch

    def play_log_probabilities(self, o, view, assign, plays=None):
        """([plays, layouts] the net's log-probability of each hidden chooser's past play, given what that seat saw in
        that layout; [plays, layouts] how many legal cards it had). A forced card scores 0."""
        plays = hidden_plays(o, self.g7.play_lead) if plays is None else plays
        c = o.contract
        ident = (o.auction, o.dealer, o.vulnerability, c, o.original_hand(c.dummy))
        if self.play_cache[0] != ident:
            self.play_cache = (ident, {})
        cache = self.play_cache[1]
        logp, options = np.zeros((len(plays), len(assign))), np.ones((len(plays), len(assign)), np.int64)
        for row, (i, seat, chooser) in enumerate(plays):
            played = o.history[i][1]
            held = self.held_then(o, view, assign, i, chooser)
            masks = held.astype(np.uint64) @ BIT
            prefix = tuple(o.history[:i + 1])
            keys, values, counts = cache[i][1:] if i in cache and cache[i][0] == prefix else \
                (np.zeros(0, np.uint64), np.zeros(0), np.zeros(0, np.int64))
            where = np.searchsorted(keys, masks).clip(max=max(0, len(keys) - 1))
            known = keys[where] == masks if len(keys) else np.zeros(len(masks), bool)
            logp[row, known], options[row, known] = values[where[known]], counts[where[known]]
            if not known.all():
                batch = self.play_arrays(o, i, seat, chooser, held[~known])
                legal = np.asarray(batch['legal'])
                if not legal[:, played].all():
                    raise RuntimeError('A listed layout makes an observed play illegal')
                count = legal.sum(axis=1)
                fresh = np.zeros(len(count))
                choice = count > 1
                if choice.any():
                    fresh[choice] = self.net.log_policy_arrays({k: batch[k][choice] for k in INPUTS})[:, played]
                    self.net_rows += int(choice.sum())
                logp[row, ~known], options[row, ~known] = fresh, count
                keys, values, counts = np.concatenate([keys, masks[~known]]), np.concatenate([values, fresh]), np.concatenate([counts, count])
                order = np.argsort(keys)
                cache[i] = (prefix, keys[order], values[order], counts[order])
        return logp, options

    def play_log_likelihood(self, o, view, assign, plays=None):
        """[layouts] sum over the hidden choosers' past plays of the floored log-probability of the card played."""
        logp, options = self.play_log_probabilities(o, view, assign, plays)
        return floored(logp, options, self.g7.play_floor).sum(axis=0)

    def layouts(self, o, view, source, rng):
        worlds, weights, info = self.weighted_layouts(o, view, source, rng)
        self.solved_layouts = worlds
        return worlds, weights, info

    def weighted_layouts(self, o, view, source, rng):
        g = self.g7
        if source != 'list' or g.play_weight <= 0:
            return super().layouts(o, view, source, rng)
        c = self.config
        assign = view.every()
        logw = self.layout_log_weights(o, view, assign)
        info = dict(listed=len(assign), effective=_effective(logw))
        plays = hidden_plays(o, g.play_lead)
        if len(assign) > g.play_max_layouts:
            index, share = systematic(np.exp(logw - logw.max()), g.play_max_layouts, rng)
            assign, logw = assign[index], np.log(share)
        rows = self.net_rows
        logw = logw + g.play_weight * self.play_log_likelihood(o, view, assign, plays)
        info.update(play_decisions=len(plays), play_layouts=len(assign), play_net_rows=self.net_rows - rows,
                    effective_with_play=_effective(logw))
        w = np.exp(logw - logw.max())
        if c.list_solve and len(assign) > c.list_solve:
            index, weights = systematic(w, c.list_solve, rng)
        else:
            index, weights = np.arange(len(assign)), w / w.sum()
        return [view.world(assign[i]) for i in index], weights, info

    # ---- the tree ------------------------------------------------------------------------
    def stage(self, o):
        """Index of the tree stage for this decision, or None: dummy must be down and the trick inside a stage."""
        if not o.history or o.known_hands[o.contract.dummy] is None:
            return None
        trick = len(o.history) // 4 + 1
        for i, s in enumerate(self.stages):
            if s.from_trick <= trick <= s.to_trick:
                return i
        return None

    def searching_reply(self, layouts=8, pool=64):
        """reply='search' / own='search': what a small PIMC from the seat's own view plays. `pool` card-fit layouts
        weighted by the hand-fit scorer, `layouts` of them solved; its equal-best cards share the probability."""
        def reply(o):
            view = View(o)
            rng = np.random.default_rng([len(o.history), o.controller, *o.known_hands[o.controller][:3]])
            assign = view.uniform(pool, rng)
            logw = self.layout_log_weights(o, view, assign)
            index, weights = systematic(np.exp(logw - logw.max()), layouts, rng)
            solved = self.dds.solve_batch([view.world(assign[i]) for i in index], o.contract.trump, o.leader, o.trick,
                                          fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
            means = {x: 0. for x in o.legal}
            for (values, _), w in zip(solved, weights):
                for x, u in utilities(o, values).items():
                    means[x] += float(w) * u
            top = max(means.values())
            best = [x for x, v in means.items() if top - v <= 1e-9]
            return {x: 1. / len(best) for x in best}
        return reply

    def replier(self, search):
        if 'search' not in (search.reply, search.own):
            return None
        key = (search.reply_layouts, search.reply_pool)
        if key not in self.repliers:
            self.repliers[key] = self.searching_reply(*key)
        return self.repliers[key]

    def search_decision(self, o, rng, solved, weights, before, after, info):
        result = super().search_decision(o, rng, solved, weights, before, after, info)
        index = self.stage(o)
        return result if index is None else self.tree_decision(o, rng, result, solved, weights, index)

    def tree_decision(self, o, rng, result, solved, weights, index):
        """The Gen6 decision with its near-best cards valued again by the tree. Returns the same kind of Decision:
        the cards left eligible are the tree's best, and break_ties chooses among them as it does among Gen6's."""
        stage, d, legal = self.stages[index], result.details, list(o.legal)
        note = dict(stage=index, consulted=False)
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
            raise RuntimeError('The tree was handed solves without their layouts')
        fork = random.Random()      # the tree's draws come from a copy: the table's own random stream is as Gen6 left it
        fork.setstate(rng.getstate())
        k = stage.search.layouts
        pick, share = systematic(w, k, np.random.default_rng(fork.getrandbits(64))) if len(worlds) > k else (np.arange(len(worlds)), w)
        tree = Tree(self.net, self.dds, stage.search, replier=self.replier(stage.search), max_solves=stage.max_solves)
        at_stake = None
        if stage.search.path > 0:   # the stake rule: what a trick is worth here in IMPs, from every layout the search solved
            declaring = o.controller % 2 == o.contract.declarer % 2
            ahead = u[:, groups[int(value.argmax())][0]]
            at_stake = trick_stake(o.contract, o.vulnerability, declaring, ahead if declaring else -ahead, w, stage.search.spread)
        started = time.perf_counter()
        try:
            got = tree.values(o, [worlds[i] for i in pick], share, cards=searched, **({} if at_stake is None else dict(stake=at_stake)))
        except OverBudget:
            return Decision(result.card, dict(d, gen7_tree=dict(note, candidates=len(near), over_budget=True, solves=tree.solves,
                                                                seconds=time.perf_counter() - started)))
        seconds = time.perf_counter() - started
        column = {x: j for j, x in enumerate(legal)}
        same = {x: float(share @ u[pick, column[x]]) for x in searched}        # plain double dummy on the tree's own layouts
        if tree.flat is not None:   # the tree worked them out itself: with `plain` its layouts are not quite the search's
            same = {x: float(tree.flat[x]) for x in searched}
        adjusted = {i: float(value[i]) + stage.trust * (got[x] - same[x]) for i, x in zip(near, searched)}
        top = max(adjusted.values())
        winners = [i for i in near if top - adjusted[i] <= 1e-9]
        eligible = sorted(legal[j] for i in winners for j in groups[i])
        choice = result.card if result.card in eligible else fork.choice(eligible)
        self.before_tree = result
        note.update(consulted=True, layouts=len(pick), seconds=seconds, lines=tree.lines, nodes=tree.nodes, net_rows=tree.net_rows,
                    solves=tree.solves, replies=tree.replies, stake=tree.stake,
                    gen6_cards=sorted(k for k, q in d['behavior_probabilities'].items() if q > 0),
                    candidates=[dict(cards=[symbol(legal[j]) for j in groups[i]], searched=symbol(x), gap=best - float(value[i]),
                                     same_layouts=same[x], tree=float(got[x]), adjusted=adjusted[i], kept=i in winners)
                                for i, x in zip(near, searched)])
        return Decision(choice, dict(d, behavior_probabilities={symbol(x): (1 / len(eligible) if x in eligible else 0.) for x in legal},
                                     selected_probability=1 / len(eligible),
                                     selected_pimc_gap=d['estimates'][symbol(choice)]['gap_to_best'], gen7_tree=note))

    # ---- one decision --------------------------------------------------------------------
    def choose(self, o, rng):
        if len(o.legal) > 1 and len(o.history) // 4 + 1 < self.g7.search_from_trick:
            return self.net_decision(o, rng)
        self.before_tree = None
        result = super().choose(o, rng)
        if 'gen6' not in result.details:
            return result
        details = dict(result.details, gen7=asdict(self.g7))
        if self.before_tree is not None and self.reference and self.g7.tree_audit:
            fork = random.Random()          # a copy again: the audit's reference costs the table's stream nothing
            fork.setstate(rng.getstate())
            plain = self.break_ties(o, fork, self.before_tree)
            details.update(reference_card=symbol(plain.card), expected_gain_imps=None, prediction_units='tree-against-no-tree',
                           gen7_tree=dict(details['gen7_tree'], audit_reference='without-tree'))
        return Decision(result.card, details)

    def net_decision(self, o, rng):
        """A card straight from the net: no layouts, no DDS, no estimates."""
        logp = self.net.log_policy([o])[0]
        p = np.exp(logp[list(o.legal)].astype(np.float64))
        p /= p.sum()
        if self.g7.net_sample:
            ticket, k = rng.random(), 0
            for k, share in enumerate(p):
                ticket -= share
                if ticket <= 0:
                    break
            behaviour = {symbol(x): float(q) for x, q in zip(o.legal, p)}
        else:
            k = int(np.argmax(p))
            behaviour = {symbol(x): float(j == k) for j, x in enumerate(o.legal)}
        chosen = o.legal[k]
        return Decision(chosen, dict(samples=0, dds_calls=0, unsearched=True, behavior_probabilities=behaviour,
            selected_probability=behaviour[symbol(chosen)], net_probabilities={symbol(x): float(q) for x, q in zip(o.legal, p)},
            gen7=dict(asdict(self.g7), source='net', trick=len(o.history) // 4 + 1)))

    def break_ties(self, o, rng, result):
        """Gen6Player.break_ties with the Gen7 net's log-probability in place of the Gen5 net's prediction."""
        if self.g7.tie_break != 'net':
            return super().break_ties(o, rng, result)
        d = result.details
        eligible = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        if len(eligible) < 2:
            return result
        logp = self.net.log_policy([o])[0]
        values = {x: float(logp[x]) for x in eligible}
        best = max(values.values())
        ties = {x for x, v in values.items() if best - v <= 1e-7}
        epsilon = self.spec.get('exploration', 0.)
        probs = {x: epsilon / len(values) + (1 - epsilon) * (x in ties) / len(ties) for x in values}
        ticket = rng.random()
        for chosen, probability in sorted(probs.items()):
            ticket -= probability
            if ticket <= 0:
                break
        details = dict(d, selector='gen7-net-' + self.spec['id'], proposal_probabilities=d['behavior_probabilities'],
            behavior_probabilities={symbol(x): p for x, p in probs.items()}, selected_probability=probs[chosen],
            selector_predictions={symbol(x): v for x, v in values.items()},
            selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'])
        if self.reference:
            seen = dict(d, samples=min(max(d['samples'], POLICY_SAMPLE_RANGE[0]), POLICY_SAMPLE_RANGE[1]))
            reference_rng = random.Random()
            reference_rng.setstate(rng.getstate())
            ref, _ = self.reference.choose(o, seen, reference_rng)
            details.update(reference_card=symbol(ref), expected_gain_imps=None, prediction_units='log-policy-probability')
        return Decision(chosen, details)


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: Gen7 specs get this engine, every other spec is as before."""
    if spec.get('engine') == ENGINE:
        return Gen7Player(spec, root, reference)
    return gen6_player(spec, root, reference)
