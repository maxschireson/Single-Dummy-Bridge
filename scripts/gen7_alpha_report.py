#!/usr/bin/env python3
"""What a Gen 7 alpha cohort's records say: the match, what the tree did and cost, and how its choices did in play.

  python scripts/gen7_alpha_report.py --episodes DIR [--bot 7a-32] [--out report.json]

DIR holds the cohort's *.json.gz episode files (any names). For the Gen 7 bot (--bot, or the one
bot whose decisions carry a tree record):

  match    IMPs per board against each opponent, common and native auctions separately, as the
           runtime scored them. Deals are the unit of the standard error.
  tree     Of its searched decisions: how many fell in a tree stage, were searched by the tree,
           ended on a card the Gen 6 search did not rate best ("moved"), or ran over the solve
           budget; seconds and layout solves per tree search; all of it by trick.
  audits   Where the tree was consulted the bot names the card it would have played without the
           tree, and the collector's audit (a coin per decision, a shared compute budget) plays
           that card out from the same position when the two differ. Each such fork is one paired
           observation of the tree's card against the no-tree card with everything else the same:
           IMPs and tricks gained by the tree's card, per fork. Forks the budget refused are
           counted; if there are many, the forks played are not a random half of the moves.

A fork changes one card and lets the same four bots finish the hand, so it prices a single choice,
not a table played by a tree-less bot throughout. One playout per card: only averages mean anything.
"""
import argparse
import gzip
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board

SKIP = ('forced', 'replayed_prefix', 'counterfactual_forced', 'fixed_opening_lead')
PHASES = ('trick 1', 'trick 2', 'tricks 3-4', 'tricks 5-6', 'tricks 7-9', 'tricks 10-13')


def phase(ply):
    trick = ply // 4 + 1
    return 'lead' if ply == 0 else 'trick 1' if trick == 1 else 'trick 2' if trick == 2 else 'tricks 3-4' if trick <= 4 \
        else 'tricks 5-6' if trick <= 6 else 'tricks 7-9' if trick <= 9 else 'tricks 10-13'


def clustered(values, families):
    """(mean, standard error) with deals as the unit; (None, None) with nothing to average."""
    by = {}
    for v, f in zip(values, families):
        by.setdefault(f, []).append(v)
    if not by:
        return None, None
    totals, counts = np.array([sum(v) for v in by.values()], float), np.array([len(v) for v in by.values()], float)
    mean = totals.sum() / counts.sum()
    if len(by) < 2:
        return round(float(mean), 4), None
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / (len(by) - 1)) / counts.sum()
    return round(float(mean), 4), round(float(se), 4)


def read(directory, bot=None):
    """Rows for the three sections, from every episode in which `bot` (or any bot with tree records) played."""
    boards, decisions, forks, refused = [], [], [], 0
    for path in sorted(Path(directory).glob('*.json.gz')):
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        who = {'candidate': d['candidate'], 'opponent': d['opponent']}
        mine = set()
        for record in d['unique_tables'].values():
            if 'tables' not in record or record.get('schema_version') == 'v4-passed-out-v1':
                continue
            declarer = Board.from_dict(record['board']).contract.declarer
            for index, table in enumerate(record['tables']):
                for a in table['actions']:
                    name = who.get(a['player'])
                    if any(a.get(k) for k in SKIP) or 'gen7' not in a or 'gen6' not in a or (bot and name != bot):
                        continue
                    mine.add(name)
                    note = a.get('gen7_tree') or {}
                    decisions.append(dict(family=d['family'], bot=name, phase=phase(a['ply']), root=index == 0, staged='stage' in note,
                                          consulted=bool(note.get('consulted')), moved=bool(note.get('consulted')) and a['selected_pimc_gap'] > 1e-9,
                                          over_budget=bool(note.get('over_budget')), seconds=note.get('seconds'), solves=note.get('solves'),
                                          decision_seconds=a.get('seconds')))
            tree_audit = lambda x: (record['tables'][x.get('candidate_table', x.get('parent_table'))]['actions'][x['ply']].get('gen7_tree') or {}).get('audit_reference')
            for x in record.get('audits', []):
                a = record['tables'][x['candidate_table']]['actions'][x['ply']]
                if x['identical_action'] or not tree_audit(x) or (bot and who.get(a['player']) != bot):
                    continue
                side = 1 if x['actor'] % 2 == declarer % 2 else -1
                tricks = side * (record['tables'][x['candidate_table']]['declarer_tricks'] - record['tables'][x['reference_table']]['declarer_tricks'])
                forks.append(dict(family=d['family'], phase=phase(x['ply']), imps=x['gain_imps'], tricks=tricks, gap=a['selected_pimc_gap'],
                                  depth=x['depth']))
            refused += sum(1 for x in record.get('budget_skips', []) if x.get('reason') == 'shared-compute-budget' and tree_audit(x)
                           and x['candidate_card'] != x['reference_card'])
        if mine and d['opponent'] != d['candidate']:
            for name in mine:
                sign = 1 if name == d['candidate'] else -1
                boards.append(dict(family=d['family'], bot=name, against=d['opponent'] if sign > 0 else d['candidate'],
                                   **{k: (None if v['imps'] is None else sign * v['imps']) for k, v in d['regimes'].items()}))
    return boards, decisions, forks, refused


def tree_rows(rows):
    staged = [r for r in rows if r['staged']]
    used = [r for r in staged if r['consulted']]
    out = dict(searched_decisions=len(rows), in_a_stage=len(staged), consulted=len(used), moved=sum(r['moved'] for r in used),
               over_budget=sum(r['over_budget'] for r in staged))
    if staged:
        out.update(consulted_share=round(len(used) / len(staged), 3), moved_share=round(out['moved'] / len(staged), 3))
    if used:
        seconds, solves = np.array([r['seconds'] for r in used]), np.array([r['solves'] for r in used])
        out.update(seconds_per_search=round(float(seconds.mean()), 3), seconds_p95=round(float(np.quantile(seconds, .95)), 2),
                   seconds_max=round(float(seconds.max()), 2), solves_per_search=round(float(solves.mean()), 1),
                   solves_p95=int(np.quantile(solves, .95)), solves_max=int(solves.max()),
                   tree_share_of_decision_time=round(float(seconds.sum() / max(1e-9, sum(r['decision_seconds'] or 0. for r in rows))), 3))
    return out


def fork_rows(rows):
    if not rows:
        return dict(forks=0)
    fam = [r['family'] for r in rows]
    return dict(forks=len(rows), deals=len(set(fam)), imps_per_fork=clustered([r['imps'] for r in rows], fam),
                tricks_per_fork=clustered([r['tricks'] for r in rows], fam),
                tree_card_better=sum(r['tricks'] > 0 for r in rows), worse=sum(r['tricks'] < 0 for r in rows),
                same=sum(r['tricks'] == 0 for r in rows))


def report(boards, decisions, forks, refused):
    out = dict(match={}, tree={}, audits={})
    for name in sorted({b['bot'] for b in boards}):
        for against in sorted({b['against'] for b in boards if b['bot'] == name}):
            sub = [b for b in boards if b['bot'] == name and b['against'] == against]
            row = dict(boards=len(sub))
            for regime in ('common', 'native'):
                got = [b for b in sub if b.get(regime) is not None]
                row[regime + '_imps_per_board'] = clustered([b[regime] for b in got], [b['family'] for b in got])
            out['match'][f'{name} against {against}'] = row
    for name in sorted({r['bot'] for r in decisions}):
        mine = [r for r in decisions if r['bot'] == name]
        roots = [r for r in mine if r['root']]
        out['tree'][name] = dict(all_tables=tree_rows(mine), root_tables=tree_rows(roots),
                                 by_trick={p: tree_rows([r for r in mine if r['phase'] == p]) for p in PHASES if any(r['phase'] == p and r['staged'] for r in mine)})
    out['audits'] = dict(all=fork_rows(forks), refused_by_budget=refused,
                         by_trick={p: fork_rows([r for r in forks if r['phase'] == p]) for p in PHASES if any(r['phase'] == p for r in forks)},
                         from_root_tables=fork_rows([r for r in forks if r['depth'] == 0]))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--bot')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    out = report(*read(a.episodes, a.bot))
    if a.out:
        a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
