#!/usr/bin/env python3
"""Which card should a bot play among those its search rates close together? Scored on fork pairs.

  python scripts/gen7_near_tie.py --net NAME=POLICY.npz [--net ...] [--head NAME=LABEL=WEIGHTS.npz ...] \
         --test FRESH_raw.npz PAIRS.npz [--test ...] [--drop TRAIN.npz] [--bot N] [--source N] [--out FILE.json]

The Gen 7 engine can make every card within `near_tie` tricks of the search's best eligible and let
the net pick among them (`Gen7Player.break_ties`). A fork pair says what that would have done at one
decision: two cards were both played out to the end by the same bots, so the tricks one made more
than the other are known. Here every pair is turned so that S is the card the search rated higher and
T the other (level pairs keep the card the bot played as S), and pairs are grouped by the search's gap
between the two. In each group, for each selector: how often it would play T, what T really cost
when it did (tricks with S minus tricks with T), and its gain a pair over always playing S. A selector
belongs in the engine's near-tie slot where that gain is above zero.

Selectors, all from the deciding seat's view:
  policy       the net's probability is higher for T (what break_ties does today)
  policy 2x    ... at least twice as high;   policy 4x: four times
  gap head     the net's gap head rates T's gap smaller
  a head       a head fitted on fork results (scripts/gen7_result_head.py) predicts that T gains; its
               label says which model: `result` is the head alone, `search_plus_res` the head plus the
               search's gap times a fitted slope, so that one overrules the search only by more than the gap
--head NAME=LABEL=WEIGHTS takes a file gen7_result_head.py wrote for the net NAME; LABEL is put before
the model's name, so that heads fitted on different pairs can stand side by side.

Pairs are gap forks (the forced card drawn by band of its gap), tie audits (the forced card rated
exactly level) and, from Gen 7 runs, tree audits. They are sampled pairs, not every near-tied card of
every decision, so every figure is per sampled pair, and the groups are not weighted as a bot would
meet them. Deals in --drop sets are left out: a net is scored on deals it did not train on. The +-
figures are standard errors with the deal as the unit (a deal played at several tables, or present in
several sets, is one unit).
"""
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.gen7_net import INPUTS, forward
from gen7_result_head import Pairs

BANDS = ((-1., 0., 'level'), (0., .1, 'gap up to 0.1'), (.1, .2, 'gap 0.1 to 0.2'), (0., .2, 'gap up to 0.2'), (.2, .5, 'gap 0.2 to 0.5'), (.5, 99., 'gap over 0.5'))
STAGES = (('all tricks', 0, 52), ('opening lead', 0, 1), ('rest of trick 1', 1, 4), ('tricks 2-4', 4, 16), ('tricks 1-4', 0, 16), ('tricks 5-8', 16, 32), ('tricks 9-13', 32, 52))
HEAD_MODELS = ('result', 'search_plus_res')


def clustered(x, fam):
    """Mean of x and its standard error with the deal as the unit (a ratio of sums over deals)."""
    if not len(x):
        return float('nan'), float('nan')
    _, inv = np.unique(fam, return_inverse=True)
    totals, counts = np.bincount(inv, x), np.bincount(inv)
    mean, k = totals.sum() / counts.sum(), len(counts)
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * k / (k - 1)) / counts.sum() if k > 1 else float('nan')
    return float(mean), float(se)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--net', action='append', required=True, metavar='NAME=POLICY')
    p.add_argument('--head', action='append', default=[], metavar='NAME=LABEL=WEIGHTS')
    p.add_argument('--test', nargs=2, action='append', required=True, metavar=('SET', 'PAIRS'))
    p.add_argument('--drop', action='append', default=[], help='a built set whose deals are left out')
    p.add_argument('--bot', type=int, default=-1, help="only pairs decided by this bot (the pairs' bot column: 0 = 6-32, 1 = 6-256, 2 = any other)")
    p.add_argument('--source', type=int, default=-1, help='only pairs of this source: 1 = gap forks, 0 = audits (tie audits and the tree\'s)')
    p.add_argument('--min-pairs', type=int, default=300)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    seen = set()
    for d in a.drop:
        with np.load(d) as z:
            seen.update(z['family'].tolist())
    seen = np.array(sorted(seen)) if seen else None
    heads = {}
    for spec in a.head:
        name, label, path = spec.split('=', 2)
        with np.load(path) as f:
            heads.setdefault(name, []).append((label, {k: f[k] for k in f.files}))
    report, kept = {}, {}
    for spec in a.net:
        name, path = spec.split('=', 1)
        with np.load(path) as f:
            params = {k: f[k] for k in f.files}
        cols = {}
        for set_path, pairs_path in a.test:
            t = Pairs(params, Path(set_path), Path(pairs_path), drop=seen)
            data = np.load(set_path)
            rows, inv = np.unique(t.p['row'], return_inverse=True)
            logit = np.concatenate([np.asarray(forward(params, {k: data[k][rows[i:i + 4096]] for k in INPUTS})['policy'], np.float64)
                                    for i in range(0, len(rows), 4096)]) if len(rows) else np.zeros((0, 52))
            part = dict(y=t.y, search=t.search, source=t.p['source'], imps=t.p['imps'].astype(np.float64), ply=t.p['ply'], bot=t.p['bot'],
                        fam=t.family[t.p['deal']], policy=logit[inv, t.p['b']] - logit[inv, t.p['a']], gap_head=-t.net_gap)
            for label, w in heads.get(name, []):
                for m in HEAD_MODELS:
                    part[f'{label} {m}'] = -t.predict(w[m])          # the head predicts the cost of B; turned, it is B's gain
            for k, v in part.items():
                cols.setdefault(k, []).append(v)
        c = {k: np.concatenate(v) for k, v in cols.items()}
        c['fam'] = np.unique(c['fam'], return_inverse=True)[1]      # the deal by its family: one deal can have boards in several sets
        if a.bot >= 0:
            c = {k: v[c['bot'] == a.bot] for k, v in c.items()}
        if a.source >= 0:
            c = {k: v[c['source'] == a.source] for k, v in c.items()}
        turn = np.where(c['search'] < -1e-9, -1., 1.)                # -1 where the search rated the forced card higher: then T is the card played
        fam, gap, cost, imps = c['fam'], np.abs(c['search']), turn * c['y'], turn * c['imps']
        score = {k: turn * v for k, v in c.items() if k not in ('y', 'search', 'source', 'imps', 'ply', 'bot', 'fam')}
        picks = {'policy': score['policy'] > 1e-9, 'policy 2x': score['policy'] > math.log(2.), 'policy 4x': score['policy'] > math.log(4.),
                 'gap head': score['gap_head'] > 1e-9}
        picks.update({k: v > 1e-9 for k, v in score.items() if k not in ('policy', 'gap_head')})
        kept[name] = dict(fam=fam, gap=gap, cost=cost, ply=c['ply'], policy=picks['policy'])
        print(f"\n######## {name}: {len(fam)} pairs on {len(np.unique(fam))} deals: {int((c['source'] == 1).sum())} gap forks, {int((c['source'] == 0).sum())} audits;"
              f" by bot {np.bincount(c['bot'], minlength=3).tolist()}; the search rated the forced card higher in {int((turn < 0).sum())}")
        out = {}
        for stage, lo_ply, hi_ply in STAGES:
            for lo, hi, label in BANDS:
                inside = (c['ply'] >= lo_ply) & (c['ply'] < hi_ply) & (gap > lo + 1e-9) & (gap <= hi + 1e-9)
                if inside.sum() < a.min_pairs:
                    continue
                f, y, ok = fam[inside], cost[inside], np.isfinite(imps[inside])
                base, base_i = clustered(y, f), clustered(imps[inside][ok], f[ok])
                line = dict(pairs=int(inside.sum()), deals=len(np.unique(f)), gap_forks=int((c['source'][inside] == 1).sum()), result_differs=float((y != 0).mean()),
                            t_better=float((y < 0).mean()), s_better=float((y > 0).mean()), cost_of_t=base, cost_of_t_imps=base_i,
                            mean_search_gap=float(gap[inside].mean()), selectors={})
                print(f"\n== {name}, {stage}, {label}: {line['pairs']} pairs ({line['gap_forks']} gap forks) on {line['deals']} deals | T better {line['t_better']:.1%}, S better {line['s_better']:.1%}"
                      f" | always T costs {base[0]:+.4f} +- {base[1]:.4f} tricks, {base_i[0]:+.3f} +- {base_i[1]:.3f} IMPs | search's gap {line['mean_search_gap']:.4f}")
                ref = np.where(picks['policy'][inside], -y, 0.)
                for sname, pick in picks.items():
                    k = pick[inside]
                    gain = np.where(k, -y, 0.)                       # tricks gained over always playing S, per pair of the group
                    g, when = clustered(gain, f), clustered(y[k], f[k])
                    gi = clustered(np.where(k, -imps[inside], 0.)[ok], f[ok])
                    over = clustered(gain - ref, f)
                    line['selectors'][sname] = dict(plays_t=float(k.mean()), cost_of_t_then=when, gain=g, gain_imps=gi, gain_over_policy=over)
                    print(f"  {sname:26s} plays T {k.mean():6.1%} | T then costs {when[0]:+.4f} +- {when[1]:.4f} | gain {g[0]:+.5f} +- {g[1]:.5f} tricks, {gi[0]:+.4f} +- {gi[1]:.4f} IMPs"
                          + ('' if sname == 'policy' else f" | over policy {over[0]:+.5f} +- {over[1]:.5f}"))
                out[f'{stage} | {label}'] = line
        report[name] = out
    names = list(kept)
    if len(names) > 1 and all(len(kept[n]['fam']) == len(kept[names[0]]['fam']) for n in names):
        first = kept[names[0]]
        print(f"\n######## the policy selector of each net against that of {names[0]}, on the same pairs (gain a pair, tricks)")
        report['between nets'] = {}
        for lo, hi, label in BANDS:
            inside = (first['gap'] > lo + 1e-9) & (first['gap'] <= hi + 1e-9)
            if inside.sum() < a.min_pairs:
                continue
            ref = np.where(first['policy'][inside], -first['cost'][inside], 0.)
            for n in names[1:]:
                differ = float((kept[n]['policy'][inside] != first['policy'][inside]).mean())
                d = clustered(np.where(kept[n]['policy'][inside], -first['cost'][inside], 0.) - ref, first['fam'][inside])
                report['between nets'][f'{n} | {label}'] = dict(pairs=int(inside.sum()), picks_differ=differ, gain_difference=d)
                print(f"  {label:16s} {n}: picks differ on {differ:6.1%} of {int(inside.sum())} pairs | {n} minus {names[0]} {d[0]:+.5f} +- {d[1]:.5f}")
    if a.out:
        a.out.write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
