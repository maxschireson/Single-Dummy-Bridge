"""Frozen family objective and evaluation shared by the residual comparison."""
from collections import Counter,defaultdict
import gzip,json
from pathlib import Path
import numpy as np
from bridge_harness.belief_capacity import INPUTS,sha
from bridge_harness.selfplay import atomic_json
from scripts.train_belief_factorial import read

def prepare(data,smoke=0):
    ds=json.loads((data/'dataset.json').read_text())
    if sha(data/'manifest.json')!=ds['manifest_sha256']:raise ValueError('Manifest changed')
    entries=ds['shards']
    if smoke:
        entries=[e for cohort in ('historical','recent') for split in ('train','validation') for source in ('play','bidding','ben')
                 for e in [x for x in entries if (x['cohort'],x['split'],x['source'])==(cohort,split,source)][:smoke]]
    train=[e for e in entries if e['split']=='train'];val=[e for e in entries if e['split']=='validation']
    counts=Counter();recent=set();families=set();val_families=set();positions=targets=0
    for e in train:
        d=read(e);groups=d['split_group'].astype(str);mass=(d['owner_loss_mask']*d['card_weight']).sum(1)
        for g,n in zip(groups,mass):counts[e['source'],g]+=float(n)
        families.update(groups);positions+=len(groups);targets+=int(d['owner_loss_mask'].sum())
        if e['cohort']=='recent':recent.update(groups)
    for e in val:
        with np.load(e['file'],allow_pickle=False) as z:val_families.update(map(str,z['split_group']))
    if families&val_families:raise ValueError('Family overlap')
    masses=Counter()
    for source,g in counts:masses[source]+=2 if g in recent else 1
    domain={'play':.5,'bidding':.25,'ben':.25}
    coeff={k:positions*domain[k[0]]*(2 if k[1] in recent else 1)/(masses[k[0]]*v) for k,v in counts.items()}
    return train,val,coeff,dict(training_positions=positions,training_card_targets=targets,training_families=len(families),validation_families=len(val_families))

def evaluate(predict,entries,out,label,batch_size=128):
    families=defaultdict(lambda:np.zeros(12))
    for e in entries:
        d=read(e)
        for lo in range(0,len(d['kind']),batch_size):
            ix=slice(lo,lo+batch_size);x={k:d[k][ix] for k in INPUTS};y=d['owner_target'][ix];mask=d['owner_loss_mask'][ix]
            z=np.asarray(predict(x));z=np.where(d['support'][ix],z,-1e9);z-=z.max(-1,keepdims=True)
            p=np.exp(z);p/=p.sum(-1,keepdims=True);true=p[np.arange(len(y))[:,None],np.arange(52),y]
            ce=-np.log(np.maximum(true,1e-30));cw=d['card_weight'][ix]*mask;acc=p.argmax(-1)==y
            brier=(p*p).sum(-1)-2*true+1;boost=mask*(d['card_weight'][ix]>1)
            sums=np.stack([(ce*cw).sum(1),cw.sum(1),(ce*mask).sum(1),mask.sum(1),(acc*mask).sum(1),(brier*mask).sum(1),
                boost.sum(1),(ce*boost).sum(1),(acc*cw).sum(1),(brier*cw).sum(1),(acc*boost).sum(1),(brier*boost).sum(1)],1)
            for g,kind,v in zip(d['split_group'][ix],d['kind'][ix],sums):
                if e['source']!='play' and kind!=1:continue
                families[e['cohort'],e['source'],str(g)]+=v
    grouped=defaultdict(list)
    for key,v in families.items():
        if v[3]:grouped[key[:2]].append(v)
    metrics={}
    for key,vs in grouped.items():
        v=np.stack(vs);boost=v[v[:,6]>0]
        def avg(n,d):return float(np.mean(v[:,n]/v[:,d]))
        def selected(n):return float(np.mean(boost[:,n]/boost[:,6])) if len(boost) else None
        metrics['/'.join(key)]=dict(nll=avg(2,3),weighted_nll=avg(0,1),accuracy=avg(4,3),brier=avg(5,3),
            weighted_accuracy=avg(8,1),weighted_brier=avg(9,1),upweighted_card_nll=selected(7),
            upweighted_card_accuracy=selected(10),upweighted_card_brier=selected(11),families=len(v),
            targets=int(v[:,3].sum()),upweighted_targets=int(v[:,6].sum()),upweighted_families=len(boost))
    score=sum(metrics[s][metric] for s,metric in [('historical/play','nll'),('recent/play','weighted_nll'),
        ('historical/bidding','nll'),('historical/ben','nll')])/4
    path=out/(label+'-families.json.gz');tmp=path.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(json.dumps({'families':{'|'.join(k):v.tolist() for k,v in families.items()}}).encode(),mtime=0));tmp.replace(path)
    return dict(score=score,domains=metrics,family_file=path.name,family_file_sha256=sha(path))
