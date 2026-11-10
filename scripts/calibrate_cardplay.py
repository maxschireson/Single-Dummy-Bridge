"""Resumable matched cardplay tests with frozen auctions and timed decisions."""
import argparse
import configparser
from dataclasses import replace
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen

for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS'):
    os.environ[k]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
os.environ['TF_ENABLE_ONEDNN_OPTS']='0'
os.environ['BRIDGE_DDS_CACHE']=''
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
os.environ.setdefault('DOTNET_ROOT',str(BASE/'dotnet'))
os.environ.setdefault('ACE_DIR',str(ROOT/'vendor/ace'))
sys.path[:0]=[str(ROOT),str(BASE/'python-deps')]
import numpy as np
from bridge_harness.core import Board,Game,auction_contract,imps
from bridge_harness.bidding_env import BidObservation,CALLS,encode,legal_mask,pack_inputs,deal_key
from bridge_harness.runner import play_table,replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.loop_registry import sha

OLD=ROOT/'fixtures/v5-ben-100'
BEN=Path(os.environ.get('BEN_ROOT','/workspace/scratch/63fa72341134/ben-runtime'))

def prepare(a):
    run=a.run;run.mkdir(parents=True,exist_ok=True)
    if (run/'manifest.json').exists():
        return
    raw=[Board.from_dict(json.loads(s)) for s in (OLD/'boards.jsonl').read_text().splitlines()]
    if a.kind=='ben':
        rows=json.loads((OLD/'auctions.json').read_text())
        for row in rows:
            for room in row['rooms']:
                room['assignments']=['v5' if x=='v5' else a.kind for x in room['assignments']]
    else:
        shared=ROOT/'runs/ace-shared-auctions.json'
        if shared.exists():rows=json.loads(shared.read_text())
        else:
            from bridge_harness.bidding_ppo import Policy
            bidder=Policy.load(ROOT/'models/ace-v5-frozen/bidder.keras')
            rows=[]
            for index,board in enumerate(raw):
                calls=[]
                for _ in range(320):
                    seat=(board.dealer+len(calls))%4
                    o=BidObservation(board.hands[seat],seat,board.dealer,board.vulnerability,tuple(calls))
                    x,n=pack_inputs([encode(o)]);p,_=bidder.predict(x,n)
                    mask=legal_mask(board.dealer,calls)
                    calls.append(CALLS[int(np.argmax(np.where(mask,p[0],-np.inf)))])
                    try:contract=auction_contract(board.dealer,calls)
                    except ValueError as e:
                        if str(e)!='Incomplete auction':raise
                        continue
                    break
                else:raise RuntimeError('Auction too long')
                board=replace(board,contract=contract,auction=tuple(calls),opening_lead=None,
                              auction_source='frozen-v5-net-only-all-four-seats')
                rows.append(dict(index=index,family=deal_key(board.hands,True),rooms=[
                    dict(board=board.to_dict(),assignments=['v5' if s%2==side else 'ace' for s in range(4)])
                    for side in (0,1)]))
                if index%20==0:print(json.dumps(dict(phase='ace-auctions',boards=index+1)),flush=True)
            atomic_json(shared,rows)
    indices=list(map(int,a.indices.split(','))) if a.indices else list(range(100))
    rows=[r for r in rows if r['index'] in indices]
    atomic_json(run/'auctions.json',rows)
    cfg=configparser.ConfigParser();cfg.read(OLD/'ben.conf')
    cfg['cardplay']['sample_hands_play']=str(a.ben_samples)
    cfg['cardplay']['min_sample_hands_play']=str(min(a.ben_samples,20))
    cfg['cardplay']['min_sample_hands_play_bad']=str(min(a.ben_samples,12))
    cfg['sampling']['sample_hands_opening_lead']=str(a.ben_samples)
    with (run/'ben.conf').open('w') as f:cfg.write(f)
    manifest=dict(schema='timed-cardplay-v1',kind=a.kind,target=len(rows),indices=indices,
        v5_samples=a.v5_samples,ben_samples=a.ben_samples,ace_ms=a.ace_ms,ace_lead_ms=a.ace_lead_ms,
        ace_depth=4,ace_threads=1,ace_exploration=.0058,ace_limiter=False,
        ace_version='1.0.5',ace_dll_sha256=sha(ROOT/'vendor/ace/Ace.dll'),
        ace_native_sha256=sha(ROOT/'vendor/ace/libbcalcdds.so'),
        ace_belief='v5 dense -> 32 legal samples -> original-hand min/max HCP and shape, margins 2 HCP/1 card',
        inference_note='ACE uses broad constraints, not exact v5 card-location probabilities',
        model_hashes={k:sha(ROOT/'models/ace-v5-frozen'/v) for k,v in
                      [('policy','policy.npz'),('belief','belief.npz'),('bidding','bidder.keras')]},
        auctions_sha256=sha(run/'auctions.json'),ben_config_sha256=sha(run/'ben.conf'),
        source_manifest=json.loads((OLD/'manifest.json').read_text()),
        evaluation_only=True,persistent_dds_cache=False,seed=193720,
        code_hashes={f:sha(ROOT/f) for f in ['scripts/calibrate_cardplay.py','bridge_harness/ace_player.py']},
        created=time.time(),timing='per-decision elapsed; worker and native threads pinned to 1')
    atomic_json(run/'manifest.json',manifest)

def verify_manifest(run,m):
    for k,f in [('policy','policy.npz'),('belief','belief.npz'),('bidding','bidder.keras')]:
        if sha(ROOT/'models/ace-v5-frozen'/f)!=m['model_hashes'][k]:
            raise RuntimeError(f'Frozen model changed: {k}')
    for f,key in [('auctions.json','auctions_sha256'),('ben.conf','ben_config_sha256')]:
        if sha(run/f)!=m[key]:raise RuntimeError(f'Frozen input changed: {f}')
    for f,digest in m.get('code_hashes',{}).items():
        if sha(ROOT/f)!=digest:raise RuntimeError(f'Frozen code changed: {f}')
    for f,key in [('Ace.dll','ace_dll_sha256'),('libbcalcdds.so','ace_native_sha256')]:
        if sha(ROOT/'vendor/ace'/f)!=m[key]:raise RuntimeError(f'ACE binary changed: {f}')

def worker(a):
    from bridge_harness.mixed_arena import ArenaPlayer
    run=a.run;m=json.loads((run/'manifest.json').read_text())
    verify_manifest(run,m)
    opponent=m['kind'];server=None;log=None;players={}
    try:
        spec=dict(id='v5-frozen',policy='models/ace-v5-frozen/policy.npz',
                  belief='models/ace-v5-frozen/belief.npz',belief_kind='public',
                  samples=m['v5_samples'],near_tie=.125,exploration=0.)
        players['v5']=ArenaPlayer(spec,ROOT)
        if opponent=='ace':
            from bridge_harness.ace_player import ACEPlayer
            players['ace']=ACEPlayer(ROOT/spec['belief'],m['ace_ms'],m['ace_lead_ms'])
        else:
            from bridge_harness.players import BenPlayer
            port=a.port+a.worker
            log=(run/f'ben-{a.worker}.log').open('a')
            server=subprocess.Popen([sys.executable,'-u','src/gameapi.py','--config',str(run/'ben.conf'),
                '--host','127.0.0.1','--port',str(port),'--nolimit','true','--record','false'],
                cwd=BEN,stdout=log,stderr=subprocess.STDOUT)
            url=f'http://127.0.0.1:{port}'
            for _ in range(180):
                if server.poll() is not None:raise RuntimeError('BEN failed to start')
                try:
                    with urlopen(url,timeout=1) as r:r.read()
                    break
                except OSError:time.sleep(.5)
            else:raise RuntimeError('BEN startup timeout')
            players['ben']=BenPlayer(url,180)
        rows=json.loads((run/'auctions.json').read_text())
        (run/'episodes').mkdir(exist_ok=True)
        for ordinal,row in enumerate(rows):
            if ordinal%a.workers!=a.worker:continue
            index=row['index'];target=run/'episodes'/f'{index:03d}.json.gz'
            if target.exists():continue
            start=time.time();tables=[]
            for room_id in ((0,1) if index%2==0 else (1,0)):
                room=row['rooms'][room_id];board=Board.from_dict(room['board'])
                def progress(act):
                    if act['ply']%4==0:
                        atomic_json(run/f'worker-{a.worker}-status.json',dict(index=index,room=room_id,
                            ply=act['ply'],last_seconds=act['seconds'],updated=time.time()))
                table=play_table(board,room['assignments'],players,seed=m['seed']+index,on_event=progress)
                record=dict(board=board.to_dict(),tables=[table],assignments=room['assignments'])
                if table['status']!='ok':
                    atomic_json(run/f'failed-{index}-{room_id}.json',record)
                    raise RuntimeError(table['traceback'])
                replay(record);tables.append(dict(room=room_id,record=record))
            tables.sort(key=lambda t:t['room'])
            scores=[t['record']['tables'][0]['ns_score'] for t in tables]
            result=dict(index=index,family=row['family'],tables=tables,
                score_difference=scores[0]-scores[1],imps=imps(scores[0]-scores[1]),
                seconds=time.time()-start,completed=time.time())
            tmp=target.with_suffix('.tmp')
            with gzip.open(tmp,'wt') as f:json.dump(result,f)
            tmp.replace(target)
            print(json.dumps(dict(index=index,imps=result['imps'],seconds=result['seconds'])),flush=True)
    except Exception:
        with (run/'errors.jsonl').open('a') as f:f.write(json.dumps(dict(worker=a.worker,error=traceback.format_exc(),time=time.time()))+'\n')
        raise
    finally:
        for p in players.values():
            if hasattr(p,'close'):p.close()
        if server:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        if log:log.close()

def summarize(a):
    m=json.loads((a.run/'manifest.json').read_text());rows=[]
    times={p:[] for p in ('v5',m['kind'])};nonforced={p:[] for p in times}
    iterations=[];retries=0
    for path in sorted((a.run/'episodes').glob('*.json.gz')):
        with gzip.open(path,'rt') as f:r=json.load(f)
        for t in r['tables']:
            replay(t['record'])
            for act in t['record']['tables'][0]['actions']:
                p=act['player'];times[p].append(act['seconds'])
                if not act.get('forced'):nonforced[p].append(act['seconds'])
                if p=='ace' and not act.get('forced'):
                    iterations.append(act['iterations']);retries+=act['retry']
        scores=[t['record']['tables'][0]['ns_score'] for t in r['tables']]
        assert r['imps']==imps(scores[0]-scores[1]);rows.append(r)
    n=len(rows);v=np.array([r['imps'] for r in rows],float)
    timing={p:dict(total_seconds=sum(t),seconds_per_paired_board=sum(t)/n if n else None,
        nonforced_mean_ms=1000*np.mean(nonforced[p]) if nonforced[p] else None,
        p95_ms=float(1000*np.percentile(nonforced[p],95)) if nonforced[p] else None,
        decisions=len(t)) for p,t in times.items()}
    report=dict(kind=m['kind'],boards=n,target=m['target'],complete=n==m['target'],
        imps=int(v.sum()),imps_per_board=float(v.mean()) if n else None,
        se=float(v.std(ddof=1)/math.sqrt(n)) if n>1 else None,
        wins=int((v>0).sum()),losses=int((v<0).sum()),ties=int((v==0).sum()),
        timing=timing,opponent_to_v5_time=sum(times[m['kind']])/sum(times['v5']) if sum(times['v5']) else None,
        ace_iterations_median=float(np.median(iterations)) if iterations else None,
        ace_iterations_p10=float(np.percentile(iterations,10)) if iterations else None,
        ace_retries=retries,updated=time.time())
    if n>1:
        rr=np.random.default_rng(20261110);means=v[rr.integers(0,n,(20000,n))].mean(1)
        report['ci95']=np.percentile(means,[2.5,97.5]).tolist()
    atomic_json(a.run/'result.json',report)
    print(json.dumps(report),flush=True)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','worker','summary'])
    p.add_argument('--run',type=Path,required=True);p.add_argument('--kind',choices=['ben','ace'],default='ace')
    p.add_argument('--v5-samples',type=int,default=64);p.add_argument('--ben-samples',type=int,default=16)
    p.add_argument('--ace-ms',type=int,default=300);p.add_argument('--ace-lead-ms',type=int,default=1500)
    p.add_argument('--indices',default='');p.add_argument('--workers',type=int,default=4)
    p.add_argument('--worker',type=int,default=0);p.add_argument('--port',type=int,default=18300)
    a=p.parse_args();a.run=a.run.resolve()
    if a.command=='summary':summarize(a);return
    if a.command=='worker':worker(a);return
    prepare(a)
    if a.command=='prepare':return
    import fcntl
    lock=(a.run/'writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    children=[]
    for i in range(a.workers):
        log=(a.run/f'worker-{i}.log').open('a')
        child=subprocess.Popen([sys.executable,'-u',__file__,'worker','--run',str(a.run),
             '--workers',str(a.workers),'--worker',str(i),'--port',str(a.port)],stdout=log,stderr=subprocess.STDOUT)
        children.append((child,log))
    while any(c.poll() is None for c,l in children):
        time.sleep(10);summarize(a)
    for c,l in children:l.close()
    summarize(a)
    if any(c.returncode for c,l in children):raise SystemExit('Worker failed; see errors.jsonl')

if __name__=='__main__':main()
