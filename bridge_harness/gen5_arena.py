"""Gen5 at explicit 32/192 budgets under common and native bidding.

Common and native auction results are separate estimands. Shared trajectories
are stored once and referenced by regime, never duplicated as training samples.
"""
from dataclasses import replace
import time
import numpy as np
from .bidding_env import BidObservation, CALLS, encode, legal_mask, pack_inputs, deal_key
from .core import Board, auction_contract, imps
from .fork_audit import collect_board, ForkBudget, GapForks, stream
from .mixed_arena import ArenaPlayer, split
from .runner import replay
from .training import digest
from .arena_pairs import pair_id,pair_members


def schedule(manifest, index):
    roster=manifest['roster']
    if len(roster)<2 or len(set(roster))!=len(roster):raise ValueError('Distinct generations required')
    if not 0<=index<manifest['target']:raise ValueError('Outside frozen cohort')
    weights=[2**(len(roster)-2-i) for i in range(len(roster)-1)]+[1]
    block=[v for v,n in zip(roster,weights) for _ in range(n)]
    stream(manifest['seed'],'v4-opponent',index//len(block)).shuffle(block)
    return block[index%len(block)]


def next_roster(roster, candidate, incumbent_lost=False):
    """A loss swaps incumbent/predecessor ranking for the following candidate."""
    old=list(roster)
    if incumbent_lost:old[:2]=old[1::-1]
    return [candidate,*old]


def auction(board, bidders):
    calls=[]; decisions=[]
    for _ in range(320):
        seat=(board.dealer+len(calls))%4
        x=encode(BidObservation(board.hands[seat],seat,board.dealer,board.vulnerability,tuple(calls)))
        mask=legal_mask(board.dealer,calls);xs,lengths=pack_inputs([x])
        raw,_=bidders[seat].predict(xs,lengths)
        action=int(np.argmax(np.where(mask,raw[0],-np.inf)))
        # Greedy behavior has probability one only on its chosen action. The
        # softmax is not a sampling propensity and is not logged as one.
        decisions.append(dict(seat=seat,ply=len(calls),call=CALLS[action],behavior='greedy',behavior_probability=1.))
        calls.append(CALLS[action])
        try:contract=auction_contract(board.dealer,calls)
        except ValueError as e:
            if str(e)!='Incomplete auction':raise
            continue
        return replace(board,contract=contract,auction=tuple(calls),opening_lead=None,
                       auction_source='gen5-neural-only'),decisions
    raise ValueError('Auction exceeded legal length bound')


def run_board(root,manifest,board_dict,index,bidders,player_factory=ArenaPlayer,collector=collect_board):
    """Bidders map immutable generation IDs to already loaded native actors."""
    current,reference=manifest['roster'][:2];opponent=schedule(manifest,index)
    if manifest.get('pair_schedule'):
        pairs=list(manifest['pair_schedule']);stream(manifest['seed'],'pair-block',index//len(pairs)).shuffle(pairs)
        current,opponent=pair_members(pairs[index%len(pairs)])
        reference=manifest['audit_references'][current]
    board=Board.from_dict(board_dict);specs=manifest['bots']
    versions={k:v['identity'] for k,v in specs.items()}
    # Gap forks: only when the manifest asks, only with the standard collector, never on a BEN board
    # (the BEN lane is single and slow). Without the manifest key every record is as before.
    with_ben=any(k=='ben' or specs[k].get('engine')=='ben' for k in (current,opponent))
    gap=GapForks(**manifest['gap_fork']) if manifest.get('gap_fork') and collector is collect_board and not with_ben else None
    if gap is not None and gap.per_band==0:gap=None
    extra={} if gap is None else {'gap':gap}
    players={'candidate':player_factory(specs[current],root,specs[reference])}
    if opponent!=current:players['opponent']=player_factory(specs[opponent],root)
    seed=int(digest([manifest['seed'],index,'gen5-play'])[:12],16)
    records={};regimes={};bidding_records={};cache={}
    budget=ForkBudget(**(manifest['ben_audit'] if with_ben else manifest['audit'])); max_forks=budget.max_forks
    try:
        common,common_bids=auction(board,[bidders[manifest.get('common_bidder',current)]]*4)
        for regime in (('self',) if opponent==current else ('common','native')):
            room_ids=[]
            for swapped in ((0,1) if manifest.get('two_self_rooms') or opponent!=current else (0,)):
                room_seed=int(digest([seed,'room',swapped])[:12],16) if manifest.get('independent_room_seeds') else seed
                assignments=['candidate' if opponent==current or s%2==swapped else 'opponent' for s in range(4)]
                native=[current if role=='candidate' else opponent for role in assignments]
                b,decisions=(auction(board,[bidders[v] for v in native]) if regime=='native' else (common,common_bids))
                bidder_ids=native if regime=='native' else [manifest.get('common_bidder',current)]*4
                key=digest([b.to_dict(),assignments,room_seed])
                if key not in cache:
                    if b.contract is None:
                        record=dict(schema_version='v4-passed-out-v1',status='ok',board=b.to_dict(),
                                    assignments=assignments,tables=[dict(ns_score=0,actions=[])],audits=[])
                    else:
                        budget.max_forks=max(0,max_forks-budget.forks)
                        record=collector(b,players,assignments,room_seed,budget,versions,**extra)
                        if collector is collect_board:replay(record)
                    cache[key]=f'table-{len(records)}';records[cache[key]]=record
                room_ids.append(cache[key])
                bidding_records[f'{regime}/{swapped}']=dict(bidders=bidder_ids,decisions=decisions,
                    calls=list(b.auction),table=cache[key],reward_source='actual-root-table-score',
                    ns_score=records[cache[key]]['tables'][0]['ns_score'])
            delta=None if regime=='self' else (records[room_ids[0]]['tables'][0]['ns_score']-
                                              records[room_ids[1]]['tables'][0]['ns_score'])
            regimes[regime]=dict(tables=room_ids,score_difference=delta,imps=None if delta is None else imps(delta))
        family=deal_key(board.hands,True)
        result=dict(board=common.to_dict(),schema='gen5-two-auction-arena-v1',index=index,family=family,split=split(family),
            candidate=current,pair=pair_id(current,opponent),opponent=opponent,versions=versions,manifest_identity=manifest['identity'],regimes=regimes,
            unique_tables=records,bidding=bidding_records,base_cpu=budget.base_cpu,branch_cpu=budget.branch_cpu,
            completed_epoch=time.time(),interpretation='Report common and native separately; self-play supplies training only.')
        if gap is not None:result.update(gap_cpu=gap.gap_cpu,gap_fork_count=gap.forks)
        return result
    finally:
        for player in players.values():player.close()
