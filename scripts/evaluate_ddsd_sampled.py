"""Evaluate held-out forks with true hands hidden from the root chooser.

Each pair uses common sampled deals from the recorded actor's belief model.
Continuation outcomes remain the already-recorded frozen-policy outcomes.
This is a local two-card test, not a full-game or Gen5-strength claim.
"""
import argparse,gzip,hashlib,json,os,random,sys,time
from pathlib import Path
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card,score,vulnerable,imps,symbol
from bridge_harness.auction_policy import AuctionSelectorWeights,encode_decision
from bridge_harness.dds import DDS
from bridge_harness.ddsd_corrector import Corrector,encode
from bridge_harness.sampling import Sampler
from bridge_harness.bidding_sampling import WeightedSampler,AuctionWeights
from bridge_harness.belief_capacity import Weights
from scripts.prepare_ddsd_corrector import bind_roles
from scripts.train_ddsd_corrector import family_stats,pair_metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--fit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    p.add_argument('--library',required=True);p.add_argument('--samples',type=int,default=32);p.add_argument('--limit',type=int)
    p.add_argument('--policy',type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    config=json.loads((a.data/'config.json').read_text());registry={}
    for m in list(config['source_manifest']['source_manifests'].values())+config['additional_registries']:
        for spec in m['bots'].values():registry[spec['identity']]=spec
    paths={hashlib.sha256(f.read_bytes()).hexdigest():f for f in a.models.glob('*belief*.npz')};nets={}
    positions=[json.loads(line) for line in gzip.open(a.data/'pair-positions.jsonl.gz','rt')]
    if a.limit:positions=sorted(positions,key=lambda r:hashlib.sha256(json.dumps([r['family'],r['prefix'],r['cards']]).encode()).hexdigest())[:a.limit]
    model=Corrector(a.fit/'candidate.pt');weight=json.loads((a.fit/'selection.json').read_text())['weight']
    policy=AuctionSelectorWeights(a.policy) if a.policy else None
    dds=DDS(a.library,cache_path='');rows=[];started=time.time();source_cache={}
    with gzip.open(a.out/'predictions.jsonl.gz','wt') as output:
        for i,r in enumerate(positions):
            if r['source'] not in source_cache:
                source_cache={r['source']:json.load(gzip.open(r['source'],'rt'))}
            record=source_cache[r['source']];ep=record['unique_tables'][r['room']]
            bind_roles(ep,record['provenance'][int(r['room'])])
            game=Game(Board.from_dict(r['board']))
            for c in r['prefix']:game.play(card(c))
            o=game.observation();identity=ep['_role_versions'][ep['assignments'][o.controller]];spec=registry[identity]
            belief_hash=spec.get('artifact_sha256',{}).get('belief')
            if belief_hash:
                if belief_hash not in nets:nets[belief_hash]=(Weights if spec['belief_kind']=='public' else AuctionWeights)(paths[belief_hash])
                sampler=WeightedSampler(o,nets[belief_hash].logits(o))
            else:sampler=Sampler(o)
            seed=int(hashlib.sha256(json.dumps([r['family'],r['prefix'],'gen6-sampled-617']).encode()).hexdigest()[:16],16)
            rng=random.Random(seed);worlds=[sampler.draw(rng) for _ in range(a.samples)]
            solved=dds.solve_batch(worlds,o.contract.trump,o.leader,o.trick,
                fixed_seats=[s for s,h in enumerate(o.known_hands) if h is not None])
            actions=list(map(card,r['cards']));x=[];calls=[];values=[]
            for hands,(v,_) in zip(worlds,solved):
                for c in actions:
                    state,cs=encode(o,hands,c,v[c],r['policy_features']);x.append(state);calls.append(cs);values.append(v[c])
            residual=model.predict(x,calls).reshape(-1,2).mean(0);dd=np.asarray(values).reshape(-1,2).mean(0)
            declaring=o.actor%2==o.contract.declarer%2;rem=13-len(o.history)//4
            final=[o.declarer_tricks+(y if declaring else rem-y) for y in r['outcomes']]
            diff=imps((score(o.contract,final[0],vulnerable(o.vulnerability,o.contract.declarer))-
                       score(o.contract,final[1],vulnerable(o.vulnerability,o.contract.declarer)))*(1 if declaring else -1))
            row=dict(family=r['family_index'],split=r['split'],dd=dd.tolist(),residual=residual.tolist(),
                y=r['outcomes'],imp_difference=diff,ply=len(o.history),declaring=declaring)
            if policy:
                means={c:sum(v[c] for v,_ in solved)/len(solved) for c in o.legal}
                best=max(means.values());eligible=[c for c in o.legal if best-means[c]<=.125+1e-9]
                already=o.declarer_tricks if declaring else len(o.history)//4-o.declarer_tricks
                details=dict(samples=a.samples,near_tie=.125,
                    estimates={symbol(c):dict(utility=v+already-(0 if declaring else 13)) for c,v in means.items()},
                    behavior_probabilities={symbol(c):float(c in eligible)/len(eligible) for c in o.legal})
                encoded,cards=encode_decision(o,details)
                valid=encoded['mask'][0].astype(bool)
                np.testing.assert_allclose(encoded['q'][0,valid],
                    [means[int(c)] for c in cards[0,valid]],rtol=0,atol=1e-6)
                prediction=policy.predict(encoded)[0]
                values={int(c):float(v) for c,v,valid in zip(cards[0],prediction,encoded['mask'][0]) if valid}
                row['policy_eligible']=[c in eligible for c in actions]
                row['policy_prediction']=[values.get(c) for c in actions]
                row['eligible_count']=len(eligible)
            rows.append(row);output.write(json.dumps(row)+'\n')
            if (i+1)%100==0:
                output.flush();status=dict(pairs=i+1,total=len(positions),seconds=time.time()-started)
                (a.out/'status.json').write_text(json.dumps(status));print(json.dumps(status),flush=True)
    result=dict(samples=a.samples,weight=weight,seconds=time.time()-started,
        evaluation='Recorded two-card forks; common newly drawn worlds using original actor belief; original frozen continuations',
        promoted=False)
    for split in ('validation','test'):
        part=[r for r in rows if r['split']==split]
        if not part:continue
        d={k:np.asarray([r[k] for r in part]) for k in part[0] if k not in ('split','policy_prediction')}
        result[split]=dict(pairs=pair_metrics(d,d['residual'],weight))
        gap=d['dd'][:,0]-d['dd'][:,1];corrected=gap+weight*(d['residual'][:,0]-d['residual'][:,1])
        old=np.where(gap>1e-8,1.,np.where(gap < -1e-8,0.,.5))
        for window in (0.,.125,1.e9):
            effective=np.where(np.abs(gap)<=window+1e-8,corrected,gap)
            new=np.where(effective>1e-8,1.,np.where(effective < -1e-8,0.,.5))
            result[split][str(window)]=dict(imp_gain=family_stats((new-old)*d['imp_difference'],d['family']),
                trick_gain=family_stats((new-old)*(d['y'][:,0]-d['y'][:,1]),d['family']),
                changed=int(np.count_nonzero(old!=new)),eligible=int(np.count_nonzero(np.abs(gap)<=window+1e-8)))
        if policy:
            both=d['policy_eligible'].all(1)
            subset={k:v[both] for k,v in d.items()}
            pp=np.asarray([r['policy_prediction'] for r in part],dtype=float)[both]
            dds_pred=subset['dd'];corrector_pred=dds_pred+weight*subset['residual'];actual=subset['y']
            family=subset['family'];baseline_gap=dds_pred[:,0]-dds_pred[:,1]
            def choice(q):return np.where(q>1e-7,1.,np.where(q < -1e-7,0.,.5))
            old=choice(baseline_gap);pc=choice(corrector_pred[:,0]-corrector_pred[:,1]);pv=choice(pp[:,0]-pp[:,1])
            outcome_errors={name:((pred-actual)**2).mean(1) for name,pred in
                [('pimc',dds_pred),('corrector',corrector_pred),('v5_policy',pp)]}
            paired={name:family_stats(error,family) for name,error in outcome_errors.items()}
            paired['corrector_minus_v5_mse']=family_stats(outcome_errors['corrector']-outcome_errors['v5_policy'],family)
            paired['v5_minus_pimc_mse']=family_stats(outcome_errors['v5_policy']-outcome_errors['pimc'],family)
            paired['corrector_minus_pimc_mse']=family_stats(outcome_errors['corrector']-outcome_errors['pimc'],family)
            comparisons={}
            for name,delta in [('corrector_vs_pimc',pc-old),('v5_vs_pimc',pv-old),('corrector_vs_v5',pc-pv)]:
                comparisons[name]=dict(imp_gain=family_stats(delta*subset['imp_difference'],family),
                    trick_gain=family_stats(delta*(actual[:,0]-actual[:,1]),family),
                    changed=int(np.count_nonzero(delta)))
            result[split]['v5_comparison']=dict(rule='Both recorded alternatives eligible under the same freshly sampled 32-world PIMC and global 0.125 window; all normal eligible actions encoded',
                rows=int(both.sum()),excluded_rows=int((~both).sum()),outcome_mse=paired,choices=comparisons,
                policy_pair_metrics=pair_metrics(subset,pp-dds_pred),corrector_pair_metrics=pair_metrics(subset,subset['residual'],weight))
    if policy:result['v5_policy_sha256']=hashlib.sha256(a.policy.read_bytes()).hexdigest()
    (a.out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':main()
