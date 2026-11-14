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

The opening lead from rollouts (spec['x8']['lead']; Max, 13 Nov 11:29 UTC: "try everything for 512 because you don't
know, and let the rollouts teach you... Same methodology but different parameters"). The same rollout decision with
dummy unseen: the layouts are all three hidden hands, drawn as the Gen 8 search draws them for its own lead (the lead
belief net's samples of declarer and dummy, or the hand-fit scorer's weighted pool where the auction does not fit
that net), and each rollout shows its own layout's dummy from the second card on. The settings are a rollout stage's,
with other defaults: every distinct lead is a candidate (`cards` 13, `prior` 0), each on all of `layouts` 512, and
none is dropped on the way (`race` 0). `capture`: how many of those layouts a level 2 record keeps (0 = the capture
block's `layouts`). Without the block the opening lead is the search's, or the net's where the search is off.

The winning-line logic (spec['x8']['claims'], x8_claims.py), with `cards` or fewer cards in hand:

  declarer    if some card guarantees the contract from the declaring side's own view, only such cards are
              candidates, in every mode. Among them the stage decides as usual.
  defender    for each candidate and each of the `defender` likeliest layouts: would declarer, from its own view in
              that layout, then hold a guaranteed line? The weighted share is the card's hand-over odds. Among cards
              within `odds_margin` of the best value the lowest odds win.
  claims      with `full`: where a card guarantees every trick left, the declaring side plays it, in any contract and mode.
  in rollouts a side that is treated as keeping a guaranteed contract (this bot's own side when it declares; the
              other side when its bot id is listed in `opponents`) has its rollouts floored at the contract from
              the point the guarantee exists: after a guaranteeing root card, after a hand-over, and at the start
              of any later trick with `leaf` or fewer cards where the claim finder says so. A rollout ends when the
              claim finder gives that side every trick left. The floor leaves overtricks as the rollout found them.

Being hard to read (spec['x8']['mix']): a seat that mixes plays any of its equal cards alike, where equal means
the cards the decision leaves eligible (touching cards, and cards rated exactly level), in place of the net's
likeliest of them. `declarer` switches it for the declaring side, whose cards nobody on its own side reads;
`defender` for a defender, whose partner reads the same cards. The record's behavior_probabilities are the
probabilities really used.

How much it mixes (`declarer_power`, `defender_power`; Max, 13 Nov 04:33: randomize only where the net has no
clear preference, trading the information a card gives away against the value given up): among the equal cards,
card x is played with probability proportional to p(x) ** power, p the net's probability. This is the choice that
maximizes  power * E[log p(x)] + H(choice):  the value given up, measured by how far below the net's favourite
the card is in log probability, against the information given away, measured by how predictable the choice is
(its entropy H; an opponent who knows the rule learns at most log n - H nats about which card of n was chosen).
The power is the price ratio: the value of a nat of the net's preference over the price of a nat of information.
Power 0 plays every equal card alike; at 1 the net's own odds; large powers the favourite. A card the net likes
half as much as its favourite is played 2 ** -power as often.

Reading a mixer (`read_declarer`, `read_defender`: opponent ids; partner when `defender` is on): where the play is
read (the deal list's weights, and the early pool), a mixer's card counts as its run of touching cards, each card
of the run equally likely: the probability of the card played in a layout is the net's probability of the whole
run divided by the run's length, the run taken in the hand that played the card as that layout has it. So which
card of a run was played says nothing, and how long the run is still does. With a power, the run's probability is
shared out as the mixer would: the card played gets p(x) ** power / (sum over the run of p(y) ** power) of it. Cards rated exactly level but not
touching are not pooled: telling them needs the mixer's own search.

Capture (spec['x8']['capture'], x8_capture.py): every decision records its candidates and their values; from level
1 also inside-rollout forks, from level 2 the layouts and per-layout results.

With every stage 'search', no claims and no mix the player is Gen7Player with the spec's settings, card for card
(tested).
"""
import copy
from dataclasses import asdict, dataclass, field, fields, replace
import hashlib
import math
from pathlib import Path
import random
import time

import numpy as np

from . import x8_capture, x8_claims
from .core import IMP_LIMITS, card, score, symbol, vulnerable
from .gen6 import Classes, View, _effective, _merge, spaced, systematic
from .gen6_nets import LeadNet
from .gen7 import BIT, Gen7Player, hidden_plays, utilities
from .gen7 import player as gen7_player
from .gen7_net import INPUTS, PolicyNet
from .players import Decision
from .x8_rollout import Seats, evaluate
from . import style as styles

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
    cut: float = 0.             # 'draw': a card under this share of the likeliest card's probability is never drawn
    seat_other: str = ''        # the seats of the side that is not deciding, where they are to differ: 'top' | 'draw' | 'blend'; '' = as `seat`
    power_other: float = 0.     # with seat_other: their exponent; 0 = `power`
    cut_other: float = 0.       # with seat_other: their cut
    objective: str = 'tricks'   # rollout: 'tricks' | 'imps' (the swing against the card with the best mean tricks, layout by layout)
    contracts: str = 'all'      # 'all' | 'games': only in games, slams and doubled contracts; in undoubled partscores the trick is
                                # played as with no stage (the plain search). Max, 13 Nov 05:30, after partscore forks lost in every match

    def __post_init__(self):
        for name in ('from_trick', 'to_trick', 'layouts', 'first', 'cards', 'horizon'):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f'8X stage {name} must be an integer')
        if self.mode not in ('search', 'blend', 'rollout') or self.seat not in ('top', 'draw', 'blend') \
                or self.objective not in ('tricks', 'imps') or self.contracts not in ('all', 'games') \
                or not (1 <= self.from_trick <= self.to_trick <= 13) \
                or not (0 <= self.trust <= 4 and 0 <= self.layouts <= 4096 and 1 <= self.first <= 4096 and 2 <= self.cards <= 13
                        and 0 <= self.prior < 1 and 0 <= self.margin <= 13 and 0 <= self.race <= 100 and 0 <= self.slack <= 13
                        and 0 <= self.horizon <= 13 and 0 < self.power <= 8) \
                or self.seat_other not in ('', 'top', 'draw', 'blend') \
                or not (0 <= self.power_other <= 8 and 0 <= self.cut < 1 and 0 <= self.cut_other < 1):
            raise ValueError('Invalid 8X stage settings')
        if self.mode == 'rollout' and self.layouts < 1:
            raise ValueError('An 8X rollout stage needs layouts')
        if self.mode == 'blend' and self.objective != 'tricks':
            raise ValueError('An 8X blend stage counts tricks, as the search does')


@dataclass(frozen=True)
class ClaimUse:
    cards: int = 0              # the winning-line logic is on, and the declaring side keeps a guarantee, with this many cards or fewer; 0 = off
    declarer: bool = True       # the declaring side keeps a guaranteed contract
    defender: int = 16          # layouts in which each candidate is tested for handing declarer a guarantee; 0 = none
    defender_cards: int = 8     # a defender tests for hand-overs with this many cards or fewer
    defender_ms: int = 400      # time allowed for that test, a decision
    odds_margin: float = .125   # the lowest hand-over odds win among cards within this of the best value (of the card chosen, for `guard`);
                                # below 0 = odds are only recorded
    sample: str = 'uniform'     # the layouts of the hand-over test: 'uniform' (any the defender cannot rule out, nothing read from the
                                # auction or the play, as tested) or 'weighted' (the likeliest of the decision's own layouts)
    contracts: str = 'games'    # where the logic acts, for both sides: 'games' (games, slams and doubled contracts) or 'all' (undoubled
                                # partscores too). Max, 13 Nov 01:42 UTC: act on claims outside undoubled partscores
    guard: bool = False         # a defender's searched card (no rollouts): among cards the search rates within `odds_margin` of it, the
                                # one that hands declarer a guarantee in the fewest layouts; the searched card kept when tied
    full: bool = False          # a claim: where some card guarantees every trick left from the declaring side's view, it is played (the
                                # net's likeliest of them), in any contract and any mode, with no search or rollouts
    leaf: int = 6               # rollouts ask the claim finder at the start of tricks with this many cards or fewer; 0 = never
    leaf_ms: int = 300          # time allowed for one such round of questions
    own: bool = True            # this bot's own side, declaring, is rolled out as keeping a guaranteed contract
    opponents: tuple = ()       # bot ids ('*' = any) whose declaring side is rolled out the same way
    each_ms: int = 1000         # the most one question may take before it is abandoned
    binary: str = ''            # the solver; default the environment's SURE_BIN

    def __post_init__(self):
        object.__setattr__(self, 'opponents', tuple(self.opponents))
        if not (0 <= self.cards <= 13 and 0 <= self.defender <= 4096 and 0 <= self.defender_cards <= 13 and 0 <= self.leaf <= 13
                and self.defender_ms >= 0 and self.leaf_ms >= 0 and self.each_ms > 0 and -1 <= self.odds_margin <= 13
                and self.sample in ('uniform', 'weighted') and self.contracts in ('games', 'all')):
            raise ValueError('Invalid 8X claim settings')


@dataclass(frozen=True)
class CaptureUse:
    level: int = 1              # 0 = values only; 1 = and inside-rollout forks; 2 = and layouts with per-layout results
    forks: int = 8              # forks a decision
    layouts: int = 64           # level 2: at most this many layouts a decision
    fork_power: float = .5      # the forced card is drawn from the net's probabilities raised to this
    audit: str = 'features'     # the reference card an audited bot names for the collector's forks: 'features' = the card plain Gen 8
                                # would have played, only where an 8X feature changed the card; 'gen7' = as Gen7Player names it
    audit_features: tuple = ('rollout', 'blend', 'guarantee', 'odds', 'guard', 'claim')     # features whose changes are forked ('mix'
                                # too to measure mixing: its changes are mostly between touching cards)
    audit_search: bool = False  # rollout decisions: also run the plain Gen 8 search, so the forks' reference is Gen 8's card (else the
                                # net's likeliest card). Costs one search a rollout decision, for audited bots only
    claim_reference: str = 'bot'    # where the winning-line logic changed the card (claim, guarantee, odds, guard): the reference is
                                # 'bot', the card this same bot plays with that logic off (rollouts, the blend, its own search), or
                                # 'search', plain Gen 8's card. Max, 13 Nov 03:01: measure claims against the net, not the search
    mix_share: float = 1.       # of the decisions where only the mix changed the card, the share forked: chosen by a hash of the
                                # position, so no random draw is spent and a replay forks the same ones. Mixing fires about as often
                                # as every other feature together, and its forks roughly doubled 8X's cost (13 Nov)

    def __post_init__(self):
        object.__setattr__(self, 'audit_features', tuple(self.audit_features))
        if self.level not in (0, 1, 2) or not (0 <= self.forks <= 512 and 1 <= self.layouts <= 4096 and 0 <= self.fork_power <= 4) \
                or self.audit not in ('features', 'gen7') or self.claim_reference not in ('bot', 'search') or not 0 <= self.mix_share <= 1 \
                or not set(self.audit_features) <= {'rollout', 'blend', 'guarantee', 'odds', 'guard', 'mix', 'claim'}:
            raise ValueError('Invalid 8X capture settings')


@dataclass(frozen=True)
class MixUse:
    """Being hard to read: which of several equal cards is played."""
    declarer: bool = False      # the declaring side plays a random one of its equal cards (nobody on its side reads them)
    defender: bool = False      # a defender does (its partner reads those cards too: see the module note on reading)
    near: float = 0.            # rollout stages: candidates within this of the best value count as equal
    read_declarer: tuple = ()   # opponent bot ids ('*' = any) whose declaring side mixes: their cards are read as a mixer's
    read_defender: tuple = ()   # the same for opponents' defenders. Partner is read as a mixer when `defender` is on
    declarer_power: float = 0.  # how the declaring side mixes its equal cards: card x with probability proportional to p(x) ** power,
    defender_power: float = 0.  # p the net's probability (Max, 13 Nov 04:33: randomize only where the net has no clear preference;
                                # see the module note). 0 = all alike; large = the net's favourite. A seat read as a mixer is read
                                # with the power of its role here (the bots it is used against share these settings)

    style: dict = field(default_factory=dict)   # a personality (bridge_harness/style.py): among a mixing seat's near-equal
                                # candidates (`near`), the ones this style prefers; the mix then chooses among those. {} = none

    def __post_init__(self):
        object.__setattr__(self, 'read_declarer', tuple(self.read_declarer))
        object.__setattr__(self, 'read_defender', tuple(self.read_defender))
        object.__setattr__(self, 'style', styles.check(self.style))
        if not 0 <= self.near <= 13 or not 0 <= self.declarer_power <= 64 or not 0 <= self.defender_power <= 64:
            raise ValueError('Invalid 8X mix settings')


@dataclass(frozen=True)
class X8Config:
    stages: tuple = ()
    claims: ClaimUse = field(default_factory=ClaimUse)
    capture: CaptureUse = field(default_factory=CaptureUse)
    mix: MixUse = field(default_factory=MixUse)
    others: tuple = ()          # ({'policy': path, 'share': s}, ...): nets that play the other side in a share of the rollouts' layouts
    names: dict = field(default_factory=dict)     # for rollout nets that take who is playing: the name in the net's vocabulary for
                                # this bot ('self') and for each opponent bot id ('*' = any other); unlisted opponents are unknown
    lead: object = None         # a rollout Stage for the opening lead (see the module note), or None: the search's or the net's lead
    lead_capture: int = 0       # level 2 records of that decision keep at most this many layouts; 0 = capture.layouts
    blind: bool = False         # told nothing about who sits against it: every setting keyed by the opponent's bot id (names, the
                                # reading weight of its cards, whether it mixes, whether it keeps guaranteed contracts) takes its
                                # '*' value, as for an opponent never met. `names` may also hold 'they_see': the name the
                                # simulated opponents are told for this bot ('' = nothing); without it they are told `self`


STAGE_ADDED = dict(cut=0., seat_other='', power_other=0., cut_other=0.)     # settings added on 14 November: pinned only where set


LEAD_DEFAULTS = dict(mode='rollout', from_trick=1, to_trick=1, layouts=512, cards=13, prior=0., race=0.)


def x8_settings(block):
    """spec['x8'] -> X8Config. No trick may belong to two stages."""
    block = dict(block or {})
    unknown = set(block) - {'stages', 'claims', 'capture', 'mix', 'others', 'names', 'lead', 'blind'}
    if unknown:
        raise ValueError(f'Unknown 8X settings: {sorted(unknown)}')
    try:
        stages = tuple(Stage(**s) for s in block.get('stages') or ())
        claims = ClaimUse(**(block.get('claims') or {}))
        capture = CaptureUse(**(block.get('capture') or {}))
        mix = MixUse(**(block.get('mix') or {}))
        lead, lead_capture = None, 0
        if block.get('lead') is not None:
            given = dict(block['lead'])
            lead_capture = given.pop('capture', 0)
            lead = Stage(**{**LEAD_DEFAULTS, **given})
    except TypeError as e:
        raise ValueError(f'Unknown 8X setting: {e}') from None
    tricks = [t for s in stages for t in range(s.from_trick, s.to_trick + 1)]
    if len(tricks) != len(set(tricks)):
        raise ValueError('8X stages overlap')
    others = tuple(dict(o) for o in block.get('others') or ())
    if any(set(o) != {'policy', 'share'} or not 0 < o['share'] < 1 for o in others) or sum(o['share'] for o in others) > 1:
        raise ValueError('8X others are {policy, share} with shares that sum to at most 1')
    names = dict(block.get('names') or {})
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in names.items()):
        raise ValueError('8X names map bot ids to names')
    if lead is not None and (lead.mode != 'rollout' or (lead.from_trick, lead.to_trick) != (1, 1) or isinstance(lead_capture, bool)
                             or not isinstance(lead_capture, int) or not 0 <= lead_capture <= 4096):
        raise ValueError('The 8X lead block is a rollout stage (no tricks to name) and a capture count')
    if not isinstance(block.get('blind', False), bool):
        raise ValueError('8X blind is true or false')
    return X8Config(stages, claims, capture, mix, others, names, lead, lead_capture, block.get('blind', False))


def resolved(block):
    """spec['x8'] with every setting written out, defaults included: what a manifest should pin."""
    c = x8_settings(block)
    pinned = lambda s: {k: v for k, v in asdict(s).items() if k not in STAGE_ADDED or v != STAGE_ADDED[k]}
    out = dict(stages=[pinned(s) for s in c.stages], claims=dict(asdict(c.claims), opponents=list(c.claims.opponents)),
               capture=dict(asdict(c.capture), audit_features=list(c.capture.audit_features)),
               mix={k: v for k, v in dict(asdict(c.mix), read_declarer=list(c.mix.read_declarer), read_defender=list(c.mix.read_defender)).items()
                    if k != 'style' or v},
               others=[dict(o) for o in c.others], names=dict(c.names))
    if c.lead is not None:                                  # written only where set: a bot without it pins what it always pinned
        out['lead'] = dict(pinned(c.lead), capture=c.lead_capture)
    if c.blind:
        out['blind'] = True
    return out


def game_or_doubled(k):
    """A game, a slam or a doubled contract (not an undoubled partscore)."""
    return k.doubled > 0 or k.level >= {'N': 3, 'S': 4, 'H': 4, 'D': 5, 'C': 5}[k.strain]


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
        self.finder = x8_claims.shared(c.claims.binary or None) if c.claims.cards or c.claims.guard or c.claims.full else None
        if self.finder is not None:
            self.finder.each = c.claims.each_ms / 1000
        self.live = None            # the stage of the decision in hand
        self.claim = None           # (state, {card: guarantees}) for the decision in hand, when the declaring side decides
        self.x8_note = None

    def meet(self, opponent_id):
        if self.x8.blind:                                   # told nothing about who sits against it: every setting keyed by the
            opponent_id = None                              # opponent's id falls to its '*' value
        super().meet(opponent_id)
        self.opponent_id = opponent_id
        if getattr(self.net, 'vocab', None):                # a table net that takes who is playing (a rollout net as `gen7_policy`)
            names = self.x8.names                           # is told what the rollouts' seats are told: its own cards (a net-alone
            self.net.who = (names.get('self', ''), names.get(opponent_id or '', names.get('*', '')))    # bot's every card) are then that bot's

    def aware(self, declaring):
        """Is the declaring side rolled out as keeping a guaranteed contract? `declaring`: this bot's side declares."""
        c = self.x8.claims
        if self.finder is None:
            return False
        return c.own if declaring else ('*' in c.opponents or self.opponent_id in c.opponents)

    # ---- reading a seat that mixes ---------------------------------------------------------
    def mixers(self, o):
        """The seats whose past cards this bot reads as a mixer's (see the module note)."""
        m, c = self.x8.mix, o.contract
        listed = lambda ids: '*' in ids or self.opponent_id in ids
        if o.controller % 2 == c.declarer % 2:
            return {(c.declarer + 1) % 4, (c.declarer + 3) % 4} if listed(m.read_defender) else set()
        out = {(o.controller + 2) % 4} if m.defender else set()
        if listed(m.read_declarer):
            out.add(c.declarer)
        return out

    def play_log_probabilities(self, o, view, assign, plays=None):
        plays = hidden_plays(o, self.g7.play_lead) if plays is None else plays
        mixers = self.mixers(o)
        if not any(chooser in mixers for _, _, chooser in plays):
            return super().play_log_probabilities(o, view, assign, plays)
        logp, options = np.zeros((len(plays), len(assign))), np.ones((len(plays), len(assign)), np.int64)
        plain = [k for k, (_, _, chooser) in enumerate(plays) if chooser not in mixers]
        if plain:
            lp, op = super().play_log_probabilities(o, view, assign, [plays[k] for k in plain])
            logp[plain], options[plain] = lp, op
        for k, (i, seat, chooser) in enumerate(plays):
            if chooser in mixers:
                logp[k], options[k] = self.pooled_play(o, view, assign, i, seat, chooser)
        return logp, options

    def pooled_play(self, o, view, assign, i, seat, chooser):
        """([layouts] log of the net's probability of play i's run divided by the run's length, or with a power shared out
        as the mixer would, [layouts] legal cards)."""
        c = o.contract
        power = self.mix_power(chooser, c.declarer)
        ident = (o.auction, o.dealer, o.vulnerability, c, o.original_hand(c.dummy))
        if getattr(self, 'mix_cache', (None,))[0] != ident:
            self.mix_cache = (ident, {})
        cache = self.mix_cache[1]
        played = o.history[i][1]
        held = self.held_then(o, view, assign, i, chooser)
        masks = held.astype(np.uint64) @ BIT
        prefix = tuple(o.history[:i + 1])
        keys, values, counts = cache[i][1:] if i in cache and cache[i][0] == prefix else \
            (np.zeros(0, np.uint64), np.zeros(0), np.zeros(0, np.int64))
        where = np.searchsorted(keys, masks).clip(max=max(0, len(keys) - 1))
        known = keys[where] == masks if len(keys) else np.zeros(len(masks), bool)
        logp, options = np.zeros(len(assign)), np.ones(len(assign), np.int64)
        logp[known], options[known] = values[where[known]], counts[where[known]]
        if not known.all():
            batch = self.play_arrays(o, i, seat, chooser, held[~known])
            legal = np.asarray(batch['legal'])
            count = legal.sum(axis=1)
            fresh = np.zeros(len(count))
            choice = count > 1
            if choice.any():
                full = self.net.log_policy_arrays({key: batch[key][choice] for key in INPUTS}).astype(np.float64)
                self.net_rows += int(choice.sum())
                if seat == chooser:
                    hand = held[~known][choice]
                else:                                       # dummy's card: dummy's hand then, the same in every layout
                    hand = np.zeros((int(choice.sum()), 52), bool)
                    hand[:, list(o.original_hand(seat))] = True
                    hand[:, [x for s, x in o.history[:i] if s == seat]] = False
                dead = np.zeros(52, bool)
                dead[[x for _, x in o.history[:i - i % 4]]] = True
                run = np.zeros_like(hand)
                run[:, played] = True
                for step in (1, -1):
                    active = np.ones(len(hand), bool)
                    y = played + step
                    while 0 <= y < 52 and y // 13 == played // 13:
                        ok = active & (hand[:, y] | dead[y])
                        run[:, y] = ok & hand[:, y]
                        active = ok
                        y += step
                p = np.exp(full) * run
                total = np.log(np.maximum(p.sum(axis=1), 1e-30))
                if power > 0:                               # the run's probability shared out as p ** power
                    lr = np.where(run, full, -np.inf)
                    top = lr.max(axis=1)
                    fresh[choice] = total + power * (full[:, played] - top) - np.log(np.exp(power * (lr - top[:, None])).sum(axis=1))
                else:
                    fresh[choice] = total - np.log(run.sum(axis=1))
            logp[~known], options[~known] = fresh, count
            keys, values, counts = np.concatenate([keys, masks[~known]]), np.concatenate([values, fresh]), np.concatenate([counts, count])
            order = np.argsort(keys)
            cache[i] = (prefix, keys[order], values[order], counts[order])
        return logp, options

    # ---- which stage, which claim ----------------------------------------------------------
    def x8_stage(self, o):
        if not o.history or o.known_hands[o.contract.dummy] is None:
            return None
        trick = len(o.history) // 4 + 1
        for s in self.x8.stages:
            if s.from_trick <= trick <= s.to_trick:
                if s.contracts == 'games' and not game_or_doubled(o.contract):
                    return None
                return s if s.mode != 'search' else None
        return None

    def root_claim(self, o):
        c = self.x8.claims
        if self.finder is None or not c.declarer or o.controller % 2 != o.contract.declarer % 2 \
                or o.known_hands[o.contract.dummy] is None or len(o.known_hands[o.actor]) > c.cards or not self.in_class(o):
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
        if not o.history:                                   # the opening lead: three hands hidden, nothing played to read
            return self.lead_layouts(o, view, source, rng, n)
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

    def lead_layouts(self, o, view, source, rng, n):
        """`n` draws of the layouts the Gen 8 search draws for its own opening lead (Gen6Player.layouts): from the lead
        belief net, declarer's and dummy's hands and so partner's; where the auction does not fit that net, uniform
        layouts weighted by the hand-fit scorer, from a pool at least 16 times the draws. Distinct layouts, weights."""
        c = self.config
        if source == 'lead_net':
            leader, context = o.controller, self.leader_context(o)
            worlds = []
            for d, m, q in LeadNet.deal(o.known_hands[leader], self.lead_net.sample(context, n, rng), rng):
                world = [None] * 4
                world[leader], world[(leader + 3) % 4], world[(leader + 1) % 4], world[(leader + 2) % 4] = o.known_hands[leader], d, m, q
                worlds.append(tuple(world))
            worlds, weights = _merge(worlds)
            return worlds, np.asarray(weights, np.float64), dict(draws=n, source='lead_net')
        if source == 'scorer':
            assign = view.uniform(max(c.lead_pool, 16 * n), rng)
            logw = self.layout_log_weights(o, view, assign)
            index, weights = systematic(np.exp(logw - logw.max()), n, rng)
            return ([view.world(assign[i]) for i in index], np.asarray(weights, np.float64),
                    dict(pool=len(assign), effective=_effective(logw), draws=n, source='scorer'))
        return None

    # ---- the winning-line logic at a defender's decision -----------------------------------
    def in_class(self, o):
        """Is the contract one the winning-line logic acts on (`contracts`)?"""
        return self.x8.claims.contracts == 'all' or game_or_doubled(o.contract)

    def defends(self, o):
        """Does the defender's hand-over test apply to this decision?"""
        c, k = self.x8.claims, o.contract
        if self.finder is None or not c.defender or o.controller % 2 == k.declarer % 2 or len(o.known_hands[o.actor]) > c.defender_cards \
                or not self.in_class(o):
            return False
        need = k.level + 6 - o.declarer_tricks
        return 0 < need <= 13 - len(o.history) // 4      # otherwise the contract is made or lost whatever is played

    def hand_overs(self, o, worlds, w, reps, rng):
        """(hand[layout, card] 1/0/-1 on `worlds`, or None when the test used layouts of its own; odds per card or None;
        the share of the layouts that were answered)."""
        c = self.x8.claims
        if not self.defends(o):
            return None, None, 0.
        if c.sample == 'uniform':
            view = View(o)
            test = [view.world(row) for row in view.uniform(c.defender, rng)]
            tw = np.ones(len(test))
            order = None
        else:
            test, tw = worlds, w
            order = np.argsort(-w, kind='stable')[:c.defender]
        hand = self.finder.handovers(o, test, reps, allowance=c.defender_ms / 1000, order=order)
        tested = (hand >= 0).all(axis=1)
        cover = float(tw[tested].sum())
        asked = float(tw[order].sum()) if order is not None else float(tw.sum())
        keep = hand if c.sample == 'weighted' else None
        if cover <= 0:
            return keep, None, 0.
        return keep, (tw[tested] @ (hand[tested] == 1)) / cover, cover / asked

    def guard_decision(self, o, rng, result):
        """The rule the strategy-fusion session tested on the Gen 8 feeds (13 Nov, 674 decisions, +0.225 +- 0.097 IMPs a
        decision; games, slams and doubled contracts +0.535 +- 0.198, undoubled partscores -0.035 +- 0.061): a defender
        looks at the cards its search rates within `odds_margin` of the card it chose and plays the one that hands
        declarer a guaranteed line in the fewest of `defender` layouts it cannot rule out; its own card when tied."""
        c, d = self.x8.claims, result.details
        est = d.get('estimates')
        if not c.guard or not est or not self.defends(o):
            return result
        u = {x: est[symbol(x)]['utility'] for x in o.legal}
        mine = u[result.card]
        near = [x for x in o.legal if abs(u[x] - mine) <= c.odds_margin + 1e-9]
        runs = [[x for x in run if x in near] for run in touching(o)]
        runs = [run for run in runs if run]
        if len(runs) < 2:
            return result
        reps = [result.card if result.card in run else run[0] for run in runs]
        fork = random.Random()                              # the test's draws come from a copy of the table's stream
        fork.setstate(rng.getstate())
        _, odds, cover = self.hand_overs(o, None, None, reps, np.random.default_rng(fork.getrandbits(64)))
        note = dict(cards=[symbol(x) for x in reps], odds=None if odds is None else [round(float(q), 4) for q in odds], cover=round(cover, 4))
        if odds is None:
            return self.with_guard(result, dict(note, moved=False))
        own = next(j for j, run in enumerate(runs) if result.card in run)
        low = min(odds)
        if odds[own] - low <= 1e-9:
            return self.with_guard(result, dict(note, moved=False))
        best = [j for j in range(len(reps)) if odds[j] - low <= 1e-9]
        logp = self.net.log_policy([o])[0]
        j = max(best, key=lambda k: (u[reps[k]], float(logp[reps[k]]), -reps[k]))
        choice = reps[j]
        note.update(moved=True, chosen=symbol(choice))
        moved = Decision(choice, dict(d, behavior_probabilities={symbol(x): float(x == choice) for x in o.legal}, selected_probability=1.,
                                      selected_pimc_gap=est[symbol(choice)]['gap_to_best']))
        return self.with_guard(moved, note)

    def with_guard(self, result, note):
        x8 = dict(result.details.get('x8') or dict(v=1, mode='search', claim=None))
        x8['guard'] = note
        return Decision(result.card, dict(result.details, x8=x8))

    def first_floor(self, o, worlds, reps, hand):
        """[layout, card] rollouts that start with the declaring side holding a guarantee: every candidate when the
        declaring side decides with one; a defender's card where it hands one over (known per layout with `sample`
        'weighted'). Only for a declaring side the bot treats as keeping guarantees."""
        declaring = o.controller % 2 == o.contract.declarer % 2
        floor0 = np.zeros((len(worlds), len(reps)), bool)
        if self.aware(declaring):
            if declaring and self.claim is not None and self.claim[0] == 'guaranteed':
                floor0[:] = True
            elif not declaring and hand is not None:
                floor0 = hand == 1
        return floor0

    # ---- rollouts --------------------------------------------------------------------------
    def roll(self, o, worlds, w, reps, stage, rng, floor0, race):
        """Roll out `reps` on `worlds`; with `race`, in rounds that drop cards clearly behind. Returns a dict:
        tricks[layout, card] (declarer's, -1 = not played), floor[layout, card], forks, alive (card indices), and counts."""
        n_w, n_c = len(worlds), len(reps)
        claims, cap = self.x8.claims, self.x8.capture
        declaring = o.controller % 2 == o.contract.declarer % 2
        target = o.contract.level + 6
        inside = self.aware(declaring) and claims.leaf > 0
        names = self.x8.names
        who = (names.get('self', ''), names.get(self.opponent_id or '', names.get('*', '')))
        other = dict(mode=stage.seat_other, power=stage.power_other or stage.power, cut=stage.cut_other) if stage.seat_other else None
        seats = Seats([self.rollout_net, *self.other_nets], stage.seat, stage.power, seed=int(rng.integers(1 << 62)), who=who,
                      seen=names.get('they_see'), cut=stage.cut, other=other).start(o)
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
            limit = self.x8.lead_capture if not o.history and self.x8.lead_capture else cap.layouts
            note['cap'] = x8_capture.capture_block(o, worlds, w, got['tricks'], got['floor'], limit)

    def mixes(self, o):
        """Does this seat play a random one of its equal cards?"""
        m = self.x8.mix
        return m.declarer if o.controller % 2 == o.contract.declarer % 2 else m.defender

    def mix_power(self, seat, declarer):
        m = self.x8.mix
        return m.declarer_power if seat % 2 == declarer % 2 else m.defender_power

    def mix_shares(self, o, eligible, logp):
        """{card: probability} a mixing seat plays among its equal cards: proportional to p ** power (see the module note)."""
        power = self.mix_power(o.controller, o.contract.declarer)
        lp = np.array([float(logp[x]) for x in eligible])
        w = np.exp(power * (lp - lp.max())) if power > 0 else np.ones(len(eligible))
        return dict(zip(eligible, w / w.sum()))

    def pick(self, o, rng, eligible, logp):
        """One of `eligible`: the net's most probable (the spec's `exploration` as Gen 7's tie-break), or with the mix
        any of them alike. Returns (card, {card: probability of playing it})."""
        eligible = sorted(eligible)
        best = max(float(logp[x]) for x in eligible)
        if self.mixes(o):
            share = self.mix_shares(o, eligible, logp)
        else:
            ties = {x for x in eligible if best - float(logp[x]) <= 1e-7}
            share = {x: (x in ties) / len(ties) for x in eligible}
        epsilon = self.spec.get('exploration', 0.)
        probs = {x: epsilon / len(eligible) + (1 - epsilon) * share[x] for x in eligible}
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
        if not o.history:
            note['lead'] = True                             # the opening lead: its layouts are three hands each (x8_capture)
        got, odds = None, None
        if len(reps) > 1:
            before = time.perf_counter()
            hrng = np.random.default_rng(nrng.integers(1 << 62))     # drawn whether or not the test runs: the rollouts' draws stay put
            hand, odds, cover = self.hand_overs(o, worlds, w, reps, hrng)
            claim_seconds = time.perf_counter() - before
            floor0 = self.first_floor(o, worlds, reps, hand)
            got = self.roll(o, worlds, w, reps, stage, nrng, floor0, race=True)
            value, mean, count, se = self.means(o, got, w, stage.objective)
            winners = self.by_odds(got['alive'], value, odds, self.x8.claims.odds_margin)
            note['odds_moved'] = winners != self.by_odds(got['alive'], value, None, 0.)
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
        if self.x8.mix.style and len(winners) > 1:          # a personality: of its near-equal candidates, the ones its style prefers
            kept = set(styles.choose(o, [reps[j] for j in winners], self.x8.mix.style, float(nrng.random())))
            note['styled'] = [symbol(reps[j]) for j in winners]
            winners = [j for j in winners if reps[j] in kept]
        eligible = [x for j in winners for x in runs[j]]
        fork = random.Random()                              # the pick's draws come from a copy, as the tree's do
        fork.setstate(rng.getstate())
        chosen, probs = self.pick(o, fork, eligible, logp)
        likeliest = max(eligible, key=lambda x: (logp[x], -x))
        note.update(chosen=symbol(chosen), mixed=bool(self.mixes(o) and len(eligible) > 1), mix_moved=bool(self.mixes(o) and chosen != likeliest),
                    narrowed=len(self.allowed(o)) < len(o.legal))
        self.capture(o, note, worlds, w, got)
        details = dict(samples=len(worlds), dds_calls=0, dds_nodes=0, objective=stage.objective, batch=True, unique_worlds=len(worlds),
                       near_tie=self.near_tie, behavior_probabilities={symbol(x): float(probs.get(x, 0.)) for x in o.legal},
                       selected_probability=float(probs[chosen]),
                       gen6=dict(info, trick=len(o.history) // 4 + 1, layout_seconds=layout_seconds, dds_seconds=0., settings=asdict(self.config)),
                       gen7=asdict(self.g7), x8=note)
        note['reference'] = symbol(max(self.allowed(o), key=lambda x: (logp[x], -x)))     # the net's own card, for the audit
        return Decision(chosen, details)

    # ---- the search's decision, corrected by rollouts --------------------------------------
    def search_decision(self, o, rng, solved, weights, before, after, info):
        result = super().search_decision(o, rng, solved, weights, before, after, info)
        self.raw = result                                   # the search's own decision, before any 8X feature
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
        self.x8_note = dict(v=1, mode='search', claim='guaranteed', moved=moved, narrowed=kept != eligible, sure=[symbol(x) for x in sorted(sure)])
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
                    claim=self.claim[0] if self.claim else None, narrowed=len(allowed) < len(legal))
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
        hrng = np.random.default_rng(nrng.integers(1 << 62))
        hand, odds, cover = self.hand_overs(o, worlds, w, reps, hrng)
        claim_seconds = time.perf_counter() - before
        floor0 = self.first_floor(o, worlds, reps, hand)
        got = self.roll(o, worlds, w, reps, stage, nrng, floor0, race=False)
        _, mean, count, _ = self.means(o, got, w, 'tricks')
        adjusted = {i: (1 - stage.trust) * float(value[i]) + stage.trust * float(mean[k]) for k, i in enumerate(near)}
        winners = self.by_odds(list(range(len(near))), [adjusted[i] for i in near], odds, self.x8.claims.odds_margin)
        plain_winners = self.by_odds(list(range(len(near))), [adjusted[i] for i in near], None, 0.)
        eligible = sorted(legal[j] for k in winners for j in groups[near[k]])
        searched = {card(k) for k, q in d['behavior_probabilities'].items() if q > 0}
        blend_moved = {legal[j] for k in plain_winners for j in groups[near[k]]} != searched
        choice = result.card if result.card in eligible else fork.choice(eligible)
        self.before_tree = result
        note.update(consulted=True, cards=[symbol(x) for x in reps], runs=[[symbol(legal[j]) for j in groups[i]] for i in near],
                    prior=[round(mass[i], 4) for i in near], search=[round(float(value[i]), 4) for i in near],
                    roll=[round(float(m), 4) for m in mean],
                    value=[round(adjusted[i], 4) for i in near], n=[int(k) for k in count], layouts=len(worlds), fresh=drawn is not None,
                    net_rows=int(got['net_rows']), asked=int(got['asked']), floored=round(float(got['floor'][got['tricks'] >= 0].mean()), 4),
                    ended=int((got['ended'] >= 0).sum()), odds=None if odds is None else [round(float(x), 4) for x in odds],
                    odds_cover=round(cover, 4), kept=[symbol(x) for x in eligible], blend_moved=blend_moved,
                    odds_moved=winners != plain_winners,
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
        if self.tie_state is None:
            self.tie_state = rng.getstate()                 # the stream as the table's own tie-break finds it
        d = result.details
        if not self.mixes(o) or 'behavior_probabilities' not in d or 'estimates' not in d:
            return super().break_ties(o, rng, result)
        eligible = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        if len(eligible) < 2:
            return result
        if self.mix_power(o.controller, o.contract.declarer) > 0:
            logp = self.net.log_policy([o])[0]
            share = self.mix_shares(o, eligible, logp)
            ticket, chosen = rng.random(), eligible[-1]
            for x in eligible:
                ticket -= share[x]
                if ticket <= 0:
                    chosen = x
                    break
        else:                                               # all alike: the draw as before powers existed
            chosen = eligible[rng.randrange(len(eligible))]
            logp = self.net.log_policy([o])[0]
            share = {x: 1 / len(eligible) for x in eligible}
        likeliest = max(eligible, key=lambda x: (float(logp[x]), -x))
        details = dict(d, selector='x8-mix-' + self.spec['id'], proposal_probabilities=d['behavior_probabilities'],
                       behavior_probabilities={symbol(x): float(share.get(x, 0.)) for x in o.legal},
                       selected_probability=float(share[chosen]), selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'],
                       x8_mix_moved=chosen != likeliest)
        if self.reference:                                  # an audited bot names the card it would have played without the mix
            details.update(reference_card=symbol(likeliest), expected_gain_imps=None, prediction_units='mix-against-the-net')
        return Decision(chosen, details)

    def claim_card(self, o):
        """With claims.full, the declaring side to play and a card that guarantees every trick left from its own view: the
        net's likeliest such card. Otherwise None."""
        c = self.x8.claims
        if not c.full or self.finder is None or o.controller % 2 != o.contract.declarer % 2 or o.known_hands[o.contract.dummy] is None:
            return None
        left = len(o.known_hands[o.actor])
        if left > max(c.cards, 1) or len(o.legal) < 2:
            return None
        state, sure = self.finder.root(o, need=left)
        if state != 'guaranteed':
            return None
        logp = self.net.log_policy([o])[0]
        return max((x for x in o.legal if sure[x]), key=lambda x: (float(logp[x]), -x))

    # ---- one decision ----------------------------------------------------------------------
    def choose(self, o, rng):
        self.live, self.claim, self.x8_note, self.raw, self.tie_state = None, None, None, None, None
        self.start_state = rng.getstate()
        if len(o.legal) < 2:
            return super().choose(o, rng)
        claimed = self.claim_card(o)
        if claimed is not None:
            note = dict(v=1, mode='claim', trick=len(o.history) // 4 + 1, chosen=symbol(claimed))
            result = Decision(claimed, dict(samples=0, dds_calls=0, behavior_probabilities={symbol(x): float(x == claimed) for x in o.legal},
                                            selected_probability=1., gen7=asdict(self.g7), x8=note))
            return self.audited(o, result)
        self.live = self.x8_stage(o)
        self.claim = self.root_claim(o)
        stage = self.live if self.live is not None and self.live.mode == 'rollout' else None
        if not o.history and self.x8.lead is not None and (self.x8.lead.contracts == 'all' or game_or_doubled(o.contract)):
            stage = self.x8.lead                            # the opening lead from rollouts
        if stage is not None:
            result = self.rollout_decision(o, rng, stage)
            if result is not None:
                return self.audited(o, result)
            self.live = None                                # no layouts of the kind rollouts need: the search decides
        result = super().choose(o, rng)
        if self.x8_note is not None:
            result = Decision(result.card, dict(result.details, x8=self.x8_note))
        if self.x8.claims.guard and (self.x8_note is None or self.x8_note.get('odds') is None):
            result = self.guard_decision(o, rng, result)
        return self.audited(o, result)

    def plain_card(self, o):
        """The card plain Gen 8 (this spec's search, the net's tie-break, no 8X feature) would have played here, or None
        when the search did not run."""
        if self.raw is None or self.tie_state is None:
            return None
        stream = random.Random()
        stream.setstate(self.tie_state)
        return Gen7Player.break_ties(self, o, stream, self.raw).card

    def unclaimed_card(self, o):
        """The card this bot plays here with the decision-level winning-line logic off (the declarer's guarantee, full
        claims, the defender's hand-over odds and rule; the claim floors inside rollouts stay), from the same random
        stream: rollouts at a rollout trick, the blend at a blend trick, the search elsewhere."""
        if getattr(self, 'unclaimed_player', None) is None:
            shadow = copy.copy(self)
            claims = replace(self.x8.claims, declarer=False, full=False, defender=0, guard=False)
            shadow.x8 = replace(self.x8, claims=claims)
            shadow.reference = None                         # no audit inside the shadow
            self.unclaimed_player = shadow
        stream = random.Random()
        stream.setstate(self.start_state)
        return X8Player.choose(self.unclaimed_player, o, stream).card

    def gen8_card(self, o):
        """The card this spec's search would play as a plain Gen7Player (no 8X feature), from the same random stream."""
        if getattr(self, 'plain_player', None) is None:
            self.plain_player = copy.copy(self)
            self.plain_player.__class__ = Gen7Player
        stream = random.Random()
        stream.setstate(self.start_state)
        return Gen7Player.choose(self.plain_player, o, stream).card

    def features(self, o, result):
        """The 8X features that acted on this decision."""
        note = result.details.get('x8') or {}
        out = {'rollout': ['rollout'], 'claim': ['claim']}.get(note.get('mode'), [])
        if note.get('mode') == 'blend' and note.get('blend_moved'):
            out.append('blend')
        if note.get('claim') == 'guaranteed' and (note.get('narrowed') or note.get('moved')):
            out.append('guarantee')
        if note.get('odds_moved'):
            out.append('odds')
        if (note.get('guard') or {}).get('moved'):
            out.append('guard')
        if result.details.get('x8_mix_moved') or note.get('mix_moved'):
            out.append('mix')
        return out

    def mix_forked(self, o):
        """Is a decision changed by the mix alone forked? capture.mix_share of them, by a hash of the position."""
        share = self.x8.capture.mix_share
        if share >= 1:
            return True
        key = repr((tuple((int(a), int(b)) for a, b in o.history), int(o.controller),
                    tuple(int(x) for x in o.known_hands[o.actor]))).encode()
        return int.from_bytes(hashlib.sha256(key).digest()[:4], 'big') < share * 2 ** 32

    def audited(self, o, result):
        """With capture.audit 'features': name as reference card the card plain Gen 8 would have played, where an 8X
        feature changed the card, so the collector's forks (fork_audit.collect_board) play it out from the same
        position; elsewhere name none, so nothing else is forked."""
        if not self.reference or self.x8.capture.audit != 'features' or len(o.legal) < 2:
            return result
        d = dict(result.details)
        for key in ('reference_card', 'expected_gain_imps', 'prediction_units'):
            d.pop(key, None)
        note = d.get('x8')
        fired = self.features(o, result)
        claimed = set(fired) & {'claim', 'guarantee', 'odds', 'guard'}
        if claimed and self.x8.capture.claim_reference == 'bot':
            plain = self.unclaimed_card(o)
            if plain != result.card and claimed & set(self.x8.capture.audit_features):
                d.update(reference_card=symbol(plain), expected_gain_imps=None, prediction_units='x8-against-no-claims', x8_features=fired)
            return Decision(result.card, d)
        if note and note.get('mode') in ('rollout', 'claim'):   # no search ran
            if self.x8.capture.audit_search or note['mode'] == 'claim':
                plain = self.gen8_card(o)                   # what plain Gen 8 would play here, searched now for the audit
            else:
                plain = card(note['reference']) if note.get('reference') else None
        else:
            plain = self.plain_card(o)
        forked = set(fired) & set(self.x8.capture.audit_features)
        if forked == {'mix'} and not self.mix_forked(o):
            forked = set()
        if plain is not None and plain != result.card and forked:
            d.update(reference_card=symbol(plain), expected_gain_imps=None, prediction_units='x8-against-plain', x8_features=fired)
        return Decision(result.card, d)


X8_KEYS = tuple(f.name for f in fields(Stage))


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: 'gen8x' specs get this engine, every other spec is as before."""
    if spec.get('engine') == ENGINE:
        return X8Player(spec, root, reference)
    return gen7_player(spec, root, reference)
