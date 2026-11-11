from pathlib import Path
import shutil,json,hashlib
from ops.export_gen5 import export
ROOT=Path(__file__).resolve().parent
run=ROOT/'runs/gen6-chatgpt-ben64-capture-20261111'
out=ROOT/'publication'
export(run,out)
for name in ('manifest.json','corpus.jsonl','state.json','heartbeat.json','source-indices.json','significance-trigger.json','plan.json','original-source-indices.json','ben-preflight.json','capture-equivalence.json','gen7-capture-monitor.json','gen7-capture-report.json','recovery-attempt.json'):
    if not (run/name).exists(): continue
    dest=out/'recovery'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(run/name,dest)
for folder in ('artifacts','assets','resolved-failures','history'):
    for p in (run/folder).rglob('*'):
        if p.is_file() and not p.name.endswith('.tmp'):
            d=out/'recovery'/p.relative_to(run);d.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,d)
# Receipts are the commit marker. Freeze the set once, then copy each verified pair.
# This keeps a live completion between folder copies from creating an orphan.
from ops.gen5_runtime import state as recovery_state
manifest=json.loads((out/'recovery/manifest.json').read_text())
records=[];names=set()
for receipt_path in sorted((run/'receipts').glob('*.json')):
    receipt_bytes=receipt_path.read_bytes();receipt=json.loads(receipt_bytes)
    stem=f"{receipt['index']:06d}";episode_bytes=(run/'episodes'/f'{stem}.json.gz').read_bytes()
    if receipt['manifest_identity']!=manifest['identity'] or hashlib.sha256(episode_bytes).hexdigest()!=receipt['episode_sha256']:
        raise ValueError('Snapshot receipt/episode identity or hash mismatch: '+stem)
    for folder,name,data in (('episodes',stem+'.json.gz',episode_bytes),('receipts',stem+'.json',receipt_bytes)):
        dest=out/'recovery'/folder/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    records.append(receipt);names.add(stem)
for folder,pattern in (('episodes','*.json.gz'),('receipts','*.json')):
    for old in (out/'recovery'/folder).glob(pattern):
        if old.name.split('.')[0] not in names:old.unlink()  # snapshot only; live records are untouched
(out/'recovery/state.json').write_text(json.dumps(recovery_state(records,manifest)))
for folder in ('bridge_harness','ops','scripts','configs','native'):
    for p in (ROOT/folder).glob('*'):
        if p.is_file() and p.suffix in ('.py','.so','.json','.cpp','.conf'):
            d=out/'recovery/runtime'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,d)
for name in ('launch_local.py','snapshot_feed.py','publish_authenticated.js','publish_dashboard.js','source-manifest.json'):
    shutil.copy2(ROOT/name,out/'recovery/runtime'/name)
shutil.copy2(ROOT/'reports/gen6-chatgpt-preflight.json',out/'recovery/preflight.json')
rows=[]
for p in out.rglob('*'):
    if p.is_file():
        b=p.read_bytes();rows.append(dict(path=str(p.relative_to(out)),size=len(b),sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()))
(ROOT/'inventory.json').write_text(json.dumps(rows))
