import argparse,gzip,json,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--pair',required=True);p.add_argument('--out',required=True);a=p.parse_args()
sys.path.insert(0,str(Path.cwd()))
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.gen7 import gen7_settings
from bridge_harness.selfplay import atomic_json
from ops import gen5_runtime
from ops.smoke_gen7 import pair_at,check_decision,SKIP
rundir=Path(a.run);m=json.loads((rundir/'manifest.json').read_text());verify_generation(rundir,m)
index=next(i for i in range(m['target']) if pair_at(m,i)==a.pair)
b=load(rundir/m['corpus'])[index];gen5_runtime.initialize_worker(str(rundir));started=time.time()
r=gen5_runtime.play(str(rundir),m,b.to_dict(),index)
roles={'candidate':r['candidate'],'opponent':r['opponent']};checked=guess=0;samples=[];labels=set()
for e in r['unique_tables'].values():
    labels.add(e['board'].get('auction_source'))
    assert str(e['board'].get('auction_source')).startswith('systems:')
    for table in e['tables']:
        for x in table['actions']:
            bot=roles[x['player']]
            if m['bots'][bot].get('engine')=='ben':
                if 'reported_samples' in x:samples.append(x['reported_samples'])
                assert x.get('configured_play_samples',m['bots'][bot]['samples'])==m['bots'][bot]['samples']
            elif m['bots'][bot].get('engine')=='gen7' and not any(x.get(k) for k in SKIP) and not x.get('unsearched') and 'gen6' in x:
                check_decision(x,gen7_settings(m['bots'][bot]['gen7'])[1]);checked+=1
                if 'guess_size' in x:guess+=1
                if 'guess_size' in x.get('gen6',{}):guess+=1
forks=sum(len(e.get('gap_forks',[])) for e in r['unique_tables'].values())
ben=any(m['bots'][x].get('engine')=='ben' for x in roles.values())
if ben:
    assert forks==0 and all(not e.get('audits') for e in r['unique_tables'].values())
    budget=next(m['bots'][x]['samples'] for x in roles.values() if m['bots'][x].get('engine')=='ben')
    assert samples and max(samples)==budget and all(0 < n <= budget for n in samples),samples
else:assert forks>0
assert checked>0
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
with gzip.open(out.with_suffix('.record.json.gz'),'wt') as f:json.dump(r,f)
report=dict(manifest=m['identity'],pair=r['pair'],index=index,checked=checked,gap_forks=forks,guess_decisions=guess,seconds=time.time()-started,auction_sources=sorted(labels),reported_samples=sorted(set(samples)),sample_interpretation="Configured budget reached; late compatible sets may be smaller",validated=True)
atomic_json(out,report);print(json.dumps(report),flush=True)
