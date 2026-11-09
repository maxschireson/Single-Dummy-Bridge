"""Resume a separate immutable cohort with persistent, single-threaded workers."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS'):
    os.environ[key]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

def initialize(root):
    global ROOT, MANIFEST, BIDDERS
    ROOT=Path(root); MANIFEST=json.loads((ROOT/'manifest.json').read_text())
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    from bridge_harness.bidding_ppo import Policy
    actors={};BIDDERS={}
    for name,spec in MANIFEST['bots'].items():
        checksum=spec['artifact_sha256']['bidding']
        if checksum not in actors:actors[checksum]=Policy.load(ROOT/spec['bidding'])
        BIDDERS[name]=actors[checksum]

def play(job):
    from bridge_harness.v4_arena import run_board
    index,board=job;started=time.time()
    record=run_board(ROOT,MANIFEST,board,index,BIDDERS)
    record['started_epoch']=started
    path=ROOT/'episodes'/f'{index:06d}.json.gz'
    temporary=path.with_suffix('.tmp')
    with gzip.open(temporary,'wt',compresslevel=3) as f:json.dump(record,f,separators=(',',':'))
    temporary.replace(path)
    return dict(index=index,pair=record['pair'],family=record['family'],split=record['split'],
        completed_epoch=record['completed_epoch'],seconds=time.time()-started,
        base_cpu=record['base_cpu'],branch_cpu=record['branch_cpu'],
        unique_tables=len(record['unique_tables']),
        audits=sum(len(t['audits']) for t in record['unique_tables'].values()),
        regimes={k:v['imps'] for k,v in record['regimes'].items()})

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--seconds',type=float,default=86400)
    a=p.parse_args();root=a.run.resolve();m=json.loads((root/'manifest.json').read_text())
    lock=(root/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if digest({k:v for k,v in m.items() if k!='identity'})!=m['identity']:raise ValueError('Manifest changed')
    if sha(root/m['corpus'])!=m['corpus_sha256']:raise ValueError('Corpus changed')
    repo=Path(__file__).resolve().parents[1]
    for name,checksum in m.get('runtime_sha256',{}).items():
        if sha(repo/name)!=checksum:raise ValueError('Runtime changed: '+name)
    for spec in m['bots'].values():
        for name,checksum in spec['artifact_sha256'].items():
            if sha(root/spec[name])!=checksum:raise ValueError('Model changed')
    boards=[json.loads(s) for s in (root/m['corpus']).read_text().splitlines()]
    directory=root/'episodes';directory.mkdir(exist_ok=True);done=set()
    for path in directory.glob('*.json.gz'):
        with gzip.open(path,'rt') as f:r=json.load(f)
        if r['manifest_identity']!=m['identity'] or r['index']!=int(path.name.split('.')[0]):raise ValueError('Wrong episode')
        done.add(r['index'])
    queue=iter(i for i in range(m['target']) if i not in done)
    started=time.time();initial=len(done);failures=0;pending={};stopping=False
    def status():
        elapsed=time.time()-started
        atomic_json(root/'status.json',dict(manifest_identity=m['identity'],completed=len(done),target=m['target'],
            workers=a.workers,in_flight=list(pending.values()),started_epoch=started,updated_epoch=time.time(),
            completed_this_session=len(done)-initial,session_per_hour=(len(done)-initial)*3600/max(elapsed,1),
            failures=failures,stopping=stopping))
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(str(root),)) as pool:
        def submit():
            index=next(queue,None)
            if index is not None:pending[pool.submit(play,(index,boards[index]))]=index
        for _ in range(a.workers):submit()
        while pending:
            finished,_=wait(pending,timeout=5,return_when=FIRST_COMPLETED)
            for future in finished:
                index=pending.pop(future)
                try:
                    row=future.result();done.add(index)
                    with (root/'progress.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
                    print(json.dumps(dict(completed=len(done),**row)),flush=True)
                except Exception as e:
                    failures+=1
                    with (root/'errors.jsonl').open('a') as f:f.write(json.dumps(dict(index=index,error=repr(e),epoch=time.time()))+'\n')
                    raise
                stopping=time.time()-started>=a.seconds or (root/'STOP').exists()
                if not stopping:submit()
            status()
    status()

if __name__=='__main__':main()
