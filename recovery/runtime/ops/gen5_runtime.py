"""Frozen Gen5 two-bidding-condition arena, with a separate single BEN lane."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import fcntl
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,imps
from bridge_harness.corpus import load
from bridge_harness.gen5_arena import run_board
from bridge_harness.mixed_arena import ArenaPlayer,verify_generation
from bridge_harness.round5_ben import Round5BenPlayer
from bridge_harness.decision_timing import from_record
from bridge_harness.selfplay import atomic_json
from bridge_harness.runner import replay
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest

BIDDERS={}
def initialize_worker(root):
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    from bridge_harness.bidding_ppo import Policy
    root=Path(root);m=json.loads((root/'manifest.json').read_text());actors={}
    for key,spec in m['bots'].items():
        checksum=spec['artifact_sha256']['bidding']
        if checksum not in actors:actors[checksum]=Policy.load(root/spec['bidding'])
        BIDDERS[key]=actors[checksum]

def player(spec,root,reference=None):
    if spec.get('engine')=='ben':return Round5BenPlayer(spec['url'],timeout=600,samples=spec['samples'])
    if spec.get('engine')=='gen6':
        from bridge_harness.gen6 import Gen6Player
        return Gen6Player(spec,root,reference)
    if spec.get('engine')=='gen7':
        from bridge_harness.gen7 import Gen7Player
        return Gen7Player(spec,root,reference)
    return ArenaPlayer(spec,root,reference)

def validate(r,m,index):
    if r['manifest_identity']!=m['identity'] or r['index']!=index:raise ValueError('Changed record identity')
    schedule=m['pair_schedule'];block=schedule.copy()
    from bridge_harness.fork_audit import stream
    stream(m['seed'],'pair-block',index//len(block)).shuffle(block)
    if r['pair']!=block[index%len(block)]:raise ValueError('Changed matchup')
    from bridge_harness.arena_pairs import pair_members
    candidate,opponent=pair_members(r['pair'])
    if r['candidate']!=candidate or r['opponent']!=opponent:raise ValueError('Changed candidate/opponent')
    self_play=candidate==opponent
    if set(r['regimes'])!=({'self'} if self_play else {'common','native'}):raise ValueError('Missing bidding condition')
    if r['versions']!={k:v['identity'] for k,v in m['bots'].items()}:raise ValueError('Wrong versions')
    for key,e in r['unique_tables'].items():
        if e.get('schema_version')!='v4-passed-out-v1':replay(e)
    if self_play:
        condition=r['regimes']['self']
        if condition['imps'] is not None or condition['score_difference'] is not None:raise ValueError('Self-play has no strength comparison')
        if len(condition['tables'])!=(2 if m.get('two_self_rooms') else 1):raise ValueError('Wrong self-play table count')
        for room,key in enumerate(condition['tables']):
            e=r['unique_tables'][key];bids=r['bidding'][f'self/{room}']
            if e['assignments']!=['candidate']*4:raise ValueError('Wrong self-play assignments')
            if bids['bidders']!=[m.get('common_bidder',candidate)]*4 or bids['calls']!=list(e['board']['auction']):raise ValueError('Wrong self-play auction')
        return
    for regime,condition in r['regimes'].items():
        if len(condition['tables'])!=2:raise ValueError('Missing swapped room')
        scores=[]
        for room,key in enumerate(condition['tables']):
            e=r['unique_tables'][key];expected=['candidate' if seat%2==room else 'opponent' for seat in range(4)]
            if e['assignments']!=expected:raise ValueError('Wrong partnership')
            scores.append(e['tables'][0]['ns_score']);bids=r['bidding'][f'{regime}/{room}']
            actors=[m.get('common_bidder',candidate)]*4 if regime=='common' else [candidate if role=='candidate' else r['opponent'] for role in expected]
            if bids['bidders']!=actors or bids['calls']!=list(e['board']['auction']):raise ValueError('Wrong bidder/auction')
        if condition['score_difference']!=scores[0]-scores[1] or condition['imps']!=imps(scores[0]-scores[1]):raise ValueError('Wrong score orientation')
    common=[r['unique_tables'][k]['board']['auction'] for k in r['regimes']['common']['tables']]
    if common[0]!=common[1]:raise ValueError('Common auction changed')

def play(root,m,board,index):
    r=run_board(root,m,board,index,BIDDERS,player_factory=player)
    validate(r,m,index);r['decision_timing']=from_record(r)
    return r

def state(rows,m):
    done={r['index'] for r in rows};contiguous=0
    while contiguous in done:contiguous+=1
    return dict(manifest_identity=m['identity'],completed=len(rows),target=m['target'],contiguous=contiguous,
        by_pair=dict(Counter(r['pair'] for r in rows)),root_games=sum(r['root_games'] for r in rows),
        tables=sum(r['tables'] for r in rows),failures=0,epoch=time.time(),complete=len(rows)==m['target'])

def receipt(r,path):
    common=r['regimes'].get('common',r['regimes'].get('self'))
    native=r['regimes'].get('native',r['regimes'].get('self'))
    return dict(index=r['index'],family=r['family'],split=r['split'],pair=r['pair'],
        manifest_identity=r['manifest_identity'],episode_sha256=sha(path),completed_epoch=r['completed_epoch'],
        imps=common['imps'],own_imps=native['imps'],
        root_games=len(r['unique_tables']),tables=sum(len(e['tables']) for e in r['unique_tables'].values()),decision_timing=r['decision_timing'])

def run(root,workers):
    root=Path(root);root.mkdir(exist_ok=True)
    with (root/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        m=json.loads((root/'manifest.json').read_text());verify_generation(root,m)
        boards=load(root/m['corpus']);rows=[]
        for path in sorted((root/'episodes').glob('*.json.gz')):
            item=root/'receipts'/(path.name.removesuffix('.json.gz')+'.json')
            if item.exists():
                r=json.loads(item.read_text())
                if r['manifest_identity']!=m['identity'] or r['episode_sha256']!=sha(path):raise ValueError('Changed archived record')
            else:
                with gzip.open(path,'rt') as f:record=json.load(f)
                validate(record,m,record['index']);r=receipt(record,path);atomic_json(item,r)
            rows.append(r)
        done={r['index'] for r in rows}
        if len(done)!=len(rows) or len({r['family'] for r in rows})!=len(rows):raise ValueError('Duplicate family/index')
        if list((root/'failures').glob('*.json')):raise ValueError('Preserved failure requires inspection')
        from bridge_harness.fork_audit import stream
        def pair_at(i):
            block=m['pair_schedule'].copy();stream(m['seed'],'pair-block',i//len(block)).shuffle(block);return block[i%len(block)]
        fast=iter(i for i in range(m['target']) if i not in done and 'ben' not in pair_at(i))
        slow=iter(i for i in range(m['target']) if i not in done and 'ben' in pair_at(i))
        os.environ['BRIDGE_DDS_CACHE']=str(root/'dds-cache.sqlite')
        pending={};started=time.time()
        with ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(root),)) as normal,ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(root),)) as ben:
            def submit(pool,jobs):
                if (root/'STOP').exists():return
                index=next(jobs,None)
                if index is not None:pending[pool.submit(play,str(root),m,boards[index].to_dict(),index)]=(index,pool,jobs)
            for _ in range(workers):submit(normal,fast)
            submit(ben,slow)
            while pending:
                finished,_=wait(pending,timeout=10,return_when=FIRST_COMPLETED)
                atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=len(rows),in_flight=sorted(x[0] for x in pending.values()),workers=workers+1,ben_workers=1,started_epoch=started,stopping=(root/'STOP').exists()))
                for future in finished:
                    index,pool,jobs=pending.pop(future)
                    try:r=future.result()
                    except BaseException as e:
                        atomic_json(root/'failures'/f'{index:06d}.json',dict(index=index,error=repr(e),epoch=time.time()));raise
                    path=root/'episodes'/f'{index:06d}.json.gz'
                    if path.exists():raise ValueError('Refusing to overwrite completed game')
                    atomic_json(path,r,compressed=True);item=receipt(r,path);atomic_json(root/'receipts'/f'{index:06d}.json',item);rows.append(item)
                    atomic_json(root/'state.json',state(rows,m));print(json.dumps(dict(completed=len(rows),index=index,pair=r['pair'],common=item['imps'],native=item['own_imps'])),flush=True)
                    submit(pool,jobs)
        atomic_json(root/'state.json',state(rows,m))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--workers',type=int,default=3);a=p.parse_args()
    run(a.run.resolve(),a.workers)
