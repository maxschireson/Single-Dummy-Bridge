#!/usr/bin/env python3
"""Build isolated actors from the frozen blind R4c full-bot definition."""
import argparse
import copy
import json
import hashlib
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--bots', type=Path, required=True)
ap.add_argument('--base', default='stu4c-put')
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
base = json.loads(args.bots.read_text())[args.base]
assert base['x8'].get('blind') is True, 'This experiment requires the blind table actor, not named self-play.'
assert base['x8']['names'] == {'self': 'stup0', '*': '', 'they_see': ''}
bots = {}
for name in ('control', 'reader', 'guarantee', 'flat32', 'recursive32', 'selective32'):
    spec = copy.deepcopy(base)
    # Identical diagnostic capture for every arm; no training or arena registration.
    spec['x8']['capture'] = dict(level=2, layouts=128, forks=0, audit='features')
    implementation = hashlib.sha256(Path(__file__).with_name('engine.py').read_bytes()).hexdigest()
    spec['rollout_experiment'] = dict(version=2, implementation_sha256=implementation, isolate_claims=True)
    if name == 'reader':
        spec['rollout_experiment']['reader_identity'] = True
    if name == 'guarantee':
        spec['x8']['claims']['opponents'] = ['*']
    if name.endswith('32'):
        for stage in [*spec['x8']['stages'], spec['x8']['lead']]:
            stage.update(layouts=32, first=32)
    if name in ('recursive32', 'selective32'):
        spec['rollout_experiment'].update(recursive='uniform' if name == 'recursive32' else 'selective',
                                         inner_layouts=8, max_calls=4, window_plies=8, logp_margin=1.0)
    bots['rx2-' + name] = spec
args.out.write_text(json.dumps(bots, indent=2) + '\n')
