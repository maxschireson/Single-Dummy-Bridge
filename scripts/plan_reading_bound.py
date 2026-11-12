#!/usr/bin/env python3
"""How much the hidden seats' plays say about their hands when the reader's model of them is the bot itself.

  python scripts/plan_reading_bound.py --episodes DIR --net gen7_policy.npz [--trick 6] [--candidates 48]
        [--seeds 2] [--files 200] [--workers 8] [--out rows.json]

Gen 7 and the Gen 8 prototype weigh layouts by the policy net's probability of every card a hidden hand has played.
The net is a model of the house bots; this bench replaces it by the house bot. One sample is one seat of one played
table (Gen 6 self-play) at its first decision of --trick. Candidate layouts are drawn from Gen 6's own beliefs there,
and the true layout is added. For every candidate and every earlier card chosen by a hidden hand (the opening lead
left out), Gen 6 is run --seeds times from the view that hand would have had in that candidate: did it play the card
that was played, and how far behind its best card did it rate that card. The net's log-probability of the same plays
in the same candidates is stored beside it. scripts/plan_reading_report.py turns the rows into nats.

A diagnostic: the true layout is among the candidates as a label, and nothing here is a player.
"""
import argparse
import gzip
import json
from multiprocessing import Pool
import os
from pathlib import Path
import random
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import SEATS, Board, Game, card, symbol
from bridge_harness.gen6 import Classes, View
from bridge_harness.gen7 import hidden_plays, past_view, player
import gen7_check as check

STATE = {}
PRUNE = 9.          # a candidate this many nats behind the best (by the crude count) is not simulated further
MISS, HIT = np.log(.05), np.log(.9)


def start(net, trick, candidates, seeds, seed):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    STATE.update(six=player(check.spec('gen6'), ROOT), seven=player(check.spec('gen7', policy=net), ROOT), trick=trick,
                 candidates=candidates, seeds=seeds, seed=seed)


def assignment(view, world):
    """Index of the hidden seat holding each unseen card."""
    where = {c: j for j, s in enumerate(view.hidden) for c in world[s]}
    return np.array([where[c] for c in view.unseen], np.int8)


def sample_of(path):
    six, seven = STATE['six'], STATE['seven']
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    out = []
    for key, e in d['unique_tables'].items():
        if 'tables' not in e or not e['tables'][0].get('actions') or e['tables'][0].get('status', 'ok') != 'ok':
            continue
        board = Board.from_dict(e['board'])
        actions = e['tables'][0]['actions']
        first = 4 * (STATE['trick'] - 1)
        if len(actions) < first + 4:
            continue
        done = set()
        game = Game(board)
        for x in actions[:first]:
            game.play(card(x['card']))
        for x in actions[first:first + 4]:
            o = game.observation()
            if o.controller not in done and len(o.legal) > 1:
                done.add(o.controller)
                started = time.time()
                row = one(d['family'], key, board, o)
                if row:
                    row['seconds'] = round(time.time() - started, 1)
                    out.append(row)
            game.play(card(x['card']))
    return out


def one(family, key, board, o):
    six, seven = STATE['six'], STATE['seven']
    view = View(o)
    if len(view.hidden) != 2:
        return None
    rng = np.random.default_rng([STATE['seed'], o.controller, int(family[:8], 16)])
    plays = hidden_plays(o, False)
    source = six.source(o, view)
    classes = Classes(view)
    logw = classes.logmult + six.type_log_weights(o, view, classes.length, classes.hon, 'scorer' if source == 'list' else source)
    p = np.exp(logw - logw.max())
    worlds = classes.worlds(rng.choice(len(p), STATE['candidates'] * 2, p=p / p.sum()), rng)
    truth = assignment(view, [tuple(c for c in board.hands[s] if c in set(view.unseen)) if s in view.hidden else () for s in range(4)])
    rows, seen = [truth], {truth.tobytes()}
    for w in worlds:
        a = assignment(view, w)
        if a.tobytes() not in seen and len(rows) <= STATE['candidates']:
            seen.add(a.tobytes())
            rows.append(a)
    assign = np.array(rows)
    net_logp, options = seven.play_log_probabilities(o, view, assign, plays)       # [plays, candidates]
    n, m = len(assign), STATE['seeds']
    same = np.full((len(plays), n, m), -1, np.int8)                                  # -1 = not simulated (pruned)
    gap = np.full((len(plays), n, m), np.nan, np.float32)
    eligible = np.zeros((len(plays), n, m), np.int8)
    crude = np.zeros(n)
    calls = 0
    for row, (i, seat, chooser) in enumerate(plays):
        played = o.history[i][1]
        j = view.hidden.index(chooser)
        later = {x for s, x in o.history[i:] if s == chooser}
        alive = crude >= crude.max() - PRUNE
        alive[0] = True
        for k in np.flatnonzero(alive):
            if options[row, k] <= 1:
                same[row, k] = 1
                gap[row, k] = 0.
                continue
            hand = {int(c) for c, h in zip(view.unseen, assign[k]) if h == j} | {int(c) for c in later}
            then = past_view(o, i, hand)
            for s in range(m):
                r = random.Random(f"{STATE['seed']}/{family}/{o.controller}/{i}/{k}/{s}")
                dec = six.choose(then, r)
                calls += 1
                est = dec.details.get('estimates') or {}
                same[row, k, s] = dec.card == played
                gap[row, k, s] = est[symbol(played)]['gap_to_best'] if symbol(played) in est else np.nan
                eligible[row, k, s] = sum(v > 0 for v in (dec.details.get('proposal_probabilities') or dec.details.get('behavior_probabilities') or {}).values())
            crude[k] += np.mean(np.where(same[row, k] == 1, HIT, MISS))
    c = o.contract
    return dict(family=family, table=key, viewer=SEATS[o.controller], declaring=o.controller % 2 == c.declarer % 2, trick=STATE['trick'],
                plays=[dict(i=i, trick=i // 4 + 1, seat=SEATS[seat], chooser=SEATS[chooser], card=symbol(o.history[i][1]),
                            partner=chooser % 2 == o.controller % 2) for i, seat, chooser in plays],
                unseen=[symbol(x) for x in view.unseen], hidden=[SEATS[s] for s in view.hidden],
                assign=assign.tolist(), net_logp=np.round(net_logp, 4).tolist(), options=options.tolist(),
                same=same.tolist(), gap=np.where(np.isnan(gap), -1., np.round(gap, 4)).tolist(), eligible=eligible.tolist(), calls=calls)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--episodes', required=True)
    p.add_argument('--net', required=True)
    p.add_argument('--trick', type=int, default=6)
    p.add_argument('--candidates', type=int, default=48)
    p.add_argument('--seeds', type=int, default=2)
    p.add_argument('--files', type=int, default=200)
    p.add_argument('--skip-files', type=int, default=0)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', type=Path, default=Path('reading_bound.json'))
    a = p.parse_args()
    src = Path(a.episodes)
    files = sorted(src.glob('*.json.gz')) if src.is_dir() else [Path(x) for x in src.read_text().split()]
    files = files[a.skip_files:a.skip_files + a.files]
    rows, started, done = [], time.time(), 0

    def save():
        part = a.out.with_suffix('.part')
        part.write_text(json.dumps(dict(settings=dict(net=a.net, trick=a.trick, candidates=a.candidates, seeds=a.seeds, files=done,
                                                      skip_files=a.skip_files, seed=a.seed, seconds=round(time.time() - started)), rows=rows)))
        part.replace(a.out)

    with Pool(a.workers, initializer=start, initargs=(str(Path(a.net).resolve()), a.trick, a.candidates, a.seeds, a.seed)) as pool:
        for part in pool.imap_unordered(sample_of, files):
            rows += part
            done += 1
            if done % 10 == 0:
                save()
                print(f'{done} files, {len(rows)} samples, {sum(r["calls"] for r in rows)} bot decisions, {round(time.time() - started)} s', flush=True)
    save()
    print(json.dumps(dict(samples=len(rows), files=done, seconds=round(time.time() - started))))


if __name__ == '__main__':
    sys.exit(main())
