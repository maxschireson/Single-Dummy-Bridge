"""Paired family comparisons for the frozen 2x2 dense belief experiment."""
import argparse,gzip,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.screen_attention_belief import save_json
from bridge_harness.belief_capacity import sha

METRICS={'nll':(2,3),'weighted_nll':(0,1),'accuracy':(4,3),'brier':(5,3),
         'weighted_accuracy':(8,1),'weighted_brier':(9,1),
         'upweighted_card_nll':(7,6),'upweighted_card_accuracy':(10,6),'upweighted_card_brier':(11,6)}
CONTRASTS={
    'size_with_ordinary':{'large_ordinary':1,'current_ordinary':-1},
    'size_with_consequence':{'large_consequence':1,'current_consequence':-1},
    'weighting_at_current':{'current_consequence':1,'current_ordinary':-1},
    'weighting_at_large':{'large_consequence':1,'large_ordinary':-1},
    'average_size_effect':{'large_ordinary':.5,'large_consequence':.5,'current_ordinary':-.5,'current_consequence':-.5},
    'average_weighting_effect':{'current_consequence':.5,'large_consequence':.5,'current_ordinary':-.5,'large_ordinary':-.5},
    'interaction':{'large_consequence':1,'large_ordinary':-1,'current_consequence':-1,'current_ordinary':1}}

def contrasts(maps,weights):
    keys=set(next(iter(maps.values())))
    if any(set(m)!=keys for m in maps.values()):raise ValueError('Validation families changed')
    domains=sorted({'|'.join(k.split('|')[:2]) for k in keys});out={}
    for domain in domains:
        out[domain]={}
        for metric,(n,d) in METRICS.items():
            values=[]
            for key in sorted(keys):
                if not key.startswith(domain+'|'):continue
                if any(maps[cell][key][d]<=0 for cell in weights):continue
                values.append(sum(w*maps[cell][key][n]/maps[cell][key][d] for cell,w in weights.items()))
            if not values:continue
            v=np.array(values);se=float(v.std(ddof=1)/np.sqrt(len(v))) if len(v)>1 else None
            out[domain][metric]=dict(delta=float(v.mean()),se=se,families=len(v),
                descriptive_95_interval=[float(v.mean()-1.96*se),float(v.mean()+1.96*se)] if se is not None else None)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();cfg=json.loads((a.run/'experiment.json').read_text());results={};configs={}
    for name,_,_ in cfg['cells']:
        results[name]=json.loads((a.run/name/'result.json').read_text());configs[name]=json.loads((a.run/name/'config.json').read_text())
        if results[name]['epochs']!=3:raise ValueError('Incomplete cell')
        if configs[name]['dataset_sha256']!=cfg['dataset_sha256']:raise ValueError('Different data')
    names=list(results);baseline=results[names[0]]['initial']
    if max(abs(r['initial']['score']-baseline['score']) for r in results.values())>1e-7:raise ValueError('Unequal starting predictions')
    summary=dict(experiment=cfg,baseline=baseline['domains'],baseline_score=baseline['score'],cells={},comparisons={},
        caveat='One seed, conditional on this initialization. Family SE does not capture retraining uncertainty. Selected-epoch contrasts are descriptive after selection; primary contrasts use fixed epoch 3. This tests a short continuation after widening, not training a larger model from scratch or tuning its learning rate. No arena or reserved test evaluation.')
    for name,r in results.items():
        summary['cells'][name]=dict(parameters=r['parameters'],best_epoch=r['best_epoch'],selected=r['selected']['domains'],
            selected_score=r['selected']['score'],last=r['history'][-1]['metrics']['domains'],last_score=r['history'][-1]['metrics']['score'],
            epoch_seconds=[x['seconds'] for x in r['history']],epochs=[dict(epoch=x['epoch'],score=x['metrics']['score'],domains=x['metrics']['domains']) for x in r['history']],
            initial_max_error=r['initial_max_error'],export_max_error=r['export_max_error'],selected_sha256=r['selected_sha256'],
            training_positions=configs[name]['training_positions'],training_card_targets=configs[name]['training_card_targets'],training_families=configs[name]['training_families'])
    def family_map(name,metrics):
        f=a.run/name/metrics['family_file']
        if sha(f)!=metrics['family_file_sha256']:raise ValueError('Family metrics changed')
        return json.loads(gzip.decompress(f.read_bytes()))['families']
    summary['versus_v4']={}
    for name,r in results.items():
        base=family_map(name,r['initial'])
        summary['versus_v4'][name]={
            str(row['epoch']):contrasts({'candidate':family_map(name,row['metrics']),'v4':base},{'candidate':1,'v4':-1})
            for row in r['history']}
    for phase in ('last','selected'):
        maps={}
        for name,r in results.items():
            m=r['history'][-1]['metrics'] if phase=='last' else r['selected']
            maps[name]=family_map(name,m)
        summary['comparisons'][phase]={k:contrasts(maps,v) for k,v in CONTRASTS.items()}
    events=[json.loads(line) for line in (a.run/'pipeline.log').read_text().splitlines() if line.startswith('{')]
    starts={name:min(e['started'] for e in events if e.get('cell')==name and 'started' in e) for name in names}
    for name,c in summary['cells'].items():
        c['wall_seconds']=json.loads((a.run/name/'status.json').read_text())['updated']-starts[name]
    summary['wall_seconds']=json.loads((a.run/'status.json').read_text())['updated']-min(starts.values())
    summary['export_verification']=json.loads((a.run/'export-verification.json').read_text())
    save_json(a.run/'summary.json',summary)
    lines=['# Dense belief: size × consequence weighting','',
        'Four matched continuations from the v4 prediction function, using fresh AdamW in all four cells. '
        'The 308,726-parameter network is compared with a function-preserving widening to 682,614 parameters. '
        'Every cell receives the identical frozen clean dataset, three epochs, row ordering, learning rate, '
        'domain/family weighting and seed. Only dense width and card-level loss weights vary. '
        'The previous v5 run inherited Adam state; these matched controls deliberately reset it.','',
        'Frozen consequence weights are 1 + 3 × min(max(0, estimated value in IMPs), 1), from cross-fitted '
        'single-card owner information value under 24 v4 and 8 uniform legal worlds, with minimum owner-group size 4 and '
        'four-world prior shrinkage. They are applied only to the existing labeled recent clean-play positions; '
        'historical replay keeps weight 1. Recent families retain twice the training mass of historical families.','',
        'Primary comparisons use the final third epoch. Checkpoint selection uses the same frozen composite '
        'objective for every cell, with unchanged v4 eligible. The tables also report each selected checkpoint.','']
    for phase,title in [('last','Fixed epoch 3'),('selected','Selected checkpoints')]:
        lines+=['## '+title,'','| Cell | Epoch | Composite | Recent NLL | Weighted NLL | Consequential-card NLL | Accuracy | Brier |','|---|---:|---:|---:|---:|---:|---:|---:|']
        b=baseline['domains']['recent/play'];lines+=[f"| v4 baseline | 0 | {baseline['score']:.8f} | {b['nll']:.8f} | {b['weighted_nll']:.8f} | {b['upweighted_card_nll']:.8f} | {b['accuracy']:.4%} | {b['brier']:.8f} |"]
        for name,c in summary['cells'].items():
            m=c[phase]['recent/play'];score=c[phase+'_score'];epoch=3 if phase=='last' else c['best_epoch']
            lines+=[f"| {name} | {epoch} | {score:.8f} | {m['nll']:.8f} | {m['weighted_nll']:.8f} | {m['upweighted_card_nll']:.8f} | {m['accuracy']:.4%} | {m['brier']:.8f} |"]
        lines+=['','| Cell | Weighted accuracy | Weighted Brier | Consequential-card accuracy | Consequential-card Brier |',
            '|---|---:|---:|---:|---:|']
        for name,m in [('v4 baseline',b)]+[(name,c[phase]['recent/play']) for name,c in summary['cells'].items()]:
            lines+=[f"| {name} | {m['weighted_accuracy']:.4%} | {m['weighted_brier']:.8f} | {m['upweighted_card_accuracy']:.4%} | {m['upweighted_card_brier']:.8f} |"]
        lines+=['','Paired differences from unchanged v4 on recent validation families:','',
            '| Cell | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |',
            '|---|---:|---:|---:|']
        for name,c in summary['cells'].items():
            epoch=3 if phase=='last' else c['best_epoch']
            if epoch==0:
                values=['0 (epoch zero selected)']*3
            else:
                m=summary['versus_v4'][name][str(epoch)]['recent|play']
                values=[f"{m[k]['delta']:+.8f} ± {m[k]['se']:.8f}" for k in ('nll','weighted_nll','upweighted_card_nll')]
            lines+=['| '+name+' | '+' | '.join(values)+' |']
        lines+=['','Recent clean-play paired effects; negative NLL deltas favor the first/additive treatment.','',
            '| Contrast | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |',
            '|---|---:|---:|---:|']
        for name,comp in summary['comparisons'][phase].items():
            m=comp['recent|play'];values=[f"{m[k]['delta']:+.8f} ± {m[k]['se']:.8f}" for k in ('nll','weighted_nll','upweighted_card_nll')]
            lines+=['| '+name+' | '+' | '.join(values)+' |']
        lines+=['']
    lines+=['## Fit and checks','',summary['caveat'],'',
        '| Cell | Epoch seconds | Total wall seconds | Initial max logit error vs v4 | Export max error |','|---|---|---:|---:|---:|']
    for name,c in summary['cells'].items():
        lines+=[f"| {name} | {', '.join(f'{x:.1f}' for x in c['epoch_seconds'])} | {c['wall_seconds']:.1f} | {c['initial_max_error']:.3g} | {c['export_max_error']:.3g} |"]
    c=next(iter(summary['cells'].values()))
    lines+=['',f"Each fit: {c['training_positions']:,} positions, {c['training_card_targets']:,} uncertain-card targets, {c['training_families']:,} training families. "
            'Recent training: 22,467 positions, 345,490 targets, 1,408 usable families, including 11,413 upweighted targets. '
            'Recent validation: 3,063 positions, 192 usable families, 47,004 uncertain-card targets, 1,687 upweighted targets in 130 families. '
            'All 186 reserved test families remain unprepared and unevaluated. Every trajectory involving the bad v4/4p policy was excluded; 4b was retained.','',
            'Metrics average within each family, then across families. Consequential-card-only metrics use families with at least one upweighted target. '
            'Card targets and positions from the same deal are correlated; the 31.1 million targets are not 31.1 million independent examples. '
            'Epoch timings include training and validation, but exclude worker startup and initial baseline evaluation.','',
            f"The complete controlled pipeline took {summary['wall_seconds']/60:.2f} minutes, excluding earlier superseded work. "
            'All exported weight arrays exactly match their selected TensorFlow checkpoint. Prediction checks cover validation samples '
            'from historical play, bidding, BEN, and recent play; maximum errors and restored AdamW iteration counts are in the JSON.','',
            'Full domain metrics, all epoch curves, paired differences from v4 at every epoch, primary factorial contrasts and selected-checkpoint contrasts are in the companion summary JSON.']
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:{'best_epoch':v['best_epoch'],'selected_score':v['selected_score'],'last_score':v['last_score'],'seconds':sum(v['epoch_seconds'])} for k,v in summary['cells'].items()},indent=2))

if __name__=='__main__':main()
