"""Report fixed final-epoch contrasts with seed and deal uncertainty separate."""
import argparse,json,math
from pathlib import Path
import numpy as np

def report(root):
    rep=root/'rounds/seed-replication';rows=[]
    for kind,epoch,first in [('policy',2,2026111029),('belief',6,2026111017)]:
        for arm in ['high','low','budget','quantity']:
            vectors=[];seeds=[]
            for seed in [first,2026111041,2026111053]:
                base=root/'fits' if seed==first else rep/'fits'
                def get(name):
                    p=base/(f'{kind}_{name}' if seed==first else f'{kind}_{name}_s{seed}')/(f'epoch-{epoch}-families.json' if kind=='policy' else f'joint-{epoch}.json')
                    if not p.exists():return None
                    x=json.loads(p.read_text());return x if kind=='policy' else x['groups']
                a,b=get(arm),get('none')
                if a is None or b is None:continue
                assert set(a)==set(b)
                keys=sorted(a);v=np.array([a[g][0]/a[g][1]-b[g][0]/b[g][1] for g in keys if a[g][1] and b[g][1]])
                vectors.append(v);seeds.append(seed)
            if not vectors:continue
            means=np.array([v.mean() for v in vectors]);avg=np.mean(vectors,axis=0)
            rows.append(dict(kind=kind,arm=arm,epoch=epoch,seeds=seeds,seed_deltas=means.tolist(),mean_delta=float(means.mean()),seed_sd=float(means.std(ddof=1)) if len(means)>1 else None,seed_se=float(means.std(ddof=1)/len(means)**.5) if len(means)>1 else None,families=len(avg),family_se=float(avg.std(ddof=1)/len(avg)**.5)))
    result=dict(rows=rows,note='Negative favors added data. Family SE of seed-averaged paired deal losses conditions on fitted models. Seed SD/SE describes training-order variability on the same frozen dataset. These are not independent data-subset replications; no heldout test or play confirmation.')
    (rep/'comparison.json').write_text(json.dumps(result,indent=2))
    lines=['# Effort pilot seed replication','',result['note'],'','| Net | Arm vs no addition | Seeds complete | Mean delta | Family SE | Seed SD |','|---|---|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['kind']} | {r['arm']} | {len(r['seeds'])} | {r['mean_delta']:.9f} | {r['family_se']:.9f} | {r['seed_sd'] if r['seed_sd'] is not None else 'pending'} |")
    (rep/'progress.md').write_text('\n'.join(lines)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();report(a.run)
