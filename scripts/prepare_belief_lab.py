"""Freeze expanded clean replay while preserving every inherited family boundary."""
import argparse, copy, gzip, json, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import FIELDS, encode_play, sha, load
from bridge_harness.selfplay import atomic_json
from scripts.screen_attention_belief import selected_observations, split
from scripts.freeze_clean_belief_sources import BAD_POLICY

def main():
    p=argparse.ArgumentParser(); p.add_argument('--base',type=Path,required=True)
    p.add_argument('--normalized',type=Path,required=True); p.add_argument('--legacy',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    if (a.out/'dataset.json').exists(): return
    base=json.loads((a.base/'dataset.json').read_text()); old=json.loads((a.base/'manifest.json').read_text())
    known={'train':set(),'validation':set(),'test':set()}
    for e in base['shards']:
        if sha(e['file'])!=e['sha256']:raise ValueError('Base shard changed')
        with np.load(e['file']) as z: known[e['split']].update(map(str,z['split_group']))
    for e in old['families']:known[e['split']].add(e['family'])
    if any(known[x]&known[y] for x,y in [('train','validation'),('train','test'),('validation','test')]):raise ValueError('Inherited overlap')
    # Canonical family IDs match the inherited split, including rotation aliases.
    normalized=[]; excluded=Counter(); seen=set(); holdout=[]; extras=[]; buf={}; serial=Counter()
    def add_arrays(d,sp,origin):
        d={k:d[k] for k in FIELDS}; d['card_weight']=np.ones(d['owner_target'].shape,np.float32)
        key=(sp,origin); buf.setdefault(key,[]).append(d)
        if sum(len(x['kind']) for x in buf[key])>=4096:flush(key)
    def flush(key):
        if not buf.get(key):return
        sp,origin=key; d={k:np.concatenate([v[k] for v in buf[key]]) for k in buf[key][0]}
        target=a.out/'packed'/f'{origin}-{sp}-{serial[key]:04d}.npz';target.parent.mkdir(exist_ok=True)
        with target.with_suffix('.tmp').open('wb') as f:np.savez_compressed(f,**d)
        target.with_suffix('.tmp').replace(target); serial[key]+=1;buf[key]=[]
        extras.append(dict(file=str(target.resolve()),sha256=sha(target),source='play',cohort='recent',split=sp,rows=len(d['kind']),origin=origin))
    old_recent={e['family'] for e in base['family_shards']}
    frozen_paths=sorted((a.normalized/'episodes').glob('*.json.gz'))
    for i,path in enumerate(frozen_paths):
        raw=path.read_bytes(); ep=json.loads(gzip.decompress(raw)); family=ep['family']
        policies={p for item in ep.get('provenance',[]) for p in item.get('policies',[])}
        if not ep.get('policy_clean') or not policies or BAD_POLICY in policies:raise ValueError('Unverified normalized policy')
        # None denotes the audited original uniform/no-policy bot in this export.
        source=dict(path=str(path.resolve()),sha256=sha(path),policy_clean=True,active_policy_sha256=sorted(policies,key=str))
        sp=split(family)
        if ep['split']!=('validation' if sp in ('validation','test') else 'train'):raise ValueError('Inherited split mismatch')
        if family in known['train']:sp='train'
        elif family in known['validation']:sp='validation'
        elif family in known['test']:sp='test'
        entry=dict(family=family,split=sp,sources=[source]); normalized.append(entry);seen.add(family)
        if sp=='test':holdout.append(entry);continue
        if family in old_recent:excluded['already_recent_family']+=1;continue
        rows=[]
        for key,o,y in selected_observations(entry):
            x,support=encode_play(o);mask=support.sum(-1)>1
            if mask.any():rows.append(dict(**x,owner_target=y.astype(np.int8),owner_loss_mask=mask,support=support,kind=np.int8(2),split_group=np.array(family)))
        if rows:add_arrays({k:np.stack([r[k] for r in rows]) for k in FIELDS},sp,'archived')
        if i%200==0:
            atomic_json(a.out/'prepare-status.json',dict(stage='archived_raw',completed=i,total=len(frozen_paths),updated=time.time()))
            print('archived',i,'/',len(frozen_paths),flush=True)
    legacy_meta=json.loads((a.legacy/'manifest.json').read_text())
    if BAD_POLICY in legacy_meta['active_policy_sha256']:raise ValueError('Bad legacy policy')
    legacy_sources=[]; excluded_legacy=seen|known['train']|known['validation']|known['test']
    for dp in sorted((a.legacy/'gen2-gen3').glob('snapshot-*/belief/dataset.json')):
        ds=json.loads(dp.read_text())
        for e in ds['shards']:
            path=dp.parent/e['file']
            if sha(path)!=e['sha256']:raise ValueError('Legacy shard changed')
            d=load(path); groups=d['split_group'].astype(str); sp=e['split']
            # Already-present family trajectories are not counted a second time.
            keep=np.array([g not in excluded_legacy for g in groups])
            if sp=='validation':keep &= np.array([split(g)=='validation' for g in groups])
            elif sp=='train':keep &= np.array([split(g)=='train' for g in groups])
            else:continue
            if keep.any():add_arrays({k:v[keep] for k,v in d.items()},sp,'legacy')
            legacy_sources.append(dict(path=str(path),sha256=e['sha256'],retained=int(keep.sum())))
    for key in list(buf):flush(key)
    shards=base['shards']+extras
    boundaries={s:set() for s in ('train','validation')}; counts=Counter()
    for e in shards:
        with np.load(e['file']) as z:boundaries[e['split']].update(map(str,z['split_group']));counts[e['split']+'_positions']+=len(z['kind'])
    if boundaries['train']&boundaries['validation'] or boundaries['train']&known['test']:raise ValueError('Final leakage')
    manifest=dict(schema='belief-lab-expanded-v1',base=str(a.base.resolve()),base_sha256=sha(a.base/'dataset.json'),
        normalized_sources=normalized,legacy_sources=legacy_sources,reserved_families=sorted(known['test']|{e['family'] for e in holdout}),
        excluded=dict(excluded),created=time.time(),test_prepared=False,policy_excluded=BAD_POLICY,
        counts=dict(counts,train_families=len(boundaries['train']),validation_families=len(boundaries['validation'])))
    atomic_json(a.out/'manifest.json',manifest)
    atomic_json(a.out/'dataset.json',dict(schema=manifest['schema'],shards=shards,manifest_sha256=sha(a.out/'manifest.json'),counts=manifest['counts']))
    # Both original-data and expanded-data controls use exactly this validation pool.
    fixed=a.out/'fixed';fixed.mkdir(exist_ok=True)
    atomic_json(fixed/'manifest.json',dict(base_sha256=sha(a.base/'dataset.json'),expanded_sha256=sha(a.out/'dataset.json')))
    atomic_json(fixed/'dataset.json',dict(shards=[e for e in base['shards'] if e['split']=='train']+[e for e in shards if e['split']=='validation'],manifest_sha256=sha(fixed/'manifest.json')))
    print(json.dumps(manifest['counts']),flush=True)

if __name__=='__main__':main()
