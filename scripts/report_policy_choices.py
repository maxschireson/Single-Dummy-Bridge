"""Report a frozen policy-choice fit without further model selection."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.train_policy_choices import load_split, family_summary, choose
from bridge_harness.selfplay import atomic_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--fit',type=Path,required=True)
    args=parser.parse_args()
    ds=json.loads((args.data/'dataset.json').read_text())
    parts=[load_split(args.data,ds,s) for s in ('train','validation','test')]
    data={k:np.concatenate([d[k] for d in parts]) for k in ('y','group','depth','current_policy','source','pair','gen4_contrast')}
    root=(data['depth']==0)&data['current_policy'].astype(bool)
    output={}
    for name, mask in [('full_gen4',root&~np.char.startswith(data['pair'],'4p')),
                       ('policy_only_4p',root&np.char.startswith(data['pair'],'4p')),
                       ('supplemental',root&(data['source']==0)),('component',root&(data['source']==1))]:
        y=data['y'][mask]
        output[name]=dict(gain=family_summary(y,data['group'][mask]),
                          wins=int((y>0).sum()),losses=int((y<0).sum()),ties=int((y==0).sum()))
    families=json.loads((args.data/'families.json').read_text())
    output['audits']={k:sum(f.get(k,0) for f in families if f['current_policy']) for k in
                     ('root_audits','root_identical','root_budget_skips','recursive_audits','recursive_identical','recursive_budget_skips')}
    current_mse=(data['gen4_contrast'][root]-data['y'][root])**2-data['y'][root]**2
    output['paired_mse_change_vs_zero']=family_summary(current_mse,data['group'][root])
    with np.load(args.fit/'test-predictions.npz',allow_pickle=False) as z:
        held={k:z[k] for k in z.files}
    mask=(held['depth']==0)&held['current_policy'].astype(bool)&(held['y']!=0)
    for baseline in ('gen3','gen4'):
        delta=(choose(held['new_contrast'][mask])-choose(held[baseline+'_contrast'][mask]))*np.sign(held['y'][mask])
        output['test_accuracy_new_minus_'+baseline]=family_summary(delta,held['group'][mask])
    selection=(held['depth']==0)&held['current_policy'].astype(bool)
    output['test_changed_from_gen3']=int(np.sum(choose(held['new_contrast'][selection])!=choose(held['gen3_contrast'][selection])))
    output['test_changed_from_gen4']=int(np.sum(choose(held['new_contrast'][selection])!=choose(held['gen4_contrast'][selection])))
    atomic_json(args.fit/'analysis.json',output)
    print(json.dumps(output))


if __name__=='__main__':main()
