"""Replay sampled production DDS queries without touching the live arena/cache.

Capture the exact RNG-derived worlds at saved main/fork observations, then
replay identical queries through upstream scalar and production ablations.
Branch prefixes and forced moves do not issue new DDS queries.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, Game, card, symbol
from bridge_harness.dds import DDS
from bridge_harness.fork_audit import stream
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import ArenaPlayer, validate_pair, verify_generation
from bridge_harness.selfplay import atomic_json


MODES = ('upstream_scalar', 'compact_scalar', 'batch_reset',
         'batch_retained', 'production_cache')


def capture(run, out, count, seed):
    m = read(run/'manifest.json'); verify_generation(run, m)
    available = sorted((run/'episodes').glob('*.json.gz'))
    chosen = random.Random(seed).sample(available, count)
    selection = dict(seed=seed, available_completed=len(available),
        manifest_identity=m['identity'], episodes=[dict(file=p.name, sha256=sha(p)) for p in chosen])
    atomic_json(out/'selection.json', selection)
    previous = os.environ.get('BRIDGE_DDS_CACHE')
    os.environ['BRIDGE_DDS_CACHE'] = ''
    captured = []
    try:
        for path in chosen:
            x = read(path); b = Board.from_dict(x['board'])
            validate_pair(x, m, b, x['index'])
            versions = dict(candidate=x['candidate'], reference=x['reference'], environment=x['opponent'])
            players = {k:ArenaPlayer(m['bots'][v], run) for k,v in versions.items()}
            queries=[]; total_requested=0
            try:
                for part in ('control','focal'):
                    for table in x[part]['tables']:
                        game=Game(b)
                        for action in table['actions']:
                            o=game.observation(); ply=len(game.history)
                            if not action.get('replayed_prefix') and action.get('dds_calls',0):
                                player=players[action['player']]
                                rng=stream(x[part]['seed'],'play',b.id,ply,o.controller)
                                sampler=player.sampler_factory(o)
                                worlds=[sampler.draw(rng) for _ in range(player.samples)]
                                assert len(worlds)==action['dds_calls']==32
                                assert len(set(worlds))==action['unique_worlds']
                                queries.append(dict(player=action['player'],part=part,node=table['node'],
                                    kind='main' if table['depth']==0 else 'fork',ply=ply,
                                    worlds=worlds,trump=o.contract.trump,leader=o.leader,trick=o.trick,
                                    fixed_seats=[s for s,h in enumerate(o.known_hands) if h is not None],
                                    declaring=o.actor%2==o.contract.declarer%2,
                                    future_tricks=13-len(o.history)//4,declarer_tricks=o.declarer_tricks,
                                    expected={c:v['declarer_tricks'] for c,v in action['estimates'].items()}))
                                total_requested+=len(worlds)
                            game.play(card(action['card']))
                        assert game.ns_score()==table['ns_score']
            finally:
                for player in players.values():player.close()
            captured.append(dict(index=x['index'],family=x['family'],opponent=x['opponent'],
                production_cpu=x['base_cpu']+x['branch_cpu'],queries=queries))
            print(json.dumps(dict(phase='captured',index=x['index'],queries=len(queries),worlds=total_requested)),flush=True)
    finally:
        if previous is None:os.environ.pop('BRIDGE_DDS_CACHE',None)
        else:os.environ['BRIDGE_DDS_CACHE']=previous
    atomic_json(out/'trace.json.gz',captured,compressed=True)
    return captured


def verify_outputs(query, solved):
    cards=set(card(c) for c in query['expected'])
    assert len(solved)==len(query['worlds'])
    totals={c:0 for c in cards}
    for values,_ in solved:
        if set(values)!=cards:raise ValueError('Legal move mismatch')
        for c,v in values.items():
            totals[c]+=query['declarer_tricks']+(v if query['declaring'] else query['future_tricks']-v)
    for c,v in totals.items():
        if abs(v/len(solved)-query['expected'][symbol(c)])>1e-10:
            raise ValueError(f"Production estimate differs at {query['part']}/{query['node']}/{query['ply']}/{symbol(c)}")


def measure(board, mode, upstream, out, tt_kind=2):
    library=upstream if mode=='upstream_scalar' else ROOT/'bridge_harness/libbridge_dds.so'
    cache=str(out/'cold-production.sqlite') if mode=='production_cache' else ''
    players={k:DDS(path=str(library),tt_kind=tt_kind,cache_path=cache) for k in ('candidate','reference','environment')}
    sums=Counter(); sizes={}; kinds={}; outputs=hashlib.sha256()
    try:
        for q in board['queries']:
            d=players[q['player']];before=d.cache_stats()
            c0=time.process_time();w0=time.perf_counter()
            if mode.endswith('_scalar'):
                solved=[d.solve(h,q['trump'],q['leader'],q['trick']) for h in q['worlds']]
            else:
                solved=d.solve_batch(q['worlds'],q['trump'],q['leader'],q['trick'],
                    fixed_seats=q['fixed_seats'],retain=mode!='batch_reset')
            wall=time.perf_counter()-w0;cpu=time.process_time()-c0
            after=d.cache_stats()
            row=Counter(cpu_seconds=cpu,wall_seconds=wall,requested=len(q['worlds']),
                queries=1,nodes=sum(n for _,n in solved),
                native_solves=after['native_solves']-before['native_solves'],
                cache_hits=after['hits']-before['hits'],
                duplicate_worlds=after['duplicate_worlds']-before['duplicate_worlds'])
            sums.update(row);sizes.setdefault(q['future_tricks'],Counter()).update(row)
            kinds.setdefault(q['kind'],Counter()).update(row)
            # Correctness and hashing are deliberately outside the timed DDS call.
            verify_outputs(q,solved)
            outputs.update(json.dumps([sorted(v.items()) for v,_ in solved],separators=(',',':')).encode())
    finally:
        for player in players.values():player.close()
    return dict(index=board['index'],mode=mode,**sums,by_remaining_tricks=sizes,by_kind=kinds,
        all_move_output_sha256=outputs.hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--upstream',type=Path,required=True);p.add_argument('--boards',type=int,default=10)
    p.add_argument('--seed',type=int,default=202611090310)
    p.add_argument('--tt-kind',type=int,choices=(1,2),default=2)
    p.add_argument('--modes',nargs='+',choices=MODES,default=list(MODES))
    p.add_argument('--capture-only',action='store_true')
    a=p.parse_args();a.run=a.run.resolve();a.out=a.out.resolve();a.upstream=a.upstream.resolve()
    a.out.mkdir(parents=True,exist_ok=True)
    trace=a.out/'trace.json.gz'
    captured=read(trace) if trace.exists() else capture(a.run,a.out,a.boards,a.seed)
    if a.capture_only:return
    if (a.out/'cold-production.sqlite').exists():
        raise ValueError('Benchmark cache already exists; use a fresh measurement directory')
    rows=[]
    for i,board in enumerate(captured):
        # Rotate order by board: no mode always benefits from running first/last.
        modes=a.modes[i%len(a.modes):]+a.modes[:i%len(a.modes)]
        canonical=None
        for mode in modes:
            row=measure(board,mode,a.upstream,a.out,a.tt_kind)
            if canonical is None:canonical=row['all_move_output_sha256']
            elif canonical!=row['all_move_output_sha256']:raise ValueError('DDS output mismatch across modes')
            rows.append(row);atomic_json(a.out/'measurements.json',rows)
            print(json.dumps({k:row[k] for k in ('index','mode','cpu_seconds','wall_seconds','native_solves','cache_hits','nodes')}),flush=True)
    totals={mode:dict(sum((Counter({k:r.get(k,0) for k in ('cpu_seconds','wall_seconds','native_solves','cache_hits','duplicate_worlds','nodes','queries','requested')})
        for r in rows if r['mode']==mode),Counter())) for mode in a.modes}
    result=dict(boards=len(captured),tt_kind=a.tt_kind,modes=totals,measurements=rows,selection=read(a.out/'selection.json'),
        upstream=read(a.out/'upstream-build.json'),production_library_sha256=sha(ROOT/'bridge_harness/libbridge_dds.so'),
        trace_sha256=sha(trace),all_worlds_all_legal_moves_equal=True,production_estimates_equal=True,
        production_cpu=sum(b['production_cpu'] for b in captured),
        notes=['DDS-call CPU time includes Python/ctypes packing and cache lookup/write; excludes belief sampling, neural selection, context construction and output verification.',
            'Cold cache at start; shares exact answers across paired tables/forks and sampled boards; never accesses or warms production cache.',
            'Random completed-board sample, fixed replayed trajectories and RNG-derived worlds, all saved fork tails included; copied prefixes excluded.',
            'One serial benchmark worker alongside live arena; CPU time is primary because wall time includes scheduling contention.',
            'One pass per mode over 10 boards, rotating mode order; small sample, not a full-run ETA prediction.'])
    atomic_json(a.out/'result.json',result)
    print(json.dumps(dict(boards=len(captured),modes=totals),indent=2))


if __name__=='__main__':main()
