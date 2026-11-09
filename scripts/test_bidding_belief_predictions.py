#!/usr/bin/env python3
"""Frozen paired ownership tests, clustering all views/cards by original deal.

Dummy diagnostics reveal the two ORIGINAL hands and omit lead/play evidence,
matching evaluate_bidding_sampling.py. This is not a played-game strength test.
"""
import argparse
from collections import defaultdict
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.stats import t
from bridge_harness.auction_belief import CALLS, encode_auction
from bridge_harness.bidding_belief_data import sha, belief_split
from bridge_harness.bidding_env import make_board, deal_key
from bridge_harness.bidding_sampling import AuctionWeights, WeightedSampler
from bridge_harness.belief_model import masked_probabilities
from bridge_harness.core import Board, Observation, auction_contract
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def two_hand_marginals(logits):
    """Batched exact 13/13 conditioning of 26 two-owner log weights."""
    logits=np.asarray(logits,dtype=np.float64)
    if logits.ndim!=3 or logits.shape[1:]!=(26,2) or not np.isfinite(logits).all():
        raise ValueError('Expected finite N x 26 x 2 log weights')
    w=np.exp(logits-logits.max(-1,keepdims=True))
    n=len(w)
    f=np.zeros((n,27,14));b=np.zeros_like(f)
    f[:,0,0]=1;b[:,26,0]=1
    for i in range(26):
        f[:,i+1]=f[:,i]*w[:,i,1,None]
        f[:,i+1,1:]+=f[:,i,:-1]*w[:,i,0,None]
    for i in range(25,-1,-1):
        b[:,i]=b[:,i+1]*w[:,i,1,None]
        b[:,i,1:]+=b[:,i+1,:-1]*w[:,i,0,None]
    z=f[:,26,13]
    if np.any(z<=0):
        raise ValueError('Partition underflow')
    p=np.stack([w[:,i,0]*np.sum(f[:,i,:13]*b[:,i+1,12::-1],axis=-1)/z for i in range(26)],axis=1)
    return np.stack([p,1-p],axis=-1)


def legacy_boards(path):
    """Decode a complete observation; use its full-deal hash to recover compass."""
    with np.load(path,allow_pickle=False) as z:
        groups=z['split_group'];kind=z['kind'];state=z['state'];calls=z['calls'];target=z['owner_target']
    seen=set()
    for i in np.flatnonzero(kind==1):
        key=str(groups[i])
        if key in seen:continue
        seen.add(key)
        rel=tuple(tuple(map(int,np.flatnonzero(target[i]==s))) for s in range(4))
        possible=[(k,rel[k:]+rel[:k]) for k in range(4) if digest(rel[k:]+rel[:k])==key]
        if len(possible)!=1:raise ValueError('Cannot reconstruct absolute hands')
        rotation,hands=possible[0];observer=(-rotation)%4
        dealer=(int(state[i,59:63].argmax())+observer)%4
        us,them=map(bool,state[i,57:59])
        vul='Both' if us and them else 'None' if not (us or them) else ('NS' if (observer%2==0)==us else 'EW')
        auction=tuple(CALLS[int(c)-1] for c in calls[i] if c)
        x,_=encode_auction(hands[observer],observer,dealer,vul,auction)
        if not np.array_equal(x['state'],state[i]) or not np.array_equal(x['calls'],calls[i]):
            raise ValueError('Decoded board does not reproduce original features')
        yield key,Board(key,hands,auction_contract(dealer,auction),dealer,vul,auction,auction_source='BEN-neural-only')


def bidding_boards(data, split):
    families=json.loads((data/'reserved-families.json').read_text())
    ds=json.loads((data/'dataset.json').read_text())
    wanted=set(families[split]);root=Path(ds['source_run'])
    raw=(root/'manifest.json').read_bytes()
    import hashlib
    if hashlib.sha256(raw).hexdigest()!=ds['source_manifest_sha256']:
        raise ValueError('Source manifest changed; restore frozen source')
    manifest=json.loads(raw);seen=set()
    for entry in ds['source_batches']:
        path=root/'batches'/entry['batch']/'auctions.json'
        if sha(path)!=entry['sha256']:raise ValueError('Frozen source batch changed')
        attempt,offset=map(int,entry['batch'][1:].split('-'))
        for j,row in enumerate(json.loads(path.read_text())):
            key=row['deal_id']
            if key not in wanted:continue
            if belief_split(key)!=split:raise ValueError('Wrong belief split')
            b=make_board(manifest['config']['seed']+attempt*100003,offset+j,'train')
            if deal_key(b.hands,True)!=key:raise ValueError('Reconstructed cards disagree')
            if key in seen:raise ValueError('Duplicate source family')
            seen.add(key);auctions=set()
            for room in row['tables']:
                calls=tuple(room['calls'])
                if calls in auctions:continue
                auctions.add(calls)
                if len(calls)>64:continue
                c=auction_contract(b.dealer,calls)
                if room['contract']!=(c.text() if c else None) or room['declarer']!=(c.declarer if c else None):
                    raise ValueError('Auction replay differs')
                yield key,replace(b,contract=c,auction=calls,auction_source='bidding-training')
    if seen!=wanted:raise ValueError('Missing test/validation families')


def loss_values(p,y):
    truth=np.take_along_axis(p,y[...,None],axis=-1)[...,0]
    return -np.log(np.maximum(truth,1e-15)),(p.argmax(-1)==y).astype(float)


def add(records,condition,family,values):
    # Rows: parent loss, candidate loss, parent correct, candidate correct, labels.
    records[condition][family]+=np.array([v.sum() for v in values]+[values[0].size])


def summarize(records):
    answer={}
    for condition,groups in records.items():
        rows=np.stack(list(groups.values()));n=len(rows);weight=rows[:,4]
        total=rows.sum(0);out=dict(deals=n,card_predictions=int(total[4]))
        for metric,indices,sign in (('nll',(0,1),-1),('accuracy',(2,3),1)):
            a,b=indices
            # Positive always means improvement. Cluster residual variance
            # preserves original card-weighted averages with unequal room counts.
            contribution=sign*(rows[:,b]-rows[:,a]);gain=contribution.sum()/weight.sum()
            residual=contribution-gain*weight
            se=np.sqrt(n/(n-1)*np.dot(residual,residual))/weight.sum()
            p=float(2*t.sf(abs(gain/se),n-1)) if se else (1. if gain==0 else 0.)
            nominal=float(t.ppf(.975,n-1))*se
            adjusted=float(t.ppf(1-.05/12/2,n-1))*se
            out[metric]=dict(parent=float(total[a]/total[4]),candidate=float(total[b]/total[4]),
                gain=float(gain),se=float(se),gain_95_interval=[float(gain-nominal),float(gain+nominal)],
                gain_familywise_95_interval=[float(gain-adjusted),float(gain+adjusted)],
                p_two_sided=p,p_bonferroni_12=min(1.,12*p))
        answer[condition]=out
    return answer


def check_conditioner(models, board):
    if board.contract is None:return False
    truth=np.empty(52,int)
    for s,h in enumerate(board.hands):truth[list(h)]=s
    for observer in range(4):
        if observer==board.contract.dummy:continue
        known=[None]*4;known[observer]=board.hands[observer];known[board.contract.dummy]=board.hands[board.contract.dummy]
        o=Observation(observer,observer,tuple(known),board.hands[observer],(),(),(board.contract.declarer+1)%4,
                      board.contract,board.dealer,board.vulnerability,board.auction,0)
        unseen=[s for s in range(4) if known[s] is None];cards=sorted(c for s in unseen for c in board.hands[s])
        for model in models:
            logits=model.logits(o)
            fast=two_hand_marginals(logits[np.ix_(cards,unseen)][None])[0]
            slow=WeightedSampler(o,logits).marginals()[np.ix_(cards,unseen)]
            np.testing.assert_allclose(fast,slow,rtol=1e-11,atol=1e-12)
    return True


def evaluate(boards,models,own_only=False):
    records={k:defaultdict(lambda:np.zeros(5)) for k in ('own_hand','declarer','defender') if not own_only or k=='own_hand'}
    count=0;passed=0;checked=False
    iterator=iter(boards)
    while True:
        chunk=[]
        for _ in range(128):
            try:chunk.append(next(iterator))
            except StopIteration:break
        if not chunk:break
        encoded=[];rows=[]
        for family,board in chunk:
            if not checked and not own_only:checked=check_conditioner(models,board)
            truth=np.empty(52,int)
            for s,h in enumerate(board.hands):truth[list(h)]=s
            for observer in range(4):
                x,support=encode_auction(board.hands[observer],observer,board.dealer,board.vulnerability,board.auction)
                encoded.append(x);rows.append((family,board,observer,truth,support))
            passed+=board.contract is None
        inputs={k:np.stack([x[k] for x in encoded]) for k in ('state','calls','seats')}
        logits=[m.predict(inputs) for m in models]
        support=np.stack([r[4] for r in rows])
        relative=np.stack([(r[3]-r[2])%4 for r in rows]);mask=relative!=0
        probs=[masked_probabilities(logit,support) for logit in logits]
        losses=[loss_values(p,relative) for p in probs]
        role_rows=[];role_logits=[[],[]]
        for i,(family,board,observer,truth,_) in enumerate(rows):
            add(records,'own_hand',family,[losses[0][0][i][mask[i]],losses[1][0][i][mask[i]],
                                          losses[0][1][i][mask[i]],losses[1][1][i][mask[i]]])
            if own_only or board.contract is None or observer==board.contract.dummy:continue
            unseen=[s for s in range(4) if s not in (observer,board.contract.dummy)]
            cards=sorted(c for s in unseen for c in board.hands[s])
            role='declarer' if observer==board.contract.declarer else 'defender'
            role_rows.append((family,role,(truth[cards]==unseen[1]).astype(int)))
            for j in range(2):role_logits[j].append(logits[j][i][np.ix_(cards,[(s-observer)%4 for s in unseen])])
        if role_rows:
            role_probs=[two_hand_marginals(np.stack(v)) for v in role_logits]
            ys=np.stack([r[2] for r in role_rows]);role_losses=[loss_values(p,ys) for p in role_probs]
            for i,(family,role,_) in enumerate(role_rows):
                add(records,role,family,[role_losses[0][0][i],role_losses[1][0][i],role_losses[0][1][i],role_losses[1][1][i]])
        count+=len(chunk)
        if count%1024==0:print(json.dumps(dict(event='evaluated',auctions=count)),flush=True)
    return dict(auctions=count,passed_out=passed,metrics=summarize(records)),records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Refusing to overwrite a frozen test')
    ds=json.loads((a.run/'data/dataset.json').read_text());fit=json.loads((a.run/'fit/result.json').read_text())
    parent=a.run/'fit/parent.npz';candidate=a.run/'fit/best.npz'
    if sha(parent)!=fit['parent_sha256'] or sha(candidate)!=fit['selected_sha256']:
        raise ValueError('Frozen weights changed')
    legacy=Path(ds['legacy']['train']['path']).parent
    audit=json.loads((legacy/'audit.json').read_text())
    if sha(legacy/'test.npz')!=audit['exports']['test']:raise ValueError('Reserved BEN test changed')
    a.out.mkdir(parents=True)
    protocol=dict(parent_sha256=sha(parent),candidate_sha256=sha(candidate),selected_epoch=fit['best_epoch'],
        model_fixed_before_test=True,update_weights=False,selection_uses_test=False,
        test_family='2 sources x 3 conditions x 2 metrics = 12 Bonferroni-adjusted two-sided comparisons',
        uncertainty='Paired cluster-robust Student-t intervals; cluster by full original deal, including both rooms and both defenders.',
        estimand='Card-weighted loss/accuracy; positive gain means improvement.',
        dummy='Both original own and dummy hands visible, exactly 26 unknown cards; no lead or play evidence. Exact 13/13 conditioning.',
        prior_validation='Descriptive only: these labels selected epoch 8.',
        bidding_test='Reserved from belief training; upstream bidder has trained on these families.',
        playing_strength_test=False,additional_dds_calls=0,
        source_sha256=sha(Path(__file__)),dataset_sha256=sha(a.run/'data/dataset.json'),ben_test_sha256=sha(legacy/'test.npz'))
    atomic_json(a.out/'protocol.json',protocol)  # Before inspecting test predictions.
    models=[AuctionWeights(parent),AuctionWeights(candidate)];result={}
    for name,boards,own in (
        ('ben_validation',legacy_boards(legacy/'validation.npz'),True),
        ('bidding_validation',bidding_boards(a.run/'data','validation'),True),
        ('ben_test',legacy_boards(legacy/'test.npz'),False),
        ('bidding_test',bidding_boards(a.run/'data','test'),False)):
        summary,records=evaluate(boards,models,own)
        result[name]=summary
        arrays={}
        for condition,groups in records.items():
            arrays[condition+'_groups']=np.array(list(groups));arrays[condition+'_values']=np.stack(list(groups.values()))
        np.savez_compressed(a.out/f'{name}-clusters.npz',**arrays)
        atomic_json(a.out/f'{name}.json',summary)
        print(json.dumps(dict(event=name,**summary)),flush=True)
    atomic_json(a.out/'result.json',dict(protocol=protocol,results=result))


if __name__=='__main__':main()
