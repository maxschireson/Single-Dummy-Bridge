#!/usr/bin/env python3
"""Resumable single-candidate v5 screen. Test families are reserved, never scored."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.core import Board, Game, card
from bridge_harness.bidding_env import deal_key
from bridge_harness.belief_capacity import Weights as DenseWeights, sha
from bridge_harness.attention_belief import encode, make_model, torch_batch, per_position_loss
from bridge_harness.belief_consequence import public_key, importance

ARCHITECTURE = dict(width=128, layers=2, heads=4, dropout=.1)
SEED = 2026110905
# Used for a preflight serialization/legality check before its split was inspected.
# Retired from this experiment, including its final test pool; no fit or metric used it.
PREFLIGHT_EXCLUDED = {'35d43f02c50c72b9409a59b07b4291f430b17266dafd5cd5d67bf6278abf3f88'}


def save_json(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n'); tmp.replace(p)


def split(family):
    b = int(family[:8], 16) % 10
    return 'test' if b == 0 else 'validation' if b == 5 else 'train'


def freeze(args):
    path = args.output/'manifest.json'
    if path.exists():
        m = json.loads(path.read_text())
        if sha(args.parent) != m['parent_sha256']:
            raise ValueError('Frozen comparator changed')
        return m
    by_family = {}; scanned = 0
    for root in args.sources:
        for p in sorted((Path(root)/'episodes').glob('*.json.gz')):
            raw = p.read_bytes(); e = json.loads(gzip.decompress(raw))
            f = e['family']; scanned += 1
            if f in PREFLIGHT_EXCLUDED: continue
            expected = 'validation' if int(f[:8],16) % 5 == 0 else 'train'
            if e['split'] != expected: raise ValueError('Historical split mismatch')
            # Only metadata is inspected for test families; no positions or metrics.
            entry = dict(path=str(p.resolve()), sha256=hashlib.sha256(raw).hexdigest())
            by_family.setdefault(f, []).append(entry)
            if scanned % 250 == 0:
                print(json.dumps(dict(stage='freeze', episodes=scanned, families=len(by_family))), flush=True)
    families = [dict(family=f, split=split(f), sources=s) for f, s in sorted(by_family.items())]
    if args.max_families:
        families = families[:args.max_families]
    m = dict(schema='standalone-attention-belief-screen-v1', seed=SEED,
        architecture=ARCHITECTURE, epochs=3, positions_per_family=16,
        parent_sha256=sha(args.parent), families=families,
        split_rule='canonical rotations hash modulo 10: 0 test, 5 validation, rest train',
        importance='DDS EVPI, 24 frozen-v4 + 8 uniform legal worlds; weight=1+3*min(EVPI/2,1)',
        target='uncertain remaining-card owner; no value or trick head',
        train_weighting='normalize importance weights to equal total mass per family',
        selection='four positions per ply band [0,8),[8,20),[20,32),[32,44), deterministic public hash',
        excluded_preflight_families=sorted(PREFLIGHT_EXCLUDED), created=time.time())
    save_json(path, m)
    return m


def worker_init(parent):
    global PARENT, SOLVER
    from bridge_harness.dds import DDS
    PARENT = DenseWeights(parent)
    SOLVER = DDS()


def selected_observations(entry):
    if entry['split'] == 'test': raise ValueError('Test families must remain unprepared')
    candidates = {}
    for source in entry['sources']:
        raw = Path(source['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('Frozen episode changed')
        episode = json.loads(gzip.decompress(raw))
        expected = 'validation' if int(entry['family'][:8],16) % 5 == 0 else 'train'
        if episode['split'] != expected: raise ValueError('Historical split mismatch')
        rooms = episode['unique_tables'].values() if 'unique_tables' in episode else [episode]
        for room in rooms:
            if room['status'] != 'ok': continue
            board = Board.from_dict(room['board'])
            if deal_key(board.hands, True) != entry['family']: raise ValueError('Family mismatch')
            if board.contract is None: continue
            roots = [t for t in room['tables'] if t.get('node') == 'root']
            if len(roots) != 1: raise ValueError('Expected exactly one root trajectory')
            game = Game(board)
            for action in roots[0]['actions']:
                o = game.observation()
                if len(o.history) < 44:
                    owners = np.zeros(52, np.int64)
                    for s, h in enumerate(game.hands):
                        owners[list(h)] = (s-o.controller) % 4
                    candidates.setdefault(public_key(o), (o, owners))
                game.play(card(action['card']))
            if not game.done or game.declarer_tricks != roots[0]['declarer_tricks']:
                raise ValueError('Root replay failed')
    chosen = []
    for low, high in [(0,8), (8,20), (20,32), (32,44)]:
        chosen.extend(sorted(k for k, (o, _) in candidates.items()
                             if low <= len(o.history) < high)[:4])
    chosen += [k for k in sorted(candidates) if k not in chosen][:16-len(chosen)]
    return [(key,*candidates[key]) for key in chosen]


def prepare_family(entry, output):
    if entry['split'] == 'test': raise ValueError('Test families must remain unprepared')
    output = Path(output); target = output/'data'/f"{entry['family']}.npz"
    meta = target.with_suffix('.json')
    if target.exists() and meta.exists():
        info = json.loads(meta.read_text())
        if sha(target) != info['sha256']: raise ValueError('Data shard changed')
        return info
    started = time.time()
    rows = []; infos = []
    for key,o,owners in selected_observations(entry):
        x, dense = encode(o); mask = x['support'].sum(-1) > 1
        if not mask.any(): continue
        if not np.all(x['support'][np.arange(52), owners] | ~mask):
            raise ValueError('Target not supported by public constraints')
        imp = importance(o, PARENT, SOLVER)
        rows.append(dict(**x, target=owners, mask=mask, weight=np.float32(imp['weight']),
            dense_state=dense['state'], dense_play=dense['play'],
            ply=np.int64(len(o.history)), role=np.int64(o.actor % 2 == o.contract.declarer % 2),
            strain=np.int64(o.contract.trump), key=np.array(key)))
        infos.append(imp)
    if not rows:
        info = dict(family=entry['family'], split=entry['split'], rows=0, targets=0, seconds=time.time()-started)
        save_json(meta, info); return info
    arrays = {k: np.stack([r[k] for r in rows]) for k in rows[0]}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.with_suffix('.tmp').open('wb') as out:
        np.savez_compressed(out, **arrays)
    target.with_suffix('.tmp').replace(target)
    info = dict(family=entry['family'], split=entry['split'], rows=len(rows),
        targets=int(arrays['mask'].sum()), sha256=sha(target),
        positive_evpi=sum(i['evpi'] > 0 for i in infos),
        mean_evpi=float(np.mean([i['evpi'] for i in infos])), seconds=time.time()-started)
    save_json(meta, info); return info


def prepare(args, manifest):
    pending = [e for e in manifest['families'] if e['split'] != 'test']
    counts = Counter(); targets = Counter(); families = Counter(); start = time.time()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=worker_init,
                             initargs=(str(args.parent),)) as pool:
        futures = [pool.submit(prepare_family, e, str(args.output)) for e in pending]
        for i, future in enumerate(as_completed(futures), 1):
            info = future.result()
            counts[info['split']] += info['rows']; targets[info['split']] += info['targets']
            families[info['split']] += bool(info['rows'])
            if i % 10 == 0 or i == len(pending):
                status = dict(stage='prepare', completed_families=i, total_families=len(pending),
                    rows=dict(counts), targets=dict(targets), seconds=time.time()-start, updated=time.time())
                save_json(args.output/'status.json', status)
                print(json.dumps(status), flush=True)
    dataset = dict(rows=dict(counts), targets=dict(targets), families=dict(families),
        test_families_reserved=sum(e['split'] == 'test' for e in manifest['families']),
        manifest_sha256=sha(args.output/'manifest.json'), parent_sha256=sha(args.parent))
    save_json(args.output/'dataset.json', dataset)
    return dataset


def load_arrays(args, manifest, wanted):
    chunks = []; family_index = 0
    for e in manifest['families']:
        if e['split'] != wanted: continue
        p = args.output/'data'/f"{e['family']}.npz"
        meta = json.loads(p.with_suffix('.json').read_text())
        if not meta['rows']: continue
        if sha(p) != meta['sha256']: raise ValueError('Data shard changed')
        with np.load(p, allow_pickle=False) as z:
            d = {k:z[k] for k in z.files}
        d['fit_weight'] = (d['weight']/d['weight'].sum()*16).astype(np.float32)
        d['family_index'] = np.full(len(d['target']), family_index, np.int64)
        family_index += 1; chunks.append(d)
    if not chunks: raise ValueError('No rows for '+wanted)
    return {k:np.concatenate([d[k] for d in chunks]) for k in chunks[0]}


def evaluate(model, arrays, batch_size, dense=False):
    import torch
    sums = {}; per_family = {}
    if not dense: model.eval()
    with torch.inference_mode():
        for lo in range(0, len(arrays['target']), batch_size):
            ix = np.arange(lo, min(lo+batch_size, len(arrays['target'])))
            if dense:
                z = model.predict(dict(state=arrays['dense_state'][ix], play=arrays['dense_play'][ix],
                                       calls=arrays['calls'][ix], seats=arrays['seats'][ix]))
            else:
                z = model(torch_batch(arrays, ix)).numpy()
            support=arrays['support'][ix]; mask=arrays['mask'][ix]; y=arrays['target'][ix]
            z=np.where(support,z,-1e9); z=z-z.max(-1,keepdims=True)
            p=np.exp(z); p=p/p.sum(-1,keepdims=True)
            truth=p[np.arange(len(ix))[:,None],np.arange(52),y]
            n=mask.sum(1)
            nll=(-np.log(np.maximum(truth,1e-30))*mask).sum(1)/n
            brier=((np.square(p).sum(-1)-2*truth+1)*mask).sum(1)/n
            acc=((p.argmax(-1)==y)*mask).sum(1)/n
            for j, row in enumerate(ix):
                for group in ['all', 'early' if arrays['ply'][row]<16 else 'later',
                              'declarer' if arrays['role'][row] else 'defender',
                              'notrump' if arrays['strain'][row]==4 else 'suit']:
                    s=sums.setdefault(group,np.zeros(7))
                    w=float(arrays['weight'][row]); s += [1,nll[j],brier[j],acc[j],w,w*nll[j],w*w]
                f=int(arrays['family_index'][row]); q=per_family.setdefault(f,[]); q.append(float(nll[j]))
    result={k:dict(positions=int(s[0]), nll=s[1]/s[0], brier=s[2]/s[0], accuracy=s[3]/s[0],
                   weighted_nll=s[5]/s[4], position_weight_ess=s[4]**2/s[6]) for k,s in sums.items()}
    result['family_nll']={str(k):float(np.mean(v)) for k,v in per_family.items()}
    return result


def train(args, manifest):
    import torch
    torch.set_num_threads(args.threads); torch.set_num_interop_threads(1)
    torch.manual_seed(SEED); np.random.seed(SEED)
    data = load_arrays(args, manifest, 'train'); val = load_arrays(args, manifest, 'validation')
    model = make_model(**ARCHITECTURE)
    parameters=sum(p.numel() for p in model.parameters())
    optimizer=torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=.01)
    n=len(data['target']); steps=(n+args.batch_size-1)//args.batch_size
    last=args.output/'last.pt'; epoch=offset=global_step=0; best=float('inf'); history=[]
    manifest_sha=sha(args.output/'manifest.json')
    if last.exists():
        c=torch.load(last,map_location='cpu',weights_only=False)
        if c['manifest_sha256'] != manifest_sha or c['batch_size'] != args.batch_size:
            raise ValueError('Resume configuration mismatch')
        model.load_state_dict(c['model']); optimizer.load_state_dict(c['optimizer'])
        epoch=c['epoch']; offset=c['offset']; global_step=c['global_step']; best=c['best']; history=c['history']
        torch.set_rng_state(c['torch_rng'])
    def checkpoint(path):
        c=dict(model=model.state_dict(), optimizer=optimizer.state_dict(), architecture=ARCHITECTURE,
            epoch=epoch,offset=offset,global_step=global_step,best=best,history=history,
            torch_rng=torch.get_rng_state(),manifest_sha256=manifest_sha,batch_size=args.batch_size)
        tmp=path.with_suffix('.tmp'); torch.save(c,tmp); tmp.replace(path)
    checkpoint(last)
    baseline_path=args.output/'v4-validation.json'
    if not baseline_path.exists():
        save_json(baseline_path,evaluate(DenseWeights(args.parent),val,256,dense=True))
    baseline=json.loads(baseline_path.read_text())
    start=time.time(); this_run_rows=0; recent=[]
    for ep in range(epoch,args.epochs):
        epoch=ep; order=np.random.default_rng(SEED+ep).permutation(n)
        model.train()
        for lo in range(offset,n,args.batch_size):
            ix=order[lo:lo+args.batch_size]
            lr=3e-4*min(1.,(global_step+1)/100)
            for g in optimizer.param_groups:g['lr']=lr
            optimizer.zero_grad(set_to_none=True)
            logits=model(torch_batch(data,ix))
            losses=per_position_loss(logits,torch.from_numpy(data['target'][ix]),
                torch.from_numpy(data['support'][ix]),torch.from_numpy(data['mask'][ix]))
            w=torch.from_numpy(data['fit_weight'][ix])
            loss=(losses*w).mean(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            optimizer.step(); global_step+=1; offset=lo+len(ix); this_run_rows+=len(ix)
            recent.append(float(loss.detach()))
            if global_step % 100 == 0 or offset == n:
                checkpoint(last)
                rate=this_run_rows/max(time.time()-start,.001)
                status=dict(stage='training',epoch=ep+1,epochs=args.epochs,positions=offset,
                    positions_per_epoch=n,parameters=parameters,global_step=global_step,
                    positions_per_second=rate,remaining_epoch_seconds=(n-offset)/rate,
                    recent_training_loss=float(np.mean(recent[-100:])),updated=time.time())
                save_json(args.output/'status.json',status); print(json.dumps(status),flush=True)
            if args.profile_steps and global_step>=args.profile_steps:
                checkpoint(last);return
        metrics=evaluate(model,val,args.batch_size)
        # A small fixed training diagnostic makes an overfitting gap visible without expensive full reevaluation.
        train_ix=np.random.default_rng(SEED).choice(n,min(2048,n),replace=False)
        train_metrics=evaluate(model,{k:v[train_ix] for k,v in data.items()},args.batch_size)
        diffs=np.array([metrics['family_nll'][f]-baseline['family_nll'][f] for f in metrics['family_nll']])
        result=dict(epoch=ep+1,validation=metrics,train_diagnostic=train_metrics,
            v4_validation=baseline['all'],delta_nll_vs_v4=float(diffs.mean()),
            family_cluster_se=float(diffs.std(ddof=1)/np.sqrt(len(diffs))) if len(diffs)>1 else None)
        save_json(args.output/f'epoch-{ep+1}-metrics.json',result)
        history.append({k:v for k,v in result.items() if k not in ('validation','train_diagnostic')})
        score_value=metrics['all']['weighted_nll']; improved=score_value<best
        if improved:best=score_value
        epoch=ep+1;offset=0
        checkpoint(args.output/f'epoch-{epoch}.pt');checkpoint(last)
        if improved:checkpoint(args.output/'best.pt')
        print(json.dumps(dict(stage='epoch_complete',epoch=epoch,validation=metrics['all'],
                              delta_nll_vs_v4=result['delta_nll_vs_v4'])),flush=True)
    save_json(args.output/'status.json',dict(stage='complete',epochs=epoch,parameters=parameters,
        updated=time.time(),history=history,test_evaluated=False,
        interpretation='Ownership screen only; paired fixed-policy play evaluation still required'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=Path('models/belief-v4.npz'))
    p.add_argument('--sources',nargs='*',default=[])
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--threads',type=int,default=2)
    p.add_argument('--batch-size',type=int,default=32)
    p.add_argument('--epochs',type=int,default=3)
    p.add_argument('--max-families',type=int,default=0)
    p.add_argument('--profile-steps',type=int,default=0)
    p.add_argument('--stage',choices=['all','prepare','train'],default='all')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'PAUSED_BY_USER').exists():
        raise SystemExit('Attention run paused by user; do not resume it')
    import fcntl
    with (args.output/'writer.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        m=freeze(args)
        if args.stage in ('all','prepare'):prepare(args,m)
        if args.stage in ('all','train'):train(args,m)


if __name__=='__main__':main()
