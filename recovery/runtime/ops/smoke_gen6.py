"""Preflight for a prepared Gen6 run: play scheduled deals through the real runtime path and check them.

Uses ops/gen5_runtime.play (bidding by the frozen bidders, common and native auctions, swapped
rooms, audit forks, replay and record validation). Nothing is written to the run.

  python ops/smoke_gen6.py --run /path/to/prepared/run --out report.json [--deals 2] [--start 0]
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
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops import gen5_runtime


def pair_at(m, i):
    block = m['pair_schedule'].copy()
    stream(m['seed'], 'pair-block', i // len(block)).shuffle(block)
    return block[i % len(block)]


def smoke(run, out, deals=2, start=0):
    run = Path(run).resolve()
    m = json.loads((run / 'manifest.json').read_text())
    verify_generation(run, m)
    gen6 = {k for k, s in m['bots'].items() if s.get('engine') == 'gen6'}
    if not gen6:
        raise ValueError('The run has no Gen6 bot')
    boards = load(run / m['corpus'])
    gen5_runtime.initialize_worker(str(run))
    report = dict(manifest=m['identity'], gen6_bots={k: dict(identity=m['bots'][k]['identity'], settings=m['bots'][k]['gen6'],
                  artifacts=m['bots'][k]['artifact_sha256']) for k in sorted(gen6)}, deals=[])
    phases = {}
    chosen = [i for i in range(start, m['target']) if set(pair_members(pair_at(m, i))) & gen6 and 'ben' not in pair_members(pair_at(m, i))][:deals]
    if not chosen:
        raise ValueError('No scheduled deal has a Gen6 bot')
    for index in chosen:
        started = time.time()
        r = gen5_runtime.play(str(run), m, boards[index].to_dict(), index)      # run_board + validate + timing
        roles = dict(candidate=r['candidate'], opponent=r['opponent'])
        row = dict(index=index, pair=r['pair'], seconds=time.time() - started, tables=len(r['unique_tables']),
                   native_auction_differs=[r['bidding'][f'native/{room}']['calls'] != r['bidding'][f'common/{room}']['calls'] for room in (0, 1)],
                   common_imps=r['regimes']['common']['imps'], native_imps=r['regimes']['native']['imps'], decisions=0, tie_breaks=0)
        for record in r['unique_tables'].values():
            for table in record['tables']:
                for a in table['actions']:
                    if roles.get(a['player']) not in gen6 or a.get('forced') or a.get('replayed_prefix') or a.get('counterfactual_forced') or a.get('fixed_opening_lead'):
                        continue
                    g = a['gen6']
                    assert a['near_tie'] == 0. and a['selected_pimc_gap'] <= 1e-9, 'Gen6 chose a card below the best'
                    proposal = a.get('proposal_probabilities', a['behavior_probabilities'])
                    assert max(a['estimates'][c]['gap_to_best'] for c, p in proposal.items() if p > 0) <= 1e-9
                    if a.get('selector'):
                        assert sum(p > 0 for p in proposal.values()) >= 2, 'policy consulted without a tie'
                    row['decisions'] += 1
                    row['tie_breaks'] += bool(a.get('selector'))
                    key = g['source'] + (' (trick 1)' if g['trick'] == 1 and g['source'] != 'lead_net' else '')
                    x = phases.setdefault(key, dict(decisions=0, seconds=0., layouts=0, max_seconds=0.))
                    x['decisions'] += 1
                    x['seconds'] += a['seconds']
                    x['layouts'] += a['samples']
                    x['max_seconds'] = max(x['max_seconds'], a['seconds'])
        report['deals'].append(row)
        print(json.dumps(row), flush=True)
    for x in phases.values():
        x['mean_seconds'] = x['seconds'] / x['decisions']
        x['mean_layouts'] = x['layouts'] / x['decisions']
    report['phases'] = phases
    settings = [m['bots'][k]['gen6'] for k in gen6]
    expected = set()
    for s in settings:
        expected |= {dict(lead_net='lead_net', scorer='scorer', gen5='gen5')[s['lead_source']], s['early_source']}
        if s['list_from_trick'] <= 13:
            expected.add('deal_list')
    seen = {k.split(' ')[0] for k in phases}
    assert expected <= seen, f'Phases not exercised: {sorted(expected - seen)}'
    assert sum(d['tie_breaks'] for d in report['deals']) > 0, 'No policy tie-break occurred'
    atomic_json(out, report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--deals', type=int, default=2)
    p.add_argument('--start', type=int, default=0, help='first deal index to consider')
    a = p.parse_args()
    print(json.dumps(smoke(a.run, a.out, a.deals, a.start)['phases'], indent=1))
