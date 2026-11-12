"""Freeze completed mixed play for ONE final predictive policy warm-start."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.auction_policy import encode_decision
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board,Game,card
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--legacy',type=Path,default=Path('/workspace/scratch/76c053ab1edf/completion'))
    p.add_argument('--positions',type=int,default=16);a=p.parse_args()
    if a.out.exists():raise ValueError('Refusing to overwrite frozen dataset')
    a.out.mkdir(parents=True);old_train=set()
    for f in a.legacy.glob('chunk-*/train.npz'):
        with np.load(f,allow_pickle=False) as z:old_train.update(map(str,np.unique(z['split_group'])))
    assert old_train,'Must protect original policy training families'
    files={}
    for src in read(a.sources):
        root=Path(src['path'])
        if root.suffix=='.jsonl':
            for i,line in enumerate(root.read_text().splitlines()):
                if line.strip():files[f'{root}#{i}']=dict(path=str(root),line=i,role=src['role'])
        elif root.is_file() and root.name.endswith('.json.gz'):
            files[str(root)]=dict(path=str(root),role=src['role'])
        elif root.exists():
            for f in root.rglob('*.json.gz'):
                if '/failures/' not in str(f):files[str(f)]=dict(path=str(f),role=src['role'])
    atomic_json(a.out/'input-files.json',list(files.values()))
    counts=Counter();seen_files=set();seen_trajectories=set();families={};provenance=[];shards=[]
    buffers={'train':[],'validation':[]}
    def flush(split):
        rows=buffers[split]
        if not rows:return
        arrays={k:np.stack([r[k] for r in rows]) for k in rows[0]}
        path=a.out/f'{split}-{len(shards):05d}.npz';np.savez_compressed(path,**arrays)
        shards.append(dict(file=path.name,split=split,rows=len(rows),sha256=sha(path)))
        counts[split+'_rows']+=len(rows);rows.clear()
    started=time.monotonic()
    for index,src in enumerate(files.values()):
        path=Path(src['path']);checksum=sha(path)
        key=(checksum,src.get('line'))
        if key in seen_files:counts['duplicate_files']+=1;continue
        seen_files.add(key)
        r=json.loads(path.read_text().splitlines()[src['line']]) if 'line' in src else read(path)
        if isinstance(r,dict):r=r.get('record',r)
        if not isinstance(r,dict) or 'board' not in r or 'tables' not in r:continue
        if r.get('status')!='ok' or any(t.get('status')!='ok' for t in r['tables']):continue
        b=Board.from_dict(r['board'])
        if not b.contract:continue
        replay(r);family=deal_key(b.hands,True)
        old_training=any(digest(b.hands[j:]+b.hands[:j]) in old_train for j in range(4))
        split='train' if old_training or int(family[:8],16)%5 else 'validation'
        assert families.setdefault(family,split)==split
        synthetic=b.auction_source in (None,'synthetic')
        for ti,t in enumerate(r['tables']):
            # Keep distinct search/behavior observations; omit timing and path names.
            tk=digest([b.hands,b.dealer,b.vulnerability,b.bids,
                [(z['card'],z.get('samples'),z.get('estimates'),z.get('behavior_probabilities')) for z in t['actions']]])
            if tk in seen_trajectories:counts['duplicate_trajectories']+=1;continue
            seen_trajectories.add(tk)
            eligible=[i for i,z in enumerate(t['actions']) if z.get('estimates') and
                sum(v>0 for v in z.get('proposal_probabilities',z.get('behavior_probabilities',{})).values())>=2]
            rng=np.random.default_rng(int(tk[:16],16));take=set(rng.choice(eligible,min(a.positions,len(eligible)),replace=False).tolist())
            g=Game(b);used=0
            for i,z in enumerate(t['actions']):
                if i in take:
                    o=g.observation();encoded=encode_decision(o,z,synthetic)
                    if encoded:
                        x,cards=encoded;chosen=card(z['card']);ix=np.flatnonzero((cards[0]==chosen)&(x['mask'][0]>0))
                        if len(ix)!=1:raise ValueError('Chosen card outside logged support')
                        probabilities=z.get('behavior_probabilities',{})
                        full=all(probabilities.get(str_c,0)>0 for str_c in z.get('proposal_probabilities',probabilities) if z.get('proposal_probabilities',probabilities)[str_c]>0)
                        prob=float(probabilities.get(z['card'],z.get('selected_probability',1)))
                        if not 0<prob<=1:raise ValueError('Invalid logged probability')
                        # Uniform-target correction is valid only under full coverage.
                        weight=1/(float(x['mask'].sum())*prob) if full else 1.
                        decl=o.actor%2==o.contract.declarer%2
                        final=t['declarer_tricks'] if decl else 13-t['declarer_tricks']
                        already=o.declarer_tricks if decl else len(o.history)//4-o.declarer_tricks
                        row={k:v[0] for k,v in x.items()};row['actions']=row['actions'].astype(np.int8)
                        row.update(chosen=np.int8(ix[0]),y=np.float32(final-already),weight=np.float32(weight),
                            group=family,coverage=np.int8(full),source=int(index),table=np.int8(ti),ply=np.int8(i),
                            auction_real=np.int8(not synthetic),actor_declarer=np.int8(decl))
                        buffers[split].append(row);used+=1
                        counts[('full_coverage' if full else 'partial_coverage')+'_rows']+=1
                        if len(buffers[split])>=2048:flush(split)
                g.play(card(z['card']))
            if used:
                provenance.append(dict(**src,sha256=checksum,family=family,split=split,trajectory=tk,table=ti,rows=used,
                    retired_benchmark=src['role']!='training',auction_source=b.auction_source,behavior=r.get('config',{})))
                counts[split+'_trajectories']+=1
        if index%250==0:
            print(json.dumps(dict(files=index+1,total=len(files),rows=dict(counts),seconds=time.monotonic()-started)),flush=True)
    for split in buffers:flush(split)
    atomic_json(a.out/'provenance.json',provenance)
    atomic_json(a.out/'families.json',families)
    manifest=dict(schema='auction-policy-predictive-bootstrap-v1',validated=True,shards=shards,counts=dict(counts),
        families=dict(Counter(families.values())),source_list_sha256=sha(a.sources),positions_per_trajectory=a.positions,
        old_policy_train_groups=len(old_train),old_train_excluded_from_validation=True,
        split='New80/20canonicaldeal-family split; all old-policy gradient families forcedtrain. Prior test benchmarks explicitly retired when imported into training. Validation is selection, not independent final test.',
        inputs='Only public auction/history, visible cards, contract, search estimates. Synthetic auctions masked. No hidden cards, outcomes or source IDs enter neural inputs.',
        target='Remaining acting-partnership tricks for chosen card; last predictive bootstrap only. Subsequent policy training must use random audited fork advantages.',
        frozen_epoch=time.time(),seconds=time.monotonic()-started)
    atomic_json(a.out/'dataset.json',manifest);print(json.dumps({k:v for k,v in manifest.items() if k!='shards'}),flush=True)


if __name__=='__main__':main()
