"""Preflight for a prepared Gen7 alpha run: play scheduled deals through the real runtime path and check them.

Uses ops/gen5_runtime.play (bidding by the frozen bidders, both bidding conditions, swapped rooms,
audit forks, replay and record validation). Nothing is written to the run. Deals are taken for
every scheduled pair that has a Gen7 bot and no BEN, --deals of each.

Checked at every decision of a Gen7 bot: outside the tree's tricks it follows the Gen6 rule (a card
level with the search's best); inside them the record adds up (candidates within the margin, the
value arithmetic, the card played among the candidates kept) and the card is never further from the
search's best than the stage's margin. The report gives what the tree did and what it cost.

  python ops/smoke_gen7.py --run /path/to/prepared/run --out report.json [--deals 2] [--start 0]
"""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.arena_pairs import pair_members
from bridge_harness.corpus import load
from bridge_harness.fork_audit import stream
from bridge_harness.gen7 import ENGINE, gen7_settings
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops import gen5_runtime

SKIP = ('forced', 'replayed_prefix', 'counterfactual_forced', 'fixed_opening_lead')


def pair_at(m, i):
    block = m['pair_schedule'].copy()
    stream(m['seed'], 'pair-block', i // len(block)).shuffle(block)
    return block[i % len(block)]


def check_decision(a, stages):
    """One searched decision of a Gen7 bot. Returns (in a stage, consulted, moved off the search's best, over budget)."""
    assert a['near_tie'] == 0., 'A Gen7 bot searched with a tie window'
    note = a.get('gen7_tree')
    if note is None:
        assert a['selected_pimc_gap'] <= 1e-9, 'Outside the tree, Gen7 chose a card below the best'
        return False, False, False, False
    stage = stages[note['stage']]
    trick = a['ply'] // 4 + 1
    assert a['ply'] > 0 and stage.from_trick <= trick <= stage.to_trick, 'The tree was consulted outside its tricks'
    if not note['consulted']:
        assert a['selected_pimc_gap'] <= 1e-9, 'With no tree answer, Gen7 chose a card below the best'
        return True, False, False, bool(note.get('over_budget'))
    cands = note['candidates']
    best = max(v['utility'] for v in a['estimates'].values())
    assert 2 <= len(cands) <= stage.root_cards and note['layouts'] <= stage.search.layouts
    assert not stage.max_solves or note['solves'] <= stage.max_solves
    for x in cands:
        assert x['gap'] <= stage.root_margin + 1e-9, 'A candidate lies outside the margin'
        assert abs(x['adjusted'] - (best - x['gap'] + stage.trust * (x['tree'] - x['same_layouts']))) <= 1e-6, 'The value does not add up'
    top = max(x['adjusted'] for x in cands)
    kept = {c for x in cands if x['kept'] for c in x['cards']}
    assert all((top - x['adjusted'] <= 1e-9) == x['kept'] for x in cands) and a['card'] in kept, 'The card played is not one the tree kept'
    assert a['selected_pimc_gap'] <= stage.root_margin + 1e-9
    if note.get('audit_reference'):
        assert a.get('reference_card') in note['gen6_cards'], 'The audit reference is not a card the search alone left eligible'
    return True, True, a['selected_pimc_gap'] > 1e-9, False


def smoke(run, out, deals=2, start=0):
    run = Path(run).resolve()
    m = json.loads((run / 'manifest.json').read_text())
    verify_generation(run, m)
    gen7 = {k: gen7_settings(s['gen7']) for k, s in m['bots'].items() if s.get('engine') == ENGINE}
    if not gen7:
        raise ValueError('The run has no Gen7 bot')
    boards = load(run / m['corpus'])
    gen5_runtime.initialize_worker(str(run))
    report = dict(manifest=m['identity'], gen7_bots={k: dict(identity=m['bots'][k]['identity'], settings=m['bots'][k]['gen7'],
                  artifacts=m['bots'][k]['artifact_sha256']) for k in sorted(gen7)}, deals=[])
    wanted = sorted({p for p in m['pair_schedule'] if set(pair_members(p)) & set(gen7) and 'ben' not in pair_members(p)})
    if not wanted:
        raise ValueError('No scheduled pair has a Gen7 bot')
    chosen = []
    for pair in wanted:
        chosen += [i for i in range(start, m['target']) if pair_at(m, i) == pair][:deals]
    phases, tree = {}, dict(in_a_stage=0, consulted=0, moved=0, over_budget=0, tree_forks=0, tree_fork_imps=0, seconds=[], solves=[])
    for index in sorted(chosen):
        started = time.time()
        r = gen5_runtime.play(str(run), m, boards[index].to_dict(), index)      # run_board + validate + timing
        roles = dict(candidate=r['candidate'], opponent=r['opponent'])
        first = next(iter(r['regimes'].values()))
        row = dict(index=index, pair=r['pair'], seconds=time.time() - started, tables=len(r['unique_tables']),
                   gap_forks=sum(len(t.get('gap_forks', [])) for t in r['unique_tables'].values()),
                   gap_enabled_roots=sum('gap_forks' in t for t in r['unique_tables'].values()),
                   imps={k: v['imps'] for k, v in r['regimes'].items()}, root_tables=len(first['tables']),
                   decisions=0, unsearched=0, in_a_stage=0, consulted=0, moved=0, over_budget=0, tree_seconds=0.,
                   tree_forks=0, tree_fork_imps=0)
        for record in r['unique_tables'].values():
            for x in record.get('audits', []):          # audit forks that played the no-tree card against the tree's
                act = record['tables'][x['candidate_table']]['actions'][x['ply']]
                if roles.get(act['player']) in gen7 and (act.get('gen7_tree') or {}).get('audit_reference') and not x['identical_action']:
                    row['tree_forks'] += 1
                    row['tree_fork_imps'] += x['gain_imps']
            for table in record['tables']:
                for a in table['actions']:
                    bot = roles.get(a['player'])
                    if bot not in gen7 or any(a.get(k) for k in SKIP):
                        continue
                    if a.get('unsearched'):
                        assert a['ply'] // 4 + 1 < gen7[bot][0].search_from_trick, 'A card came from the net at a searched trick'
                        row['unsearched'] += 1
                        continue
                    if 'gen6' not in a:
                        continue
                    staged, consulted, moved, over = check_decision(a, gen7[bot][1])
                    row['decisions'] += 1
                    row['in_a_stage'] += staged
                    row['consulted'] += consulted
                    row['moved'] += moved
                    row['over_budget'] += over
                    if consulted:
                        row['tree_seconds'] += a['gen7_tree']['seconds']
                        tree['seconds'].append(a['gen7_tree']['seconds'])
                        tree['solves'].append(a['gen7_tree']['solves'])
                    g = a['gen6']
                    key = g['source'] + (' (trick 1)' if g['trick'] == 1 and g['source'] != 'lead_net' else '')
                    x = phases.setdefault(key, dict(decisions=0, seconds=0., layouts=0, max_seconds=0.))
                    x['decisions'] += 1
                    x['seconds'] += a['seconds']
                    x['layouts'] += a['samples']
                    x['max_seconds'] = max(x['max_seconds'], a['seconds'])
        for k in ('in_a_stage', 'consulted', 'moved', 'over_budget', 'tree_forks', 'tree_fork_imps'):
            tree[k] += row[k]
        report['deals'].append(row)
        print(json.dumps(row), flush=True)
    for x in phases.values():
        x['mean_seconds'] = x['seconds'] / x['decisions']
        x['mean_layouts'] = x['layouts'] / x['decisions']
    report['phases'] = phases
    seconds, solves = sorted(tree.pop('seconds')), sorted(tree.pop('solves'))
    if seconds:
        at = lambda v, q: v[min(len(v) - 1, int(q * len(v)))]
        tree.update(mean_seconds=sum(seconds) / len(seconds), p95_seconds=at(seconds, .95), max_seconds=seconds[-1],
                    mean_solves=sum(solves) / len(solves), p95_solves=at(solves, .95), max_solves=solves[-1])
    report['tree'] = tree
    assert sum(d['decisions'] for d in report['deals']) > 0, 'No Gen7 decision was searched'
    if any(stages for _, stages in gen7.values()):
        assert tree['consulted'] > 0, 'The tree was never consulted: play more deals, or the settings leave it nothing to do'
    atomic_json(out, report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--deals', type=int, default=2, help='deals per scheduled Gen7 pair')
    p.add_argument('--start', type=int, default=0, help='first deal index to consider')
    a = p.parse_args()
    r = smoke(a.run, a.out, a.deals, a.start)
    print(json.dumps(dict(tree=r['tree'], phases=r['phases']), indent=1))
