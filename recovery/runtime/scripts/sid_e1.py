#!/usr/bin/env python3
"""E1 of experiments/sid_loop/SPEC.md: a student net against the exact line finder, offline, on held-out boards.

  python scripts/sid_e1.py --data freshB.npz --net s0/policy.npz [--net other.npz ...] --out DIR [--limit N]

--data is a set built by scripts/gen7_build_dataset.py with --labels and --label-floors from labels made with
scripts/sid_label.py --full (every card labelled, also where another card guarantees the target). Prediction only:
nothing is played, and the deals must be ones no net here was trained on.

For each net with the label heads (bridge_harness.gen7_net.forward: guar, cert, single):

1. Heads. Per head, role (declaring side / defender), cards held and target: entries, the share that are 1, the
   head's log-loss and Brier score, and the log-loss of predicting that share for every entry. A calibration table
   for the contract target (ten bands of predicted probability: entries, mean prediction, share that are 1).
2. Declaring decisions (rows where every legal card has an exact floor), per target and cards held: the mean exact
   floor of the best card; the shortfall from it of the card the student ranks first on `cert` (mean, and the share
   of decisions above 0.05), and of other choosers on the same decisions: first on `single`, first on `guar`, the
   net's policy head, the card played, a card drawn at random. And on the decisions whose two best cards differ by
   more than 0.05 in exact floor: how often each chooser takes the best card.
3. Defender decisions at the contract where some card hands declarer a guaranteed line and some card does not:
   how often the card with the lowest predicted `guar` does not hand it over, against the policy head's card, the
   card played and a random card.

Cards of one run of touching cards carry the same labels, so a chooser is scored by the labels of the card it names.
A net without the label heads (rollout net v2) is scored on the policy rows only. Errors are standard errors with
the deal as the unit.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.gen7_net import BANK_KEYS, INPUTS, SID_HEADS, forward, log_softmax         # noqa: E402
from train_rollout_net import SID_KINDS, SID_SLOTS, match_bots, sid_labels                       # noqa: E402

TARGET = ('one down', 'contract', 'overtrick')


def sigmoid(x):
    return 1. / (1. + np.exp(-np.clip(x, -40, 40)))


def by_deal(values, deal):
    """Mean of per-row values and its standard error with the deal as the unit."""
    values = np.asarray(values, np.float64)
    if not len(values):
        return None, None, 0
    u, inv = np.unique(deal, return_inverse=True)
    s = np.bincount(inv, weights=values, minlength=len(u))
    n = np.bincount(inv, minlength=len(u)).astype(np.float64)
    mean = s.sum() / n.sum()
    if len(u) < 2:
        return float(mean), None, len(values)
    resid = s - mean * n
    se = np.sqrt(len(u) / (len(u) - 1) * (resid ** 2).sum()) / n.sum()
    return float(mean), float(se), len(values)


def fmt(m, digits=4):
    mean, se, n = m
    if mean is None:
        return dict(n=0)
    return dict(n=int(n), mean=round(mean, digits), se=None if se is None else round(se, digits))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--net', type=Path, action='append', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--limit', type=int, default=0, help='at most this many rows (a test)')
    p.add_argument('--chunk', type=int, default=4096)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with np.load(a.data) as z:
        d = {k: z[k] for k in (*INPUTS, 'meta', 'deal', 'sid', 'sid_floor', 'sid_ceil', 'bot_names', 'family')}
    sid = d['sid'].reshape(len(d['sid']), len(SID_KINDS), SID_SLOTS, 3)
    rows = np.flatnonzero((sid >= 0).any(axis=(1, 2, 3)))
    if a.limit:
        rows = rows[:a.limit]
    meta, deal, legal = d['meta'][rows], d['deal'][rows], d['legal'][rows].astype(bool)
    lab = {k[4:]: v for k, v in sid_labels(d['sid'][rows], legal).items()}                 # [n, 52, 3]
    n = len(rows)
    slot = np.cumsum(legal, axis=1) - 1
    floor = np.where(legal[:, :, None], np.take_along_axis(d['sid_floor'][rows].astype(np.float32), np.clip(slot, 0, SID_SLOTS - 1)[:, :, None], axis=1), np.nan)
    role = meta[:, 6]
    declaring = role < 2
    state = d['state'][rows]
    held = np.where(role == 1, (state == 2).sum(axis=1), (state == 1).sum(axis=1))
    played = meta[:, 0]
    rng = np.random.default_rng(0)
    random_card = np.array([rng.choice(np.flatnonzero(l)) for l in legal])
    report = dict(data=str(a.data), deals=int(len(np.unique(deal))), rows=int(n), rows_declaring=int(declaring.sum()),
                  evidence='prediction against exact solver labels; nothing played', nets={})
    text = [f'E1: {n} labelled rows on {report["deals"]} held-out deals ({int(declaring.sum())} declaring, {int((~declaring).sum())} defending)']
    for path in a.net:
        with np.load(path) as w:
            params = {k: w[k] for k in w.files if k not in BANK_KEYS + ('bot_vocab',)}
            vocab = [str(x) for x in w['bot_vocab']] if 'bot_vocab' in w.files else None
        m2 = match_bots(meta, d['bot_names'], vocab) if vocab else meta
        out = {k: [] for k in ('policy', *SID_HEADS)}
        has = 'wd1s' in params
        for i in range(0, n, a.chunk):
            b = {k: d[k][rows[i:i + a.chunk]] for k in INPUTS}
            if vocab:
                b['bot_own'], b['bot_other'] = m2[i:i + a.chunk, 8].astype(np.int32), m2[i:i + a.chunk, 9].astype(np.int32)
            f = forward(params, b)
            out['policy'].append(log_softmax(f['policy']))
            if has:
                for k in SID_HEADS:
                    out[k].append(sigmoid(f[k]).astype(np.float32))
        logp = np.concatenate(out['policy'])
        prob = {k: np.concatenate(out[k]) for k in SID_HEADS} if has else {}
        R = dict(label_heads=has)
        text.append(f'\n== {path}' + ('' if has else '  (no label heads: policy rows only)'))
        R['policy_nll_played'] = fmt(by_deal(-logp[np.arange(n), played], deal))

        # 1. the heads
        if has:
            heads = {}
            text.append('head    role       cards target      entries  share 1  log-loss  base     Brier')
            for k in SID_HEADS:
                for rname, rmask in (('declaring', declaring), ('defender', ~declaring)):
                    if k == 'single' and rname == 'defender':
                        continue
                    for hname, hmask in (('all', np.ones(n, bool)), ('7', held == 7), ('6', held == 6), ('5 or fewer', held <= 5)):
                        for t in range(3):
                            sel = rmask & hmask
                            y, q = lab[k][sel][:, :, t], np.clip(prob[k][sel][:, :, t].astype(np.float64), 1e-7, 1 - 1e-7)
                            m = y >= 0
                            cnt = int(m.sum())
                            if not cnt:
                                continue
                            rate = float(y[m].mean())
                            r_ = min(max(rate, 1e-7), 1 - 1e-7)
                            nll = float(-np.where(y[m] == 1, np.log(q[m]), np.log(1 - q[m])).mean())
                            e = dict(n=cnt, rate=round(rate, 4), nll=round(nll, 4), base_nll=round(float(-(r_ * np.log(r_) + (1 - r_) * np.log(1 - r_))), 4),
                                     brier=round(float(((q[m] - y[m]) ** 2).mean()), 4))
                            heads[f'{k}|{rname}|{hname}|{TARGET[t]}'] = e
                            text.append(f'{k:<7} {rname:<10} {hname:<5.5} {TARGET[t]:<10} {cnt:>8} {rate:>8.3f} {nll:>9.4f} {e["base_nll"]:>8.4f} {e["brier"]:>7.4f}')
            R['heads'] = heads
            cal = {}
            text.append('calibration, contract target: predicted band, entries, mean predicted, share 1')
            for k in SID_HEADS:
                for rname, rmask in (('declaring', declaring), ('defender', ~declaring)):
                    if k == 'single' and rname == 'defender':
                        continue
                    y, q = lab[k][rmask][:, :, 1], prob[k][rmask][:, :, 1]
                    m = y >= 0
                    band = np.minimum((q[m] * 10).astype(int), 9)
                    rows_ = []
                    for bnd in range(10):
                        mm = band == bnd
                        if mm.any():
                            rows_.append([bnd / 10, int(mm.sum()), round(float(q[m][mm].mean()), 4), round(float(y[m][mm].mean()), 4)])
                    cal[f'{k}|{rname}'] = rows_
                    text.append(f'  {k} {rname}: ' + '  '.join(f'{r[0]:.1f}:{r[1]}/{r[2]:.2f}/{r[3]:.2f}' for r in rows_))
            R['calibration_contract'] = cal

        # 2. declaring decisions: the exact floor of the card each chooser names
        choosers = {}
        if has:
            for k in SID_HEADS:
                choosers[k] = lambda t, k=k: np.where(legal, prob[k][:, :, t], -1.).argmax(axis=1)
        choosers['policy'] = lambda t: logp.argmax(axis=1)
        choosers['played'] = lambda t: played
        choosers['random'] = lambda t: random_card
        dec = {}
        text.append('declaring decisions: shortfall in exact floor from the best card (mean +- se by deal; share above 0.05), and on')
        text.append('decisions whose two best cards differ by more than 0.05: share where the chooser names the best card')
        text.append('target     cards  decisions  best floor | chooser: shortfall, >0.05 | ... || apart: decisions | chooser: best card named')
        for t in range(3):
            fl = floor[:, :, t]
            full = declaring & ~(np.isnan(fl) & legal).any(axis=1) & (legal.sum(axis=1) > 1)
            fl0 = np.where(legal, np.nan_to_num(fl, nan=-1.), -1.)
            best = fl0.max(axis=1)
            is_best = fl0 >= best[:, None] - 1e-6
            second = np.where(is_best, -1., fl0).max(axis=1)              # the best floor among cards that are not at the best
            apart = full & (second >= 0) & (best - second > .05)
            for hname, hmask in (('all', np.ones(n, bool)), ('7', held == 7), ('6', held == 6), ('5 or fewer', held <= 5)):
                sel = full & hmask
                if not sel.any():
                    continue
                e = dict(decisions=int(sel.sum()), best_floor=fmt(by_deal(best[sel], deal[sel])), apart=int((apart & hmask).sum()), choosers={})
                line = f'{TARGET[t]:<10} {hname:<5.5} {int(sel.sum()):>9}  {e["best_floor"]["mean"]:.4f}    |'
                line2 = f' || {int((apart & hmask).sum())} |'
                for cname, pick in choosers.items():
                    c = pick(t)
                    got = fl0[np.arange(n), c]
                    short = best - got
                    ce = dict(shortfall=fmt(by_deal(short[sel], deal[sel])), above_005=fmt(by_deal((short[sel] > .05).astype(float), deal[sel])))
                    if (apart & hmask).any():
                        ce['best_named_when_apart'] = fmt(by_deal(is_best[np.arange(n), c][apart & hmask].astype(float), deal[apart & hmask]))
                    e['choosers'][cname] = ce
                    line += f' {cname}: {ce["shortfall"]["mean"]:.4f}+-{ce["shortfall"]["se"] or 0:.4f}, {ce["above_005"]["mean"]:.3f} |'
                    if 'best_named_when_apart' in ce:
                        line2 += f' {cname}: {ce["best_named_when_apart"]["mean"]:.3f}+-{ce["best_named_when_apart"]["se"] or 0:.3f} |'
                dec[f'{TARGET[t]}|{hname}'] = e
                text.append(line + line2)
        R['declaring_decisions'] = dec

        # 3. defender decisions at the contract where the hand-over can be avoided and can be made
        g = lab['guar'][:, :, 1]
        some0, some1 = ((g == 0) & legal).any(axis=1), ((g == 1) & legal).any(axis=1)
        known = ~((g < 0) & legal).any(axis=1)
        mixed = ~declaring & known & some0 & some1
        dfd = {}
        text.append('defender decisions at the contract where some card hands declarer a guaranteed line and some card does not:')
        text.append('cards  decisions | chooser: share that does not hand it over')
        dchoosers = dict(policy=logp.argmax(axis=1), played=played, random=random_card)
        if has:
            dchoosers = dict(guar=np.where(legal, prob['guar'][:, :, 1], 2.).argmin(axis=1), cert=np.where(legal, prob['cert'][:, :, 1], 2.).argmin(axis=1), **dchoosers)
        for hname, hmask in (('all', np.ones(n, bool)), ('7', held == 7), ('6', held == 6), ('5 or fewer', held <= 5)):
            sel = mixed & hmask
            if not sel.any():
                continue
            e = dict(decisions=int(sel.sum()), choosers={})
            line = f'{hname:<5.5} {int(sel.sum()):>9} |'
            for cname, c in dchoosers.items():
                e['choosers'][cname] = fmt(by_deal((g[np.arange(n), c][sel] == 0).astype(float), deal[sel]))
                line += f' {cname}: {e["choosers"][cname]["mean"]:.3f}+-{e["choosers"][cname]["se"] or 0:.3f} |'
            dfd[hname] = e
            text.append(line)
        R['defender_handover_decisions'] = dfd
        report['nets'][str(path)] = R
    (a.out / 'e1.json').write_text(json.dumps(report, indent=1))
    (a.out / 'e1.txt').write_text('\n'.join(text) + '\n')
    print('\n'.join(text))


if __name__ == '__main__':
    main()
