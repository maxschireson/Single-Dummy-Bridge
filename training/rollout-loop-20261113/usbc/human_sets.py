#!/usr/bin/env python3
"""The training sets of the human-boards experiment (Max, 09:25 to 09:39 UTC on 14 November; exp_human.sh trains on them).

  python3 human_sets.py HUMAN.npz OUT_DIR BOT_BLOCK.npz [BOT_BLOCK.npz ...] --eval EVAL_BLOCK.npz

HUMAN.npz: scripts/gen7_build_dataset.py --policy-only on human_episodes.py's files (the experts' cards, bot name usbc).
BOT_BLOCKs: published row blocks of the one-net SiD's self-play (rows.sh; bot name stup0, the rollouts' values kept).
Writes to OUT_DIR:
  human.npz   the human rows as they are
  bot.npz     as many whole deals of the bot blocks as the human set has, in the blocks' order
  mixed.npz   both together (a net that is told who is who: usbc and stup0)
  stu_eval.npz, stu_eval_usbc.npz   the EVAL block (deals in none of the above), and the same rows with the bot named usbc:
              the rollouts' values there rate any net's first card, whoever it thinks it is

  python3 human_sets.py --merge OUT.npz IN.npz [IN.npz ...]
Joins sets (a set named twice counts twice: that is how the human rows get more weight), the bots' names united.
"""
import argparse
from pathlib import Path

import numpy as np

ROWS = ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta')
BANK = ('bank_length', 'bank_hon', 'bank_log_weight', 'meta_columns')


def load(path):
    with np.load(path, allow_pickle=True) as z:
        return {k: z[k] for k in z.files}


def keep_deals(z, deals):
    deals = np.asarray(deals)
    rows = np.isin(z['deal'], deals)
    renumber = np.full(len(z['family']), -1, np.int64)
    renumber[deals] = np.arange(len(deals))
    out = {k: z[k][rows] for k in ROWS}
    out['deal'] = renumber[z['deal'][rows]].astype(np.int32)
    out['family'], out['deal_split'] = z['family'][deals], z['deal_split'][deals]
    for k in BANK + ('bot_names',):
        out[k] = z[k]
    return out


def merge(parts):
    names = [''] + sorted({str(n) for p in parts for n in p['bot_names']} - {''})
    out = {k: [] for k in ROWS + ('deal', 'family', 'deal_split')}
    first = 0
    for p in parts:
        index = np.array([names.index(str(n)) for n in p['bot_names']])
        meta = p['meta'].copy()
        meta[:, 8], meta[:, 9] = index[meta[:, 8]], index[meta[:, 9]]
        for k in ROWS:
            out[k].append(meta if k == 'meta' else p[k])
        out['deal'].append(p['deal'] + first)
        out['family'].append(p['family'])
        out['deal_split'].append(p['deal_split'])
        first += len(p['family'])
        for k in BANK:
            if not np.array_equal(p[k], parts[0][k]):
                print(f'warning: {k} differs between the sets; the first set\'s is kept')
    z = {k: np.concatenate(v) for k, v in out.items()}
    z['deal'] = z['deal'].astype(np.int32)
    for k in BANK:
        z[k] = parts[0][k]
    z['bot_names'] = np.array(names)
    return z


def renamed(z, old, new):
    out = dict(z)
    out['bot_names'] = np.array([new if str(n) == old else str(n) for n in z['bot_names']])
    return out


def describe(name, z):
    split = z['deal_split']
    by = {str(z['bot_names'][b]): int((z['meta'][:, 8] == b).sum()) for b in np.unique(z['meta'][:, 8])}
    print(f'{name}: {len(z["deal"])} rows of {len(split)} deals (train {int((split == 0).sum())}, validation {int((split == 1).sum())}, '
          f'test {int((split == 2).sum())}); rows by bot {by}; with the rollouts\' values {float(z["meta"][:, 10].mean()):.0%}')


def main():
    import sys
    if len(sys.argv) > 3 and sys.argv[1] == '--merge':
        z = merge([load(f) for f in sys.argv[3:]])
        describe(sys.argv[2], z)
        np.savez(sys.argv[2], **z)
        return
    p = argparse.ArgumentParser()
    p.add_argument('human', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('blocks', type=Path, nargs='+')
    p.add_argument('--eval', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    human = load(a.human)
    n = len(human['family'])
    bots = merge([load(b) for b in a.blocks])
    assert len(bots['family']) >= n, 'not enough bot deals'
    assert not set(map(str, bots['family'])) & set(map(str, human['family']))
    bot = keep_deals(bots, np.arange(n))
    ev = load(a.eval)
    assert not set(map(str, ev['family'])) & (set(map(str, bot['family'])) | set(map(str, human['family'])))
    sets = dict(human=human, bot=bot, mixed=merge([human, bot]), stu_eval=ev, stu_eval_usbc=renamed(ev, 'stup0', 'usbc'))
    for name, z in sets.items():
        describe(name, z)
        np.savez(a.out / f'{name}.npz', **z)                    # uncompressed, as the builder writes (the trainer memory-maps)


if __name__ == '__main__':
    main()
