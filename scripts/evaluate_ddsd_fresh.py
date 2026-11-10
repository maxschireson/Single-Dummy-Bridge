"""Fresh, resumable three-way global-choice forks under frozen Gen5 continuation.

One randomly selected nonforced position per phase, regardless of disagreement
or outcome. Identical choices reuse their continuation and count as zero gains.
The base trajectory and every continuation use the same frozen Gen5 player.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse,gzip,hashlib,json,random,sys,time
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,symbol,imps,card
from bridge_harness.bidding_env import deal_key
from bridge_harness.belief_capacity import Weights
from bridge_harness.bidding_sampling import WeightedSampler
from bridge_harness.auction_policy import AuctionSelectorWeights,encode_decision
from bridge_harness.dds import DDS
from bridge_harness.ddsd_corrector import Corrector,encode
from bridge_harness.selfplay import atomic_json
from scripts.train_ddsd_corrector import family_stats

METHODS=('pimc','v5','corrector')
PHASES=((0,20),(20,40),(40,52))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def seed_for(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps(parts,separators=(',',':')).encode()).digest()[:16],'big')

def argmax_common(values,priority):
    best=max(values.values())
    return min((c for c,v in values.items() if abs(v-best)<=1e-7),key=lambda c:priority[c])

class Search:
    def __init__(self,m):
        self.m=m;self.belief=Weights(m['models']['belief']['path'])
        self.policy=AuctionSelectorWeights(m['models']['policy']['path'])
        self.corrector=Corrector(m['models']['corrector']['path'])
        self.dds=DDS(m['models']['dds']['path'],cache_path='')
        self.policy_features=[5/6,m['samples']/192,1.,m['window']]*4

    def evaluate(self,o,seed,with_corrector=False):
        if len(o.legal)==1:
            c=o.legal[0];return dict(choices={k:c for k in METHODS},forced=True)
        rng=random.Random(seed);sampler=WeightedSampler(o,self.belief.logits(o))
        worlds=[sampler.draw(rng) for _ in range(self.m['samples'])]
        solved=self.dds.solve_batch(worlds,o.contract.trump,o.leader,o.trick,
            fixed_seats=[s for s,h in enumerate(o.known_hands) if h is not None])
        legal=sorted(o.legal)
        dd=np.array([[v[c] for c in legal] for v,_ in solved],dtype=float)
        means=dict(zip(legal,dd.mean(0)));best=max(means.values())
        eligible=[c for c in legal if best-means[c]<=self.m['window']+1e-9]
        declaring=o.actor%2==o.contract.declarer%2
        already=o.declarer_tricks if declaring else len(o.history)//4-o.declarer_tricks
        details=dict(samples=self.m['samples'],near_tie=self.m['window'],
            estimates={symbol(c):dict(utility=q+already-(0 if declaring else 13)) for c,q in means.items()},
            behavior_probabilities={symbol(c):float(c in eligible)/len(eligible) for c in legal})
        x,cards=encode_decision(o,details);valid=x['mask'][0].astype(bool)
        np.testing.assert_allclose(x['q'][0,valid],[means[int(c)] for c in cards[0,valid]],rtol=0,atol=1e-6)
        pred=self.policy.predict(x)[0];pv={int(c):float(v) for c,v,ok in zip(cards[0],pred,valid) if ok}
        priority={c:seed_for(seed,'shared-tie',c) for c in legal}
        choices=dict(pimc=argmax_common(means,priority),v5=argmax_common(pv,priority))
        q=dict(pimc=means,v5=pv)
        if with_corrector:
            states=[];calls=[]
            for hands,(values,_) in zip(worlds,solved):
                for c in eligible:
                    state,cs=encode(o,hands,c,values[c],self.policy_features);states.append(state);calls.append(cs)
            residual=self.corrector.predict(states,calls).reshape(-1,len(eligible)).mean(0)
            q['corrector']={c:means[c]+self.m['weight']*float(r) for c,r in zip(eligible,residual)}
            choices['corrector']=argmax_common(q['corrector'],priority)
        return dict(choices=choices,values=q,eligible=eligible,forced=False)

    def play(self,board,prefix=(),forced=None):
        game=Game(board);actions=[]
        for c in prefix:game.play(c);actions.append(c)
        if forced is not None:game.play(forced);actions.append(forced)
        decision_plies=[]
        while not game.done:
            o=game.observation();ply=len(game.history)
            if len(o.legal)>1:decision_plies.append(ply)
            seed=seed_for(self.m['seed'],board.id,'play',ply,o.controller)
            c=self.evaluate(o,seed)['choices']['v5']
            game.play(c);actions.append(c)
        return dict(actions=actions,declarer_tricks=game.declarer_tricks,ns_score=game.ns_score(),decision_plies=decision_plies)

    def board(self,item):
        index,raw=item;board=Board.from_dict(raw);family=deal_key(board.hands,True);started=time.time()
        if board.contract is None:
            return dict(index=index,family=family,passed_out=True,board=raw,audits=[],seconds=time.time()-started)
        base=self.play(board);audits=[];branches=[]
        for phase,(lo,hi) in enumerate(PHASES):
            possible=[p for p in base['decision_plies'] if lo<=p<hi]
            if not possible:continue
            ply=random.Random(seed_for(self.m['seed'],family,'audit',phase)).choice(possible)
            prefix=base['actions'][:ply];game=Game(board)
            for c in prefix:game.play(c)
            o=game.observation();seed=seed_for(self.m['seed'],board.id,'play',ply,o.controller)
            scored=self.evaluate(o,seed,with_corrector=True)
            assert scored['choices']['v5']==base['actions'][ply], 'Base and audit searches differ'
            assert scored['values']['pimc'][scored['choices']['pimc']]==max(scored['values']['pimc'].values())
            outcomes={base['actions'][ply]:base};branch_indices={base['actions'][ply]:-1}
            for c in sorted(set(scored['choices'].values())):
                if c not in outcomes:
                    branch=self.play(board,prefix,c);outcomes[c]=branch
                    branch_indices[c]=len(branches);branches.append(branch)
            declaring=o.actor%2==o.contract.declarer%2
            already=o.declarer_tricks if declaring else ply//4-o.declarer_tricks
            y={c:(r['declarer_tricks'] if declaring else 13-r['declarer_tricks'])-already for c,r in outcomes.items()}
            baseline=outcomes[scored['choices']['pimc']]
            gains={};tricks={}
            for method in METHODS:
                r=outcomes[scored['choices'][method]]
                gains[method]=imps((r['ns_score']-baseline['ns_score'])*(1 if o.actor%2==0 else -1))
                tricks[method]=(r['declarer_tricks']-baseline['declarer_tricks'])*(1 if declaring else -1)
            direct=imps((outcomes[scored['choices']['corrector']]['ns_score']-outcomes[scored['choices']['v5']]['ns_score'])*(1 if o.actor%2==0 else -1))
            true_dd,_=self.dds.solve(tuple(tuple(sorted(h)) for h in game.hands),o.contract.trump,o.leader,o.trick)
            audit=dict(ply=ply,phase=phase,actor=o.actor,declaring=declaring,choices={k:symbol(c) for k,c in scored['choices'].items()},
                values={k:{symbol(c):float(v) for c,v in values.items()} for k,values in scored['values'].items()},
                true_dd={symbol(c):true_dd[c] for c in outcomes},outcomes={symbol(c):v for c,v in y.items()},
                branches={symbol(c):i for c,i in branch_indices.items()},imp_gain=gains,trick_gain=tricks,
                corrector_vs_v5_imps=direct,distinct_choices=len(set(scored['choices'].values())),
                any_outcome_difference=len(set(y.values()))>1,
                pimc_gap_to_v5=max(scored['values']['pimc'].values())-scored['values']['pimc'][scored['choices']['v5']],
                pimc_gap_to_corrector=max(scored['values']['pimc'].values())-scored['values']['pimc'][scored['choices']['corrector']])
            audits.append(audit)
        return dict(index=index,family=family,board=raw,passed_out=False,base=base,branches=branches,audits=audits,seconds=time.time()-started)

def initialize(manifest):
    global SEARCH
    torch.set_num_threads(1);SEARCH=Search(manifest)

def work(item):return SEARCH.board(item)

def summarize(records,target,elapsed):
    rows=[(r['index'],a) for r in records for a in r['audits']]
    out=dict(complete=len(records)==target,boards=len(records),target=target,
        passed_out=sum(r['passed_out'] for r in records),decisions=len(rows),
        extra_continuations=sum(len(r.get('branches',[])) for r in records),
        disagreements=sum(a['distinct_choices']>1 for _,a in rows),
        unequal_outcomes=sum(a['any_outcome_difference'] for _,a in rows),
        elapsed_seconds=elapsed,updated_epoch=time.time(),promoted=False,
        unit='Equal-board mean of audited decision gains; not IMP per board of whole-agent play')
    if not rows:return out
    groups=np.array([i for i,a in rows])
    out['comparisons']={}
    for method in ('v5','corrector'):
        out['comparisons'][method+'_vs_pimc']=dict(
            imps=family_stats([a['imp_gain'][method] for _,a in rows],groups),
            tricks=family_stats([a['trick_gain'][method] for _,a in rows],groups))
    out['comparisons']['corrector_vs_v5']=dict(
        imps=family_stats([a['corrector_vs_v5_imps'] for _,a in rows],groups),
        tricks=family_stats([a['trick_gain']['corrector']-a['trick_gain']['v5'] for _,a in rows],groups))
    out['by_phase']={}
    for phase in range(3):
        part=[(i,a) for i,a in rows if a['phase']==phase]
        if part:out['by_phase'][str(phase)]={m:family_stats([a['imp_gain'][m] for _,a in part],[i for i,a in part]) for m in ('v5','corrector')}
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    for name in ('belief','policy','corrector','dds'):p.add_argument('--'+name,type=Path)
    p.add_argument('--samples',type=int,default=32);p.add_argument('--window',type=float,default=.125)
    p.add_argument('--weight',type=float,default=1.);p.add_argument('--seed',type=int,default=202611106618)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int)
    p.add_argument('--summarize',action='store_true');a=p.parse_args();root=a.run.resolve()
    boards=[json.loads(s) for s in (root/'boards.jsonl').read_text().splitlines()]
    manifest_path=root/'evaluation-manifest.json'
    if manifest_path.exists():m=json.loads(manifest_path.read_text())
    else:
        if any(getattr(a,k) is None for k in ('belief','policy','corrector','dds')):raise ValueError('Initial run requires every model')
        m=dict(schema='ddsd-fresh-global-choice-v1',models={k:dict(path=str(getattr(a,k).resolve()),sha256=sha(getattr(a,k))) for k in ('belief','policy','corrector','dds')},
            corpus_sha256=sha(root/'boards.jsonl'),samples=a.samples,window=a.window,weight=a.weight,seed=a.seed,target=len(boards),
            phases=PHASES,selection='One uniform nonforced base-trajectory decision per phase, independent of predictions and outcomes',
            continuation='All seats frozen Gen5 belief and policy; common streams keyed by board, ply and controller',
            choices='Global PIMC best; V5 and corrector best inside global 0.125-trick PIMC window; common uniform tie ordering',
            training='No updates; current-policy transfer test of the historical-policy-trained corrector',
            source_sha256={str(f.relative_to(ROOT)):sha(f) for f in [Path(__file__).resolve(),ROOT/'bridge_harness/ddsd_corrector.py']})
        atomic_json(manifest_path,m)
    for v in m['models'].values():
        if sha(v['path'])!=v['sha256']:raise ValueError('Frozen model changed')
    if sha(root/'boards.jsonl')!=m['corpus_sha256']:raise ValueError('Frozen corpus changed')
    for name,digest in m['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen evaluator changed')
    directory=root/'episodes';directory.mkdir(exist_ok=True)
    records=[json.load(gzip.open(f,'rt')) for f in sorted(directory.glob('*.json.gz'))]
    done={r['index'] for r in records};started=time.time()
    if not a.summarize:
        import fcntl
        lock=(root/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        jobs=iter((i,b) for i,b in enumerate(boards) if i not in done and (a.limit is None or i<a.limit))
        with ProcessPoolExecutor(max_workers=a.workers,initializer=initialize,initargs=(m,)) as pool:
            pending={}
            def submit():
                item=next(jobs,None)
                if item is not None:pending[pool.submit(work,item)]=item[0]
            for _ in range(a.workers):submit()
            while pending:
                finished,_=wait(pending,timeout=5,return_when=FIRST_COMPLETED)
                for future in finished:
                    index=pending.pop(future);r=future.result()
                    r['manifest_sha256']=sha(manifest_path)
                    atomic_json(directory/f'{index:06}.json.gz',r,compressed=True);records.append(r)
                    print(json.dumps(dict(boards=len(records),index=index,seconds=r['seconds'],audits=len(r['audits']))),flush=True)
                    if not (root/'STOP').exists():submit()
                state=summarize(records,len(boards),time.time()-started);state['in_flight']=list(pending.values())
                atomic_json(root/'status.json',state)
    result=summarize(records,len(boards),time.time()-started)
    atomic_json(root/'result.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
