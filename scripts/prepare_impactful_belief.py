"""Freeze broad replay plus recent public-world card-importance labels."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import Weights,encode_play,sha,load
from bridge_harness.belief_consequence import impactful_cards
from scripts.screen_attention_belief import selected_observations,save_json


def init(parent,cache):
    global PARENT,SOLVER,CACHE
    from bridge_harness.dds import DDS
    PARENT=Weights(parent);SOLVER=DDS();CACHE=Path(cache)


def one(entry,output):
    if entry['split'] not in ('train','validation'):raise ValueError('Reserved split')
    root=Path(output);p=root/'recent'/f"{entry['family']}.npz";meta=p.with_suffix('.json')
    if meta.exists():
        d=json.loads(meta.read_text())
        if not d['rows']:return d
        if p.exists() and sha(p)==d['sha256']:return d
        raise ValueError('Recent shard changed')
    cached={};cp=CACHE/'data'/p.name;cm=cp.with_suffix('.json')
    if cp.exists() and cm.exists():
        md=json.loads(cm.read_text())
        if sha(cp)!=md['sha256']:raise ValueError('Prior label shard changed')
        with np.load(cp,allow_pickle=False) as z:cached=dict(zip(z['key'].tolist(),z['weight'].tolist()))
    rows=[];started=time.time();reuse=0
    for key,o,y in selected_observations(entry):
        x,support=encode_play(o);mask=support.sum(-1)>1
        if not mask.any():continue
        if not np.all(support[np.arange(52),y]|~mask):raise ValueError('Unsupported target')
        # Under these identical frozen worlds zero perfect-information value
        # certifies zero value for any single-card reveal. Reuse that certificate.
        if cached.get(key)==1.:
            value=np.zeros(52,np.float32);reuse+=1
        else:value=impactful_cards(o,PARENT,SOLVER)
        value[~mask]=0
        weight=(1+3*np.minimum(value,1)).astype(np.float32)
        rows.append(dict(**x,support=support,owner_target=y.astype(np.int8),owner_loss_mask=mask,
            card_value=value,card_weight=weight,kind=np.int8(2),split_group=np.array(entry['family']),
            ply=np.int8(len(o.history)),role=np.int8(o.actor%2==o.contract.declarer%2),key=np.array(key)))
    md=dict(family=entry['family'],split=entry['split'],rows=len(rows),seconds=time.time()-started,
            targets=0,upweighted_targets=0,reused_zero_value_rows=reuse)
    if rows:
        a={k:np.stack([r[k] for r in rows]) for k in rows[0]};p.parent.mkdir(parents=True,exist_ok=True)
        with p.with_suffix('.tmp').open('wb') as f:np.savez_compressed(f,**a)
        p.with_suffix('.tmp').replace(p)
        md.update(targets=int(a['owner_loss_mask'].sum()),
            upweighted_targets=int(((a['card_weight']>1)&a['owner_loss_mask']).sum()),
            sha256=sha(p),file=str(p.resolve()),source='play',cohort='recent')
    save_json(meta,md);return md


def pack(entries,out):
    """Combine family recovery shards into normal training batches."""
    result=[];out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for split in ('train','validation'):
        buffer=[];size=0;number=0
        def flush():
            nonlocal buffer,size,number
            arrays={k:np.concatenate([d[k] for d in buffer]) for k in buffer[0]}
            p=out/f'{split}-{number:04d}.npz'
            with p.with_suffix('.tmp').open('wb') as f:np.savez_compressed(f,**arrays)
            p.with_suffix('.tmp').replace(p)
            result.append(dict(file=str(p.resolve()),sha256=sha(p),source='play',cohort='recent',split=split,rows=size))
            number+=1;buffer=[];size=0
        for e in sorted(entries,key=lambda e:e['family']):
            if e['split']!=split:continue
            if sha(e['file'])!=e['sha256']:raise ValueError('Family shard changed')
            with np.load(e['file'],allow_pickle=False) as z:d={k:z[k] for k in z.files}
            buffer.append(d);size+=e['rows']
            if size>=4096:flush()
        if buffer:flush()
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--parent-partition',type=Path,required=True);ap.add_argument('--parent-checkpoint',type=Path,required=True)
    ap.add_argument('--old-screen',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--parent',type=Path,default=Path('models/belief-v4.npz'));ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--max-families',type=int,default=0)
    ap.add_argument('--clean-sources',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (a.out/'prepare.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest_path=a.out/'manifest.json'
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text())
            if sha(a.parent)!=manifest['parent_sha256']:raise ValueError('Parent changed')
        else:
            old=json.loads((a.old_screen/'manifest.json').read_text())
            if old['parent_sha256']!=sha(a.parent):raise ValueError('Cached world proposal changed')
            partition=json.loads(a.parent_partition.read_text())
            trained=set(partition['train_families']);reserved=set(partition['validation_families'])
            bd=json.loads((a.base/'dataset.json').read_text());base=[]
            by_split={'train':set(),'validation':set()};base_counts=Counter()
            for e in bd['shards']:
                if e['split'] not in by_split:continue
                path=a.base/e['file']
                if sha(path)!=e['sha256']:raise ValueError('Historical shard changed')
                d=load(path);groups=set(map(str,np.unique(d['split_group'])));by_split[e['split']].update(groups)
                base_counts[e['split']]+=len(d['kind'])
                base.append({**e,'file':str(path.resolve()),'cohort':'historical'})
            if by_split['train'] & by_split['validation']:raise ValueError('Historical split leakage')
            if by_split['train'] & reserved:raise ValueError('Replay contains v4 validation family')
            br=json.loads((a.base/'bidding-reserved-families.json').read_text())
            reserved.update(br.get('test',[]));reserved.update(by_split['validation'])
            trained.update(by_split['train'])
            families=[];excluded=[]
            clean=json.loads(a.clean_sources.read_text())
            for e in clean['families']:
                if not all(s.get('policy_clean') for s in e['sources']):raise ValueError('Unverified policy source')
                if (e['split']=='train' and e['family'] in reserved) or (e['split']!='train' and e['family'] in trained):
                    excluded.append(dict(family=e['family'],split=e['split'],reason='Preserve inherited train/holdout boundary'));continue
                families.append(e)
            if a.max_families:
                families=[e for e in families if e['split']=='train'][:a.max_families]+[e for e in families if e['split']=='validation'][:max(2,a.max_families//4)]
            manifest=dict(schema='dense-impactful-card-belief-v5-v1',parent_sha256=sha(a.parent),
                parent_checkpoint=str(a.parent_checkpoint.resolve()),parent_partition_sha256=sha(a.parent_partition),
                replay_dataset_sha256=sha(a.base/'dataset.json'),base=base,families=families,
                excluded_overlap=excluded,historical_rows=dict(base_counts),seed=2026110906,
                clean_sources_sha256=sha(a.clean_sources),clean_sources_counts=clean['counts'],excluded_policy_sha256=clean['excluded_policy_sha256'],
                parameters=308726,epochs=3,learning_rate=.0001,batch_size=2048,
                importance='Cross-fitted single-card owner information value under 24 v4 + 8 uniform legal worlds. Both owner groups >=4 worlds; prior shrinkage 4 worlds. Per-card weight 1+3*min(max(0,value_IMP),1).',
                training='50/25/25 play/bidding/BEN; recent family mass 2x; within-family weights normalized over uncertain-card targets.',
                selection='50% play (equal historical ordinary and recent impactful family NLL), 25% historical complete bidding auctions, 25% historical complete BEN auctions; epoch zero eligible.',
                old_screen_manifest_sha256=sha(a.old_screen/'manifest.json'),test_evaluated=False)
            save_json(manifest_path,manifest)
        pending=[e for e in manifest['families'] if e['split']!='test'];started=time.time();entries=[];counts=Counter()
        with ProcessPoolExecutor(max_workers=a.workers,initializer=init,initargs=(str(a.parent),str(a.old_screen))) as pool:
            futures=[pool.submit(one,e,str(a.out)) for e in pending]
            for i,f in enumerate(as_completed(futures),1):
                md=f.result()
                if md['rows']:entries.append(md)
                counts[md['split']+'_rows']+=md['rows'];counts[md['split']+'_targets']+=md['targets']
                counts['upweighted_targets']+=md['upweighted_targets'];counts['reused_zero_value_rows']+=md['reused_zero_value_rows']
                if i%20==0 or i==len(pending):
                    state=dict(stage='card_labeling',completed_families=i,total_families=len(pending),counts=dict(counts),seconds=time.time()-started,updated=time.time())
                    save_json(a.out/'status.json',state);print(json.dumps(state),flush=True)
        packed=pack(entries,a.out/'packed')
        save_json(a.out/'dataset.json',dict(schema=manifest['schema'],shards=manifest['base']+packed,family_shards=sorted(entries,key=lambda e:e['family']),counts=dict(counts),historical_rows=manifest['historical_rows'],manifest_sha256=sha(manifest_path),test_evaluated=False))


if __name__=='__main__':main()
