"""Six-bot common-auction arena with frozen hybrid identities and allocation."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board, imps
from bridge_harness.corpus import load,save
from bridge_harness.bidding_env import deal_key
from bridge_harness.fork_audit import ForkBudget,collect_board
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import ArenaPlayer,verify_generation
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

LABELS={'4':'Gen 4','P':'Gen 4p','Q':'Gen 4b','3':'Gen 3','2':'Gen 2','1':'Gen 1'}
ALLOCATION={'44':4,'43':4,'P3':4,'Q3':4,'4P':2,'4Q':2,'PQ':2,'42':2,'41':1,'32':1}

def initialize(source,root,count):
    if root.exists():raise ValueError('Refusing to overwrite arena')
    old=read(source/'manifest.json');verify_generation(source,old)
    boards=load(source/old['corpus'])
    boards.sort(key=lambda b:digest(['gen4-hybrid-mix-v1',deal_key(b.hands,True)]))
    if not 1<=count<=len(boards):raise ValueError('Invalid count')
    root.mkdir(parents=True)
    for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
    bots=deepcopy(old['bots'])
    for alias,name,bp,pp in [('P','4p','3','4'),('Q','4b','4','3')]:
        spec=deepcopy(bots['3']);spec.pop('identity');spec['id']=name
        for key,parent in [('belief',bp),('policy',pp)]:
            spec[key]=bots[parent][key];spec['artifact_sha256'][key]=bots[parent]['artifact_sha256'][key]
        spec['identity']=digest(spec);bots[alias]=spec
    save(boards[:count],root/'corpus.jsonl')
    schedule=[];block=[p for p,n in ALLOCATION.items() for _ in range(n)]
    for i in range((count+len(block)-1)//len(block)):
        shuffled=block.copy();random.Random(int(digest(['gen4-hybrid-mix-v1',i])[:12],16)).shuffle(shuffled);schedule+=shuffled
    schedule=schedule[:count];atomic_json(root/'schedule.json',schedule)
    m=dict(schema='gen4-hybrid-mix-v1',campaign='Gen 4 component mix',generation=4,candidate='4',reference='3',
        target=count,seed=202611091625,bots=bots,labels=LABELS,order=list(LABELS),
        corpus='corpus.jsonl',corpus_sha256=sha(root/'corpus.jsonl'),schedule_sha256=sha(root/'schedule.json'),
        source_sha256=source_hash(),runtime_sha256={'ops/gen4_mix.py':sha(Path(__file__))},
        allocation=ALLOCATION,pair_counts=dict(Counter(schedule)),created_epoch=time.time(),
        source_manifest_identity=old['identity'],source_cohort_overlap=True,
        audit=dict(probability=.5,multiplier=3.,max_depth=2,max_forks=64),
        protocol='Swapped partnerships on common frozen Gen4 auctions; hybrid P=4p, Q=4b. Random policy audits for the first partnership when it uses Gen4 policy. No historical bidder conditions.',
        interpretation='Separate cohort reusing source frozen deals. Never pool its IMPs or unique-family counts with other cohorts. No automatic training or promotion.')
    m['identity']=digest(m);atomic_json(root/'manifest.json',m)
    atomic_json(root/'created_epoch.json',m['created_epoch']);atomic_json(root/'state.json',summarize([],m))

def validate(r,m,board,index):
    if (r['manifest_identity']!=m['identity'] or r['index']!=index or r['board']!=board.to_dict()
        or r['family']!=deal_key(board.hands,True) or r['pair'] not in ALLOCATION
        or r['versions']!={k:s['identity'] for k,s in m['bots'].items()}):raise ValueError('Changed mix identity')
    pair=r['pair'];episodes=r['unique_tables']
    for room,key in enumerate(('0','1')):
        e=episodes[key];replay(e)
        seats=['candidate','environment'] if room==0 else ['environment','candidate']
        if e['assignments']!=seats*2 or e['board']!=board.to_dict() or e['versions']!=r['versions']:raise ValueError('Wrong mix room')
    expected=None if pair[0]==pair[1] else imps(episodes['0']['tables'][0]['ns_score']-episodes['1']['tables'][0]['ns_score'])
    if r['imps']!=expected or r['regimes']['common']['imps']!=expected:raise ValueError('Wrong mix IMP orientation')

def run_board(root,m,board_dict,index):
    root=Path(root);pair=read(root/'schedule.json')[index];board=Board.from_dict(board_dict)
    x,y=pair;players={};versions={k:s['identity'] for k,s in m['bots'].items()}
    seed=int(digest([m['seed'],index,'play'])[:12],16)
    budget=ForkBudget(**m['audit']);episodes={}
    try:
        players['candidate']=ArenaPlayer(m['bots'][x],root,m['bots']['3'] if x in ('4','P') else None)
        players['environment']=ArenaPlayer(m['bots'][y],root)
        order=(0,1) if seed%2 else (1,0)
        for room in order:
            budget.max_forks=max(0,m['audit']['max_forks']-budget.forks)
            seats=['candidate','environment'] if room==0 else ['environment','candidate']
            room_seed=int(digest([seed,room])[:12],16) if x==y else seed
            episodes[str(room)]=collect_board(board,players,seats*2,room_seed,budget,versions)
        score=None if x==y else imps(episodes['0']['tables'][0]['ns_score']-episodes['1']['tables'][0]['ns_score'])
        r=dict(schema='gen4-hybrid-mix-episode-v1',manifest_identity=m['identity'],index=index,
            family=deal_key(board.hands,True),board=board_dict,pair=pair,versions=versions,
            unique_tables=episodes,regimes={'common':dict(tables=['0','1'],imps=score)},
            imps=score,completed_epoch=time.time(),base_cpu=budget.base_cpu,branch_cpu=budget.branch_cpu)
        validate(r,m,board,index);return r
    finally:
        for p in players.values():p.close()

def compact(r):
    events=[a for e in r['unique_tables'].values() for a in e['audits']]
    return dict(index=r['index'],family=r['family'],pair=r['pair'],imps=r['imps'],
        own_imps=r['imps'],completed_epoch=r['completed_epoch'],base_cpu=r['base_cpu'],branch_cpu=r['branch_cpu'],
        deviations=sum(not a['identical_action'] for a in events),tables=sum(len(e['tables']) for e in r['unique_tables'].values()))

def summarize(rows,m):
    done={r['index'] for r in rows};contiguous=0
    while contiguous in done:contiguous+=1
    return dict(completed=len(rows),target=m['target'],total_imps=None,
        audited_deviations=sum(r['deviations'] for r in rows),tables=sum(r['tables'] for r in rows),best='4',
        contiguous=contiguous,by_pair=dict(Counter(r['pair'] for r in rows)),epoch=time.time())

def configured(root):
    import ops.mixed_generation as runtime
    from ops.independent_workers import IndependentWorkers
    IndependentWorkers.run=root;runtime.ProcessPoolExecutor=IndependentWorkers
    runtime.run_board=run_board;runtime.validate_pair=validate;runtime.compact=compact;runtime.summarize=summarize
    return runtime

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['init','run','audit']);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--source',type=Path);p.add_argument('--count',type=int,default=10000);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();root=a.run.resolve()
    if a.mode=='init':initialize(a.source.resolve(),root,a.count);return
    m=read(root/'manifest.json');verify_generation(root,m)
    if sha(root/'schedule.json')!=m['schedule_sha256']:raise ValueError('Changed mix schedule')
    runtime=configured(root)
    if a.mode=='audit':print(json.dumps(summarize(runtime.receipts(root,m,audit=True),m)));return
    from ops.watch_direct_arena import lock
    with lock(root/'.supervisor.lock'):
        while not (root/'STOP').exists():
            runtime.collect(root,60,a.workers)
            rows=runtime.receipts(root,m)
            if len(rows)==m['target']:break

if __name__=='__main__':main()
