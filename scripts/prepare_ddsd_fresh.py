"""Reserve fresh canonical test deals and freeze neural-only Gen5 auctions."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS'):
    os.environ[key]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import argparse,hashlib,json,sys,time
from dataclasses import replace
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,auction_contract
from bridge_harness.bidding_env import deal_key,BidObservation,encode,legal_mask,pack_inputs,CALLS
from bridge_harness.bidding_ppo import Policy
from bridge_harness.selfplay import atomic_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--bidder',type=Path,required=True)
    p.add_argument('--count',type=int,default=256);p.add_argument('--seed',type=int,default=202611106617)
    p.add_argument('--exclude-families',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    blocked={r['family'] for r in json.loads(a.exclude_families.read_text())}
    rng=np.random.default_rng(a.seed);boards=[];families=set();started=time.time()
    while len(boards)<a.count:
        cards=rng.permutation(52);hands=tuple(tuple(sorted(map(int,cards[13*s:13*s+13]))) for s in range(4))
        family=deal_key(hands,True)
        if int(family[:8],16)%10!=0 or family in blocked or family in families:continue
        families.add(family);boards.append(Board(family,hands,None,int(rng.integers(4)),('None','NS','EW','Both')[int(rng.integers(4))]))
    config=dict(schema='ddsd-fresh-auctions-v1',count=a.count,seed=a.seed,
        bidder=str(a.bidder.resolve()),bidder_sha256=hashlib.sha256(a.bidder.read_bytes()).hexdigest(),
        rule='Fresh random deals, canonical test bucket zero, no prior corrector family; permanently evaluation-only',
        excluded_families=len(blocked),excluded_sha256=hashlib.sha256(a.exclude_families.read_bytes()).hexdigest())
    atomic_json(a.out/'auction-config.json',config)
    atomic_json(a.out/'reserved-families.json',sorted(families))
    policy=Policy.load(a.bidder);calls=[[] for _ in boards];active=list(range(len(boards)))
    while active:
        obs=[BidObservation(boards[i].hands[(boards[i].dealer+len(calls[i]))%4],
            (boards[i].dealer+len(calls[i]))%4,boards[i].dealer,boards[i].vulnerability,tuple(calls[i])) for i in active]
        x,lengths=pack_inputs([encode(o) for o in obs]);probs,_=policy.predict(x,lengths);pending=[]
        for i,pr in zip(active,probs):
            allowed=legal_mask(boards[i].dealer,calls[i]);action=int(np.argmax(np.where(allowed,pr,-np.inf)))
            calls[i].append(CALLS[action])
            if len(calls[i])>64:raise ValueError('Auction beyond critic support')
            try:contract=auction_contract(boards[i].dealer,calls[i])
            except ValueError as e:
                if str(e)!='Incomplete auction':raise
                pending.append(i);continue
            boards[i]=replace(boards[i],contract=contract,auction=tuple(calls[i]),auction_source='fresh-gen6-evaluation-gen5-neural-only')
        active=pending
    output=a.out/'boards.jsonl';output.write_text(''.join(json.dumps(b.to_dict())+'\n' for b in boards))
    atomic_json(a.out/'auction-result.json',dict(boards=len(boards),passed_out=sum(b.contract is None for b in boards),
        corpus_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),seconds=time.time()-started))
    print((a.out/'auction-result.json').read_text(),flush=True)

if __name__=='__main__':main()
