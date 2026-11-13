#!/usr/bin/env python3
"""Train a rollout net: the Gen 7 policy net told who is playing, on a set made by
scripts/gen7_build_dataset.py with its bot columns (meta 8 'bot_name', 9 'bot_other', 10 'has_gap').

  python scripts/train_rollout_net.py --data data.npz --out run_dir [--kind suit] [--epochs 5] [--width 768]
                                      [--id-dropout 0.15] [--compare other_policy.npz ...]

What differs from scripts/train_gen7_policy.py (the v4.1 run's trainer, copied with its options):
- Two learned vectors, the deciding side's bot and the other side's (rows of the set's `bot_names`; row 0 is
  unknown), added to the first trunk layer (bridge_harness.gen7_net.forward, `emb_own` and `emb_other`). They start
  at zero, so a net begins as the plain net. --id-dropout: the share of training rows whose each id is replaced
  by unknown, so that the unknown row learns a generic player. The net is saved with `bot_vocab`.
- Rows without the search's gap (has_gap 0: BEN, the net's own cards, any bot without a search) count for the
  policy, owner and tricks heads but not the gap head, and are left out of the regret scores.
- A legal card whose gap is -1 has no gap (an 8X rollout decision rates its candidates only; scripts/gen7_build_dataset.py
  --rollout-gap): it is left out of the gap loss, and the regret scores count rated cards only (`rated_pick`: the
  share of rows where the net's own card is one the bot rated; `regret` is over those rows).
- Scores also by bot (the deciding side's), from trick 7 on, and with both ids blanked (`who_use`); --compare
  scores other nets on the same held-out rows. Held-out sets are matched to the training set's bots by name.
- --init loads every weight of the given net that this net has; the bot vectors may be missing (they stay zero),
  and a net with another list of bots gives each bot's vectors by name. --init-as NEW=OLD[,...] starts a bot the
  --init net lacks from the vectors of one it has (a new bot built on an old one's play).
- --only-vectors BOT[,BOT...] trains nothing but those bots' two vectors: every other weight, the other bots' vectors
  included, is saved exactly as --init gave it. The net then learns who a new bot is and cannot forget anything
  about the others. Rows of other bots do not move a weight; use --id-dropout 0 with it.
- A set built with --labels (scripts/gen7_build_dataset.py; it carries `sid`) trains a student of the exact line
  finder (experiments/sid_loop/SPEC.md, Part B): per card and target the outputs guar, cert and single, and
  tricks14 from the trunk (bridge_harness.gen7_net.forward). Their losses are binary cross-entropy averaged over
  the labelled (row, legal card, target) entries, and cross-entropy on the final tricks, each added with
  --sid-weight (1.0). Rows without labels train the other heads only. The new weights may be missing from --init
  (they start random). Held-out scores of the label heads are printed every epoch (`sid`). Not with --augment.
  A set with no labels at all trains a net without the label heads; --keep-heads then saves the --init net's label
  weights with the new net, byte for byte. They are not trained, and the layers they read are, so what they
  predict drifts with every step: a stop-gap until the set carries labels, to be scored (scripts/sid_e1.py) before use.

Options as in train_gen7_policy.py:
  python scripts/train_rollout_net.py --data data.npz --out run_dir [--kind suit|mlp] [--epochs 8]
                                      [--augment none|cards|all] [--patience 0]
                                      [--fraction 1.0] [--seed 0] [--all-train --val-data fresh.npz]
                                      [--init policy.npz --lr 5e-4]

Targets: the card Gen 6 played (policy head), Gen 6's gap for every legal card (gap head),
the holder of each unseen card and the final tricks. Deals are split by family in the data
file; --fraction keeps that share of the training deals, for the learning curve. --all-train
trains on every deal of the file whatever its split; the held-out rows then come from --val-data,
a second set of the same format (boards that arrived after the training set was fetched).
--init starts from the weights of a saved net of the same kind and width instead of random ones:
more epochs for a finished net. The rate still warms up and follows one cosine from --lr to
--lr / 50, so give a lower --lr than a run from scratch (a finished run ends at its own floor).
The optimizer's moments are not saved with a net and start from zero.

--augment relabels the four suits of a training position (card play is the same game under
any relabelling as long as the trump suit moves with it). The auction is not: a 2C response
to 1NT says nothing about clubs. 'cards' therefore blanks the auction of a relabelled
position and leaves --identity of the positions untouched, auction included; 'all' relabels
the auction's suit bids too. Held-out positions are never relabelled.
Writes policy.npz (NumPy weights for bridge_harness.gen7_net.PolicyNet) and metrics.json.
Needs jax and optax; inference needs neither.
"""
import argparse
from itertools import permutations
import json
from pathlib import Path
import sys
import time
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.gen7_net import BANK_KEYS, CARD_FEATURES, INPUTS, N_GLOBAL, SEAT_SHOWN, SID_HEADS, SUIT_INPUT, forward

KINDS = {'mlp': 0, 'suit': 1}
PHASES = ('lead', 'tricks 1-4', 'tricks 5-8', 'tricks 9-13')
PERMS = np.array(list(permutations(range(4))), np.int64)        # PERMS[0] is the identity
CARD_KEYS = ('state', 'order', 'legal', 'gap', 'owner')
REGRET = ('in_best', 'regret', 'regret_gap_head', 'regret_random', 'regret_lowest', 'tie_nll', 'rated_pick')


def match_bots(meta, names, vocab):
    """meta with columns 8 and 9 renumbered from `names` into `vocab` (bots the vocabulary lacks become 0, unknown)."""
    index = {n: i for i, n in enumerate(vocab)}
    table = np.array([index.get(str(n), 0) for n in names], np.int32)
    meta = meta.copy()
    meta[:, 8], meta[:, 9] = table[meta[:, 8]], table[meta[:, 9]]
    return meta
PACKED = ('state', 'order', 'legal', 'auction', 'owner', 'sid')  # small whole numbers: held in memory at a few bits each
SID_KINDS = ('guar', 'single', 'cert')          # the order of the label kinds in a set's `sid` (scripts/gen7_build_dataset.py)
SID_SLOTS = 8
SID_NEW = ('wd1s', 'bd1s', 'wk14', 'bk14')      # weights a net started with --init may lack


def sid_labels(sid, legal):
    """{'sid_guar', 'sid_single', 'sid_cert'}: [n, 52, 3] int8 from a set's `sid` rows [n, 72] and the legal mask; -1 where
    there is no label. A row's label slots are its legal cards in rising order."""
    n = len(sid)
    lab = np.asarray(sid).reshape(n, len(SID_KINDS), SID_SLOTS, 3)
    legal = np.asarray(legal).astype(bool)
    slot = np.cumsum(legal, axis=1) - 1
    ok = legal & (slot < SID_SLOTS)
    index = np.clip(slot, 0, SID_SLOTS - 1)[:, :, None]
    return {'sid_' + k: np.where(ok[:, :, None], np.take_along_axis(lab[:, i], index, axis=1), -1).astype(np.int8)
            for i, k in enumerate(SID_KINDS)}


def stored_arrays(path):
    """The arrays of a data file. An uncompressed .npz gives read-only memory maps, so nothing is
    read until it is used and no array is ever in memory twice; a compressed one is read the usual way."""
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
    if any(m.compress_type != zipfile.ZIP_STORED for m in members):
        return np.load(path)
    out = {}
    with open(path, 'rb') as raw:
        for m in members:
            raw.seek(m.header_offset)
            head = raw.read(30)
            if head[:4] != b'PK\x03\x04':
                raise ValueError(f'{path}: bad entry {m.filename}')
            raw.seek(m.header_offset + 30 + int.from_bytes(head[26:28], 'little') + int.from_bytes(head[28:30], 'little'))
            version = np.lib.format.read_magic(raw)
            read = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
            shape, fortran, dtype = read(raw)
            if fortran or dtype.hasobject:
                raise ValueError(f'{path}: cannot map {m.filename}')
            name = m.filename[:-4] if m.filename.endswith('.npy') else m.filename
            out[name] = np.memmap(path, dtype, 'r', raw.tell(), shape) if int(np.prod(shape)) else np.zeros(shape, dtype)
    return out


class Packed:
    """A table of small whole numbers held at the fewest bits that carry them. Indexing with rows
    gives those rows back exactly as they were, in the dtype they came in."""

    def __init__(self, x, chunk=200_000):
        self.shape, self.dtype = x.shape, x.dtype
        lo, hi = 0, 0
        for i in range(0, len(x), chunk):
            c = np.asarray(x[i:i + chunk])
            lo, hi = (int(c.min()), int(c.max())) if i == 0 else (min(lo, int(c.min())), max(hi, int(c.max())))
        self.lo, self.bits = lo, max(1, (hi - lo).bit_length())
        if self.bits > 8:
            raise ValueError('values span more than 8 bits')
        self.weights = (1 << np.arange(self.bits - 1, -1, -1)).astype(np.uint8)
        self.data = np.empty((len(x), (x.shape[1] * self.bits + 7) // 8), np.uint8)
        for i in range(0, len(x), chunk):
            c = (np.asarray(x[i:i + chunk]).astype(np.int16) - lo).astype(np.uint8)
            planes = np.unpackbits(c[:, :, None], axis=2)[:, :, 8 - self.bits:]
            self.data[i:i + chunk] = np.packbits(planes.reshape(len(c), -1), axis=1)

    def __len__(self):
        return self.shape[0]

    def __getitem__(self, rows):
        p = self.data[rows]
        planes = np.unpackbits(p, axis=1, count=self.shape[1] * self.bits).reshape(len(p), self.shape[1], self.bits)
        values = planes[:, :, 0] if self.bits == 1 else planes @ self.weights
        return (values.astype(np.int16) + self.lo).astype(self.dtype)


def relabel(b, perm, auction='permute'):
    """The same positions with suit perm[i, s] of each moved to suit s (cards are 13 * suit + rank).

    auction: 'permute' moves the suit bids with the suits; 'blank' removes the auction of every
    row whose suits actually moved.
    """
    n = len(perm)
    rows = np.arange(n)
    index = (perm[:, :, None] * 13 + np.arange(13)[None, None, :]).reshape(n, 52)
    out = dict(b)
    for k in CARD_KEYS:
        if k in b:
            out[k] = np.take_along_axis(b[k], index, axis=1)
    if 'card' in b:
        out['card'] = np.argsort(perm, axis=1)[rows, b['card'] // 13] * 13 + b['card'] % 13
    ctx = b['ctx'].copy()
    ctx[:, :4] = np.take_along_axis(b['ctx'][:, :4], perm, axis=1)
    out['ctx'] = ctx
    calls = b['auction'].reshape(n, 4, -1)
    moved = (perm != np.arange(4)).any(axis=1)
    if auction == 'blank':
        calls = np.where(moved[:, None, None], 0, calls).astype(calls.dtype)
    else:
        bids = calls[:, :, 3:].reshape(n, 4, 7, 5)              # strain order C D H S N; suit s is strain 3 - s
        source = np.concatenate([3 - perm[:, ::-1], np.full((n, 1), 4)], axis=1)
        bids = np.take_along_axis(bids, np.broadcast_to(source[:, None, None, :], bids.shape), axis=3)
        calls = np.concatenate([calls[:, :, :3], bids.reshape(n, 4, 35)], axis=2)
    out['auction'] = calls.reshape(n, -1)
    shown = b['shown'].reshape(n, 4, SEAT_SHOWN)                # what the calls show is about suits, so it moves with them
    by_suit = np.take_along_axis(shown[:, :, :16].reshape(n, 4, 4, 4), np.broadcast_to(perm[:, None, None, :], (n, 4, 4, 4)), axis=3)
    out['shown'] = np.concatenate([by_suit.reshape(n, 4, 16), shown[:, :, 16:]], axis=2).reshape(n, -1)
    return out


def init(kind, rng, width, bots=0, sid=False):
    def dense(a, b):
        return (rng.standard_normal((a, b)) * np.sqrt(2. / a)).astype(np.float32), np.zeros(b, np.float32)
    g = N_GLOBAL
    p = {}
    if sid and kind == 0:
        raise SystemExit('the label heads need --kind suit')
    if kind == 0:
        sizes = [52 * CARD_FEATURES + g, width, width, width // 2]
        for i in range(3):
            p[f'w{i}'], p[f'b{i}'] = dense(sizes[i], sizes[i + 1])
        p['w_out'], p['b_out'] = dense(sizes[3], 261)
    else:
        e, t = width // 4, width
        p['ws0'], p['bs0'] = dense(SUIT_INPUT, 2 * e)
        p['ws1'], p['bs1'] = dense(2 * e, e)
        p['wt0'], p['bt0'] = dense(4 * e + g, t)
        p['wt1'], p['bt1'] = dense(t, 3 * t // 4)
        p['wd0'], p['bd0'] = dense(e + 3 * t // 4 + 4, 2 * e)
        p['wd1'], p['bd1'] = dense(2 * e, 65)
        p['wk'], p['bk'] = dense(3 * t // 4, 1)
        if sid:                             # after every other draw, so a net without them starts from the same weights
            p['wd1s'], p['bd1s'] = dense(2 * e, 13 * len(SID_HEADS) * 3)
            p['wk14'], p['bk14'] = dense(3 * t // 4, 14)
    if bots:
        p['emb_own'], p['emb_other'] = np.zeros((bots, t), np.float32), np.zeros((bots, t), np.float32)
    return p


def phase_of(ply):
    trick = ply // 4 + 1
    return np.where(ply == 0, 0, np.where(trick <= 4, 1, np.where(trick <= 8, 2, 3)))


def with_ids(b, meta, blank=False):
    ids = np.zeros(len(meta), np.int32)
    return dict(b, bot_own=ids if blank else meta[:, 8].astype(np.int32), bot_other=ids if blank else meta[:, 9].astype(np.int32))


def evaluate(predict, data, index, batch=4096, blank=False):
    """Scores of the policy and gap heads against what the bots did, on the rows in `index` (regret scores on the
    rows with the search's gap only). blank: both bot ids read as unknown."""
    logp, gap_hat = [], []
    for i in range(0, len(index), batch):
        rows = index[i:i + batch]
        out = predict(with_ids({k: data[k][rows] for k in INPUTS}, data['meta'][rows], blank))
        logp.append(np.asarray(out[0]))
        gap_hat.append(np.asarray(out[1]))
    logp, gap_hat = np.concatenate(logp), np.concatenate(gap_hat)
    legal = data['legal'][index]
    gap = data['gap'][index].astype(np.float32)
    meta = data['meta'][index]
    chosen, n = meta[:, 0], len(index)
    rows = np.arange(n)
    pick = logp.argmax(1)
    rated = legal.astype(bool) & (gap >= 0)                     # -1: a legal card the bot's rollouts did not rate
    pick_q = np.where(rated, gap_hat, 1e9).argmin(1)
    tied = rated & (gap <= 1e-9)
    lowest = legal.argmax(1)                                    # the lowest spade, else heart, ...: a fixed dumb rule
    cols = dict(nll=-logp[rows, chosen], uniform_nll=np.log(legal.sum(1)), tie_nll=np.log(np.maximum(tied.sum(1), 1)),
                agree=pick == chosen, in_best=tied[rows, pick], rated_pick=rated[rows, pick],
                regret=np.where(rated[rows, pick], gap[rows, pick], np.nan), regret_gap_head=gap[rows, pick_q],
                regret_random=(gap * rated).sum(1) / np.maximum(rated.sum(1), 1),
                regret_lowest=np.where(rated[rows, lowest], gap[rows, lowest], np.nan))
    searched = meta[:, 10] == 1
    def summary(mask):
        out = dict(n=int(mask.sum()), searched=int((mask & searched).sum()))
        for k, v in cols.items():
            x = np.asarray(v[mask & searched if k in REGRET else mask], np.float64)
            x = x[~np.isnan(x)]
            out[k] = round(float(x.mean()), 4) if len(x) else None
        return out
    phase = phase_of(meta[:, 3])
    declaring = meta[:, 6] < 2
    names = data.get('bot_names')
    name = lambda b: str(names[b]) if names is not None else str(b)
    return dict(all=summary(np.ones(n, bool)), root_tables=summary(meta[:, 2] == 0),
                by_phase={PHASES[i]: summary(phase == i) for i in range(4) if (phase == i).any()},
                declaring=summary(declaring), defending=summary(~declaring), from_trick_7=summary(meta[:, 3] >= 24),
                by_bot={name(b): summary(meta[:, 8] == b) for b in np.unique(meta[:, 8])},
                by_bot_phase={name(b): {PHASES[i]: summary((meta[:, 8] == b) & (phase == i)) for i in range(4) if ((meta[:, 8] == b) & (phase == i)).any()}
                              for b in np.unique(meta[:, 8])})


def evaluate_sid(predict_sid, data, index, batch=4096):
    """Held-out scores of the label heads: per head and target, log-loss and Brier score over the labelled entries, the
    log-loss of the entries' own base rate, and the same for the contract target on rows of the declaring side and of
    the defenders with exactly 7 cards (ply 24 to 27). tricks14: log-loss of the final tricks."""
    sums = {}
    t14 = [0., 0]
    for i in range(0, len(index), batch):
        rows = index[i:i + batch]
        b = with_ids({k: data[k][rows] for k in INPUTS}, data['meta'][rows])
        out = [np.asarray(x) for x in predict_sid(b)]
        probs = dict(zip(SID_HEADS, out[:len(SID_HEADS)]))
        logp14 = out[len(SID_HEADS)]
        meta = data['meta'][rows]
        t14[0] += float(-logp14[np.arange(len(rows)), np.clip(meta[:, 1], 0, 13)].sum())
        t14[1] += len(rows)
        labels = sid_labels(data['sid'][rows], b['legal'])
        declaring = meta[:, 6] < 2
        seven = (meta[:, 3] >= 24) & (meta[:, 3] < 28)
        for k in SID_HEADS:
            y, p = labels['sid_' + k], np.clip(probs[k].astype(np.float64), 1e-7, 1 - 1e-7)
            for name, rmask, tsel in (('all', np.ones(len(rows), bool), slice(None)), ('contract', np.ones(len(rows), bool), slice(1, 2)),
                                      ('contract_7_declaring', seven & declaring, slice(1, 2)), ('contract_7_defending', seven & ~declaring, slice(1, 2))):
                yy, pp = y[rmask][:, :, tsel], p[rmask][:, :, tsel]
                m = yy >= 0
                e = sums.setdefault((k, name), np.zeros(4))
                e += [m.sum(), yy[m].sum(), -(np.where(yy == 1, np.log(pp), np.log(1 - pp)) * m).sum(), (((pp - yy) ** 2) * m).sum()]
    out = {}
    for (k, name), (n, ones, nll, brier) in sums.items():
        if n:
            rate = min(max(ones / n, 1e-7), 1 - 1e-7)
            out.setdefault(k, {})[name] = dict(n=int(n), rate=round(float(ones / n), 4), nll=round(float(nll / n), 4),
                                               base_nll=round(float(-(rate * np.log(rate) + (1 - rate) * np.log(1 - rate))), 4),
                                               brier=round(float(brier / n), 4))
    out['tricks14_nll'] = round(t14[0] / max(t14[1], 1), 4)
    return out


def temperature(predict, data, index, batch=4096):
    """The softmax temperature that minimizes the held-out log-loss of the card played, and that log-loss (a net
    used to draw cards in playouts should be calibrated; v4.1's 768-wide run wanted 1.2 at its last epoch)."""
    logp = np.concatenate([np.asarray(predict(with_ids({k: data[k][index[i:i + batch]] for k in INPUTS}, data['meta'][index[i:i + batch]]))[0])
                           for i in range(0, len(index), batch)]).astype(np.float64)
    chosen = data['meta'][index, 0]
    rows = np.arange(len(index))
    def nll(t):
        x = logp / t
        x = x - x.max(1, keepdims=True)
        return float((np.log(np.exp(x).sum(1)) - x[rows, chosen]).mean())
    grid = np.arange(.7, 2.001, .01)
    losses = [nll(t) for t in grid]
    i = int(np.argmin(losses))
    return dict(t=round(float(grid[i]), 2), nll=round(losses[i], 4), nll_at_1=round(nll(1.), 4))


def main():
    import jax
    import jax.numpy as jnp
    import optax
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--kind', choices=list(KINDS), default='suit')
    p.add_argument('--width', type=int, default=512)
    p.add_argument('--epochs', type=int, default=8)
    p.add_argument('--batch', type=int, default=512)
    p.add_argument('--lr', type=float, default=2e-3)
    p.add_argument('--fraction', type=float, default=1.)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--augment', choices=('none', 'cards', 'all'), default='none')
    p.add_argument('--identity', type=float, default=.5, help="with --augment cards: share of positions left as recorded")
    p.add_argument('--patience', type=int, default=0, help='stop after this many epochs without a better held-out loss; 0 = never')
    p.add_argument('--weight-decay', type=float, default=1e-4)
    p.add_argument('--kinds', default='0,1,2', help='table kinds to train on: 0 root tables, 1 tie-fork tables, 2 gap-fork tables')
    p.add_argument('--save-epochs', action='store_true', help="also write each epoch's weights as policy_epoch<n>.npz")
    p.add_argument('--all-train', action='store_true', help='train on every deal of --data, whatever its split (needs --val-data)')
    p.add_argument('--val-data', type=Path, help='held-out rows come from this set (all of its rows) instead of split 1 of --data')
    p.add_argument('--init', type=Path, help='start from the weights of this net (same kind and width; bot vectors may be missing)')
    p.add_argument('--init-as', default='', help='NEW=OLD[,NEW=OLD...]: a bot the --init net lacks starts from the vectors of one it has')
    p.add_argument('--only-vectors', default='', help="BOT[,BOT...]: train only these bots' vectors; every other weight stays as --init gave it")
    p.add_argument('--id-dropout', type=float, default=.15, help='share of training rows whose each bot id is read as unknown')
    p.add_argument('--compare', type=Path, action='append', default=[], help='also score this net on the same held-out rows')
    p.add_argument('--select', default='', help="BOT[:KEY]: keep the epoch with the lowest held-out KEY (default nll) on this bot's rows, among "
                                                "the epochs whose log-loss on every other bot's rows is within --forget of the starting net's; "
                                                'the starting weights are kept if none is. Default: the lowest log-loss over all rows')
    p.add_argument('--forget', type=float, default=.02, help="with --select: how far the other bots' held-out log-loss may rise")
    p.add_argument('--sid-weight', type=float, default=1., help='weight of each label-head loss (guar, cert, single, tricks14) when the set has labels')
    p.add_argument('--keep-heads', action='store_true', help='a set without labels: save the label weights of the --init net unchanged with the new net')
    a = p.parse_args()
    if a.all_train and not a.val_data:
        p.error('--all-train needs --val-data: with no deal held back there is nothing to score an epoch on')
    a.out.mkdir(parents=True, exist_ok=True)
    kind = KINDS[a.kind]
    z = stored_arrays(a.data)
    sid = 'sid' in z
    if sid and a.augment != 'none':
        p.error('a set with labels cannot be trained with --augment')
    data = {k: Packed(z[k]) if k in PACKED else np.array(z[k]) for k in (*INPUTS, 'gap', 'owner', 'meta', 'deal', *(('sid',) if sid else ()))}
    bank = {k: np.array(z[k]) for k in BANK_KEYS}
    split = np.array(z['deal_split'])
    vocab = [str(x) for x in z['bot_names']]
    data['bot_names'] = np.array(vocab)
    if data['meta'].shape[1] < 11:
        raise SystemExit(f'{a.data} has no bot columns: build it with this branch\'s scripts/gen7_build_dataset.py')
    del z
    print(f"data in memory {sum(v.data.nbytes if isinstance(v, Packed) else v.nbytes for k, v in data.items() if k != 'bot_names') / 2**30:.2f} GB, "
          f"{len(data['deal'])} examples", file=sys.stderr, flush=True)
    train_deals = np.arange(len(split)) if a.all_train else np.flatnonzero(split == 0)
    keep = train_deals[:max(1, int(round(len(train_deals) * a.fraction)))]         # deal order is arbitrary but fixed
    kinds = [int(k) for k in a.kinds.split(',')]
    train = np.flatnonzero(np.isin(data['deal'], keep) & np.isin(data['meta'][:, 2], kinds))
    if a.val_data:
        with np.load(a.val_data) as zv:
            if sid and 'sid' not in zv.files:
                raise SystemExit(f'{a.val_data} has no labels (`sid`) and the training set has')
            vdata = {k: np.array(zv[k]) for k in (*INPUTS, 'gap', 'owner', 'meta', 'deal', *(('sid',) if sid else ()))}
            vdata['meta'] = match_bots(vdata['meta'], zv['bot_names'], vocab)
        vdata['bot_names'] = data['bot_names']
        val = np.arange(len(vdata['deal']))
    else:
        vdata, val = data, np.flatnonzero(split[data['deal']] == 1)
    test = np.zeros(0, np.int64) if a.all_train else np.flatnonzero(split[data['deal']] == 2)
    print(f"{len(keep)} training deals, {len(train)} training examples, {len(val)} held-out examples"
          + (f" from {a.val_data.name} ({len(np.unique(vdata['deal']))} deals)" if a.val_data else ''), file=sys.stderr, flush=True)
    rng = np.random.default_rng(a.seed)
    start = init(kind, rng, a.width, len(vocab), sid)
    kept = {}
    init_as = dict(x.split('=', 1) for x in a.init_as.split(',') if x)
    if init_as and not a.init:
        p.error('--init-as needs --init')
    if a.init:
        with np.load(a.init) as f:
            loaded = {k: f[k].astype(np.float32) for k in f.files if k in start}
            if a.keep_heads and not sid:
                kept = {k: f[k] for k in SID_NEW if k in f.files}
                if len(kept) != len(SID_NEW):
                    raise SystemExit(f'--keep-heads: {a.init} has no label heads')
            theirs = [str(x) for x in f['bot_vocab']] if 'bot_vocab' in f.files else None
            same_kind = int(f['kind']) == kind
        if theirs is not None and theirs != vocab:              # the bot vectors by name; a bot the net lacks starts at zero
            for k in ('emb_own', 'emb_other'):
                if k in loaded:
                    table = np.zeros_like(start[k])
                    for i, name in enumerate(vocab):
                        source = name if name in theirs else init_as.get(name)
                        if source in theirs:
                            table[i] = loaded[k][theirs.index(source)]
                    loaded[k] = table
        if not same_kind or any((k not in loaded and not k.startswith('emb_') and k not in SID_NEW) or (k in loaded and loaded[k].shape != v.shape)
                                for k, v in start.items()):
            raise SystemExit(f'{a.init} is not a net of kind {a.kind} and width {a.width}')
        start = {k: loaded.get(k, v) for k, v in start.items()}
    params = {k: jnp.asarray(v) for k, v in start.items()}
    only = None
    if a.only_vectors:
        if not a.init or a.id_dropout:
            p.error('--only-vectors needs --init and --id-dropout 0')
        missing = [n for n in a.only_vectors.split(',') if n not in vocab]
        if missing:
            p.error(f'--only-vectors: {missing} not among the set\'s bots')
        rows = np.array([vocab.index(n) for n in a.only_vectors.split(',')])
        only = {k: np.zeros(v.shape, np.float32) for k, v in start.items()}
        for k in ('emb_own', 'emb_other'):
            only[k][rows] = 1.
        only = {k: jnp.asarray(v) for k, v in only.items()}
    steps = a.epochs * (len(train) // a.batch)
    schedule = optax.warmup_cosine_decay_schedule(0., a.lr, min(500, steps // 10), steps, a.lr / 50)
    opt = optax.chain(optax.clip_by_global_norm(1.), optax.adamw(schedule, weight_decay=a.weight_decay))
    state = opt.init(params)

    def loss_fn(params, b):
        out = forward(params, b, jnp, kind)
        n = b['legal'].shape[0]
        rows = jnp.arange(n)
        logp = jax.nn.log_softmax(out['policy'])
        ce = -logp[rows, b['card']].mean()
        legal = b['legal'].astype(jnp.float32) * b['has_gap'][:, None] * (b['gap'] >= 0)       # -1: a card with no gap
        target = jnp.clip(b['gap'].astype(jnp.float32), 0., 3.)
        gap = (optax.huber_loss(out['gap'], target, delta=1.) * legal).sum() / jnp.maximum(legal.sum(), 1.)
        seen = b['owner'] < 0
        owner_logp = jax.nn.log_softmax(out['owner'])
        picked = jnp.take_along_axis(owner_logp, jnp.clip(b['owner'], 0, 2).astype(jnp.int32)[..., None], axis=2)[..., 0]
        owner = -(picked * ~seen).sum() / jnp.maximum((~seen).sum(), 1)
        tricks = ((out['tricks'] - b['tricks'] / 13.) ** 2).mean()
        loss = ce + 2. * gap + .5 * owner + tricks
        if not sid:
            return loss, (ce, gap, owner, tricks)
        heads = []
        for k in SID_HEADS:                 # binary cross-entropy over the labelled (row, legal card, target) entries
            y = b['sid_' + k].astype(jnp.float32)
            m = (y >= 0).astype(jnp.float32)
            heads.append((optax.sigmoid_binary_cross_entropy(out[k], jnp.clip(y, 0., 1.)) * m).sum() / jnp.maximum(m.sum(), 1.))
        t14 = optax.softmax_cross_entropy_with_integer_labels(out['tricks14'], jnp.clip(b['tricks'], 0, 13).astype(jnp.int32)).mean()
        return loss + a.sid_weight * (sum(heads) + t14), (ce, gap, owner, tricks, *heads, t14)

    @jax.jit
    def step(params, state, b):
        (loss, parts), grads = jax.value_and_grad(loss_fn, has_aux=True)(params, b)
        if only is not None:                        # before the clip, so its norm is the trained weights' alone
            grads = {k: g * only[k] for k, g in grads.items()}
        updates, state = opt.update(grads, state, params)
        if only is not None:                        # and after, so weight decay does not move a frozen weight
            updates = {k: u * only[k] for k, u in updates.items()}
        return optax.apply_updates(params, updates), state, loss, parts

    @jax.jit
    def predict(params, b):
        out = forward(params, b, jnp, kind)
        return jax.nn.log_softmax(out['policy']), out['gap']

    @jax.jit
    def predict_sid(params, b):
        out = forward(params, b, jnp, kind)
        return (*[jax.nn.sigmoid(out[k]) for k in SID_HEADS], jax.nn.log_softmax(out['tricks14']))

    def batch_of(rows):
        b = {k: data[k][rows] for k in (*INPUTS, 'gap', 'owner')}
        if sid:
            b.update(sid_labels(data['sid'][rows], b['legal']))
        meta = data['meta'][rows]
        b['card'] = meta[:, 0]
        b['tricks'] = meta[:, 1].astype(np.float32)
        b['has_gap'] = meta[:, 10].astype(np.float32)
        for key, col in (('bot_own', 8), ('bot_other', 9)):
            b[key] = np.where(rng.random(len(rows)) < a.id_dropout, 0, meta[:, col]).astype(np.int32)
        if a.augment == 'all':
            b = relabel(b, PERMS[rng.integers(0, len(PERMS), len(rows))])
        elif a.augment == 'cards':
            pick = np.where(rng.random(len(rows)) < a.identity, 0, rng.integers(1, len(PERMS), len(rows)))
            b = relabel(b, PERMS[pick], auction='blank')
        return b

    history, best, started = [], None, time.time()
    select_bot, _, select_key = a.select.partition(':')
    select_key = select_key or 'nll'

    def chooser(v):
        """(the bot's score, the other bots' log-loss) on the held-out rows, for --select."""
        mine, everyone = v['by_bot'][select_bot], v['all']
        rest = (everyone['nll'] * everyone['n'] - mine['nll'] * mine['n']) / max(everyone['n'] - mine['n'], 1)
        return mine[select_key], rest

    start_rest = None
    if select_bot:                              # the starting net is epoch 0: the limit on forgetting is measured from it
        v0 = evaluate(lambda b: predict(params, b), vdata, val)
        if select_bot not in v0['by_bot']:
            raise SystemExit(f'--select: no held-out rows of {select_bot}')
        score0, start_rest = chooser(v0)
        best = (score0, 0, {k: np.asarray(x) for k, x in params.items()})
        history.append(dict(epoch=0, val=v0['all'], select=dict(bot=select_bot, key=select_key, value=score0, rest_nll=round(start_rest, 4))))
        print(json.dumps(history[-1]), flush=True)
    for epoch in range(a.epochs):
        order = rng.permutation(train)
        total = np.zeros(4 + (len(SID_HEADS) + 1 if sid else 0))
        count = 0
        for i in range(0, len(order) - a.batch + 1, a.batch):
            params, state, loss, parts = step(params, state, batch_of(order[i:i + a.batch]))
            total += np.array([float(x) for x in parts])
            count += 1
            if count % 2000 == 0:
                print(f"epoch {epoch + 1} step {count} of {len(order) // a.batch}, {round(time.time() - started)} s", file=sys.stderr, flush=True)
        v = evaluate(lambda b: predict(params, b), vdata, val)
        row = dict(epoch=epoch + 1, seconds=round(time.time() - started), train_ce=round(total[0] / count, 4),
                   train_gap=round(total[1] / count, 4), train_owner=round(total[2] / count, 4), val=v['all'],
                   temperature=temperature(lambda b: predict(params, b), vdata, val))
        if sid:
            row['train_sid'] = {k: round(total[4 + i] / count, 4) for i, k in enumerate((*SID_HEADS, 'tricks14'))}
            row['sid'] = evaluate_sid(lambda b: predict_sid(params, b), vdata, val)
        history.append(row)
        print(json.dumps(row), flush=True)
        if a.save_epochs:                   # every epoch's weights, so an epoch can be chosen by another measure
            np.savez(a.out / f'policy_epoch{epoch + 1}.npz', **{k: np.asarray(x) for k, x in params.items()}, **kept, kind=np.array(kind),
                     bot_vocab=np.array(vocab), **bank)
        if select_bot:
            score, rest = chooser(v)
            row['select'] = dict(bot=select_bot, key=select_key, value=score, rest_nll=round(rest, 4), within=bool(rest <= start_rest + a.forget))
            print(json.dumps(dict(epoch=epoch + 1, select=row['select'])), flush=True)
            if rest <= start_rest + a.forget and score < best[0]:
                best = (score, epoch + 1, {k: np.asarray(x) for k, x in params.items()})
            elif rest > start_rest + a.forget or (a.patience and epoch + 1 - best[1] >= a.patience):
                break                           # past the limit on forgetting (it does not come back), or no better for `patience` epochs
        elif best is None or v['all']['nll'] < best[0]:
            best = (v['all']['nll'], epoch + 1, {k: np.asarray(x) for k, x in params.items()})
        elif a.patience and epoch + 1 - best[1] >= a.patience:
            break
    final = {k: jnp.asarray(x) for k, x in best[2].items()}
    exported = dict(best[2], **kept, kind=np.array(kind))
    np.savez(a.out / 'policy.npz', **exported, bot_vocab=np.array(vocab), **bank)
    # NumPy inference must agree with the trained graph.
    rows = val[:512]
    b = with_ids({k: vdata[k][rows] for k in INPUTS}, vdata['meta'][rows])
    jax_out = np.asarray(forward(final, b, jnp, kind)['policy'])
    numpy_out = forward(exported, b)['policy']
    parity = float(np.abs(np.where(b['legal'], jax_out - numpy_out, 0.)).max())
    if sid:
        j, q = forward(final, b, jnp, kind), forward(exported, b)
        parity = max(parity, *[float(np.abs(np.asarray(j[k]) - q[k]).max()) for k in (*SID_HEADS, 'tricks14')])
    # Does the net use the auction? The same held-out positions with the auction inputs blanked, and with
    # another position's auction in their place. A net that reads the auction must score worse on both.
    held = {k: vdata[k][val] for k in (*INPUTS, 'gap', 'meta')}
    held['bot_names'] = vdata['bot_names']
    everyone = np.arange(len(val))
    other = np.random.default_rng(0).permutation(len(val))
    def short(d):
        return {k: {m: v[m] for m in ('nll', 'agree', 'regret')} for k, v in (('all', d['all']), *d['by_phase'].items())}
    auction_use = {
        'real': short(evaluate(lambda b: predict(final, b), held, everyone)),
        'blank': short(evaluate(lambda b: predict(final, b), dict(held, auction=np.zeros_like(held['auction']),
                                                                  shown=np.zeros_like(held['shown'])), everyone)),
        'another_deals': short(evaluate(lambda b: predict(final, b), dict(held, auction=held['auction'][other],
                                                                          shown=held['shown'][other]), everyone)),
        'blank_calls_only': short(evaluate(lambda b: predict(final, b), dict(held, auction=np.zeros_like(held['auction'])), everyone)),
        'blank_shown_only': short(evaluate(lambda b: predict(final, b), dict(held, shown=np.zeros_like(held['shown'])), everyone)),
    }
    compared = {}
    for path in a.compare:
        with np.load(path) as w:
            other = {k: jnp.asarray(w[k]) for k in w.files if k not in BANK_KEYS + ('kind', 'bot_vocab')}
            if 'bot_vocab' in w.files:              # another rollout net: its own numbering of the bots
                theirs = [str(x) for x in w['bot_vocab']]
                held_other = dict(vdata, meta=match_bots(vdata['meta'], vocab, theirs), bot_names=np.array(theirs))      # by_bot names its rows
            else:
                held_other = vdata
        compared[str(path)] = evaluate(lambda b: predict(other, b), held_other, val)
    who_use = dict(real=short(evaluate(lambda b: predict(final, b), vdata, val)),
                   blank=short(evaluate(lambda b: predict(final, b), vdata, val, blank=True)))
    metrics = dict(bots=vocab, id_dropout=a.id_dropout, only_vectors=a.only_vectors, compared=compared, who_use=who_use, kind=a.kind, width=a.width, kinds=kinds, augment=a.augment, identity=a.identity, weight_decay=a.weight_decay, parameters=int(sum(x.size for x in best[2].values())), epochs=a.epochs,
                   selected_epoch=best[1], fraction=a.fraction, train_deals=int(len(keep)), train_examples=int(len(train)),
                   all_train=a.all_train, val_data=a.val_data.name if a.val_data else None,
                   init=str(a.init) if a.init else None, lr=a.lr, batch=a.batch,
                   validation=evaluate(lambda b: predict(final, b), vdata, val),
                   test=evaluate(lambda b: predict(final, b), data, test) if a.fraction == 1. and len(test) else None,
                   auction_use=auction_use, numpy_parity_max_abs_logit=parity, seconds=round(time.time() - started), history=history,
                   sid_weight=a.sid_weight if sid else None,
                   sid=evaluate_sid(lambda b: predict_sid(final, b), vdata, val) if sid else None,
                   train_labelled=int((data['sid'][train[:200000]] >= 0).any(axis=1).mean() * len(train)) if sid else None)
    (a.out / 'metrics.json').write_text(json.dumps(metrics, indent=1))
    print(json.dumps(dict(done=str(a.out), selected_epoch=best[1], validation=metrics['validation']['all'], parity=parity,
                          auction_use={k: v['all'] for k, v in auction_use.items()},
                          auction_use_lead={k: v.get('lead') for k, v in auction_use.items()})))


if __name__ == '__main__':
    main()
