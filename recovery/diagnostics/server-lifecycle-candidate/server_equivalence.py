import os,sys,json,time,subprocess,urllib.request,urllib.error,multiprocessing as mp
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
NEW=Path('/workspace/scratch/c7932514d17d/gen6-ben-server-recycled');MODE=sys.argv[1] if len(sys.argv)>1 else 'orchestrate';BASE=NEW.parent/'gen6-ben-recycled' if MODE=='baseline' else NEW;sys.path.insert(0,str(BASE));RUN=BASE/('runs/gen6-chatgpt-ben-recycled-20261111' if MODE=='baseline' else 'runs/gen6-chatgpt-ben-server-recycled-20261111');OUT=NEW/'runs/gen6-chatgpt-ben-server-recycled-20261111/diagnostics'
import resource
from bridge_harness.training import digest
from ops.gen5_runtime import initialize_worker,play
from ops.ben_board_executor import BenBoardExecutor
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
from concurrent.futures import ProcessPoolExecutor

def semantics(record):
    # Capture every root and audit action, score, seed, assignment and auction.
    # BEN has no gaps/audits; self-play gap CPU caps can change capture volume,
    # so separately compare the complete root + tie-audit trajectory.
    episodes = {}
    for key, episode in record['unique_tables'].items():
        tables = []
        for table in episode['tables']:
            if table.get('node', '').startswith('gap'):
                continue
            tables.append({k: table.get(k) for k in ('node', 'depth', 'status', 'ns_score', 'declarer_tricks')})
            tables[-1]['actions'] = [{k: action.get(k) for k in
                ('ply', 'seat', 'controller', 'player', 'card', 'behavior_probabilities', 'selected_probability', 'selected_pimc_gap')}
                for action in table['actions']]
        episodes[key] = dict(board=episode['board'], seed=episode.get('seed'),
            assignments=episode.get('assignments'), tables=tables)
    return dict(index=record['index'], family=record['family'], pair=record['pair'],
        versions=record['versions'], regimes=record['regimes'], episodes=episodes)

def probe(root, manifest, board, index):
    start = time.time()
    record = play(root, manifest, board, index)
    semantic = semantics(record)
    return dict(index=index, pid=os.getpid(), seconds=time.time()-start,
        maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        semantic=semantic, fingerprint=digest(semantic),
        audit_counts=[len(e.get('audits', [])) for e in record['unique_tables'].values()])

def collect():
 m=json.loads((RUN/'manifest.json').read_text());verify_generation(RUN,m);boards=load(RUN/m['corpus']);os.environ['BRIDGE_DDS_CACHE']=str(OUT/(MODE+'-server-cache.sqlite'))
 kwargs={}
 if MODE=='candidate':
  from ops.ben_server_lifecycle import BenServer
  kwargs['server_factory']=lambda:BenServer(RUN)
 rows=[]
 with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(RUN),)) as normal,BenBoardExecutor(RUN,initialize_worker,(str(RUN),),**kwargs) as ben:
  fs=[normal.submit(probe,str(RUN),m,boards[i].to_dict(),i) for i in (621,622,623)]
  for _ in range(3):
   row=ben.submit(probe,str(RUN),m,boards[3062].to_dict(),3062).result(600);rows.append(row);print(MODE,row['index'],row['fingerprint'],flush=True)
  rows.extend(f.result(600) for f in fs)
 (OUT/(MODE+'-server-equivalence.json')).write_text(json.dumps(rows))

def main():
 server=None
 try:
  log=(OUT/'baseline-server.log').open('w');old=NEW.parent/'gen6-ben-recycled/runs/gen6-chatgpt-ben-recycled-20261111';server=subprocess.Popen([sys.executable,'src/gameapi.py','--config',str(old/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=NEW.parent/'ben',stdout=log,stderr=subprocess.STDOUT)
  for _ in range(60):
   if server.poll() is not None:raise RuntimeError('baseline server exited')
   try:urllib.request.urlopen('http://127.0.0.1:8087/',timeout=2);break
   except urllib.error.HTTPError:break
   except urllib.error.URLError:time.sleep(1)
  else:raise RuntimeError('baseline readiness timeout')
  subprocess.run([sys.executable,__file__,'baseline'],cwd=NEW,check=True)
 finally:
  if server is not None:server.terminate();server.wait(timeout=30)
 subprocess.run([sys.executable,__file__,'candidate'],cwd=NEW,check=True)
 a=json.loads((OUT/'baseline-server-equivalence.json').read_text());b=json.loads((OUT/'candidate-server-equivalence.json').read_text());assert len(a)==len(b)==6;assert [r['fingerprint'] for r in a]==[r['fingerprint'] for r in b],'Play changed'
 report=dict(status='passed',epoch=time.time(),manifest=json.loads((RUN/'manifest.json').read_text())['identity'],plays_per_mode=6,ben_index=3062,self_indices=[621,622,623],fingerprints=[r['fingerprint'] for r in b],production_commits=0)
 (RUN/'server-recycling-preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':
 if MODE=='orchestrate':main()
 else:collect()
