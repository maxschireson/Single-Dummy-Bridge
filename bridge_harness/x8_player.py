"""The 8X bot (prototype): rollouts on a rollout net as the main judge of a card, the winning-line logic as a
constraint on them, and the Gen 8 search where rollouts have not yet tested well enough.

Max's plan of 12 November 2026 (23:40 UTC): a rollout net trained on all matches from Gen 7 on; a bot that uses the
single-dummy winning-line logic out to ten tricks (declarer does not give away a made contract, a defender
minimises the odds of handing declarer a claim), rolls out on the new net as broadly as calibration tests allow,
uses PIMC only where it must, and captures inside-rollout data; let it play, retrain the net on the results, repeat,
with a varied population. This is that bot. Until the rollout net exists the Gen 7 policy net stands in for it:
`rollout_policy` in the spec names the net the rollouts use, and defaults to `gen7_policy`.

One decision, by the stage its trick belongs to (spec['x8']['stages']; tricks in no stage, and the opening lead,
are 'search'):

  search    the Gen 8 search as the spec's `gen6` and `gen7` blocks describe it (layouts read from the auction and
            the play, double dummy, the net among level cards). Nothing is rolled out.
  blend     that search, and then its near-best cards are rolled out: every later card of all four seats from the
            rollout net, each seat seeing only its own view (x8_rollout), and
                value = (1 - trust) x the search's estimate + trust x the rollouts' mean.
            With `layouts` above zero the rollouts run on that many fresh layouts, drawn as the search draws its
            own; with `layouts` 0 on the layouts the search solved (the blend is then the search's estimate
            corrected by trust x (rollouts - double dummy) on the same layouts).
  rollout   no double dummy. Candidates are the cards the net gives at least `prior` of its probability (touching
            cards are one candidate; at most `cards`), each rolled out on `layouts` layouts. They race: all get the
            first `first` layouts, and a card behind the leader by more than `race` paired standard errors (plus
            `slack`) gets no more. The value is the weighted mean of the rollouts' results.

`trust`, the stage boundaries, the depth (`horizon`: 0 = to the end, k = k tricks and then double dummy) and the
simulated seat are settings, to be set from the calibration test (scripts/x8_calibrate.py), not constants.

The winning-line logic (spec['x8']['claims'], x8_claims.py), with `cards` or fewer cards in hand:

  declarer    if some card guarantees the contract from the declaring side's own view, only such cards are
              candidates, in every mode. Among them the stage decides as usual.
  defender    for each candidate and each of the `defender` likeliest layouts: would declarer, from its own view in
              that layout, then hold a guaranteed line? The weighted share is the card's hand-over odds. Among cards
              within `odds_margin` of the best value the lowest odds win.
  in rollouts a side that is treated as keeping a guaranteed contract (this bot's own side when it declares; the
              other side when its bot id is listed in `opponents`) has its rollouts floored at the contract from
              the point the guarantee exists: after a guaranteeing root card, after a hand-over, and at the start
              of any later trick with `leaf` or fewer cards where the claim finder says so. A rollout ends when the
              claim finder gives that side every trick left. The floor leaves overtricks as the rollout found them.

Being hard to read (spec['x8']['mix']): a seat that mixes plays any of its equal cards alike, where equal means
the cards the decision leaves eligible (touching cards, and cards rated exactly level), in place of the net's
likeliest of them. `declarer` switches it for the declaring side, whose cards nobody on its own side reads.
`defender` switches it for a defender, whose partner reads the same cards: until the partner's reading treats a
mixing seat's equal cards as equally likely (not built yet; Gen7Player.play_log_likelihood reads every seat as
the net plays), a mixing defender misleads partner as much as declarer. The record's behavior_probabilities are
the probabilities really used.

Capture (spec['x8']['capture'], x8_capture.py): every decision records its candidates and their values; from level
1 also inside-rollout forks, from level 2 the layouts and per-layout results.

With every stage 'search', no claims and no mix the player is Gen7Player with the spec's settings, card for card
(tested).
"""
from dataclasses import asdict, dataclass, field, fields
import math
from pathlib import Path
import random
import time

import numpy as np

from . import x8_capture, x8_claims
from .core import IMP_LIMITS, card, score, symbol, vulnerable
from .gen6 import Classes, View, _effective, _merge, spaced, systematic
from .gen7 import Gen7Player, hidden_plays, utilities
from .gen7 import player as gen7_player
from .gen7_net import PolicyNet
from .players import Decision
from .x8_rollout import Seats, evaluate

ENGINE = 'gen8x'
LIMITS = np.array(IMP_LIMITS)


@dataclass(frozen=True)
class Stage:
    from_trick: int = 1
    to_trick: int = 13
    mode: str = 'rollout'       # 'search' | 'blend' | 'rollout'
    trust: float = 1.           # blend: the weight of the rollouts
    layouts: int = 128          # rollout: layouts played out. blend: fresh layouts for a plain blend; 0 = the solved layouts, as a correction
    first: int = 32             # rollout: layouts every candidate gets before the race may drop it
    cards: int = 4              # at most this many candidates
    prior: float = .02          # rollout: a candidate needs this share of the net's probability (the two likeliest always enter)
    margin: float = .25         # blend: candidates are the cards the search rates within this many tricks of its best
    race: float = 2.5           # rollout: standard errors behind the leader at which a candidate is dropped; 0 = no race
    slack: float = .05          # ... plus this many tricks (or IMPs)
    horizon: int = 0            # 0 = roll out to the end; k = k tricks, then double dummy
    seat: str = 'top'           # the simulated seat: 'top' | 'draw' | 'blend' (x8_rollout.Seats)
    power: float = 1.           # 'draw': the exponent on the net's probabilities
    objective: str = 'tricks'   # rollout: 'tricks' | 'imps' (the swing against the card with the best mean tricks, layout by layout)

    def __post_init__(self):
        for name in ('from_trick', 'to_trick', 'layouts', 'first', 'cards', 'horizon'):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f'8X stage {name} must be an integer')
        if self.mode not in ('search', 'blend', 'rollout') or self.seat not in ('top', 'draw', 'blend') \
                or self.objective not in ('tricks', 'imps') or not (1 <= self.from_trick <= self.to_trick <= 13) \
                or not (0 <= self.trust <= 4 and 0 <= self.layouts <= 4096 and 1 <= self.first <= 4096 and 2 <= self.cards <= 13
                        and 0 <= self.prior < 1 and 0 <= self.margin <= 13 and 0 <= self.race <= 100 and 0 <= self.slack <= 13
                        and 0 <= self.horizon <= 13 and 0 < self.power <= 8):
            raise ValueError('Invalid 8X stage settings')
        if self.mode == 'rollout' and self.layouts < 1:
            raise ValueError('An 8X rollout stage needs layouts')
        if self.mode == 'blend' and self.objective != 'tricks':
            raise ValueError('An 8X blend stage counts tricks, as the search does')


@dataclass(frozen=True)
class ClaimUse:
    cards: int = 0              # the winning-line logic applies with this many cards or fewer in hand; 0 = never
    declarer: bool = True       # the declaring side keeps a guaranteed contract
    defender: int = 16          # layouts in which each candidate is tested for handing declarer a guarantee; 0 = none
    defender_ms: int = 400      # time allowed for that test, a decision
    odds_margin: float = .1     # the lowest hand-over odds win among cards within this of the best value; below 0 = odds are only recorded
    leaf: int = 6               # rollouts ask the claim finder at the start of tricks with this many cards or fewer; 0 = never
    leaf_ms: int = 300          # time allowed for one such round of questions
    own: bool = True            # this bot's own side, declaring, is rolled out as keeping a guaranteed contract
    opponents: tuple = ()       # bot ids ('*' = any) whose declaring side is rolled out the same way
    each_ms: int = 1000         # the most one question may take before it is abandoned
    binary: str = ''            # the solver; default the environment's SURE_BIN

    def __post_init__(self):
        object.__setattr__(self, 'opponents', tuple(self.opponents))
        if not (0 <= self.cards <= 13 and 0 <= self.defender <= 4096 and 0 <= self.leaf <= 13 and self.defender_ms >= 0
                and self.leaf_ms >= 0 and self.each_ms > 0 and -1 <= self.odds_margin <= 13):
            raise ValueError('Invalid 8X claim settings')


@dataclass(frozen=True)
class CaptureUse:
    level: int = 1              # 0 = values only; 1 = and inside-rollout forks; 2 = and layouts with per-layout results
    forks: int = 8              # forks a decision
    layouts: int = 64           # level 2: at most this many layouts a decision
    fork_power: float = .5      # the forced card is drawn from the net's probabilities raised to this

    def __post_init__(self):
        if self.level not in (0, 1, 2) or not (0 <= self.forks <= 512 and 1 <= self.layouts <= 4096 and 0 <= self.fork_power <= 4):
            raise ValueError('Invalid 8X capture settings')


@dataclass(frozen=True)
class MixUse:
    """Being hard to read: which of several equal cards is played."""
    declarer: bool = False      # the declaring side plays a random one of its equal cards (nobody on its side reads them)
    defender: bool = False      # a defender does (its partner reads those cards too: see the module note on reading)
    near: float = 0.            # rollout stages: candidates within this of the best value count as equal

    def __post_init__(self):
        if not 0 <= self.near <= 13:
            raise ValueError('Invalid 8X mix settings')


@dataclass(frozen=True)
class X8Config:
    stages: tuple = ()
    claims: ClaimUse = field(default_factory=ClaimUse)
    capture: CaptureUse = field(default_factory=CaptureUse)
    mix: MixUse = field(default_factory=MixUse)
    others: tuple = ()          # ({'policy': path, 'share': s}, ...): nets that play the other side in a share of the rollouts' layouts


def x8_settings(block):
    """spec['x8'] -> X8Config. No trick may belong to two stages."""
    block = dict(block or {})
    unknown = set(block) - {'stages', 'claims', 'capture', 'mix', 'others'}
    if unknown:
        raise ValueError(f'Unknown 8X settings: {sorted(unknown)}')
    try:
        stages = tuple(Stage(**s) for s in block.get('stages') or ())
        claims = ClaimUse(**(block.get('claims') or {}))
        capture = CaptureUse(**(block.get('capture') or {}))
        mix = MixUse(**(block.get('mix') or {}))
    except TypeError as e:
        raise ValueError(f'Unknown 8X setting: {e}') from None
    tricks = [t for s in stages for t in range(s.from_trick, s.to_trick + 1)]
    if len(tricks) != len(set(tricks)):
        raise ValueError('8X stages overlap')
    others = tuple(dict(o) for o in block.get('others') or ())
    if any(set(o) != {'policy', 'share'} or not 0 < o['share'] < 1 for o in others) or sum(o['share'] for o in others) > 1:
        raise ValueError('8X others are {policy, share} with shares that sum to at most 1')
    return X8Config(stages, claims, capture, mix, others)


def resolved(block):
    """spec['x8'] with every setting written out, defaults included: what a manifest should pin."""
    c = x8_settings(block)
    return dict(stages=[asdict(s) for s in c.stages], claims=dict(asdict(c.claims), opponents=list(c.claims.opponents)),
                capture=asdict(c.capture), mix=asdict(c.mix), others=[dict(o) for o in c.others])


def touching(o):
    """The legal cards in runs the play cannot tell apart: same suit, and every card between two of them is in the
    same hand or was played to an earlier trick."""
    hand = set(o.known_hands[o.actor])
    gone = {x for _, x in o.history} - {x for _, x in o.trick}
    runs = []
    for x in sorted(o.legal):
        if runs and runs[-1][-1] // 13 == x // 13 and all(z in hand or z in gone for z in range(runs[-1][-1] + 1, x)):
            runs[-1].append(x)
        else:
            runs.append([x])
    return runs


def worth(tricks, o, objective, reference=None):
    """[layout, card] what declarer's final tricks are worth to the side deciding: its tricks (negated for the
    defence, as the search counts), or with 'imps' the swing in IMPs against column `reference` in the same layout."""
    declaring = o.controller % 2 == o.contract.declarer % 2
    t = np.asarray(tricks, np.int64)
    if objective == 'tricks':
        return (t if declaring else -t).astype(np.float64)
    vul = vulnerable(o.vulnerability, o.contract.declarer)
    table = np.array([score(o.contract, k, vul) for k in range(14)], np.int64) * (1 if declaring else -1)
    points = table[t]
    diff = points - points[:, [reference]]
    return (np.sign(diff) * np.searchsorted(LIMITS, np.abs(diff), side='right')).astype(np.float64)


def paired(u, w, lead):
    """(mean, standard error) of column `lead` minus each column of u [layout, card] under weights w."""
    w = w / w.sum()
    d = u[:, [lead]] - u
    mean = w @ d
    n = max(len(w), 2)
    return mean, np.sqrt(np.maximum((w[:, None] ** 2 * (d - mean) ** 2).sum(axis=0) * n / (n - 1), 0.))


class X8Player(Gen7Player):
    """Gen7Player (with the Gen 8 prototype's reading) that rolls out, keeps guaranteed lines and records both."""

    def __init__(self, spec, root, reference=None):
        self.x8 = x8_settings(spec.get('x8'))
        self.opponent_id = None
        super().__init__(spec, root, reference)
        c = self.x8
        for s in c.stages:
            if s.mode == 'blend' and any(t.from_trick <= s.to_trick and s.from_trick <= t.to_trick for t in self.stages):
                raise ValueError('An 8X blend stage and a Gen 7 tree stage cover the same trick: the two corrections are alternatives')
        root = Path(root)
        self.rollout_net = PolicyNet(root / spec['rollout_policy'], self.scorer) if spec.get('rollout_policy') else self.net
        self.rollout_name = Path(spec.get('rollout_policy') or spec['gen7_policy']).name
        self.other_nets = [PolicyNet(root / o['policy'], self.scorer) for o in c.others]
        self.other_share = np.array([o['share'] for o in c.others])
        self.finder = x8_claims.shared(c.claims.binary or None) if c.claims.cards else None
        if self.finder is not None:
            self.finder.each = c.claims.each_ms / 1000
        self.live = None            # the stage of the decision in hand
        self.claim = None           # (state, {card: guarantees}) for the decision in hand, when the declaring side decides
        self.x8_note = None

    def meet(self, opponent_id):
        super().meet(opponent_id)
        self.opponent_id = opponent_id

    def aware(self, declaring):
        """Is the declaring side rolled out as keeping a guaranteed contract? `declaring`: this bot's side declares."""
        c = self.x8.claims
        if self.finder is None:
            return False
        return c.own if declaring else ('*' in c.opponents or self.opponent_id in c.opponents)

    # ---- which stage, which claim ----------------------------------------------------------
    def x8_stage(self, o):
        if not o.history or o.known_hands[o.contract.dummy] is None:
            return None
        trick = len(o.history) // 4 + 1
        for s in self.x8.stages:
            if s.from_trick <= trick <= s.to_trick:
                return s if s.mode != 'search' else None
        return None

    def root_claim(self, o):
        c = self.x8.claims
        if self.finder is None or not c.declarer or o.controller % 2 != o.contract.declarer % 2 \
                or o.known_hands[o.contract.dummy] is None or len(o.known_hands[o.actor]) > c.cards:
            return None
        state, sure = self.finder.root(o)
        return state, sure

    def allowed(self, o):
        """The legal cards the winning-line logic leaves: all of them, or those that keep a guaranteed contract."""
        if self.claim is not None and self.claim[0] == 'guaranteed':
            return [x for x in o.legal if self.claim[1][x]]
        return list(o.legal)

    # ---- layouts for the rollouts ----------------------------------------------------------
    def read_layouts(self, o, view, source, rng, n):
        """`n` draws of the layouts the Gen 8 search would draw here (Gen7Player.weighted_layouts: the auction through
        the hand-fit scorer, the play through the net's reading), as distinct layouts and their weights. None for a
        source the play does not re-weigh (the caller then keeps to the search)."""
        g, c = self.g7, self.config
        plays = hidden_plays(o, g.play_lead)
        if source == 'list':
            assign = view.every()
            logw = self.layout_log_weights(o, view, assign)
            info = dict(listed=len(assign), effective=_effective(logw))
            if g.play_weight > 0:
                if len(assign) > g.play_max_layouts:
                    index, share = systematic(np.exp(logw - logw.max()), g.play_max_layouts, rng)
                    assign, logw = assign[index], np.log(share)
                logw = logw + g.play_weight * self.play_log_likelihood(o, view, assign, plays)
                info.update(play_decisions=len(plays), play_layouts=len(assign), effective_with_play=_effective(logw))
            w = np.exp(logw - logw.max())
            if len(assign) > n:
                index, weights = systematic(w, n, rng)
            else:
                index, weights = np.arange(len(assign)), w / w.sum()
            return [view.world(assign[i]) for i in index], np.asarray(weights, np.float64), dict(info, source='deal_list')
        if source in ('scorer', 'lead_net') and len(view.hidden) == 2:
            classes = Classes(view)
            logw = classes.logmult + self.type_log_weights(o, view, classes.length, classes.hon, source)
            pool = max(g.early_pool, 2 * n)
            worlds = classes.worlds(spaced(logw, pool, rng.random()), rng)
            info = dict(classes=len(classes), effective=_effective(logw), draws=n, pool=len(worlds), source=source)
            logp = np.zeros(len(worlds))
            if g.early_play_weight > 0 and plays:
                owner = np.zeros(52, np.int8)
                assign = np.empty((len(worlds), len(view.unseen)), np.int8)
                for k, world in enumerate(worlds):
                    owner[list(world[view.hidden[1]])] = 1
                    owner[list(world[view.hidden[0]])] = 0
                    assign[k] = owner[view.unseen]
                fit = self.play_log_likelihood(o, view, assign, plays)
                power = g.early_play_weight
                while _effective(power * fit) < g.early_min_effective and power > 1e-3:
                    power /= 2
                logp = power * fit
                info.update(pick='play-pool', play_decisions=len(plays), play_power=power, effective_with_play=_effective(logp))
            index, share = systematic(np.exp(logp - logp.max()), n, rng)
            worlds, weights = _merge([worlds[i] for i in index], share)
            return worlds, np.asarray(weights, np.float64), info
        return None

    # ---- the winning-line logic at a defender's decision -----------------------------------
    def hand_overs(self, o, worlds, w, reps):
        """(hand[layout, card] 1/0/-1, odds per card or None, the weight of the layouts tested)."""
        c = self.x8.claims
        blank = np.full((len(worlds), len(reps)), -1, np.int8)
        if self.finder is None or not c.defender or o.controller % 2 == o.contract.declarer % 2 or len(o.known_hands[o.actor]) > c.cards:
            return blank, None, 0.
        need = o.contract.level + 6 - o.declarer_tricks
        if need <= 0 or need > 13 - len(o.history) // 4:
            return blank, None, 0.                           # the contract is made or lost whatever is played
        order = np.argsort(-w, kind='stable')[:c.defender]
        hand = self.finder.handovers(o, worlds, reps, allowance=c.defender_ms / 1000, order=order)
        tested = (hand >= 0).all(axis=1)
        cover = float(w[tested].sum())
        if cover <= 0:
            return hand, None, 0.
        return hand, (w[tested] @ (hand[tested] == 1)) / cover, cover / float(w.sum())

    # ---- rollouts --------------------------------------------------------------------------
    def roll(self, o, worlds, w, reps, stage, rng, floor0, race):
        """Roll out `reps` on `worlds`; with `race`, in rounds that drop cards clearly behind. Returns a dict:
        tricks[layout, card] (declarer's, -1 = not played), floor[layout, card], forks, alive (card indices), and counts."""
        n_w, n_c = len(worlds), len(reps)
        claims, cap = self.x8.claims, self.x8.capture
        declaring = o.controller % 2 == o.contract.declarer % 2
        target = o.contract.level + 6
        inside = self.aware(declaring) and claims.leaf > 0
        seats = Seats([self.rollout_net, *self.other_nets], stage.seat, stage.power, seed=int(rng.integers(1 << 62))).start(o)
        other = None
        if self.other_nets:
            other = np.searchsorted(np.cumsum(self.other_share), rng.random(n_w), side='right') + 1
            other[other > len(self.other_nets)] = 0
        tricks = np.full((n_w, n_c), -1, np.int16)
        floor = np.zeros((n_w, n_c), bool)
        ended = np.full((n_w, n_c), -1, np.int16)
        order = rng.permutation(n_w)
        bounds = [n_w]
        if race and stage.race > 0 and n_c > 1 and n_w > stage.first:
            bounds, k = [], stage.first
            while k < n_w:
                bounds.append(k)
                k *= 2
            bounds.append(n_w)
        alive, done, forks, rounds = list(range(n_c)), 0, [], []
        net_rows = asked = 0
        seconds = 0.
        want = cap.forks if cap.level >= 1 else 0
        for b in bounds:
            index = order[done:b]
            share = (b - done) * len(alive) / max(1, n_w * n_c)
            k = min(want - len(forks), int(math.ceil(want * share))) if want else 0
            got = evaluate(o, [worlds[i] for i in index], [reps[j] for j in alive], seats, other=None if other is None else other[index],
                           horizon=stage.horizon, dds=self.dds, finder=self.finder if inside else None, target=target,
                           ask=~floor0[np.ix_(index, alive)], leaf_cards=claims.leaf, leaf_allowance=claims.leaf_ms / 1000,
                           forks=max(k, 0), fork_power=cap.fork_power, rng=rng)
            cell = np.ix_(index, alive)
            tricks[cell], floor[cell], ended[cell] = got.tricks, got.floor, got.ended
            for f in got.forks:
                forks.append((int(index[f.layout]), f))
            net_rows += got.net_rows
            asked += got.asked
            seconds += got.seconds
            done = b
            rounds.append(dict(layouts=int(b), cards=len(alive)))
            if b < n_w and len(alive) > 1:
                seen = order[:done]
                final = self.floored(tricks[np.ix_(seen, alive)], floor[np.ix_(seen, alive)] | floor0[np.ix_(seen, alive)], target)
                lead = int(np.argmax((w[seen] / w[seen].sum()) @ worth(final, o, 'tricks')))
                u = worth(final, o, stage.objective, lead)
                lead = int(np.argmax((w[seen] / w[seen].sum()) @ u))
                behind, se = paired(u, w[seen], lead)
                alive = [j for k, j in enumerate(alive) if k == lead or behind[k] <= stage.slack + stage.race * se[k]]
                if len(alive) == 1:
                    break
        return dict(tricks=tricks, floor=floor | floor0, ended=ended, forks=forks, alive=alive, rounds=rounds, net_rows=net_rows,
                    asked=asked, seconds=seconds)

    @staticmethod
    def floored(tricks, floor, target):
        """Declarer's tricks with the contract floor applied where a guarantee was found."""
        return np.where(floor & (tricks >= 0), np.maximum(tricks, target), tricks)

    def means(self, o, got, w, objective):
        """Per candidate: (value by `objective` over the layouts it was played on, mean of the deciding side's tricks
        there, layouts played, standard error of its deficit to the best)."""
        target = o.contract.level + 6
        final = self.floored(got['tricks'], got['floor'], target)
        played = got['tricks'] >= 0
        count = played.sum(axis=0)
        mean = np.array([float(w[played[:, j]] @ worth(final[played[:, j], j:j + 1], o, 'tricks')[:, 0] / w[played[:, j]].sum()) if count[j] else -np.inf
                         for j in range(final.shape[1])])
        alive = got['alive']
        reference = max(alive, key=lambda j: (mean[j], -j))
        value, se = np.full(final.shape[1], -np.inf), np.zeros(final.shape[1])
        for j in range(final.shape[1]):
            rows = played[:, j] & played[:, reference]
            if not rows.any():
                continue
            u = worth(final[rows][:, [reference, j]], o, objective, 0)
            ww = w[rows] / w[rows].sum()
            value[j] = float(ww @ u[:, 1])
            se[j] = float(paired(u, w[rows], 0)[1][1])
        return value, mean, count, se

    def capture(self, o, note, worlds, w, got):
        cap = self.x8.capture
        if cap.level >= 1 and got is not None:
            note['forks'] = [x8_capture.fork_row(o, worlds[i], f) for i, f in got['forks']]
        if cap.level >= 2 and got is not None:
            note['cap'] = x8_capture.capture_block(o, worlds, w, got['tricks'], got['floor'], cap.layouts)

    def mixes(self, o):
        """Does this seat play a random one of its equal cards?"""
        m = self.x8.mix
        return m.declarer if o.controller % 2 == o.contract.declarer % 2 else m.defender

    def pick(self, o, rng, eligible, logp):
        """One of `eligible`: the net's most probable (the spec's `exploration` as Gen 7's tie-break), or with the mix
        any of them alike. Returns (card, {card: probability of playing it})."""
        eligible = sorted(eligible)
        best = max(float(logp[x]) for x in eligible)
        ties = set(eligible) if self.mixes(o) else {x for x in eligible if best - float(logp[x]) <= 1e-7}
        epsilon = self.spec.get('exploration', 0.)
        probs = {x: epsilon / len(eligible) + (1 - epsilon) * (x in ties) / len(ties) for x in eligible}
        ticket = rng.random()
        for chosen, probability in sorted(probs.items()):
            ticket -= probability
            if ticket <= 0:
                break
        return chosen, probs

    def by_odds(self, order, value, odds, margin):
        """Of the candidate indices `order`, those with the best value; with hand-over odds and a margin, those with
        the lowest odds among the ones within the margin of the best value (and of them the best value)."""
        top = max(value[j] for j in order)
        if odds is None or margin < 0:
            return [j for j in order if top - value[j] <= 1e-9]
        near = [j for j in order if top - value[j] <= margin + 1e-9]
        low = min(odds[j] for j in near)
        near = [j for j in near if odds[j] - low <= 1e-9]
        top = max(value[j] for j in near)
        return [j for j in near if top - value[j] <= 1e-9]

    # ---- a decision from rollouts alone ----------------------------------------------------
    def rollout_decision(self, o, rng, stage):
        started = time.perf_counter()
        nrng = np.random.default_rng(rng.getrandbits(64))
        view = View(o)
        source = self.source(o, view)
        drawn = self.read_layouts(o, view, source, nrng, stage.layouts)
        if drawn is None:
            return None
        worlds, w, info = drawn
        w = w / w.sum()
        layout_seconds = time.perf_counter() - started
        logp = self.net.log_policy([o])[0].astype(np.float64)
        allowed = set(self.allowed(o))
        runs = [[x for x in run if x in allowed] for run in touching(o)]
        runs = [run for run in runs if run]
        mass = np.array([float(np.exp(logp[run]).sum()) for run in runs])
        order = sorted(range(len(runs)), key=lambda i: (-mass[i], runs[i][0]))
        keep = [i for i in order if mass[i] >= stage.prior][:stage.cards]
        if len(keep) < min(2, len(order)):
            keep = order[:min(2, len(order))]
        runs, mass = [runs[i] for i in keep], mass[keep]
        reps = [max(run, key=lambda x: (logp[x], -x)) for run in runs]
        note = dict(v=1, mode='rollout', trick=len(o.history) // 4 + 1, seat=stage.seat, objective=stage.objective, net=self.rollout_name,
                    cards=[symbol(x) for x in reps], runs=[[symbol(x) for x in run] for run in runs], prior=[round(float(m), 4) for m in mass],
                    layouts=len(worlds), claim=self.claim[0] if self.claim else None)
        got, odds = None, None
        if len(reps) > 1:
            before = time.perf_counter()
            hand, odds, cover = self.hand_overs(o, worlds, w, reps)
            claim_seconds = time.perf_counter() - before
            declaring = o.controller % 2 == o.contract.declarer % 2
            floor0 = np.zeros((len(worlds), len(reps)), bool)
            if self.aware(declaring):
                if declaring and self.claim is not None and self.claim[0] == 'guaranteed':
                    floor0[:] = True                        # every candidate keeps the guarantee
                elif not declaring:
                    floor0 = hand == 1
            got = self.roll(o, worlds, w, reps, stage, nrng, floor0, race=True)
            value, mean, count, se = self.means(o, got, w, stage.objective)
            winners = self.by_odds(got['alive'], value, odds, self.x8.claims.odds_margin)
            if self.mixes(o) and self.x8.mix.near > 0:      # close decisions are mixed too: every survivor within `near` of the card chosen
                top = max(value[j] for j in winners)
                winners = [j for j in got['alive'] if top - value[j] <= self.x8.mix.near + 1e-9 and (odds is None or odds[j] <= min(odds[k] for k in winners) + 1e-9)]
            note.update(value=[round(float(v), 4) for v in value], roll=[round(float(m), 4) for m in mean], n=[int(k) for k in count],
                        se=[round(float(s), 4) for s in se], alive=[int(j) for j in got['alive']], rounds=got['rounds'],
                        net_rows=int(got['net_rows']), asked=int(got['asked']), floored=round(float(got['floor'][got['tricks'] >= 0].mean()), 4),
                        ended=int((got['ended'] >= 0).sum()), odds=None if odds is None else [round(float(x), 4) for x in odds],
                        odds_cover=round(cover, 4), seconds=dict(layouts=round(layout_seconds, 4), claims=round(claim_seconds, 4),
                                                                 rollouts=round(got['seconds'], 4)))
        else:
            winners = [0]
            note.update(value=[0.], roll=[None], n=[0], alive=[0], seconds=dict(layouts=round(layout_seconds, 4)))
        eligible = [x for j in winners for x in runs[j]]
        fork = random.Random()                              # the pick's draws come from a copy, as the tree's do
        fork.setstate(rng.getstate())
        chosen, probs = self.pick(o, fork, eligible, logp)
        note.update(chosen=symbol(chosen), mixed=bool(self.mixes(o) and len(eligible) > 1))
        self.capture(o, note, worlds, w, got)
        details = dict(samples=len(worlds), dds_calls=0, dds_nodes=0, objective=stage.objective, batch=True, unique_worlds=len(worlds),
                       near_tie=self.near_tie, behavior_probabilities={symbol(x): float(probs.get(x, 0.)) for x in o.legal},
                       selected_probability=float(probs[chosen]),
                       gen6=dict(info, trick=len(o.history) // 4 + 1, layout_seconds=layout_seconds, dds_seconds=0., settings=asdict(self.config)),
                       gen7=asdict(self.g7), x8=note)
        if self.reference:                                  # an audited bot names the card the net alone would have played
            alone = max(self.allowed(o), key=lambda x: (logp[x], -x))
            details.update(reference_card=symbol(alone), expected_gain_imps=None, prediction_units='rollouts-against-the-net')
        return Decision(chosen, details)

    # ---- the search's decision, corrected by rollouts --------------------------------------
    def search_decision(self, o, rng, solved, weights, before, after, info):
        result = super().search_decision(o, rng, solved, weights, before, after, info)
        stage = self.live
        if stage is not None and stage.mode == 'blend':
            return self.blend_decision(o, rng, result, solved, weights, stage)
        return self.keep_guarantee(o, result)

    def keep_guarantee(self, o, result):
        """The search's decision with its eligible cards cut to those that keep a guaranteed contract (the search's
        best-rated such card when none of its own cards does)."""
        if self.claim is None or self.claim[0] != 'guaranteed':
            if self.claim is not None:
                self.x8_note = dict(v=1, mode='search', claim=self.claim[0])
            return result
        d = result.details
        sure = set(self.allowed(o))
        eligible = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        kept = [x for x in eligible if x in sure]
        moved = not kept
        if moved:
            low = min(d['estimates'][symbol(x)]['gap_to_best'] for x in sure)
            kept = sorted(x for x in sure if d['estimates'][symbol(x)]['gap_to_best'] - low <= 1e-9)
        self.x8_note = dict(v=1, mode='search', claim='guaranteed', moved=moved, sure=[symbol(x) for x in sorted(sure)])
        if kept == eligible:
            return result
        choice = result.card if result.card in kept else kept[0]
        return Decision(choice, dict(d, behavior_probabilities={symbol(x): (1 / len(kept) if x in kept else 0.) for x in o.legal},
                                     selected_probability=1 / len(kept), selected_pimc_gap=d['estimates'][symbol(choice)]['gap_to_best']))

    def blend_decision(self, o, rng, result, solved, weights, stage):
        """The search's decision with its near-best cards valued again by rollouts. Candidates are chosen as the Gen 7
        tree chooses them; the Decision has the same shape, with a short note under `gen7_tree` and the full one
        under `x8`."""
        d, legal = result.details, list(o.legal)
        wd = np.asarray(weights, np.float64)
        wd = wd / wd.sum()
        u = np.array([[row[x] for x in legal] for row in (utilities(o, values) for values, _ in solved)])      # [layout, card]
        allowed = set(self.allowed(o))
        groups = {}                 # cards the solves cannot tell apart: same suit, same result in every layout
        for j, x in enumerate(legal):
            if x in allowed:
                groups.setdefault((x // 13, u[:, j].tobytes()), []).append(j)
        groups = list(groups.values())
        value = np.array([float(wd @ u[:, g[0]]) for g in groups])
        best = float(value.max())
        near = [i for i in range(len(groups)) if best - value[i] <= stage.margin + 1e-9]
        note = dict(v=1, mode='blend', trick=len(o.history) // 4 + 1, seat=stage.seat, trust=stage.trust, net=self.rollout_name,
                    claim=self.claim[0] if self.claim else None)
        if len(near) < 2:
            only = [legal[j] for j in groups[near[0]]]
            kept = self.narrowed(o, result, only)
            self.x8_note = dict(note, cards=[symbol(only[0])], consulted=False, moved=kept.card != result.card)
            return kept
        logp = self.net.log_policy([o])[0].astype(np.float64)
        mass = {i: float(np.exp(logp[[legal[j] for j in groups[i]]]).sum()) for i in near}
        near = sorted(near, key=lambda i: (round(best - value[i], 9), -mass[i], legal[groups[i][0]]))[:stage.cards]
        reps = [legal[max(groups[i], key=lambda j: (logp[legal[j]], -legal[j]))] for i in near]
        fork = random.Random()      # the rollouts' draws come from a copy: the table's own stream is as the search left it
        fork.setstate(rng.getstate())
        nrng = np.random.default_rng(fork.getrandbits(64))
        started = time.perf_counter()
        if stage.layouts:
            view = View(o)
            drawn = self.read_layouts(o, view, self.source(o, view), nrng, stage.layouts)
        else:
            drawn = None
        if drawn is not None:
            worlds, w, _ = drawn
            w = w / w.sum()
        else:
            worlds = self.solved_layouts
            if worlds is None or len(worlds) != len(solved):
                raise RuntimeError('The rollouts were handed solves without their layouts')
            w = wd
        layout_seconds = time.perf_counter() - started
        before = time.perf_counter()
        hand, odds, cover = self.hand_overs(o, worlds, w, reps)
        claim_seconds = time.perf_counter() - before
        declaring = o.controller % 2 == o.contract.declarer % 2
        floor0 = np.zeros((len(worlds), len(reps)), bool)
        if self.aware(declaring):
            if declaring and self.claim is not None and self.claim[0] == 'guaranteed':
                floor0[:] = True
            elif not declaring:
                floor0 = hand == 1
        got = self.roll(o, worlds, w, reps, stage, nrng, floor0, race=False)
        _, mean, count, _ = self.means(o, got, w, 'tricks')
        adjusted = {i: (1 - stage.trust) * float(value[i]) + stage.trust * float(mean[k]) for k, i in enumerate(near)}
        winners = self.by_odds(list(range(len(near))), [adjusted[i] for i in near], odds, self.x8.claims.odds_margin)
        eligible = sorted(legal[j] for k in winners for j in groups[near[k]])
        choice = result.card if result.card in eligible else fork.choice(eligible)
        self.before_tree = result
        note.update(consulted=True, cards=[symbol(x) for x in reps], runs=[[symbol(legal[j]) for j in groups[i]] for i in near],
                    prior=[round(mass[i], 4) for i in near], search=[round(float(value[i]), 4) for i in near],
                    roll=[round(float(m), 4) for m in mean],
                    value=[round(adjusted[i], 4) for i in near], n=[int(k) for k in count], layouts=len(worlds), fresh=drawn is not None,
                    net_rows=int(got['net_rows']), asked=int(got['asked']), floored=round(float(got['floor'][got['tricks'] >= 0].mean()), 4),
                    ended=int((got['ended'] >= 0).sum()), odds=None if odds is None else [round(float(x), 4) for x in odds],
                    odds_cover=round(cover, 4), kept=[symbol(x) for x in eligible],
                    seconds=dict(layouts=round(layout_seconds, 4), claims=round(claim_seconds, 4), rollouts=round(got['seconds'], 4)))
        self.capture(o, note, worlds, w, got)
        self.x8_note = note
        short = dict(kind='x8', consulted=True, layouts=len(worlds), seconds=layout_seconds + claim_seconds + got['seconds'], net_rows=int(got['net_rows']),
                     gen6_cards=sorted(k for k, q in d['behavior_probabilities'].items() if q > 0))
        return Decision(choice, dict(d, behavior_probabilities={symbol(x): (1 / len(eligible) if x in eligible else 0.) for x in legal},
                                     selected_probability=1 / len(eligible),
                                     selected_pimc_gap=d['estimates'][symbol(choice)]['gap_to_best'], gen7_tree=short))

    def narrowed(self, o, result, cards):
        """The search's decision when one candidate is left: its card if it is among `cards`, else those cards."""
        d = result.details
        eligible = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        kept = [x for x in eligible if x in cards] or sorted(cards)
        if kept == eligible:
            return result
        choice = result.card if result.card in kept else kept[0]
        return Decision(choice, dict(d, behavior_probabilities={symbol(x): (1 / len(kept) if x in kept else 0.) for x in o.legal},
                                     selected_probability=1 / len(kept), selected_pimc_gap=d['estimates'][symbol(choice)]['gap_to_best']))

    def break_ties(self, o, rng, result):
        """Gen7Player.break_ties, except that a seat that mixes plays any of the cards left eligible alike."""
        d = result.details
        if not self.mixes(o) or 'behavior_probabilities' not in d or 'estimates' not in d:
            return super().break_ties(o, rng, result)
        eligible = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        if len(eligible) < 2:
            return result
        chosen = eligible[rng.randrange(len(eligible))]
        details = dict(d, selector='x8-mix-' + self.spec['id'], proposal_probabilities=d['behavior_probabilities'],
                       behavior_probabilities={symbol(x): (1 / len(eligible) if x in eligible else 0.) for x in o.legal},
                       selected_probability=1 / len(eligible), selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'])
        if self.reference:                                  # an audited bot names the card it would have played without the mix
            logp = self.net.log_policy([o])[0]
            details.update(reference_card=symbol(max(eligible, key=lambda x: (float(logp[x]), -x))), expected_gain_imps=None,
                           prediction_units='mix-against-the-net')
        return Decision(chosen, details)

    # ---- one decision ----------------------------------------------------------------------
    def choose(self, o, rng):
        self.live, self.claim, self.x8_note = None, None, None
        if len(o.legal) < 2:
            return super().choose(o, rng)
        self.live = self.x8_stage(o)
        self.claim = self.root_claim(o)
        if self.live is not None and self.live.mode == 'rollout':
            result = self.rollout_decision(o, rng, self.live)
            if result is not None:
                return result
            self.live = None                                # no layouts of the kind rollouts need: the search decides
        result = super().choose(o, rng)
        if self.x8_note is not None:
            return Decision(result.card, dict(result.details, x8=self.x8_note))
        return result


X8_KEYS = tuple(f.name for f in fields(Stage))


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: 'gen8x' specs get this engine, every other spec is as before."""
    if spec.get('engine') == ENGINE:
        return X8Player(spec, root, reference)
    return gen7_player(spec, root, reference)
