"""Fixed Gen6 belief confirmation; never trains or selects on reserved labels."""
import copy, fcntl, json, os, sys, gzip
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
ROOT=Path(__file__).resolve().parents[1]
REPO=Path('/workspace/scratch/e9691f0e7615/belief-lab')
sys.path.insert(0,str(REPO))
import numpy as np
from bridge_harness.belief_capacity import INPUTS,encode_play,sha
from bridge_harness.belief_lab import Weights
from bridge_harness.selfplay import atomic_json
from scripts.screen_attention_belief import selected_observations
from scripts.score_belief_joint import score

def paired(values):
    x=np.asarray(values,dtype=float)
    mean=float(x.mean());se=float(x.std(ddof=1)/np.sqrt(len(x)))
    return dict(families=len(x),mean=mean,se=se,ci95=[mean-1.96*se,mean+1.96*se],negative_favors_candidate=True)

def main():
    run=ROOT/'belief-full1513';out=run/'confirmation';out.mkdir(exist_ok=True)
    lock=(out/'writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fit=json.loads((run/'fit/result.json').read_text())
    assert fit['epochs']==3 and len(fit['history'])==3
    model=run/'fit/best.npz'
    parent=Path('/workspace/scratch/919dc41e3067/bridge-gen5rz-ben/models/cardplay/gen5-belief-2026-11-10/belief.npz')
    assert sha(model)==fit['selected_sha256']=='f6e3443b0e7fddcc51e6c4585cb5d5a8ece13077d33b772e8256a4e10fcec7a4'
    assert sha(parent)=='99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a'
    families=json.loads((ROOT/'policy-full1513/confirmation-families.json').read_text())
    fresh={e['family'] for e in families if not e['previously_inspected']}
    assert len(fresh)==150
    sources=json.loads((run/'incremental-sources.json').read_text())
    entries={e['family']:e for e in sources['families'] if e['split']=='test' and e['family'] in fresh}
    assert set(entries)==fresh
    manifest=json.loads((run/'manifest.json').read_text())
    used={e['family'] for e in manifest['families'] if e['split']!='test'}
    assert not used&fresh
    selection=dict(candidate_sha256=sha(model),parent_sha256=sha(parent),fit_sha256=sha(run/'fit/result.json'),
        source_sha256=sha(run/'incremental-sources.json'),families=sorted(fresh),excluded_previously_inspected=27,
        primary_metric='Masked marginal owner NLL, equal family weight, unweighted uncertain cards',
        secondary_metric='Exact two-hidden-seat capacity-conditioned NLL',
        scope='Fresh for belief prediction confirmation; bidding outcomes for these families were previously evaluated. Not an untouched whole-game strength test.')
    frozen=out/'selection.json'
    if frozen.exists():assert json.loads(frozen.read_text())==selection
    else:atomic_json(frozen,selection)
    if (out/'result.json').exists():return
    # Only after freezing the selected candidate do we replay reserved labels.
    if not (out/'dataset.json').exists():
        raw=ROOT/'raw-policy-1513'
        receipts={e['family']:e for e in json.loads((raw/'receipts.json').read_text())}
        atomic_json(out/'raw-source-binding.json',dict(receipts_sha256=sha(raw/'receipts.json'),sources=[receipts[g] for g in sorted(fresh)]))
        rows=[]
        for family,e in sorted(entries.items()):
            view=copy.deepcopy(e);view['split']='validation'
            receipt=receipts[family];source=raw/'episodes'/f"{receipt['index']:06d}.json.gz"
            assert sha(source)==receipt['episode_sha256']
            episode=json.loads(gzip.decompress(source.read_bytes()))
            assert episode['family']==family
            for room in episode['unique_tables'].values():
                room.setdefault('status','ok')
            normalized=out/'episodes'/source.name;normalized.parent.mkdir(exist_ok=True)
            normalized.write_bytes(gzip.compress(json.dumps(episode,sort_keys=True).encode(),mtime=0))
            view['sources']=[dict(path=str(normalized),sha256=sha(normalized))]
            for key,o,y in selected_observations(view):
                x,support=encode_play(o);mask=support.sum(-1)>1
                if not mask.any():continue
                assert np.all(support[np.arange(52),y] | ~mask)
                rows.append(dict(**x,owner_target=y.astype(np.int8),owner_loss_mask=mask,support=support,
                    kind=np.int8(2),split_group=np.array(family),card_weight=np.ones(52,np.float32)))
        assert rows, 'No confirmation observations'
        d={k:np.stack([r[k] for r in rows]) for k in rows[0]}
        path=out/'reserved.npz';np.savez_compressed(path,**d)
        atomic_json(out/'dataset.json',dict(shards=[dict(file=str(path),sha256=sha(path),source='play',cohort='recent',split='validation',rows=len(rows))],
            evaluation_only=True,original_split='test',families=sorted(fresh),selection_sha256=sha(frozen)))
    ds=json.loads((out/'dataset.json').read_text());p=Path(ds['shards'][0]['file']);assert sha(p)==ds['shards'][0]['sha256']
    with np.load(p,allow_pickle=False) as z:d={k:z[k] for k in z.files}
    per_model={};conditional={}
    for name,path in [('candidate',model),('gen5',parent)]:
        m=Weights(path);losses=[]
        for lo in range(0,len(d['kind']),256):
            ix=slice(lo,lo+256);logits=m.predict({k:d[k][ix] for k in INPUTS}).astype(np.float64)
            logits=np.where(d['support'][ix],logits,-1e30);logits-=logits.max(-1,keepdims=True)
            logp=logits-np.log(np.exp(logits).sum(-1,keepdims=True))
            losses.append(-np.take_along_axis(logp,d['owner_target'][ix][...,None],axis=-1)[...,0])
        nll=np.concatenate(losses);groups={}
        for g in np.unique(d['split_group']):
            pick=d['split_group']==g;mask=d['owner_loss_mask'][pick]
            groups[str(g)]=float((nll[pick]*mask).sum()/mask.sum())
        per_model[name]=groups
        conditional[name]=score(path,out,out/(name+'-conditional.json'))
    assert per_model['candidate'].keys()==per_model['gen5'].keys()
    primary=paired([v-per_model['gen5'][g] for g,v in per_model['candidate'].items()])
    a,b=conditional['candidate']['groups'],conditional['gen5']['groups']
    secondary=paired([v[0]/v[1]-b[g][0]/b[g][1] for g,v in a.items() if v[1] and b[g][1]])
    result=dict(selection=selection,positions=len(d['kind']),card_targets=int(d['owner_loss_mask'].sum()),
        marginal_nll={k:float(np.mean(list(v.values()))) for k,v in per_model.items()},paired_marginal_nll=primary,
        paired_conditional_nll=secondary,test_evaluated=True,promoted=False,metric_note='Prediction likelihood, not IMP/board; no tuning after confirmation.')
    atomic_json(out/'marginal-by-family.json',per_model);atomic_json(out/'result.json',result)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
