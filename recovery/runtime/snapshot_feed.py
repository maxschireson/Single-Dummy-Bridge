"""Freeze a receipt-verified full recovery snapshot and arena export."""
from pathlib import Path
import shutil,json,hashlib
from ops.export_gen5 import export
from ops.gen5_runtime import state
ROOT=Path(__file__).resolve().parent
run=ROOT/'runs/phase1-extra-20261112';out=ROOT/'publication';rec=out/'recovery'
rec.mkdir(parents=True,exist_ok=True)
for name in ('manifest.json','corpus.jsonl','state.json','heartbeat.json','plan.json','capture-equivalence.json','preflight.json','supervisor.json','source-indices.json','STOP','WATCHDOG_STOP'):
    if (run/name).exists():shutil.copy2(run/name,rec/name)
for folder in ('artifacts','assets','anchors'):
    if (run/folder).exists():shutil.copytree(run/folder,rec/folder,dirs_exist_ok=True)
manifest=json.loads((rec/'manifest.json').read_text());rows=[]
for p in sorted((run/'receipts').glob('*.json')):
    raw=p.read_bytes();r=json.loads(raw);ep=run/'episodes'/f"{r['index']:06d}.json.gz";data=ep.read_bytes()
    assert r['manifest_identity']==manifest['identity'] and hashlib.sha256(data).hexdigest()==r['episode_sha256']
    for folder,name,b in [('receipts',p.name,raw),('episodes',ep.name,data)]:
        (rec/folder).mkdir(exist_ok=True);(rec/folder/name).write_bytes(b)
    rows.append(r)
(rec/'state.json').write_text(json.dumps(state(rows,manifest)))
# Export from the frozen snapshot so dashboard and complete records share the same cutoff.
(rec/'failures').mkdir(exist_ok=True)
export(rec,out)
dashboard=json.loads((out/'arena/data.json').read_text())
dashboard['configured_workers']=2;dashboard['collection']['workers']=2
dashboard['feed'].update(interval_seconds=3600,next_update_epoch=dashboard['generated_epoch']+3600)
(out/'arena/data.json').write_text(json.dumps(dashboard))
for folder in ('bridge_harness','ops','scripts','configs','native'):
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            dst=rec/'runtime'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
for name in ('launch_selfplay.py','snapshot_feed.py','publish_feed.js','source-provenance.json','RECOVERY.md','runtime-requirements.txt'):
    if (ROOT/name).exists():shutil.copy2(ROOT/name,rec/'runtime'/name)
inventory=[]
for p in out.rglob('*'):
    if p.is_file():
        b=p.read_bytes();inventory.append(dict(path=str(p.relative_to(out)),size=len(b),sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()))
(ROOT/'inventory.json').write_text(json.dumps(inventory))
print(json.dumps(dict(snapshot_completed=len(rows),files=len(inventory))))
