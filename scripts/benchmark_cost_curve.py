#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Paired quality/cost curves with CPU timing, cluster intervals and resumable rows."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import json
import math
import multiprocessing as mp
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.players import GreedyPlayer, PIMCPlayer
from bridge_harness.rollout import AlphaMuPlayer, ContinuationPlayer, StrategyPlayer
from bridge_harness.runner import play_table, replay

VARIANTS = ('pimc8', 'alphamu8', 'pimc16', 'continuation2', 'plan8_tail2')
COMPARISONS = (('alphamu8','pimc8'), ('pimc16','pimc8'), ('plan8_tail2','continuation2'), ('plan8_tail2','pimc8'))


def make_variant(name):
    if name.startswith('pimc'):
        p = PIMCPlayer(int(name[4:]), 'tricks'); p.rng_stream = 'pimc'; return p
    if name == 'alphamu8':
        # Node/product limits are deterministic; no wall cutoff under CPU contention.
        return AlphaMuPlayer(8, 'tricks', seconds=None)
    if name == 'continuation2': return ContinuationPlayer('pimc', 2, 'tricks')
    if name == 'plan8_tail2': return StrategyPlayer(8, 'tricks', 1, 'pimc', 'greedy', 2)
    raise ValueError(name)


def worker(item):
    index, cohort, board = item
    common = GreedyPlayer()
    lead = common.choose(Game(board).observation(), random.Random(9)).card
    board = replace(board, opening_lead=lead)
    row = dict(id=board.id, cohort=cohort, family=board.family, variants={})
    order = VARIANTS[index % len(VARIANTS):] + VARIANTS[:index % len(VARIANTS)]
    for name in order:
        p = make_variant(name)
        try:
            assignment = [name if s % 2 == board.contract.declarer % 2 else 'greedy' for s in range(4)]
            table = play_table(board, assignment, {name:p, 'greedy':common}, seed=17041)
            if table['status'] != 'ok': raise RuntimeError(table.get('error'))
            replay(dict(board=board.to_dict(), tables=[table]))
            actions = [a for a in table['actions'] if a['player'] == name and not a.get('fixed_opening_lead')]
            events = Counter(a['alpha_mu_fallback'] for a in actions if 'alpha_mu_fallback' in a)
            events.update(a['strategy_action'] for a in actions if 'strategy_action' in a)
            row['variants'][name] = dict(tricks=table['declarer_tricks'],
                cpu_seconds=sum(a['cpu_seconds'] for a in actions),
                wall_seconds=sum(a['seconds'] for a in actions),
                dds_calls=sum(a.get('dds_calls',0) for a in actions), events=dict(events),
                cards=[a['card'] for a in table['actions']])
        finally:
            p.close()
    return row


def grade(gain, ratio):
    if ratio <= 1:
        return None  # dominance/tradeoff, never divide by a negative extra budget
    return gain / math.log2(ratio)


def interval(xs):
    if not xs: return None
    xs=sorted(xs)
    return [xs[round(.025*(len(xs)-1))],xs[round(.975*(len(xs)-1))]]


def summarize_rows(rows, replicates=2000):
    output={}
    for cohort in ('all','broad','related'):
        subset=sorted((r for r in rows if cohort=='all' or r['cohort']==cohort),key=lambda r:r['id'])
        if not subset: continue
        clusters=defaultdict(list)
        for r in subset:
            clusters[(r['cohort'],r['family'] or r['id'])].append(r)
        groups=list(clusters.values())
        comparisons=[]
        for candidate, baseline in COMPARISONS:
            # Pre-aggregate whole families; resample clusters, not related layouts.
            sums=[]
            strata=defaultdict(list)
            for g in groups:
                entry=(len(g),sum(r['variants'][candidate]['tricks']-r['variants'][baseline]['tricks'] for r in g),
                    sum(r['variants'][candidate]['cpu_seconds'] for r in g),
                    sum(r['variants'][baseline]['cpu_seconds'] for r in g))
                sums.append(entry)
                strata[g[0]['cohort']].append(entry)
            def calc(values):
                n=sum(v[0] for v in values); gain=sum(v[1] for v in values)/n
                ratio=sum(v[2] for v in values)/sum(v[3] for v in values)
                return gain,ratio,grade(gain,ratio)
            gain,ratio,gain_per_doubling=calc(sums)
            rng=random.Random(91845); boots=[]
            for _ in range(replicates):
                # Preserve the designed broad/related mix as well as each family.
                boots.append(calc([rng.choice(s) for s in strata.values() for _ in s]))
            rci=interval([x[1] for x in boots])
            grade_ci=interval([x[2] for x in boots if x[2] is not None]) if rci[0]>1 else None
            comparisons.append(dict(candidate=candidate,baseline=baseline,boards=len(subset),clusters=len(groups),
                tricks_per_board=gain,tricks_interval=interval([x[0] for x in boots]),
                cpu_ratio=ratio,cpu_ratio_interval=rci,time_doublings=math.log2(ratio),
                tricks_per_board_per_time_doubling=gain_per_doubling,grade_interval=grade_ci,
                cpu_candidate_per_board=sum(v[2] for v in sums)/len(subset),
                cpu_baseline_per_board=sum(v[3] for v in sums)/len(subset),
                wall_ratio=sum(r['variants'][candidate]['wall_seconds'] for r in subset)/sum(r['variants'][baseline]['wall_seconds'] for r in subset),
                grade_stable_denominator=rci[0]>1,
                wins=sum(r['variants'][candidate]['tricks']>r['variants'][baseline]['tricks'] for r in subset),
                losses=sum(r['variants'][candidate]['tricks']<r['variants'][baseline]['tricks'] for r in subset)))
        events={name:dict(sum((Counter(r['variants'][name]['events']) for r in subset),Counter())) for name in VARIANTS}
        output[cohort]=dict(comparisons=comparisons,events=events)
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=1000)
    parser.add_argument('--seed',type=int,default=860001)
    parser.add_argument('--family-size',type=int,default=10)
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--out',required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and not args.resume: raise ValueError('Output exists; use --resume')
    config=dict(count=args.count,seed=args.seed,family_size=args.family_size,variants=VARIANTS,
                cpu_metric='sum of tested declarer policy process CPU time',schema=1)
    confpath=dest.with_suffix('.config.json')
    if args.resume:
        if json.loads(confpath.read_text()) != json.loads(json.dumps(config)): raise ValueError('Resume config mismatch')
    else: confpath.write_text(json.dumps(config,indent=2)+'\n')
    rows=[json.loads(s) for s in dest.read_text().splitlines()] if dest.exists() else []
    done={r['id'] for r in rows}; items=[]
    broad=args.count//2
    for cohort,n,seed,fs in [('broad',broad,args.seed,1),('related',args.count-broad,args.seed+1,args.family_size)]:
        for b in generate(n,seed=seed,family_size=fs):
            b=replace(b,id=f'{cohort}-{b.id}',family=f'{cohort}-{b.family}' if b.family else None)
            if b.id not in done: items.append((len(items),cohort,b))
    started=time.perf_counter()
    with dest.open('a') as f, ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn')) as pool:
        pending={pool.submit(worker,item):item[2].id for item in items}
        for future in as_completed(pending):
            row=future.result()  # no silent exclusion of failed boards
            f.write(json.dumps(row,sort_keys=True)+'\n'); f.flush(); rows.append(row)
            if len(rows)%25==0: print(f'{len(rows)}/{args.count} boards; {time.perf_counter()-started:.1f}s',flush=True)
    result=summarize_rows(rows)
    dest.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': main()
