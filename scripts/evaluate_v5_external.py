"""Evaluate frozen v5 checkpoints on unused clean exported branch comparisons."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.policy_v5 import V5Weights
from scripts.train_policy_choices import choose,family_summary
from scripts.freeze_clean_policy import CLEAN
run=ROOT/'runs/v5-clean/experiment'
excluded={r['family'] for r in json.loads((run/'data/families.json').read_text())}
source=ROOT.parent/'clean-legacy-import/gen2-gen3'
rows=[];seen=set();files=[]
for folder in sorted(source.glob('snapshot-*')):
 ds=json.loads((folder/'policy/dataset.json').read_text())
 assert ds['validated'] and ds['schema']=='audited-neural-imp-v1'
 assert ds['parent_sha256'].startswith('8c62c88b')
 assert all(v['artifact_sha256'].get('policy') in CLEAN for v in ds['versions'].values())
 for entry in ds['shards']:
  p=folder/'policy'/entry['file'];checksum=hashlib.sha256(p.read_bytes()).hexdigest();assert checksum==entry['sha256'];files.append(dict(path=str(p),sha256=checksum))
  with np.load(p,allow_pickle=False) as z:
   loaded={k:z[k] for k in z.files}
   for i,g in enumerate(loaded['group']):
    if g in excluded:continue
    row={k:v[i] for k,v in loaded.items()}
    key=hashlib.sha256(b''.join(np.asarray(row[k]).tobytes() for k in sorted(row) if k!='weight')).hexdigest()
    if key not in seen:rows.append(row);seen.add(key)
data={k:np.stack([r[k] for r in rows]) for k in rows[0]}
meta=dict(rows=len(rows),families=len(set(data['group'])),decisive_rows=int((data['y']!=0).sum()),files=files,
 scope='External clean post-v3 comparisons unused by all current v5 fits or checkpoint selection. Includes recursive branches; depth is absent from export. Original train/validation tags concern historical fits, not these v5 candidates. No model selection on this evaluation.')
out=run/'external-evaluation';out.mkdir(exist_ok=True)
(out/'frozen-inputs.json').write_text(json.dumps(meta,indent=2))
models={'v3':ROOT/'models/cardplay/gen3-2026-11-09/restored/auction-policy.npz'}
for mode in ['baseline','wide','attention']:
 if (run/mode/'result.json').exists():models[mode]=run/mode/'best.npz'
contrasts={}
for name,path in models.items():
 model=V5Weights(path);values=[]
 for start in range(0,len(rows),128):
  b={k:v[start:start+128] for k,v in data.items()};pred=model.predict(b);ix=np.arange(len(pred));values.extend(pred[ix,b['chosen']]-pred[ix,b['reference']])
 contrasts[name]=np.array(values)
results={name:family_summary((choose(c)-choose(contrasts['v3']))*data['y'],data['group']) for name,c in contrasts.items() if name!='v3'}
(out/'results.json').write_text(json.dumps(dict(metadata=meta,models=results),indent=2))
print(json.dumps(dict(rows=meta['rows'],families=meta['families'],decisive_rows=meta['decisive_rows'],results=results)))
