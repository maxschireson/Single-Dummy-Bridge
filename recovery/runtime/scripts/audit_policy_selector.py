#!/usr/bin/env python3
"""Replay all frozen selector games and enforce the decision budget/window."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board
from bridge_harness.runner import replay
from bridge_harness.training import digest,split_for
from bridge_harness.report import summarize


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    protocol=json.loads((args.run/'protocol.json').read_text());expected=set(protocol['play_deal_ids'])
    totals=Counter();controls={};summaries={}
    for control in ('random','pimc-best'):
        ids=set();counts=Counter();gap_sum=0.;records=[]
        for path in sorted((args.run/control).glob('*.json.gz')):
            with gzip.open(path,'rt') as f:r=json.load(f)
            b=Board.from_dict(r['board']);did=digest(b.hands)
            assert did in expected and did not in ids and split_for(b)=='test';ids.add(did)
            assert r['status']=='ok' and r['config']['control']==control
            records.append(r)
            assert r['config']['samples']==32 and r['config']['batch'] and r['config']['objective']=='tricks'
            replay(r)
            assert r['assignments']==[['selector32','control32','selector32','control32'],['control32','selector32','control32','selector32']]
            for table in r['tables']:
                assert len(table['actions'])==52;totals['games']+=1
                for action in table['actions']:
                    totals['plies']+=1
                    if action.get('forced'):continue
                    assert action['dds_calls']==action['samples']==32 and action['batch']
                    totals['nonforced']+=1;totals['dds_world_solves']+=32
                    if action['player']=='selector32':
                        assert action['selected_pimc_gap']<=.125+1e-9
                        if action.get('selector'):
                            counts['selector_decisions']+=1
                            assert action['proposal_probabilities'][action['card']]>0
                            counts['selected_below_top_pimc']+=action['selected_pimc_gap']>1e-9
                            gap_sum+=action['selected_pimc_gap']
                    elif control=='pimc-best':assert action['selected_pimc_gap']<=1e-9
            # Before their first different play, both tables must have the same
            # sampled PIMC estimates, irrespective of which policy is acting.
            for left,right in zip(*(t['actions'] for t in r['tables'])):
                if not left.get('forced'):
                    assert left['estimates']==right['estimates'];counts['matched_prefix_estimates']+=1
                if left['card']!=right['card']:break
        assert ids==expected
        summaries[control]=summarize(records)
        assert summaries[control]['independent_clusters']==len(expected)
        controls[control]=dict(counts,mean_selector_pimc_gap=gap_sum/max(1,counts['selector_decisions']))
    assert totals['games']==800
    result=dict(validated=True,independent_deals=len(expected),failures=0,**totals,controls=controls)
    (args.run/'play-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    # Recompute in deterministic deal-hash order and cluster by cards, not
    # display board numbers that can repeat between source chunks.
    path=args.run/'play-summary.json';s=json.loads(path.read_text());s.update(summaries)
    path.write_text(json.dumps(s,indent=2))


if __name__=='__main__':main()
