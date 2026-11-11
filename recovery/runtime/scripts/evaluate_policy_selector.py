#!/usr/bin/env python3
"""Frozen selector versus random near-ties and versus highest-PIMC tie-breaking."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
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
from bridge_harness.core import Board,imps
from bridge_harness.corpus import load,save
from bridge_harness.players import PIMCPlayer
from bridge_harness.policy_selector import SelectorPlayer
from bridge_harness.runner import play_table,replay,decision_rng
from bridge_harness.training import digest,split_for
from bridge_harness.report import summarize


class SharedRNG:
    """Couple sampled worlds when policies encounter the same public history."""
    def __init__(self,player,board_id,seed):self.player,self.board_id,self.seed=player,board_id,seed
    def choose(self,o,ignored):return self.player.choose(o,decision_rng(self.seed,self.board_id,'pimc32-shared',o))


def pair(job):
    data,path,seed,control=job;b=Board.from_dict(data)
    candidate=SelectorPlayer(path)
    baseline=PIMCPlayer(32,'tricks',True,.125 if control=='random' else 0.)
    players={'selector32':SharedRNG(candidate,b.id,seed),'control32':SharedRNG(baseline,b.id,seed)}
    assignments=[['selector32','control32','selector32','control32'],['control32','selector32','control32','selector32']]
    r=dict(schema_version=1,board=data,config=dict(mode='partnership',candidate='selector32',baseline='control32',
        control=control,samples=32,batch=True,objective='tricks',near_tie=.125,seed=seed,
        rng='same decision seed and namespace for both policies; common observations get identical worlds'),
        assignments=assignments,tables=[])
    try:
        for seats in assignments:r['tables'].append(play_table(b,seats,players,seed))
        r['status']='ok' if all(t['status']=='ok' for t in r['tables']) else 'error'
        if r['status']=='ok':
            a,c=r['tables'];r['score_difference']=a['ns_score']-c['ns_score'];r['imps']=imps(r['score_difference'])
            r['first_difference']=next((i for i,(x,y) in enumerate(zip(a['actions'],c['actions'])) if x['card']!=y['card']),None)
            replay(r)
            for t in r['tables']:
                assert len(t['actions'])==52
                for action in t['actions']:
                    assert action.get('forced') or (action['samples']==action['dds_calls']==32 and action['batch'])
                    if action.get('selector'):
                        assert action['selected_pimc_gap']<=.125+1e-9
                        assert action['proposal_probabilities'][action['card']]>0
        return r
    finally:candidate.close();baseline.close()


def prepare(data,root):
    lookup={}
    for di in range(10):
        d=data/f'chunk-{di}'
        with np.load(d/'test.npz',allow_pickle=False) as z:
            for group,episode in zip(z['split_group'][::52],z['episode_id'][::52]):
                assert str(group) not in lookup
                lookup[str(group)]=d/'episodes'/(str(episode)+'.json.gz')
    assert len(lookup)==999
    ids=sorted(lookup);random.Random(20261120).shuffle(ids);selected=ids[:200];boards=[]
    for did in selected:
        with gzip.open(lookup[did],'rt') as f:r=json.load(f)
        b=Board.from_dict(r['record']['board'])
        assert digest(b.hands)==did and split_for(b)=='test'
        boards.append(b)
    save(boards,root/'play-corpus.jsonl')
    p=root/'protocol.json';protocol=json.loads(p.read_text());protocol.update(
        play_deal_ids=selected,controls=['random near-ties (0.125)','highest PIMC mean (0.0)'],
        control_rationale='distinguish learned preferences from merely choosing the top PIMC estimate',
        shared_randomness='identical PIMC worlds on identical information states; same fixed seed')
    p.write_text(json.dumps(protocol,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--prepare-only',action='store_true');args=p.parse_args();root=args.run
    if not (root/'play-corpus.jsonl').exists():prepare(args.data,root)
    if args.prepare_only:return
    weights=root/'training/weights.npz';assert weights.exists()
    boards=load(root/'play-corpus.jsonl');records={'random':[],'pimc-best':[]};jobs=[]
    for control in records:
        dest=root/control;dest.mkdir(exist_ok=True)
        for b in boards:
            path=dest/(digest(b.hands)+'.json.gz')
            if path.exists():
                with gzip.open(path,'rt') as f:r=json.load(f)
                assert r['status']=='ok';replay(r);records[control].append(r)
            else:jobs.append((b.to_dict(),str(weights.resolve()),20261120,control))
    started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(pair,j) for j in jobs]):
            r=future.result();control=r['config']['control'];assert r['status']=='ok',r
            path=root/control/(digest(Board.from_dict(r['board']).hands)+'.json.gz')
            temp=path.with_suffix('.tmp')
            with gzip.open(temp,'wt') as f:json.dump(r,f)
            temp.replace(path);records[control].append(r)
            done=sum(map(len,records.values()))
            if done%20==0:print(json.dumps(dict(pairs=done,seconds=time.perf_counter()-started)),flush=True)
    result={c:summarize(r) for c,r in records.items()}
    result['wall_seconds']=time.perf_counter()-started
    result['independent_deals']=200;result['complete_games']=800
    result['weights_sha256']=hashlib.sha256(weights.read_bytes()).hexdigest()
    (root/'play-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
