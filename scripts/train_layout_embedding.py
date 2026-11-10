"""Small resumable metric fit. No production player changes or promotion."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
from collections import defaultdict
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.layout_embedding import encode, make_model, centered, reduce_layouts, export_numpy, Weights
from scripts.prepare_layout_embedding import save


def load(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def arrays(data, groups, rng, size=32, augment=False):
    indices = []
    for group in groups:
        lo, hi = data['starts'][group:group+2]
        indices.append(rng.choice(np.arange(lo, hi), size, replace=hi-lo < size))
    ix = np.concatenate(indices)
    fixed = np.repeat(data['fixed'][groups], size, axis=0)
    legal = data['scores'][ix] >= 0
    x, order = encode(data['raw'][ix], fixed, legal, rng.permutation(4) if augment else None)
    y = centered(data['scores'][ix][:, order], legal[:, order])
    return x, y, legal[:, order]


def objective(model, x, y, mask, n_groups, size):
    z, q = model(x)
    q = (q - (q*mask).sum(-1, keepdim=True)/mask.sum(-1, keepdim=True)) * mask
    za = z.reshape(n_groups, size, -1)
    ya = y.reshape(n_groups, size, -1)
    ma = mask.reshape(n_groups, size, -1)
    # Pair contrasts within one observable position, never between unrelated deals.
    shifts = (1, 7, 13)
    losses = []
    for shift in shifts:
        dz = za - torch.roll(za, shift, 1)
        dy = ya - torch.roll(ya, shift, 1)
        predicted = torch.sqrt(dz.square().mean(-1) + 1e-6)
        target = torch.sqrt((dy.square()*ma).sum(-1)/ma.sum(-1) + 1e-6)
        losses.append(F.smooth_l1_loss(predicted, target, beta=.25))
    metric = torch.stack(losses).mean()
    auxiliary = ((q-y).square()*mask).sum()/mask.sum()
    loss = metric + .2*auxiliary + 1e-4*z.square().mean()
    return loss, metric, auxiliary


@torch.no_grad()
def evaluate(model, data, groups):
    model.eval(); metric=[]; auxiliary=[]; predictions=[]; targets=[]
    rng=np.random.default_rng(2026111018)
    for start in range(0,len(groups),16):
        gs=groups[start:start+16];x,y,m=arrays(data,gs,rng)
        x,y,m=map(torch.from_numpy,(x,y,m.astype(np.float32)))
        _,me,au=objective(model,x,y,m,len(gs),32)
        metric.append(float(me));auxiliary.append(float(au))
        z,_=model(x);z=z.numpy().reshape(len(gs),32,-1);y=y.numpy().reshape(len(gs),32,-1);m=m.numpy().reshape(len(gs),32,-1)
        predictions.extend(np.sqrt(((z-np.roll(z,1,axis=1))**2).mean(-1)).ravel())
        targets.extend(np.sqrt((((y-np.roll(y,1,axis=1))**2)*m).sum(-1)/m.sum(-1)).ravel())
    corr=float(np.corrcoef(predictions,targets)[0,1]) if np.std(predictions)>0 and np.std(targets)>0 else 0.
    return dict(pair_distance_loss=float(np.mean(metric)),centered_action_mse=float(np.mean(auxiliary)),
                pair_distance_correlation=corr,groups=len(groups))


@torch.no_grad()
def screen(model, data, limit=400):
    """Finite-pool compression diagnostic; not independent posterior regret."""
    model.eval();rows=[]
    groups=[g for g in range(len(data['fixed'])) if data['starts'][g+1]-data['starts'][g]>=32]
    rng=np.random.default_rng(2026111019);rng.shuffle(groups)
    for group in groups[:limit]:
        lo,hi=data['starts'][group:group+2];n=int(min(64,hi-lo));ix=np.arange(lo,lo+n)
        legal=data['scores'][ix]>=0;fixed=np.repeat(data['fixed'][group:group+1],n,0)
        x,_=encode(data['raw'][ix],fixed,legal);z,q=model(torch.from_numpy(x));z=z.numpy();q=q.numpy()
        mask=legal[0];y=data['scores'][ix][:,mask].astype(float);target=y.mean(0);budget=n//4
        w=np.full(n,1/n);methods={}
        for name,embedding in [('learned',z),('learned_head',centered(q[:,mask],np.ones_like(y,bool))),
                               ('card_geometry',x[:,:208]),('oracle',centered(y,np.ones_like(y,bool)))]:
            chosen,masses=reduce_layouts(embedding,w,budget);estimate=masses@y[chosen]
            best=np.flatnonzero(np.isclose(estimate,estimate.max(),atol=1e-8,rtol=0))
            methods[name]=dict(regret=float(target.max()-target[best].mean()),
                               contrast_mse=float(np.mean(((estimate-estimate.mean())-(target-target.mean()))**2)))
        regrets=[];errors=[];strat_regrets=[];strat_errors=[]
        for _ in range(24):
            chosen=rng.choice(n,budget,replace=False);estimate=y[chosen].mean(0)
            best=np.flatnonzero(np.isclose(estimate,estimate.max(),atol=1e-8,rtol=0))
            regrets.append(target.max()-target[best].mean());errors.append(np.mean(((estimate-estimate.mean())-(target-target.mean()))**2))
            chosen,masses=reduce_layouts(z,w,budget,rng);estimate=masses@y[chosen]
            best=np.flatnonzero(np.isclose(estimate,estimate.max(),atol=1e-8,rtol=0))
            strat_regrets.append(target.max()-target[best].mean());strat_errors.append(np.mean(((estimate-estimate.mean())-(target-target.mean()))**2))
        methods['random']=dict(regret=float(np.mean(regrets)),contrast_mse=float(np.mean(errors)))
        methods['learned_random_within']=dict(regret=float(np.mean(strat_regrets)),contrast_mse=float(np.mean(strat_errors)))
        rows.append(dict(group=str(data['group'][group]),family=int(data['family'][group]),pool=n,budget=budget,methods=methods))
    methods={}
    for name in ('random','card_geometry','learned','learned_head','learned_random_within','oracle'):
        family=defaultdict(list)
        for r in rows:family[r['family']].append(r['methods'][name]['regret']-r['methods']['random']['regret'])
        delta=np.array([np.mean(v) for v in family.values()]);boot=np.random.default_rng(421).choice(delta,(2000,len(delta)),replace=True).mean(1)
        methods[name]=dict(regret=float(np.mean([r['methods'][name]['regret'] for r in rows])),
                           contrast_mse=float(np.mean([r['methods'][name]['contrast_mse'] for r in rows])),
                           family_delta_vs_random=float(delta.mean()),ci95=np.quantile(boot,[.025,.975]).tolist())
    return dict(groups=len(rows),families=len({r['family'] for r in rows}),methods=methods,rows=rows,
                limitations=['Validation-only 32-to-8 or 64-to-16 finite-pool proxy, not 128-to-32 live play.',
                             'Reference shares candidate pool; cannot establish superiority to full 128.',
                             'Uniform mass is a diagnostic over saved distinct layouts, not current belief weights.',
                             'Oracle uses DDS labels and is unavailable during inference.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=16);p.add_argument('--threads',type=int,default=1)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'run.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    torch.set_num_threads(a.threads);torch.set_num_interop_threads(1);torch.manual_seed(2026111016)
    tr=load(a.data/'train.npz');va=load(a.data/'validation.npz')
    if set(tr['family'])&set(va['family']):raise ValueError('Family split leakage')
    model=make_model();opt=torch.optim.AdamW(model.parameters(),lr=8e-4,weight_decay=1e-4)
    config=dict(parameters=sum(p.numel() for p in model.parameters()),embedding_dimensions=16,hidden=[256,128],
                train_worlds=len(tr['raw']),train_groups=len(tr['fixed']),train_families=len(set(tr['family'])),
                validation_worlds=len(va['raw']),validation_groups=len(va['fixed']),validation_families=len(set(va['family'])),
                epochs=a.epochs,threads=a.threads,seed=2026111016,
                loss='within-context pair-distance Huber + 0.2 centered all-action MSE + 0.0001 embedding norm',
                selection='validation pair-distance loss; inherited test families untouched',
                augmentation='actor-relative seats, random suit permutation shared by batch',
                sampling='uniform family, then uniform group in family; 32 worlds/group, 16 groups/batch',
                data_sha256=hashlib.sha256((a.data/'dataset.json').read_bytes()).hexdigest())
    save(a.out/'config.json',config)
    by_family={int(f):np.flatnonzero(tr['family']==f) for f in np.unique(tr['family'])};families=np.array(sorted(by_family))
    vg=np.arange(len(va['fixed']));np.random.default_rng(228).shuffle(vg);vg=vg[:800]
    history=[];best=float('inf');best_epoch=0;first=1;elapsed=0
    checkpoint=a.out/'last.pt'
    if checkpoint.exists():
        ck=torch.load(checkpoint,map_location='cpu',weights_only=False)
        if ck['config']['data_sha256']!=config['data_sha256']:raise ValueError('Resume data mismatch')
        model.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);history=ck['history']
        best=ck['best'];best_epoch=ck['best_epoch'];first=ck['epoch']+1;elapsed=ck['elapsed']
    else:
        save(a.out/'untrained.json',evaluate(model,va,vg))
    started=time.time();steps=max(1,(len(tr['raw'])+511)//512)
    print(json.dumps(dict(stage='training_started',config=config,steps_per_epoch=steps)),flush=True)
    for epoch in range(first,a.epochs+1):
        for param_group in opt.param_groups:
            param_group['lr'] = 8e-4 if epoch<=16 else 4e-4 if epoch<=32 else 2e-4 if epoch<=48 else 1e-4
        model.train();epoch_start=time.time();rng=np.random.default_rng(2026111016+epoch);stats=[]
        for step in range(steps):
            fs=rng.choice(families,16);gs=np.array([rng.choice(by_family[int(f)]) for f in fs])
            x,y,mask=arrays(tr,gs,rng,augment=True)
            x,y,mask=map(torch.from_numpy,(x,y,mask.astype(np.float32)))
            opt.zero_grad();loss,metric,aux=objective(model,x,y,mask,16,32)
            if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2.);opt.step()
            stats.append([float(loss.detach()),float(metric.detach()),float(aux.detach())])
            if step%100==0:
                save(a.out/'status.json',dict(stage='training',epoch=epoch,epochs=a.epochs,step=step,steps=steps,
                                             elapsed_seconds=elapsed+time.time()-started,updated_epoch=time.time()))
        val=evaluate(model,va,vg)
        if val['pair_distance_loss']<best:
            best=val['pair_distance_loss'];best_epoch=epoch;export_numpy(model,a.out/'best.npz')
        row=dict(epoch=epoch,train_loss=np.mean(stats,0).tolist(),validation=val,epoch_seconds=time.time()-epoch_start,
                 elapsed_seconds=elapsed+time.time()-started,best_epoch=best_epoch)
        history.append(row);export_numpy(model,a.out/'last.npz')
        ck=dict(model=model.state_dict(),optimizer=opt.state_dict(),history=history,config=config,epoch=epoch,
                best=best,best_epoch=best_epoch,elapsed=elapsed+time.time()-started)
        torch.save(ck,a.out/'last.tmp');(a.out/'last.tmp').replace(checkpoint)
        save(a.out/'training.json',dict(config=config,history=history,best_epoch=best_epoch));print(json.dumps(row),flush=True)
    w=Weights(a.out/'best.npz');model.load_state_dict({k:torch.from_numpy(v) for k,v in w.w.items()})
    raw=va['raw'][:32];fixed=np.repeat(va['fixed'][:1],len(raw),0);legal=va['scores'][:32]>=0
    x,_=encode(raw,fixed,legal)
    with torch.no_grad():reference=model(torch.from_numpy(x))[0].numpy()
    error=float(np.max(np.abs(reference-w.predict(raw,fixed,legal))))
    if error>1e-4:raise ValueError('Export mismatch')
    save(a.out/'status.json',dict(stage='validation_screen',updated_epoch=time.time()))
    diagnostic=screen(model,va);save(a.out/'compression-screen.json',diagnostic)
    result=dict(config=config,best_epoch=best_epoch,best_validation_loss=best,export_max_error=error,
                elapsed_seconds=elapsed+time.time()-started,diagnostic={k:v for k,v in diagnostic.items() if k!='rows'},
                deployment='Experimental checkpoint only; no production promotion.')
    save(a.out/'result.json',result);save(a.out/'status.json',dict(stage='complete',updated_epoch=time.time()))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
