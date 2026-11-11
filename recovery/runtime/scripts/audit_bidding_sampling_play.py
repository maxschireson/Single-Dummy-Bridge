#!/usr/bin/env python3
"""Audit paired play and measure beliefs on the actual public play histories."""
import argparse
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.core import Board, Game, card
from bridge_harness.training import digest, split_for
from bridge_harness.runner import replay
from bridge_harness.bidding_sampling import AuctionWeights, WeightedSampler
from scripts.evaluate_bidding_sampling import metrics


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();root=args.run;protocol=json.loads((root/'protocol.json').read_text())
    prior=AuctionWeights(root/'auction_weights.npz');records=[];seen=set();observations=[];decisions=0;worlds=0
    for path in sorted((root/'episodes').glob('*.json.gz')):
        with gzip.open(path,'rt') as f:r=json.load(f)
        b=Board.from_dict(r['board']);did=digest(b.hands)
        assert did not in seen and split_for(b)=='test';seen.add(did)
        assert r['status']=='ok' and len(r['tables'])==2
        assert r['config']['samples']==32 and r['config']['batch'] and r['config']['near_tie']==.125
        assert r['config']['objective']=='tricks' and r['config']['strength']==1.
        replay(r);records.append(r)
        for table_index,table in enumerate(r['tables']):
            g=Game(b)
            for a in table['actions']:
                o=g.observation()
                if len(o.legal)>1:
                    assert a['samples']==32 and a['dds_calls']==32 and a['batch']
                    decisions+=1;worlds+=a['dds_calls']
                g.play(card(a['card']))
                if len(g.history) not in (1,12,24,36,44):continue
                actual=g.observation();truth=np.full(52,-1,int)
                for seat,hand in enumerate(g.hands):truth[list(hand)]=seat
                for observer in range(4):
                    if observer==b.contract.dummy:continue
                    known=[None]*4;known[observer]=tuple(sorted(g.hands[observer]))
                    known[b.contract.dummy]=tuple(sorted(g.hands[b.contract.dummy]))
                    view=replace(actual,controller=observer,actor=observer,
                                 known_hands=tuple(known),legal=tuple(sorted(g.hands[observer])))
                    neural=WeightedSampler(view,prior.logits(view));uniform=WeightedSampler(view)
                    n=neural.marginals();u=uniform.marginals()
                    cards=[c for c in neural.cards if (u[c]>1e-12).sum()>1]
                    if not cards:continue
                    observations.append(dict(deal_id=did,table=table_index,ply=len(g.history),
                        role='declarer' if observer==b.contract.declarer else 'defender',cards=len(cards),
                        neural=metrics(n,truth,cards),uniform=metrics(u,truth,cards)))
    assert seen==set(protocol['play_deal_ids']) and len(records)==protocol['play_deals']
    audit=dict(validated=True,independent_deals=len(records),complete_games=2*len(records),
               failures=0,plies=104*len(records),nonforced_decisions=decisions,dds_world_solves=worlds,
               source_split='test',samples_per_nonforced_decision=32)
    (root/'play-audit.json').write_text(json.dumps(audit,indent=2))
    with gzip.open(root/'actual-play-beliefs.json.gz','wt') as f:json.dump(observations,f)
    result={};rng=np.random.default_rng(20261114)
    for ply in (1,12,24,36,44):
        result[ply]={}
        for role in ('all','declarer','defender'):
            rows=[r for r in observations if r['ply']==ply and (role=='all' or r['role']==role)]
            groups={d:[r for r in rows if r['deal_id']==d] for d in {r['deal_id'] for r in rows}}
            values=np.array([[np.mean([r[k] for r in group],axis=0) for k in ('neural','uniform')] for group in groups.values()])
            means=values.mean(0);delta=values[:,0]-values[:,1]
            boot=np.array([delta[rng.integers(len(delta),size=len(delta))].mean(0) for _ in range(2000)])
            result[ply][role]=dict(deals=len(groups),views=len(rows),uncertain_card_labels=sum(r['cards'] for r in rows),
                neural=dict(zip(('accuracy','nll','brier'),means[0].tolist())),
                uniform=dict(zip(('accuracy','nll','brier'),means[1].tolist())),
                paired_delta_95_interval=np.quantile(boot,[.025,.975],axis=0).tolist())
    (root/'actual-play-belief-summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(audit));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
