"""Fixed-epoch development contrasts, with deal-family paired standard errors."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.selfplay import atomic_json

def contrast(a,b):
    assert set(a)==set(b),'Different development families'
    d=np.array([a[g][0]/a[g][1]-b[g][0]/b[g][1] for g in a if a[g][1] and b[g][1]])
    return dict(delta=float(d.mean()),se=float(d.std(ddof=1)/math.sqrt(len(d))),families=len(d))

def report(root):
    rows=[];plan=json.loads((root/'plan.json').read_text())
    for kind in ('belief','policy'):
        for epoch in range(1,7 if kind=='belief' else 3):
            paths={n:root/'fits'/f'{kind}_{n}'/(f'joint-{epoch}.json' if kind=='belief' else f'epoch-{epoch}-families.json') for n in ('none','high','low','quantity')}
            if not all(p.exists() for p in paths.values()):continue
            data={k:json.loads(p.read_text()) for k,p in paths.items()}
            if kind=='belief':data={k:v['groups'] for k,v in data.items()}
            for left,right in [('high','low'),('high','quantity'),('low','none'),('high','none'),('quantity','none')]:
                rows.append(dict(kind=kind,epoch=epoch,left=left,right=right,**contrast(data[left],data[right])))
            budget=root/'fits'/f'{kind}_budget'/(f'joint-{epoch}.json' if kind=='belief' else f'epoch-{epoch}-families.json')
            if budget.exists():
                b=json.loads(budget.read_text());b=b['groups'] if kind=='belief' else b
                rows.append(dict(kind=kind,epoch=epoch,left='high',right='budget',**contrast(data['high'],b)))
    atomic_json(root/'comparison.json',dict(rows=rows,counts=plan['counts'],interpretation='Development fixed-epoch screens. Negative is better. Family SE conditions on these trained models; no seed/data-subset replication or playing-strength confirmation yet.'))
    lines=['# Effort versus volume pilot','',f"Added training families: high {plan['counts']['high']['families']}, low {plan['counts']['low']['families']}, quantity {plan['counts']['quantity']['families']}. Common-auction roots only, matched opponent counts.",'','Negative change favors the left arm. Belief: exact conditional card NLL. Policy: observed remaining-trick MSE. Development only; conditional family SE excludes seed and training-set uncertainty.','','| Net | Epoch | Comparison | Change | Family SE | Dev families |','|---|---:|---|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['kind']} | {r['epoch']} | {r['left']} minus {r['right']} | {r['delta']:.9f} | {r['se']:.9f} | {r['families']} |")
    (root/'progress.md').write_text('\n'.join(lines)+'\n');return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();report(a.run)
