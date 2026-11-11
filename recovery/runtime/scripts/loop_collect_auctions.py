#!/usr/bin/env python3
"""Batched BEN net-only auctions, loading only the bidder (no play/search nets).

Uses BEN's own encoder, legality checks and Bidder class from the separately
installed GPL-3.0 project https://github.com/lorserker/ben. No BEN code/weights
are redistributed. Only the current bidder's hand crosses the encoder boundary.
"""
import argparse
from collections import defaultdict
import configparser
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.core import auction_contract,hand_text
from bridge_harness.corpus import load,save
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ben-dir',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--input-corpus',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--count',type=int,required=True);p.add_argument('--batch-size',type=int,default=128)
    p.add_argument('--verify-scalar',type=int,default=8)
    a=p.parse_args();ben=a.ben_dir.resolve();cfg=a.config.resolve();out=a.out.resolve()
    if out.exists():raise ValueError('Output exists')
    boards=load(a.input_corpus);config=configparser.ConfigParser();config.read(cfg)
    if len(boards)!=a.count or len({digest(b.hands) for b in boards})!=a.count:raise ValueError('Bad input cohort')
    if config.getfloat('bidding','search_threshold')!=-1 or config.getboolean('bidding','check_final_contract'):
        raise ValueError('Explicit net-only/no-rescue bidding config required')
    if any(config.getboolean('models',k) for k in ('use_bba','consult_bba')):
        raise ValueError('BBA must be disabled')
    for k,v in {'TF_CPP_MIN_LOG_LEVEL':'3','TF_NUM_INTRAOP_THREADS':'1','TF_NUM_INTEROP_THREADS':'1',
                'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}.items():os.environ.setdefault(k,v)
    sys.path.insert(0,str(ben/'src'))
    import numpy as np
    import binary
    from bidding import bidding
    from nn.bidder_tf2 import Bidder
    model_path=(ben/config.get('bidding','bidder')).resolve()
    models=SimpleNamespace(n_cards_bidding=config.getint('models','n_cards_bidding'),
        model_version=config.getint('models','model_version'),adjust_hcp=config.getboolean('bidding','adjust_hcp'),
        ns=config.getint('models','ns'),ew=config.getint('models','ew'))
    if models.model_version!=3:raise ValueError('Pinned v3 bidder required')
    model=Bidder('loop-net-only',str(model_path),config.getboolean('bidding','alert_supported'))
    out.mkdir(parents=True);results={};calls=0;checked=0;max_error=0.;started=time.monotonic()
    for start in range(0,len(boards),a.batch_size):
        active=[dict(board=b,calls=[]) for b in boards[start:start+a.batch_size]]
        while active:
            groups=defaultdict(list)
            for item in active:
                b=item['board'];prefix=item['calls'];seat=(b.dealer+len(prefix))%4
                auction=['PAD_START']*b.dealer+prefix
                if len(prefix)>=320:raise ValueError('Auction too long')
                first=seat
                while first<len(auction) and auction[first]=='PAD_START':first+=4
                steps=1+(len(auction)-first)//4
                own=binary.parse_hand_f(models.n_cards_bidding)(hand_text(b.hands[seat]))
                x=binary.get_auction_binary(steps,auction,seat,own,
                    [b.vulnerability in ('NS','Both'),b.vulnerability in ('EW','Both')],models)
                groups[steps].append((item,auction,x))
            following=[]
            for group in groups.values():
                x=np.concatenate([r[2] for r in group],axis=0)
                probabilities,_=model.pred_fun_seq(x)
                for i,(item,auction,one) in enumerate(group):
                    values=probabilities[i,-1]
                    if not np.isfinite(values).all():raise ValueError('Nonfinite bidder probabilities')
                    legal=[j for j in np.argsort(-values,kind='stable') if bidding.can_bid(bidding.ID2BID[j],auction)]
                    bid=bidding.ID2BID[legal[0]]
                    if checked<a.verify_scalar:
                        scalar,_=model.pred_fun_seq(one);err=float(np.abs(scalar[0,-1]-values).max())
                        scalar_legal=[j for j in np.argsort(-scalar[0,-1],kind='stable') if bidding.can_bid(bidding.ID2BID[j],auction)]
                        if err>1e-4 or bidding.ID2BID[scalar_legal[0]]!=bid:raise ValueError('Batched/scalar mismatch')
                        checked+=1;max_error=max(max_error,err)
                    item['calls'].append(bid);calls+=1;b=item['board']
                    try:ct=auction_contract(b.dealer,item['calls'])
                    except ValueError as e:
                        if str(e)!='Incomplete auction':raise
                        following.append(item);continue
                    results[b.id]=replace(b,contract=ct,auction=tuple(item['calls']),opening_lead=None,
                                          auction_source='BEN-neural-only-batched')
            active=following
    save([results[b.id] for b in boards],out/'frozen.jsonl')
    atomic_json(out/'manifest.json',dict(bidder='BEN-neural-only',requested_deals=a.count,calls=calls,
        config_sha256=sha(cfg),model_sha256=sha(model_path),source_sha256=sha(__file__),
        search=False,rescue=False,dds_calls=0,loaded_networks=['bidder'],scalar_checked=checked,
        max_scalar_error=max_error,seconds=time.monotonic()-started))
    print(json.dumps(read_manifest(out)),flush=True)


def read_manifest(out):return json.loads((out/'manifest.json').read_text())


if __name__=='__main__':main()
