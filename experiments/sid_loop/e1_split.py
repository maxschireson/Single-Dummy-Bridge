"""E1's declaring-side heads split by whether some card guarantees the target outright.

  python e1_split.py --data freshB.npz --net s0/policy.npz [--out split.json]

The training labels (scripts/sid_label.py without --full) leave `cert` and `single` unasked for the cards that do
not guarantee a target when another card does; the held-out labels E1 scores (with --full) ask them. So E1's `cert`
and `single` entries on declaring rows come from two populations: positions where no card guarantees the target
(the only kind the heads were trained on for those cards) and positions where some card does (cards the heads never
saw labelled there). This prints log-loss, base-rate log-loss, Brier score and a calibration table for each head and
target on each population, and the same for `guar`, which is labelled alike in both sets.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.gen7_net import BANK_KEYS, INPUTS, SID_HEADS, forward          # noqa: E402
from train_rollout_net import SID_KINDS, SID_SLOTS, match_bots, sid_labels           # noqa: E402

TARGET = ('one down', 'contract', 'overtrick')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--net', type=Path, required=True)
    p.add_argument('--out', type=Path)
    p.add_argument('--chunk', type=int, default=4096)
    a = p.parse_args()
    with np.load(a.data) as z:
        d = {k: z[k] for k in (*INPUTS, 'meta', 'sid', 'bot_names')}
    sid = d['sid'].reshape(len(d['sid']), len(SID_KINDS), SID_SLOTS, 3)
    rows = np.flatnonzero((sid >= 0).any(axis=(1, 2, 3)) & (d['meta'][:, 6] < 2))       # labelled rows of the declaring side
    meta, legal = d['meta'][rows], d['legal'][rows].astype(bool)
    lab = {k[4:]: v for k, v in sid_labels(d['sid'][rows], legal).items()}
    with np.load(a.net) as w:
        params = {k: w[k] for k in w.files if k not in BANK_KEYS + ('bot_vocab',)}
        vocab = [str(x) for x in w['bot_vocab']] if 'bot_vocab' in w.files else None
    m2 = match_bots(meta, d['bot_names'], vocab) if vocab else meta
    prob = {k: [] for k in SID_HEADS}
    for i in range(0, len(rows), a.chunk):
        b = {k: d[k][rows[i:i + a.chunk]] for k in INPUTS}
        if vocab:
            b['bot_own'], b['bot_other'] = m2[i:i + a.chunk, 8].astype(np.int32), m2[i:i + a.chunk, 9].astype(np.int32)
        f = forward(params, b)
        for k in SID_HEADS:
            prob[k].append((1. / (1. + np.exp(-np.clip(f[k], -40, 40)))).astype(np.float32))
    prob = {k: np.concatenate(v) for k, v in prob.items()}
    out, text = {}, [f'{len(rows)} labelled declaring rows; per head and target: population, entries, share 1, log-loss, base, Brier; calibration']
    for t in range(3):
        claim = ((lab['guar'][:, :, t] == 1) & legal).any(axis=1)                       # some card guarantees the target
        for k in SID_HEADS:
            for pname, pmask in (('no card guarantees it', ~claim), ('some card guarantees it', claim)):
                y = lab[k][pmask][:, :, t]
                q = np.clip(prob[k][pmask][:, :, t].astype(np.float64), 1e-7, 1 - 1e-7)
                mk = y >= 0
                if not mk.any():
                    continue
                yy, qq = y[mk], q[mk]
                rate = float(yy.mean())
                r_ = min(max(rate, 1e-7), 1 - 1e-7)
                e = dict(n=int(mk.sum()), rate=round(rate, 4),
                         nll=round(float(-np.where(yy == 1, np.log(qq), np.log(1 - qq)).mean()), 4),
                         base_nll=round(float(-(r_ * np.log(r_) + (1 - r_) * np.log(1 - r_))), 4),
                         brier=round(float(((qq - yy) ** 2).mean()), 4))
                band = np.minimum((qq * 10).astype(int), 9)
                e['calibration'] = [[bnd / 10, int((band == bnd).sum()), round(float(qq[band == bnd].mean()), 3), round(float(yy[band == bnd].mean()), 3)]
                                    for bnd in range(10) if (band == bnd).any()]
                out[f'{k}|{TARGET[t]}|{pname}'] = e
                text.append(f'{k:<6} {TARGET[t]:<10} {pname:<24} {e["n"]:>8} {e["rate"]:>6.3f} {e["nll"]:>7.4f} {e["base_nll"]:>7.4f} {e["brier"]:>7.4f}  '
                            + ' '.join(f'{c[0]:.1f}:{c[2]:.2f}/{c[3]:.2f}' for c in e['calibration']))
    print('\n'.join(text))
    if a.out:
        a.out.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
