#!/usr/bin/env python3
"""Score a search on gap-fork pairs: would it have played the card that did better?

  python scripts/gen7_bench.py --episodes DIR --policy policy.npz [--tricks 1,2] [--breadth 2] [--mass 0.9]
                               [--layouts 8] [--from-trick 3] [--to-trick 13] [--pairs 2000] [--workers 2] [--out rows.json]
                               [--policy2 other.npz] [--splits 1,2]

--tricks lists the trees to score, ';' between them: a horizon in tricks, optionally ':' and tree
settings that differ from the command line, e.g. "2;2:reply_power=2;2:breadth=1,reply_gap=0.2".
"2:net=2" runs that tree on the net given by --policy2, on the same pairs. --splits keeps only
deals of those splits (0 train, 1 validation, 2 test): a net must be scored on deals it was not
trained on. Files are read in a fixed order, so the same --pairs gives the same pairs.

In a gap-fork pair A is the card Gen 6 played and B a card it rated worse, which the collector
forced and played out from the same position (docs/gen7_data_capture_2026-11-11.md). The realized
cost of B is known. Each pair's position is rebuilt, Gen 6's own layouts are drawn again, and A and
B are valued by:

  pimc     plain PIMC on all those layouts (Gen 6 again, with a fresh draw)
  pimc_k   plain PIMC on the --layouts of them that go into the tree
  tree_N   the tree (bridge_harness/gen7_tree.py) to the end of N tricks on the same --layouts
  mix_N    pimc plus the tree's correction: pimc + (tree_N - pimc_k)

An evaluator that prefers B is credited with what B really gained (minus its realized cost);
one that prefers A scores nothing. Gen 6 itself scores zero by construction, so `gain` is tricks
per pair gained over Gen 6 by following that evaluator on these pairs. `over_pimc` is the same
thing measured against the fresh PIMC draw on identical layouts, which removes the luck of the draw
from the comparison. Pairs are sampled by band of estimated gap, so these are per sampled pair.
The opening lead is left out (the tree needs dummy on the table).

--ties adds the tie-audit pairs as band -1: two cards Gen 6 rated exactly level, both played out.
PIMC cannot tell them apart, so any gain there is information the tree adds.

`per_side` in the output weights the pairs back to whole tables. Every gap fork records the
probability with which it was drawn, so the sum over drawn pairs of (what the evaluator loses by
preferring B) / probability estimates the total over every (decision, other card) of one side at
one table. It is given for any card B and for B among the net's root candidates (at most
--root-cards of them, kept until their probabilities add to --root-mass), in tricks and in IMPs.
Limits: one card is swapped and the arena's bots play the rest, and when an evaluator prefers two
other cards at one decision both are counted.
"""
import argparse
import gzip
import json
import math
from multiprocessing import Pool
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import SEATS, Board, Game, card
from bridge_harness.gen6 import View, systematic
from bridge_harness.gen7 import Gen7Player
from bridge_harness.gen7_net import PolicyNet
from bridge_harness.gen7_tree import Tree, TreeConfig
import gen7_check as check
from gen7_lookahead import PHASES, phase

STATE = {}


def label(n, extra):
    return str(n) + ''.join(f'_{k}{v}' for k, v in sorted(extra.items()))


def variants(text):
    """'1,2' or '2;2:reply_power=2;2:breadth=1,reply_gap=0.2' -> ((tricks, {setting: value}), ...)"""
    out = []
    for part in text.replace(',', ';').split(';') if ':' not in text and '=' not in text else text.split(';'):
        n, _, rest = part.partition(':')
        extra = {}
        for item in filter(None, rest.split(',')):
            k, v = item.split('=')
            extra[k] = v if k in ('reply', 'own') else float(v) if '.' in v else int(v)      # net=2: the tree runs on --policy2
        out.append((int(n), extra))
    return tuple(out)


def searching_reply(p, layouts=8, pool=64):
    """The stand-in searcher for reply='search' and own='search' (Gen7Player.searching_reply)."""
    return p.searching_reply(layouts, pool)


def start(policy, tricks, breadth, mass, layouts, from_trick, ties=False, to_trick=13, policy2=None, splits=None):
    os.environ['BRIDGE_DDS_CACHE'] = ''                          # thousands of small batches: no disk cache
    STATE.update(player=Gen7Player(check.spec('gen7', policy, play_weight=0., tie_break='gen5'), ROOT), replier=None, splits=splits,
                 tricks=tricks, breadth=breadth, mass=mass, layouts=layouts, from_trick=from_trick, to_trick=to_trick, ties=ties)
    STATE['nets'] = {1: STATE['player'].net}
    if policy2:
        STATE['nets'][2] = PolicyNet(Path(policy2).resolve(), STATE['player'].scorer)
    STATE['replier'] = searching_reply(STATE['player'])


def net_order(net, o, act, a, b):
    """Where A and B stand among the net's choices at the root. Cards the search cannot tell apart
    (same suit, same estimate) count as one choice. mass_before is the probability of the choices ranked above."""
    logp = net.log_policy([o])[0]
    name = lambda c: 'SHDC'[c // 13] + '23456789TJQKA'[c % 13]
    kind = lambda c: (c // 13, round(act['estimates'][name(c)]['utility'], 9))
    mass = {}
    for c in o.legal:
        mass[kind(c)] = mass.get(kind(c), 0.) + float(np.exp(logp[c]))
    order = sorted(mass, key=lambda k: (-mass[k], k))
    before = np.concatenate([[0.], np.cumsum([mass[k] for k in order])])
    ra, rb = order.index(kind(a)), order.index(kind(b))
    return dict(rank_a=ra, rank_b=rb, mass_before_a=float(before[ra]), mass_before_b=float(before[rb]))


def pairs_of(path):
    p, rows, tables = STATE['player'], [], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    if STATE['splits'] is not None and check.split_of(d['family']) not in STATE['splits']:
        return rows, tables
    for key, e in d['unique_tables'].items():
        if 'tables' not in e:
            continue
        ok = lambda ply: ply > 0 and STATE['from_trick'] <= ply // 4 + 1 <= STATE['to_trick']
        if e.get('gap_forks'):                  # one entry per side played by a Gen 6 engine
            tables += [f"{d['family']}/{key}/{who}" for who in ('candidate', 'opponent') if d[who].startswith('6-')]
        # (table A was played at, table B was played at, ply, card B, band, estimated gap, sampling probability, IMPs B cost)
        forks = [(0, g['fork_table'], g['ply'], g['forced_card'], g['band'], g['estimated_gap'], g['propensity'], g.get('realized_cost_imps'))
                 for g in e.get('gap_forks') or [] if ok(g['ply'])]
        if STATE['ties']:                       # tie audits: two cards Gen 6 rated exactly level, both played out
            forks += [(x['candidate_table'], x['reference_table'], x['ply'], x['reference_card'], -1, 0., x['audit_probability'], None)
                      for x in e.get('audits') or [] if not x['identical_action'] and ok(x['ply'])
                      and not (e['tables'][x['candidate_table']]['actions'][x['ply']].get('gen7_tree') or {}).get('audit_reference')]
        if not forks:
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        for table_a, table_b, ply, forced, band, estimated, propensity, cost_imps in sorted(forks, key=lambda g: (g[2], g[0])):
            root, fork = e['tables'][table_a], e['tables'][table_b]
            game = Game(board)
            for act in root['actions'][:ply]:
                game.play(card(act['card']))
            o = game.observation()
            a, b = card(root['actions'][ply]['card']), card(forced)
            if not root['actions'][ply].get('gen6'):
                continue                        # not a Gen 6 decision
            seat = SEATS.index(root['actions'][ply]['seat'])
            sign = 1 if seat % 2 == declarer % 2 else -1
            row = dict(family=d['family'], table=key, opponent=d['opponent'], player=root['actions'][ply].get('player'),
                       phase=phase(ply), ply=ply, band=band, estimated=estimated, propensity=propensity, imps=cost_imps,
                       final=sign * (root['declarer_tricks'] - fork['declarer_tricks']), **net_order(p.net, o, root['actions'][ply], a, b))
            if 2 in STATE['nets']:
                row.update({f'{x}_net2': v for x, v in net_order(STATE['nets'][2], o, root['actions'][ply], a, b).items()})
            view = View(o)
            rng = np.random.default_rng([ply, int(d['family'][:8], 16)])
            started = time.perf_counter()
            worlds, weights, _ = p.layouts(o, view, p.source(o, view), rng)
            means = {a: 0., b: 0.}
            for (values, _), w in zip(check.solve(p, o, worlds), weights):
                u = check.utilities(o, values)
                means[a] += float(w) * u[a]
                means[b] += float(w) * u[b]
            row['pimc'] = means[a] - means[b]
            row['seconds_pimc'] = time.perf_counter() - started
            k = STATE['layouts']
            index, share = systematic(np.asarray(weights), k, rng) if len(worlds) > k else (np.arange(len(worlds)), np.asarray(weights))
            sub = [worlds[i] for i in index]
            for n, extra in ((0, {}), *STATE['tricks']):
                settings = {x: v for x, v in extra.items() if x != 'net'}
                tree = Tree(STATE['nets'][extra.get('net', 1)], p.dds,
                            TreeConfig(**dict(dict(tricks=n, breadth=STATE['breadth'], mass=STATE['mass'], layouts=k), **settings)), replier=STATE['replier'])
                started = time.perf_counter()
                v = tree.values(o, sub, share, cards=[a, b])
                name = 'pimc_k' if n == 0 else f'tree_{label(n, extra)}'
                row[name] = v[a] - v[b]
                if n:
                    t = label(n, extra)
                    row[f'seconds_{t}'], row[f'lines_{t}'], row[f'rows_{t}'], row[f'solves_{t}'] = time.perf_counter() - started, tree.lines, tree.net_rows, tree.solves
            rows.append(row)
    return rows, tables


def per_side(rows, tricks, tables, root_cards, root_mass):
    """Per side per table: how often each evaluator overrules Gen 6 and what that loses, from the gap-fork pairs.
    `tables` counts the sides played by a Gen 6 engine at the root tables read."""
    rows = [r for r in rows if r['band'] >= 0 and r.get('imps') is not None]
    if not rows or not tables:
        return {}
    f, imps = np.array([r['final'] for r in rows], float), np.array([r['imps'] for r in rows], float)
    w = 1 / np.array([r['propensity'] for r in rows])
    families = [r['family'] for r in rows]
    of_net = lambda sfx: np.array([r['rank_b' + sfx] < root_cards and r['mass_before_b' + sfx] < root_mass for r in rows])
    candidate = of_net('')

    def total(x):
        by = {}
        for v, fam in zip(x * w, families):
            by[fam] = by.get(fam, 0.) + v
        t = np.array(list(by.values()))
        return round(float(t.sum() / tables), 3), round(float(math.sqrt(len(t) / max(1, len(t) - 1) * ((t - t.mean()) ** 2).sum()) / tables), 3)

    out = dict(sides=tables, pairs=len(rows), other_cards=total(np.ones(len(rows)))[0], candidates=total(candidate.astype(float))[0])
    names = {'pimc': '', 'pimc_k': '', **{f'tree_{label(n, extra)}': '_net2' if extra.get('net') == 2 else '' for n, extra in tricks}}
    for name, sfx in names.items():
        prefers = np.array([r[name] < -1e-9 for r in rows])
        for tag, keep in (('any_card', prefers), ('root_candidates', prefers & of_net(sfx))):
            out[f'{name}/{tag}'] = dict(overrules=total(keep.astype(float))[0], tricks_lost=total(np.where(keep, f, 0.)), imps_lost=total(np.where(keep, imps, 0.)))
    return out


def summarize(rows, tricks):
    f = np.array([r['final'] for r in rows], float)
    n = len(rows)
    families = [r['family'] for r in rows]

    def clustered(x):
        """Mean and standard error with deals as the unit."""
        by = {}
        for v, fam in zip(x, families):
            by.setdefault(fam, []).append(v)
        totals, counts = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
        mean = totals.sum() / counts.sum()
        se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
        return round(float(mean), 4), round(float(se), 4)

    evaluators = {'pimc': np.array([r['pimc'] for r in rows]), 'pimc_k': np.array([r['pimc_k'] for r in rows])}
    tricks = [label(n, extra) for n, extra in tricks]
    for t in tricks:
        tree = np.array([r[f'tree_{t}'] for r in rows])
        evaluators[f'tree_{t}'] = tree
        evaluators[f'mix_{t}'] = evaluators['pimc'] + tree - evaluators['pimc_k']
    out = dict(pairs=n, deals=len(set(families)), realized_cost_of_b=clustered(f), b_did_better=round(float((f < 0).mean()), 3),
               hindsight=clustered(np.maximum(0, -f)))
    base = {}
    for name, diff in evaluators.items():
        prefers_b = diff < -1e-9
        gain = np.where(prefers_b, -f, 0.)
        base[name] = gain
        ref = base['pimc'] if name.startswith('mix') or name == 'pimc' else base['pimc_k']
        out[name] = dict(prefers_b=round(float(prefers_b.mean()), 3), gain=clustered(gain), over_pimc=clustered(gain - ref),
                         cost_of_b_when_preferred=round(float(f[prefers_b].mean()), 3) if prefers_b.any() else None)
    for t in tricks:
        out[f'tree_{t}'].update(seconds=round(float(np.mean([r[f'seconds_{t}'] for r in rows])), 3),
                                lines=round(float(np.mean([r[f'lines_{t}'] for r in rows])), 1),
                                net_rows=round(float(np.mean([r[f'rows_{t}'] for r in rows])), 1),
                                solves=round(float(np.mean([r[f'solves_{t}'] for r in rows])), 1))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path)
    p.add_argument('--policy', type=Path)
    p.add_argument('--tricks', default='1,2')
    p.add_argument('--breadth', type=int, default=2)
    p.add_argument('--mass', type=float, default=.9)
    p.add_argument('--layouts', type=int, default=8)
    p.add_argument('--from-trick', type=int, default=3)
    p.add_argument('--to-trick', type=int, default=13)
    p.add_argument('--policy2', type=Path, help='a second net, for trees marked net=2')
    p.add_argument('--splits', help='keep only deals of these splits, e.g. 1,2 (0 train, 1 validation, 2 test)')
    p.add_argument('--root-cards', type=int, default=3, help='per_side: the most root candidates taken from the net')
    p.add_argument('--root-mass', type=float, default=.98, help='per_side: root candidates are kept until their probabilities add to this')
    p.add_argument('--pairs', type=int, default=2000)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seconds', type=float, default=1e9)
    p.add_argument('--ties', action='store_true', help='also score tie-audit pairs (band -1): two cards Gen 6 rated level')
    p.add_argument('--rows', type=Path, help='summarize a rows file written earlier with --out instead of running')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    tricks = variants(a.tricks)
    if a.rows:
        saved = json.loads(a.rows.read_text())
        rows, tricks = saved['rows'], tuple((t, {}) if isinstance(t, int) else (t[0], t[1]) for t in saved['settings']['tricks'])
        tables = saved['settings'].get('tables', 0)
    else:
        files = sorted(a.episodes.glob('*.json.gz'))
        rows, tables, started = [], 0, time.time()
        splits = None if a.splits is None else tuple(int(x) for x in a.splits.split(','))
        with Pool(a.workers, initializer=start,
                  initargs=(a.policy, tricks, a.breadth, a.mass, a.layouts, a.from_trick, a.ties, a.to_trick, a.policy2, splits)) as pool:
            for got, seen in pool.imap(pairs_of, files, chunksize=4):
                rows += got
                tables += len(seen)
                if len(rows) >= a.pairs or time.time() - started > a.seconds:
                    pool.terminate()
                    break
        if a.out:
            a.out.write_text(json.dumps(dict(settings=dict(tricks=tricks, breadth=a.breadth, mass=a.mass, layouts=a.layouts, from_trick=a.from_trick,
                                                           to_trick=a.to_trick, tables=tables, policy=str(a.policy), policy2=str(a.policy2), splits=a.splits,
                                                           seconds=round(time.time() - started)),
                                             rows=rows)))
    result = dict(all=summarize(rows, tricks), per_side=per_side(rows, tricks, tables, a.root_cards, a.root_mass) if 'rank_b' in rows[0] else {},
                  by_phase={k: summarize(sub, tricks) for k in PHASES for sub in [[r for r in rows if r['phase'] == k]] if len(sub) >= 50},
                  by_band={str(b): summarize(sub, tricks) for b in sorted({r['band'] for r in rows}) for sub in [[r for r in rows if r['band'] == b]] if len(sub) >= 50})
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
