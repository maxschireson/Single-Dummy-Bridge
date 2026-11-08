#!/usr/bin/env python3
"""Report a fixed generation-order prefix while the full experiment continues."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_policy_over_belief import read_run, SETTINGS, ASSIGNMENTS, BELIEF_HASH
from bridge_harness.core import Board, imps
from bridge_harness.runner import replay
from bridge_harness.training import digest
from bridge_harness.report import summarize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--count', type=int, choices=(200,400), required=True)
    p.add_argument('--wait', action='store_true')
    args = p.parse_args()
    root = args.run.resolve()
    protocol, boards = read_run(root)
    paths = [root/'episodes'/f'{digest(b.hands)}.json.gz' for b in boards[:args.count]]
    while True:
        missing = sum(not p.exists() for p in paths)
        if not missing: break
        if not args.wait:
            print(json.dumps(dict(ready=False, required=args.count, missing=missing)), flush=True)
            return
        time.sleep(2)
    records = []
    nonforced = 0
    for board, path in zip(boards[:args.count], paths):
        with gzip.open(path, 'rt') as f: r = json.load(f)
        assert r['status']=='ok' and r['board']==board.to_dict() and r['config']==SETTINGS
        assert r['assignments']==ASSIGNMENTS
        assert all(t['complete'] and t['plies']==52 for t in replay(r))
        assert r['score_difference']==r['tables'][0]['ns_score']-r['tables'][1]['ns_score']
        assert r['imps']==imps(r['score_difference'])
        for table in r['tables']:
            for action in table['actions']:
                assert action['belief_sha256']==BELIEF_HASH and action['sampler']=='auction-weighted-dp'
                if not action.get('forced'):
                    nonforced += 1
                    assert action['samples']==action['dds_calls']==32 and action['batch']
                    assert action['near_tie']==.125 and action['objective']=='tricks'
                    assert action['selected_pimc_gap']<=.125+1e-9
        records.append(r)
    result=summarize(sorted(records,key=lambda r:digest(Board.from_dict(r['board']).hands)))
    result.update(preliminary=True, fixed_final_deals=protocol['count'],
        checkpoint_selection='first N deals in the predeclared generation-order cohort; never completion-order selection',
        interval_caveat='nominal 95% intervals; unadjusted for interim looks; no stopping or model selection',
        nonforced_decisions=nonforced, complete_games=2*len(records),
        failures_so_far=len(list((root/'failures').glob('*.json.gz'))))
    dest=root/'checkpoints';dest.mkdir(exist_ok=True)
    (dest/f'{args.count}-pairs.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['completed_pairs','complete_games','mean_tricks',
        'tricks_cluster_bootstrap_95_interval','mean_imps','cluster_bootstrap_95_interval',
        'wins','ties','losses','failures_so_far','nonforced_decisions']}),flush=True)


if __name__=='__main__':main()
