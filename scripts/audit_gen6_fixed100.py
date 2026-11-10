import importlib.util,json,math,hashlib
from pathlib import Path
p=Path('/workspace/scratch/d59c0a9fe14a/gen6-full-data/scripts/match_gen6_5rz.py')
s=importlib.util.spec_from_file_location('fixed_match',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
run=m.RUN
reported=json.loads((run/'result.json').read_text())
assert reported['complete'] and reported['boards']==reported['target']==100,'Fixed match is not complete'
manifest=json.loads((run/'manifest.json').read_text());m.verify(manifest)
auctions=json.loads((run/'auctions.json').read_text())
assert len(auctions)==100 and len({r['family'] for r in auctions})==100
assert [r['family'] for r in auctions]==json.loads((run/'reserved-families.json').read_text())
assert len(list((run/'tables').glob('*.json.gz')))==200
assert len(list((run/'episodes').glob('*.json.gz')))==100
values=[];hashes={}
for i,row in enumerate(auctions):
    assert row['index']==i
    b=m.Board.from_dict(row['board'])
    assert m.deal_key(b.hands,True)==row['family']
    scores=[]
    for room in (0,1):
        q=run/'tables'/f'{i:04d}-{room}.json.gz';rec=m.readgz(q)
        assert rec['board']==row['board']
        assert rec['assignments']==['gen6' if seat%2==room else '5RZ' for seat in range(4)]
        m.replay(rec);scores.append(rec['tables'][0]['ns_score'])
        hashes[str(q.relative_to(run))]=m.sha(q)
    value=m.imps(scores[0]-scores[1]);episode=m.readgz(run/'episodes'/f'{i:04d}.json.gz')
    assert episode['index']==i and episode['family']==row['family'] and episode['imps']==value
    values.append(value)
import numpy as np
from scipy.stats import t
x=np.asarray(values,dtype=float);mean=float(x.mean());se=float(x.std(ddof=1)/np.sqrt(100));ci=[mean-float(t.ppf(.975,99))*se,mean+float(t.ppf(.975,99))*se]
assert reported['total_imps']==sum(values)
for a,b in zip([reported['imps_per_board'],reported['se'],*reported['ci95']],[mean,se,*ci]):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
audit={'unique_families':100,'legally_replayed_rooms':200,'all_models_runtime_auctions_hashes_verified':True,'scores_recomputed':True,'paired_family_statistics_verified':True,'table_sha256':hashes,'result':reported,'scope':manifest['scope'],'recovery_note':'Original workspace outputs unavailable. Replayed the identical predeclared100-family test using restored exact model/runtime bytes and original auction SHA. No adaptive extension, model tuning or promotion.'}
m.atomic_json(run/'final-audit.json',audit)
print(json.dumps({k:v for k,v in audit.items() if k!='table_sha256'}))
