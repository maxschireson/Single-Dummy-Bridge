#!/usr/bin/env python3
"""Read rows written by scripts/plan_reading_bound.py.

  python scripts/plan_reading_report.py rows.json [more.json ...] [--floor 0.05]

Three ways to weigh a candidate layout by the hidden hands' past plays:

  net     the policy net's probability of each card played, mixed with `floor` of uniform (as the bots do)
  count   Gen 6 re-run from the candidate's hand: (times it played that card + 0.5 / legal cards) / (runs + 0.5)
  rated   Gen 6 re-run from the candidate's hand, read through how it rated the card played: the chance that a second
          run plays a card, given whether the first played it and how far behind its best the first rated it. That
          chance is measured on these rows (pairs of runs of the same hand), on the other half of the deals.

The bot is only run on candidates drawn from the pool by the net's reading; its reading of the pool follows by
importance weights (bot's likelihood over net's). For each reading: the true layout's log-weight gained against the pool
(nats), the mean log-likelihood ratio of the true layout to a drawn candidate, and the mean log-probability of the true
holder of each unseen card under the reading WITHOUT the true layout (honours T to A, and small cards).
Errors take deals as the unit (bootstrap).
"""
import argparse
import json
import sys

import numpy as np

EDGES = [1e-9, .03125, .0625, .125, .25, .5, 1.]


def bucket(hit, gap):
    """0 = played it; 1 = rated level with the best but another card played; 2.. = by how far behind."""
    b = 1 + np.searchsorted(EDGES, np.nan_to_num(gap, nan=9.), side='left')
    return np.where(hit == 1, 0, b)


def logmeanexp(x):
    m = x.max()
    return m + np.log(np.mean(np.exp(x - m)))


def boot(values, groups, rng, n=1000):
    ids = sorted(set(groups))
    by = {g: [] for g in ids}
    for v, g in zip(values, groups):
        by[g].append(v)
    sums = np.array([np.sum(by[g], axis=0) for g in ids])
    counts = np.array([len(by[g]) for g in ids])
    pick = rng.integers(0, len(ids), (n, len(ids)))
    means = sums[pick].sum(1) / counts[pick].sum(1)[:, None] if sums.ndim > 1 else sums[pick].sum(1) / counts[pick].sum(1)
    return sums.sum(0) / counts.sum(), means.std(0)


def swaps(rows, S, half, rated, fam, a, rng):
    """Rows made with --swaps: the evidence the plays hold about one card's place, as the log-likelihood ratio of the true
    layout to the same layout with that card in the other hidden hand."""
    recs = []
    for s, h, r, f in zip(S, half, rows, fam):
        same, gap, net, opt = s['same'], s['gap'], s['net'], s['opt']
        sim = same >= 0
        choice = opt > 1
        runs = sim.sum(2)
        ln = np.where(choice, np.log((1 - a.floor) * np.exp(net) + a.floor / np.maximum(opt, 1)), 0.)
        pr = np.where(sim, rated[h][bucket(same, gap)], 0.).sum(2) / np.maximum(runs, 1)
        lr = np.where(choice & (runs > 0), np.log(np.maximum(pr, 1e-6)), 0.)
        partner = s['partner']
        for k, (kind, card, other) in enumerate(r['kinds']):
            if k == 0:
                continue
            recs.append(dict(family=f, kind=kind, rank='23456789TJQKA'[card % 13], declaring=r['declaring'],
                             net=float((ln[:, 0] - ln[:, k]).sum()), bot=float((lr[:, 0] - lr[:, k]).sum()),
                             bot_partner=float((lr[partner, 0] - lr[partner, k]).sum()), net_partner=float((ln[partner, 0] - ln[partner, k]).sum()),
                             plays_differ=int(((same[:, k, :] == 0).any(1) & choice[:, k]).sum())))
    print(f'\n{len(rows)} seats on {len(set(fam))} deals, {len(recs)} single-card neighbours of the true layout. Evidence = log-likelihood of the plays under '
          f'the true layout minus under the neighbour (nats). With even prior odds the true holder then gets log-probability -log(1 + exp(-evidence)).')
    print(f"   {'':34s}{'n':>6s}{'bot: mean evidence':>22s}{'net: mean evidence':>22s}{'bot: log-prob':>18s}{'net: log-prob':>18s}{'bot says wrong':>16s}{'net says wrong':>16s}")
    lp = lambda e: -np.log1p(np.exp(-np.clip(e, -30, 30)))

    def line(label, sub):
        if len(sub) < 10:
            return
        g = [x['family'] for x in sub]
        cells = []
        for key in ('bot', 'net'):
            m, e = boot([x[key] for x in sub], g, rng)
            cells.append(f'{m:+12.2f} +- {e:.2f}')
        for key in ('bot', 'net'):
            m, e = boot(lp(np.array([x[key] for x in sub])), g, rng)
            cells.append(f'{m:+9.3f} +- {e:.3f}')
        for key in ('bot', 'net'):
            cells.append(f"{np.mean([x[key] < -1e-9 for x in sub]):16.3f}")
        print(f'   {label:34s}{len(sub):6d}' + ''.join(cells))

    for kind in ('honour', 'honour and length', 'small'):
        line(kind, [x for x in recs if x['kind'] == kind])
    hon = [x for x in recs if x['kind'].startswith('honour')]
    for rank in 'AKQJT':
        line(f'honours: {rank}', [x for x in hon if x['rank'] == rank])
    line('honours, viewer declaring', [x for x in hon if x['declaring']])
    line('honours, viewer defending', [x for x in hon if not x['declaring']])
    m, e = boot([x['bot_partner'] for x in hon if not x['declaring']], [x['family'] for x in hon if not x['declaring']], rng)
    m2, e2 = boot([x['net_partner'] for x in hon if not x['declaring']], [x['family'] for x in hon if not x['declaring']], rng)
    print(f"   of the defenders' evidence about honours, from partner's plays alone: bot {m:+.2f} +- {e:.2f}, net {m2:+.2f} +- {e2:.2f}")
    print(f"   honours on which no play of the bot would have differed in the neighbour: {np.mean([x['plays_differ'] == 0 for x in hon]):.3f}; "
          f"bot's evidence above 3 nats: {np.mean([x['bot'] > 3 for x in hon]):.3f}; net's: {np.mean([x['net'] > 3 for x in hon]):.3f}")
    d = np.array([x['bot'] - x['net'] for x in hon])
    m, e = boot(d, [x['family'] for x in hon], rng)
    print(f'   bot minus net, honours: {m:+.2f} +- {e:.2f} nats; correlation of the two {np.corrcoef([x["bot"] for x in hon], [x["net"] for x in hon])[0, 1]:.2f}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('files', nargs='+')
    p.add_argument('--floor', type=float, default=.05)
    p.add_argument('--smooth', type=float, default=.05)
    a = p.parse_args()
    rows = []
    for f in a.files:
        d = json.load(open(f))
        rows += d['rows']
        print(f, d['settings'])
    rng = np.random.default_rng(0)
    fam = [r['family'] for r in rows]
    half = [int(f[:8], 16) % 2 for f in fam]
    S = []
    for r in rows:
        same, gap = np.array(r['same']), np.array(r['gap'], float)
        gap = np.where(gap < 0, np.nan, gap)
        S.append(dict(same=same, gap=gap, net=np.array(r['net_logp']), opt=np.array(r['options']), assign=np.array(r['assign']),
                      honour=np.array([c[1] in 'TJQKA' for c in r['unseen']]), tricks=np.array([q['trick'] for q in r['plays']]),
                      partner=np.array([q['partner'] for q in r['plays']])))

    # the chance that a second run plays the card, by what the first run did with it: per half of the deals
    nb = len(EDGES) + 2
    table = np.zeros((2, nb, 2))
    for s, h in zip(S, half):
        same, gap, opt = s['same'], s['gap'], s['opt']
        m = same.shape[2]
        live = (same >= 0).all(2) & (opt > 1)
        for x in range(m):
            for y in range(m):
                if x != y:
                    b = bucket(same[:, :, x], gap[:, :, x])[live]
                    np.add.at(table[h], (b, same[:, :, y][live]), 1)
    rated = np.zeros((2, nb))
    for h in range(2):
        t = table[1 - h]                                # fitted on the other half
        rated[h] = (t[:, 1] + 1) / (t.sum(1) + 2)
    both = table.sum(0)
    names = ['played it', 'level, other played'] + [f'behind <= {e}' for e in EDGES[1:]] + ['behind > 1']
    print('\nA second run of Gen 6 from the same hand plays a card with this chance, by what the first run did with it:')
    for b in range(nb):
        if both[b].sum():
            print(f'   {names[b]:22s} {both[b, 1] / both[b].sum():.3f}  ({int(both[b].sum())} pairs of runs)')

    if rows and rows[0].get('kinds'):
        return swaps(rows, S, half, rated, fam, a, rng)
    out = []
    self_hits, cand_hits, net_true, rated_true = [], [], [], []
    lp = lambda pt: np.log((1 - a.smooth) * np.clip(pt, 0, 1) + a.smooth / 2)
    for s, h, r in zip(S, half, rows):
        same, gap, net, opt = s['same'], s['gap'], s['net'], s['opt']
        P, C, m = same.shape
        sim = same >= 0
        choice = opt > 1
        L = {}
        L['net'] = np.where(choice, np.log((1 - a.floor) * np.exp(net) + a.floor / np.maximum(opt, 1)), 0.)
        k = (same == 1).sum(2)
        runs = sim.sum(2)
        L['count'] = np.where(choice & (runs > 0), np.log((k + .5 / np.maximum(opt, 1)) / (np.maximum(runs, 1) + .5)), 0.)
        pr = np.where(sim, rated[h][bucket(same, gap)], 0.).sum(2) / np.maximum(runs, 1)
        L['rated'] = np.where(choice & (runs > 0), np.log(np.maximum(pr, 1e-6)), 0.)
        pool, share = r['pool'], np.array(r['share'])
        N = pool['n']
        rec = dict(candidates=C - 1, pool=N, plays=int(choice[:, 0].sum()), simulated=float(sim[:, 1:, 0].mean()) if C > 1 else 1.)
        real = choice[:, 0]
        self_hits.append((float((same[real, 0, :] == 1).sum()), float(same[real, 0, :].size)))
        cm = sim[:, 1:, :] & choice[:, 1:, None]
        cand_hits.append((float((same[:, 1:, :] == 1)[cm].sum()), float(cm.sum())))
        net_true.append((float(net[real, 0].sum()), float(real.sum())))
        rated_true.append((float(L['rated'][real, 0].sum()), float(real.sum())))
        honour = s['honour']
        truth = s['assign'][0]
        agree = (s['assign'][1:] == truth[None, :]).astype(float)                   # [candidates, unseen]
        tot = {name: l.sum(0) for name, l in L.items()}
        marg = dict(prior=np.array(pool['prior_agree']), net=np.array(pool['net_agree']), net_drawn=share[1:] @ agree)
        gain = dict(net=pool['true_net'] - np.logaddexp(np.log(N) + pool['logz_net'], pool['true_net']) + np.log(N + 1))
        eff = dict(net=pool['effective'], net_drawn=1 / (share[1:] ** 2).sum())
        for name in ('count', 'rated'):
            lw = np.log(share[1:]) + tot[name][1:] - tot['net'][1:]                 # importance weights: drawn by the net, read by the bot
            logz = pool['logz_net'] + np.log(np.exp(lw - lw.max()).sum()) + lw.max()
            gain[name] = tot[name][0] - np.logaddexp(np.log(N) + logz, tot[name][0]) + np.log(N + 1)
            w = np.exp(lw - lw.max())
            marg[name] = (w / w.sum()) @ agree
            eff[name] = w.sum() ** 2 / (w ** 2).sum()
        for name, pt in marg.items():
            v = lp(pt)
            rec[name + '_honours'] = float(v[honour].mean()) if honour.any() else np.nan
            rec[name + '_small'] = float(v[~honour].mean()) if (~honour).any() else np.nan
        for name, g in gain.items():
            rec[name + '_gain'] = float(g)
        for name, e in eff.items():
            rec[name + '_effective'] = float(e)
        for name in ('net', 'count', 'rated'):
            rec[name + '_ratio'] = float(share[1:] @ (tot[name][0] - tot[name][1:])) if C > 1 else 0.
        rec.update(declaring=r['declaring'], seconds=r.get('seconds', 0), calls=r['calls'])
        out.append(rec)

    tot = lambda x: (sum(v for v, _ in x), sum(n for _, n in x))
    h, n = tot(self_hits)
    ch, cn = tot(cand_hits)
    nt, nn = tot(net_true)
    rt, rn = tot(rated_true)
    C = int(np.mean([o['candidates'] for o in out]))
    N = int(np.mean([o['pool'] for o in out]))
    print(f'\n{len(out)} seats on {len(set(fam))} deals; pool of about {N} layouts a seat, {C} distinct candidates drawn from it by the net\'s reading; '
          f'{np.mean([o["plays"] for o in out]):.1f} past choices by hidden hands a seat; {np.mean([o["seconds"] for o in out]):.0f} s a seat; '
          f'candidates still simulated at a play: {np.mean([o["simulated"] for o in out]):.2f}')
    print(f'Gen 6 re-run from the TRUE hand played the card that was played in {h / n:.3f} of {int(n)} runs; from a candidate hand in {ch / cn:.3f} of {int(cn)}.')
    print(f'Mean log-probability of a true play: net {nt / nn:+.3f}; Gen 6 re-run and rated {rt / rn:+.3f} ({int(nn)} plays with a choice).')
    cols = ['gain', 'ratio', 'honours', 'small', 'effective']
    heads = ['log-weight gained', 'log ratio to a drawn', 'honours log-prob', 'small log-prob', 'effective layouts']
    print(f"\n{'':10s}" + ''.join(f'{c:>22s}' for c in heads))
    for name in ['prior', 'net', 'net_drawn', 'count', 'rated']:
        cells = []
        for c in cols:
            key = f'{name}_{c}'
            if key not in out[0]:
                cells.append(f"{'':>22s}")
                continue
            v = [o[key] for o in out]
            ok = [i for i, x in enumerate(v) if x == x]
            m, e = boot([v[i] for i in ok], [fam[i] for i in ok], rng)
            cells.append(f'{m:+14.3f} +- {e:.3f}')
        print(f'{name:10s}' + ''.join(cells))
    print('(log-weight gained: the true layout against the pool. net_drawn = the net\'s reading seen through the drawn candidates only, the same lens the bot\'s reading has.)')
    for x, y in [('rated', 'net'), ('rated', 'net_drawn'), ('count', 'net')]:
        line = f'{x} - {y}:'
        for c in ['gain', 'honours', 'small']:
            if f'{y}_{c}' not in out[0]:
                continue
            v = [o[f'{x}_{c}'] - o[f'{y}_{c}'] for o in out]
            ok = [i for i, q in enumerate(v) if q == q]
            m, e = boot([v[i] for i in ok], [fam[i] for i in ok], rng)
            line += f'  {c} {m:+.3f} +- {e:.3f}'
        print(line)
    for side in (True, False):
        sub = [i for i, o in enumerate(out) if o['declaring'] == side]
        if len(sub) > 5:
            line = f"{'declarer' if side else 'defenders'} ({len(sub)} seats):"
            for name in ['net', 'rated']:
                for c in ['gain', 'honours']:
                    m, e = boot([out[i][f'{name}_{c}'] for i in sub], [fam[i] for i in sub], rng)
                    line += f'  {name} {c} {m:+.3f} +- {e:.3f}'
            m, e = boot([out[i]['prior_honours'] for i in sub], [fam[i] for i in sub], rng)
            print(line + f'  prior honours {m:+.3f}')


if __name__ == '__main__':
    sys.exit(main())
