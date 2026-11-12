"""Bounded, resumable random fork collection with frozen direct-auction policy."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.fork_audit import DraftPlayer,ForkBudget,collect_board
from bridge_harness.public_belief_player import PublicBeliefPlayer
from bridge_harness.corpus import load
from bridge_harness.bidding_env import deal_key
from bridge_harness.improvement import read,writer_lock
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','corpus','belief','bootstrap','incumbent'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--seconds',type=float,default=180);p.add_argument('--probability',type=float,default=.5)
    p.add_argument('--multiplier',type=float,default=3.);p.add_argument('--max-depth',type=int,default=2)
    p.add_argument('--exploration',type=float,default=.15);p.add_argument('--samples',type=int,default=32)
    p.add_argument('--seed',type=int,default=2026110908);a=p.parse_args()
    a.root.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('BRIDGE_DDS_CACHE',str((a.root/'dds-cache.sqlite').resolve()))
    versions={name:sha(getattr(a,name)) for name in ('belief','bootstrap','incumbent')}
    source_names=['fork_audit','auction_policy','public_belief_player','policy_selector','combined_player',
        'belief_capacity','auction_belief','bidding_sampling','players','sampling','dds','dds_cache','core','training','runner']
    sources={name:sha(ROOT/'bridge_harness'/f'{name}.py') for name in source_names}
    sources['collector']=sha(__file__)
    config=dict(schema='random-fork-collection-v1',versions=versions,source_sha256=sources,corpus_sha256=sha(a.corpus),
        probability=a.probability,multiplier=a.multiplier,max_depth=a.max_depth,exploration=a.exploration,
        samples=a.samples,seed=a.seed,reference='old selector with SAME promoted beliefs/PIMC samples',
        continuation='Frozen candidate and reference partnerships; alternate candidate NS/EW by board',
        policy_objective='ONLY matched audited IMP differences after this predictive bootstrap')
    with writer_lock(a.root):
        if (a.root/'config.json').exists():assert read(a.root/'config.json')==config,'Frozen configuration changed'
        else:atomic_json(a.root/'config.json',config)
        boards=load(a.corpus);families=[deal_key(b.hands,True) for b in boards]
        assert len(set(families))==len(boards),'Repeated deal family'
        budget=ForkBudget(probability=a.probability,multiplier=a.multiplier,max_depth=a.max_depth)
        records=[];done=set()
        for f in sorted((a.root/'episodes').glob('*.json.gz')):
            r=read(f);assert r['versions']==versions and r['status']=='ok';records.append(r);done.add(r['family'])
            budget.base_cpu+=r['compute']['base_cpu'];budget.branch_cpu+=r['compute']['branch_cpu']
            budget.forks+=len(r['tables'])-1
        players=dict(candidate=DraftPlayer(a.belief,a.bootstrap,a.incumbent,samples=a.samples,exploration=a.exploration),
            incumbent=PublicBeliefPlayer(a.belief,a.incumbent,samples=a.samples,exploration=0.))
        started=time.monotonic()
        try:
            for i,b in enumerate(boards):
                family=families[i]
                if family in done:continue
                if time.monotonic()-started>=a.seconds or (a.root/'STOP').exists():break
                assignment=['candidate' if seat%2==i%2 else 'incumbent' for seat in range(4)]
                r=collect_board(b,players,assignment,a.seed+i,budget,versions)
                atomic_json(a.root/'episodes'/f'{family}.json.gz',r,compressed=True);records.append(r);done.add(family)
                audits=[v for z in records for v in z['audits'] if not v['identical_action']]
                state=dict(boards=len(done),target=len(boards),audited_deviations=len(audits),
                    recursive_deviations=sum(v['depth']>0 for v in audits),
                    zero_action_audits=sum(v['identical_action'] for z in records for v in z['audits']),
                    budget_skips=sum(len(z['budget_skips']) for z in records),
                    mean_local_imp_gain=sum(v['gain_imps'] for v in audits)/len(audits) if audits else None,
                    base_cpu=budget.base_cpu,branch_cpu=budget.branch_cpu,
                    compute_multiplier=(budget.base_cpu+budget.branch_cpu)/budget.base_cpu if budget.base_cpu else 1.,
                    complete=len(done)==len(boards),epoch=time.time(),promoted=False)
                atomic_json(a.root/'state.json',state)
                print(json.dumps(state),flush=True)
        finally:
            for player in players.values():
                if hasattr(player,'close'):player.close()


if __name__=='__main__':main()
