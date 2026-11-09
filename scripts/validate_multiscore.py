"""Read-only parity and small cost check against an existing frozen arena.

Use a separate checkout and BRIDGE_DDS_LIBRARY; never change the live run.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import random
import sys
import time
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from bridge_harness.core import Game
from bridge_harness.corpus import load
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.multiscore import MultiScorePlayer

COST = {'dds_calls','dds_native_solves','dds_cache_hits','dds_duplicate_worlds',
        'dds_nodes','work_accounting','scored_budget'}


def check(run, count):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    manifest = json.loads((run/'manifest.json').read_text())
    spec = manifest['bots'][manifest['candidate']]
    reference = manifest['bots'][manifest['reference']]
    for bot in (spec, reference):
        for kind, expected in bot.get('artifact_sha256', {}).items():
            if sha(run/bot[kind]) != expected:
                raise ValueError('Frozen artifact changed')
    multi = MultiScorePlayer(ArenaPlayer(spec, run, reference))
    solo = {n: ArenaPlayer(dict(spec, samples=n), run, reference) for n in (16,32,64)}
    rows = []; cpu = dict(joint=0., separate=0., solo64=0.)
    try:
        for board in list(load(run/manifest['corpus']))[:count]:
            game = Game(board); moves = random.Random(381)
            for ply in range(52):
                o = game.observation()
                if ply in (0, 12, 24, 36, 44, 48) and len(o.legal) > 1:
                    seed = 197+ply
                    def together():
                        start=time.process_time(); result=multi.choose_all(o, random.Random(seed))
                        cpu['joint']+=time.process_time()-start
                        return result
                    def separately():
                        results={}
                        for n, player in solo.items():
                            rng=random.Random(seed);start=time.process_time()
                            d=player.choose(o,rng);elapsed=time.process_time()-start
                            cpu['separate']+=elapsed
                            if n==64:cpu['solo64']+=elapsed
                            results[n]=(d,rng.getstate())
                        return results
                    if len(rows)%2: expected=separately(); actual=together()
                    else: actual=together(); expected=separately()
                    for n,(d,state) in expected.items():
                        a=actual.decisions[n]
                        assert a.card==d.card
                        assert {k:v for k,v in a.details.items() if k not in COST}=={k:v for k,v in d.details.items() if k not in COST}
                        assert actual.rng_states[n]==state
                    rows.append(dict(board=board.id,ply=ply,cards={n:d.card for n,d in actual.decisions.items()},shared_work=actual.shared_work))
                game.play(moves.choice(o.legal))
    finally:
        multi.close()
        for player in solo.values():player.close()
    return dict(schema='multiscore-validation-v1',manifest_identity=manifest['identity'],
        artifact_sha256=spec['artifact_sha256'],positions=len(rows),budget_decisions=3*len(rows),
        exact_cards_estimates_probabilities_reference_and_rng=True,cpu_seconds=cpu,
        joint_over_separate=cpu['joint']/cpu['separate'],joint_over_solo64=cpu['joint']/cpu['solo64'],
        caveat='Small alternating-order CPU check on random legal trajectories, cache disabled. Not a full-board collection throughput claim.',rows=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--boards',type=int,default=2);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=check(a.run,a.boards);a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=2))
