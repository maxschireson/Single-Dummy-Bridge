import os,sys,json,tempfile,subprocess
from pathlib import Path
from probe import OUT,commit,accepted,materialize,export
POST=(OUT.parent/'ben-rng-broader/baseline-state.json').read_bytes()
if len(sys.argv)>1:
 commit(Path(sys.argv[1]),int(sys.argv[2]),POST if sys.argv[2]=='2561' else None);sys.exit(0)
results=[]
for index in (2561,1601):
 for stage in ('mkdir','episode','receipt.json','rng.json','manifest','generation_fsync','parent_fsync','next_fsync','pointer_replace','commit_fsync'):
  with tempfile.TemporaryDirectory(prefix='rng-adapter-crash-') as tmp:
   t=Path(tmp);j=t/'journal';j.mkdir();commit(j,1600)
   if index==1601:commit(j,2561,POST)
   old,oldrng=accepted(j)
   child=subprocess.run([sys.executable,__file__,str(j),str(index)],env=dict(os.environ,RNG_DIAGNOSTIC_CUT=stage));assert child.returncode==-9
   rows,rng=accepted(j);advanced=stage in ('pointer_replace','commit_fsync');assert len(rows)==len(old)+int(advanced)
   assert rng==(POST if advanced and index==2561 else oldrng)
   materialize(j,t/'view');export(t/'view',t/'export')
   data=json.loads((t/'export/arena/data.json').read_bytes());assert data['completed']==len(rows)
   results.append({'lane':'BEN' if index==2561 else 'normal','cut':stage,'exitcode':child.returncode,'accepted':len(rows),'export_count':data['completed'],'rng_coherent':True})
report={'status':'passed','cases':results,'production_commits':0,'scope':'20 actual SIGKILL interruptions of diagnostic adapter using archived fixtures; recovery and actual exporter agree. No live server/collector loop wiring or power-loss simulation.'}
(OUT/'crash-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
