#!/usr/bin/env python3
"""How reliable is one inside-rollout pair? (H05's small reliability run, #37; Max, 21:38 UTC on 14 November: "please keep this
thread moving one way or the other".)

  SURE_BIN=... python training/rollout-loop-20261113/bench/pair_reliability.py RUN_DIR --source CAPSULE/recovery \\
      [--pairs 3000] [--layouts 128] [--workers 4] [--seed 5] [--out rows.jsonl]

A recorded pair (x8_rollout.Fork, in a rollout decision's `forks`) is one imagined layout: at a later turn of one rollout the
simulated seat's card and a forced other card were each played out to the end by the net, once. Its label is the sign and
size of (tricks after the chosen card - tricks after the other), for the side to play there. This bench rebuilds the fork
seat's own view (x8_capture.fork_view), draws fresh layouts from THAT seat's information (the bot's own layout reader, as it
draws for its own decisions), plays both cards out on every layout with the same net and seat settings (no claims inside, as
the recorded pairs have none), and compares:

  single   the recorded pair's difference (one layout, one playout each), for the side to play at the fork
  panel    the mean difference over the fresh layouts, with its standard error

By the trick of the fork and the side to play: how often the single pair has the panel's sign, the correlation, the slope of
panel on single, the share of pairs whose single difference is 0, and the reliability of the single label (the share of its
variance that is the panel's signal: var(panel) less the panel's noise, over var(single)). Pairs are drawn at random from the
records, at most --per-record of each, from the candidate's decisions. Read-only.
"""
import argparse
from collections import defaultdict
from dataclasses import replace
import glob
import gzip
import json
import math
from multiprocessing import Pool
from pathlib import Path
import random
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bridge_harness import x8_capture, x8_player       # noqa: E402
from bridge_harness.core import Board, Game, card      # noqa: E402

STATE = {}


def start(run, source, role, layouts):
    m = json.loads((Path(run) / 'manifest.json').read_text())
    a, b = m['roster'][:2]
    me, other = (a, b) if role == 'candidate' else (b, a)
    p = x8_player.X8Player(m['bots'][me], source, None)
    p.meet(other)
    p.reference = None
    stage = next(s for s in p.x8.stages if s.mode == 'rollout')
    STATE.update(player=p, stage=replace(stage, race=0., layouts=layouts),
                 claims_off=replace(p.x8, claims=replace(p.x8.claims, leaf=0)), role=role)


def jobs(files, n, per_record, role, seed):
    """[(file, table key, table index, action index, fork index)] drawn at random."""
    rng = random.Random(seed)
    out = []
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        mine = []
        for key, e in d['unique_tables'].items():
            for ti, t in enumerate(e.get('tables') or ()):
                if t.get('depth', 0) or t.get('fork_kind'):
                    continue
                for ai, a in enumerate(t['actions']):
                    note = a.get('x8') or {}
                    if (a.get('player') or a.get('role')) == role and note.get('mode') == 'rollout':
                        mine += [(f, key, ti, ai, k) for k in range(len(note.get('forks') or ()))]
        rng.shuffle(mine)
        out += mine[:per_record]
    rng.shuffle(out)
    return out[:n]


def one(job):
    f, key, ti, ai, k = job
    p, stage = STATE['player'], STATE['stage']
    started = time.process_time()
    d = json.load(gzip.open(f, 'rt'))
    e = d['unique_tables'][key]
    board, table = Board.from_dict(e['board']), e['tables'][ti]
    g = Game(board)
    for a in table['actions'][:ai]:
        g.play(card(a['card']))
    o = g.observation()
    row = table['actions'][ai]['x8']['forks'][k]
    try:
        fo, main, other, t_main, t_other, p_main, p_other = x8_capture.fork_view(o, row)
    except Exception as ex:
        return dict(skip=f'fork_view: {ex}'[:120])
    declaring = fo.controller % 2 == fo.contract.declarer % 2
    sign = 1 if declaring else -1
    single = sign * (int(t_main) - int(t_other))
    saved = p.x8
    p.x8 = STATE['claims_off']
    try:
        view = x8_player.View(fo)
        source = p.source(fo, view)
        nrng = np.random.default_rng(zlib.crc32(f'{f}|{key}|{ti}|{ai}|{k}'.encode()))
        drawn = p.read_layouts(fo, view, source, nrng, stage.layouts)
        if drawn is None:
            return dict(skip='no layouts for this view')
        worlds, w, _ = drawn
        w = np.asarray(w, float); w = w / w.sum()
        got = p.roll(fo, worlds, w, [main, other], stage, nrng, np.zeros((len(worlds), 2), bool), race=False)
    except Exception as ex:
        return dict(skip=f'rollout: {type(ex).__name__}: {ex}'[:160])
    finally:
        p.x8 = saved
    t = got['tricks'].astype(np.int64)
    ok = (t >= 0).all(axis=1)
    if ok.sum() < 1:
        return dict(skip=f'no layout played (drawn {len(worlds)})')
    u = x8_player.worth(t[ok], fo, 'tricks')            # the side to play's tricks, each card
    ww = w[ok] / w[ok].sum()
    diff = u[:, 0] - u[:, 1]
    panel = float(ww @ diff)
    n = int(ok.sum())
    se = float(math.sqrt(max((ww ** 2 * (diff - panel) ** 2).sum() * n / max(n - 1, 1), 0.)))
    return dict(file=Path(f).name, trick=len(fo.history) // 4 + 1, root_trick=len(o.history) // 4 + 1, declaring=declaring,
                single=single, panel=round(panel, 4), se=round(se, 4), layouts=n, drawn=len(worlds), unplayed=int((~ok).sum()), p_main=p_main, p_other=p_other,
                main_tricks=int(t_main), other_tricks=int(t_other), cpu=round(time.process_time() - started, 3))


def report(rows):
    rows = [r for r in rows if 'single' in r]
    few = np.mean([r['layouts'] < 32 for r in rows])
    print(f'pairs with under 32 distinct layouts drawn (late in the hand; the panel there is close to every layout the seat allows): {few:.2f}')
    print(f'{len(rows)} pairs re-evaluated; CPU a pair {np.mean([r["cpu"] for r in rows]):.2f} s; layouts a pair {np.mean([r["layouts"] for r in rows]):.0f}')
    print('single = the recorded pair (one layout); panel = mean over fresh layouts from the fork seat\'s own information; for the side to play')
    print(f'{"":22s} {"pairs":>6s} {"single=0":>8s} {"same sign":>9s} {"corr":>6s} {"slope":>6s} {"reliab.":>7s} | {"mean single":>11s} {"mean panel":>10s} {"panel SE":>8s} | {"|panel|>2SE":>11s}')
    def line(name, sel):
        if len(sel) < 30:
            return
        s = np.array([r['single'] for r in sel], float); q = np.array([r['panel'] for r in sel]); se = np.array([r['se'] for r in sel])
        nz = s != 0
        same = float(np.mean(np.sign(s[nz]) == np.sign(q[nz]))) if nz.any() else float('nan')
        corr = float(np.corrcoef(s, q)[0, 1]) if s.std() > 0 and q.std() > 0 else float('nan')
        slope = float(np.polyfit(s, q, 1)[0]) if s.std() > 0 else float('nan')
        signal = max(q.var() - float(np.mean(se ** 2)), 0.)
        rel = signal / s.var() if s.var() > 0 else float('nan')
        sharp = float(np.mean(np.abs(q) > 2 * se))
        print(f'{name:22s} {len(sel):6d} {1 - nz.mean():8.2f} {same:9.2f} {corr:6.2f} {slope:6.2f} {rel:7.3f} | {s.mean():+11.3f} {q.mean():+10.3f} {se.mean():8.3f} | {sharp:11.2f}')
    line('all', rows)
    for side in (True, False):
        line('declaring side' if side else 'defending side', [r for r in rows if r['declaring'] == side])
    for lo, hi in ((1, 2), (3, 4), (5, 6), (7, 8), (9, 13)):
        line(f'fork at tricks {lo}-{hi}', [r for r in rows if lo <= r['trick'] <= hi])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('--source', default='')
    ap.add_argument('--bot', default='candidate')
    ap.add_argument('--pairs', type=int, default=3000)
    ap.add_argument('--per-record', type=int, default=3)
    ap.add_argument('--layouts', type=int, default=128)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--seed', type=int, default=5)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--report', type=Path, nargs='+')
    a = ap.parse_args()
    if a.report:
        report([json.loads(l) for f in a.report for l in open(f) if l.strip()])
        return
    files = sorted(glob.glob(str(a.run / 'episodes' / '*.json.gz')))
    random.Random(a.seed).shuffle(files)
    todo = jobs(files[:max(1, a.pairs // a.per_record * 2)], a.pairs, a.per_record, a.bot, a.seed)
    print(f'{len(todo)} pairs drawn from {a.run.name}', flush=True)
    rows, skips = [], defaultdict(int)
    out = open(a.out, 'a') if a.out else None
    with Pool(a.workers, initializer=start, initargs=(str(a.run), a.source, a.bot, a.layouts)) as pool:
        for r in pool.imap_unordered(one, todo, chunksize=4):
            if 'skip' in r:
                skips[r['skip'][:60]] += 1
                continue
            rows.append(r)
            if out:
                out.write(json.dumps(r) + '\n'); out.flush()
    if skips:
        print('skipped:', dict(skips))
    report(rows)


if __name__ == '__main__':
    main()
