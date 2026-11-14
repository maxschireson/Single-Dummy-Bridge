#!/usr/bin/env python3
"""P10 post-run comparison: score several rollout nets on the same held-out rows, by bot and by phase.

    eval_nets.py --data freshB.npz --net NAME=path/policy.npz [--net ...] [--rows N] [--out report.json]

Uses scripts/train_rollout_net.py's own `evaluate` (log-loss, agreement, regret against the rollouts' or search's
gaps, by phase, by bot, by bot and phase) with the fp32 NumPy forward pass, so the numbers are the trainer's held-out
numbers, computed the same way for every net on the same rows. Each net reads the rows' bot ids through its own
vocabulary (as the trainer's --compare does). Also records each net's parameter count and its NumPy forward cost
(rows a second, one thread, 512 rows a call) as the inference side of the compute comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.gen7_net import BANK_KEYS, INPUTS, forward  # noqa: E402
import train_rollout_net as T  # noqa: E402


def sha(path, n=16):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:n]


def load_net(path):
    with np.load(path) as z:
        p = {k: z[k] for k in z.files}
    vocab = [str(x) for x in p.pop('bot_vocab')] if 'bot_vocab' in p else []
    for k in BANK_KEYS:
        p.pop(k, None)
    kind = int(np.asarray(p['kind']))
    params = sum(int(np.prod(v.shape)) for k, v in p.items() if k != 'kind')
    return p, vocab, kind, params


def log_softmax(x):
    x = x - x.max(axis=1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=1, keepdims=True))


def speed(p, data, index, rows=512, reps=6):
    b = {k: np.asarray(data[k][index[:rows]]) for k in INPUTS}
    b['bot_own'] = b['bot_other'] = np.zeros(len(index[:rows]), np.int32)
    forward(p, b)
    t = time.perf_counter()
    for _ in range(reps):
        forward(p, b)
    return round(reps * len(index[:rows]) / (time.perf_counter() - t))


def deal_sums(predict, data, index, batch=4096):
    """Per deal: sum and count of regret on rated searched rows (as `evaluate` scores it), sum and count of log-loss."""
    deal = np.asarray(data['deal'])[index]
    deals, inv = np.unique(deal, return_inverse=True)
    reg_s, reg_n, nll_s, nll_n = (np.zeros(len(deals)) for _ in range(4))
    for i in range(0, len(index), batch):
        rows = index[i:i + batch]
        logp = np.asarray(predict(T.with_ids({k: data[k][rows] for k in INPUTS}, data['meta'][rows]))[0])
        meta, legal = data['meta'][rows], np.asarray(data['legal'][rows]).astype(bool)
        gap = np.asarray(data['gap'][rows]).astype(np.float32)
        r = np.arange(len(rows))
        pick = logp.argmax(1)
        rated = legal & (gap >= 0)
        ok = rated[r, pick] & (meta[:, 10] == 1)
        j = inv[i:i + batch]
        np.add.at(reg_s, j[ok], gap[r, pick][ok])
        np.add.at(reg_n, j[ok], 1)
        np.add.at(nll_s, j, -logp[r, meta[:, 0]])
        np.add.at(nll_n, j, 1)
    return dict(reg_s=reg_s, reg_n=reg_n, nll_s=nll_s, nll_n=nll_n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--net', action='append', required=True, help='NAME=path/policy.npz')
    ap.add_argument('--rows', type=int, default=0, help='score only the first N rows (0: all)')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--per-deal', type=Path, help='also save per-deal sums (regret on rated searched rows, log-loss) for paired SEs')
    a = ap.parse_args()
    data = dict(T.stored_arrays(a.data))
    names = [str(x) for x in data['bot_names']] if 'bot_names' in data else None
    n = len(data['meta'])
    index = np.arange(n if not a.rows else min(n, a.rows))
    report = dict(data=str(a.data), data_sha256=sha(a.data), rows=int(len(index)), nets={})
    per_deal = {}
    for spec in a.net:
        name, _, path = spec.partition('=')
        p, vocab, kind, params = load_net(path)
        d = dict(data)
        if vocab and names is not None:
            d['meta'] = T.match_bots(np.asarray(data['meta']), names, vocab)
            d['bot_names'] = np.array(vocab)
        predict = lambda b, p=p, kind=kind: (lambda o: (log_softmax(np.asarray(o['policy'])), np.asarray(o['gap'])))(forward(p, b, np, kind))
        t = time.perf_counter()
        v = T.evaluate(predict, d, index)
        if a.per_deal:
            per_deal[name] = deal_sums(predict, d, index)
        report['nets'][name] = dict(path=path, sha256=sha(path), parameters=params, kind=kind,
                                    width=int(p['wt0'].shape[1]) if 'wt0' in p else None,
                                    eval_seconds=round(time.perf_counter() - t, 1),
                                    rows_per_s_fp32=speed(p, d, index), scores=v)
        s = v['all']
        print(f"{name:24s} params {params/1e6:5.2f}M  nll {s['nll']}  agree {s['agree']}  regret {s['regret']}  "
              f"phases {[v['by_phase'][k]['regret'] for k in v['by_phase']]}", flush=True)
    if a.out:
        a.out.write_text(json.dumps(report, indent=1))
    if a.per_deal:
        np.savez(a.per_deal, deals=np.unique(np.asarray(data['deal'])[index]),
                 **{f'{k}__{m}': v[m] for k, v in per_deal.items() for m in v})


if __name__ == '__main__':
    main()
