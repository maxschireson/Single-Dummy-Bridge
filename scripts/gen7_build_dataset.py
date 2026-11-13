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

--labels DIR [DIR ...] joins the exact line finder's labels (scripts/sid_label.py: one sidecar file per episode,
rows keyed by table and action). The set then has `sid` [rows, 72] int8: label kind (guar, single, cert) x slot
(the row's legal cards in rising order, at most 8) x target (one down, contract, overtrick), -1 where there is no
label, which is every entry of a row no sidecar covers. --label-floors also stores `sid_floor` and `sid_ceil`
[rows, 8, 3] float16 (NaN = none), for scoring a student. A sidecar row the builder does not keep is an error.

--rollout-gap also gives a gap to the decisions an 8X bot made by rollouts alone (the records of
scripts/x8_match.py --episodes; their `x8` note of mode 'rollout' with two or more candidates). Such a decision has no
search estimates. Its gap is each candidate's deficit to the best candidate in the deciding side's tricks, as the
rollouts measured it: paired, layout by layout, where the record keeps the per-layout results (capture level 2), else
the difference of the candidates' means. Every card of a candidate's run of touching cards gets the candidate's
value. The row's other legal cards were not rolled out: their gap is -1, which a trainer must leave out of the gap
loss, and has_gap is 1.

--rollout-layouts K[,K...] (with --rollout-gap): also, for each K, the labels a bot with only K layouts would have had:
`gap_kK` (each candidate's deficit over K of the recorded layouts on which every candidate was played, drawn at random,
nested across K) and `card_kK` (the candidate best over them, the card played where that is the played card's
candidate). Rows the per-layout results cannot shorten (no capture, or fewer than K layouts on which every candidate was
played: mostly late tricks with few layouts, where K binds nothing) keep the full labels; the summary counts them. For measuring how
label quality trades against volume; training reads a variant through training/rollout-loop-20261113/label_variant.py.

--alias OLD=NEW[,OLD=NEW...] renames bots before anything else reads their names (two ids of one bot, as a pair of
distinct ids for self-play, become one name).

DIR holds *.json.gz episode files (any names). Deals are split by family hash:
test when int(family[:8], 16) % 10 == 0, validation when it is 5, otherwise train.
"""
import argparse
import base64
import zlib
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
LABELS = ()
FLOORS = False
SID_KINDS = ('guar', 'single', 'cert')
SID_SLOTS = 8
ROLLOUT_GAP = False
ALIAS = {}
LAYOUTS_K = ()


def start(scorer_path, bots=None, policy_only=False, labels=(), floors=False, rollout_gap=False, alias=None, layouts_k=()):
    global SHOWN, KEEP, POLICY_ONLY, LABELS, FLOORS, ROLLOUT_GAP, ALIAS, LAYOUTS_K
    ROLLOUT_GAP = rollout_gap
    LAYOUTS_K = tuple(layouts_k)
    ALIAS = dict(alias or {})
    SHOWN = Shown(FitScorer(scorer_path), *make_bank())
    KEEP = set(bots) if bots else None
    POLICY_ONLY = policy_only
    LABELS = tuple(Path(x) for x in labels)
    FLOORS = floors


def sidecar(path):
    """{(entry, table, action): (slots, labels [3 kinds, 8 slots, 3 targets], floor, ceil)} for an episode file, from the
    first label directory that has it; None when none has."""
    name = path.name[:-len('.json.gz')] + '.npz'
    for d in LABELS:
        if (d / name).exists():
            with np.load(d / name) as z:
                key, slots = z['key'], z['slots']
                lab = np.stack([z[k] for k in SID_KINDS], axis=1)
                floor, ceil = z['floor'], z['ceil']
            return {tuple(int(v) for v in key[i]): (slots[i], lab[i], floor[i], ceil[i]) for i in range(len(key))}
    return None


def rollout_gaps(note, declaring, target):
    """{card: deficit to the best candidate, in the deciding side's tricks} for an 8X decision made by rollouts alone,
    from its `x8` note; None for any other decision. `declaring`: the deciding side is the declaring side. `target`: the
    tricks the contract needs (a rollout row with a guaranteed contract counts as at least that, as the bot counted it).

    The reference is the surviving candidate with the best mean. With the per-layout results (`cap`: [layout, candidate]
    declarer's tricks, -1 where the candidate was dropped before the layout) a deficit is the weighted mean, over the
    layouts both were played on, of the reference's tricks minus the candidate's; without them it is the difference of
    the two means, each over its own layouts. Where the record keeps only some of the layouts and the candidate and the
    reference were both played on every layout (an opening lead from rollouts: 512 layouts, none dropped), the difference
    of the two means is already that paired mean over all of them, and it is used as it stands. The surviving candidate
    with the least deficit is the zero."""
    if not note or note.get('mode') != 'rollout' or len(note.get('cards') or ()) < 2:
        return None
    roll = note.get('roll') or ()
    if len(roll) != len(note['cards']) or any(r is None for r in roll):
        return None
    roll = np.array(roll, np.float64)
    alive = [int(j) for j in note.get('alive') or range(len(roll))]
    ref = max(alive, key=lambda j: (roll[j], -j))
    deficit = roll[ref] - roll
    cap = note.get('cap')
    if cap:
        k, m = cap['shape']
        t = np.frombuffer(base64.b64decode(cap['t']), np.int8).reshape(k, m).astype(np.int64)
        f = np.frombuffer(base64.b64decode(cap['f']), np.uint8).reshape(k, m).astype(bool)
        w = np.frombuffer(base64.b64decode(cap['w']), np.float32).astype(np.float64)
        played = t >= 0
        final = np.where(f & played, np.maximum(t, target), t)
        worth = final if declaring else -final
        count, full = note.get('n') or (), note.get('layouts') or 0
        for j in range(m):
            if k < full and len(count) == m and count[j] == count[ref] == full:
                continue                                    # both means are over every layout: their difference is the paired one
            rows = played[:, j] & played[:, ref]
            if rows.any():
                deficit[j] = w[rows] @ (worth[rows, ref] - worth[rows, j]) / w[rows].sum()
    deficit = deficit - min(deficit[j] for j in alive)
    return {card(x): float(min(max(deficit[j], 0.), 8.)) for j, run in enumerate(note['runs']) for x in run}


def rollout_gaps_first(note, declaring, target, k):
    """({card: deficit}, best card, best candidate's run) for an 8X rollout decision as `k` of its recorded layouts alone
    measure it (the deficit of rollout_gaps over those layouts); None where the record cannot say (no per-layout results,
    or fewer than k layouts on which every candidate was played). The record keeps the layouts heaviest first, not in
    the order they were played (a random order), so the k are drawn at random from the layouts every candidate was
    played on, the same random order for every k (the 8 are among the 16, the 16 among the 32), seeded by the record."""
    cap = note.get('cap') if note else None
    if not cap or note.get('mode') != 'rollout' or len(note.get('cards') or ()) < 2:
        return None
    rows_, m = cap['shape']
    t = np.frombuffer(base64.b64decode(cap['t']), np.int8).reshape(rows_, m).astype(np.int64)
    complete = np.flatnonzero((t >= 0).all(axis=1))
    if len(complete) < k:
        return None
    pick = complete[np.random.default_rng(zlib.crc32(cap['t'].encode())).permutation(len(complete))[:k]]
    f = np.frombuffer(base64.b64decode(cap['f']), np.uint8).reshape(rows_, m).astype(bool)[pick]
    w = np.frombuffer(base64.b64decode(cap['w']), np.float32).astype(np.float64)[pick]
    t = t[pick]
    if w.sum() <= 0:
        return None
    final = np.where(f, np.maximum(t, target), t)
    worth = (final if declaring else -final).astype(np.float64)
    mean = w @ worth / w.sum()
    best = int(np.argmax(mean))
    deficit = mean[best] - mean
    return ({card(x): float(min(max(deficit[j], 0.), 8.)) for j, run in enumerate(note['runs']) for x in run},
            card(note['cards'][best]), [card(x) for x in note['runs'][best]])


def examples(path):
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    first, second = ALIAS.get(d['candidate'], d['candidate']), ALIAS.get(d['opponent'], d['opponent'])
    who = {'candidate': first, 'opponent': second}
    side = {'candidate': second, 'opponent': first}                         # the other side's bot
    rows, names = [], []
    side_rows = sidecar(path) if LABELS else None
    sid, sid_floor, sid_ceil, used = [], [], [], 0
    extra_k = {}
    for ei, e in enumerate(d['unique_tables'].values()):
        if e.get('schema_version') == 'v4-passed-out-v1':
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        for ti, table in enumerate(e['tables']):
            game = Game(board)
            kind = 2 if table.get('fork_kind') == 'gap' else 0 if table.get('depth', 0) == 0 else 1
            for ai, a in enumerate(table['actions']):
                c = card(a['card'])
                est = a.get('estimates')
                searched = bool(a.get('gen6') and est and len(est) > 1)
                rolled = None
                if ROLLOUT_GAP and not searched and a.get('x8'):
                    seat = game.observation().controller
                    rolled = rollout_gaps(a['x8'], seat % 2 == declarer % 2, board.contract.level + 6)
                if (searched or rolled is not None or (POLICY_ONLY and len(game.observation().legal) > 1)) and not any(a.get(k) for k in SKIP) \
                        and (KEEP is None or who.get(a['player'], '') in KEEP):
                    o = game.observation()
                    x = encode(o, SHOWN)
                    gap = np.zeros(52, np.float16)
                    for k, v in (est.items() if searched else ()):
                        gap[card(k)] = min(v['gap_to_best'], 8.)
                    if rolled is not None:
                        if c not in rolled or not set(rolled) <= set(o.legal):
                            raise ValueError(f'{path.name}: the rollout candidates of {(ei, ti, ai)} do not fit the legal cards')
                        gap[list(o.legal)] = -1.
                        for k, v in rolled.items():
                            gap[k] = v
                    owner = np.full(52, -1, np.int8)
                    for seat, hand in enumerate(game.hands):
                        if seat != o.controller and not (seat == board.contract.dummy and o.history):
                            for h in hand:
                                owner[h] = (seat - o.controller) % 4 - 1
                    if LABELS:
                        got = side_rows.get((ei, ti, ai)) if side_rows else None
                        if got is None:
                            sid.append(np.full((3, SID_SLOTS, 3), -1, np.int8))
                            sid_floor.append(np.full((SID_SLOTS, 3), np.nan, np.float16))
                            sid_ceil.append(np.full((SID_SLOTS, 3), np.nan, np.float16))
                        else:
                            n_legal = len(o.legal)
                            if n_legal > SID_SLOTS or list(got[0][:n_legal]) != sorted(o.legal) or (got[0][n_legal:] >= 0).any():
                                raise ValueError(f'{path.name}: the labels of {(ei, ti, ai)} are for other cards than the legal ones')
                            sid.append(got[1])
                            sid_floor.append(got[2])
                            sid_ceil.append(got[3])
                            used += 1
                    mine = o.controller % 2 == declarer % 2
                    bot = who.get(a['player'], '')
                    names.append((bot, side.get(a['player'], '')))
                    for kk in LAYOUTS_K:            # the labels from the first kk recorded layouts (the full ones where they cannot be shortened)
                        short = rollout_gaps_first(a['x8'], o.controller % 2 == declarer % 2, board.contract.level + 6, kk) \
                            if rolled is not None else None
                        g = gap.copy()
                        pick = c
                        if short is not None:
                            values, best, best_run = short
                            g[list(o.legal)] = -1.
                            for key, v in values.items():
                                g[key] = v
                            pick = c if c in best_run else best
                        extra_k.setdefault(kk, []).append((g, pick, short is None and rolled is not None))
                    rows.append((x['state'], x['order'], x['legal'], x['ctx'], x['auction'], x['shown'].astype(np.float16), gap, owner, (
                        c, table['declarer_tricks'] if mine else 13 - table['declarer_tricks'], kind, a['ply'],
                        0 if bot == '6-32' else 1 if bot == '6-256' else 2, SOURCES.get((a.get('gen6') or {}).get('source'), 4),
                        role(o), min(int(a.get('samples') or 0), 30000), -1, -1, int(searched or rolled is not None))))
                game.play(c)
    if side_rows and KEEP is None and used != len(side_rows):
        raise ValueError(f'{path.name}: {len(side_rows) - used} label rows match no decision the builder keeps')
    if not rows:
        return None
    cols = list(zip(*rows))
    arrays = [np.stack(v) for v in cols[:8]] + [np.array(cols[8], np.int32)]
    if LABELS:
        arrays.append(np.stack(sid).reshape(len(rows), -1))
        if FLOORS:
            arrays += [np.stack(sid_floor), np.stack(sid_ceil)]
    for kk in LAYOUTS_K:
        got = extra_k.get(kk, [])
        arrays.append(np.stack([g for g, _, _ in got]))
        arrays.append(np.array([pk for _, pk, _ in got], np.int32))
        arrays.append(np.array([full for _, _, full in got], bool))
    return d['family'], arrays, names


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--scorer', type=Path, required=True)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--bots', default='', help='comma-separated bot names whose decisions are kept; all when empty')
    p.add_argument('--policy-only', action='store_true', help='also keep decisions without search estimates (has_gap 0)')
    p.add_argument('--labels', type=Path, nargs='*', default=[], help='directories of scripts/sid_label.py sidecar files to join as `sid`')
    p.add_argument('--label-floors', action='store_true', help='with --labels: also store sid_floor and sid_ceil')
    p.add_argument('--rollout-gap', action='store_true', help="8X rollout decisions get the rollouts' gap for their candidates (-1 for the other legal cards)")
    p.add_argument('--rollout-layouts', default='', help='K[,K...]: also the labels from the first K recorded layouts of each rollout decision (gap_kK, card_kK)')
    p.add_argument('--alias', default='', help='OLD=NEW[,OLD=NEW...]: bots renamed before anything else reads their names')
    a = p.parse_args()
    alias = dict(x.split('=', 1) for x in a.alias.split(',') if x)
    layouts_k = tuple(int(x) for x in a.rollout_layouts.split(',') if x)
    if layouts_k and not a.rollout_gap:
        p.error('--rollout-layouts needs --rollout-gap')
    files = sorted(a.episodes.glob('*.json.gz'))
    if a.limit:
        files = files[:a.limit]
    families, parts, deal, who = [], [], [], []
    with Pool(a.workers, initializer=start, initargs=(a.scorer, [b for b in a.bots.split(',') if b], a.policy_only, a.labels,
                                                      a.label_floors, a.rollout_gap, alias, layouts_k)) as pool:
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
    if a.labels:
        names += ('sid', 'sid_floor', 'sid_ceil') if a.label_floors else ('sid',)
    for kk in layouts_k:
        names += (f'gap_k{kk}', f'card_k{kk}', f'full_k{kk}')
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
    summary = dict(episodes=len(files), deals=len(families), unique_families=len(set(families)), examples=n,
                   train=int(by[0]), validation=int(by[1]), test=int(by[2]))
    if a.labels:
        summary['labelled'] = int((out['sid'] >= 0).any(axis=1).sum())
    if a.rollout_gap:
        summary['rows_with_unrated_cards'] = int((out['gap'] < 0).any(axis=1).sum())
    for kk in layouts_k:
        summary[f'k{kk}'] = dict(card_changed=int((out[f'card_k{kk}'] != out['meta'][:, 0]).sum()), kept_full=int(out[f'full_k{kk}'].sum()))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
