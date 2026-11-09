#!/usr/bin/env python3
"""Measure exact replay and changed-behavior reuse; never claim a new-version hit rate."""
import argparse
import json
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.players import PIMCPlayer
from bridge_harness.selfplay import atomic_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--deals',type=int,default=4)
    p.add_argument('--samples',type=int,default=8)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Refusing overwrite')
    a.out.mkdir(parents=True)
    cache = a.out/'positions.sqlite'
    boards = list(generate(a.deals,seed=2026110917))
    results,reference,changed_reference = {},None,None
    previous = os.environ.get('BRIDGE_DDS_CACHE')
    try:
        for name,enabled,band in (('uncached',False,0.),('cold_cache',True,0.),
                                   ('warm_replay',True,0.),('changed_uncached',False,.125),
                                   ('changed_near_tie',True,.125)):
            os.environ['BRIDGE_DDS_CACHE'] = str(cache.resolve()) if enabled else ''
            begin = time.monotonic()
            player = PIMCPlayer(a.samples,'tricks',True,band)
            traces=[];requests=0
            try:
                for i,b in enumerate(boards):
                    game=Game(b);trace=[]
                    while not game.done:
                        o=game.observation()
                        d=player.choose(o,random.Random(10101+i*1009+len(o.history)))
                        trace.append((d.card,d.details.get('estimates')))
                        requests+=d.details.get('dds_calls',0)
                        game.play(d.card)
                    traces.append(trace)
                stats=player.dds.cache_stats()
            finally:
                player.close()
            elapsed=time.monotonic()-begin
            if name=='uncached':
                reference=traces
            elif name in ('cold_cache','warm_replay') and traces!=reference:
                raise ValueError('Caching changed actions or evaluations')
            elif name=='changed_uncached':
                changed_reference=traces
            elif name=='changed_near_tie' and traces!=changed_reference:
                raise ValueError('Caching changed the alternate policy behavior')
            results[name]=dict(seconds=elapsed,requested_worlds=requests,**stats)
            print(json.dumps(dict(phase=name,**results[name])),flush=True)
    finally:
        if previous is None:
            os.environ.pop('BRIDGE_DDS_CACHE',None)
        else:
            os.environ['BRIDGE_DDS_CACHE']=previous
    report=dict(deals=a.deals,samples=a.samples,results=results,
        warm_speedup=results['uncached']['seconds']/results['warm_replay']['seconds'],
        changed_speedup=results['changed_uncached']['seconds']/results['changed_near_tie']['seconds'],
        cache_bytes=cache.stat().st_size,identical_replay_verified=True,
        limitation='Small uniform-PIMC benchmark. Changed near-tie behavior is not a trained candidate or updated belief net.',
        test_promotion=False)
    atomic_json(a.out/'result.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
