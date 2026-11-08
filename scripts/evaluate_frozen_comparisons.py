#!/usr/bin/env python3
"""Fixed 500-deal frozen policy+belief comparisons; no training or tuning."""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_policy_over_belief import CoupledBeliefPlayer, BELIEF_HASH, POLICY_HASH
from bridge_harness.bidding_sampling import AuctionWeights
from bridge_harness.core import Board, Game, SEATS, card, hand_text, imps, symbol, auction_contract
from bridge_harness.corpus import load, save
from bridge_harness.players import PIMCPlayer, BenPlayer
from bridge_harness.policy_selector import SelectorPlayer, SelectorWeights
from bridge_harness.report import summarize
from bridge_harness.runner import play_table, replay
from bridge_harness.training import digest

CANDIDATE='belief-policy32'
BASELINES={'strict':'belief-best32','ben':'ben-full'}
SEED=20261602
NATIVE_HASH='7c76508d7082e5665872d89bcc580915ff90f8cd434a39d3704d762e72dc9870'
BEN_REVISION='9b5f43104aeac713a80b73513f2f2d6daf9f8769'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def read_episode(path):
    with gzip.open(path,'rt') as f:return json.load(f)
def store_episode(path,record):
    if path.exists():raise ValueError('Refusing to overwrite completed record')
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    with gzip.open(tmp,'wt') as f:json.dump(record,f)
    tmp.replace(path)

def settings(root,kind):
    p=read(root/'protocol.json')
    return dict(mode='partnership',candidate=CANDIDATE,baseline=BASELINES[kind],seed=SEED,
        samples=32,batch=True,objective='tricks',near_tie=.125,
        candidate_belief_sha256=BELIEF_HASH,policy_sha256=POLICY_HASH,
        baseline_belief_sha256=BELIEF_HASH if kind=='strict' else None,
        baseline_near_tie=0. if kind=='strict' else None,
        ben_revision=BEN_REVISION if kind=='ben' else None,
        ben_config_sha256=p['ben_config_sha256'] if kind=='ben' else None,
        ben_url=p['ben_url'] if kind=='ben' else None,
        comparison=kind,protocol_sha256=sha(root/'protocol.json'))

def validate_run(root):
    p=read(root/'protocol.json');boards=load(root/'play-corpus.jsonl')
    assert p['count']==len(boards)==500 and p['decision_seed']==SEED
    assert [digest(b.hands) for b in boards]==p['play_deal_ids']
    assert len(set(p['play_deal_ids']))==500
    assert sha(root/'belief_weights.npz')==BELIEF_HASH and sha(root/'policy_weights.npz')==POLICY_HASH
    assert sha(ROOT/'bridge_harness/libbridge_dds.so')==NATIVE_HASH
    assert sha(root/'exclusions.json')==p['exclusions_sha256']
    assert sha(root/'ben.conf')==p['ben_config_sha256']
    assert sha(root/'auctions/frozen.jsonl')==p['auctions_sha256']
    for name,expected in read(root/'provenance.json')['verified_source_sha256'].items():
        if name.startswith('bridge_harness/'):assert sha(ROOT/name)==expected,name
    return p,boards

def prepare(root):
    if (root/'protocol.json').exists():raise ValueError('Protocol already frozen')
    original=load(root/'source.jsonl');boards=load(root/'auctions/frozen.jsonl')
    m=read(root/'auctions/manifest.json');excluded=set(read(root/'exclusions.json')['deal_ids'])
    assert len(boards)==len(original)==512 and m['requested_deals']==512
    assert m['search'] is False and m['rescue'] is False and m['dds_calls']==0
    assert m['loaded_networks']==['bidder'] and m['scalar_checked']==16
    for a,b in zip(original,boards):
        assert (a.id,a.hands,a.dealer,a.vulnerability)==(b.id,b.hands,b.dealer,b.vulnerability)
        assert b.opening_lead is None and b.auction_source=='BEN-neural-only-batched'
        assert auction_contract(b.dealer,b.auction)==b.contract
    ids=[digest(b.hands) for b in boards]
    assert len(set(ids))==512 and not set(ids)&excluded
    selected=[b for b in boards if b.contract is not None][:500];assert len(selected)==500
    save(selected,root/'play-corpus.jsonl')
    atomic(root/'protocol.json',dict(count=500,generated_deals=512,deal_seed=20261601,decision_seed=SEED,
        generated_passed_out=sum(b.contract is None for b in boards),selection='first 500 playable in generation order, before play',
        generated_deal_ids=ids,play_deal_ids=[digest(b.hands) for b in selected],
        comparisons=['frozen policy+belief versus same belief, zero-band best PIMC',
                     'frozen policy+belief versus portable full-search BEN card play'],
        auctions='BEN neural only; one frozen auction per deal, shared across both tables and both comparisons',
        primary='candidate-oriented paired tricks per original deal',secondary='paired IMPs per original deal',
        horizon=500,interim_prefix=200,interval='95% original-deal bootstrap, 2000 resamples; nominal per comparison',
        no_outcome_based_stopping=True,no_retraining=True,all_source_deals_evaluation_only=True,
        exclusions_sha256=sha(root/'exclusions.json'),auctions_sha256=sha(root/'auctions/frozen.jsonl'),
        ben_config_sha256=sha(root/'ben.conf'),ben_url='http://127.0.0.1:8101',
        created_unix=time.time()))
    validate_run(root)

def pair(job,emit=None):
    data,root,kind=job;root=Path(root);b=Board.from_dict(data);cfg=settings(root,kind)
    belief=AuctionWeights(root/'belief_weights.npz')
    players={CANDIDATE:CoupledBeliefPlayer(SelectorPlayer(root/'policy_weights.npz'),belief,b.id,SEED)}
    players[BASELINES[kind]]=CoupledBeliefPlayer(PIMCPlayer(32,'tricks',True,0.),belief,b.id,SEED) if kind=='strict' else BenPlayer(cfg['ben_url'],600)
    assignments=[[CANDIDATE,BASELINES[kind]]*2,[BASELINES[kind],CANDIDATE]*2]
    r=dict(schema_version=1,board=data,config=cfg,assignments=assignments,tables=[],status='error')
    try:
        for i,assignment in enumerate(assignments):
            r['tables'].append(play_table(b,assignment,players,SEED,
                on_event=(lambda a,index=i:emit(dict(table=index,action=a))) if emit else None))
            if r['tables'][-1]['status']!='ok':return r
        a,c=r['tables'];r.update(status='ok',score_difference=a['ns_score']-c['ns_score'])
        r['imps']=imps(r['score_difference'])
        r['first_difference']=next((i for i,(x,y) in enumerate(zip(a['actions'],c['actions'])) if x['card']!=y['card']),None)
        replay(r);return r
    finally:
        for player in players.values():
            if hasattr(player,'close'):player.close()

def isolated_entry(conn,job):
    try:conn.send(('result',pair(job,lambda a:conn.send(('action',a)))))
    finally:conn.close()

def isolated(job,deadline=1800):
    ctx=mp.get_context('spawn');parent,child=ctx.Pipe(duplex=False)
    process=ctx.Process(target=isolated_entry,args=(child,job));process.start();child.close()
    until=time.monotonic()+deadline;actions=[[],[]];result=None
    try:
        while time.monotonic()<until:
            if parent.poll(.1):
                try:kind,value=parent.recv()
                except EOFError:break
                if kind=='result':result=value;break
                actions[value['table']].append(value['action'])
            elif not process.is_alive():break
        if result is None:
            data,root,kind=job
            result=dict(schema_version=1,board=data,config=settings(Path(root),kind),status='timeout' if time.monotonic()>=until else 'crash',
                error=f'Isolated worker exit {process.exitcode}; deadline {deadline}s',tables=[dict(status='incomplete',actions=a) for a in actions])
        return result
    finally:
        process.join(.2)
        if process.is_alive():process.terminate();process.join(2)
        if process.is_alive():process.kill();process.join()
        parent.close()

@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield

@contextmanager
def ben_server(root):
    ext=read(root/'ben-runtime.json');lock=Path(ext['resource_lock']);proc=None
    while True:
        memory=next(int(x.split()[1]) for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
        if memory<5*1024*1024:
            atomic(root/'ben/status.json',dict(status='waiting_for_memory',available_kib=memory,minimum_kib=5*1024*1024,updated_unix=time.time()))
            time.sleep(30);continue
        handle=lock.open('a')
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            handle.close();atomic(root/'ben/status.json',dict(status='waiting_for_BEN_resource',updated_unix=time.time()));time.sleep(30)
    try:
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ext['ben_dir'],text=True).strip()==BEN_REVISION
        for name,expected in read(root/'ben-models.json').items():assert sha(name)==expected,name
        with socket.socket() as sock:sock.bind(('127.0.0.1',8101))
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
        with (root/'ben/server.log').open('a') as log:
            proc=subprocess.Popen([ext['python'],'-u','src/gameapi.py','--config',str(root/'ben.conf'),
                '--host','127.0.0.1','--port','8101','--nolimit','true','--record','false'],cwd=ext['ben_dir'],env=env,stdout=log,stderr=subprocess.STDOUT)
            for _ in range(240):
                if proc.poll() is not None:raise RuntimeError('BEN startup failed')
                try:
                    with urlopen('http://127.0.0.1:8101',timeout=1) as response:response.read()
                    break
                except OSError:time.sleep(.5)
            else:raise TimeoutError('BEN startup timed out')
            yield
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        handle.close()

def play(root,kind,workers,stop_after=None):
    protocol,boards=validate_run(root);folder=root/kind
    for sub in ['episodes','failures']:(folder/sub).mkdir(parents=True,exist_ok=True)
    with exclusive(folder/'worker.lock'):
        jobs=[];completed=0
        for b in boards:
            path=folder/'episodes'/f'{digest(b.hands)}.json.gz'
            if path.exists():
                r=read_episode(path);assert r['status']=='ok' and r['board']==b.to_dict() and r['config']==settings(root,kind)
                assert all(t['complete'] and t['plies']==52 for t in replay(r));completed+=1
            else:jobs.append((b.to_dict(),str(root),kind))
        with (folder/'invocations.jsonl').open('a') as f:f.write(json.dumps(dict(started_unix=time.time(),workers=workers,resumed_pairs=completed,source_sha256=sha(__file__)))+'\n')
        if stop_after is not None:jobs=jobs[:stop_after]
        audits=[];started=time.monotonic()
        def saved(r):
            nonlocal completed
            did=digest(Board.from_dict(r['board']).hands)
            if r['status']!='ok':
                store_episode(folder/'failures'/f'{did}-{time.time_ns()}.json.gz',r)
                atomic(folder/'status.json',dict(status='failed_attempt',completed_pairs=completed,deal_id=did,updated_unix=time.time()))
                raise RuntimeError('Failed attempt preserved; inspect before resuming')
            store_episode(folder/'episodes'/f'{did}.json.gz',r);completed+=1
            atomic(folder/'status.json',dict(status='playing',completed_pairs=completed,elapsed_seconds=time.monotonic()-started,updated_unix=time.time()))
            if completed%25==0:print(json.dumps(dict(comparison=kind,completed_pairs=completed,seconds=time.monotonic()-started)),flush=True)
            if not (folder/'audit-200.json').exists() and not audits and all((folder/'episodes'/f'{d}.json.gz').exists() for d in protocol['play_deal_ids'][:200]):
                stream=(folder/'audit-200.log').open('a')
                audits.append((subprocess.Popen([sys.executable,'-u',__file__,'--run',str(root),'--mode','audit','--opponent',kind,'--count','200'],stdout=stream,stderr=subprocess.STDOUT),stream))
        if jobs and kind=='ben':
            with ben_server(root):
                for job in jobs:saved(isolated(job))
        elif jobs:
            # Spawn clean workers; do not fork a retained corpus of replay records.
            with ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn')) as pool:
                iterator=iter(jobs);pending=set()
                for _ in range(workers):
                    job=next(iterator,None)
                    if job:pending.add(pool.submit(pair,job))
                while pending:
                    done,pending=wait(pending,return_when=FIRST_COMPLETED)
                    for f in done:
                        saved(f.result());job=next(iterator,None)
                        if job:pending.add(pool.submit(pair,job))
        for proc,stream in audits:
            if proc.wait():raise RuntimeError('Interim audit failed; inspect audit-200.log')
            stream.close()
        if completed==500:
            if not (folder/'audit-200.json').exists():audit(root,kind,200)
            audit(root,kind,500)
            atomic(folder/'status.json',dict(status='audited',completed_pairs=500,updated_unix=time.time()))

def audit(root,kind,count):
    protocol,boards=validate_run(root);assert count in (1,200,500)
    selector=SelectorWeights(root/'policy_weights.npz');records=[];folder=root/kind
    counts=dict(independent_deals=0,complete_games=0,plies=0,pimc_nonforced=0,policy_decisions=0,policy_below_pimc_best=0,common_positions=0,ben_nonforced=0)
    for b in boards[:count]:
        r=read_episode(folder/'episodes'/f'{digest(b.hands)}.json.gz')
        assert r['status']=='ok' and r['board']==b.to_dict() and r['config']==settings(root,kind)
        assignments=[[CANDIDATE,BASELINES[kind]]*2,[BASELINES[kind],CANDIDATE]*2]
        assert r['assignments']==assignments and len(r['tables'])==2
        assert all(t['complete'] and t['plies']==52 for t in replay(r))
        assert r['score_difference']==r['tables'][0]['ns_score']-r['tables'][1]['ns_score']
        assert r['imps']==imps(r['score_difference']);common={}
        for i,t in enumerate(r['tables']):
            game=Game(b)
            for a in t['actions']:
                o=game.observation();assert a['player']==assignments[i][o.controller]
                assert a['seat']==SEATS[o.actor] and a['controller']==SEATS[o.controller]
                if a['player']=='ben-full':
                    if len(o.legal)==1:assert a['forced']
                    else:
                        counts['ben_nonforced']+=1
                        params=dict(hand=hand_text(o.original_hand(o.controller)),seat=SEATS[o.controller],dealer=SEATS[o.dealer],vul=o.vulnerability,ctx=BenPlayer.context(o.auction),matchtype='IMP',details='false')
                        if o.history:params.update(dummy=hand_text(o.original_hand(o.contract.dummy)),played=''.join(symbol(c) for _,c in o.history),format='false')
                        assert a['request']==params and a['endpoint']==('play' if o.history else 'lead')
                        assert card(a['response']['card'])==card(a['card'])
                else:
                    assert a['belief_sha256']==BELIEF_HASH and a['sampler']=='auction-weighted-dp' and a['strength']==1.
                    if len(o.legal)==1:assert a['forced'] and a['samples']==a['dds_calls']==0
                    else:
                        counts['pimc_nonforced']+=1;band=.125 if a['player']==CANDIDATE else 0.
                        assert a['samples']==a['dds_calls']==32 and a['batch'] is True and a['objective']=='tricks' and a['near_tie']==band
                        assert set(a['estimates'])=={symbol(c) for c in o.legal}
                        support=a.get('proposal_probabilities',a['behavior_probabilities'])
                        eligible={c for c,v in a['estimates'].items() if v['gap_to_best']<=band+1e-9}
                        assert {c for c,p in support.items() if p>0}==eligible
                        assert all(abs(support[c]-1/len(eligible))<1e-8 for c in eligible)
                        assert a['card'] in eligible and a['selected_pimc_gap']<=band+1e-9
                        assert abs(sum(a['behavior_probabilities'].values())-1)<1e-8 and a['behavior_probabilities'][a['card']]>0
                        key=(o.controller,o.history);signature=(a['sampled_worlds_sha256'],a['estimates'])
                        if key in common:assert signature==common[key];counts['common_positions']+=1
                        else:common[key]=signature
                        if a.get('selector'):
                            assert a['player']==CANDIDATE and len(eligible)>1
                            _,pred=selector.choose(o,dict(a,behavior_probabilities=support),random.Random(0))
                            assert pred=={card(c):v for c,v in a['selector_predictions'].items()}
                            assert max(pred.values())-pred[card(a['card'])]<=1e-7
                            counts['policy_decisions']+=1;counts['policy_below_pimc_best']+=a['selected_pimc_gap']>0
                        else:assert a['player']!=CANDIDATE or len(eligible)==1
                game.play(card(a['card']));counts['plies']+=1
        first=next((i for i,(x,y) in enumerate(zip(r['tables'][0]['actions'],r['tables'][1]['actions'])) if x['card']!=y['card']),None)
        assert first==r['first_difference']
        if kind=='strict' and first is not None:
            at=[t['actions'][first] for t in r['tables']]
            assert at[0]['sampled_worlds_sha256']==at[1]['sampled_worlds_sha256']
        counts['independent_deals']+=1;counts['complete_games']+=2;records.append(r)
    counts.update(dds_world_solves=32*counts['pimc_nonforced'],failed_attempts=len(list((folder/'failures').glob('*.json.gz'))),
        excluded_original_deals=len(read(root/'exclusions.json')['deal_ids']),zero_overlap_with_exclusions=True,
        passed_out_source_deals=protocol['generated_passed_out'],fixed_prefix=True,source_sha256=sha(__file__))
    assert not set(protocol['generated_deal_ids'])&set(read(root/'exclusions.json')['deal_ids'])
    result=summarize(sorted(records,key=lambda r:digest(Board.from_dict(r['board']).hands)))
    assert result['completed_pairs']==result['independent_clusters']==count
    atomic(folder/f'summary-{count}.json',result);atomic(folder/f'audit-{count}.json',counts)
    print(json.dumps(dict(comparison=kind,count=count,audit=counts,summary=result)),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--mode',choices=['prepare','play','audit'],required=True);p.add_argument('--opponent',choices=['strict','ben'],default='strict')
    p.add_argument('--workers',type=int,default=4);p.add_argument('--count',type=int,choices=[1,200,500],default=500)
    p.add_argument('--stop-after',type=int);a=p.parse_args();root=a.run.resolve()
    if a.mode=='prepare':prepare(root)
    elif a.mode=='play':play(root,a.opponent,a.workers,a.stop_after)
    else:audit(root,a.opponent,a.count)
if __name__=='__main__':main()
