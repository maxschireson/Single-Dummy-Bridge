"""Fixed100-family common-auction Gen6 cardplay vs frozen5RZ, equal32 layouts."""
import os,sys,json,gzip,time,fcntl,multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS'):os.environ[k]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3';os.environ['TF_ENABLE_ONEDNN_OPTS']='0';os.environ['BRIDGE_DDS_CACHE']=''
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'whole-game-100';REPO=Path('/workspace/scratch/919dc41e3067/bridge-gen5rz-ben')
sys.path.insert(0,str(REPO))
import numpy as np
from bridge_harness.bidding_env import make_board,deal_key
from bridge_harness.core import Board,imps
from bridge_harness.gen5_arena import auction
from bridge_harness.gen5r import reduction,load_plan
from bridge_harness.loop_registry import sha
from bridge_harness.runner import play_table,replay
from bridge_harness.selfplay import atomic_json

def savegz(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(json.dumps(d).encode(),mtime=0));tmp.replace(p)
def readgz(p):return json.loads(gzip.decompress(p.read_bytes()))
def collect(v,s):
    if isinstance(v,str) and len(v)==64:s.add(v)
    elif isinstance(v,dict):
        for k,x in v.items():collect(k,s);collect(x,s)
    elif isinstance(v,list):
        for x in v:collect(x,s)
def verify(m):
    for p,h in m['hashes'].items():assert sha(Path(p))==h,p
    assert sha(RUN/'auctions.json')==m['auctions_sha256']
def prepare():
    if (RUN/'manifest.json').exists():
        m=json.loads((RUN/'manifest.json').read_text());verify(m);return m
    from bridge_harness.bidding_ppo import Policy
    sources=[ROOT/'belief-full1513/manifest.json',ROOT/'policy-full1513/union/families.json',ROOT/'raw-policy-1513/receipts.json']
    sources += [Path('/workspace/scratch/e9691f0e7615/belief-lab/runs/belief-lab-20261110/data/manifest.json'),Path('/workspace/scratch/919dc41e3067/bridge-ddsd-corrector/reports/gen6-ddsd-fresh-256-2026-11-10/reserved-families.json')]
    excluded=set()
    for p in sources:collect(json.loads(p.read_text()),excluded)
    for p in REPO.glob('reports/**/reserved-families.json'):collect(json.loads(p.read_text()),excluded)
    candidate=dict(policy=str(ROOT/'policy-full1513/fit/best.npz'),belief=str(ROOT/'belief-full1513/fit/best.npz'))
    baseline=dict(policy=str(REPO/'models/cardplay/gen5-2026-11-10/policy.npz'),belief=str(REPO/'models/cardplay/gen5-belief-2026-11-10/belief.npz'))
    assert sha(Path(candidate['policy']))=='c48675e15adff57e5f662827ec4438b2803a63a88414b39aee69e9ac22a2fb99'
    assert sha(Path(candidate['belief']))=='f6e3443b0e7fddcc51e6c4585cb5d5a8ece13077d33b772e8256a4e10fcec7a4'
    assert sha(Path(baseline['policy']))=='03e70a6f6021c8bed471dc9de53f462b0e991320ff4ad7734bcc20f54c5aff18'
    assert sha(Path(baseline['belief']))=='99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a'
    specs={name:dict(id=name,samples=32,near_tie=0.,exploration=0.,belief_kind='public',policy_role='pimc-ties-only',layout_reduction=reduction(load_plan(),32),**models) for name,models in [('gen6',candidate),('5RZ',baseline)]}
    bidderpath=REPO/'models/bidding/gen5-2026-11-10/bidder.keras';assert sha(bidderpath)=='9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc'
    bidder=Policy.load(bidderpath);seed=202611102150;rows=[];index=0
    while len(rows)<100:
        b=make_board(seed,index,'test');index+=1;family=deal_key(b.hands,True)
        if family in excluded:continue
        excluded.add(family);bid,decisions=auction(b,[bidder]*4)
        rows.append(dict(index=len(rows),family=family,board=bid.to_dict(),raw_board=b.to_dict(),bidding=decisions))
    atomic_json(RUN/'reserved-families.json',[r['family'] for r in rows]);atomic_json(RUN/'auctions.json',rows)
    paths=[Path(__file__),bidderpath,REPO/'bridge_harness/libbridge_dds.so']+list((REPO/'bridge_harness').glob('*.py'))+[Path(p) for x in [candidate,baseline] for p in x.values()]
    m=dict(target=100,seed=seed,specs=specs,hashes={str(p):sha(p) for p in paths},auctions_sha256=sha(RUN/'auctions.json'),excluded_source_hashes={str(p):sha(p) for p in sources},evaluation_only=True,promoted=False,
        scope='Fixed refreshed policy+belief vs frozen5RZ; common promotedGen5 bidding, evaluated separately. Equal32 samples and same representative/ties-only runtime. New independent test families, fixed100 target.')
    atomic_json(RUN/'manifest.json',m);return m
def init():
    global PLAYERS,M
    from bridge_harness.mixed_arena import ArenaPlayer
    M=json.loads((RUN/'manifest.json').read_text());verify(M)
    PLAYERS={k:ArenaPlayer(v,REPO) for k,v in M['specs'].items()}
def one(row):
    i=row['index'];target=RUN/'episodes'/f'{i:04d}.json.gz'
    if target.exists():return readgz(target)
    board=Board.from_dict(row['board']);scores={};start=time.time()
    for room in ([0,1] if i%2==0 else [1,0]):
        p=RUN/'tables'/f'{i:04d}-{room}.json.gz';assign=['gen6' if s%2==room else '5RZ' for s in range(4)]
        if p.exists():record=readgz(p);assert record['assignments']==assign and record['board']==row['board']
        else:
            def progress(a):
                if not a.get('forced'):assert a['estimates'][a['card']]['gap_to_best']<=1.0001e-9
                atomic_json(RUN/f'worker-{os.getpid()}.json',dict(index=i,room=room,ply=a['ply'],updated=time.time()))
            table=play_table(board,assign,PLAYERS,seed=M['seed']+i,on_event=progress)
            if table['status']!='ok':raise RuntimeError(table.get('traceback',str(table)))
            record=dict(board=row['board'],assignments=assign,tables=[table]);savegz(p,record)
        replay(record);scores[room]=record['tables'][0]['ns_score']
    result=dict(index=i,family=row['family'],imps=imps(scores[0]-scores[1]),seconds=time.time()-start)
    savegz(target,result);return result
def summarize():
    rows=[readgz(p) for p in sorted((RUN/'episodes').glob('*.json.gz'))];x=np.array([r['imps'] for r in rows],float);n=len(x)
    mean=float(x.mean()) if n else None;se=float(x.std(ddof=1)/np.sqrt(n)) if n>1 else None
    from scipy.stats import t
    d=dict(boards=n,target=100,complete=n==100,total_imps=float(x.sum()),imps_per_board=mean,se=se,ci95=[mean-t.ppf(.975,n-1)*se,mean+t.ppf(.975,n-1)*se] if n>1 else None,positive_favors='gen6',promoted=False)
    atomic_json(RUN/'result.json',d);return d
def main():
    RUN.mkdir(exist_ok=True);lock=(RUN/'writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    prepare();rows=json.loads((RUN/'auctions.json').read_text());print('Prepared100 independent paired families',flush=True)
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn'),initializer=init) as pool:
        futures=[pool.submit(one,r) for r in rows]
        for f in as_completed(futures):f.result();print(json.dumps(summarize()),flush=True)
    print(json.dumps(summarize()),flush=True)
if __name__=='__main__':main()
