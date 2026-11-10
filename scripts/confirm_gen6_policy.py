"""Score the fixed selected full-data policy on its 150 fresh reserved families.

Refuses to prepare any confirmation labels before the eight-epoch fit completes.
Recorded-choice IMP differences are diagnostic, not whole-game IMP/board gains.
"""
import argparse
from collections import defaultdict
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import time

for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[k] = '1'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', type=Path, required=True)
    a = ap.parse_args(); plan = json.loads(a.plan.read_text())
    root = Path(plan['output'])
    result_path = root / 'fit/result.json'
    if not result_path.exists():
        raise ValueError('Fit incomplete: confirmation remains unopened')
    result = json.loads(result_path.read_text())
    assert result['config']['epochs'] == 8 and result['test_evaluated'] is False
    sys.path.insert(0, plan['repository'])
    import numpy as np
    from bridge_harness.loop_registry import sha
    from bridge_harness.policy_v5 import V5Weights, scores
    from bridge_harness.selfplay import atomic_json
    from scripts.prepare_outcome_policy import extract
    from scripts.train_policy_choices import family_summary, choose
    selected = root / 'fit/best.npz'; parent = Path(plan['parent'])
    assert sha(selected) == result['selected_sha256']
    assert sha(parent) == result['config']['parent_sha256']
    out = root / 'confirmation'; out.mkdir(exist_ok=True)
    lock = (out / 'writer.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (out / 'result.json').exists():
        prior = json.loads((out / 'result.json').read_text())
        assert prior['selected_sha256'] == sha(selected)
        print(json.dumps(prior), flush=True); return
    entries = [e for e in json.loads((root / 'confirmation-families.json').read_text()) if not e['previously_inspected']]
    assert len(entries) == 150 and len({e['family'] for e in entries}) == 150
    raw = Path(plan['raw']); batch = out / 'raw'
    (batch / 'episodes').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw / 'manifest.json', batch / 'manifest.json')
    receipts = {e['index']: e for e in json.loads((raw / 'receipts.json').read_text())}
    for e in entries:
        source = raw / 'episodes' / f"{e['index']:06d}.json.gz"
        assert receipts[e['index']]['family'] == e['family']
        assert sha(source) == receipts[e['index']]['episode_sha256']
        target = batch / 'episodes' / source.name
        if not target.exists(): target.symlink_to(source.resolve())
    atomic_json(out / 'selection-lock.json', dict(selected_sha256=sha(selected),
        parent_sha256=sha(parent), fit_result_sha256=sha(result_path),
        families=entries, rule='One fixed candidate; no adaptation to confirmation'))
    data = out / 'data'
    if not (data / 'dataset.json').exists():
        if data.exists(): data.rename(out / ('interrupted-data-' + str(time.time_ns())))
        extract([batch], data, Path(plan['feature_parent']), Path(plan['legacy_comparator']))
    manifest = json.loads((data / 'dataset.json').read_text())
    models = [V5Weights(selected), V5Weights(parent)]
    errors = defaultdict(lambda: np.zeros(3))
    deltas, groups = [], []
    for e in manifest['shards']:
        assert e['split'] == 'test' and sha(data / e['file']) == e['sha256']
        with np.load(data / e['file'], allow_pickle=False) as z:
            d = {k: z[k] for k in z.files}
        for start in range(0, len(d['y']), 256):
            b = {k: v[start:start+256] for k, v in d.items()}
            if e['kind'] == 'outcomes':
                ix = np.arange(len(b['y']))
                sq = [(m.predict(b)[ix, b['chosen']] - b['y'])**2 for m in models]
                for f in np.unique(b['group']):
                    mask = b['group'] == f
                    errors[str(f)] += [sq[0][mask].sum(), sq[1][mask].sum(), mask.sum()]
            elif e['kind'] == 'pairs':
                pred = [scores(m.weights, b, 'gen3') for m in models]
                delta = (choose(pred[0][:, 0]-pred[0][:, 1])-choose(pred[1][:, 0]-pred[1][:, 1]))*b['y']
                deltas.extend(delta.tolist()); groups.extend(b['group'].tolist())
    names = sorted(errors); mat = np.array([errors[f][:2]/errors[f][2] for f in names])
    report = dict(selected_sha256=sha(selected), parent_sha256=sha(parent), reserved_families=150,
        evaluated_outcome_families=len(names), candidate_mse=float(mat[:, 0].mean()),
        parent_mse=float(mat[:, 1].mean()), paired_mse=family_summary(mat[:, 0]-mat[:, 1], names),
        recorded_choice_imp_difference=family_summary(deltas, groups),
        test_evaluated=True, whole_game_strength_tested=False, promoted=False,
        limitation='Recorded-choice diagnostic uses mixed frozen continuations; not whole-game IMP/board evidence.')
    atomic_json(out / 'outcome-errors-by-family.json', {k: v.tolist() for k, v in errors.items()})
    atomic_json(out / 'result.json', report)
    print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    main()
