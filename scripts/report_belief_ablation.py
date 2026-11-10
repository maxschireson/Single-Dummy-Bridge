"""Development-only parent/schedule comparisons with separate uncertainty sources."""
import argparse
import json
from pathlib import Path

import numpy as np


def report(root):
    main = root.parents[1]
    cells = {}
    for parent, schedule, prefix, base in (
        ('v5', 'gentle', 'dense_added', main / 'fits'),
        ('v3', 'aggressive', 'dense_v3', main / 'fits'),
        ('v5', 'aggressive', 'v5_aggressive', root / 'fits'),
        ('v3', 'gentle', 'v3_gentle', root / 'fits'),
    ):
        cell = cells[parent + '_' + schedule] = {}
        for p in base.glob(prefix + '*/result.json'):
            joint = p.parent / 'joint.json'
            if not joint.exists():
                continue
            result = json.loads(p.read_text())
            cell[result['config']['seed']] = json.loads(joint.read_text())
    rows = []
    for left, right in (
        ('v3_aggressive', 'v5_gentle'),
        ('v5_aggressive', 'v5_gentle'),
        ('v3_aggressive', 'v5_aggressive'),
        ('v3_gentle', 'v5_gentle'),
        ('v3_aggressive', 'v3_gentle'),
    ):
        seeds = sorted(cells[left].keys() & cells[right].keys())
        if not seeds:
            continue
        diffs = []
        for seed in seeds:
            a, b = cells[left][seed]['groups'], cells[right][seed]['groups']
            diffs.append({k: a[k][0] / a[k][1] - b[k][0] / b[k][1]
                          for k in a.keys() & b.keys() if a[k][1] and b[k][1]})
        families = sorted(set.intersection(*(set(d) for d in diffs)))
        values = np.array([[d[k] for k in families] for d in diffs])
        per_seed = values.mean(axis=1)
        family_average = values.mean(axis=0)
        sd = float(per_seed.std(ddof=1)) if len(seeds) > 1 else None
        rows.append(dict(left=left, right=right, seeds=seeds, families=len(families),
                         loss_delta=float(per_seed.mean()),
                         family_se=float(family_average.std(ddof=1) / np.sqrt(len(families))),
                         seed_sd=sd, seed_se=sd / np.sqrt(len(seeds)) if sd is not None else None,
                         per_seed_loss_delta=per_seed.tolist()))
    result = dict(comparisons=rows, interpretation='Development only. Negative delta favors left. '
                  'Family SE conditions on fitted models; seed dispersion is separate. Reused deals '
                  'are not independent dataset replications. Learning rate and epoch count remain bundled. '
                  'Original confirmation selection is unchanged; no held-out results used.')
    (root / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Warm-start and schedule development comparison', '', result['interpretation'], '',
             '| Left minus right | Matched seeds | Families | NLL delta | Family SE | Seed SD |',
             '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        sd = 'pending' if r['seed_sd'] is None else f"{r['seed_sd']:.9f}"
        lines.append(f"| {r['left']} − {r['right']} | {len(r['seeds'])} | {r['families']} | "
                     f"{r['loss_delta']:.9f} | {r['family_se']:.9f} | {sd} |")
    (root / 'progress.md').write_text('\n'.join(lines) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    print(json.dumps(report(parser.parse_args().run.resolve()), indent=2))
