#!/usr/bin/env python3
"""Audit independent auctions and export eight legal observations per deal.

Four completed-auction views plus one pre-call view per observer. Prefix views
contain no future calls or final contract. True owners remain separate targets.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.core import Board, SEATS, auction_contract
from bridge_harness.training import digest, split_for
from bridge_harness.auction_belief import encode_auction, SCHEMA


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--exclude-groups',type=Path,required=True)
    p.add_argument('--expected-deals',type=int,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Refusing overwrite')
    manifest=json.loads((args.data/'manifest.json').read_text())
    reserved=set(json.loads(args.exclude_groups.read_text())['deal_ids'])
    expected=set(manifest['deal_ids']);seen=set();groups={s:set() for s in ('train','validation','test')}
    rows={s:[] for s in groups};passed=0;total_calls=0;max_calls=0
    rng=random.Random(20261108)
    for path in sorted((args.data/'episodes').glob('*.json.gz')):
        with gzip.open(path,'rt') as f:e=json.load(f)
        b=Board.from_dict(e['board']);did=digest(b.hands);split=split_for(b)
        if did in seen or did in reserved:raise ValueError('Duplicate/reserved original deal')
        seen.add(did);groups[split].add(did)
        assert e['metadata']['deal_id']==did and e['metadata']['split_group']==did
        assert e['metadata']['split']==split and auction_contract(b.dealer,b.auction)==b.contract
        assert b.auction_source=='BEN-neural-only-batched'
        assert len(e['transcript'])==len(b.auction)
        for i,t in enumerate(e['transcript']):
            assert t['seat']==SEATS[(b.dealer+i)%4] and t['bid']==b.auction[i]
            assert t['behavior_probability']==1 and 0<=t['neural_probability']<=1
        passed+=b.contract is None;total_calls+=len(b.auction);max_calls=max(max_calls,len(b.auction))
        owners=np.empty(52,np.int8)
        for seat,hand in enumerate(b.hands):owners[list(hand)]=seat
        for observer in range(4):
            before=rng.choice([i for i in range(len(b.auction)) if (b.dealer+i)%4==observer])
            for length,kind in ((before,0),(len(b.auction),1)):
                x,support=encode_auction(b.hands[observer],observer,b.dealer,b.vulnerability,b.auction[:length])
                target=(owners-observer)%4;mask=target!=0
                assert support[np.arange(52),target].all() and mask.sum()==39
                rows[split].append((x,target,mask,did,kind))
    assert len(seen)==args.expected_deals and seen==expected
    assert all(not groups[a].intersection(groups[b]) for a in groups for b in groups if a!=b)
    args.out.mkdir(parents=True)
    audit=dict(validated=True,schema=SCHEMA,independent_auctions=len(seen),passed_out=passed,
        complete_played_games=0,calls=total_calls,max_calls=max_calls,excluded_deals=len(reserved),
        duplicate_deals=0,split_leakage=0,source_manifest_sha256=hashlib.sha256((args.data/'manifest.json').read_bytes()).hexdigest(),
        splits={s:dict(deals=len(groups[s]),rows=len(rows[s])) for s in groups},exports={})
    for split,items in rows.items():
        arrays={k:np.stack([r[0][k] for r in items]) for k in ('state','calls','seats')}
        arrays.update(owner_target=np.stack([r[1] for r in items]),owner_loss_mask=np.stack([r[2] for r in items]),
            split_group=np.array([r[3] for r in items]),kind=np.array([r[4] for r in items],np.int8))
        path=args.out/f'{split}.npz';np.savez_compressed(path,**arrays)
        audit['exports'][split]=hashlib.sha256(path.read_bytes()).hexdigest()
    (args.out/'audit.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
