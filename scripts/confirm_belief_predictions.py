"""One-time reserved-family evaluation after the candidate is irrevocably frozen."""
import argparse,copy,json,math,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import FIELDS,encode_play,sha
from bridge_harness.selfplay import atomic_json
from scripts.screen_attention_belief import selected_observations
from scripts.score_belief_joint import score

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();root=a.run.resolve()
    selection=json.loads((root/'selection.json').read_text());test=root/'reserved';test.mkdir(exist_ok=True)
    if sha(selection['chosen']['recipe'])!=selection['chosen']['recipe_sha256']:raise ValueError('Selected recipe changed')
    if not (test/'dataset.json').exists():
        m=json.loads((root/'data/manifest.json').read_text());entries={e['family']:e for e in m['normalized_sources'] if e['split']=='test'}
        old=json.loads((Path(m['base'])/'manifest.json').read_text())
        for e in old['families']:
            if e['split']=='test':entries.setdefault(e['family'],e)
        if set(entries)!=set(m['reserved_families']):raise ValueError('Reserved source coverage changed')
        shards=[];buf=[]
        def flush():
            if not buf:return
            d={k:np.stack([r[k] for r in buf]) for k in buf[0]};path=test/f'shard-{len(shards):03d}.npz'
            with path.with_suffix('.tmp').open('wb') as f:np.savez_compressed(f,**d)
            path.with_suffix('.tmp').replace(path);shards.append(dict(file=str(path),sha256=sha(path),source='play',cohort='recent',split='validation',rows=len(buf)));buf.clear()
        for family,e in sorted(entries.items()):
            # The legacy reader permits only train/development. This explicit local
            # adapter is called AFTER selection, and its output is evaluation-only.
            view=copy.deepcopy(e);view['split']='validation'
            for key,o,y in selected_observations(view):
                x,support=encode_play(o);mask=support.sum(-1)>1
                if not mask.any():continue
                buf.append(dict(**x,owner_target=y.astype(np.int8),owner_loss_mask=mask,support=support,kind=np.int8(2),split_group=np.array(family),card_weight=np.ones(52,np.float32)))
            if len(buf)>=4096:flush()
        flush();atomic_json(test/'dataset.json',dict(shards=shards,evaluation_only=True,original_split='test',selection_sha256=sha(root/'selection.json'),families=sorted(entries)))
    results={}
    for name,path in [('candidate',selection['chosen']['recipe']),('data_control',selection['data_control']),('current_v5',selection['baseline'])]:
        results[name]=score(Path(path),test,test/(name+'.json'))
    contrasts={}
    for name in ('data_control','current_v5'):
        candidate=results['candidate']['groups'];reference=results[name]['groups'];d=[]
        for f,v in candidate.items():
            w=reference[f]
            if v[1] and w[1]:d.append(v[0]/v[1]-w[0]/w[1])
        mean=float(np.mean(d));se=float(np.std(d,ddof=1)/math.sqrt(len(d)))
        contrasts[name]=dict(families=len(d),conditional_nll_delta=mean,se=se,ci95=[mean-1.96*se,mean+1.96*se],negative_favors_candidate=True)
    atomic_json(test/'summary.json',dict(selection_sha256=sha(root/'selection.json'),contrasts=contrasts,
        models={k:{x:y for x,y in v.items() if x!='groups'} for k,v in results.items()},
        interpretation='Untouched family confirmation after development selection; primary comparator data-only dense, secondary current v5. Conditional likelihood is not IMP/board. No tuning on these results.',promoted=False))

if __name__=='__main__':main()
