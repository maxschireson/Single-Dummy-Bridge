"""Fit only random-audited IMP contrasts; ordinary play cannot supply labels."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.fork_policy import ForkAdvantageWeights
from bridge_harness.auction_policy import encode_decision
from bridge_harness.core import Board,Game,card
from bridge_harness.fork_audit import audited_gain
from bridge_harness.bidding_env import deal_key
from bridge_harness.improvement import read
from bridge_harness.runner import replay
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def examples(record,model):
    if record.get('schema_version')!='random-fork-audit-v1':raise ValueError('Only random fork records are accepted')
    replay(record);board=Board.from_dict(record['board']);family=deal_key(board.hands,True)
    assert record['family']==family
    split='validation' if int(family[:8],16)%5==0 else 'train'
    for event in record['audits']:
        if event['identical_action']:continue
        assert event['selection']=='independent-random-post-commit'
        t=record['tables'][event['candidate_table']];u=record['tables'][event['reference_table']];ply=event['ply']
        assert [z['card'] for z in t['actions'][:ply]]==[z['card'] for z in u['actions'][:ply]]
        z=t['actions'][ply];assert z['committed_before_audit'] and z['audit_draw']
        assert z['card']==event['candidate_card'] and u['actions'][ply]['card']==event['reference_card']
        g=Game(board)
        for previous in t['actions'][:ply]:g.play(card(previous['card']))
        o=g.observation();assert o.actor==event['actor']
        y=audited_gain(t['ns_score'],u['ns_score'],o.actor);assert y==event['gain_imps']
        x,cards=encode_decision(o,z);valid=x['mask'][0]>0
        chosen=int(np.flatnonzero((cards[0]==card(event['candidate_card']))&valid)[0])
        reference=int(np.flatnonzero((cards[0]==card(event['reference_card']))&valid)[0])
        f=model.features(x)[0]
        yield dict(features=f[chosen]-f[reference],y=y,family=family,split=split,depth=event['depth'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bootstrap',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Use a new frozen fit directory')
    config=read(a.run/'config.json');assert config['versions']['bootstrap']==sha(a.bootstrap)
    model=ForkAdvantageWeights(a.bootstrap);rows=[];sources=[]
    for path in sorted((a.run/'episodes').glob('*.json.gz')):
        record=read(path);assert record['versions']==config['versions']
        rows.extend(examples(record,model));sources.append(dict(path=str(path),sha256=sha(path)))
    if not rows:raise ValueError('No audited deviations')
    x=np.stack([r['features'] for r in rows]).astype('float64');y=np.array([r['y'] for r in rows],float)
    train=np.array([r['split']=='train' for r in rows]);groups=np.array([r['family'] for r in rows])
    if min(len(set(groups[train])),len(set(groups[~train])))<10:raise ValueError('Need at least ten train and ten validation families with deviations')
    # Equal family weighting prevents heavily branched boards dominating the fit.
    count={g:sum(groups==g) for g in set(groups)};w=np.array([1/count[g] for g in groups]);w[train]/=w[train].mean()
    scale=np.sqrt(np.average(x[train]**2,axis=0,weights=w[train]));scale=np.maximum(scale,1e-4)
    z=x/scale;zt=z[train];yt=y[train];wt=w[train]
    gram=zt.T@(zt*wt[:,None]);rhs=zt.T@(wt*yt)
    zero=float(np.average(y[~train]**2,weights=w[~train]));best=(zero,None,np.zeros(x.shape[1]));history=[]
    for strength in (.01,.1,1.,10.,100.):
        coef=np.linalg.solve(gram+strength*wt.sum()*np.eye(x.shape[1]),rhs)/scale
        mse=float(np.average((x[~train]@coef-y[~train])**2,weights=w[~train]));history.append(dict(ridge=strength,mse=mse))
        if mse<best[0]:best=(mse,strength,coef)
    a.out.mkdir(parents=True);np.savez_compressed(a.out/'fork-data.npz',features=x,y=y,train=train,group=groups,weight=w)
    np.savez_compressed(a.out/'candidate.npz',**model.weights,imp_linear_coef=best[2].astype('float32'))
    result=dict(schema='fork-imp-linear-head-v1',rows=len(rows),train_families=len(set(groups[train])),
        validation_families=len(set(groups[~train])),zero_gain_mse=zero,selected_mse=best[0],ridge=best[1],
        predictive_improvement=best[1] is not None,trainable_parameters=x.shape[1],representation='frozen direct auction/history bootstrap',
        objective='MSE of audited candidate-minus-reference IMPs; no ordinary outcome labels',
        history=history,versions=config['versions'],sources=sources,promoted=False,
        interpretation='Selection validation only. Prediction improvement is not demonstrated play strength; retain frozen reference.')
    atomic_json(a.out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='sources'}))


if __name__=='__main__':main()
