#!/usr/bin/env python3
"""How much do more rollouts help pure Stu's play, and what do they cost? (Max, 22:31 UTC on 13 November: "do a sweep to
see how much more rollouts help ... what run-time strength levers we have".) Real rollout decisions of pure Stu's
collection are played again by the same bot with other rollout budgets, and each card chosen is scored against a large
reference rollout of every legal card from the same position:

  python training/rollout-loop-20261113/bench/budget.py EPISODES_DIR --decisions 400 --workers 8 [--out rows.jsonl]

Budgets (layouts, first, cards): the bot's own (128, 32, 4) and others below and above it. The reference: every legal
card (runs of touching cards as one) on --reference layouts, no race. A decision's regret is the reference's best value
minus the reference value of the chosen card's run, in the deciding side's tricks; its CPU is the process time of the
whole decision (layouts, claims test, rollouts). The reference rates by the same rollouts (the net's play from each
seat's view), so this measures how far each budget is from what unlimited rollouts of this kind would choose: the noise
part of the budget's cost, not whether the rollouts' own values are right. Opening leads, forced cards and claims are
left out. Prints, for each budget, mean regret and its standard error, how often it chose the reference's best, and
mean CPU, overall and by phase.
"""
import argparse, gzip, json, random, sys, time, zlib
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card, symbol  # noqa: E402
import x8_match  # noqa: E402

BUDGETS = [(32, 16, 4), (64, 32, 4), (128, 32, 4), (256, 32, 4), (512, 32, 4), (128, 32, 6), (256, 32, 6), (128, 128, 4)]
BOT = None


def start(source, pair, reference):
    global BOT, REF
    m = x8_match.build_manifest(Path(source), ROOT / 'configs/loop-bots.json', pair, 9001)
    a, b = pair.split('~')
    BOT = x8_match.player(m['bots'][a], source)
    BOT.meet(b)
    REF = reference


def value_of(note, x):
    for j, run in enumerate(note['runs']):
        if symbol(x) in run:
            return note['value'][j]
    return None


def one(task):
    path, table, ply = task
    d = json.load(gzip.open(path, 'rt'))
    e = list(d['unique_tables'].values())[table]
    board = Board.from_dict(e['board'])
    game = Game(board)
    for act in e['tables'][0]['actions'][:ply]:
        game.play(card(act['card']))
    o = game.observation()
    base = BOT.x8.stages[0]
    seed = zlib.crc32(f'{Path(path).name}:{table}:{ply}'.encode())
    out = dict(file=Path(path).name, table=table, ply=ply, trick=ply // 4 + 1, legal=len(o.legal))
    # the reference: every legal card, many layouts, no race
    first_try = BOT.choose(o, random.Random(seed))          # as in play; it also sets the claim state the reference uses
    if (first_try.details.get('x8') or {}).get('mode') != 'rollout':
        return None
    ref_stage = replace(base, layouts=REF, first=REF, cards=52, prior=0., race=0.)
    t = time.process_time()
    ref = BOT.rollout_decision(o, random.Random(seed + 1), ref_stage)
    out['ref_cpu'] = time.process_time() - t
    note = ref.details['x8']
    if len(note['runs']) < 2:
        return None
    best = max(note['value'])
    out['ref_spread'] = best - min(note['value'])
    for lay, first, cards in BUDGETS:
        BOT.x8 = replace(BOT.x8, stages=(replace(base, layouts=lay, first=first, cards=cards),))
        t = time.process_time()
        got = BOT.choose(o, random.Random(seed + 2))
        cpu = time.process_time() - t
        BOT.x8 = replace(BOT.x8, stages=(base,))
        v = value_of(note, got.card)
        out[f'{lay}/{first}/{cards}'] = dict(card=symbol(got.card), regret=None if v is None else best - v, cpu=cpu)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('--decisions', type=int, default=400)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--reference', type=int, default=1024)
    p.add_argument('--pair', default='stu0-pa~stu0-pb')
    p.add_argument('--source', type=Path, default=Path.home() / 'work/loop/capsule/recovery')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    rng = random.Random(5)
    tasks = []
    for f in sorted(a.episodes.glob('*.json.gz')):
        d = json.load(gzip.open(f, 'rt'))
        for ti, e in enumerate(d['unique_tables'].values()):
            if not e.get('tables'):
                continue
            plies = [i for i, act in enumerate(e['tables'][0]['actions']) if i > 0 and (act.get('x8') or {}).get('mode') == 'rollout'
                     and len((act.get('x8') or {}).get('cards') or ()) >= 2]
            if plies:
                tasks.append((str(f), ti, rng.choice(plies)))
        if len(tasks) >= a.decisions:
            break
    print(f'{len(tasks)} decisions, one a table; reference {a.reference} layouts, every legal card', flush=True)
    rows = []
    with Pool(a.workers, initializer=start, initargs=(str(a.source), a.pair, a.reference)) as pool:
        for r in pool.imap_unordered(one, tasks):
            if r is not None:
                rows.append(r)
                if a.out:
                    with a.out.open('a') as f:
                        f.write(json.dumps(r) + '\n')
    print(f'{len(rows)} scored (reference spread of values: mean {np.mean([r["ref_spread"] for r in rows]):.3f} tricks; '
          f'reference CPU {np.mean([r["ref_cpu"] for r in rows]):.2f} s a decision)')
    phases = (('all', 1, 13), ('tricks 1-4', 1, 4), ('tricks 5-8', 5, 8), ('tricks 9-13', 9, 13))
    print('budget (layouts/first/cards) | ' + ' | '.join(f'{name}: regret +- se, best, cpu' for name, _, _ in phases))
    for lay, first, cards in BUDGETS:
        key, cells = f'{lay}/{first}/{cards}', []
        for name, lo, hi in phases:
            got = [r[key] for r in rows if lo <= r['trick'] <= hi and r[key]['regret'] is not None]
            if not got:
                cells.append('-'); continue
            reg = np.array([g['regret'] for g in got])
            cells.append(f'{reg.mean():.4f} +- {reg.std(ddof=1) / np.sqrt(len(reg)):.4f}, {np.mean(reg <= 1e-9):.2f}, '
                         f'{np.mean([g["cpu"] for g in got]):.2f}s (n={len(reg)})')
        print(f'{key:>12} | ' + ' | '.join(cells))


if __name__ == '__main__':
    main()
