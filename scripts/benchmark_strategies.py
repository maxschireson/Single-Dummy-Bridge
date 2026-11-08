#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproducible small-ending and full-hand policy experiments; raw output stays out of Git."""
import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Contract, symbol
from bridge_harness.corpus import generate
from bridge_harness.dds import DDS
from bridge_harness.report import summarize
from bridge_harness.runner import run_pair, replay
from bridge_harness.strategy import AlphaMu, Position, evaluate_policy


def family(seed, cards, samples):
    rng = random.Random(seed)
    # Half of the families use two suits to enrich connected card combinations.
    deck = rng.sample(range(26 if seed % 2 else 52), 4 * cards)
    hands = [tuple(sorted(deck[s*cards:(s+1)*cards])) for s in range(4)]
    pool = hands[1] + hands[3]
    splits = list(combinations(pool, cards)); rng.shuffle(splits)
    worlds = []
    for split in splits[:samples]:
        h = list(hands); h[1] = tuple(sorted(split)); h[3] = tuple(sorted(set(pool)-set(split)))
        worlds.append(Position(tuple(h), 2, tricks=13-cards))
    return worlds


def endgames(count, cards, samples, seed, dest):
    rows, started = [], time.perf_counter()
    dds = DDS()
    try:
        with dest.open('w') as f:
            for i in range(count):
                worlds = family(seed+i, cards, samples)
                contract = Contract(6, 'NSHDC'[i % 5], 2)
                solver = AlphaMu(contract, 'tricks', dds=dds, seconds=30)
                pimc = solver.solve(worlds, max_plies=1)
                exact = solver.solve(worlds)
                c = pimc.best.policy.card
                constrained = solver.solve([p.play(c, contract.trump, 2) for p in worlds])
                observed = tuple(evaluate_policy(p, exact.best.policy, contract, solver.utility) for p in exact.worlds)
                if observed != exact.best.values:
                    raise AssertionError('Executable witness mismatch')
                row = dict(id=i, cards=cards, worlds=len(worlds), strain=contract.strain,
                           pimc=pimc.value, exact=exact.value, pimc_root_achievable=constrained.value,
                           fusion_gap=pimc.value-exact.value, root_regret=exact.value-constrained.value,
                           pimc_card=symbol(c), exact_card=symbol(exact.best.policy.card),
                           pimc_seconds=pimc.stats['seconds'], exact_seconds=exact.stats['seconds'],
                           nodes=exact.stats['nodes'], max_front=exact.stats['max_front'])
                if row['fusion_gap'] > 1e-8 or row['root_regret'] > 1e-8:
                    row['example'] = [dict(hands=[[symbol(c) for c in h] for h in p.hands],
                                           leader=p.leader, tricks=p.tricks) for p in worlds]
                f.write(json.dumps(row)+'\n'); f.flush(); rows.append(row)
                if (i+1) % 100 == 0:
                    print(f'endings {i+1}/{count}, elapsed {time.perf_counter()-started:.1f}s', flush=True)
    finally:
        dds.close()
    summary = dict(count=count, cards=cards, worlds=samples, seed=seed,
        fusion_cases=sum(r['fusion_gap']>1e-8 for r in rows),
        inferior_pimc_root_cases=sum(r['root_regret']>1e-8 for r in rows),
        mean_fusion_gap=statistics.mean(r['fusion_gap'] for r in rows),
        max_fusion_gap=max(r['fusion_gap'] for r in rows),
        mean_root_regret=statistics.mean(r['root_regret'] for r in rows),
        max_root_regret=max(r['root_regret'] for r in rows),
        mean_pimc_seconds=statistics.mean(r['pimc_seconds'] for r in rows),
        mean_exact_seconds=statistics.mean(r['exact_seconds'] for r in rows),
        max_front=max(r['max_front'] for r in rows), seconds=time.perf_counter()-started)
    dest.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)


def matches(count, samples, seed, dest, candidate, baseline, family_size, continuation, decisions, policy_samples):
    rows, counts = [], Counter()
    with dest.open('w') as f:
        for i, board in enumerate(generate(count, seed=seed, family_size=family_size)):
            row = run_pair(board, dict(candidate=candidate, baseline=baseline, common='greedy',
                                      samples=samples, objective='tricks', mode='declarer', seed=4041,
                                      strategy_continuation=continuation, strategy_decisions=decisions, strategy_policy_samples=policy_samples))
            if row['status'] != 'ok':
                raise RuntimeError(row)
            replay(row)
            for a in row['tables'][0]['actions']:
                if 'alpha_mu_fallback' in a: counts[a['alpha_mu_fallback']] += 1
                if 'strategy_action' in a: counts[a['strategy_action']] += 1
            f.write(json.dumps(row)+'\n'); f.flush(); rows.append(row)
            if (i+1) % 10 == 0: print(f'matches {i+1}/{count}', flush=True)
    summary = summarize(rows)
    summary['strategy_events'] = dict(counts)
    summary['mean_trick_difference'] = statistics.mean(r['tables'][0]['declarer_tricks']-r['tables'][1]['declarer_tricks'] for r in rows)
    summary['candidate_mean_seconds'] = statistics.mean(r['tables'][0]['seconds'] for r in rows)
    summary['baseline_mean_seconds'] = statistics.mean(r['tables'][1]['seconds'] for r in rows)
    dest.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k in ('completed_pairs','mean_imps','cluster_bootstrap_95_interval','mean_trick_difference','candidate_mean_seconds','baseline_mean_seconds','strategy_events')}, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('endings','matches'))
    p.add_argument('--count', type=int, default=1000)
    p.add_argument('--cards', type=int, default=3)
    p.add_argument('--samples', type=int, default=8)
    p.add_argument('--seed', type=int, default=620001)
    p.add_argument('--candidate', default='strategy')
    p.add_argument('--baseline', default='pimc')
    p.add_argument('--family-size', type=int, default=1)
    p.add_argument('--continuation', choices=('greedy','pimc'), default='greedy')
    p.add_argument('--decisions', type=int, default=2)
    p.add_argument('--policy-samples', type=int, default=2)
    p.add_argument('--out', required=True)
    a = p.parse_args(); dest=Path(a.out); dest.parent.mkdir(parents=True,exist_ok=True)
    if a.mode == 'endings': endgames(a.count,a.cards,a.samples,a.seed,dest)
    else: matches(a.count,a.samples,a.seed,dest,a.candidate,a.baseline,a.family_size,a.continuation,a.decisions,a.policy_samples)

if __name__ == '__main__': main()
