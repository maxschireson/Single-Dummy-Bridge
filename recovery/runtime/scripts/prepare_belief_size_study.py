#!/usr/bin/env python3
"""Freeze current auction and replay-validated public-play data for two model sizes."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.belief_capacity import SCHEMA,FIELDS,sha,add_empty_play,encode_play
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board,Game,card,auction_contract
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest,split_for


def read(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else Path(p).open()) as f:return json.load(f)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bidding-data',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--sources',type=Path,required=True,help='JSON list of {path,role}; role is training or retired-evaluation')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Frozen datasets cannot be overwritten')
    a.out.mkdir(parents=True)
    ds=read(a.bidding_data/'dataset.json')
    if not ds['validated'] or ds['bidding_evaluation_imported']:raise ValueError('Expected audited bidding TRAIN data')
    shutil.copyfile(a.parent,a.out/'parent.npz')
    for name in ('dataset.json','reserved-families.json'):
        shutil.copyfile(a.bidding_data/name,a.out/('bidding-'+name))
    shutil.copyfile(a.sources,a.out/'sources.json')
    entries=[];counts=Counter();sources=[];group_splits={};retired={};trajectories=set();play_groups={s:set() for s in ('train','validation','test')}
    original_splits={};bidding_splits={}
    for split,groups in read(a.bidding_data/'reserved-families.json').items():
        for g in groups:bidding_splits[g]=split
    # Inspect old test GROUP METADATA only; no test features or targets are loaded.
    old_root=Path(ds['legacy']['train']['path']).parent
    old_audit=read(old_root/'audit.json')
    for split in ('train','validation','test'):
        f=old_root/f'{split}.npz'
        if sha(f)!=old_audit['exports'][split]:raise ValueError('Legacy dataset changed')
        with np.load(f,allow_pickle=False) as z:
            for g in np.unique(z['split_group']):original_splits[str(g)]=split

    def save(source,split,arrays):
        if not len(arrays['kind']):return
        for start in range(0,len(arrays['kind']),4096):
            d={k:arrays[k][start:start+4096] for k in FIELDS}
            path=a.out/f'{source}-{split}-{len(entries):05d}.npz'
            np.savez_compressed(path,**d)
            entries.append(dict(file=path.name,sha256=sha(path),source=source,split=split,rows=len(d['kind'])))
            counts[f'{source}_{split}_rows']+=len(d['kind'])
            for g in np.unique(d['split_group']):
                previous=group_splits.setdefault(str(g),split)
                if previous!=split:raise ValueError('Cross-source split leakage')

    for split in ('train','validation'):
        for e in ds['shards'][split]:
            f=a.bidding_data/e['file']
            if sha(f)!=e['sha256']:raise ValueError('Bidding data changed')
            with np.load(f,allow_pickle=False) as z:
                d={k:z[k] for k in FIELDS if k not in ('play','support')}
            save('bidding',split,add_empty_play(d))
        f=Path(ds['legacy'][split]['path'])
        if sha(f)!=ds['legacy'][split]['sha256']:raise ValueError('BEN data changed')
        with np.load(f,allow_pickle=False) as z:
            # Expand play zeros in small chunks, avoiding a multi-GB allocation.
            d={k:z[k] for k in FIELDS if k not in ('play','support')}
        for start in range(0,len(d['kind']),4096):
            save('ben',split,add_empty_play({k:v[start:start+4096] for k,v in d.items()}))
        del d
    atomic_json(a.out/'auction-progress.json',dict(counts))
    # Freeze list and file hashes now. Atomic completed episodes can be used even
    # when a surrounding collection shard is still incomplete.
    files={}
    for src in read(a.sources):
        root=Path(src['path'])
        if not root.exists():raise ValueError(f'Missing input: {root}')
        if root.is_file() and root.suffix=='.jsonl':
            h=sha(root)
            for line,text in enumerate(root.read_text().splitlines()):
                if text.strip():files[f'{root}#{line}']=dict(path=str(root),sha256=h,role=src['role'],line=line)
            continue
        for f in sorted(root.rglob('*.json.gz')):
            if '/failures/' in str(f):continue
            files[str(f)]=dict(path=str(f),sha256=sha(f),role=src['role'])
    atomic_json(a.out/'input-files.json',list(files.values()))
    buffers={s:[] for s in ('train','validation')}
    for i,src in enumerate(files.values()):
        f=Path(src['path'])
        if sha(f)!=src['sha256']:raise ValueError('Captured episode changed')
        obj=json.loads(f.read_text().splitlines()[src['line']]) if 'line' in src else read(f)
        if not isinstance(obj,dict):
            counts['nonplay_files']+=1;continue
        e=obj.get('record',obj)
        if not isinstance(e,dict) or 'tables' not in e or 'board' not in e:
            counts['nonplay_files']+=1;continue
        if e.get('status')!='ok':counts['incomplete_records']+=1;continue
        b=Board.from_dict(e['board']);family=deal_key(b.hands,True)
        if any(t.get('status')!='ok' for t in e['tables']):counts['incomplete_records']+=1;continue
        replay(e)
        if b.auction and auction_contract(b.dealer,b.auction)!=b.contract:raise ValueError('Auction/contract mismatch')
        # All views of a deal keep the oldest assigned split. Existing holdouts
        # remain held out, including after use of former card-play eval records.
        assigned={original_splits[digest(b.hands[j:]+b.hands[:j])] for j in range(4)
                  if digest(b.hands[j:]+b.hands[:j]) in original_splits}
        if family in bidding_splits:assigned.add(bidding_splits[family])
        if len(assigned)>1:raise ValueError('Conflicting existing split assignments')
        split=next(iter(assigned)) if assigned else split_for(b)
        old=group_splits.setdefault(family,split)
        if old!=split:raise ValueError('Rotated/related family split conflict')
        play_groups[split].add(family)
        if src['role']=='retired-evaluation' and split=='train':retired[family]=str(f)
        if split=='test':counts['play_test_records_reserved']+=1;continue
        synthetic=b.auction_source in (None,'synthetic')
        for ti,t in enumerate(e['tables']):
            key=digest([b.hands,b.dealer,b.vulnerability,b.bids,[x['card'] for x in t['actions']]])
            if key in trajectories:counts['duplicate_trajectories']+=1;continue
            trajectories.add(key)
            sources.append(dict(**src,table=ti,family=family,split=split,trajectory=key,
                                behavior=e.get('config',{}),auction_source=b.auction_source))
            g=Game(b)
            # Sixteen spread-out positions per trajectory limit correlated-row
            # overweighting and keep the capacity pilot cheap. Every completed
            # deal/trajectory is eligible; raw episode hashes permit expansion.
            rng=np.random.default_rng(int(key[:16],16))
            selected=set(np.concatenate([rng.choice(np.arange(lo,hi),4,replace=False)
                         for lo,hi in ((0,13),(13,26),(26,39),(39,52))]))
            for action in t['actions']:
                if len(g.history) not in selected:
                    g.play(card(action['card']));continue
                o=g.observation();x,support=encode_play(o)
                if synthetic:
                    x['calls'][:]=0;x['seats'][:]=4;x['state'][-1]=0
                y=np.zeros(52,np.int8)
                for seat,hand in enumerate(g.hands):y[list(hand)]=(seat-o.controller)%4
                mask=support.sum(-1)>1
                if np.any(mask & ~support[np.arange(52),y]):raise ValueError('True owner excluded')
                if mask.any():
                    buffers[split].append(dict(**x,owner_target=y,owner_loss_mask=mask,
                        support=support,kind=np.int8(2),split_group=family))
                g.play(card(action['card']))
                if len(buffers[split])>=4096:
                    save('play',split,{k:np.stack([r[k] for r in buffers[split]]) for k in FIELDS});buffers[split].clear()
        if i%250==0:
            atomic_json(a.out/'progress.json',dict(files=i+1,total=len(files),counts=dict(counts)))
            print(json.dumps(dict(files=i+1,total=len(files),play_deals={s:len(g) for s,g in play_groups.items()})),flush=True)
    for split,rows in buffers.items():
        if rows:save('play',split,{k:np.stack([r[k] for r in rows]) for k in FIELDS})
    if not all(any(e['source']==source and e['split']==split for e in entries)
               for source in ('bidding','ben','play') for split in ('train','validation')):raise ValueError('Missing training/validation domain')
    atomic_json(a.out/'play-provenance.json',sources)
    atomic_json(a.out/'retired-evaluation-families.json',retired)
    result=dict(schema=SCHEMA,validated=True,shards=entries,counts=dict(counts),
        parent_sha256=sha(a.out/'parent.npz'),bidding_dataset_sha256=sha(a.out/'bidding-dataset.json'),
        source_files_sha256=sha(a.out/'input-files.json'),play_provenance_sha256=sha(a.out/'play-provenance.json'),
        unique_play_deals={s:len(g) for s,g in play_groups.items()},unique_play_trajectories=len(trajectories),
        retired_evaluation_training_families=len(retired),test_evaluated=False,
        play_note='16 deterministic stratified pre-action positions per completed trajectory; zero-uncertainty rows excluded. Synthetic auction tokens masked; real auctions unchanged. No future cards, action choices, results or DDS inputs.',
        frozen_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    atomic_json(a.out/'dataset.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='shards'}),flush=True)

if __name__=='__main__':main()
