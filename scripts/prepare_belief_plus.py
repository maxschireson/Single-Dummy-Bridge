"""Freeze family-contained joint data; DDS estimates are targets only."""
import argparse,gzip,json,hashlib,sys,time
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card,symbol
from bridge_harness.belief_plus import encode_observation
from bridge_harness.bidding_env import deal_key
from bridge_harness.selfplay import atomic_json
from scripts.policy_choice_data import family_split

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',action='append',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--per-family',type=int,default=128)
    p.add_argument('--part',type=int,default=0);p.add_argument('--parts',type=int,default=1)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    files=[p for run in a.run for p in sorted((run/'episodes').glob('*.json.gz'))]
    files=files[a.part::a.parts]
    atomic_json(a.out/'snapshot.json',dict(files=[str(p) for p in files],per_family=a.per_family))
    buffers=defaultdict(list);shards=[];families=[];seen=set();start=time.time();stats=Counter()
    def flush(split):
        rows=buffers[split]
        if not rows:return
        data={k:np.stack([r[k] for r in rows]) for k in rows[0]};path=a.out/f'{split}-{len(shards):05d}.npz'
        np.savez_compressed(path,**data)
        shards.append(dict(file=path.name,split=split,rows=len(rows),sha256=hashlib.sha256(path.read_bytes()).hexdigest()));rows.clear()
    for fi,path in enumerate(files):
        raw=path.read_bytes();r=json.loads(gzip.decompress(raw));family=r['family']
        if family in seen:raise ValueError('Duplicate family')
        seen.add(family);split=family_split(family);candidates=[];keys=set();boards=[]
        for room,e in r['unique_tables'].items():
            if e.get('schema_version')=='v4-passed-out-v1':continue
            board=Board.from_dict(e['board'])
            if deal_key(board.hands,True)!=family:raise ValueError('Family mismatch')
            boards.append(board.to_dict())
            for ti,t in enumerate(e['tables']):
                game=Game(board)
                for ply,act in enumerate(t['actions']):
                    chosen=card(act['card']);o=game.observation()
                    # All executed alternatives are eligible, never DDS's near-tie mask.
                    if not act.get('replayed_prefix') and len(o.legal)>1:
                        key=(tuple(game.history),chosen,t['declarer_tricks'],board.contract)
                        if key not in keys:
                            keys.add(key)
                            # Store compact replay locator; encode only sampled positions.
                            candidates.append((ply,board,t,chosen,dict(act),ti))
                    game.play(chosen)
                if not game.done or game.ns_score()!=t['ns_score']:raise ValueError('Invalid replay')
        rng=np.random.default_rng(int(family[:16],16));early=[i for i,c in enumerate(candidates) if c[0]<28];late=[i for i,c in enumerate(candidates) if c[0]>=28]
        take=[]
        for ix,n in ((early,3*a.per_family//4),(late,a.per_family//4)):
            take+=rng.choice(ix,min(n,len(ix)),replace=False).tolist() if ix else []
        if len(take)<a.per_family:
            rest=sorted(set(range(len(candidates)))-set(take));take+=rng.choice(rest,min(a.per_family-len(take),len(rest)),replace=False).tolist() if rest else []
        rows=[]
        for i in take:
            ply,board,t,chosen,act,ti=candidates[i];game=Game(board)
            for b in t['actions'][:ply]:game.play(card(b['card']))
            o=game.observation();x,support,cards=encode_observation(o)
            owners=np.zeros(52,np.int8)
            for s,h in enumerate(game.hands):owners[list(h)]=(s-o.controller)%4
            mask=support.sum(-1)>1
            if np.any(~support[np.arange(52),owners]&mask):raise ValueError('Ownership support')
            declaring=o.actor%2==o.contract.declarer%2
            already=o.declarer_tricks if declaring else ply//4-o.declarer_tricks
            y=(t['declarer_tricks'] if declaring else 13-t['declarer_tricks'])-already
            q=np.zeros(13,np.float32);qm=np.zeros(13,bool)
            for j,c in enumerate(cards):
                est=act.get('estimates',{}).get(symbol(int(c))) if c>=0 else None
                if est is not None:
                    q[j]=(est['declarer_tricks'] if declaring else 13-est['declarer_tricks'])-already;qm[j]=True
            row=dict(**x,support=support,owner=owners,owner_mask=mask,cards=cards,chosen=np.int8(np.flatnonzero(cards==chosen)[0]),y=np.int8(y),remaining=np.int8(13-ply//4),ply=np.int8(ply),q=q,q_mask=qm,group=family,weight=np.float32(1/max(1,len(take))))
            row['actions']=row['actions'].astype(np.int8);rows.append(row)
        buffers[split]+=rows;families.append(dict(family=family,split=split,source=str(path),sha256=hashlib.sha256(raw).hexdigest(),rows=len(rows),candidate_rows=len(candidates),boards=boards))
        stats[split+'_rows']+=len(rows);stats['early_rows']+=int(sum(row['ply']<28 for row in rows));stats['candidate_rows']+=len(candidates)
        if len(buffers[split])>=4096:flush(split)
        if (fi+1)%100==0:print(json.dumps(dict(files=fi+1,total=len(files),seconds=time.time()-start,stats=dict(stats))),flush=True)
    for split in ('train','validation','test'):flush(split)
    atomic_json(a.out/'families.json',families)
    atomic_json(a.out/'dataset.json',dict(schema='belief-plus-public-only-v1',shards=shards,stats=dict(stats),families=dict(Counter(f['split'] for f in families)),per_family=a.per_family,early_fraction=.75,split_rule='canonical family modulo10:0 test,5 validation,else train',seconds=time.time()-start))
if __name__=='__main__':main()
