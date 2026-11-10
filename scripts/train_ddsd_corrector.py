"""Train observed-outcome residuals; select on validation, then open test once."""
import argparse,copy,json,os,sys,time
from pathlib import Path
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.ddsd_corrector import make_model,SCHEMA,mask_hidden_features

def load(data,kind,split):
    manifest=json.loads((data/'dataset.json').read_text());parts=[]
    for s in manifest['shards']:
        if s['kind']==kind and s['split']==split:
            with np.load(data/s['file']) as z:parts.append({k:z[k] for k in z.files})
    return {k:np.concatenate([p[k] for p in parts]) for k in parts[0]} if parts else None

def mask_hidden(d):
    """Ablation retains visible original hands and all already-public cards.

    True-deal DD remains an input. This tests the incremental usefulness of
    explicit hidden ownership, not the full proposal versus old PIMC labels.
    """
    if d is None:return d
    d['x']=mask_hidden_features(d['x'])
    return d

def family_stats(values,groups):
    ids,inverse=np.unique(groups,return_inverse=True)
    means=np.bincount(inverse,weights=np.asarray(values,dtype=float))/np.bincount(inverse)
    se=float(means.std(ddof=1)/len(means)**.5) if len(means)>1 else None
    mean=float(means.mean())
    return dict(mean=mean,se=se,ci95=None if se is None else [mean-1.96*se,mean+1.96*se],families=len(ids),rows=len(values))

def predict(model,d):
    shape=d['dd'].shape
    x=d['x'].reshape(-1,d['x'].shape[-1]);calls=d['calls'].reshape(-1,d['calls'].shape[-1]);pred=[]
    model.eval()
    with torch.no_grad():
        for i in range(0,len(x),2048):
            pred.append(model(torch.tensor(x[i:i+2048],dtype=torch.float32),
                torch.tensor(calls[i:i+2048],dtype=torch.long)).numpy())
    return np.concatenate(pred).reshape(shape)

def outcome_metrics(d,r,weight=1):
    actual=d['y']-d['dd'];old=actual**2;new=(actual-weight*r)**2
    result=dict(dd_mse=family_stats(old,d['family']),corrected_mse=family_stats(new,d['family']),
        mse_change=family_stats(new-old,d['family']),residual_mean=family_stats(actual,d['family']))
    result['by_phase']={}
    for name,mask in [('early',d['ply']<16),('middle',(d['ply']>=16)&(d['ply']<36)),('late',d['ply']>=36),
                      ('declarer',d['declaring'].astype(bool)),('defence',~d['declaring'].astype(bool))]:
        if mask.any():result['by_phase'][name]=dict(dd_mse=family_stats(old[mask],d['family'][mask]),
            corrected_mse=family_stats(new[mask],d['family'][mask]),mse_change=family_stats((new-old)[mask],d['family'][mask]))
    return result

def pair_metrics(d,r,weight=1):
    dd=d['dd'][:,0]-d['dd'][:,1];y=d['y'][:,0]-d['y'][:,1]
    q=dd+weight*(r[:,0]-r[:,1])
    # Half credit at exact ties: no dependence on logged candidate ordering.
    old=np.where(dd>1e-8,1.,np.where(dd < -1e-8,0.,.5))
    new=np.where(q>1e-8,1.,np.where(q < -1e-8,0.,.5))
    return dict(dd_difference_mse=family_stats((dd-y)**2,d['family']),
        corrected_difference_mse=family_stats((q-y)**2,d['family']),
        difference_mse_change=family_stats((q-y)**2-(dd-y)**2,d['family']),
        choice_trick_gain=family_stats((new-old)*y,d['family']),
        change_fraction=float(np.mean(old!=new)),
        decisive_rows=int(np.count_nonzero(y)),dd_ties=int(np.count_nonzero(dd==0)),
        non_tie_gain=family_stats(((new-old)*y)[dd!=0],d['family'][dd!=0]) if (dd!=0).any() else None)

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=20);p.add_argument('--width',type=int,default=128);p.add_argument('--seed',type=int,default=617)
    p.add_argument('--mask-hidden',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1);torch.manual_seed(a.seed)
    np.random.seed(a.seed);rng=np.random.default_rng(a.seed)
    train=load(a.data,'outcomes','train');val=load(a.data,'outcomes','validation')
    if a.mask_hidden:train=mask_hidden(train);val=mask_hidden(val)
    model=make_model(train['x'].shape[1],a.width);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.001)
    ids,inv,counts=np.unique(train['family'],return_inverse=True,return_counts=True)
    w=len(train['family'])/len(ids)/counts[inv]
    x=torch.tensor(train['x'],dtype=torch.float32);calls=torch.tensor(train['calls'],dtype=torch.long)
    target=torch.tensor(train['y']-train['dd'],dtype=torch.float32);weights=torch.tensor(w,dtype=torch.float32)
    config=dict(schema=SCHEMA,state_size=x.shape[1],width=a.width,epochs=a.epochs,seed=a.seed,mask_hidden=a.mask_hidden,
        training_rows=len(x),training_families=len(ids),parameters=sum(p.numel() for p in model.parameters()),
        loss='Equal-family-weighted observed residual MSE; no pairwise loss',
        selection='Minimum validation outcome MSE, including epoch zero; test read after checkpoint selection',
        correction_weight_grid=[0,.25,.5,1],data=str(a.data.resolve()))
    (a.out/'config.json').write_text(json.dumps(config,indent=2));history=[];best=float('inf');started=time.time()
    for epoch in range(a.epochs+1):
        if epoch:
            model.train();total=0.
            for indices in np.array_split(rng.permutation(len(x)),max(1,(len(x)+511)//512)):
                optimizer.zero_grad();pred=model(x[indices],calls[indices]);loss=((pred-target[indices])**2*weights[indices]).mean()
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();total+=float(loss.detach())*len(indices)
        residual=predict(model,val);metrics=outcome_metrics(val,residual);mse=metrics['corrected_mse']['mean']
        entry=dict(epoch=epoch,seconds=time.time()-started,validation_mse=mse,dd_mse=metrics['dd_mse']['mean'],
            training_loss=total/len(x) if epoch else None)
        history.append(entry);print(json.dumps(entry),flush=True)
        if mse<best:
            best=mse;best_epoch=epoch;checkpoint=dict(model=copy.deepcopy(model.state_dict()),state_size=x.shape[1],width=a.width,epoch=epoch)
            checkpoint['mask_hidden']=a.mask_hidden;torch.save(checkpoint,a.out/'candidate.pt')
        (a.out/'history.json').write_text(json.dumps(history,indent=2))
    model.load_state_dict(checkpoint['model']);val_res=predict(model,val)
    weight=min(config['correction_weight_grid'],key=lambda w:outcome_metrics(val,val_res,w)['corrected_mse']['mean'])
    selection=dict(epoch=best_epoch,weight=weight,validation_mse=best)
    (a.out/'selection.json').write_text(json.dumps(selection,indent=2))
    results=dict(config=config,selection=selection,promoted=False)
    for split in ('validation','test'):
        d=val if split=='validation' else load(a.data,'outcomes',split)
        if a.mask_hidden and split!='validation':d=mask_hidden(d)
        r=predict(model,d)
        results[split]=dict(outcomes=outcome_metrics(d,r,weight))
        pairs=load(a.data,'pairs',split)
        if a.mask_hidden:pairs=mask_hidden(pairs)
        if pairs is not None:
            pr=predict(model,pairs);results[split]['true_deal_pairs']=pair_metrics(pairs,pr,weight)
            np.savez_compressed(a.out/f'{split}-pairs-predictions.npz',prediction=pr,**{k:pairs[k] for k in ('dd','y','family','ply')})
        np.savez_compressed(a.out/f'{split}-outcome-predictions.npz',prediction=r,**{k:d[k] for k in ('dd','y','family','ply','declaring')})
    results['seconds']=time.time()-started
    (a.out/'result.json').write_text(json.dumps(results,indent=2));print(json.dumps(results),flush=True)

if __name__=='__main__':main()
