"""Paired pool-size screen using frozen, independent reference DDS labels.

Extends the original candidate stream, never the independent reference stream.
All representative choices/weights are fixed before any DDS labels are read.
One low-priority CPU, cold DDS contexts, and per-position resume checkpoints.
"""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import Weights
from bridge_harness.bidding_sampling import WeightedSampler
from bridge_harness.layout_reduction import ReductionConfig, feature_mean, reduce_pool
from scripts.test_representative_sampling import reconstruct, seed, geometry, solve, selected


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def aggregate(rows):
    result = dict(positions=len(rows), families=len({r['family'] for r in rows}), methods={}, comparisons={})
    if not rows:
        return result
    assert result['families'] == len(rows)
    for name in rows[0]['methods']:
        m = [r['methods'][name] for r in rows]
        result['methods'][name] = dict(
            regret=float(np.mean([x['regret'] for x in m])),
            contrast_mse=float(np.mean([x['contrast_mse'] for x in m])),
            solves=float(np.mean([x['solves'] for x in m])),
            cpu_ms=float(np.mean([x['cpu_seconds'] for x in m])*1000),
            mistakes_over_quarter_trick=sum(x['regret'] > .25 for x in m),
        )
        if 'timing' in m[0]:
            result['methods'][name]['timing_ms'] = {
                k:float(np.mean([x['timing'][k] for x in m])*1000) for k in m[0]['timing']}
    for left, right in [('natural512','natural128'), ('natural256','natural128'),
                        ('natural512','natural256'), ('cap512','cap128'),
                        ('cap256','cap128'), ('cap512','cap256'),
                        ('cap128','natural128'), ('cap512','natural512'),
                        ('natural512','random32'), ('natural512','full128')]:
        d = np.array([r['methods'][left]['reference_value']-r['methods'][right]['reference_value'] for r in rows])
        boot = np.random.default_rng(2026111042).choice(d,(10000,len(d)),replace=True).mean(1)
        checks = [r for r in rows if r['reference_draws'] > 512]
        pair = dict(improvement_tricks=float(d.mean()),
                    standard_error=float(d.std(ddof=1)/np.sqrt(len(d))) if len(d)>1 else None,
                    ci95=np.quantile(boot,[.025,.975]).tolist(),
                    changed_action_sets=sum(r['methods'][left]['selected_cards'] != r['methods'][right]['selected_cards'] for r in rows),
                    nonzero_value_differences=int(np.count_nonzero(np.abs(d)>1e-12)),
                    wins=int((d>1e-12).sum()),losses=int((d < -1e-12).sum()))
        if checks:
            delta = [r['methods'][left]['double_reference_value']-r['methods'][right]['double_reference_value']
                     -(r['methods'][left]['reference_value']-r['methods'][right]['reference_value']) for r in checks]
            pair['double_reference_sensitivity'] = dict(positions=len(checks),mean_change=float(np.mean(delta)))
        result['comparisons'][left+'_vs_'+right] = pair
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--limit', type=int, default=200)
    p.add_argument('--belief', type=Path)
    p.add_argument('--library', type=Path)
    a = p.parse_args()
    original = json.loads((a.source/'inputs.json').read_text())
    belief = a.belief or Path(original['belief'])
    library = a.library or Path(original['library'])
    assert sha(belief) == original['belief_sha256'], 'Belief model changed'
    assert sha(library) == original['library_sha256'], 'DDS library changed'
    config = ReductionConfig(**json.loads((a.source/'config.json').read_text()))
    assert config.large_pool == 128 and config.large_budget == 32 and config.weighting == 'belief'
    rows = json.loads((a.source/'contexts.json').read_text())[:a.limit]
    assert all(r['split']=='validation' and r['remaining'] >= 10 for r in rows)
    keys = [r['family'][:16]+'-'+r['stage'] for r in rows]
    assert len(set(keys)) == len(keys)
    files = {str(a.source/'positions'/f'{k}.{suffix}'):sha(a.source/'positions'/f'{k}.{suffix}')
             for k in keys for suffix in ['json','npz']}
    plan = dict(source=str(a.source), source_inputs_sha256=sha(a.source/'inputs.json'),
                contexts_sha256=sha(a.source/'contexts.json'), config=asdict(config),
                belief_sha256=sha(belief),library_sha256=sha(library),
                source_labels_sha256=files,script_sha256=sha(__file__),positions=len(rows),
                pools=[128,256,512],solve_ceiling=32,reference=512,
                primary='natural512 versus natural128; original tolerance and weights held fixed',
                control='cap512 versus cap128; tolerance zero to hold solve counts at 32 where distinct geometry permits',
                selection='All six selections frozen before labels; nested candidate prefixes; original independent references',
                limitation='Reused validation screen, one candidate seed per position, expected DDS tricks rather than played IMPs')
    a.out.mkdir(parents=True, exist_ok=True)
    if (a.out/'plan.json').exists():
        assert json.loads((a.out/'plan.json').read_text()) == plan, 'Resume inputs changed'
    else:
        save(a.out/'plan.json', plan)
    net = Weights(belief)
    completed = []
    started = time.perf_counter()
    for i,(row,key) in enumerate(zip(rows, keys)):
        path = a.out/'positions'/f'{key}.json'
        if path.exists():
            completed.append(json.loads(path.read_text()))
            continue
        o = reconstruct(row)
        t = time.process_time()
        sampler = WeightedSampler(o,net.logits(o),1.)
        setup = time.process_time()-t
        rng = random.Random(seed(row['family'],row['stage'],'candidate'))
        worlds,draw_times = [],{}
        t = time.process_time()
        for j in range(512):
            worlds.append(sampler.draw(rng))
            if j+1 in (128,256,512):
                draw_times[j+1] = time.process_time()-t
        t = time.process_time()
        target = feature_mean(sampler,o)
        moment = time.process_time()-t
        proposals,packing = {},{}
        for n in (128,256,512):
            t = time.process_time()
            raw,fixed = geometry(worlds[:n],o)
            packing[n] = time.process_time()-t
            for mode,tolerance in [('natural',config.large_tolerance),('cap',0.)]:
                ix,w,info = reduce_pool(raw,fixed,32,tolerance,'belief',target,config.ridge)
                assert len(ix) <= 32 and np.all(w>=0) and abs(w.sum()-1)<1e-12
                proposals[f'{mode}{n}'] = (ix,w,info)
        # No candidate or reference outcome has been read until this point.
        prior = json.loads((a.source/'positions'/f'{key}.json').read_text())
        with np.load(a.source/'positions'/f'{key}.npz',allow_pickle=False) as z:
            assert np.array_equal(raw[:128],z['candidate_raw']), 'Candidate prefix changed'
            assert np.array_equal(fixed[0],z['fixed']) and np.array_equal(sorted(o.legal),z['legal'])
            assert np.allclose(target,prior['belief_target'],atol=1e-10,rtol=0)
            ref_y = z['reference_scores'].copy()
            old_y = z['candidate_scores'].copy()
        ref = ref_y[:512].mean(0)
        full_ref = ref_y.mean(0)
        solved_cache,methods = {},{}
        # Alternate order deterministically to avoid always timing 512 last.
        names = list(proposals)
        random.Random(seed(key,'timing-order')).shuffle(names)
        saved_arrays = dict(candidate_raw=raw,reference_scores=ref_y,legal=np.array(sorted(o.legal)))
        for name in names:
            ix,w,info = proposals[name]
            index_key = tuple(int(j) for j in ix)
            if index_key not in solved_cache:
                exact,cpu,wall = solve([worlds[j] for j in index_key],o,library)
                solved_cache[index_key] = (exact,cpu,wall)
            exact,cpu,wall = solved_cache[index_key]
            known = ix < 128
            assert np.array_equal(exact[known],old_y[ix[known]]), 'DDS labels changed'
            estimate = w@exact
            choice = selected(estimate)
            n = info['pool']
            timing = dict(setup=setup,draw=draw_times[n],packing=packing[n],moment=moment,
                          selection=info['reduction_cpu_seconds'],dds=cpu)
            methods[name] = dict(reference_value=float(ref[choice].mean()),
                regret=float(ref.max()-ref[choice].mean()),
                double_reference_value=float(full_ref[choice].mean()),
                solves=len(ix),positive_weights=int((w>0).sum()),cpu_seconds=sum(timing.values()),timing=timing,
                selected_cards=[int(sorted(o.legal)[j]) for j in choice],
                contrast_mse=float(np.square((estimate-estimate.mean())-(ref-ref.mean())).mean()),
                reduction=info)
            saved_arrays[name+'_indices'] = ix
            saved_arrays[name+'_weights'] = w
            saved_arrays[name+'_scores'] = exact
        assert methods['natural128']['selected_cards'] == prior['methods']['belief']['selected_cards']
        assert abs(methods['natural128']['reference_value']-prior['methods']['belief']['reference_value'])<1e-12
        assert proposals['natural128'][0].tolist() == prior['reduction']['belief']['indices']
        for name,n in [('random32',32),('full128',128)]:
            estimate = old_y[:n].mean(0)
            choice = selected(estimate)
            methods[name] = dict(prior['methods'][name],double_reference_value=float(full_ref[choice].mean()))
        result = dict(family=row['family'],remaining=row['remaining'],actor=o.actor,
                      opening_lead=len(o.history)==0,reference_draws=len(ref_y),methods=methods)
        path.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(path.with_suffix('.npz'),**saved_arrays)
        save(path,result)
        completed.append(result)
        save(a.out/'status.json',dict(stage='running',completed=len(completed),total=len(rows),elapsed=time.perf_counter()-started))
        if len(completed)%20==0 or len(completed)==1:
            summary = aggregate(completed)
            save(a.out/'summary.json',summary)
            print(json.dumps(dict(completed=len(completed),total=len(rows),elapsed=time.perf_counter()-started,
                                  primary=summary['comparisons']['natural512_vs_natural128'])),flush=True)
    summary = aggregate(completed)
    summary['subsets'] = {label:aggregate([r for r in completed if (r['opening_lead'] if label=='opening_lead' else not r['opening_lead'])])
                         for label in ['opening_lead','later']}
    save(a.out/'summary.json',summary)
    save(a.out/'status.json',dict(stage='complete',completed=len(completed),total=len(rows),elapsed=time.perf_counter()-started))
    print(json.dumps(dict(stage='complete',summary=summary)),flush=True)


if __name__ == '__main__':
    main()
