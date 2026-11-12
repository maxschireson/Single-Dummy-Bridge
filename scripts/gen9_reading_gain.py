#!/usr/bin/env python3
"""E9-4 part 1: what reading a declared carding scheme is worth, on recorded boards with relabelled spots.

Gen 9 work in progress (sam, signals). Prediction evidence; no new matches are played.

1. Relabel. Each recorded main table is replayed. At every defender decision whose recorded tie set
   (`proposal_probabilities`, else `behavior_probabilities`) holds two or more cards of the class of
   the recorded card, the card is drawn again from the carding bot's rule (signals.SignalModel with
   the cell's scheme and honesty, the defender's true hand), and the two cards' order of play is
   swapped for the rest of the board. A swap that changes the winner of any trick is undone (the
   latest swap touching the first trick that changed, repeatedly). The defenders' spot play is then
   the carding bot's, on real deals and real house-bot play; nobody reacts to the signals.
2. Score. At declarer's decisions after the opening lead and before `--until`, with two hidden hands,
   a pool of layouts is drawn as Gen7Player.early_layouts draws it (the deal list's layouts later), the
   true layout is added, and the defenders' plays so far are scored under each reader. The gain is

       fit(true layout) - log mean over the pool of exp(fit(layout))

   in nats: how far the reading moves weight toward the truth, against auction-only weights.

Readers, each at a factor phi of 0.3 (Gen 8's unknown opponent) and 1 (the house net in full): `net<phi>`
(the net on the card: Gen 8), `class<phi>` (the class term alone: spots ignored), and `sig<phi>-h<h>`
(class plus the signal term for the cell's scheme, the reader assuming honesty h: the bot's true
value, or 0, .5, .8, .9). `sig-h0` knows which spots the scheme plays but not what they mean, so
sig-h(x) minus sig-h0 is what the facts are worth.

  python scripts/gen9_reading_gain.py EPISODES --source CAPSULE/recovery --bot 7s-32 --out rows.jsonl \\
      --cells std-100,std-80,std-50,std-0,ud-100,ud-80,ud-50,std35-80 --tables 300
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import glob
import gzip
import json
from pathlib import Path
import random
import sys
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import Classes, View, spaced  # noqa: E402
from bridge_harness.gen7 import hidden_plays  # noqa: E402
from bridge_harness.gen9_play import Gen9Player  # noqa: E402
from bridge_harness.signal_experience import card_stats  # noqa: E402
from bridge_harness.signals import SPOT, SignalModel, situation  # noqa: E402

STD = dict(length_lead_vs_suit='4th', length_lead_vs_nt='4th', lead_from_ak='ace', honor_sequence_lead='top', attitude='standard',
           count='standard', signal_on_partner_lead='attitude', signal_on_declarer_lead='count', first_discard='attitude', trump_signal='none')
SCHEMES = dict(std=STD, ud=dict(STD, attitude='upside_down', count='upside_down'),
               std35=dict(STD, length_lead_vs_suit='3rd_5th', length_lead_vs_nt='3rd_5th'))
PHIS = (.3, 1.)
ASSUMED = ('true', 0., .5, .8, .9)              # the honesty the reader assumes
STATE = {}


def cell_model(name, eps=0.):
    scheme, h = name.split('-')
    return SignalModel(SCHEMES[scheme], int(h) / 100, eps)


def ties(a):
    t = a.get('proposal_probabilities') or a.get('behavior_probabilities') or {}
    return {card(k) for k, p in t.items() if p > 0}


def relabel(board, actions, model, rng, blocked):
    """(plays [(seat, card)], swaps [(ply, x, y)], chances, bad) with the defenders' spots drawn by `model`. `bad` is
    the first ply of the first trick whose winner differs from the record's (the replay stops there), or None."""
    c = board.contract
    game = Game(board)
    recorded = Game(board)
    sigma = [dict() for _ in range(4)]          # recorded card -> the card played in its place
    plays, swaps, chances = [], [], 0
    for ply, a in enumerate(actions):
        o = game.observation()
        seat = o.actor
        rec = card(a['card'])
        x = sigma[seat].get(rec, rec)
        if seat not in (c.declarer, c.dummy):
            tied = {sigma[seat].get(t, t) for t in ties(a)}
            sit = situation(tuple(game.history) + ((seat, x),), ply, c)
            key = sit[0] if sit else 'none'
            kind = model.signal(key) if sit else 'none'
            if kind is not None and len(tied) >= 2:
                suit = x // 13
                if key == 'lead.opening':
                    members = [y for y in o.legal if y // 13 == suit]
                elif x % 13 <= SPOT:
                    members = [y for y in o.legal if y // 13 == suit and y % 13 <= SPOT]
                else:
                    members = []
                choices = [y for y in members if y in tied]
                if len(choices) >= 2 and x in choices:
                    chances += kind != 'none'
                    if ply not in blocked:
                        hand = board.hands[seat]
                        led_suit = game.trick[0][1] // 13 if game.trick else suit
                        holding = [y for y in hand if y // 13 == suit] if key == 'lead.opening' else None
                        dist = model.distribution(key, kind, choices, hand, suit, c.trump, led_suit, c.trump == 4, holding)
                        ticket, y = rng.random(), choices[-1]
                        for z in sorted(dist):
                            ticket -= dist[z]
                            if ticket <= 0:
                                y = z
                                break
                        if y != x:
                            back = {v: k for k, v in sigma[seat].items()}
                            sigma[seat][back.get(y, y)] = x
                            sigma[seat][rec] = y
                            swaps.append((ply, x, y))
                            x = y
        game.play(x)
        recorded.play(rec)
        plays.append((seat, x))
        if len(game.history) % 4 == 0 and game.leader != recorded.leader:
            return plays, swaps, chances, len(game.history) - 4
    return plays, swaps, chances, None


def relabel_consistent(board, actions, model, rng_seed):
    """relabel() with swaps that change a trick's winner undone; None if that does not settle in 12 rounds."""
    blocked = set()
    for _ in range(12):
        plays, swaps, chances, bad = relabel(board, actions, model, random.Random(rng_seed), blocked)
        if bad is None:
            return plays, swaps, chances, len(blocked)
        trick = {x for _, x in plays[bad:bad + 4]} | {card(a['card']) for a in actions[bad:bad + 4]}
        culprit = [ply for ply, x, y in swaps if ply < bad + 4 and ({x, y} & trick) and ply not in blocked]
        if not culprit:
            return None
        blocked.add(max(culprit))
    return None


def gains(fit):
    return float(fit[-1] - (np.logaddexp.reduce(fit[:-1]) - np.log(len(fit) - 1)))


def table_rows(job):
    path, key, cells, source, bot, pool, until, seed, assumed = job
    if 'p' not in STATE:
        m = json.loads((Path(source) / 'manifest.json').read_text())
        STATE['p'] = Gen9Player(dict(m['bots'][bot], engine='gen9', gen9={}), source)
    p = STATE['p']
    with gzip.open(path, 'rt') as f:
        record = json.load(f)['unique_tables'][key]
    board = Board.from_dict(record['board'])
    main = [t for t in record['tables'] if t.get('depth', 0) == 0]
    if board.contract is None or not main or len(main[0]['actions']) < 8:
        return []
    actions = main[0]['actions']
    rows = []
    for cell in cells:
        bot_model = cell_model(cell)
        got = relabel_consistent(board, actions, bot_model, zlib.crc32(f'{Path(path).name}/{key}/{cell}/{seed}'.encode()))
        if got is None:
            rows.append(dict(episode=Path(path).name, table=key, cell=cell, dropped=True))
            continue
        plays, swaps, chances, undone = got
        readers = {h: cell_model(cell, .05) if h == 'true' else SignalModel(bot_model.descriptor, h, .05) for h in assumed}
        rows.append(dict(episode=Path(path).name, table=key, cell=cell, kind='card_stats', swaps=len(swaps), chances=chances, undone=undone,
                         stats=card_stats(board, plays, bot_model, 1 - board.contract.declarer % 2)))
        rng = np.random.default_rng(zlib.crc32(f'{Path(path).name}/{key}/{seed}'.encode()))     # the same pools in every cell
        game = Game(board)
        truth = tuple(tuple(sorted(h)) for h in board.hands)
        for ply, (seat, x) in enumerate(plays):
            if game.done or len(game.history) // 4 + 1 >= until:
                break
            o = game.observation()
            if o.history and o.controller == board.contract.declarer and len(o.legal) > 1:
                view = View(o)
                hidden = hidden_plays(o, True)
                if len(view.hidden) == 2 and hidden:
                    src = p.source(o, view)
                    if src in ('scorer', 'lead_net'):
                        classes = Classes(view)
                        logw = classes.logmult + p.type_log_weights(o, view, classes.length, classes.hon, src)
                        worlds = classes.worlds(spaced(logw, pool, rng.random()), rng)
                        owner = np.zeros(52, np.int8)
                        assign = np.empty((len(worlds) + 1, len(view.unseen)), np.int8)
                        for k, world in enumerate(worlds + [truth]):
                            owner[list(world[view.hidden[1]])] = 1
                            owner[list(world[view.hidden[0]])] = 0
                            assign[k] = owner[view.unseen]
                    else:
                        every = view.every()
                        lw = p.layout_log_weights(o, view, every)
                        w = np.exp(lw - lw.max())
                        pick = rng.choice(len(every), pool, p=w / w.sum())
                        owner = np.zeros(52, np.int8)
                        owner[list(truth[view.hidden[1]])] = 1
                        owner[list(truth[view.hidden[0]])] = 0
                        assign = np.concatenate([every[pick], owner[view.unseen][None].astype(every.dtype)])
                    card_part, class_part = np.zeros(len(assign)), np.zeros(len(assign))
                    signal_part = {h: np.zeros(len(assign)) for h in assumed}
                    read = 0
                    for play in hidden:
                        for h, model in readers.items():
                            lc, lk, ls = p.signal_row(o, view, assign, *play, model)       # the net is called once: cached
                            signal_part[h] += ls
                        card_part += lc
                        class_part += lk
                        read += bool(np.abs(ls).max() > 0)
                    fit = {}
                    for phi in PHIS:
                        fit[f'net{phi:g}'] = phi * card_part
                        fit[f'class{phi:g}'] = phi * class_part
                        for h in assumed:
                            fit[f'sig{phi:g}-h{h}'] = phi * class_part + signal_part[h]
                    rows.append(dict(episode=Path(path).name, table=key, cell=cell, trick=len(o.history) // 4 + 1, source=src,
                                     plays=len(hidden), signal_plays=read, swaps=len(swaps), chances=chances, undone=undone,
                                     gains={r: gains(v) for r, v in fit.items()}))
            game.play(x)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes')
    ap.add_argument('--source', required=True)
    ap.add_argument('--bot', default='7s-32', help="whose net and scorer read the play (a bot of the capsule's manifest)")
    ap.add_argument('--cells', default='std-100,std-80,std-50,std-0,ud-100,ud-80,ud-50,std35-80')
    ap.add_argument('--tables', type=int, default=300)
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--until', type=int, default=7, help='first trick not scored')
    ap.add_argument('--seed', type=int, default=9)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', required=True)
    ap.add_argument('--curve', action='store_true', help='readers assume honesty 0, .1, ..., 1 (for the learning curve, G9-S5)')
    args = ap.parse_args()
    assumed = ('true',) + tuple(round(.1 * k, 1) for k in range(11)) if args.curve else ASSUMED
    cells = args.cells.split(',')
    jobs = []
    for path in sorted(glob.glob(str(Path(args.episodes) / '*.json.gz'))):
        with gzip.open(path, 'rt') as f:
            keys = sorted(json.load(f)['unique_tables'])
        jobs += [(path, k, cells, str(Path(args.source).resolve()), args.bot, args.pool, args.until, args.seed, assumed) for k in keys]
        if len(jobs) >= args.tables:
            break
    jobs = jobs[:args.tables]
    done = 0
    with open(args.out, 'w') as out, ProcessPoolExecutor(args.workers) as pool:
        for rows in pool.map(table_rows, jobs, chunksize=1):
            for r in rows:
                out.write(json.dumps(r) + '\n')
            done += 1
            if done % 10 == 0:
                print(f'{done}/{len(jobs)} tables', flush=True)
    print(f'{done}/{len(jobs)} tables', flush=True)


if __name__ == '__main__':
    main()
