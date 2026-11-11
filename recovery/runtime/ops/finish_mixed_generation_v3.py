"""Shared bidding transition: all play versions use the latest validated actor.

Retain the actual best if neither play component changes.

At a completed boundary, fit both nets and prepare the next frozen generation.

Training never waits for a significant positive IMP result. Failed predictive
updates retain the prior component. A play-demoted version ages into the roster.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import generate,save,load
from bridge_harness.improvement import read,writer_lock
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import mixture,summarize,verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.mixed_generation import freeze_spec,receipts,supervised_command
from ops.shared_bidding import prepare_shared_bidder,bind_shared_bidder


def successor_plan(m, state, belief_changed, policy_changed):
    roster=list(m['roster'])
    if state['demotion']:
        roster.remove(m['candidate']);roster.insert(roster.index(m['reference'])+1,m['candidate'])
    changed=belief_changed or policy_changed
    candidate=f"g{m['generation']+1:04}-belief-policy" if changed else state['best']
    if changed:roster.insert(0,candidate)
    else:
        roster.remove(candidate);roster.insert(0,candidate)
    reference=state['best'] if changed else next(v for v in roster if v!=candidate)
    return dict(candidate=candidate,reference=reference,roster=roster,changed=changed)


def finish(run):
    with writer_lock(run/'transition'):
        m=read(run/'manifest.json');verify_generation(run,m);state=summarize(receipts(run,m,audit=True),m)
        if not state['complete']:raise ValueError('Cannot train before generation boundary')
        cfg=read(run/'training-config.json');python=cfg['python'];candidate=m['bots'][m['candidate']]
        parent_belief=run/candidate['belief'];parent_policy=run/candidate['policy']
        data=run/'training-data'
        if not (data/'complete.json').exists():
            supervised_command([sys.executable,'scripts/prepare_mixed_training.py','--run',str(run),'--out',str(data),
                '--base',cfg['base_belief_data'],'--parent',str(parent_belief)],run,43200)
        policy_out=run/'policy-fit';belief_out=run/'belief-fit'
        while not (policy_out/'result.json').exists():
            supervised_command([python,'scripts/train_mixed_policy.py','--data',str(data/'policy'),'--out',str(policy_out),
                '--parent',str(parent_policy),'--seconds','240'],run,43200)
        parent_bot=run/'belief-parent.json';registry=run/'belief-parent-registry.json'
        if not parent_bot.exists():
            atomic_json(parent_bot,dict(identity=candidate['identity'],spec=dict(artifacts=dict(belief=dict(
                file=str(parent_belief),sha256=sha(parent_belief))))))
            atomic_json(registry,dict(collector=str(parent_bot),collector_identity=candidate['identity']))
        while not (belief_out/'result.json').exists() or not read(belief_out/'result.json')['complete']:
            supervised_command([python,'scripts/continue_large_belief.py','--data',str(data/'belief'),'--out',str(belief_out),
                '--parent-checkpoint',cfg['belief_checkpoint'],'--registry',str(registry),'--run-seconds','240'],run,43200)
        policy=read(policy_out/'result.json');belief=read(belief_out/'result.json')
        new_belief=Path(belief['selected_weights']) if belief['promotion_eligible'] else parent_belief
        new_policy=Path(policy['selected_weights'])
        if sha(new_policy)!=policy['selected_sha256']:raise ValueError('Policy result changed')
        if belief['promotion_eligible'] and sha(new_belief)!=belief['selected_sha256']:raise ValueError('Belief result changed')
        n=m['generation']+1;next_run=run.parent/f'g{n:04}';next_run.mkdir(parents=True,exist_ok=True)
        plan=successor_plan(m,state,sha(new_belief)!=sha(parent_belief),sha(new_policy)!=sha(parent_policy))
        name=plan['candidate'];target=m['next_generation_target']
        shared=prepare_shared_bidder(next_run,cfg)
        if not (next_run/'manifest.json').exists():
            roster=plan['roster']
            bots={name:freeze_spec(next_run,name,new_belief,new_policy)} if plan['changed'] else {}
            for old in m['roster']:
                s=m['bots'][old]
                bots[old]=freeze_spec(next_run,old,run/s['belief'] if s.get('belief') else None,
                    run/s['policy'] if s.get('policy') else None,s['belief_kind'])
            bind_shared_bidder(bots,shared)
            input_path=next_run/'input.jsonl';auction_path=next_run/'auctions'
            if not (auction_path/'frozen.jsonl').exists():
                if not input_path.exists():save(generate(target+max(200,target//100),m['seed']+n*100003),input_path)
                supervised_command([python,'scripts/loop_collect_auctions.py','--ben-dir',cfg['ben_dir'],'--config',str(next_run/shared['config']),
                    '--input-corpus',str(input_path),'--out',str(auction_path),'--count',str(len(load(input_path)))],run,43200)
            previous=set()
            from bridge_harness.bidding_env import deal_key
            for generation in run.parent.glob('g*/manifest.json'):
                g=read(generation)
                previous.update(deal_key(b.hands,True) for b in load(generation.parent/g['corpus']))
            boards=[]
            for b in load(auction_path/'frozen.jsonl'):
                f=deal_key(b.hands,True)
                if b.contract and f not in previous:
                    boards.append(b);previous.add(f)
                    if len(boards)==target:break
            if len(boards)!=target:raise ValueError('Not enough fresh contracted deals for successor')
            save(boards,next_run/'corpus.jsonl')
            new=deepcopy(m)
            new.update(bidding=shared,generation=n,target=target,candidate=name,reference=plan['reference'],bots=bots,roster=roster,
                mixture=mixture(roster),seed=m['seed']+n*100003,corpus_sha256=sha(next_run/'corpus.jsonl'),
                source_sha256=source_hash(),input_corpus_sha256=sha(auction_path/'frozen.jsonl'),
                previous_generation=str(run),previous_manifest_sha256=sha(run/'manifest.json'),
                demotion_looks=sorted({min(target,k) for k in (500,1000,2500,5000,10000,25000,50000,100000,target)}),
                next_generation_target=min(250000,target*2),
                created_epoch=time.time(),component_validation=dict(belief=belief['promotion_eligible'],policy=policy['eligible']))
            if m.get('protocol') == 'direct-pairs-v1':
                new.update(direct_versions=dict(zip('ABC', roster[:3])), legacy_completed=0,
                    retained_training_runs=[], batch_target=target,
                    pair_protocol='Direct swapped-partnership two-table matches, separate pair scores',
                    pair_interpretation='Labels follow frozen successor roster; consult component hashes for attribution')
            new.pop('identity',None);new['identity']=digest(new)
            atomic_json(next_run/'manifest.json',new);atomic_json(next_run/'state.json',summarize([],new))
        checkpoints=dict(cfg.get('belief_checkpoints',{}))
        checkpoints.setdefault(m['candidate'],cfg['belief_checkpoint'])
        if m['bots'][m['reference']].get('artifact_sha256',{}).get('belief')==sha(parent_belief):
            checkpoints.setdefault(m['reference'],cfg['belief_checkpoint'])
        if plan['changed']:
            checkpoints[name]=str((ROOT/belief['selected_checkpoint']).resolve()) if belief['promotion_eligible'] else cfg['belief_checkpoint']
        if name not in checkpoints:raise ValueError('Missing selected historical belief optimizer checkpoint')
        next_cfg=dict(cfg,base_belief_data=str(data/'belief'),belief_checkpoint=checkpoints[name],belief_checkpoints=checkpoints,ben_config=str(next_run/shared['config']))
        atomic_json(next_run/'training-config.json',next_cfg)
        atomic_json(run/'next-generation.json',dict(run=str(next_run),generation=n,target=target,
            source_boundary_boards=m['target'],previous_demoted=bool(state['demotion']),new_weights=plan['changed'],candidate=plan['candidate'],inconclusive_does_not_block=True))
        atomic_json(run.parent/'current.json',dict(run=str(next_run),generation=n,target=target))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    finish(p.parse_args().run.resolve())
