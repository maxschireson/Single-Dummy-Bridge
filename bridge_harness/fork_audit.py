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


def collect_board(board, players, assignments, seed, budget, versions):
    """All branches share one budget; finish admitted tails even if they overrun.

    Common random seeds are keyed by board/ply/controller, not history. Different
    observations may consume streams differently; worlds need not stay equal.
    Audit draws use an entirely separate stream, after a move is committed.
    """
    family=deal_key(board.hands,True);tables=[];pending=[];audits=[];skipped=[]
    started=time.perf_counter();budget_before=(budget.base_cpu,budget.branch_cpu);forks_before=budget.forks

    def play(prefix,forced,depth,node):
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
            if kind=='candidate' and ref is not None:
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
    record=dict(schema_version='random-fork-audit-v1',status='ok',board=board.to_dict(),family=family,
        split='validation' if int(family[:8],16)%5==0 else 'train',assignments=assignments,versions=versions,
        seed=seed,tables=tables,audits=audits,budget_skips=skipped,
        compute=dict(base_cpu=budget.base_cpu-budget_before[0],branch_cpu=budget.branch_cpu-budget_before[1],
            cumulative_base_cpu=budget.base_cpu,cumulative_branch_cpu=budget.branch_cpu,target_multiplier=budget.multiplier,
            finish_admitted_tail=True),seconds=time.perf_counter()-started,
        interpretation='Matched one-move IMP advantages under frozen continuation. Ordinary outcomes are belief data only.')
    replay(record)
    return record
