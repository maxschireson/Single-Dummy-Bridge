"""Replay fresh forks and compute frozen prediction diagnostics on chosen cards."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,gzip,json,sys
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card,imps
from bridge_harness.ddsd_corrector import Corrector,encode
from bridge_harness.selfplay import atomic_json
from scripts.evaluate_ddsd_fresh import sha,Search,seed_for,summarize,METHODS
from scripts.train_ddsd_corrector import family_stats

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--control',type=Path,required=True);a=p.parse_args();torch.set_num_threads(1)
    root=a.run;m=json.loads((root/'evaluation-manifest.json').read_text())
    boards=[json.loads(s) for s in (root/'boards.jsonl').read_text().splitlines()]
    records=[json.load(gzip.open(f,'rt')) for f in sorted((root/'episodes').glob('*.json.gz'))]
    if len({r['family'] for r in records})!=len(records):raise ValueError('Duplicate deal family')
    full=Corrector(m['models']['corrector']['path']);control=Corrector(a.control)
    context=[5/6,m['samples']/192,1.,m['window']]*4
    families=[];true_errors={k:[] for k in ('dd','full','control')};diff_errors={k:[] for k in METHODS}
    predicted=[];replays=0;audits=0;contrasts=0;audit_rows=[]
    for r in records:
        assert r['manifest_sha256']==sha(root/'evaluation-manifest.json')
        assert r['board']==boards[r['index']]
        if r['passed_out']:assert r['board']['contract'] is None;continue
        b=Board.from_dict(r['board']);tables=[r['base']]+r['branches']
        for t in tables:
            game=Game(b)
            for c in t['actions']:game.play(c)
            assert game.done and game.declarer_tricks==t['declarer_tricks'] and game.ns_score()==t['ns_score']
            replays+=1
        for audit in r['audits']:
            ply=audit['ply'];game=Game(b)
            for c in r['base']['actions'][:ply]:game.play(c)
            o=game.observation();q=audit['values'];choices=audit['choices']
            assert q['pimc'][choices['pimc']]==max(q['pimc'].values())
            for method in ('v5','corrector'):
                assert abs(q[method][choices[method]]-max(q[method].values()))<=1e-7
                assert max(q['pimc'].values())-q['pimc'][choices[method]]<=m['window']+1e-9
            outcomes={}
            for c,j in audit['branches'].items():
                t=r['base'] if j==-1 else r['branches'][j]
                assert t['actions'][:ply]==r['base']['actions'][:ply] and t['actions'][ply]==card(c)
                outcomes[c]=t
                declaring=o.actor%2==o.contract.declarer%2
                y=(t['declarer_tricks'] if declaring else 13-t['declarer_tricks'])-(o.declarer_tricks if declaring else ply//4-o.declarer_tricks)
                assert audit['outcomes'][c]==y
            for method in METHODS:
                score_diff=outcomes[choices[method]]['ns_score']-outcomes[choices['pimc']]['ns_score']
                assert audit['imp_gain'][method]==imps(score_diff*(1 if o.actor%2==0 else -1))
            assert audit['corrector_vs_v5_imps']==imps((outcomes[choices['corrector']]['ns_score']-outcomes[choices['v5']]['ns_score'])*(1 if o.actor%2==0 else -1))
            names=sorted(set(choices.values()));xs=[];calls=[]
            for c in names:
                x,cs=encode(o,game.hands,card(c),audit['true_dd'][c],context);xs.append(x);calls.append(cs)
            dd=np.array([audit['true_dd'][c] for c in names]);y=np.array([audit['outcomes'][c] for c in names])
            residual=full.predict(xs,calls);masked=control.predict(xs,calls)
            for name,value in [('dd',dd),('full',dd+m['weight']*residual),('control',dd+m['weight']*masked)]:
                true_errors[name].append(float(np.mean((value-y)**2)))
            # Fixed three policy-pair contrasts per audited decision; equal choices
            # yield exact zero. This secondary metric is on policy-selected cards.
            for method in METHODS:
                errors=[]
                for left,right in [('pimc','v5'),('pimc','corrector'),('v5','corrector')]:
                    c,d=choices[left],choices[right]
                    errors.append((q[method][c]-q[method][d]-audit['outcomes'][c]+audit['outcomes'][d])**2)
                diff_errors[method].append(float(np.mean(errors)))
            families.append(r['index']);audits+=1;contrasts+=3
            audit_rows.append((r['index'],audit))
            predicted.append(dict(index=r['index'],ply=ply,cards=names,actual=y.tolist(),dd=dd.tolist(),
                residual=residual.tolist(),masked_residual=masked.tolist()))
    diagnostics=dict(verification=dict(boards=len(records),complete_continuations_replayed=replays,audits=audits,
        exact_global_pimc_maximum=True,legal_prefixes=True,recorded_payoffs_verified=True),
        control_sha256=sha(a.control),
        true_deal_outcome_mse={k:family_stats(v,families) for k,v in true_errors.items()},
        sampled_choice_contrast_mse={k:family_stats(v,families) for k,v in diff_errors.items()},
        secondary_metric_note='Equal-weight policy-selected card set per decision; three fixed policy-pair contrasts, including zero contrasts for equal choices; not an independent random action sample')
    for result,errors,base in [(diagnostics['true_deal_outcome_mse'],true_errors,'dd'),
                               (diagnostics['sampled_choice_contrast_mse'],diff_errors,'pimc')]:
        for name in list(errors):
            if name!=base:result[name+'_minus_'+base]=family_stats(np.array(errors[name])-errors[base],families)
    diagnostics['true_deal_outcome_mse']['full_minus_control']=family_stats(np.array(true_errors['full'])-true_errors['control'],families)
    diagnostics['choice_slices']={}
    for method in ('v5','corrector'):
        slices={}
        for label,predicate in [
            ('pimc_tie_change',lambda a:a['choices'][method]!=a['choices']['pimc'] and a['pimc_gap_to_'+method]==0),
            ('non_tie_change',lambda a:a['pimc_gap_to_'+method]>0),
            ('declarer',lambda a:a['declaring']),('defence',lambda a:not a['declaring'])]:
            part=[(i,a) for i,a in audit_rows if predicate(a)]
            if part:slices[label]=dict(imps=family_stats([a['imp_gain'][method] for i,a in part],[i for i,a in part]),
                tricks=family_stats([a['trick_gain'][method] for i,a in part],[i for i,a in part]),
                total_imps=sum(a['imp_gain'][method] for i,a in part),
                total_tricks=sum(a['trick_gain'][method] for i,a in part),
                contribution_per_all_audits=family_stats([a['imp_gain'][method] if predicate(a) else 0. for i,a in audit_rows],[i for i,a in audit_rows]))
        diagnostics['choice_slices'][method]=slices
    atomic_json(root/'diagnostics.json',diagnostics)
    atomic_json(root/'diagnostic-predictions.json.gz',predicted,compressed=True)
    print(json.dumps(diagnostics),flush=True)

if __name__=='__main__':main()
