#!/usr/bin/env python3
"""The trainer's per-epoch held-out scores, for any saved nets on any built set.

  python scripts/gen7_score_nets.py SET.npz [--bot N] NAME=POLICY.npz [NAME=POLICY.npz ...]

One JSON line per net: the same figures scripts/train_gen7_policy.py prints after an epoch (log-loss on
the card played, exact card, an equal-best card first, tricks given up by the policy head's card and by
the gap head's card, by Gen 6's estimates), over all rows and by phase. --bot keeps the rows of one
deciding bot (the set's meta column: 0 = 6-32, 1 = 6-256, 2 = any other, which is 7s-32 in Gen 7 runs).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.gen7_net import INPUTS, forward, log_softmax
from train_gen7_policy import evaluate

args = sys.argv[1:]
bot = None
if '--bot' in args:
    i = args.index('--bot')
    bot = int(args[i + 1])
    del args[i:i + 2]
with np.load(args[0]) as z:
    data = {k: z[k] for k in (*INPUTS, 'gap', 'meta', 'deal')}
index = np.arange(len(data['deal'])) if bot is None else np.flatnonzero(data['meta'][:, 4] == bot)
print(json.dumps(dict(set=Path(args[0]).name, bot=bot, rows=len(index), deals=len(np.unique(data['deal'][index])))), flush=True)
for spec in args[1:]:
    name, path = spec.split('=', 1)
    with np.load(path) as f:
        params = {k: f[k] for k in f.files}
    def predict(b):
        out = forward(params, b)
        return log_softmax(out['policy']), out['gap']
    r = evaluate(predict, data, index)
    print(json.dumps(dict(net=name, all=r['all'], by_phase=r['by_phase'], root_tables=r['root_tables'])), flush=True)
