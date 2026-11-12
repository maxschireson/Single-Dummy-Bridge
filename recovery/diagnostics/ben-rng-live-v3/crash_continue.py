"""V3.1 transaction-only crash continuation on the newly played V3 records."""
import os,sys,json,tempfile,subprocess
from pathlib import Path
from adapter_v31 import OUT,commit,accepted,materialize,export
fixtures={r[0]['index']:r for r in accepted(OUT/'journal')[0]}
def add(j,index):
 r=fixtures[index];return commit(j,index,post_rng=r[2] if index==1082 else None,raw=r[1])
if len(sys.argv)>1:add(Path(sys.argv[1]),int(sys.argv[2]));sys.exit(0)
results=[]
for index in (1082,1931):
 for stage in ('mkdir','episode','receipt.json','rng.json','manifest','generation_fsync','parent_fsync','next_fsync','pointer_replace','commit_fsync'):
  with tempfile.TemporaryDirectory(prefix='rng-live-continue-') as tmp:
   t=Path(tmp);j=t/'journal';j.mkdir();add(j,1932)
   if index==1931:add(j,1082)
   old,oldrng=accepted(j)
   child=subprocess.run([sys.executable,__file__,str(j),str(index)],env=dict(os.environ,RNG_DIAGNOSTIC_CUT=stage));assert child.returncode==-9
   rows,rng=accepted(j);advanced=stage in ('pointer_replace','commit_fsync')
   assert len(rows)==len(old)+int(advanced)
   assert rng==(fixtures[1082][2] if advanced and index==1082 else oldrng)
   if not advanced:add(j,index)
   else:
    before=(j/'CURRENT').read_bytes()
    try:add(j,index)
    except AssertionError as exc:assert str(exc)=='duplicate'
    else:raise AssertionError('duplicate accepted')
    assert (j/'CURRENT').read_bytes()==before
   add(j,1930)
   rows,rng=accepted(j);assert len(rows)==len(old)+2 and rng==fixtures[1082][2]
   materialize(j,t/'view');export(t/'view',t/'export')
   data=json.loads((t/'export/arena/data.json').read_text());assert data['completed']==len(rows)
   results.append({'lane':'BEN' if index==1082 else 'normal','cut':stage,'exitcode':-9,'complete_count':len(rows),'continued':True,'export_count':data['completed'],'rng_exact':True})
report={'status':'passed','schema':'diagnostic-rng-live-v3.1','cases':results,'production_commits':0,'scope':'20 actual SIGKILL interruptions and successful continuation using records newly played by V3. V3.1 changes only generation naming; live futures were exercised with V3. No power-loss simulation or production adoption.'}
(OUT/'crash-continue-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
