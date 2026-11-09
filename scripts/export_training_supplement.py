"""Export frozen completed records from partial campaigns as a tensor supplement."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.auction_policy import encode_decision
from bridge_harness.belief_capacity import FIELDS, SCHEMA, encode_play
from bridge_harness.core import Board, Game, card
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import validate_pair
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def build(runs, out):
    if out.exists(): raise ValueError('Refusing to overwrite a frozen export')
    out.mkdir(parents=True)
    m=read(runs[-1]/'manifest.json')
    belief=out/'belief';policy=out/'policy';belief.mkdir();policy.mkdir()
    entries=[];policy_entries=[];sources=[]
    buffers={domain:{s:[] for s in ('train','validation')} for domain in ('belief','policy')}
    counts=Counter();families={s:set() for s in ('train','validation')}
    def flush(domain,split):
        rows=buffers[domain][split]
        if not rows:return
        folder=belief if domain=='belief' else policy
        listing=entries if domain=='belief' else policy_entries
        path=folder/f'arena-{split}-{len(listing):06}.npz'
        np.savez_compressed(path,**{k:np.stack([r[k] for r in rows]) for k in rows[0]})
        listing.append(dict(file=path.name,sha256=sha(path),source='play',split=split,rows=len(rows)))
        counts[domain+'_'+split]+=len(rows);rows.clear()
    source_runs = runs
    files = [(p, read(p/'manifest.json'), f) for p in source_runs for f in sorted((p/'episodes').glob('*.json.gz'))]
    for source_run, source_manifest, file in files:
        r=read(file);board=Board.from_dict(r['board']);validate_pair(r,source_manifest,board,r['index'])
        split=r['split'];family=r['family']
        if family in families['train'] or family in families['validation']: raise ValueError('Duplicate training family')
        families[split].add(family)
        sources.append(dict(campaign=source_manifest['identity'],file=file.name,index=r['index'],sha256=sha(file),family=family,split=split,versions=r['versions']))
        # Only completed audited contrasts label the policy, including losses.
        events=[(episode,e) for episode in (r['focal'],r['control']) for e in episode['audits'] if not e['identical_action']]
        for episode,event in events:
            table=episode['tables'][event['candidate_table']];ply=event['ply']
            game=Game(board)
            for action in table['actions'][:ply]:game.play(card(action['card']))
            action=table['actions'][ply];x,cards=encode_decision(game.observation(),action)
            valid=x['mask'][0]>0
            chosen=int(np.flatnonzero(valid & (cards[0]==card(event['candidate_card'])))[0])
            reference=int(np.flatnonzero(valid & (cards[0]==card(event['reference_card'])))[0])
            row={k:v[0] for k,v in x.items()}
            row.update(chosen=np.int32(chosen),reference=np.int32(reference),y=np.float32(event['gain_imps']),
                       weight=np.float32(1/max(1,len(events))),group=family)
            buffers['policy'][split].append(row)
            if len(buffers['policy'][split])>=2048:flush('policy',split)
        # Every trajectory is eligible. Deduplicate replayed prefixes and sample
        # 16 deterministic pre-action states per trajectory without hidden inputs.
        seen=set();rows=[]
        for episode in (r['control'],r['focal']):
            for table in episode['tables']:
                trajectory=digest([family,[a['card'] for a in table['actions']]])
                rng=np.random.default_rng(int(trajectory[:16],16))
                selected=set(np.concatenate([rng.choice(np.arange(lo,lo+13),4,replace=False) for lo in (0,13,26,39)]))
                game=Game(board)
                for action in table['actions']:
                    key=tuple(c for _,c in game.history)
                    if len(game.history) in selected and key not in seen:
                        seen.add(key);o=game.observation();x,support=encode_play(o);mask=support.sum(-1)>1
                        if mask.any():
                            y=np.zeros(52,np.int8)
                            for seat,hand in enumerate(game.hands):y[list(hand)]=(seat-o.controller)%4
                            if np.any(mask & ~support[np.arange(52),y]):raise ValueError('True owner excluded')
                            rows.append(dict(**x,owner_target=y,owner_loss_mask=mask,support=support,kind=np.int8(2),split_group=family))
                    game.play(card(action['card']))
        # Limit duplicate-family influence while retaining raw full trajectories.
        if len(rows)>128:
            rng=np.random.default_rng(int(family[:16],16));rows=[rows[i] for i in sorted(rng.choice(len(rows),128,replace=False))]
        for row in rows:
            buffers['belief'][split].append(row)
            if len(buffers['belief'][split])>=4096:flush('belief',split)
        if len(sources)%100==0:
            atomic_json(out/'progress.json',dict(deals=len(sources),target=len(files),rows=dict(counts)))
    for domain in buffers:
        for split in buffers[domain]:flush(domain,split)
    if len(sources)!=len(files) or families['train'] & families['validation']:raise ValueError('Invalid family partition')
    atomic_json(out/'sources.json',sources)
    atomic_json(belief/'dataset.json',dict(schema=SCHEMA,validated=True,shards=entries,counts=dict(counts),
        source_files_sha256=sha(out/'sources.json'),
        unique_play_deals={k:len(v) for k,v in families.items()},test_evaluated=False,
        note='80/20 canonical family split; all branches grouped. Raw outcomes never label policy.'))
    atomic_json(policy/'dataset.json',dict(schema='audited-neural-imp-v1',validated=True,shards=policy_entries,
        counts=dict(counts),families={k:len(v) for k,v in families.items()},versions=m['bots'],
        source_manifests=[dict(identity=read(r/'manifest.json')['identity'],sha256=sha(r/'manifest.json')) for r in runs],source_files_sha256=sha(out/'sources.json')))
    atomic_json(out/'provenance.json',dict(schema='archived-arena-training-export-v1',boards=len(sources),counts=dict(counts),families={k:len(v) for k,v in families.items()},source_files_sha256=sha(out/'sources.json'),partial_campaign_snapshot=True,source_manifests=[dict(identity=read(r/'manifest.json')['identity'],sha256=sha(r/'manifest.json')) for r in runs],base_training_data_included=False,interpretation='Training-only tensor supplement. Preserve original splits; experiment partitions are separate. No score pooling.'))
    print(read(out/'provenance.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.run,a.out)
