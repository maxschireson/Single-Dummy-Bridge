"""Frozen simple-geometry baselines and a two-coefficient training-only fit."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import nnls

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.layout_geometry import components, combine, encode as simple_encode
from bridge_harness.layout_embedding import Weights, encode, centered, reduce_layouts


def load(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def fit_weights(data):
    """Two nonnegative distance coefficients; equal weight per training family."""
    start = time.perf_counter()
    rng = np.random.default_rng(2026111020)
    counts = {int(f): int(np.sum(data['family'] == f)) for f in np.unique(data['family'])}
    xx, yy, sample_weights = [], [], []
    for g, f in enumerate(data['family']):
        lo, hi = data['starts'][g:g+2]
        a = rng.integers(lo, hi, 64)
        # Distinct pair members, sampled uniformly within the same position.
        b = lo + ((a - lo + rng.integers(1, hi-lo, 64)) % (hi-lo))
        ix = np.concatenate([a, b])
        fixed = np.repeat(data['fixed'][g:g+1], len(ix), 0)
        shape, strength = components(data['raw'][ix], fixed)
        x = np.stack([np.square(shape[:64]-shape[64:]).sum(1),
                      np.square(strength[:64]-strength[64:]).sum(1)], 1)
        legal = data['scores'][lo] >= 0
        y = data['scores'][ix][:, legal].astype(float)
        y -= y.mean(1, keepdims=True)
        target = np.square(y[:64]-y[64:]).mean(1)
        xx.append(x); yy.append(target)
        sample_weights.extend([1. / counts[int(f)]] * 64)
    x = np.concatenate(xx); y = np.concatenate(yy)
    sw = np.sqrt(sample_weights)
    coefficients, _ = nnls(x * sw[:, None], y * sw)
    return dict(coefficients=coefficients.tolist(), parameters=2,
                pairs=len(y), families=len(counts), groups=len(data['fixed']),
                seconds=time.perf_counter()-start,
                objective='Family-balanced nonnegative least squares, squared centered DDS action-contrast distance; no intercept',
                training_mse=float(np.average(np.square(x @ coefficients-y), weights=np.square(sw))))


def loss(y, target, indices, weights):
    estimate = weights @ y[indices]
    best = np.flatnonzero(np.isclose(estimate, estimate.max(), atol=1e-8, rtol=0))
    return [float(target.max()-target[best].mean()),
            float(np.square((estimate-estimate.mean())-(target-target.mean())).mean())]


def summarize(rows):
    result = {}
    families = sorted({r['family'] for r in rows})
    boot = np.random.default_rng(2026111024).integers(0, len(families), (5000, len(families)))
    for method in rows[0]['methods']:
        by_family = defaultdict(list)
        for r in rows:
            by_family[r['family']].append([*r['methods'][method], *r['methods']['random']])
        values = np.array([np.mean(by_family[f], 0) for f in families])
        delta = values[:, 0] - values[:, 2]
        result[method] = dict(
            family_regret=float(values[:, 0].mean()),
            family_contrast_mse=float(values[:, 1].mean()),
            group_regret=float(np.mean([r['methods'][method][0] for r in rows])),
            family_delta_vs_random=float(delta.mean()),
            delta_ci95=np.quantile(delta[boot].mean(1), [.025, .975]).tolist())
    return dict(groups=len(rows), families=len(families), methods=result)


def evaluate(data, neural, coefficients, repeats):
    groups = np.flatnonzero(np.diff(data['starts']) >= 32)
    np.random.default_rng(2026111019).shuffle(groups)
    rows = []
    for i, g in enumerate(groups):
        lo, hi = data['starts'][g:g+2]; n = int(min(64, hi-lo)); budget=n//4
        ix = np.arange(lo, lo+n); raw=data['raw'][ix]
        fixed=np.repeat(data['fixed'][g:g+1], n, 0); legal=data['scores'][ix] >= 0
        y=data['scores'][ix][:, legal[0]].astype(float); target=y.mean(0); w=np.full(n, 1/n)
        shape, strength=components(raw, fixed)
        x, _=encode(raw, fixed, legal)
        representations={
            'shape': shape, 'honor_strength': strength,
            'shape_honor': combine(shape, strength),
            'shape_honor_cosine': combine(shape, strength, cosine=True),
            'shape_honor_fitted': combine(shape, strength, coefficients),
            'card_geometry': x[:, :208],
            'neural': neural.predict(raw, fixed, legal),
            'oracle': centered(y, np.ones_like(y, bool))}
        methods={}
        for name, z in representations.items():
            indices, masses=reduce_layouts(z, w, budget)
            methods[name]=loss(y, target, indices, masses)
        rng=np.random.default_rng(2026111021 + int(g))
        random=[]; within=[]
        for _ in range(repeats):
            indices=rng.choice(n, budget, replace=False)
            random.append(loss(y, target, indices, np.full(budget, 1/budget)))
            indices, masses=reduce_layouts(representations['shape_honor'], w, budget, rng)
            within.append(loss(y, target, indices, masses))
        methods['random']=np.mean(random, 0).tolist()
        methods['shape_honor_random_within']=np.mean(within, 0).tolist()
        rows.append(dict(group=str(data['group'][g]), family=int(data['family'][g]), pool=n, budget=budget, methods=methods))
        if (i+1)%100 == 0:
            print(json.dumps(dict(stage='screen', groups=i+1, total=len(groups))), flush=True)
    return dict(all=summarize(rows), previous_400=summarize(rows[:400]), additional_309=summarize(rows[400:]), rows=rows)


def timing(data, neural, coefficients):
    # Timing only. Candidate rows span different positions; not a quality test.
    raw=data['raw'][:128]; legal=data['scores'][:128] >= 0
    group=np.searchsorted(data['starts'][1:], np.arange(128), side='right')
    fixed=data['fixed'][group]; w=np.full(128, 1/128); result={}
    for name, fn in [('shape_honor', lambda: simple_encode(raw, fixed)),
                     ('shape_honor_cosine', lambda: simple_encode(raw, fixed, cosine=True)),
                     ('shape_honor_fitted', lambda: simple_encode(raw, fixed, coefficients)),
                     ('neural', lambda: neural.predict(raw, fixed, legal))]:
        for _ in range(10): z=fn(); reduce_layouts(z, w, 32)
        encode_ns=0; select_ns=0
        for _ in range(300):
            a=time.perf_counter_ns(); z=fn(); b=time.perf_counter_ns()
            reduce_layouts(z, w, 32); c=time.perf_counter_ns()
            encode_ns+=b-a; select_ns+=c-b
        result[name]=dict(encode_ms=encode_ns/300e6, select_ms=select_ns/300e6, total_ms=(encode_ns+select_ns)/300e6)
    return dict(layouts=128, selected=32, repetitions=300, methods=result, note='One BLAS thread; mixed-position rows for computation timing only.')


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data', type=Path, required=True)
    p.add_argument('--neural', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repeats', type=int, default=64); a=p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    started=time.perf_counter(); tr=load(a.data/'train.npz'); va=load(a.data/'validation.npz')
    assert not set(tr['family']) & set(va['family'])
    config=dict(features='32 coordinates: 16 suit lengths plus 16 per-seat/per-suit honor-strength sums',
                honor_weights=dict(A=4., K=3., Q=2., J=1., T=.5, lower=0.),
                fixed_weights=[1., 1.], fit_parameters=2, repetitions=a.repeats,
                train_sha256=hashlib.sha256((a.data/'train.npz').read_bytes()).hexdigest(),
                validation_sha256=hashlib.sha256((a.data/'validation.npz').read_bytes()).hexdigest(),
                neural_sha256=hashlib.sha256(a.neural.read_bytes()).hexdigest(),
                primary='Family-balanced mean candidate-pool action regret. All variants specified before inspecting their validation results.',
                frozen_test='Untouched. Validation was previously used to select the neural checkpoint.')
    save(a.out/'config.json', config)
    fit=fit_weights(tr); save(a.out/'fit.json', fit); print(json.dumps(dict(stage='fitted', **fit)), flush=True)
    neural=Weights(a.neural); result=evaluate(va, neural, fit['coefficients'], a.repeats)
    save(a.out/'screen.json', result)
    bench=timing(va, neural, fit['coefficients']); save(a.out/'timing.json', bench)
    report=dict(config=config, fit=fit, validation={k:v for k,v in result.items() if k!='rows'}, timing=bench,
                seconds=time.perf_counter()-started,
                limitations=['Uniform mass over saved distinct layouts, not current belief probabilities.',
                             '32-to-8 or 64-to-16 finite-pool diagnostic, not weighted 128-to-32 live play.',
                             'Reference reuses candidate layouts; cannot demonstrate beating the full 128.',
                             'Multiple exploratory baselines; no production promotion.'])
    save(a.out/'result.json', report); print(json.dumps(report), flush=True)


if __name__ == '__main__': main()
