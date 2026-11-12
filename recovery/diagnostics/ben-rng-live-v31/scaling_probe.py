"""Bounded serialization test of V3.1's nested previous-marker representation."""
import json,sys
from pathlib import Path
p=Path(__file__).resolve().parent
sample=json.loads((p.parent/'ben-rng-live-v3/journal/CURRENT').read_text())
sample['previous']=None
marker=None;last=0;failure=None
for n in range(1,8129):
 marker=dict(sample,generation=f'synthetic-{n}',previous=marker)
 if n not in (128,512,1024,2015,8128):continue
 try:
  encoded=json.dumps(marker,sort_keys=True);decoded=json.loads(encoded);assert decoded==marker
 except RecursionError:
  failure=n;break
 last=len(encoded)
r={'status':'blocked' if failure else 'passed','first_failed_depth':failure,'last_serialized_bytes':last,'python_recursion_limit':sys.getrecursionlimit(),'target':8128,'scope':'Synthetic marker serialization only, no model plays or production writes. Checks JSON roundtrip and structural equality at selected depths using actual V3.1 marker shape; nested markers grow per-commit storage.','next':'Replace embedded ancestor chain with SHA-bound parent references and iterative validation; test complete8128+recovery before adoption.'}
(p/'scaling-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
