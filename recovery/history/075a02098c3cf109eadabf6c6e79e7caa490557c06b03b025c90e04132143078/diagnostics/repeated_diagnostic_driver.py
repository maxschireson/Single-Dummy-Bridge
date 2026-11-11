import subprocess,sys,os,time,json,pathlib,psutil
base=pathlib.Path('/workspace/scratch/c7932514d17d/gen6-fast-selfplay');run=base/'runs/gen6-chatgpt-fast-selfplay-20261111';out=run/'diagnostics';out.mkdir(exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',PYTHONFAULTHANDLER='1',BRIDGE_DDS_CACHE='/tmp/bridge-diagnostic-dds.sqlite')
code='''import json,time,resource,sys
from pathlib import Path
from ops.gen5_runtime import initialize_worker,play
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
root=Path(sys.argv[1]);m=json.loads((root/'manifest.json').read_text());verify_generation(root,m);boards=load(root/m['corpus']);initialize_worker(str(root))
for index in [233,234,235]*5:
 t=time.time();r=play(str(root),m,boards[index].to_dict(),index);print(json.dumps(dict(index=index,status='replay_validated',seconds=time.time()-t,maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,tables=len(r['unique_tables']))),flush=True)
'''
log=(out/'repeated-233-235.log').open('w');p=subprocess.Popen([str(base/'.venv/bin/python'),'-c',code,str(run)],cwd=base,env=env,stdout=log,stderr=subprocess.STDOUT);peak=0;t=time.time()
while p.poll() is None:
 try:peak=max(peak,psutil.Process(p.pid).memory_info().rss)
 except psutil.NoSuchProcess:pass
 time.sleep(.5)
 if time.time()-t>360:p.terminate();break
p.wait();log.close();r=dict(exit_code=p.returncode,peak_rss_bytes=peak,seconds=time.time()-t,epoch=time.time(),note='Isolated diagnostic; production failure retained; no records committed; separate cache')
(out/'repeated-233-235.json').write_text(json.dumps(r));print(json.dumps(r));print((out/'repeated-233-235.log').read_text()[-2500:])
