#!/usr/bin/env python3
"""Turn published Gen 6 episodes into the Gen 7 policy training set.

One example per committed Gen 6 search decision (root tables and the fresh decisions of fork
tables): the actor's view through bridge_harness.gen7_net.encode, the search's gap for every
legal card, the card played, the holder of each unseen card and the final tricks.

  python scripts/gen7_build_dataset.py --episodes DIR --scorer hand_fit_v0.npz --out data.npz [--workers 2] [--bots 7s-32,71s-32]

--bots keeps only the decisions of those bots (by name, as the episodes' candidate and opponent). Columns 8 and 9
of `meta` ('bot_name', 'bot_other') are the deciding side's bot and the other side's, as rows of `bot_names` (the
names found, sorted, after '' at row 0 for none). Column 10 ('has_gap') is 1 where the row has the search's gap.

--policy-only also keeps the decisions that carry no search estimates (BEN, the Gen 7 net's own cards, Gen 5,
any bot without a search): every decision with more than one legal card. Their gap is 0 and has_gap 0, so a
trainer must leave them out of the gap loss and the regret scores.

--scorer is the hand-fit scorer the bots play with; the net's `shown` inputs are its reading
of each seat's calls (see bridge_harness.gen7_net.Shown).

DIR holds *.json.gz episode files (any names). Deals are split by family hash:
test when int(family[:8], 16) % 10 == 0, validation when it is 5, otherwise train.
"""
import argparse
import gzip
import json
from multiprocessing import Pool
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, Game, card
from bridge_harness.gen6_nets import FitScorer
from bridge_harness.gen7_net import Shown, encode, make_bank, role

SOURCES = {'lead_net': 0, 'scorer': 1, 'deal_list': 2, 'gen5': 3}
SKIP = ('replayed_prefix', 'counterfactual_forced', 'forced', 'fixed_opening_lead')


def split_of(family):
    bucket = int(family[:8], 16) % 10
    return 2 if bucket == 0 else 1 if bucket == 5 else 0


SHOWN = None
KEEP = None
POLICY_ONLY = False


def start(scorer_path, bots=None, policy_only=False):
    global SHOWN, KEEP, POLICY_ONLY
    SHOWN = Shown(FitScorer(scorer_path), *make_bank())
    KEEP = set(bots) if bots else None
    POLICY_ONLY = policy_only


def examples(path):
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    who = {'candidate': d['candidate'], 'opponent': d['opponent']}
    side = {'candidate': d['opponent'], 'opponent': d['candidate']}         # the other side's bot
    rows, names = [], []
    for e in d['unique_tables'].values():
        if e.get('schema_version') == 'v4-passed-out-v1':
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        for table in e['tables']:
            game = Game(board)
            kind = 2 if table.get('fork_kind') == 'gap' else 0 if table.get('depth', 0) == 0 else 1
            for a in table['actions']:
                c = card(a['card'])
                est = a.get('estimates')
                searched = bool(a.get('gen6') and est and len(est) > 1)
                if (searched or (POLICY_ONLY and len(game.observation().legal) > 1)) and not any(a.get(k) for k in SKIP) \
                        and (KEEP is None or who.get(a['player'], '') in KEEP):
                    o = game.observation()
                    x = encode(o, SHOWN)
                    gap = np.zeros(52, np.float16)
                    for k, v in (est.items() if searched else ()):
                        gap[card(k)] = min(v['gap_to_best'], 8.)
                    owner = np.full(52, -1, np.int8)
                    for seat, hand in enumerate(game.hands):
                        if seat != o.controller and not (seat == board.contract.dummy and o.history):
                            for h in hand:
                                owner[h] = (seat - o.controller) % 4 - 1
                    mine = o.controller % 2 == declarer % 2
                    bot = who.get(a['player'], '')
                    names.append((bot, side.get(a['player'], '')))
                    rows.append((x['state'], x['order'], x['legal'], x['ctx'], x['auction'], x['shown'].astype(np.float16), gap, owner, (
                        c, table['declarer_tricks'] if mine else 13 - table['declarer_tricks'], kind, a['ply'],
                        0 if bot == '6-32' else 1 if bot == '6-256' else 2, SOURCES.get((a.get('gen6') or {}).get('source'), 4),
                        role(o), min(int(a.get('samples') or 0), 30000), -1, -1, int(searched))))
                game.play(c)
    if not rows:
        return None
    cols = list(zip(*rows))
    return d['family'], [np.stack(v) for v in cols[:8]] + [np.array(cols[8], np.int32)], names


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--scorer', type=Path, required=True)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--bots', default='', help='comma-separated bot names whose decisions are kept; all when empty')
    p.add_argument('--policy-only', action='store_true', help='also keep decisions without search estimates (has_gap 0)')
    a = p.parse_args()
    files = sorted(a.episodes.glob('*.json.gz'))
    if a.limit:
        files = files[:a.limit]
    families, parts, deal, who = [], [], [], []
    with Pool(a.workers, initializer=start, initargs=(a.scorer, [b for b in a.bots.split(',') if b], a.policy_only)) as pool:
        for i, result in enumerate(pool.imap(examples, files, chunksize=8)):
            if result is None:
                continue
            family, arrays, names = result
            parts.append(arrays)
            who += names
            deal.append(np.full(len(arrays[0]), len(families), np.int32))
            families.append(family)
            if (i + 1) % 500 == 0:
                print(i + 1, 'episodes', sum(len(x) for x in deal), 'examples', flush=True)
    names = ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta')
    out = {n: np.concatenate([part[j] for part in parts]) for j, n in enumerate(names)}
    out['deal'] = np.concatenate(deal)
    out['family'] = np.array(families)
    out['deal_split'] = np.array([split_of(f) for f in families], np.int8)
    out['bank_length'], out['bank_hon'], out['bank_log_weight'] = make_bank()
    vocab = [''] + sorted({n for pair in who for n in pair} - {''})
    index = {n: i for i, n in enumerate(vocab)}
    out['meta'][:, 8] = [index[x] for x, _ in who]
    out['meta'][:, 9] = [index[y] for _, y in who]
    out['meta_columns'] = np.array(['card', 'side_tricks', 'table_kind', 'ply', 'bot', 'source', 'role', 'samples', 'bot_name',
                                    'bot_other', 'has_gap'])
    out['bot_names'] = np.array(vocab)
    np.savez(a.out, **out)
    n = len(out['deal'])
    by = np.bincount(out['deal_split'][out['deal']], minlength=3)
    print(json.dumps(dict(episodes=len(files), deals=len(families), unique_families=len(set(families)), examples=n,
                          train=int(by[0]), validation=int(by[1]), test=int(by[2]))))


if __name__ == '__main__':
    main()
