#!/usr/bin/env python3
"""Profile pinned external BEN bidding without changing its search settings.

BEN (lorserker/ben) is GPL-3.0; this driver loads an external checkout and models.
No BEN source, models, bulk profiles or generated games belong in this repository.
"""
import argparse
from collections import defaultdict
import cProfile
import functools
import hashlib
import json
import os
from pathlib import Path
import pstats
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ben-dir',required=True)
    p.add_argument('--config',required=True)
    p.add_argument('--requests',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--limit',type=int)
    p.add_argument('--profile',action='store_true')
    p.add_argument('--variant',default='baseline',choices=['baseline','scalar-cache','native-cache'])
    args=p.parse_args()
    ben=Path(args.ben_dir).resolve();out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    requests=json.loads(Path(args.requests).read_text())
    if args.limit:requests=requests[:args.limit]
    os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
    os.environ.setdefault('TF_NUM_INTRAOP_THREADS','1')
    os.environ.setdefault('TF_NUM_INTEROP_THREADS','1')
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    os.chdir(ben)
    sys.path.insert(0,str(ben/'src'))
    import numpy as np
    import tensorflow as tf
    import conf
    from nn.models_tf2 import Models
    from nn.timing import ModelTimer
    from sample import Sample
    from botbidder import BotBid
    from ddsolver.ddsolver import DDSolver
    from bidding import bidding
    from cached_dds import ScalarDDSCache
    config=conf.load(str(Path(args.config).resolve()))
    models=Models.from_conf(config,str(ben),False)
    sampler=Sample.from_conf(config,False)
    dds=DDSolver(max_threads=config.getint('dds','dds_max_threads',fallback=2))
    native=None
    if args.variant=='native-cache':
        from native_dds import NativeScalarDDS
        native=NativeScalarDDS(dds,workers=config.getint('dds','dds_max_threads',fallback=2))
    ModelTimer.enabled=True
    stage=defaultdict(lambda:dict(calls=0,seconds=0))
    for name in ('sample_hands_for_auction','bidding_rollout','expected_tricks_dd','evaluate_rescue_bid'):
        original=getattr(BotBid,name)
        def wrap(fn,label):
            @functools.wraps(fn)
            def timed(*a,**kw):
                start=time.perf_counter()
                try:return fn(*a,**kw)
                finally:
                    stage[label]['calls']+=1
                    stage[label]['seconds']+=time.perf_counter()-start
            return timed
        setattr(BotBid,name,wrap(original,name))
    try:
        for i,request in enumerate(requests):
            dest=out/f'{i:03d}-{request["id"]}.json'
            if dest.exists():raise ValueError(f'Refuse overwrite {dest}')
            np.random.seed(42);tf.random.set_seed(42)
            stage.clear();ModelTimer.reset()
            dealer='NESW'.index(request['dealer']);seat='NESW'.index(request['seat'])
            ctx=request['ctx']
            calls=[{'--':'PASS','Db':'X','Rd':'XX'}.get(ctx[j:j+2],ctx[j:j+2]) for j in range(0,len(ctx),2)]
            auction=['PAD_START']*dealer+calls
            assert len(auction)%4==seat
            vul=request['vul'];vuln=[vul in ('Both','NS'),vul in ('Both','EW')]
            cached=ScalarDDSCache(native or dds,enabled=args.variant!='baseline')
            bot=BotBid(vuln,request['hand'],models,sampler,seat,dealer,cached,False,False)
            profile=cProfile.Profile()
            started=time.perf_counter()
            if args.profile:profile.enable()
            response=bot.bid(auction).to_dict()
            if args.profile:profile.disable()
            elapsed=time.perf_counter()-started
            result=dict(request=request,variant=args.variant,seconds=elapsed,stages=dict(stage),
                model_timing=ModelTimer.get_stats(),response=response,dds_cache=cached.stats(),
                config_sha256=hashlib.sha256(Path(args.config).read_bytes()).hexdigest())
            dest.write_text(json.dumps(result,indent=2)+'\n')
            if args.profile:
                profile.dump_stats(str(dest.with_suffix('.prof')))
                with dest.with_suffix('.profile.txt').open('w') as f:
                    pstats.Stats(profile,stream=f).strip_dirs().sort_stats('cumulative').print_stats(35)
            print(json.dumps(dict(id=request['id'],seconds=elapsed,bid=response['bid'],stages=dict(stage),
                model_timing=ModelTimer.get_stats(),dds_cache=cached.stats())),flush=True)
    finally:
        if native:native.close()
        dds._pool.shutdown(wait=True)


if __name__=='__main__':main()
