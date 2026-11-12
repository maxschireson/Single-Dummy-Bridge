#!/usr/bin/env python3
"""Fork pairs as a learning set: what the policy net sees at a fork, and what the fork really cost.

  python scripts/plan_fork_data.py --episodes DIR --net gen7_policy.npz --out forks.npz [--workers 2] [--files N]

One row per gap fork of a played table (scripts/plan_bench.py's pairs, any trick after the opening lead): the
decision at which the table's bot played card A and a forced card B was played out by the same bots.

  y          tricks B really cost on the true deal (A's result minus B's, for the decider's side)
  est        the gap the bot's search gave B at the table
  band, propensity, trick, declaring, legal, family (first 8 bytes of the deal's id), index (the episode's number), ply
  a, b       the two cards (13 * suit + rank)
  da, db     the net's decoder activations for the suits of A and of B [256 each] (the layer its policy, gap and holder
             heads read), ha the trunk's [384]
  net        the net's own figures for the pair: log-probability of A and of B, its gap head for A and for B, its
             tricks head

Nothing here is a player input beyond what the net is given at play; y is a label.
"""
import argparse
import gzip
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import SEATS, Board, Game, card
from bridge_harness.gen7 import player
from bridge_harness.gen7_net import PolicyNet, SEAT_SHOWN, SUIT_SHOWN, CARD_FEATURES, features, log_softmax, relu, stack
import gen7_check as check

STATE = {}


def hidden(params, batch):
    """(decoder activations [n, 4, 256], trunk [n, 384], heads [n, 4, 13, 5], tricks [n]) of the suit-shared net."""
    cards, g = features(batch)
    n = cards.shape[0]
    shown = np.asarray(batch['shown']).astype(np.float32).reshape(n, 4, SEAT_SHOWN)[:, :, :SUIT_SHOWN * 4]
    about_suit = np.transpose(shown.reshape(n, 4, SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * SUIT_SHOWN)
    s = np.concatenate([cards.reshape(n, 4, 13 * CARD_FEATURES), about_suit], axis=2)
    s = relu(s @ params['ws0'] + params['bs0'])
    s = relu(s @ params['ws1'] + params['bs1'])
    h = np.concatenate([s.reshape(n, -1), g], axis=1)
    h = relu(h @ params['wt0'] + params['bt0'])
    h = relu(h @ params['wt1'] + params['bt1'])
    slot = np.broadcast_to(np.eye(4, dtype=np.float32)[None], (n, 4, 4))
    d = np.concatenate([s, np.broadcast_to(h[:, None, :], (n, 4, h.shape[1])), slot], axis=2)
    d = relu(d @ params['wd0'] + params['bd0'])
    out = (d @ params['wd1'] + params['bd1']).reshape(n, 4, 13, 5)
    return d, h, out, (h @ params['wk'] + params['bk'])[:, 0]


def start(net):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    six = player(check.spec('gen6'), ROOT)
    STATE.update(net=PolicyNet(Path(net).resolve(), six.scorer))


def rows_of(path):
    net = STATE['net']
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    meta, obs = [], []
    for e in d['unique_tables'].values():
        if 'tables' not in e:
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        for g in e.get('gap_forks') or []:
            ply = g['ply']
            root, fork = e['tables'][0], e['tables'][g['fork_table']]
            if ply <= 0 or root.get('status', 'ok') != 'ok' or fork.get('status', 'ok') != 'ok' or len(root['actions']) <= ply:
                continue
            game = Game(board)
            for x in root['actions'][:ply]:
                game.play(card(x['card']))
            o = game.observation()
            a, b = card(root['actions'][ply]['card']), card(g['forced_card'])
            if a == b or b not in o.legal:
                continue
            sign = 1 if SEATS.index(root['actions'][ply]['seat']) % 2 == declarer % 2 else -1
            meta.append((sign * (root['declarer_tricks'] - fork['declarer_tricks']), g['estimated_gap'], g['band'], g['propensity'], ply // 4 + 1,
                         sign == 1, len(o.legal), int(d['family'][:15], 16), d.get('index', -1), ply, a, b, len(o.trick), o.actor == board.contract.dummy))
            obs.append(net.encode(o))
    if not meta:
        return None
    batch = stack(obs)
    dec, h, out, tricks = hidden(net.params, batch)
    logp = log_softmax(np.where(np.asarray(batch['legal']), out[..., 0].reshape(len(obs), 52), -1e9))
    gap = out[..., 1].reshape(len(obs), 52)
    m = np.array(meta, np.float64)
    i = np.arange(len(meta))
    a, b = m[:, 10].astype(int), m[:, 11].astype(int)
    return dict(meta=m, da=dec[i, a // 13].astype(np.float32), db=dec[i, b // 13].astype(np.float32), ha=h.astype(np.float32),
                net=np.column_stack([logp[i, a], logp[i, b], gap[i, a], gap[i, b], tricks]).astype(np.float32))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--net', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--files', type=int, default=10 ** 9)
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    files = sorted(a.episodes.glob('*.json.gz'))[:a.files]
    parts = []
    with Pool(a.workers, initializer=start, initargs=(a.net,)) as pool:
        for n, part in enumerate(pool.imap(rows_of, files, chunksize=8)):
            if part:
                parts.append(part)
            if (n + 1) % 500 == 0:
                print(f'{n + 1} files, {sum(len(x["meta"]) for x in parts)} forks', flush=True)
    keys = ('y', 'est', 'band', 'propensity', 'trick', 'declaring', 'legal', 'family', 'index', 'ply', 'a', 'b', 'position', 'dummy')
    meta = np.concatenate([x['meta'] for x in parts])
    np.savez_compressed(a.out, **{k: meta[:, j] for j, k in enumerate(keys)}, **{k: np.concatenate([x[k] for x in parts]) for k in ('da', 'db', 'ha', 'net')})
    print(json.dumps(dict(files=len(files), forks=len(meta))))


if __name__ == '__main__':
    sys.exit(main())
