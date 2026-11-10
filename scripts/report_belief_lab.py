"""Summarize completed development runs without treating cards as independent."""
import argparse,gzip,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.selfplay import atomic_json

def families(path):return json.loads(gzip.decompress(path.read_bytes()))['families']
def contrast(a,b):
    aa=families(a);bb=families(b);d=[]
    for k,v in aa.items():
        if k.startswith('recent|play|') and k in bb and v[3] and bb[k][3]:d.append(v[2]/v[3]-bb[k][2]/bb[k][3])
    return dict(families=len(d),nll_delta=float(np.mean(d)) if d else None,se=float(np.std(d,ddof=1)/math.sqrt(len(d))) if len(d)>1 else None)
def report(root):
    rows=[];control=root/'fits/dense_added';cp=control/'result.json'
    cr=json.loads(cp.read_text()) if cp.exists() else None
    for p in sorted((root/'fits').glob('*/result.json')):
        r=json.loads(p.read_text());row=dict(name=p.parent.name,score=r['best_score'],best_epoch=r['best_epoch'],parameters=r['parameters'],seconds=sum(x['seconds'] for x in r['history']),seed=r['config']['seed'])
        if cr:row['vs_data_control']=contrast(p.parent/f"epoch-{r['best_epoch']}-families.json.gz",control/f"epoch-{cr['best_epoch']}-families.json.gz")
        rows.append(row)
    rows.sort(key=lambda r:r['score']);atomic_json(root/'leaderboard.json',dict(rows=rows,interpretation='Development selection; conditional paired SE is not retraining uncertainty. No confirmation claim.'))
    lines=['# Belief experiment development results','','Scores below are development measurements, not final confirmation. All cards and positions from the same canonical deal are clustered together. Seed variability is separate.','','| Recipe | Selected epoch | Composite NLL | Recent NLL delta vs data control | Family SE | Families | Training + validation minutes |','|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        d=r.get('vs_data_control',{});lines.append(f"| {r['name']} | {r['best_epoch']} | {r['score']:.8f} | {d.get('nll_delta','')} | {d.get('se','')} | {d.get('families','')} | {r['seconds']/60:.1f} |")
    (root/'progress.md').write_text('\n'.join(lines)+'\n');return rows
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();report(a.run)
