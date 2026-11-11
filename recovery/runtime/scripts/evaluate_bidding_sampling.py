#!/usr/bin/env python3
"""Frozen-model paired PIMC test and dummy-reveal ownership measurement."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.core import Board, Game, Observation, imps
from bridge_harness.corpus import load, save
from bridge_harness.training import digest, split_for
from bridge_harness.bidding_sampling import AuctionWeights, WeightedSampler
from bridge_harness.players import PIMCPlayer
from bridge_harness.runner import play_table, replay
from bridge_harness.report import summarize


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pair(job):
    board_dict,weights_path,seed=job;board=Board.from_dict(board_dict)
    weights=AuctionWeights(weights_path)
    candidate=PIMCPlayer(32,'tricks',True,.125,
        sampler_factory=lambda o:WeightedSampler(o,weights.logits(o),1.))
    baseline=PIMCPlayer(32,'tricks',True,.125)
    players={'bidding32':candidate,'uniform32':baseline}
    assignments=[['bidding32','uniform32','bidding32','uniform32'],
                 ['uniform32','bidding32','uniform32','bidding32']]
    r=dict(schema_version=1,status='error',board=board_dict,
        config=dict(mode='partnership',candidate='bidding32',baseline='uniform32',
                    samples=32,objective='tricks',batch=True,near_tie=.125,seed=seed,
                    weighting='product of neural ownership weights conditioned on hard constraints',strength=1.),
        assignments=assignments,tables=[])
    try:
        for seats in assignments:r['tables'].append(play_table(board,seats,players,seed))
        if all(t['status']=='ok' for t in r['tables']):
            a,b=r['tables'];r['status']='ok'
            r['score_difference']=a['ns_score']-b['ns_score'];r['imps']=imps(r['score_difference'])
            r['first_difference']=next((i for i,(x,y) in enumerate(zip(a['actions'],b['actions'])) if x['card']!=y['card']),None)
            replay(r)
            for table in r['tables']:
                assert len(table['actions'])==52
                for action in table['actions']:
                    assert action.get('forced') or (action['samples']==32 and action['dds_calls']==32 and action['batch'])
        return r
    finally:candidate.close();baseline.close()


def metrics(prob,truth,cards):
    p=prob[cards];y=truth[cards]
    t=p[np.arange(len(cards)),y]
    ties=np.isclose(p,p.max(-1,keepdims=True),rtol=0,atol=1e-12)
    accuracy=ties[np.arange(len(cards)),y]/ties.sum(-1)
    return [float(np.mean(accuracy)),float(-np.log(np.maximum(t,1e-15)).mean()),
            float((np.square(p).sum(-1)-2*t+1).mean())]


def dummy_deal(job):
    d,path=job;b=Board.from_dict(d);weights=AuctionWeights(path)
    truth=np.empty(52,int)
    for s,h in enumerate(b.hands):truth[list(h)]=s
    rows=[]
    for observer in range(4):
        if observer==b.contract.dummy:continue
        known=[None]*4;known[observer]=b.hands[observer];known[b.contract.dummy]=b.hands[b.contract.dummy]
        # Isolate revelation of the two ORIGINAL visible hands: intentionally
        # omit lead/play evidence. This is a conditional ownership diagnostic,
        # not an assertion that dummy is available before the opening lead.
        o=Observation(observer,observer,tuple(known),b.hands[observer],(),(),
                      (b.contract.declarer+1)%4,b.contract,b.dealer,b.vulnerability,b.auction,0)
        neural=WeightedSampler(o,weights.logits(o));uniform=WeightedSampler(o)
        n=neural.marginals();u=uniform.marginals();cards=list(neural.cards)
        assert len(cards)==26 and np.allclose(n[cards].sum(-1),1)
        assert np.allclose(n.sum(0),13,atol=1e-8)
        rows.append(dict(role='declarer' if observer==b.contract.declarer else 'defender',
            observer=observer,neural=metrics(n,truth,cards),uniform=metrics(u,truth,cards)))
    return dict(deal_id=digest(b.hands),rows=rows)


def dummy_summary(results):
    answer={};rng=np.random.default_rng(20261113)
    for role in ('all','declarer','defender'):
        values=np.array([[np.mean([r[k] for r in d['rows'] if role=='all' or r['role']==role],axis=0)
                          for k in ('neural','uniform')] for d in results])
        delta=values[:,0]-values[:,1];means=values.mean(0)
        # Resample original deals, not individual cards or repeated views.
        boot=np.array([delta[rng.integers(len(delta),size=len(delta))].mean(0) for _ in range(2000)])
        answer[role]=dict(deals=len(values),neural=dict(zip(('accuracy','nll','brier'),means[0].tolist())),
            uniform=dict(zip(('accuracy','nll','brier'),means[1].tolist())),
            paired_delta_95_interval=np.quantile(boot,[.025,.975],axis=0).tolist())
    return answer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',type=Path,required=True);p.add_argument('--weights',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=200)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--mode',choices=('prepare','play','dummy'),required=True)
    args=p.parse_args();out=args.out.resolve();weights=args.weights.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.mode=='prepare':
        test=[b for b in load(args.corpus) if split_for(b)=='test']
        playable=[b for b in test if b.contract is not None]
        assert len({digest(b.hands) for b in test})==len(test)
        shuffled=sorted(playable,key=lambda b:digest(b.hands));random.Random(20261112).shuffle(shuffled)
        cohort=shuffled[:args.count];assert len(cohort)==args.count
        manifest=dict(source_sha256=sha(args.corpus),weights_sha256=sha(weights),
            test_deals=len(test),test_passed_out=len(test)-len(playable),dummy_deals=len(playable),
            play_deals=args.count,play_deal_ids=[digest(b.hands) for b in cohort],
            samples=32,batch=True,near_tie=.125,objective='tricks',strength=1.,decision_seed=20261112,
            selection='200 playable held-out test deals, sorted by deal hash and shuffled before outcomes',
            interpretation='frozen one-visible-hand auction model plus exact conditioning of factorized weights; no joint retraining',
            dummy_protocol='all non-passed-out test deals, three non-dummy observers; original own and dummy hands visible; omit lead/play evidence to isolate dummy revelation')
        with (out/'protocol.json').open('x') as f:json.dump(manifest,f,indent=2)
        save(cohort,out/'play-corpus.jsonl');save(playable,out/'dummy-corpus.jsonl')
        print(json.dumps(manifest,indent=2));return
    protocol=json.loads((out/'protocol.json').read_text());assert sha(weights)==protocol['weights_sha256']
    started=time.perf_counter()
    if args.mode=='play':
        boards=load(out/'play-corpus.jsonl');records=[];(out/'episodes').mkdir(exist_ok=True)
        pending=[]
        for b in boards:
            path=out/'episodes'/f'{digest(b.hands)}.json.gz'
            if path.exists():
                with gzip.open(path,'rt') as f:r=json.load(f)
                replay(r);assert r['status']=='ok';records.append(r)
            else:pending.append((b.to_dict(),str(weights),protocol['decision_seed']))
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(pair,j) for j in pending]
            for future in as_completed(futures):
                r=future.result();did=digest(Board.from_dict(r['board']).hands)
                path=out/'episodes'/f'{did}.json.gz';temp=path.with_suffix('.tmp')
                with gzip.open(temp,'wt') as f:json.dump(r,f)
                temp.replace(path);records.append(r)
                if len(records)%10==0:print(json.dumps(dict(completed=len(records),seconds=time.perf_counter()-started)),flush=True)
        assert len(records)==protocol['play_deals']
        result=summarize(records);result['wall_seconds_this_invocation']=time.perf_counter()-started
        (out/'play-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    else:
        boards=load(out/'dummy-corpus.jsonl');results=[]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,r in enumerate(pool.map(dummy_deal,[(b.to_dict(),str(weights)) for b in boards],chunksize=20)):
                results.append(r)
                if (i+1)%1000==0:print('dummy',i+1,flush=True)
        with gzip.open(out/'dummy-per-deal.json.gz','wt') as f:json.dump(results,f)
        summary=dummy_summary(results);summary['seconds']=time.perf_counter()-started
        (out/'dummy-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
