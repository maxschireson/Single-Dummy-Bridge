"""Gen5 at explicit 32/192 budgets under common and native bidding.

Common and native auction results are separate estimands. Shared trajectories
are stored once and referenced by regime, never duplicated as training samples.
"""
from dataclasses import replace
import time
import numpy as np
from .bidding_env import BidObservation, CALLS, CALL_ID, encode, legal_mask, pack_inputs, deal_key
from .core import Board, auction_contract, imps, normalize_bid
from .fork_audit import collect_board, ForkBudget, stream
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


VULNERABILITIES=('None','NS','EW','Both')


def table_source(systems):
    """A board's auction_source. Unchanged when no system is declared; otherwise it names the systems North-South
    and East-West declared, so that tables which differ only in that are different tables."""
    systems=tuple(systems or (None,None))
    return 'gen5-neural-only' if systems==(None,None) else 'systems:'+'|'.join(s or 'undeclared' for s in systems)


def auction(board, bidders, systems=None):
    """The four seats' bidders bid the board. A bidder is a BEN-format net (`predict`) or a system bidder
    (`call`, bridge_harness/system_bidders.py and rule_bidder.py). `systems` are the systems North-South and
    East-West have declared (Gen 8), or None; a rule system is told whether the other side plays the same system."""
    calls=[]; decisions=[]
    systems=tuple(systems or (None,None))
    same=systems[0] is not None and systems[0]==systems[1]
    bidders=[b.facing(same) if hasattr(b,'facing') else b for b in bidders]
    for _ in range(320):
        seat=(board.dealer+len(calls))%4
        mask=legal_mask(board.dealer,calls)
        if hasattr(bidders[seat],'predict'):
            x=encode(BidObservation(board.hands[seat],seat,board.dealer,board.vulnerability,tuple(calls)))
            xs,lengths=pack_inputs([x])
            raw,_=bidders[seat].predict(xs,lengths)
            action=int(np.argmax(np.where(mask,raw[0],-np.inf)))
        else:
            action=int(bidders[seat].call(board.hands[seat],seat,board.dealer,VULNERABILITIES.index(board.vulnerability),
                                          [CALL_ID[normalize_bid(c)] for c in calls]))
            if not mask[action]:action=CALL_ID['PASS']
        # Greedy behavior has probability one only on its chosen action. The
        # softmax is not a sampling propensity and is not logged as one.
        decisions.append(dict(seat=seat,ply=len(calls),call=CALLS[action],behavior='greedy',behavior_probability=1.))
        calls.append(CALLS[action])
        try:contract=auction_contract(board.dealer,calls)
        except ValueError as e:
            if str(e)!='Incomplete auction':raise
            continue
        return replace(board,contract=contract,auction=tuple(calls),opening_lead=None,
                       auction_source=table_source(systems)),decisions
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
    players={'candidate':player_factory(specs[current],root,specs[reference])}
    if opponent!=current:players['opponent']=player_factory(specs[opponent],root)
    for role,other in (('candidate',opponent),('opponent',current)):
        # A player that keeps settings by opponent type is told who it faces (Gen 8 prototype); others have no `meet`.
        if role in players and hasattr(players[role],'meet'):players[role].meet(other)
    seed=int(digest([manifest['seed'],index,'gen5-play'])[:12],16)
    records={};regimes={};bidding_records={};cache={}
    # Gen 8: manifest['systems'] maps a bot to the bidding system it declares (absent: nothing is declared, as before).
    # manifest['table_systems'], if given, fixes the two directions' systems for this board whoever sits there (a
    # table whose auction was bid beforehand, scripts/gen8_match.py --book).
    declared=manifest.get('systems') or {};fixed=manifest.get('table_systems')
    table=lambda ids:tuple(fixed) if fixed else (declared.get(ids[0]),declared.get(ids[1])) if declared else None
    # with nothing declared the auction is called exactly as before Gen 8
    bid=lambda ids:auction(board,[bidders[v] for v in ids],table(ids)) if declared or fixed else auction(board,[bidders[v] for v in ids])
    common_ids=[manifest.get('common_bidder',current)]*4
    budget=ForkBudget(**(manifest['ben_audit'] if opponent=='ben' else manifest['audit'])); max_forks=budget.max_forks
    try:
        common,common_bids=bid(common_ids)
        for regime in (('self',) if opponent==current else ('common','native')):
            room_ids=[]
            for swapped in ((0,1) if manifest.get('two_self_rooms') or opponent!=current else (0,)):
                room_seed=int(digest([seed,'room',swapped])[:12],16) if manifest.get('independent_room_seeds') else seed
                assignments=['candidate' if opponent==current or s%2==swapped else 'opponent' for s in range(4)]
                native=[current if role=='candidate' else opponent for role in assignments]
                b,decisions=(bid(native) if regime=='native' else (common,common_bids))
                bidder_ids=native if regime=='native' else common_ids
                key=digest([b.to_dict(),assignments,room_seed])
                if key not in cache:
                    if b.contract is None:
                        record=dict(schema_version='v4-passed-out-v1',status='ok',board=b.to_dict(),
                                    assignments=assignments,tables=[dict(ns_score=0,actions=[])],audits=[])
                    else:
                        budget.max_forks=max(0,max_forks-budget.forks)
                        for p in players.values():      # a player that reads auctions by system is told this table's systems
                            if hasattr(p,'seat_table'):p.seat_table(table(bidder_ids))
                        record=collector(b,players,assignments,room_seed,budget,versions)
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
        return dict(board=common.to_dict(),schema='gen5-two-auction-arena-v1',index=index,family=family,split=split(family),
            candidate=current,pair=pair_id(current,opponent),opponent=opponent,versions=versions,manifest_identity=manifest['identity'],regimes=regimes,
            unique_tables=records,bidding=bidding_records,base_cpu=budget.base_cpu,branch_cpu=budget.branch_cpu,
            completed_epoch=time.time(),interpretation='Report common and native separately; self-play supplies training only.')
    finally:
        for player in players.values():player.close()
