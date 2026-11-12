"""Gen6 card play: layouts come from the auction through two new nets, then DDS as before.

One decision, in order:
  1. Layouts.   Opening lead: the lead belief net samples them (leader's seat only).
                After dummy appears: the two hidden hands are grouped into hand-type classes
                (honours held and number of low cards per suit); each class is weighted by its
                number of layouts times the hand-fit scorer's value for both hands, and
                layouts are dealt from the weighted classes (`samples` of them, `mid_samples`
                from `mid_from_trick`). This is the exact scorer-weighted posterior, with no
                sampling collapse.
                From `list_from_trick`: every card-fit layout is listed and weighted by the
                scorer (the deal list); the list, or a weighted resample of it, is solved.
  2. DDS.       Each distinct layout is solved once; cards are ranked by weighted mean tricks.
  3. Policy.    The policy net chooses only among cards within `near_tie` of the best
                (0 = exact ties), as in Gen5RZ.

No bidder is asked about a hidden hand during play. The lead net takes the frozen Gen5
bidder's features for the leader's own hand as an input, nothing else.

Any phase can be switched back to the Gen5R/RZ decision ("gen5": the spec's belief sampler,
sample count and layout reduction) for comparison. Switches live in spec['gen6'] and are part
of the bot identity; see Gen6Config. The class method is the one measured in
analysis/auction_belief (classes.py, play_classes.py) on the belief-research branch.
"""
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations
import math
from pathlib import Path
import random
import time

import numpy as np

from .core import symbol
from .gen6_nets import BidderState, FitScorer, LeadNet, POP, hand_types
from .mixed_arena import ArenaPlayer, IMPSelector
from .players import Decision

ENGINE = 'gen6'
POLICY_SAMPLE_RANGE = (32, 192)     # sample counts the policy net saw in training
LOGC = np.array([[math.log(math.comb(n, k)) if k <= n else -np.inf for k in range(9)] for n in range(9)])


@dataclass(frozen=True)
class Gen6Config:
    lead_source: str = 'lead_net'       # opening lead: 'lead_net' | 'scorer' | 'gen5'
    early_source: str = 'scorer'        # after dummy, before the deal list: 'scorer' | 'gen5'
    leader_early_source: str = ''       # opening leader's seat in that phase: '' (= early_source) | 'lead_net'
    early_pick: str = 'spaced'          # layouts from the weighted classes: 'spaced' (evenly through the cumulative weight) | 'random'
                                        # | 'strata' (one random member per cluster of a pool of draws) | 'centres' (each cluster's centre)
    cluster_pool: int = 256             # independent draws that 'strata' and 'centres' cluster; only the picks are solved
    mid_from_trick: int = 3             # from this trick until the deal list starts, deal mid_samples layouts instead of spec['samples']
    mid_samples: int = 64               # solving is cheap by then and more layouts help most there; 14 above = never
    lead_pool: int = 32768              # uniform layouts weighted by the scorer when it has to make the opening lead
    list_from_trick: int = 6            # first trick (1-13) decided from the deal list; 14 = never
    list_max_layouts: int = 20000       # a longer list is not built; that decision uses the early source
    list_solve: int = 256               # most distinct layouts solved from the list; 0 = the whole list

    def __post_init__(self):
        if self.lead_source not in ('lead_net', 'scorer', 'gen5') or self.early_source not in ('scorer', 'gen5') \
                or self.leader_early_source not in ('', 'lead_net') or self.early_pick not in ('spaced', 'random', 'strata', 'centres'):
            raise ValueError('Unknown Gen6 layout source')
        for name in ('lead_pool', 'cluster_pool', 'mid_from_trick', 'mid_samples', 'list_from_trick', 'list_max_layouts', 'list_solve'):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f'Gen6 {name} must be an integer')
        if not (1 <= self.lead_pool <= 1 << 20 and 1 <= self.list_from_trick <= 14 and 1 <= self.mid_from_trick <= 14
                and 1 <= self.mid_samples <= 4096 and 1 <= self.cluster_pool <= 4096
                and 1 <= self.list_max_layouts <= 100000 and 0 <= self.list_solve <= 100000):
            raise ValueError('Invalid Gen6 settings')


@lru_cache(maxsize=64)
def _subsets(n, k):
    """Every k-subset of range(n) as an (C, k) index array."""
    count = math.comb(n, k)
    return np.fromiter((i for c in combinations(range(n), k) for i in c), np.int16, count * k).reshape(count, k)


class View:
    """What the deciding player cannot see: the unseen cards and how they may lie."""

    def __init__(self, o):
        self.o = o
        self.hidden = tuple(s for s in range(4) if o.known_hands[s] is None)
        gone = {c for _, c in o.history} | {c for h in o.known_hands if h is not None for c in h}
        self.unseen = np.array(sorted(set(range(52)) - gone), np.int64)
        self.played = {s: [c for seat, c in o.history if seat == s] for s in self.hidden}
        self.caps = [13 - len(self.played[s]) for s in self.hidden]
        if sum(self.caps) != len(self.unseen):
            raise ValueError('Unseen cards do not match hidden hand sizes')
        self.voids = set()
        for i, (seat, c) in enumerate(o.history):
            led = o.history[i - i % 4][1] // 13
            if c // 13 != led and seat in self.hidden:
                self.voids.add((seat, led))
        # owner forced by a show-out: index into hidden, or -1 when either hand may hold the card
        self.forced = np.full(len(self.unseen), -1, np.int8)
        if len(self.hidden) == 2:
            a, b = self.hidden
            for i, c in enumerate(self.unseen):
                va, vb = (a, c // 13) in self.voids, (b, c // 13) in self.voids
                if va and vb:
                    raise ValueError('No hidden deal is consistent with observation')
                self.forced[i] = 1 if va else 0 if vb else -1
        elif self.voids:
            raise ValueError('Show-outs with three hidden hands are not supported')
        self.free = np.flatnonzero(self.forced < 0)
        self.need = [cap - int((self.forced == j).sum()) for j, cap in enumerate(self.caps)]
        if min(self.need) < 0 or sum(self.need) != len(self.free):
            raise ValueError('No hidden deal is consistent with observation')

    def count(self):
        """Number of card-fit layouts."""
        n, total = len(self.free), 1
        for k in self.need[:-1]:
            total *= math.comb(n, k)
            n -= k
        return total

    def _assign(self, free_owner):
        assign = np.broadcast_to(self.forced, (len(free_owner), len(self.unseen))).copy()
        assign[:, self.free] = free_owner
        return assign

    def uniform(self, n, rng):
        """n uniform card-fit layouts: (n, unseen) owner index per unseen card."""
        labels = np.repeat(np.arange(len(self.hidden), dtype=np.int8), self.need)
        return self._assign(rng.permuted(np.broadcast_to(labels, (n, len(labels))), axis=1))

    def every(self):
        """Every card-fit layout (two hidden hands)."""
        if len(self.hidden) != 2:
            raise ValueError('The deal list needs exactly two hidden hands')
        chosen = _subsets(len(self.free), self.need[0])
        owner = np.ones((len(chosen), len(self.free)), np.int8)
        np.put_along_axis(owner, chosen.astype(np.int64), 0, axis=1)
        return self._assign(owner)

    def original(self, assign, j):
        """Membership (n, 52) of hidden hand j's original thirteen cards: held now plus already played."""
        member = np.zeros((len(assign), 52), np.int8)
        member[:, self.unseen] = assign == j
        member[:, self.played[self.hidden[j]]] = 1
        return member

    def world(self, row):
        hands = list(self.o.known_hands)
        for j, s in enumerate(self.hidden):
            hands[s] = tuple(int(c) for c in self.unseen[row == j])
        return tuple(hands)


def _suit_options(honours, n_low, void_a, void_b):
    """Ways to split one suit's unseen cards: which honours hand A holds and how many low cards."""
    h = len(honours)
    bit = [1 << (12 - c % 13) for c in honours]
    held = np.array([sum(bit[j] for j in range(h) if m >> j & 1) for m in range(1 << h)], np.int64)
    mask = np.repeat(np.arange(1 << h), n_low + 1)
    n = np.tile(np.arange(n_low + 1), 1 << h)
    keep = np.ones(len(mask), bool)
    if void_a:
        keep &= (mask == 0) & (n == 0)
    if void_b:
        keep &= (mask == (1 << h) - 1) & (n == n_low)
    mask, n = mask[keep], n[keep]
    return dict(mask=mask, n=n, cnt=POP[mask] + n, hon_a=held[mask], hon_b=sum(bit) - held[mask], logmult=LOGC[n_low, n])


def _join(cnt, ka):
    """Every choice of one option per suit that gives hand A exactly ka cards: (n, 4) option indices."""
    def pair(x, y):
        i, j = np.repeat(np.arange(len(x)), len(y)), np.tile(np.arange(len(y)), len(x))
        return i, j, x[i] + y[j]
    i0, i1, s01 = pair(cnt[0], cnt[1])
    i2, i3, s23 = pair(cnt[2], cnt[3])
    o01, o23 = np.argsort(s01, kind='stable'), np.argsort(s23, kind='stable')
    b01, b23 = np.searchsorted(s01[o01], np.arange(ka + 2)), np.searchsorted(s23[o23], np.arange(ka + 2))
    left, right = [], []
    for t in range(ka + 1):
        l, r = o01[b01[t]:b01[t + 1]], o23[b23[ka - t]:b23[ka - t + 1]]
        if len(l) and len(r):
            left.append(np.repeat(l, len(r)))
            right.append(np.tile(r, len(l)))
    if not left:
        return np.zeros((0, 4), np.int64)
    left, right = np.concatenate(left), np.concatenate(right)
    return np.stack([i0[left], i1[left], i2[right], i3[right]], axis=1)


class Classes:
    """Hand-type classes of the two hidden hands.

    The bidder and the scorer see a hand as A, K, Q, J, T per suit plus a count of low cards.
    Layouts that give hidden hand A the same unseen honours and the same number of unseen low
    cards in every suit are interchangeable for the bidding. Such a set is a class; logmult is
    the log of its number of layouts. Weighting classes gives the same posterior as weighting
    every layout, at any trick.
    """

    def __init__(self, view):
        if len(view.hidden) != 2:
            raise ValueError('Classes need exactly two hidden hands')
        self.view = view
        a, b = view.hidden
        unseen = [int(c) for c in view.unseen]
        self.honours = [[c for c in unseen if c // 13 == s and c % 13 >= 8] for s in range(4)]
        self.lows = [[c for c in unseen if c // 13 == s and c % 13 < 8] for s in range(4)]
        self.options = opts = [_suit_options(self.honours[s], len(self.lows[s]), (a, s) in view.voids, (b, s) in view.voids) for s in range(4)]
        self.index = idx = _join([op['cnt'] for op in opts], view.caps[0])
        if not len(idx):
            raise ValueError('No hidden deal is consistent with observation')
        seen_len = {s: np.bincount([c // 13 for c in view.played[s]], minlength=4) for s in (a, b)}
        seen_hon = {s: [sum(1 << (12 - c % 13) for c in view.played[s] if c // 13 == u and c % 13 >= 8) for u in range(4)] for s in (a, b)}
        total = [len(self.honours[s]) + len(self.lows[s]) for s in range(4)]
        # types of the original thirteen cards: unseen cards assigned by the class plus cards already played
        self.length = [np.stack([opts[s]['cnt'][idx[:, s]] + seen_len[a][s] for s in range(4)], axis=1),
                       np.stack([total[s] - opts[s]['cnt'][idx[:, s]] + seen_len[b][s] for s in range(4)], axis=1)]
        self.hon = [np.stack([opts[s]['hon_a'][idx[:, s]] | seen_hon[a][s] for s in range(4)], axis=1),
                    np.stack([opts[s]['hon_b'][idx[:, s]] | seen_hon[b][s] for s in range(4)], axis=1)]
        self.logmult = sum(opts[s]['logmult'][idx[:, s]] for s in range(4))

    def __len__(self):
        return len(self.index)

    def worlds(self, picks, rng):
        """One layout per picked class; the low cards are dealt at random within the class."""
        a, b = self.view.hidden
        out = []
        for i in picks:
            ha, hb = [], []
            for s in range(4):
                op, j = self.options[s], self.index[i, s]
                m, n = int(op['mask'][j]), int(op['n'][j])
                for t, c in enumerate(self.honours[s]):
                    (ha if m >> t & 1 else hb).append(c)
                low = self.lows[s]
                if low:
                    order = rng.permutation(len(low))
                    ha += [low[t] for t in order[:n]]
                    hb += [low[t] for t in order[n:]]
            hands = list(self.view.o.known_hands)
            hands[a], hands[b] = tuple(sorted(ha)), tuple(sorted(hb))
            out.append(tuple(hands))
        return out


def spaced(log_weights, m, u):
    """m picks in proportion to exp(log_weights), evenly spaced through the cumulative weight."""
    c = np.cumsum(np.exp(log_weights - log_weights.max()))
    return np.searchsorted(c / c[-1], (u + np.arange(m)) / m, side='left').clip(max=len(c) - 1)


def systematic(weights, m, rng):
    """m draws in proportion to weight with the fewest possible repeats: (indices, share of draws)."""
    c = np.cumsum(weights, dtype=np.float64)
    picks = np.minimum(np.searchsorted(c / c[-1], (rng.random() + np.arange(m)) / m, side='right'), len(c) - 1)
    index, counts = np.unique(picks, return_counts=True)
    return index, counts / m


def _merge(worlds, weights=None):
    """Distinct layouts and the weight each received (the share of draws when no weights are given)."""
    total = {}
    for i, w in enumerate(worlds):
        total[w] = total.get(w, 0.) + (1. if weights is None else float(weights[i]))
    values = np.array(list(total.values()))
    return list(total), values / values.sum()


CARD_WEIGHT = np.array([0.5] * 8 + [1.0, 1.5, 2.0, 3.0, 4.0])       # by rank: 2-9, T, J, Q, K, A


def cluster_picks(pool, hand, unseen, trump, k, rng, centres):
    """k-medoids over a pool of layouts described by one hidden hand (its cards weighted by rank,
    its suit lengths, trumps counting more; L1 distance). Returns pool indices and cluster shares:
    each cluster's centre, or one random member of it. The method of the layout-selection test
    (analysis/auction_belief/select_layouts.py on the research branch: med_K and strat_K)."""
    column = {int(c): i for i, c in enumerate(unseen)}
    x = np.zeros((len(pool), len(unseen) + 4))
    for r, world in enumerate(pool):
        for c in world[hand]:
            x[r, column[c]] = CARD_WEIGHT[c % 13]
            x[r, len(unseen) + c // 13] += 3.0 if c // 13 == trump else 2.0
    distance = np.abs(x[:, None, :] - x[None, :, :]).sum(axis=2)
    medoids = [int(rng.integers(len(pool)))]
    nearest = distance[medoids[0]].copy()
    while len(medoids) < k and nearest.sum() > 0:
        medoids.append(int(rng.choice(len(pool), p=nearest / nearest.sum())))
        nearest = np.minimum(nearest, distance[medoids[-1]])
    medoids = np.array(medoids)
    for _ in range(20):
        label = np.argmin(distance[:, medoids], axis=1)
        moved = medoids.copy()
        for j in range(len(medoids)):
            members = np.flatnonzero(label == j)
            if len(members):
                moved[j] = members[np.argmin(distance[np.ix_(members, members)].sum(axis=1))]
        if (moved == medoids).all():
            break
        medoids = moved
    label = np.argmin(distance[:, medoids], axis=1)
    size = np.bincount(label, minlength=len(medoids))
    keep = size > 0
    picks = medoids if centres else np.array([rng.choice(np.flatnonzero(label == j)) if size[j] else medoids[j] for j in range(len(medoids))])
    return picks[keep], size[keep] / size.sum()


def _effective(log_weights):
    """exp(entropy) of the normalised weights: how many equally likely items they amount to."""
    p = np.exp(log_weights - log_weights.max())
    p = p[p > 0] / p.sum()
    return float(np.exp(-(p * np.log(p)).sum()))


class Gen6Player(ArenaPlayer):
    """ArenaPlayer whose layouts come from the lead net, the hand-fit scorer and the deal list."""

    def __init__(self, spec, root, reference=None):
        super().__init__(spec, root, reference)
        self.config = c = Gen6Config(**spec.get('gen6', {}))
        root = Path(root)
        if 'gen5' in (c.lead_source, c.early_source) and not spec.get('belief'):
            raise ValueError("A 'gen5' layout source needs the spec's belief net")
        self.scorer = FitScorer(root / spec['scorer'])
        # Gen 8 prototype (inert unless the spec names these): the systems NS and EW have declared at this table
        # (spec['table_systems']), a scorer that reads each side's calls by its system (spec['system_scorer']), and
        # the systems whose auctions the lead net was trained on (spec['lead_systems']; elsewhere the scorer leads).
        systems = tuple(spec.get('table_systems') or (None, None))
        if spec.get('system_scorer'):
            from .system_nets import SystemFitScorer
            from .systems import TableSystems
            self.scorer = SystemFitScorer(root / spec['system_scorer']).bind(TableSystems(*systems))
        self.lead_fits = 'lead_systems' not in spec or all(x in spec['lead_systems'] for x in systems)
        self.lead_net = None
        if 'lead_net' in (c.lead_source, c.leader_early_source):
            self.lead_net = LeadNet(root / spec['lead_belief'], BidderState(root / spec['lead_state_bidder']))
        self.lead_context = (None, None)

    # ---- which layouts -------------------------------------------------------------------
    def source(self, o, view):
        c = self.config
        if not o.history:
            return 'scorer' if c.lead_source == 'lead_net' and not (self.lead_fits and LeadNet.fits(o.auction)) else c.lead_source
        if len(o.history) // 4 + 1 >= c.list_from_trick and view.count() <= c.list_max_layouts:
            return 'list'
        if c.leader_early_source == 'lead_net' and o.controller == (o.contract.declarer + 1) % 4 and self.lead_fits and LeadNet.fits(o.auction):
            return 'lead_net'
        return c.early_source

    def leader_context(self, o):
        hand = o.original_hand(o.controller)
        key = (hand, o.controller, o.dealer, o.vulnerability, o.auction)
        if self.lead_context[0] != key:
            self.lead_context = (key, self.lead_net.context(hand, o.controller, o.dealer, o.vulnerability, o.auction))
        return self.lead_context[1]

    def type_log_weights(self, o, view, length, hon, source):
        """Log weight, up to a constant, of hidden hands given as original-hand types:
        length[j], hon[j] are (n,4) arrays for hidden hand j."""
        if source == 'lead_net':        # the opening leader after dummy appeared: P(declarer's hand, the actual dummy)
            j = view.hidden.index(o.contract.declarer)
            member = np.zeros(52, np.int8)
            member[list(o.original_hand(o.contract.dummy))] = 1
            m_len, m_hon = (np.repeat(x[None], len(length[j]), 0) for x in hand_types(member))
            return self.lead_net.log_density(self.leader_context(o), length[j], hon[j], m_len, m_hon)
        return sum(self.scorer.type_log_score(length[j], hon[j], seat, o.dealer, o.vulnerability, o.auction)
                   for j, seat in enumerate(view.hidden))

    def layout_log_weights(self, o, view, assign, source='scorer'):
        types = [hand_types(view.original(assign, j)) for j in range(len(view.hidden))]
        return self.type_log_weights(o, view, [t[0] for t in types], [t[1] for t in types], source)

    def layouts(self, o, view, source, rng):
        """Distinct layouts to solve and their weights (summing to one), plus a description."""
        c, n = self.config, self.samples
        if not o.history and source == 'lead_net':
            leader, context = o.controller, self.leader_context(o)
            deals = LeadNet.deal(o.known_hands[leader], self.lead_net.sample(context, n, rng), rng)
            worlds = []
            for d, m, p in deals:
                world = [None] * 4
                world[leader], world[(leader + 3) % 4], world[(leader + 1) % 4], world[(leader + 2) % 4] = o.known_hands[leader], d, m, p
                worlds.append(tuple(world))
            return (*_merge(worlds), dict(draws=n))
        if not o.history:               # the scorer has to lead: three hidden hands, weighted uniform layouts
            assign = view.uniform(c.lead_pool, rng)
            logw = self.layout_log_weights(o, view, assign)
            index, weights = systematic(np.exp(logw - logw.max()), n, rng)
            return [view.world(assign[i]) for i in index], weights, dict(pool=len(assign), effective=_effective(logw), draws=n)
        if source == 'list':
            assign = view.every()
            logw = self.layout_log_weights(o, view, assign)
            w = np.exp(logw - logw.max())
            info = dict(listed=len(assign), effective=_effective(logw))
            if c.list_solve and len(assign) > c.list_solve:
                index, weights = systematic(w, c.list_solve, rng)
            else:
                index, weights = np.arange(len(assign)), w / w.sum()
            return [view.world(assign[i]) for i in index], weights, info
        if len(o.history) // 4 + 1 >= c.mid_from_trick:
            n = c.mid_samples
        classes = Classes(view)
        logw = classes.logmult + self.type_log_weights(o, view, classes.length, classes.hon, source)
        info = dict(classes=len(classes), effective=_effective(logw), draws=n, pick=c.early_pick)
        if c.early_pick == 'spaced':
            return (*_merge(classes.worlds(spaced(logw, n, rng.random()), rng)), info)
        p = np.exp(logw - logw.max())
        if c.early_pick == 'random':
            return (*_merge(classes.worlds(rng.choice(len(p), n, p=p / p.sum()), rng)), info)
        pool = classes.worlds(rng.choice(len(p), c.cluster_pool, p=p / p.sum()), rng)
        picks, share = cluster_picks(pool, view.hidden[0], view.unseen, o.contract.trump, n, rng, c.early_pick == 'centres')
        return (*_merge([pool[i] for i in picks], share), dict(info, pool=len(pool), clusters=len(picks)))

    # ---- one decision --------------------------------------------------------------------
    def choose(self, o, rng):
        if len(o.legal) == 1:
            return super().choose(o, rng)
        view = View(o)
        source = self.source(o, view)
        if source == 'gen5':
            result = super().choose(o, rng)
            return Decision(result.card, dict(result.details, gen6=dict(source='gen5', trick=len(o.history) // 4 + 1)))
        started = time.perf_counter()
        worlds, weights, info = self.layouts(o, view, source, np.random.default_rng(rng.getrandbits(64)))
        middle = time.perf_counter()
        before = self.dds.cache_stats()
        solved = self.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick,
            fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
        after = self.dds.cache_stats()
        info = dict(info, source='deal_list' if source == 'list' else source, trick=len(o.history) // 4 + 1,
            layout_seconds=middle - started, dds_seconds=time.perf_counter() - middle, settings=asdict(self.config))
        return self.break_ties(o, rng, self.search_decision(o, rng, solved, weights, before, after, info))

    def search_decision(self, o, rng, solved, weights, before, after, info):
        """Weighted-mean tricks per legal card; eligible = within near_tie of the best (PIMCPlayer's rule)."""
        declaring = o.actor % 2 == o.contract.declarer % 2
        remaining = 13 - len(o.history) // 4
        means = {c: 0. for c in o.legal}
        tricks = dict(means)
        nodes = 0
        for (values, count), w in zip(solved, weights):
            if set(values) != set(o.legal):
                raise RuntimeError('DDS legal-card expansion mismatch')
            nodes += count
            for c, t in values.items():
                total = o.declarer_tricks + (t if declaring else remaining - t)
                means[c] += float(w) * (total if declaring else -total)
                tricks[c] += float(w) * total
        best = max(means.values())
        eligible = sorted(c for c, v in means.items() if best - v <= self.near_tie + 1e-9)
        choice = rng.choice(eligible)
        n = len(solved)
        return Decision(choice, dict(samples=n, dds_calls=n, dds_nodes=nodes, objective='tricks', batch=True,
            dds_native_solves=after['native_solves'] - before['native_solves'], dds_cache_hits=after['hits'] - before['hits'],
            dds_duplicate_worlds=after['duplicate_worlds'] - before['duplicate_worlds'], unique_worlds=n,
            near_tie=self.near_tie, behavior_probabilities={symbol(c): 1 / len(eligible) if c in eligible else 0. for c in means},
            selected_probability=1 / len(eligible), selected_pimc_gap=best - means[choice], gen6=info,
            uncertainty_note='Weighted layouts; no IID standard error.',
            estimates={symbol(c): dict(utility=v, utility_stderr=None, gap_to_best=best - v, gap_stderr=None,
                                       declarer_tricks=tricks[c]) for c, v in means.items()}))

    def break_ties(self, o, rng, result):
        """ArenaPlayer.choose's policy step, unchanged except that the policy net is told a
        sample count inside the range it was trained on."""
        d = result.details
        if self.selector is None or sum(p > 0 for p in d['behavior_probabilities'].values()) < 2:
            return result
        seen = dict(d, samples=min(max(d['samples'], POLICY_SAMPLE_RANGE[0]), POLICY_SAMPLE_RANGE[1]))
        ranking = random.Random()
        ranking.setstate(rng.getstate())
        _, values = self.selector.choose(o, seen, ranking)
        best = max(values.values())
        ties = {c for c, v in values.items() if abs(v - best) <= 1e-7}
        epsilon = self.spec.get('exploration', 0.)
        probs = {c: epsilon / len(values) + (1 - epsilon) * (c in ties) / len(ties) for c in values}
        ticket = rng.random()
        for chosen, probability in sorted(probs.items()):
            ticket -= probability
            if ticket <= 0:
                break
        details = dict(d, selector='mixed-arena-' + self.spec['id'], proposal_probabilities=d['behavior_probabilities'],
            behavior_probabilities={symbol(c): p for c, p in probs.items()}, selected_probability=probs[chosen],
            selector_predictions={symbol(c): v for c, v in values.items()},
            selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'])
        if self.reference:
            reference_rng = random.Random()
            reference_rng.setstate(rng.getstate())
            ref, _ = self.reference.choose(o, seen, reference_rng)
            details.update(reference_card=symbol(ref),
                expected_gain_imps=float(values[chosen] - values[ref]) if isinstance(self.selector, IMPSelector) else None,
                prediction_units='matched-fork-imps' if isinstance(self.selector, IMPSelector) else 'remaining-partnership-tricks')
        return Decision(chosen, details)


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: Gen6 specs get the Gen6 engine, every other spec is unchanged."""
    if spec.get('engine') == ENGINE:
        return Gen6Player(spec, root, reference)
    if spec.get('engine') == 'ben':
        from .round5_ben import Round5BenPlayer
        return Round5BenPlayer(spec['url'], timeout=600, samples=spec['samples'])
    return ArenaPlayer(spec, root, reference)
