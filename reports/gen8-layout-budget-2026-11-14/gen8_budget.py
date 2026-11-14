#!/usr/bin/env python3
"""How much do more or fewer early layouts change Gen 8's card play, and what do they cost? (Max, 14 November 2026.)

Real decisions from Gen 8 self-play records (scripts/gen8_match.py --episodes, pair g8a~g8b) are played again by the same
bot with other early-layout budgets, and each card chosen is scored against a large reference of every legal card from
the same position, drawn from Gen 8's own posterior and solved double dummy:

  python gen8_budget.py --root REPO --source CAPSULE/recovery EPISODES_DIR --workers 2 --out rows.jsonl

Only tricks 1 to 6 after the opening lead are replayed: that is where Gen 8 solves `samples` layouts (32) drawn from a
pool of `early_pool` (512) hand-fit-scorer layouts weighted by the net's reading of the play; from trick 7 it lists
every compatible layout (up to 256 solved), and the budget does not apply. Each table gives up to one decision in each
of tricks 1-2, 3-4 and 5-6 (non-forced; the opening lead is left out).

Budgets are (samples, early_pool); the bot's own is (32, 512). The reference: samples 1024 from a pool of 8192, every
legal card solved in every layout, weighted as Gen 8 weights them. A decision's regret is the reference's best mean
minus the reference mean of the chosen card, in the deciding side's tricks. The reference uses Gen 8's own posterior,
so this measures the sampling-noise part of the budget's cost, not whether the posterior or double dummy are right.
The tree (tricks 3-6) and the net's tie-break run as in play at every budget. Also kept: each budget's error in its
per-card gap estimates against the reference's gaps (what a gap head learns from), and CPU (process time) a decision.
"""
import argparse, gzip, json, random, sys, time, zlib
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

BUDGETS = [(16, 512), (32, 512), (64, 512), (128, 512), (128, 2048), (256, 512), (256, 2048)]
REFERENCE = (1024, 8192)
WINDOWS = ((1, 2), (3, 4), (5, 6))
BOT = None
G = {}


def start(root, source, pair):
    global BOT
    sys.path.insert(0, str(root)); sys.path.insert(0, str(Path(root) / 'scripts'))
    import gen8_match
    from bridge_harness import core, gen6, gen7
    G.update(core=core, gen6=gen6)
    m = gen8_match.build_manifest(Path(source), Path(root) / 'configs/loop-bots.json', pair, 9001)
    a, b = pair.split('~')
    BOT = gen7.player(m['bots'][a], source)
    BOT.meet(b)


def set_budget(samples, pool):
    BOT.samples = samples
    BOT.g7 = replace(BOT.g7, early_pool=pool)


def values(o, solved, weights):
    """Weighted mean tricks for the deciding side, by legal card (as Gen6Player.search_decision computes them)."""
    declaring = o.actor % 2 == o.contract.declarer % 2
    remaining = 13 - len(o.history) // 4
    w = np.asarray(weights, float)
    w = w / w.sum()
    out = {c: 0. for c in o.legal}
    for (vals, _), share in zip(solved, w):
        for c, t in vals.items():
            total = o.declarer_tricks + (t if declaring else remaining - t)
            out[c] += share * (total if declaring else 13 - total)
    return out


def one(task):
    path, ti, ply = task
    core, gen6 = G['core'], G['gen6']
    d = json.load(gzip.open(path, 'rt'))
    e = list(d['unique_tables'].values())[ti]
    game = core.Game(core.Board.from_dict(e['board']))
    for act in e['tables'][0]['actions'][:ply]:
        game.play(core.card(act['card']))
    o = game.observation()
    if len(o.legal) < 2:
        return None
    view = gen6.View(o)
    source = BOT.source(o, view)
    if source not in ('scorer', 'lead_net'):
        return None
    seed = zlib.crc32(f'{Path(path).name}:{ti}:{ply}'.encode())
    own = (BOT.samples, BOT.g7.early_pool)
    fixed = [s for s, h in enumerate(o.known_hands) if h is not None]
    set_budget(*REFERENCE)
    t = time.process_time()
    worlds, weights, info = BOT.layouts(o, view, source, np.random.default_rng(seed))
    solved = BOT.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick, fixed_seats=fixed)
    ref = values(o, solved, weights)
    ref_cpu = time.process_time() - t
    set_budget(*own)
    best = max(ref.values())
    out = dict(file=Path(path).name, table=ti, ply=ply, trick=ply // 4 + 1, legal=len(o.legal), ref_cpu=ref_cpu,
               ref_layouts=len(worlds), ref_effective=info.get('effective_with_play'), ref_spread=best - min(ref.values()),
               ref_distinct=len({round(v, 6) for v in ref.values()}))
    order = list(BUDGETS)
    random.Random(seed).shuffle(order)      # no budget always pays the first call's warm-up
    for samples, pool in order:
        set_budget(samples, pool)
        t = time.process_time()
        got = BOT.choose(o, random.Random(seed + 2))
        cpu = time.process_time() - t
        set_budget(*own)
        est = got.details.get('estimates') or {}
        gap_err = [abs(est[core.symbol(c)]['gap_to_best'] - (best - v)) for c, v in ref.items() if core.symbol(c) in est]
        tree = (got.details.get('gen7_tree') or {})
        out[f'{samples}/{pool}'] = dict(card=core.symbol(got.card), regret=best - ref[got.card], cpu=cpu,
                                        gap_mae=float(np.mean(gap_err)) if gap_err else None,
                                        unique=got.details.get('unique_worlds'), tree=bool(tree), moved=bool(tree.get('moved')))
    return out


def tasks_from(episodes, per_table_windows, seed=5):
    rng = random.Random(seed)
    tasks, counts = [], []
    for f in sorted(Path(episodes).glob('*.json.gz')):
        d = json.load(gzip.open(f, 'rt'))
        for ti, e in enumerate(d['unique_tables'].values()):
            if not e.get('tables'):
                continue
            acts = e['tables'][0]['actions']
            by = {w: [] for w in WINDOWS}
            for i, a in enumerate(acts):
                trick = i // 4 + 1
                legal = len(a.get('behavior_probabilities') or {}) or None
                if i == 0 or trick > 6 or not legal or legal < 2:
                    continue
                for w in WINDOWS:
                    if w[0] <= trick <= w[1]:
                        by[w].append(i)
            counts.append({f'{w[0]}-{w[1]}': len(by[w]) for w in WINDOWS})
            for w in WINDOWS[:per_table_windows]:
                if by[w]:
                    tasks.append((str(f), ti, rng.choice(by[w])))
    return tasks, counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--pair', default='g8a~g8b')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    tasks, counts = tasks_from(a.episodes, len(WINDOWS))
    done = set()
    if a.out.exists():
        for line in a.out.read_text().splitlines():
            r = json.loads(line)
            done.add((r['file'], r['table'], r['ply']))
    tasks = [t for t in tasks if (Path(t[0]).name, t[1], t[2]) not in done]
    if a.limit:
        tasks = tasks[:a.limit]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    (a.out.parent / "decisions_per_table.json").write_text(json.dumps(counts))
    print(f'{len(tasks)} decisions to score ({len(done)} already); {len(counts)} tables', flush=True)
    t0 = time.time()
    with Pool(a.workers, initializer=start, initargs=(str(a.root), str(a.source), a.pair)) as pool:
        for k, r in enumerate(pool.imap_unordered(one, tasks), 1):
            if r is not None:
                with a.out.open('a') as f:
                    f.write(json.dumps(r) + '\n')
            if k % 20 == 0:
                print(f'{k} of {len(tasks)} in {time.time() - t0:.0f} s', flush=True)


if __name__ == '__main__':
    main()
