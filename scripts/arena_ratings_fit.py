#!/usr/bin/env python3
"""ratings-v1 from every paired result the arena has published (Gen 9 task G9-D3).

Gen 9 work in progress (dave). Read-only; decides nothing. Fits g9's rating model
(docs/gen9/arena-statistics.md section 1, bridge_harness/arena_ratings.py) to the per-board rows
of scripts/arena_feed_rows.py, one table per bidding condition:

  native            each side bid with its own bidder: the whole bot; comparable across feeds
  common@<bidder>   all four seats bid by the cohort's common bidder: card play alone, one table per
                    common bidder (identified by the sha256 of its bidding network), because the same
                    two bots meet different contracts under different common bidders

Counting rules are the dashboard's (scripts/generation_results.py), applied within each table:
records after the feed's snapshot are ignored, the hidden actor (ben32) and the accidental
fast-against-BEN cohorts are out, a source's allowed pairs are respected, a deal family counts once
per pair (earliest completion wins). Self-play carries no strength and is left out.

For every played pair the table gives the pair's own result with its published (unshrunk) 95%
interval, the model's fitted difference, the cell, and the out-of-line test: the pair's own mean
against its leave-one-out prediction (the model fitted to every other pair, with the pair-effect
variance t2 re-estimated without it), z = (m - pred) / sqrt(e^2 + var(pred) + t2), with
Holm-adjusted p-values over the pairs that have an independent prediction.

  python scripts/arena_ratings_fit.py --rows rows.jsonl.gz [--rows more.jsonl.gz] --cache DIR --out ratings.json [--markdown report.md]
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness import arena_ratings as ar  # noqa: E402
import arena_feed_rows as afr  # noqa: E402
import generation_results as gr  # noqa: E402

REFERENCE = 'ben'
UNTESTABLE_SE = 1.0      # leave-one-out SE above this: the prediction is the prior, not the other pairs
PROVISIONAL_FIELD = {'ben': 0.25, 'ben64': 0.25, '5RZ32': 0.25, '1': 0.25}   # not a decision: Max sets the field


def common_bidders(rows, cache):
    """Source -> sha256 of the common bidder's bidding network, from each feed's arena/manifest.json at its ref."""
    out = {}
    for src, ref in sorted({(r['source'], r['ref']) for r in rows}):
        m = afr.fetch(cache, ref, 'arena/manifest.json')
        cb = m.get('common_bidder')
        sha = ((m.get('bots') or {}).get(cb) or {}).get('artifact_sha256', {}).get('bidding')
        out[src] = dict(bot=cb, sha256=sha)
    return out


def rank(bot):
    """The dashboard's actor order; a bot it does not list yet (newer than its list, such as 71s-32) comes first."""
    return gr.ORDER.index(bot) if bot in gr.ORDER else -1


def normalize(pair):
    a, b = gr.members(pair)
    return (gr.pair_id(b, a), True) if rank(a) > rank(b) else (gr.pair_id(a, b), False)


def tables(rows, bidders):
    """{condition: [(i, j, x, family, t)]} under the dashboard's rules, pairs in the dashboard's order."""
    kept = {}
    for r in rows:
        if r['completed_epoch'] > r['snapshot_epoch']:
            continue
        p, flip = normalize(r['pair'])
        a, b = gr.members(p)
        if a == b or any(x in gr.HIDDEN for x in (a, b)) or (p == '6-32~ben' and r['cohort'] in gr.ACCIDENTAL):
            continue
        if r['allowed_pairs'] and r['pair'] not in r['allowed_pairs']:
            continue
        s = -1 if flip else 1
        cb = bidders[r['source']]
        if r['common'] is not None:
            kept.setdefault(f"common@{(cb['sha256'] or 'unknown')[:8]}", []).append((a, b, s * r['common'], r['family'], r['completed_epoch']))
        if r['native_ok'] and r['native'] is not None:
            kept.setdefault('native', []).append((a, b, s * r['native'], r['family'], r['completed_epoch']))
    out = {}
    for cond, items in kept.items():
        items.sort(key=lambda x: x[4])
        seen, use = set(), []
        for a, b, x, fam, t in items:
            if (fam, a, b) not in seen:
                seen.add((fam, a, b)); use.append((a, b, x))
        out[cond] = use
    return out


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda k: pvals[k])
    adj, run = [0.0] * len(pvals), 0.0
    for rank, k in enumerate(order):
        run = max(run, min(1.0, (len(pvals) - rank) * pvals[k]))
        adj[k] = run
    return adj


def fit_table(results, reference=REFERENCE, field=PROVISIONAL_FIELD):
    pairs = ar.summarise(results)
    players = sorted({p.i for p in pairs} | {p.j for p in pairs}, key=lambda x: (rank(x), x))
    ref = reference if reference in players else players[-1]
    R = ar.fit(pairs, players, ref)
    boards = {p: 0 for p in players}
    for q in pairs:
        boards[q.i] += q.n; boards[q.j] += q.n
    prow = []
    for q in pairs:
        se_raw = math.sqrt(q.var / q.n) if q.n > 1 else float('nan')
        fitted, _ = R.predict(q.i, q.j)
        # The out-of-line test re-estimates the pair-effect variance without the pair under test: one large
        # effect would otherwise raise t2, widen its own prediction's interval and hide itself.
        loo = ar.fit([x for x in pairs if x is not q], players, ref)
        a = loo._a(q.i, q.j)
        pred, var_est = float(a @ loo.s), float(a @ loo.C @ a)
        z = (q.mean - pred) / math.sqrt(q.se2() + var_est + loo.t2)
        cell, vcell = R.cell(q.i, q.j)
        prow.append(dict(pair=f'{q.i}~{q.j}', boards=q.n, mean=round(q.mean, 4), se=round(se_raw, 4),
                         ci95=[round(q.mean - 1.96 * se_raw, 4), round(q.mean + 1.96 * se_raw, 4)],
                         fitted=round(fitted, 4), fitted_in_ci=bool(abs(fitted - q.mean) <= 1.96 * se_raw),
                         loo_prediction=round(pred, 4), loo_se=round(math.sqrt(var_est), 4), loo_t2=round(loo.t2, 5), z=round(z, 3),
                         p=2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))),
                         cell=round(cell, 4), cell_se=round(math.sqrt(vcell), 4)))
    # A pair that is a player's only link to the rest of the table has no independent prediction (the
    # leave-one-out fit falls back on the prior): it cannot be checked, and is left out of the adjustment.
    testable = [r for r in prow if r['loo_se'] < UNTESTABLE_SE]
    for row, padj in zip(testable, holm([r['p'] for r in testable])):
        row['p_holm'] = round(padj, 5); row['out_of_line'] = padj < 0.05
    for row in prow:
        row['p'] = round(row['p'], 5); row['testable'] = row['loo_se'] < UNTESTABLE_SE
        row.setdefault('p_holm', None); row.setdefault('out_of_line', None)
    prow.sort(key=lambda r: -r['boards'])
    players_out = {}
    for p in players:
        s, v = R.strength(p)
        players_out[p] = dict(strength=round(s, 4), se=round(math.sqrt(v), 4), boards=boards[p])
    six = {}
    if '6-32' in players:
        k = players.index('6-32')
        for p in players:
            j = players.index(p)
            a = np.zeros(len(players)); a[j] += 1; a[k] -= 1
            six[p] = dict(vs_6_32=round(float(a @ R.s), 4), se=round(math.sqrt(float(a @ R.C @ a)), 4))
    fld = {j: w for j, w in field.items() if j in players}
    tot = sum(fld.values())
    fld = {j: w / tot for j, w in fld.items()} if tot else {}
    scores = {}
    if len(fld) >= 2:
        for p in players:
            F, vF, worst = R.field_score(p, {j: w for j, w in fld.items()})
            scores[p] = dict(F=round(F, 4), se=round(math.sqrt(vF), 4), worst=worst)
    return dict(reference=ref, t2=round(R.t2, 5), Q=round(R.details.get('Q', float('nan')), 2), df=R.details.get('df'),
                boards=sum(q.n for q in pairs), players=players_out, relative_to_6_32=six, pairs=prow,
                field=dict(provisional=True, shares=fld, scores=scores))


def markdown(doc):
    L = [f"Computed {doc['computed_utc']} UTC from {doc['rows']:,} rows of {len(doc['sources'])} sources.", '']
    for cond, t in doc['tables'].items():
        L += [f"### {cond}", '', f"{t['boards']:,} boards in {len(t['pairs'])} pairs; reference `{t['reference']}`; "
              f"pair-effect variance t2 = {t['t2']} (Q = {t['Q']} on {t['df']} degrees of freedom).", '',
              '| Player | Strength vs BEN (16) | SE | vs Gen 6 fast | SE | Boards |', '| --- | ---: | ---: | ---: | ---: | ---: |']
        for p, v in sorted(t['players'].items(), key=lambda kv: -kv[1]['strength']):
            six = t['relative_to_6_32'].get(p)
            L.append(f"| `{p}` | {v['strength']:+.3f} | {v['se']:.3f} | " + (f"{six['vs_6_32']:+.3f} | {six['se']:.3f}" if six else '— | —') + f" | {v['boards']:,} |")
        L += ['', '| Pair | Boards | Own result (95%) | Fitted | Leave-one-out prediction | z | Holm p | Out of line |',
              '| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |']
        for r in t['pairs']:
            if r['testable']:
                tail = f"{r['loo_prediction']:+.3f} ± {r['loo_se']:.3f} | {r['z']:+.2f} | {r['p_holm']:.3f} | {'**yes**' if r['out_of_line'] else 'no'} |"
            else:
                tail = "none (only link) | | | not testable |"
            L.append(f"| `{r['pair']}` | {r['boards']:,} | {r['mean']:+.3f} ({r['ci95'][0]:+.2f} to {r['ci95'][1]:+.2f}) | {r['fitted']:+.3f}"
                     f"{'' if r['fitted_in_ci'] else ' (outside)'} | " + tail)
        L.append('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rows', type=Path, action='append', required=True)
    ap.add_argument('--cache', type=Path, default=Path.home() / '.cache' / 'arena-feeds')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--markdown', type=Path)
    a = ap.parse_args()
    rows = []
    for path in a.rows:
        with gzip.open(path, 'rt') as f:
            rows += [json.loads(line) for line in f]
    bidders = common_bidders(rows, a.cache)
    out = dict(schema='ratings-v1', model='docs/gen9/arena-statistics.md section 1 (bridge_harness/arena_ratings.py)',
               computed_utc=time.strftime('%Y-%m-%d %H:%M', time.gmtime()), rows=len(rows),
               sources={s: dict(common_bidder=b) for s, b in bidders.items()}, tables={})
    for cond, results in sorted(tables(rows, bidders).items()):
        out['tables'][cond] = fit_table(results)
        t = out['tables'][cond]
        print(f"{cond}: {t['boards']:,} boards, {len(t['pairs'])} pairs, t2 {t['t2']}, out of line: "
              f"{[r['pair'] for r in t['pairs'] if r['out_of_line']]}, fitted outside own CI: {[r['pair'] for r in t['pairs'] if not r['fitted_in_ci']]}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    if a.markdown:
        a.markdown.write_text(markdown(out) + '\n')


if __name__ == '__main__':
    main()
