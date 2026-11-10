"""Matched architecture contrasts on frozen family validation records."""
import argparse,gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import sha
from bridge_harness.selfplay import atomic_json
from scripts.report_belief_factorial import contrasts

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    cfg=json.loads((a.run/'experiment.json').read_text());results={n:json.loads((a.run/n/'result.json').read_text()) for n in ['dense','attention']}
    if any(r['epochs']!=cfg['epochs'] or r['dataset_sha256']!=cfg['dataset_sha256'] or r['parent_sha256']!=cfg['parent_sha256'] for r in results.values()):raise ValueError('Different/incomplete fits')
    if abs(results['dense']['initial']['score']-results['attention']['initial']['score'])>1e-7:raise ValueError('Unequal starting predictions')
    def fm(n,m):
        path=a.run/n/m['family_file']
        if sha(path)!=m['family_file_sha256']:raise ValueError('Changed family metrics')
        return json.loads(gzip.decompress(path.read_bytes()))['families']
    summary=dict(experiment=cfg,baseline=results['dense']['initial'],cells={},comparisons={},versus_parent={},
        caveat='One seed; family SE omits retraining uncertainty. Fixed final epoch is primary. Selected-checkpoint comparisons are descriptive after selection. No reserved test evaluation or arena promotion.')
    for n,r in results.items():
        conf=json.loads((a.run/n/'config.json').read_text())
        summary['cells'][n]=dict(parameters=r['parameters'],best_epoch=r['best_epoch'],selected=r['selected'],last=r['history'][-1]['metrics'],
            history=r['history'],selected_sha256=r['selected_sha256'],export_max_abs_error=r['export_max_abs_error'],
            selected_optimizer_steps=r['selected_optimizer_steps'],wall_seconds=r['wall_seconds'],
            active_epoch_seconds=sum(row['seconds'] for row in r['history']),
            training_positions=conf['training_positions'],training_card_targets=conf['training_card_targets'],training_families=conf['training_families'],
            validation_families=conf['validation_families'])
        summary['versus_parent'][n]={str(row['epoch']):contrasts({'candidate':fm(n,row['metrics']),'parent':fm(n,r['initial'])},{'candidate':1,'parent':-1}) for row in r['history']}
    for phase in ['last','selected']:
        maps={n:fm(n,c[phase]) for n,c in summary['cells'].items()}
        summary['comparisons'][phase]=contrasts(maps,{'attention':1,'dense':-1})
    atomic_json(a.run/'summary.json',summary)
    lines=['# Residual attention belief versus dense continuation','',
        'Both fits start from the selected dense v5 candidate, with the same frozen data, consequential-card weights, '
        'family/domain normalization, fresh AdamW, batch size 128, seed, three epochs and checkpoint-selection objective. '
        'The attention model adds a zero-initialized 64-wide, two-head cross-attention correction.','',summary['caveat'],'']
    for phase in ['last','selected']:
        lines+=['## '+('Fixed final epoch' if phase=='last' else 'Selected checkpoints'),'','| Model | Epoch | Composite | Recent ordinary NLL | Weighted NLL | Consequential-only NLL | Accuracy | Brier |','|---|---:|---:|---:|---:|---:|---:|---:|']
        records=[('Parent dense v5',0,summary['baseline'])]+[(n,cfg['epochs'] if phase=='last' else c['best_epoch'],c[phase]) for n,c in summary['cells'].items()]
        for n,epoch,m in records:
            d=m['domains']['recent/play'];lines+=[f"| {n} | {epoch} | {m['score']:.8f} | {d['nll']:.8f} | {d['weighted_nll']:.8f} | {d['upweighted_card_nll']:.8f} | {d['accuracy']:.4%} | {d['brier']:.8f} |"]
        lines+=['','Attention minus dense on recent validation families (negative loss deltas favor attention):','',
            '| Metric | Paired delta ± family SE | Families |','|---|---:|---:|']
        for metric,d in summary['comparisons'][phase]['recent|play'].items():
            lines+=[f"| {metric} | {d['delta']:+.8f} ± {d['se']:.8f} | {d['families']} |"]
        lines+=['']
        lines+=['Recent validation accuracy and Brier details:','','| Model | Weighted accuracy | Weighted Brier | Consequential-only accuracy | Consequential-only Brier |','|---|---:|---:|---:|---:|']
        for n,epoch,m in records:
            d=m['domains']['recent/play']
            lines+=[f"| {n} | {d['weighted_accuracy']:.4%} | {d['weighted_brier']:.8f} | {d['upweighted_card_accuracy']:.4%} | {d['upweighted_card_brier']:.8f} |"]
        lines+=['']
    lines+=['## All epochs','','| Model | Epoch | Composite | Recent ordinary NLL | Weighted NLL | Consequential-only NLL | Accuracy | Brier | Active epoch seconds |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,c in summary['cells'].items():
        for row in c['history']:
            m=row['metrics'];d=m['domains']['recent/play']
            lines+=[f"| {n} | {row['epoch']} | {m['score']:.8f} | {d['nll']:.8f} | {d['weighted_nll']:.8f} | {d['upweighted_card_nll']:.8f} | {d['accuracy']:.4%} | {d['brier']:.8f} | {row['seconds']:.1f} |"]
    lines+=['','Paired recent-play differences from the unchanged starting dense v5:','','| Model | Epoch | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-only NLL delta ± SE |','|---|---:|---:|---:|---:|']
    for n,epochs in summary['versus_parent'].items():
        for epoch,domains in epochs.items():
            d=domains['recent|play'];values=[f"{d[k]['delta']:+.8f} ± {d[k]['se']:.8f}" for k in ('nll','weighted_nll','upweighted_card_nll')]
            lines+=['| '+n+' | '+epoch+' | '+' | '.join(values)+' |']
    lines+=['','## Fit and export checks','','| Model | Parameters | Active epoch minutes | Elapsed minutes | Selected Adam steps | Maximum NumPy prediction error |','|---|---:|---:|---:|---:|---:|']
    for n,c in summary['cells'].items():
        lines+=[f"| {n} | {c['parameters']:,} | {c['active_epoch_seconds']/60:.2f} | {c['wall_seconds']/60:.2f} | {c['selected_optimizer_steps']:,} | {max(c['export_max_abs_error'].values()):.3g} |"]
    lines+=['','Active epoch time includes training and validation, excluding worker startup and interrupted downtime. Elapsed time includes those interruptions. Export checks cover all four validation domains.','']
    for n,c in summary['cells'].items():
        if c['best_epoch']==0:lines+=[f"{n}: epoch zero won; this fit did not improve its validation objective.",'']
    c=summary['cells']['dense'];lines+=[f"Each fit uses {c['training_positions']:,} positions, {c['training_card_targets']:,} uncertain-card targets, and {c['training_families']:,} training families."]
    d=summary['baseline']['domains']['recent/play']
    lines+=[f"Validation contains {c['validation_families']:,} distinct families in total. Recent play contributes {d['families']:,} families and {d['targets']:,} uncertain-card targets, including {d['upweighted_targets']:,} consequential targets in {d['upweighted_families']:,} families. Positions and targets within a family are correlated; SEs use families as the sampling unit."]
    lines+=['All domain metrics, every epoch, export checks and paired differences from the parent are in summary.json. Hybrid inference requires bridge_harness.residual_attention_belief.Weights; legacy loading deliberately rejects hybrid files.']
    (a.run/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({n:dict(best_epoch=r['best_epoch'],score=r['selected']['score']) for n,r in results.items()}),flush=True)

if __name__=='__main__':main()
