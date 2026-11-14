#!/usr/bin/env python3
"""Run x8_match arguments against STU_RUNTIME with the opt-in experiment player."""
import os
from pathlib import Path
import sys

RUNTIME = Path(os.environ['STU_RUNTIME']).resolve()
sys.path[:0] = [str(RUNTIME), str(RUNTIME / 'scripts')]
import x8_match
from engine import ExperimentalPlayer

original = x8_match.player
def player(spec, root, reference=None):
    if spec.get('rollout_experiment'):
        return ExperimentalPlayer(spec, root, reference)
    return original(spec, root, reference)

x8_match.player = player
if __name__ == '__main__':
    x8_match.gen8_match.main()
