"""Real R4c/BF16/native-SURE acceptance; synthetic views, no strength estimate."""
import argparse
import copy
import json
import random
import sys
from pathlib import Path

import match
from accounting import isolated_finder
from engine import ExperimentalPlayer
from bridge_harness import x8_player as xp

sys.path.insert(0, str(match.RUNTIME / 'tests'))
from test_x8 import spot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--bots', required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    m = match.gm.build_manifest(args.source, args.bots, 'rx2-flat32~rx2-control', 2026111401)
    spec = m['bots']['rx2-flat32']
    checks = []
    for seed, plies in [(2026111401, 16), (2026111402, 28), (2026111403, 40), (2026111404, 24)]:
        game, o, _ = spot(seed, plies)
        outcomes = []
        for mode in ('base', 'null', 'zero'):
            s = copy.deepcopy(spec)
            if mode == 'zero':
                s['rollout_experiment'].update(recursive='uniform', max_calls=0)
            p = xp.X8Player(s, args.source) if mode == 'base' else ExperimentalPlayer(s, args.source)
            if mode == 'base' and p.finder:
                # Same cold per-actor solver boundary as the corrected runner.
                p.finder = isolated_finder(p.finder.binary, p.x8.claims.each_ms / 1000)
            p.meet('rx2-control')
            try:
                assert p.net.precision == 'bf16', p.net.precision
                rng = random.Random(seed)
                result = p.choose(o, rng)
                outcomes.append((result.card, result.details.get('x8', {}).get('value'), rng.getstate()))
                if mode != 'base':
                    work = result.details['experiment_work']
                    assert work['solver_cpu_seconds'] >= 0 and work['wall_seconds'] > 0, work
            finally:
                if mode == 'base' and p.finder:
                    p.finder.close()
                p.close()
        assert outcomes[0] == outcomes[1] == outcomes[2], (seed, plies, [x[:2] for x in outcomes])
        checks.append(dict(seed=seed, plies=plies, null_zero_parity=True, card=outcomes[0][0]))
        print(json.dumps(checks[-1]), flush=True)
    child_calls = 0
    for seed in range(2026111401, 2026111405):
        _, o, _ = spot(seed, 24)
        s = copy.deepcopy(spec)
        s['rollout_experiment'].update(recursive='uniform', max_calls=1, inner_layouts=8, window_plies=8)
        p = ExperimentalPlayer(s, args.source)
        p.meet('rx2-control')
        try:
            result = p.choose(o, random.Random(seed))
            assert result.card in o.legal
            assert result.details['recursive']['calls'] <= 1
            child_calls += result.details['recursive']['calls']
            if p.child is not None:
                assert p.child.finder is not p.finder
                assert p.child.net.precision == 'bf16'
                assert not p.child.experiment.get('recursive')
                assert result.details['experiment_work']['solver_cpu_seconds'] >= 0
        finally:
            p.close()
        if child_calls:
            break
    assert child_calls, 'No real child search exercised'
    report = dict(status='passed', parity=checks, child_calls=child_calls,
                  precision='bf16', manifest_identity=m['identity'],
                  purpose='correctness only; generated-view seeds above also excluded from training')
    with args.out.open('x') as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
