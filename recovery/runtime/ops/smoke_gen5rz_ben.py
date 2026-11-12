"""Verify zero-margin policy decisions in full native, replay-checked games."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import generate
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.runner import play_table,replay
from bridge_harness.selfplay import atomic_json
from ops.prepare_gen5rz_ben import make_bots,load_plan

def smoke(source,out):
    old=json.loads((source/'manifest.json').read_text());bots=make_bots(old,load_plan());report=dict(source_manifest=old['identity'],models=bots['5RZ192']['artifact_sha256'],tables=[])
    board=next(generate(1,202611101718));players={key:ArenaPlayer(bots[key],source) for key in ['5RZ192','5R32']}
    try:
        for room in [0,1]:
            result=play_table(board,['5RZ192' if s%2==room else '5R32' for s in range(4)],players,seed=19,rng_group='5rz-smoke')
            assert result['status']=='ok';replay(dict(board=board.to_dict(),tables=[result]))
            rows=[a for a in result['actions'] if a['player']=='5RZ192' and not a.get('forced')]
            for a in rows:
                assert a.get('near_tie')==0. and a['selected_pimc_gap']<=1e-9
                proposal=a.get('proposal_probabilities',a.get('behavior_probabilities',{}))
                if a.get('selector'):
                    assert sum(p>0 for p in proposal.values())>=2
                    assert max(a['estimates'][c]['gap_to_best'] for c,p in proposal.items() if p>0)<=1e-9
                if a.get('layout_reduction'):assert a['layout_reduction']['pool']==768 and a['samples']<=192
                else:assert a['samples']==192
            row=dict(swapped=room,actions=len(result['actions']),z_decisions=len(rows),z_policy_tie_breaks=sum(bool(a.get('selector')) for a in rows),max_z_gap=max(a['selected_pimc_gap'] for a in rows),large=sum('layout_reduction' in a for a in rows),seconds=result['seconds'])
            report['tables'].append(row);print(json.dumps(row),flush=True)
        assert sum(t['z_policy_tie_breaks'] for t in report['tables'])>0
    finally:
        for p in players.values():p.close()
    atomic_json(out,report);return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();smoke(a.source,a.out)
