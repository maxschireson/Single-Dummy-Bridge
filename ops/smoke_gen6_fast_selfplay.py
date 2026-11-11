"""Real-model fast self-play and BEN16 preflight through collector/export paths."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops import gen5_runtime
from ops.smoke_gen6 import pair_at


def smoke(run):
    m=json.loads((run/'manifest.json').read_text());verify_generation(run,m)
    assert m['pair_weights']=={'6-32~6-32':37,'6-32~ben':3}
    gen5_runtime.initialize_worker(str(run));boards=load(run/m['corpus']);seen=[];reports=[]
    for wanted,n in [('6-32~6-32',2),('6-32~ben',1)]:
        for i in range(m['target']):
            if pair_at(m,i)!=wanted:continue
            e=gen5_runtime.play(str(run),m,boards[i].to_dict(),i)
            gen5_runtime.validate(e,m,i)
            gaps=sum(len(r.get('gap_forks',[])) for r in e['unique_tables'].values())
            if wanted=='6-32~6-32':
                assert set(e['regimes'])=={'self'} and e['regimes']['self']['imps'] is None
                assert len(e['unique_tables'])==1
                actions=next(iter(e['unique_tables'].values()))['tables'][0]['actions']
                if not actions:continue
                for a in actions:
                    if a.get('gen6') and not a.get('forced') and a['gen6']['source']!='gen5':
                        assert a['guess_size']>=0 and 'best_share' in next(iter(a['estimates'].values()))
            else:
                assert gaps==0 and all(not r['audits'] for r in e['unique_tables'].values())
                actions=[a for r in e['unique_tables'].values() for a in r['tables'][0]['actions'] if a.get('engine')=='BEN']
                if not actions:continue
                assert all(a['configured_opening_lead_samples']==a['configured_play_samples']==16 for a in actions)
            reports.append(dict(index=i,pair=wanted,root_tables=len(e['unique_tables']),gap_forks=gaps))
            seen.append(e);n-=1
            if not n:break
        assert n==0,'Required preflight pairing not exercised'
    assert sum(r['gap_forks'] for r in reports)>0
    # Exercise actual exporter/receipt handling without putting smoke games in production.
    from tempfile import TemporaryDirectory
    from ops.export_gen5 import export
    from ops.gen5_runtime import receipt
    with TemporaryDirectory(dir=run.parent) as directory:
        temp=Path(directory);(temp/'episodes').mkdir();(temp/'receipts').mkdir()
        for name in ('manifest.json','heartbeat.json'):(temp/name).write_bytes((run/name).read_bytes())
        for e in seen:
            path=temp/'episodes'/f"{e['index']:06d}.json.gz";atomic_json(path,e,compressed=True)
            atomic_json(temp/'receipts'/f"{e['index']:06d}.json",receipt(e,path))
        export(temp,temp/'publication')
        d=json.loads((temp/'publication/arena/data.json').read_text())
        assert d['completed']==3 and d['views']['0']['groups']['6-32~6-32']['mean'] is None
    result=dict(status='passed',manifest=m['identity'],deals=reports,checks=['actor identities','replay validation','null self-play scores','gap capture','BEN16 budget and fork exclusion','receipt/export'])
    atomic_json(run/'preflight.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();print(json.dumps(smoke(a.run)))
