"""Frozen paired component interventions on existing root tables; no arena writes."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
os.environ['BRIDGE_DDS_CACHE']=''
import sys,json,gzip,time,random,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path('/workspace/scratch/79c1d8b49652/bridge-gen4-local')
RUN=ROOT/'runs/gen4-supplement-20261109'
OUT=Path(__file__).parent/'gen4_diagnosis'
sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card,imps,symbol
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.fork_audit import stream

def init():
    global PLAYERS
    m=json.loads((RUN/'manifest.json').read_text());spec=m['bots']
    PLAYERS={k:ArenaPlayer(s,RUN) for k,s in spec.items()}
    PLAYERS['old_policy']=ArenaPlayer(dict(spec['4'],policy=spec['3']['policy']),RUN)
    PLAYERS['old_belief']=ArenaPlayer(dict(spec['4'],belief=spec['3']['belief']),RUN)

def play(job,variant):
    b=Board.from_dict(job['board'])
    if b.contract is None:return 0,[]
    g=Game(b);actions=[]
    while not g.done:
        o=g.observation();seat=o.controller
        role=variant if seat%2==job['side'] else job['opponent']
        c=PLAYERS[role].choose(o,stream(job['seed'],'play',b.id,len(actions),seat)).card
        g.play(c);actions.append(symbol(c))
    return g.ns_score(),actions

def work(job):
    started=time.time();cpu=time.process_time()
    out={k:job[k] for k in ('index','family','pair','side','opponent','score')}
    if job['check']:
        score,actions=play(job,'4')
        if score!=job['score'] or actions!=job['actions']:
            raise ValueError('Replay does not match '+str(job['index']))
        out['baseline_reproduced']=True
    for variant in ('old_policy','old_belief'):
        score,_=play(job,variant);d=(score-job['score'])*(1 if job['side']==0 else -1)
        out[variant]={'score':score,'delta_points':d,'gain_imps':imps(d)}
    out['seconds']=time.time()-started;out['cpu_seconds']=time.process_time()-cpu
    return out

def summary(rows):
    result={}
    for label in ['all','44','43','42','41']:
        selected=rows if label=='all' else [r for r in rows if r['pair']==label]
        if not selected:continue
        result[label]={}
        for variant in ('old_policy','old_belief'):
            v=np.array([r[variant]['gain_imps'] for r in selected]);n=len(v)
            se=float(v.std(ddof=1)/np.sqrt(n)) if n>1 else None
            result[label][variant]=dict(n=n,total=int(v.sum()),mean=float(v.mean()),se=se,
                ci95=None if se is None else [float(v.mean()-1.96*se),float(v.mean()+1.96*se)],
                wins=int((v>0).sum()),losses=int((v<0).sum()),ties=int((v==0).sum()))
    return result

def main():
    OUT.mkdir(exist_ok=True);jobsfile=OUT/'jobs.json'
    if jobsfile.exists():jobs=json.loads(jobsfile.read_text())
    else:
        jobs=[]
        for p in sorted((RUN/'episodes').glob('*.json.gz')):
            r=json.load(gzip.open(p,'rt'))
            if r['candidate']!='4':continue
            # Prespecified family hash selects one root room, independent of outcomes.
            side=int(r['family'][:8],16)%2
            regime=r['regimes'].get('common',r['regimes'].get('self'))
            t=r['unique_tables'][regime['tables'][side]]
            jobs.append(dict(index=r['index'],family=r['family'],pair=r['pair'],side=side,
                opponent=r['opponent'],board=t['board'],seed=t.get('seed',0),
                score=t['tables'][0]['ns_score'],actions=[a['card'] for a in t['tables'][0]['actions']],check=len(jobs)<8))
            if len(jobs)==500:break
        jobsfile.write_text(json.dumps(jobs))
    rows=[];done=set();results=OUT/'results.jsonl'
    if results.exists():
        rows=[json.loads(s) for s in results.read_text().splitlines()];done={r['index'] for r in rows}
    started=time.time()
    with ProcessPoolExecutor(max_workers=8,initializer=init) as pool:
        futures=[pool.submit(work,j) for j in jobs if j['index'] not in done]
        for f in as_completed(futures):
            r=f.result();rows.append(r)
            with results.open('a') as out:out.write(json.dumps(r)+'\n')
            if len(rows)%25==0 or len(rows)==len(jobs):
                s=summary(rows);(OUT/'summary.json').write_text(json.dumps(s,indent=2))
                print(json.dumps(dict(completed=len(rows),target=len(jobs),seconds=time.time()-started,all=s['all'])),flush=True)
    (OUT/'summary.json').write_text(json.dumps(summary(rows),indent=2))

if __name__=='__main__':main()
