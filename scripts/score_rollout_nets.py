#!/usr/bin/env python3
"""Score policy and rollout nets on one held-out set (made by scripts/gen7_build_dataset.py with its bot columns).

  python scripts/score_rollout_nets.py --data held.npz --net v41=PATH --net v2=PATH [--net ...] [--out scores.json]

Every net sees the same rows. A rollout net (one with `bot_vocab`) gets each row's bots by name, matched to its own
numbering (bots it was not trained on read as unknown), and is scored a second time with both ids blank. Scores are
scripts/train_rollout_net.py's (all rows, from trick 7, by phase, side and bot; regret scores on rows with the
search's gap only) plus the temperature that minimizes the log-loss. NumPy only: no JAX needed.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.gen7_net import BANK_KEYS, INPUTS, forward, log_softmax  # noqa: E402

spec = importlib.util.spec_from_file_location('train_rollout_net', ROOT / 'scripts' / 'train_rollout_net.py')
trn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trn)


def predictor(params):
    def predict(b):
        out = forward(params, b)
        return log_softmax(out['policy']), out['gap']
    return predict


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--net', action='append', required=True, help='name=path')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    with np.load(a.data) as z:
        data = {k: np.array(z[k]) for k in (*INPUTS, 'gap', 'meta', 'deal')}
        names = [str(x) for x in z['bot_names']]
    index = np.arange(len(data['deal']))
    print(f'{len(index)} rows, {len(np.unique(data["deal"]))} deals, bots {names[1:]}', file=sys.stderr, flush=True)
    out = {}
    for item in a.net:
        name, path = item.split('=', 1)
        with np.load(path) as w:
            params = {k: w[k] for k in w.files if k not in BANK_KEYS}
        vocab = [str(x) for x in params.pop('bot_vocab')] if 'bot_vocab' in params else None
        d = dict(data, meta=trn.match_bots(data['meta'], names, vocab) if vocab else data['meta'], bot_names=np.array(names))
        if vocab:          # by_bot keys stay the set's names: renumbered rows are labelled through the net's vocabulary
            d['bot_names'] = np.array(vocab)
        pr = predictor(params)
        row = dict(scores=trn.evaluate(pr, d, index), temperature=trn.temperature(pr, d, index))
        if vocab:
            row['ids_blank'] = trn.evaluate(pr, d, index, blank=True)['all']
        out[name] = row
        s = row['scores']
        print(f"{name:12s} log-loss {s['all']['nll']:.4f}  exact {s['all']['agree']:.4f}  tricks given up {s['all']['regret']:.4f}  "
              f"from trick 7 {s['from_trick_7']['nll']:.4f}/{s['from_trick_7']['regret']:.4f}  T {row['temperature']['t']}"
              + (f"  ids blank {row['ids_blank']['nll']:.4f}" if vocab else ''), flush=True)
    if a.out:
        a.out.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
