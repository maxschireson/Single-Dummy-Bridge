#!/usr/bin/env python3
"""E9-6 part 1: what designed signals are worth to the house defenders, and what they leak to declarer.

Gen 9 work in progress (sam, signals). Prediction evidence; no new matches are played.

Recorded main tables are replayed twice: as recorded, and with both defenders' spots and opening
leads re-chosen by a carding scheme at honesty 1 within the recorded tie sets
(scripts/gen9_reading_gain.py: relabel_consistent). At the same plies of the two games:

  defender's decisions   (a) recorded spots, partner read by the house net in full (today's house
                         defence); (b) the scheme's spots, partner read by the scheme (class term at
                         factor 1 plus the signal term, honesty assumed 0.9); (c) the scheme's spots
                         read by the house net (partner signals, nobody reads).
  declarer's decisions   (a) recorded spots read by the house net (today); (b) the scheme's spots read
                         by a declarer who knows the scheme; (c) read by the house net.

Gains are in nats of the true layout against a pool of auction-weighted layouts (as gen8_play_info.py).
Declarer's own plays, at a defender's decisions, are read by the house net in full in every column.

Cells isolate the signals: `all` (fourth-best leads, attitude on partner's lead, count on
declarer's lead, attitude discards), `attitude`, `count`, `discards`, `leads`.

  python scripts/gen9_signal_pair_gain.py EPISODES --source CAPSULE/recovery --tables 300 --out rows.jsonl
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
import sys
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen7 import Gen7Player, hidden_plays  # noqa: E402
from bridge_harness.gen9_play import SignalPlayer  # noqa: E402
from bridge_harness.signals import SignalModel  # noqa: E402
from gen9_reading_gain import gains, pool_layouts, relabel_consistent  # noqa: E402

LEADS = dict(length_lead_vs_suit='4th', length_lead_vs_nt='4th', lead_from_ak='ace', honor_sequence_lead='top')
CELLS = {
    'all': dict(LEADS, attitude='standard', count='standard', signal_on_partner_lead='attitude', signal_on_declarer_lead='count',
                first_discard='attitude', trump_signal='none'),
    'attitude': dict(attitude='standard', signal_on_partner_lead='attitude'),
    'count': dict(count='standard', signal_on_declarer_lead='count'),
    'discards': dict(attitude='standard', first_discard='attitude'),
    'leads': dict(LEADS),
}
STATE = {}


def read(p, o, view, assign, plays, model):
    """[layouts] fits (house, scheme): the house net in full on every hidden play; and the scheme on the plays of a
    defender the model reads (class term at 1 plus signal), the house net on the rest."""
    house = np.zeros(len(assign))
    scheme = np.zeros(len(assign))
    c = o.contract
    for play in plays:
        chooser = play[2]
        if chooser == c.declarer:
            fit = Gen7Player.play_log_likelihood(p, o, view, assign, [play])
            house += fit
            scheme += fit
        else:
            lc, lk, ls = p.signal_row(o, view, assign, *play, model)
            house += lc
            scheme += lk + ls
    return house, scheme


def table_rows(job):
    path, key, cells, source, bot, pool, until, seed = job
    if 'p' not in STATE:
        m = json.loads((Path(source) / 'manifest.json').read_text())
        STATE['p'] = SignalPlayer(dict(m['bots'][bot], gen9={}), source)
    p = STATE['p']
    with gzip.open(path, 'rt') as f:
        record = json.load(f)['unique_tables'][key]
    board = Board.from_dict(record['board'])
    main = [t for t in record['tables'] if t.get('depth', 0) == 0]
    if board.contract is None or not main or len(main[0]['actions']) < 8:
        return []
    actions = main[0]['actions']
    c = board.contract
    truth = tuple(tuple(sorted(h)) for h in board.hands)
    rows = []
    for cell in cells:
        bot_model = SignalModel(CELLS[cell], 1., 0.)
        reader = SignalModel(CELLS[cell], .9, .05)
        got = relabel_consistent(board, actions, bot_model, zlib.crc32(f'{Path(path).name}/{key}/{cell}/{seed}'.encode()))
        if got is None:
            rows.append(dict(episode=Path(path).name, table=key, cell=cell, dropped=True))
            continue
        plays, swaps, chances, undone = got
        recorded, relabelled = Game(board), Game(board)
        for ply, (seat, x) in enumerate(plays):
            if recorded.done or len(recorded.history) // 4 + 1 >= until:
                break
            o0, o1 = recorded.observation(), relabelled.observation()
            if o0.history and len(o0.legal) > 1:
                v0, v1 = View(o0), View(o1)
                h0, h1 = hidden_plays(o0, True), hidden_plays(o1, True)
                if len(v0.hidden) == 2 and h0:
                    role = 'declarer' if o0.controller == c.declarer else 'defender'
                    rng_seed = zlib.crc32(f'{Path(path).name}/{key}/{ply}/{seed}'.encode())
                    src0, a0 = pool_layouts(p, o0, v0, truth, pool, np.random.default_rng(rng_seed))
                    src1, a1 = pool_layouts(p, o1, v1, truth, pool, np.random.default_rng(rng_seed))
                    house0, _ = read(p, o0, v0, a0, h0, reader)
                    house1, scheme1 = read(p, o1, v1, a1, h1, reader)
                    rows.append(dict(episode=Path(path).name, table=key, cell=cell, role=role, trick=len(o0.history) // 4 + 1,
                                     source=src0, swaps=len(swaps), chances=chances, undone=undone,
                                     gains=dict(recorded_house=gains(house0), scheme_read=gains(scheme1), scheme_house=gains(house1))))
            recorded.play(card(actions[ply]['card']))
            relabelled.play(x)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes')
    ap.add_argument('--source', required=True)
    ap.add_argument('--bot', default='7s-32')
    ap.add_argument('--cells', default=','.join(CELLS))
    ap.add_argument('--tables', type=int, default=300)
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--until', type=int, default=7)
    ap.add_argument('--seed', type=int, default=9)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    jobs = []
    for path in sorted(glob.glob(str(Path(args.episodes) / '*.json.gz'))):
        with gzip.open(path, 'rt') as f:
            keys = sorted(json.load(f)['unique_tables'])
        jobs += [(path, k, args.cells.split(','), str(Path(args.source).resolve()), args.bot, args.pool, args.until, args.seed) for k in keys]
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
