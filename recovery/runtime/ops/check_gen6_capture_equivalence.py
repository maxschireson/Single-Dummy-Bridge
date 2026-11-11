"""Real-net preflight with gap capture on/off; require the original games and audits to agree."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.selfplay import atomic_json
from ops import gen5_runtime,smoke_gen6


def original_games(episode):
    result={}
    for key,record in episode['unique_tables'].items():
        tables=[t for t in record['tables'] if t.get('fork_kind')!='gap']
        result[key]=dict(board=record['board'],assignments=record['assignments'],
            tables=[dict(node=t.get('node'),depth=t.get('depth'),ns_score=t['ns_score'],declarer_tricks=t.get('declarer_tricks'),
                         actions=[{k:a[k] for k in ('ply','seat','controller','player','card','replayed_prefix','counterfactual_forced') if k in a} for a in t['actions']]) for t in tables],
            audits=[{k:v for k,v in e.items() if k not in ('rollout_cpu','estimated_cpu')} for e in record['audits']])
    return dict(pair=episode['pair'],family=episode['family'],regimes=episode['regimes'],
                bidding={k:{x:v for x,v in b.items() if 'second' not in x and 'cpu' not in x} for k,b in episode['bidding'].items()},games=result)


def check(capture,control,out,deals=3):
    manifests=[json.loads((run/'manifest.json').read_text()) for run in (capture,control)]
    on,off=deepcopy(manifests)
    assert on.pop('gap_fork')['per_band']>0 and not off.get('gap_fork')
    for m in (on,off):
        for k in ('identity','created_epoch','campaign','plan_sha256'):m.pop(k,None)
    assert on==off,'Prepared runs differ beyond capture settings'
    original=gen5_runtime.play;episodes={};reports={}
    try:
        for name,run in (('capture',capture),('control',control)):
            episodes[name]=[]
            def record(*args,**kwargs):
                result=original(*args,**kwargs);episodes[name].append(result);return result
            gen5_runtime.play=record
            reports[name]=smoke_gen6.smoke(run,run/'preflight.json',deals)
        assert len(episodes['capture'])==len(episodes['control'])==deals
        for a,b in zip(episodes['capture'],episodes['control']):
            assert original_games(a)==original_games(b),f"Original root/audit game changed at index {a['index']}"
        result=dict(status='passed',capture_manifest=manifests[0]['identity'],control_manifest=manifests[1]['identity'],
                    deals=deals,root_tables=sum(len(e['unique_tables']) for e in episodes['capture']),
                    audit_fork_tables=sum(sum(t.get('depth',0)>0 and t.get('fork_kind')!='gap' for t in r['tables']) for e in episodes['capture'] for r in e['unique_tables'].values()),
                    gap_forks=sum(e.get('gap_fork_count',0) for e in episodes['capture']),
                    checks=['root cards and scores','audit fork cards and scores','audit events excluding CPU','auctions and regime scores'],preflights=reports)
        atomic_json(out,result);return result
    finally:gen5_runtime.play=original


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--control',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--deals',type=int,default=3);a=p.parse_args()
    r=check(a.capture,a.control,a.out,a.deals);print(json.dumps({k:v for k,v in r.items() if k!='preflights'}))
