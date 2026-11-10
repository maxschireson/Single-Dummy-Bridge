"""Audit saved independent-reference labels and summarize a completed screen."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.prepare_layout_embedding import save


def paired(values, seed=2026111041):
    values=np.asarray(values,float)
    if len(values)==0:return None
    boot=np.random.default_rng(seed).choice(values,(10000,len(values)),replace=True).mean(1)
    se=float(values.std(ddof=1)/np.sqrt(len(values))) if len(values)>1 else None
    return dict(n=len(values),mean=float(values.mean()),standard_error=se,
                ci95=np.quantile(boot,[.025,.975]).tolist(),
                positive=int((values>1e-12).sum()),negative=int((values < -1e-12).sum()),
                ties=int((np.abs(values)<=1e-12).sum()))


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    result=json.loads((a.run/'result.json').read_text())
    contexts=json.loads((a.run/'contexts.json').read_text())
    rows=[json.loads(f.read_text()) for f in sorted((a.run/'positions').glob('*.json'))]
    assert len(rows)==len(contexts)==200
    assert len({r['family'] for r in rows})==200
    assert all(r['remaining']>=10 for r in rows)
    assert {r['family'] for r in rows}=={r['family'] for r in contexts}
    error=0.
    for r in rows:
        key=r['family'][:16]+'-large'
        with np.load(a.run/'positions'/f'{key}.npz') as z:
            assert len(z['candidate_raw'])==128 and len(z['candidate_scores'])==128
            ref=z['reference_scores'][:512].mean(0);legal=z['legal'].tolist()
            for mode,m in r['methods'].items():
                cards=[legal.index(c) for c in m['selected_cards']]
                error=max(error,abs(float(ref[cards].mean())-m['reference_value']))
                error=max(error,abs(float(ref.max()-ref[cards].mean())-m['regret']))
            for mode,d in r['reduction'].items():
                weights=np.array(d['weights']);ix=np.array(d['indices'])
                assert 1<=len(ix)<=32 and len(set(ix))==len(ix)
                assert (weights>=0).all() and abs(weights.sum()-1)<1e-9
                estimate=weights@z['candidate_scores'][ix]
                selected=np.flatnonzero(np.isclose(estimate,estimate.max(),atol=1e-8,rtol=0))
                assert [int(z['legal'][j]) for j in selected]==r['methods'][mode]['selected_cards']
    assert error<1e-10
    comparisons={}
    for left,right in [('belief','random32'),('cluster','random32'),('pool','random32'),
                       ('belief','full128'),('belief','cluster'),('belief','pool'),('belief','random_matched')]:
        comparisons[f'{left}_minus_{right}']=paired([r['methods'][left]['reference_value']-r['methods'][right]['reference_value'] for r in rows])
    checks=[r for r in rows if r['reference_draws']==1024]
    sensitivity={}
    for left,right in [('belief','random32'),('belief','full128')]:
        primary=[r['methods'][left]['reference_value']-r['methods'][right]['reference_value'] for r in checks]
        doubled=[r['methods'][left]['double_reference_value']-r['methods'][right]['double_reference_value'] for r in checks]
        sensitivity[f'{left}_minus_{right}']=dict(primary512=paired(primary),doubled1024=paired(doubled),
            reference_change=paired(np.array(doubled)-primary))
    times={m:sum(r['methods'][m]['cpu_seconds'] for r in rows) for m in rows[0]['methods']}
    fit=[r['reduction']['belief']['calibration'] for r in rows]
    detail=dict(positions=len(rows),families=len(rows),label_audit_max_error=error,comparisons=comparisons,
        reference_checks=len(checks),reference_sensitivity=sensitivity,
        cpu_ratio_belief_vs_random32=times['belief']/times['random32'],
        cpu_ratio_belief_vs_full128=times['belief']/times['full128'],
        mean_weight_fit_cpu=sum(r['reduction']['belief']['reduction_cpu_seconds'] for r in rows)/len(rows),
        mean_exact_moment_cpu=sum(r['timing']['moment_cpu'] for r in rows)/len(rows),
        mean_moment_mse_before=float(np.mean([f['standardized_moment_mse_before'] for f in fit])),
        mean_moment_mse_after=float(np.mean([f['standardized_moment_mse_after'] for f in fit])),
        converged_weight_fits=sum(f['success'] for f in fit),
        notes=['Positive paired differences mean better independent-reference action value.',
               'Individual bootstrap intervals are exploratory, not multiplicity-adjusted.',
               'No whole-play or IMP-strength claim.'])
    save(a.run/'analysis.json',detail)
    print(json.dumps(detail),flush=True)


if __name__=='__main__':main()
