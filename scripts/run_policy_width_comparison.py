"""Run the two pinned policy-width fits and compare validation by deal family."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np


def write(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    root = Path(plan['output'])
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'writer.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for spec in plan['verified_files']:
        assert hashlib.sha256(Path(spec['path']).read_bytes()).hexdigest() == spec['sha256'], spec['path']

    def fit(arm):
        out = root / arm['name']
        result = out / 'result.json'
        if result.exists():
            return json.loads(result.read_text())
        if out.exists() and not (out / 'training.json').exists():
            out.rename(root / (arm['name'] + '-interrupted-' + str(time.time_ns())))
        cmd = [plan['python'], '-u', str(Path(plan['repository']) / 'scripts/train_clean_policy_v5.py'),
               '--data', plan['data'], '--out', str(out), '--parent', plan['parent'],
               '--rank-candidate', plan['comparison_checkpoint'],
               '--previous-families', plan['previous_families'], '--epochs', str(plan['epochs']),
               '--mode', 'attention', '--attention-width', str(arm['width']),
               '--validation-only', '--comparison-checkpoint', plan['comparison_checkpoint']]
        write(root / (arm['name'] + '-command.json'), dict(command=cmd, started=time.time()))
        with (root / (arm['name'] + '.log')).open('a') as log:
            subprocess.run(cmd, cwd=plan['repository'], stdout=log, stderr=subprocess.STDOUT, check=True)
        data = json.loads(result.read_text())
        assert data['parameters'] == arm['parameters']
        assert data['test_evaluated'] is False
        return data

    write(root / 'status.json', dict(stage='running', arms=plan['arms'], started=time.time()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(fit, plan['arms']))
    family = []
    for arm in plan['arms']:
        family.append(json.loads((root / arm['name'] / 'validation-outcomes-by-family.json').read_text()))
    assert family[0].keys() == family[1].keys()
    names = sorted(family[0])
    diff = np.array([family[0][k][0] / family[0][k][4] - family[1][k][0] / family[1][k][4] for k in names])
    mean = float(diff.mean())
    se = float(diff.std(ddof=1) / np.sqrt(len(diff)))
    report = dict(stage='complete', completed=time.time(), families=len(names),
                  paired_validation_mse_small_minus_large=dict(mean=mean, se=se, ci95=[mean-1.96*se, mean+1.96*se]),
                  arms=[dict(name=a['name'], width=a['width'], parameters=r['parameters'],
                             selected_epoch=r['selected_epoch'], selected_sha256=r['selected_sha256'],
                             validation=r['validation'], numpy_max_error=r['numpy_max_error'])
                        for a,r in zip(plan['arms'],results)],
                  test_evaluated=False, promoted=False,
                  interpretation='Single-seed validation screen; lower MSE is better. Independent confirmation is required before promotion.')
    write(root / 'comparison.json', report)
    write(root / 'status.json', dict(stage='complete', completed=time.time()))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
