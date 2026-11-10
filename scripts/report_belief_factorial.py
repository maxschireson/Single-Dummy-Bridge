"""Paired family comparisons for the frozen 2x2 dense belief experiment."""
import argparse,gzip,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.screen_attention_belief import save_json
from bridge_harness.belief_capacity import sha

METRICS={'nll':(2,3),'weighted_nll':(0,1),'accuracy':(4,3),'brier':(5,3),
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
        caveat='One seed, conditional on this initialization. Family SE does not capture retraining uncertainty. Selected-epoch contrasts are descriptive after selection; primary contrasts use fixed epoch 3. No arena or reserved test evaluation.')
    for name,r in results.items():
        summary['cells'][name]=dict(parameters=r['parameters'],best_epoch=r['best_epoch'],selected=r['selected']['domains'],
            selected_score=r['selected']['score'],last=r['history'][-1]['metrics']['domains'],last_score=r['history'][-1]['metrics']['score'],
            epoch_seconds=[x['seconds'] for x in r['history']],epochs=[dict(epoch=x['epoch'],score=x['metrics']['score'],domains=x['metrics']['domains']) for x in r['history']],
            initial_max_error=r['initial_max_error'],export_max_error=r['export_max_error'],selected_sha256=r['selected_sha256'],
            training_positions=configs[name]['training_positions'],training_card_targets=configs[name]['training_card_targets'],training_families=configs[name]['training_families'])
    for phase in ('last','selected'):
        maps={}
        for name,r in results.items():
            m=r['history'][-1]['metrics'] if phase=='last' else r['selected'];f=a.run/name/m['family_file']
            if sha(f)!=m['family_file_sha256']:raise ValueError('Family metrics changed')
            maps[name]=json.loads(gzip.decompress(f.read_bytes()))['families']
        summary['comparisons'][phase]={k:contrasts(maps,v) for k,v in CONTRASTS.items()}
    save_json(a.run/'summary.json',summary)
    lines=['# Dense belief: size × consequence weighting','',
        'Four matched continuations from the v4 prediction function, using fresh AdamW in all four cells. '
        'The 308,726-parameter network is compared with a function-preserving widening to 682,614 parameters. '
        'Every cell receives the identical frozen clean dataset, three epochs, row ordering, learning rate, '
        'domain/family weighting and seed. Only dense width and card-level loss weights vary. '
        'The previous v5 run inherited Adam state; these matched controls deliberately reset it.','',
        'Primary comparisons use the final third epoch. Checkpoint selection uses the same frozen composite '
        'objective for every cell, with unchanged v4 eligible. The tables also report each selected checkpoint.','']
    for phase,title in [('last','Fixed epoch 3'),('selected','Selected checkpoints')]:
        lines+=['## '+title,'','| Cell | Epoch | Composite | Recent NLL | Weighted NLL | Consequential-card NLL | Accuracy | Brier |','|---|---:|---:|---:|---:|---:|---:|---:|']
        b=baseline['domains']['recent/play'];lines+=[f"| v4 baseline | 0 | {baseline['score']:.8f} | {b['nll']:.8f} | {b['weighted_nll']:.8f} | {b['upweighted_card_nll']:.8f} | {b['accuracy']:.4%} | {b['brier']:.8f} |"]
        for name,c in summary['cells'].items():
            m=c[phase]['recent/play'];score=c[phase+'_score'];epoch=3 if phase=='last' else c['best_epoch']
            lines+=[f"| {name} | {epoch} | {score:.8f} | {m['nll']:.8f} | {m['weighted_nll']:.8f} | {m['upweighted_card_nll']:.8f} | {m['accuracy']:.4%} | {m['brier']:.8f} |"]
        lines+=['','Recent clean-play paired effects; negative NLL deltas favor the first/additive treatment.','',
            '| Contrast | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |',
            '|---|---:|---:|---:|']
        for name,comp in summary['comparisons'][phase].items():
            m=comp['recent|play'];values=[f"{m[k]['delta']:+.8f} ± {m[k]['se']:.8f}" for k in ('nll','weighted_nll','upweighted_card_nll')]
            lines+=['| '+name+' | '+' | '.join(values)+' |']
        lines+=['']
    lines+=['## Fit and checks','',summary['caveat'],'',
        '| Cell | Epoch seconds | Initial max logit error vs v4 | Export max error |','|---|---|---:|---:|']
    for name,c in summary['cells'].items():
        lines+=[f"| {name} | {', '.join(f'{x:.1f}' for x in c['epoch_seconds'])} | {c['initial_max_error']:.3g} | {c['export_max_error']:.3g} |"]
    c=next(iter(summary['cells'].values()))
    lines+=['',f"Each fit: {c['training_positions']:,} positions, {c['training_card_targets']:,} uncertain-card targets, {c['training_families']:,} training families. "
            'Recent validation: 192 usable families, 47,004 uncertain-card targets, 1,687 upweighted targets. '
            'All 186 reserved test families remain unprepared and unevaluated. Every trajectory involving the bad v4/4p policy was excluded; 4b was retained.','',
            'Full domain metrics, all epoch curves, primary factorial contrasts and selected-checkpoint contrasts are in the companion summary JSON.']
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:{'best_epoch':v['best_epoch'],'selected_score':v['selected_score'],'last_score':v['last_score'],'seconds':sum(v['epoch_seconds'])} for k,v in summary['cells'].items()},indent=2))

if __name__=='__main__':main()
