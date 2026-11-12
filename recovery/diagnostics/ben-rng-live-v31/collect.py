"""Diagnostic-only live futures, accepted journal, snapshot and restored continuation."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
import sys,json,gzip,shutil,subprocess,multiprocessing as mp,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from adapter import OUT,RUN,ROOT,commit,accepted,materialize,sha,export
from live_executor import BenBoardExecutor
from live_server import BenServer
from semantics import semantics
from ops.gen5_runtime import initialize_worker,play
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.training import digest

def phase(number):
 journal=OUT/('journal' if number==1 else 'restored')
 if number==1:journal.mkdir()
 manifest=json.loads((RUN/'manifest.json').read_text());verify_generation(RUN,manifest)
 boards=load(RUN/manifest['corpus'])
 _,rng=accepted(journal)
 if rng is None:rng=(OUT.parent/'ben-rng-broader/initial-state.json').read_bytes()
 pre=sha(rng);working=OUT/f'working-{number}.json';working.write_bytes(rng)
 os.environ.update(CLAIM_STATE=str(working),CLAIM_START=str(OUT/f'start-{number}.json'),BRIDGE_DDS_CACHE=str(OUT/f'cache-{number}.sqlite'))
 factory=lambda:BenServer(OUT,command=[sys.executable,str(OUT/'server.py'),'--config',str(RUN/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=ROOT.parent/'ben')
 events=[];benindex=1082 if number==1 else 2561
 selfindices=(1930,1931,1932) if number==1 else (1933,1934,1935)
 with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(RUN),)) as normal,BenBoardExecutor(OUT,initialize_worker,(str(RUN),),server_factory=factory) as ben:
  futures={normal.submit(play,str(RUN),manifest,boards[i].to_dict(),i):i for i in selfindices}
  bf=ben.submit(play,str(RUN),manifest,boards[benindex].to_dict(),benindex);futures[bf]=benindex
  for future in as_completed(futures,timeout=900):
   index=futures[future];record=future.result();raw=gzip.compress(json.dumps(record,sort_keys=True).encode(),mtime=0)
   _,before=accepted(journal);before=before or rng
   post=working.read_bytes() if future is bf else None
   result=commit(journal,index,post_rng=post,expected_rng=pre if future is bf else sha(before),raw=raw)
   if future is not bf:assert result==sha(before)
   event={'index':index,'kind':'BEN' if future is bf else 'self','fingerprint':digest(semantics(record)),'rng_before':sha(before),'rng_after':result,'epoch':time.time()}
   events.append(event);print(json.dumps(event),flush=True)
 (OUT/f'events-{number}.json').write_text(json.dumps(events,indent=2))
 materialize(journal,OUT/f'view-{number}');export(OUT/f'view-{number}',OUT/f'export-{number}')


def main():
 subprocess.run([sys.executable,__file__,'1'],check=True)
 shutil.copytree(OUT/'journal',OUT/'snapshot');shutil.copytree(OUT/'snapshot',OUT/'restored')
 materialize(OUT/'restored',OUT/'restore-view');export(OUT/'restore-view',OUT/'restore-export')
 keys=('completed','views','own_views','difference_views','allocation','manifest_identity')
 a=json.loads((OUT/'export-1/arena/data.json').read_text());b=json.loads((OUT/'restore-export/arena/data.json').read_text())
 assert all(a[k]==b[k] for k in keys) and a['completed']==4
 assert accepted(OUT/'journal')[1]==accepted(OUT/'restored')[1]
 subprocess.run([sys.executable,__file__,'2'],check=True)
 rows,rng=accepted(OUT/'restored');assert len(rows)==8
 reference={r['index']:r['fingerprint'] for r in json.loads((OUT.parent/'ben-rng-broader/baseline-equivalence.json').read_text())}
 events=json.loads((OUT/'events-1.json').read_text())+json.loads((OUT/'events-2.json').read_text())
 comparisons={e['index']:e['fingerprint']==reference[e['index']] for e in events if e['index'] in reference}
 assert len(comparisons)==5 and all(comparisons.values()),comparisons
 assert rng==(OUT.parent/'ben-rng-broader/baseline-state.json').read_bytes()
 result={'status':'passed','schema':'diagnostic-rng-live-v3.1','newly_played_records':8,'ben_indices':[1082,2561],'self_indices':[1930,1931,1932,1933,1934,1935],'reference_fingerprints_exact':comparisons,'final_rng_exact':True,'snapshot_restore_export_exact':True,'normal_commits_preserve_rng':True,'actual_futures_server_exit_gate':True,'production_commits':0,'scope':'Diagnostic isolated claim protocol on both reference and new run. Not unchanged-production equivalence, not recovered dead-server RNG, no power-loss validation or production adoption.'}
 (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':
 if len(sys.argv)>1:phase(int(sys.argv[1]))
 else:main()
