from pathlib import Path
import sys, shutil
ROOT=Path('/workspace/scratch/f846a051cf69')
sys.path.insert(0,str(ROOT/'gen7-cloud-source'))
from ops.export_gen5 import export
from ops.publish_gen5 import snapshot_runtime
run=ROOT/'gen7-phase1-cloud-v2-run'
out=ROOT/'gen7-publication'
export(run,out)
backup=out/'recovery'
backup.mkdir(exist_ok=True)
for name in ('manifest.json','state.json','heartbeat.json','corpus.jsonl','source-indices.json','preflight.json','launch.json','runtime-requirements.txt','STOP','WATCHDOG_STOP'):
    if (run/name).exists(): shutil.copy2(run/name,backup/name)
for name in ('episodes','receipts','artifacts','assets','failures','diagnostics','failure-history'):
    if (run/name).exists(): shutil.copytree(run/name,backup/name,dirs_exist_ok=True)
snapshot_runtime(run,backup)
for name in ('export_gen7_cloud.py','publish_gen7_cloud.js','run_gen7_cloud.py'):
    shutil.copy2(ROOT/name,backup/name)
