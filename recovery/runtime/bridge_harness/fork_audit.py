"""Random, post-commit one-move audits under a shared recursive compute budget.

Audits compare policy choices, holding beliefs/search and continuation players
fixed. They are local advantages, not a whole-agent tournament result.
"""
from dataclasses import dataclass
import hashlib
import json
import random
import time

from .core import Game, SEATS, card, imps, symbol
from .players import Decision
from .policy_selector import SelectorWeights
from .auction_policy import AuctionPolicyPlayer
from .public_belief_player import PublicBeliefPlayer
from .bidding_env import deal_key
from .runner import replay


def stream(seed, *parts):
    payload=json.dumps([seed,*parts],sort_keys=True).encode()
    return random.Random(int.from_bytes(hashlib.sha256(payload).digest(),'big'))


class DraftPlayer(AuctionPolicyPlayer):
    def __init__(self, belief, policy, reference, **kwargs):
        super().__init__(belief,policy,**kwargs)
        self.reference=SelectorWeights(reference)

    def choose(self,o,rng):
        result=super().choose(o,rng);d=dict(result.details)
        if d.get('forced') or len(d.get('selector_predictions',{}))<2:return result
        reference_details=dict(d,behavior_probabilities=d['proposal_probabilities'])
        # Frozen incumbent chooses from the EXACT same PIMC search estimates.
        ref,_=self.reference.choose(o,reference_details,rng)
        d.update(selector='direct-auction-policy-bootstrap',reference_card=symbol(ref),
            expected_gain_imps=None, prediction_units='remaining-partnership-tricks',
            predicted_trick_difference=d['selector_predictions'][symbol(result.card)]-d['selector_predictions'][symbol(ref)])
        return Decision(result.card,d)


@dataclass
class ForkBudget:
    probability: float=.5
    multiplier: float=3.
    max_depth: int=2
    max_forks: int=64
    base_cpu: float=0.
    branch_cpu: float=0.
    forks: int=0

    def __post_init__(self):
        if not 0<=self.probability<=1 or self.multiplier<1 or self.max_depth<0 or self.max_forks<0:
            raise ValueError('Invalid audit budget')

    def coin(self,rng,depth):
        # No prediction, importance flag, hidden deal or outcome is accepted.
        return depth<self.max_depth and rng.random()<self.probability

    def admit(self,estimate,board_forks=0):
        allowance=(self.multiplier-1)*self.base_cpu-self.branch_cpu
        return board_forks<self.max_forks and allowance>0 and estimate<=allowance


def audited_gain(candidate_score, reference_score, actor):
    return imps((candidate_score-reference_score)*(1 if actor%2==0 else -1))


GAP_SELECTION='gap-banded-post-commit'


@dataclass
class GapForks:
    """Forks to a strictly inferior card, banded by the actor's own search gap.

    The audits above only ever swap one exactly tied card for another. These forks
    supply (a) the search's estimates in positions that follow an inferior card and
    (b) realized cost against estimated gap. They are drawn after the root table and
    every audit on it is complete, from their own stream, and never charge ForkBudget:
    play and audits are identical with or without them. One instance per board.
    """
    per_band: int=2
    bands: tuple=(.125,.5)
    max_cpu_share: float=1.5
    gap_cpu: float=0.
    forks: int=0

    def __post_init__(self):
        self.bands=tuple(float(b) for b in self.bands)
        if self.per_band<0 or self.max_cpu_share<0 or any(b<=0 for b in self.bands) or list(self.bands)!=sorted(set(self.bands)):
            raise ValueError('Invalid gap-fork settings')

    def band(self,gap):
        """Band 0 is (0, bands[0]], band i is (bands[i-1], bands[i]], the last is open-ended."""
        for i,edge in enumerate(self.bands):
            if gap<=edge+1e-9:return i
        return len(self.bands)


def gap_eligible(action):
    """A committed Gen 6 search decision with at least one strictly inferior legal card."""
    if any(action.get(k) for k in ('replayed_prefix','counterfactual_forced','forced','fixed_opening_lead')):return False
    return bool(action.get('gen6')) and any(e['gap_to_best']>1e-9
        for c,e in (action.get('estimates') or {}).items() if c!=action['card'])


def gap_picks(actions, config, rng):
    """Per band: up to per_band decisions without replacement, then one card of that band each.

    Works from recorded actions alone, so the same draw can be repeated on archived tables.
    propensity is the probability that this (decision, card) was picked.
    """
    by_band={}
    for action in actions:
        if not gap_eligible(action):continue
        for c,e in sorted(action['estimates'].items()):
            if c!=action['card'] and e['gap_to_best']>1e-9:
                by_band.setdefault(config.band(e['gap_to_best']),{}).setdefault(action['ply'],[]).append(c)
    picks=[]
    for band in sorted(by_band):
        decisions=sorted(by_band[band])
        for ply in rng.sample(decisions,min(config.per_band,len(decisions))):
            cards=by_band[band][ply]
            picks.append(dict(ply=ply,forced_card=cards[rng.randrange(len(cards))],band=band,
                decisions_in_band=len(decisions),cards_in_band=len(cards),
                propensity=min(1.,config.per_band/len(decisions))/len(cards)))
    # Random order, so a budget stop is not correlated with the band.
    rng.shuffle(picks)
    return picks


def collect_board(board, players, assignments, seed, budget, versions, gap=None):
    """All branches share one budget; finish admitted tails even if they overrun.

    Common random seeds are keyed by board/ply/controller, not history. Different
    observations may consume streams differently; worlds need not stay equal.
    Audit draws use an entirely separate stream, after a move is committed.
    Gap forks (see GapForks) come last and touch neither that stream nor the budget.
    """
    family=deal_key(board.hands,True);tables=[];pending=[];audits=[];skipped=[]
    started=time.perf_counter();budget_before=(budget.base_cpu,budget.branch_cpu);forks_before=budget.forks

    def play(prefix,forced,depth,node,audit=True,fork_kind=None):
        game=Game(board);actions=[];candidates=[];cpu_start=time.process_time();wall=time.perf_counter()
        for previous in prefix:
            game.play(card(previous['card']));actions.append(dict(previous,replayed_prefix=True))
        if forced is not None:
            o=game.observation();game.play(forced)
            actions.append(dict(ply=len(actions),seat=SEATS[o.actor],controller=SEATS[o.controller],
                player=assignments[o.controller],card=symbol(forced),seconds=0.,cpu_seconds=0.,counterfactual_forced=True))
        while not game.done:
            o=game.observation();ply=len(actions);kind=assignments[o.controller]
            before=time.process_time();w=time.perf_counter()
            if ply==0 and board.opening_lead is not None:
                result=Decision(board.opening_lead,{'fixed_opening_lead':True})
            else:result=players[kind].choose(o,stream(seed,'play',board.id,ply,o.controller))
            # Committed move exists before the independent audit draw.
            detail=dict(result.details);ref=detail.get('reference_card')
            if audit and kind=='candidate' and ref is not None:
                audit_rng=stream(seed,'audit',family,node,ply)
                chosen=budget.coin(audit_rng,depth)
                detail.update(audit_draw=chosen,audit_probability=budget.probability if depth<budget.max_depth else 0.,
                    committed_before_audit=True)
                if chosen:candidates.append(dict(ply=ply,actor=o.actor,depth=depth,priority=audit_rng.random()))
            game.play(result.card)
            actions.append(dict(ply=ply,seat=SEATS[o.actor],controller=SEATS[o.controller],player=kind,
                card=symbol(result.card),seconds=time.perf_counter()-w,cpu_seconds=time.process_time()-before,**detail))
        table=dict(status='ok',actions=actions,declarer_tricks=game.declarer_tricks,ns_score=game.ns_score(),
            seconds=time.perf_counter()-wall,cpu_seconds=time.process_time()-cpu_start,depth=depth,node=node)
        if fork_kind is not None:table['fork_kind']=fork_kind
        index=len(tables);tables.append(table)
        for candidate in candidates:pending.append(dict(candidate,table=index))
        return index

    root=play([],None,0,'root');budget.base_cpu+=tables[root]['cpu_seconds']
    while pending:
        # Random priorities avoid always spending the allowance on early play.
        pending.sort(key=lambda e:e['priority']);e=pending.pop(0)
        t=tables[e['table']];ply=e['ply'];action=t['actions'][ply];ref=card(action['reference_card'])
        event=dict(parent_table=e['table'],ply=ply,actor=e['actor'],depth=e['depth'],
            candidate_card=action['card'],reference_card=symbol(ref),audit_probability=action['audit_probability'],
            expected_gain_imps=action.get('expected_gain_imps'),selection='independent-random-post-commit')
        if action['card']==symbol(ref):
            audits.append(dict(event,candidate_table=e['table'],reference_table=e['table'],gain_imps=0,identical_action=True))
            continue
        estimate=sum(z.get('cpu_seconds',0.) for z in t['actions'][ply+1:])
        if not budget.admit(estimate,budget.forks-forks_before):
            skipped.append(dict(event,reason='shared-compute-budget',estimated_cpu=estimate));continue
        budget.forks+=1
        other=play(t['actions'][:ply],ref,e['depth']+1,f"{t['node']}/{ply}")
        budget.branch_cpu+=tables[other]['cpu_seconds']
        audits.append(dict(event,candidate_table=e['table'],reference_table=other,identical_action=False,
            gain_imps=audited_gain(t['ns_score'],tables[other]['ns_score'],e['actor']),
            rollout_cpu=tables[other]['cpu_seconds'],estimated_cpu=estimate))
    gap_active=gap is not None and gap.per_band>0;gap_forks=[];gap_cpu=0.
    if gap_active:
        # After every audit, from the root table only. No audit and no further gap fork is drawn inside.
        t=tables[root];cap=gap.max_cpu_share*t['cpu_seconds'];declarer=board.contract.declarer
        for pick in gap_picks(t['actions'],gap,stream(seed,'gap-fork',family,'root')):
            ply=pick['ply'];action=t['actions'][ply];forced=pick['forced_card'];actor=SEATS.index(action['seat'])
            event=dict(pick,parent_table=root,actor=actor,chosen_card=action['card'],
                estimated_gap=action['estimates'][forced]['gap_to_best'],band_edges=list(gap.bands),
                per_band=gap.per_band,selection=GAP_SELECTION,
                estimated_cpu=sum(z.get('cpu_seconds',0.) for z in t['actions'][ply+1:]))
            if gap_cpu>cap:
                # Checked against CPU already spent, never against this fork's estimate, so a costly
                # early fork (an opening lead, say) is as likely to run as a cheap late one.
                skipped.append(dict(event,reason='gap-fork-budget'));continue
            # The prefix is stored as bare cards: its search details already sit in the root table.
            prefix=[{k:z[k] for k in ('ply','seat','controller','player','card')} for z in t['actions'][:ply]]
            other=play(prefix,card(forced),1,f"root/gap/{ply}/{forced}",audit=False,fork_kind='gap')
            cost=tables[other]['cpu_seconds'];gap_cpu+=cost;gap.gap_cpu+=cost;gap.forks+=1
            side=(lambda table:table['declarer_tricks'] if actor%2==declarer%2 else 13-table['declarer_tricks'])
            gap_forks.append(dict(event,fork_table=other,realized_cost_tricks=side(t)-side(tables[other]),
                realized_cost_imps=audited_gain(t['ns_score'],tables[other]['ns_score'],actor),rollout_cpu=cost))
    record=dict(schema_version='random-fork-audit-v1',status='ok',board=board.to_dict(),family=family,
        split='validation' if int(family[:8],16)%5==0 else 'train',assignments=assignments,versions=versions,
        seed=seed,tables=tables,audits=audits,budget_skips=skipped,
        compute=dict(base_cpu=budget.base_cpu-budget_before[0],branch_cpu=budget.branch_cpu-budget_before[1],
            cumulative_base_cpu=budget.base_cpu,cumulative_branch_cpu=budget.branch_cpu,target_multiplier=budget.multiplier,
            finish_admitted_tail=True),seconds=time.perf_counter()-started,
        interpretation='Matched one-move IMP advantages under frozen continuation. Ordinary outcomes are belief data only.')
    if gap_active:
        # Kept out of `audits`: every consumer of that list assumes a tie against the reference policy.
        record['gap_forks']=gap_forks;record['compute']['gap_cpu']=gap_cpu
    replay(record)
    return record
