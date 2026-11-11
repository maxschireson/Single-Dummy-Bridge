from pathlib import Path
import shutil,json,hashlib
from ops.export_gen5 import export
ROOT=Path(__file__).resolve().parent
run=ROOT/'runs/gen6-chatgpt-ben-followups-20261111'
out=ROOT/'publication'
export(run,out)
for name in ('manifest.json','corpus.jsonl','state.json','heartbeat.json'):
    dest=out/'recovery'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(run/name,dest)
for folder in ('artifacts','assets','episodes','receipts','resolved-failures','history'):
    for p in (run/folder).rglob('*'):
        if p.is_file() and not p.name.endswith('.tmp'):
            d=out/'recovery'/p.relative_to(run);d.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,d)
for folder in ('bridge_harness','ops','scripts','configs','native'):
    for p in (ROOT/folder).glob('*'):
        if p.is_file() and p.suffix in ('.py','.so','.json','.cpp'):
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
