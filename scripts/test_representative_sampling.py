"""Fresh belief draws, independent DDS reference, and cold per-method timings.

The reserved test families are untouched. Geometry tolerances use only training
positions and no DDS labels. This is a validation pilot, not a whole-play match.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse
from collections import defaultdict
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board, Game, card
from bridge_harness.belief_capacity import Weights
from bridge_harness.bidding_sampling import WeightedSampler
from bridge_harness.dds import DDS
from bridge_harness.layout_geometry import encode
from bridge_harness.layout_reduction import ReductionConfig, cluster_layouts, feature_mean, reduce_pool, pack
from scripts.prepare_layout_embedding import save, CLEAN


def seed(*parts):return int(hashlib.sha256(repr(parts).encode()).hexdigest()[:14],16)


def reconstruct(row):
    game=Game(Board.from_dict(row['board']))
    for c in row['history']:game.play(c)
    return game.observation()


def contexts(data, train_count, validation_count):
    with gzip.open(data/'contexts.json.gz','rt') as f:original=json.load(f)
    split={row['family']:row['split'] for row in original}
    wanted={}
    for label,n in [('train',train_count),('validation',validation_count)]:
        families=sorted(f for f,s in split.items() if s==label)
        random.Random(seed('families',label)).shuffle(families)
        wanted.update({f:label for f in families[:n]})
    sources=json.loads((data/'sources.json').read_text())['episodes'];found={}
    for path,checksum in sorted(sources.items()):
        raw=Path(path).read_bytes();ep=json.loads(gzip.decompress(raw));family=ep['family']
        if family not in wanted or family in found:continue
        if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('Source changed')
        if not {ep.get('candidate'),ep.get('opponent')} <= CLEAN:raise ValueError('Unclean play source')
        rooms=[r for r in ep['unique_tables'].values() if r['status']=='ok' and r['tables'] and r['board'].get('contract')]
        if not rooms:continue
        room=random.Random(seed(family,'room')).choice(rooms);trajectory=room['tables'][0]
        game=Game(Board.from_dict(room['board']));buckets=defaultdict(list)
        for action in trajectory['actions']:
            o=game.observation();remaining=13-len(o.history)//4
            if len(o.legal)>1 and remaining>=4:
                stage='large' if remaining>=10 else 'medium' if remaining>=7 else 'small'
                buckets[stage].append(dict(family=family,split=wanted[family],stage=stage,remaining=remaining,
                    board=room['board'],history=[c for _,c in o.history],source=path,source_sha256=checksum))
            game.play(card(action['card']))
        chosen=[]
        for stage in ('large','medium','small'):
            if buckets[stage]:chosen.append(random.Random(seed(family,stage)).choice(buckets[stage]))
        found[family]=chosen
    rows=[r for f in sorted(found) for r in found[f]]
    if len(found)!=len(wanted):raise ValueError('Could not reconstruct all selected families')
    return rows


def draw(o,net,n,key):
    start=time.process_time();sampler=WeightedSampler(o,net.logits(o),1.)
    setup=time.process_time()-start;rng=random.Random(key);worlds=[];prefix={}
    start=time.process_time()
    for i in range(n):
        worlds.append(sampler.draw(rng))
        if i+1 in (16,32,64,128):prefix[i+1]=time.process_time()-start
    return sampler,worlds,setup,prefix


def geometry(worlds,o):
    raw=np.stack([pack(h,o.contract.trump,o.leader,o.trick) for h in worlds])
    fixed=np.tile([h is not None for h in o.known_hands],(len(worlds),1))
    return raw,fixed


def solve(worlds,o,library):
    solver=DDS(library,cache_path='')
    try:
        start=time.process_time();wall=time.perf_counter()
        values=solver.solve_batch(worlds,o.contract.trump,o.leader,o.trick,
                                  fixed_seats=[i for i,h in enumerate(o.known_hands) if h is not None])
        cpu=time.process_time()-start;wall=time.perf_counter()-wall
        legal=sorted(o.legal)
        if any(set(v)!=set(legal) for v,_ in values):raise ValueError('DDS labels mismatch')
        return np.array([[v[c] for c in legal] for v,_ in values],np.int8),cpu,wall
    finally:solver.close()


def selected(estimate):return np.flatnonzero(np.isclose(estimate,estimate.max(),atol=1e-8,rtol=0))


def summary(rows):
    result={}
    for stage in ('large','medium','small'):
        rr=[r for r in rows if r['stage']==stage]
        if not rr:continue
        output={}
        for method in rr[0]['methods']:
            differences=np.array([r['methods'][method]['reference_value']-r['methods']['random32']['reference_value'] for r in rr])
            # Exactly one observation per family per stage; bootstrap whole families.
            boot=np.random.default_rng(2026111034).choice(differences,(5000,len(rr)),replace=True).mean(1)
            output[method]=dict(regret=float(np.mean([r['methods'][method]['regret'] for r in rr])),
                improvement_vs_random32=float(differences.mean()),ci95=np.quantile(boot,[.025,.975]).tolist(),
                regret_std=float(np.std([r['methods'][method]['regret'] for r in rr])),
                mistakes_over_quarter_trick=sum(r['methods'][method]['regret']>.25 for r in rr),
                mean_solve_count=float(np.mean([r['methods'][method]['solves'] for r in rr])),
                mean_cpu_seconds=float(np.mean([r['methods'][method]['cpu_seconds'] for r in rr])))
        result[stage]=dict(positions=len(rr),families=len({r['family'] for r in rr}),methods=output)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--belief',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--calibration-families',type=int,default=12);p.add_argument('--validation-families',type=int,default=24)
    p.add_argument('--reference',type=int,default=512)
    p.add_argument('--context-file',type=Path);p.add_argument('--config-file',type=Path)
    p.add_argument('--extended',action='store_true',help='Matched-count control, 64-to-16 on large positions, and marked reference checks')
    p.add_argument('--large-only',action='store_true',help='Require large contexts and omit the 16-solve experiments')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'positions').mkdir(exist_ok=True)
    inputs=dict(belief=str(a.belief),belief_sha256=hashlib.sha256(a.belief.read_bytes()).hexdigest(),
                library=str(a.library),library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                calibration_families=a.calibration_families,validation_families=a.validation_families,reference=a.reference,
                context_sha256=hashlib.sha256(a.context_file.read_bytes()).hexdigest() if a.context_file else None,
                config_sha256=hashlib.sha256(a.config_file.read_bytes()).hexdigest() if a.config_file else None,extended=a.extended,large_only=a.large_only,
                sampler='WeightedSampler at strength=1; all draws retained with multiplicity',
                target='Exact shape and honor-strength expectations from constrained sampler marginals',
                primary='Independent-reference expected action value versus random32, by stage',
                reserved_test='Untouched; frozen validation pilot only; no policy reranking or whole-play claim')
    inputs_path=a.out/'inputs.json'
    if inputs_path.exists():
        previous=json.loads(inputs_path.read_text())
        for key,default in [('context_sha256',None),('config_sha256',None),('extended',False),('large_only',False)]:previous.setdefault(key,default)
        if previous!=inputs:raise ValueError('Resume inputs changed')
    save(inputs_path,inputs)
    if (a.out/'contexts.json').exists():rows=json.loads((a.out/'contexts.json').read_text())
    else:
        rows=json.loads(a.context_file.read_text()) if a.context_file else contexts(a.data,a.calibration_families,a.validation_families)
        save(a.out/'contexts.json',rows)
    if a.large_only and any(r['remaining']<10 for r in rows):raise ValueError('Non-large position in large-only screen')
    net=Weights(a.belief)
    if (a.out/'config.json').exists():config=ReductionConfig(**json.loads((a.out/'config.json').read_text()))
    elif a.config_file:
        config=ReductionConfig(**json.loads(a.config_file.read_text()));save(a.out/'config.json',asdict(config))
    else:
        thresholds=defaultdict(list)
        for row in rows:
            if row['split']!='train' or row['stage']=='small':continue
            o=reconstruct(row);n,k=(128,32) if row['stage']=='large' else (64,16)
            _,worlds,_,_=draw(o,net,n,seed(row['family'],row['stage'],'calibration'))
            raw,fixed=geometry(worlds,o);_,_,d=cluster_layouts(encode(raw,fixed),k)
            thresholds[row['stage']].append(d['distance_threshold'])
        config=ReductionConfig(large_tolerance=float(np.median(thresholds['large'])),medium_tolerance=float(np.median(thresholds['medium'])))
        save(a.out/'calibration.json',dict(thresholds=thresholds,selection='Median capped-cut distance on training positions, without DDS labels'))
        save(a.out/'config.json',asdict(config))
    print(json.dumps(dict(stage='frozen',config=asdict(config))),flush=True)
    output=[];evaluation=[r for r in rows if r['split']=='validation'];started=time.perf_counter()
    for i,row in enumerate(evaluation):
        key=f"{row['family'][:16]}-{row['stage']}";path=a.out/'positions'/f'{key}.json'
        if path.exists():output.append(json.loads(path.read_text()));continue
        save(a.out/'status.json',dict(stage='evaluating',completed=len(output),total=len(evaluation),current=key,updated=time.time()))
        o=reconstruct(row);n,k,tolerance=(config.large_pool,config.large_budget,config.large_tolerance) if row['stage']=='large' else (config.medium_pool,config.medium_budget,config.medium_tolerance)
        sampler,worlds,setup,prefix=draw(o,net,n,seed(row['family'],row['stage'],'candidate'))
        t=time.process_time();raw,fixed=geometry(worlds,o);packing=time.process_time()-t
        t=time.process_time();target=feature_mean(sampler,o);moment_cpu=time.process_time()-t
        proposals={};infos={}
        for mode in ('cluster','pool','belief'):
            ix,w,info=reduce_pool(raw,fixed,k,tolerance,mode,target,config.ridge)
            proposals[mode]=(ix,w);infos[mode]=info
        if a.extended and not a.large_only and row['stage']=='large':
            ix16,w16,info16=reduce_pool(raw[:64],fixed[:64],16,config.medium_tolerance,'belief',target,config.ridge)
        # All choices and weights are frozen before reading any DDS answers.
        measures={};y,full_cpu,_=solve(worlds,o,a.library)
        full_name='full128' if n==128 else 'full64'
        measures[full_name]=(y.mean(0),n,setup+prefix[n]+full_cpu)
        for count in ((32,) if a.large_only else (16,32)):
            exact,cpu,_=solve(worlds[:count],o,a.library)
            if not np.array_equal(exact,y[:count]):raise ValueError('Cold baseline DDS disagrees')
            measures[f'random{count}']=(exact.mean(0),count,setup+prefix[count]+cpu)
        cluster_ix=proposals['cluster'][0]
        exact,rep_cpu,_=solve([worlds[int(j)] for j in cluster_ix],o,a.library)
        if not np.array_equal(exact,y[cluster_ix]):raise ValueError('Cold representative DDS disagrees')
        for mode,(ix,w) in proposals.items():
            if not np.array_equal(ix,cluster_ix):raise ValueError('Weights changed representatives')
            # Count all representatives for conservative timing, even if a fitted
            # weight is zero and the runtime hook can skip that solve.
            cpu=setup+prefix[n]+packing+infos[mode]['reduction_cpu_seconds']+rep_cpu+(moment_cpu if mode=='belief' else 0)
            measures[mode]=(w@y[ix],len(ix),cpu)
        if a.extended:
            count=len(cluster_ix);ym,cpu,_=solve(worlds[:count],o,a.library)
            if not np.array_equal(ym,y[:count]):raise ValueError('Matched-count DDS disagrees')
            # Prefix timing is approximated proportionally only for this control.
            measures['random_matched']=(ym.mean(0),count,setup+prefix[n]*count/n+cpu)
            if not a.large_only and row['stage']=='large':
                y16,cpu,_=solve([worlds[int(j)] for j in ix16],o,a.library)
                if not np.array_equal(y16,y[ix16]):raise ValueError('16-representative DDS disagrees')
                measures['belief16']=(w16@y16,len(ix16),setup+prefix[64]+packing/2+moment_cpu+info16['reduction_cpu_seconds']+cpu)
                infos['belief16']=info16
        ref_n=a.reference*(2 if a.extended and row.get('double_reference') else 1)
        ref_sampler,reference,ref_setup,ref_prefix=draw(o,net,ref_n,seed(row['family'],row['stage'],'independent-reference'))
        ref_y,ref_cpu,ref_wall=solve(reference,o,a.library);ref=ref_y.mean(0)
        ref_primary=ref_y[:a.reference].mean(0)
        methods={}
        for name,(estimate,count,cpu) in measures.items():
            choice=selected(estimate);value=float(ref_primary[choice].mean())
            methods[name]=dict(regret=float(ref_primary.max()-value),reference_value=value,solves=count,cpu_seconds=cpu,
                selected_cards=[int(sorted(o.legal)[j]) for j in choice],contrast_mse=float(np.square((estimate-estimate.mean())-(ref_primary-ref_primary.mean())).mean()))
            if ref_n>a.reference:methods[name].update(double_reference_value=float(ref[choice].mean()),double_reference_regret=float(ref.max()-ref[choice].mean()))
        result=dict(family=row['family'],stage=row['stage'],remaining=row['remaining'],pool=n,budget=k,
            unique_candidates=len(set(worlds)),methods=methods,reduction=infos,
            reference_draws=ref_n,
            timing=dict(setup_cpu=setup,draw_cpu=prefix,packing_cpu=packing,moment_cpu=moment_cpu,full_dds_cpu=full_cpu,
                        representative_dds_cpu=rep_cpu,reference_dds_cpu=ref_cpu,reference_dds_wall=ref_wall),
            belief_target=target.tolist())
        np.savez_compressed(a.out/'positions'/f'{key}.npz',candidate_raw=raw,candidate_scores=y,
                            reference_raw=geometry(reference,o)[0],reference_scores=ref_y,fixed=fixed[0],legal=np.array(sorted(o.legal)))
        save(path,result);output.append(result)
        save(a.out/'summary.json',summary(output))
        print(json.dumps(dict(stage='position_complete',completed=len(output),total=len(evaluation),position_stage=row['stage'],
                              remaining=row['remaining'],clusters=len(cluster_ix),elapsed=time.perf_counter()-started)),flush=True)
    result=dict(inputs=inputs,config=asdict(config),positions=len(output),summary=summary(output),elapsed_seconds=time.perf_counter()-started,
        limitations=['Validation pilot, not production promotion or a paired whole-play test.',
                     'Independent 512-draw reference is itself noisy; paired differences share that reference.',
                     'Exact belief moments do not imply exact cluster probabilities or correct nonlinear DDS expectations.',
                     'Timing uses separate fresh DDS contexts with persistent cache disabled; shared production cache may change savings.',
                     'Only large positions are evaluated; smaller-position runtime remains unchanged.' if a.large_only else
                     'Small-stage reduction is measured experimentally but remains disabled in the runtime schedule.'])
    save(a.out/'result.json',result);save(a.out/'status.json',dict(stage='complete',positions=len(output),updated=time.time()))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
