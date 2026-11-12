"""Native DDS and promoted-network smoke for both new matchup types."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import generate
from bridge_harness.gen5r import load_plan,make_bots
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.runner import play_table,replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.loop_registry import sha

def smoke(source,out):
    old=json.loads((source/'manifest.json').read_text());bots=make_bots(old,load_plan())
    for key in ('5R32','5R192','5-32'):
        for artifact,expected in bots[key]['artifact_sha256'].items():
            if sha(source/bots[key][artifact])!=expected:raise ValueError('Changed model')
    report=dict(schema='gen5r-native-smoke-v1',source_manifest=old['identity'],models=old['bots']['5']['artifact_sha256'],tables=[])
    for a,b in [('5R32','5-32'),('5R32','5R192')]:
        board=next(generate(1,202611101345));players={k:ArenaPlayer(bots[k],source) for k in (a,b)}
        try:
            for swapped in (0,1):
                assignments=[a if s%2==swapped else b for s in range(4)]
                result=play_table(board,assignments,players,seed=17,rng_group='gen5r-smoke')
                if result['status']!='ok':raise RuntimeError(result)
                replay(dict(board=board.to_dict(),tables=[result]))
                by_bot=defaultdict(lambda:dict(large=0,small=0,forced=0,solved=[],pools=[],calibration_success=0,selector_calls=0))
                for action in result['actions']:
                    k=action['player'];d=by_bot[k]
                    if action.get('selector'):d['selector_calls']+=1
                    if action.get('forced'):d['forced']+=1;continue
                    cfg=bots[k].get('layout_reduction');large=action['ply']<16 and cfg is not None
                    if large:
                        q=action['layout_reduction'];d['large']+=1;d['solved'].append(action['samples']);d['pools'].append(q['pool'])
                        assert q['pool']==4*bots[k]['samples'] and action['samples']<=bots[k]['samples']
                        assert min(q['actual_weights'])>=0 and abs(sum(q['actual_weights'])-1)<1e-8
                        d['calibration_success']+=int(q['calibration']['success'])
                    else:
                        d['small']+=1
                        assert 'layout_reduction' not in action and action['samples']==bots[k]['samples']
                row=dict(pair=a+'~'+b,swapped=swapped,actions=len(result['actions']),seconds=result['seconds'],by_bot=dict(by_bot))
                report['tables'].append(row);print(json.dumps(row),flush=True)
        finally:
            for p in players.values():p.close()
    atomic_json(out,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();smoke(a.source,a.out)
