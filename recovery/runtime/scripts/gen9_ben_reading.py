#!/usr/bin/env python3
"""E9-7: a reading model for BEN, fitted on BEN's recorded cards and scored on held-out boards.

Gen 9 work in progress (sam, signals). Prediction evidence.

Boards against BEN (16) and BEN (64) from the Gen 7 and 7.1 feeds are split by deal family: one in
five families is held out. On the other four:

  fit      BEN's defenders, read under a count-everywhere descriptor (count on partner's and declarer's
           leads, in discards and in trumps; third-and-fifth leads), give per signal an emission table
           (signal_experience.emission: P(lowest, highest or a middle spot | the true parity)) and a
           symmetric honesty (signal_experience.honesty), per BEN version.

On held-out boards, at the house bot's decisions after the opening lead and before `--until`:

  house declarer, BEN defending   readers of BEN's defenders: `net0.3` (Gen 8's unknown opponent), `net1`,
                                  `class1` (the class term alone), `honesty1` (class + symmetric honesty),
                                  `emission1` and `emission0.3` (class at 1 or 0.3 + the emission tables)
  house defender, BEN declaring   BEN's declarer plays read by the net at 0, 0.3, 0.5 and 1 (`decl<f>`);
                                  partner's plays always read in full

Gains in nats of the true layout against a pool of auction-weighted layouts (gen8_play_info.py's measure).

  python scripts/gen9_ben_reading.py FEED_EPISODES_DIRS... --source CAPSULE/recovery --out rows.jsonl --tables 300
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
from bridge_harness import experience as xp  # noqa: E402
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen7 import Gen7Player, hidden_plays  # noqa: E402
from bridge_harness.gen9_play import SignalPlayer  # noqa: E402
from bridge_harness.signal_experience import card_stats, emission, emission_stats, honesty, replay_plays  # noqa: E402
from bridge_harness.signals import SignalModel  # noqa: E402
from gen9_reading_gain import gains, pool_layouts  # noqa: E402

BEN_CARD = dict(length_lead_vs_suit='3rd_5th', length_lead_vs_nt='3rd_5th', lead_from_ak='ace', honor_sequence_lead='top', count='standard',
                signal_on_partner_lead='count', signal_on_declarer_lead='count', first_discard='count', trump_signal='count')
DECL_FACTORS = (0., .3, .5, 1.)
STATE = {}


def ben_tables(dirs):
    """[(path, table key, ben id, held out)] for every main table against BEN."""
    out = []
    for path in sorted(f for d in dirs for f in glob.glob(str(Path(d) / '*.json.gz'))):
        with gzip.open(path, 'rt') as f:
            e = json.load(f)
        ben = e.get('opponent')
        if ben not in ('ben', 'ben64'):
            continue
        held = zlib.crc32(str(e.get('family')).encode()) % 5 == 0
        out += [(path, k, ben, held) for k in sorted(e['unique_tables'])]
    return out


def load(path, key):
    with gzip.open(path, 'rt') as f:
        record = json.load(f)['unique_tables'][key]
    board = Board.from_dict(record['board'])
    main = [t for t in record['tables'] if t.get('depth', 0) == 0]
    if board.contract is None or not main or len(main[0]['actions']) < 8:
        return None, None, None
    actions = main[0]['actions']
    roles = {'NESW'.index(a['seat']): a['player'] for a in actions}
    ben_side = next((s % 2 for s, r in roles.items() if r == 'opponent'), None)
    return board, actions, ben_side


def fit_stats(job):
    path, key = job
    board, actions, ben_side = load(path, key)
    if board is None or ben_side is None or ben_side == board.contract.declarer % 2:
        return {}
    plays = replay_plays(board, actions)
    model = SignalModel(BEN_CARD)
    return dict(card_stats(board, plays, model, ben_side), **emission_stats(board, plays, model, ben_side))


def readers_for(stats):
    """(SignalModel with emission tables, SignalModel with symmetric honesty) from pooled fit statistics."""
    base = SignalModel(BEN_CARD)
    emit, hon = {}, {}
    for name, st in stats.items():
        if name.endswith('.emit'):
            emit[name[5:-5]] = emission(st)
        else:
            hon[name[5:]] = honesty(st, prior_mean=.5, prior_n=8., eps=.05)[0]
    lead = hon.get('lead.opening', .5)
    return SignalModel(BEN_CARD, dict(hon, **{'*': .5}), .05, emission=emit), SignalModel(BEN_CARD, dict(hon, **{'*': .5, 'lead.opening': lead}), .05)


def scored(job):
    path, key, source, bot, pool, until, seed, emit_model, hon_model = job
    if 'p' not in STATE:
        m = json.loads((Path(source) / 'manifest.json').read_text())
        STATE['p'] = SignalPlayer(dict(m['bots'][bot], gen9={}), source)
    p = STATE['p']
    board, actions, ben_side = load(path, key)
    if board is None or ben_side is None:
        return []
    c = board.contract
    ben_declares = ben_side == c.declarer % 2
    em = SignalModel(BEN_CARD, emit_model['honesty'], .05, emission=emit_model['emission'])
    hm = SignalModel(BEN_CARD, hon_model['honesty'], .05)
    rng = np.random.default_rng(zlib.crc32(f'{Path(path).name}/{key}/{seed}'.encode()))
    truth = tuple(tuple(sorted(h)) for h in board.hands)
    game = Game(board)
    rows = []
    for a in actions:
        if game.done or len(game.history) // 4 + 1 >= until:
            break
        o = game.observation()
        house = o.controller % 2 != ben_side
        if house and o.history and len(o.legal) > 1:
            view = View(o)
            hidden = hidden_plays(o, True)
            if len(view.hidden) == 2 and hidden:
                src, assign = pool_layouts(p, o, view, truth, pool, rng)
                if not ben_declares:                                   # house declarer reading BEN's defenders
                    card_part, class_part = np.zeros(len(assign)), np.zeros(len(assign))
                    sig_e, sig_h = np.zeros(len(assign)), np.zeros(len(assign))
                    for play in hidden:
                        lc, lk, le = p.signal_row(o, view, assign, *play, em)
                        _, _, lh = p.signal_row(o, view, assign, *play, hm)
                        card_part += lc
                        class_part += lk
                        sig_e += le
                        sig_h += lh
                    g = {'net0.3': gains(.3 * card_part), 'net1': gains(card_part), 'class1': gains(class_part),
                         'honesty1': gains(class_part + sig_h), 'emission1': gains(class_part + sig_e), 'emission0.3': gains(.3 * class_part + sig_e)}
                    role = 'declarer'
                else:                                                  # house defender reading BEN's declarer
                    partner, decl = np.zeros(len(assign)), np.zeros(len(assign))
                    for play in hidden:
                        fit = Gen7Player.play_log_likelihood(p, o, view, assign, [play])
                        if play[2] == c.declarer:
                            decl += fit
                        else:
                            partner += fit
                    g = {f'decl{f:g}': gains(partner + f * decl) for f in DECL_FACTORS}
                    role = 'defender'
                rows.append(dict(episode=Path(path).name, feed=Path(path).parents[2].name, table=key, role=role,
                                 trick=len(o.history) // 4 + 1, source=src, gains=g))
        game.play(card(a['card']))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes', nargs='+')
    ap.add_argument('--source', required=True)
    ap.add_argument('--bot', default='7s-32')
    ap.add_argument('--tables', type=int, default=300, help='held-out tables scored, per BEN version')
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--until', type=int, default=7)
    ap.add_argument('--seed', type=int, default=9)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    tables = ben_tables(args.episodes)
    fitted = {}
    with ProcessPoolExecutor(args.workers) as pool:
        for ben in ('ben', 'ben64'):
            fit = [(p_, k) for p_, k, b, held in tables if b == ben and not held]
            pooled = {}
            for st in pool.map(fit_stats, fit, chunksize=8):
                for name, s in st.items():
                    pooled[name] = xp.merge_stat(pooled[name], s) if name in pooled else s
            em, hm = readers_for(pooled)
            fitted[ben] = dict(fit_tables=len(fit), stats=pooled,
                               emission=dict(honesty=em.honesty_by_key, emission={k: v.tolist() for k, v in em.emission.items()}),
                               honesty=dict(honesty=hm.honesty_by_key))
            print(ben, len(fit), 'fit tables;', {k: [round(x, 3) for x in v[1]] for k, v in fitted[ben]['emission']['emission'].items()},
                  {k: round(v, 3) for k, v in hm.honesty_by_key.items()}, flush=True)
        Path(args.out).with_suffix('.fit.json').write_text(json.dumps(fitted, indent=1))
        with open(args.out, 'w') as out:
            for ben in ('ben', 'ben64'):
                held = [(p_, k) for p_, k, b, h in tables if b == ben and h][:args.tables]
                jobs = [(p_, k, str(Path(args.source).resolve()), args.bot, args.pool, args.until, args.seed,
                         fitted[ben]['emission'], fitted[ben]['honesty']) for p_, k in held]
                done = 0
                for rows in pool.map(scored, jobs, chunksize=1):
                    for r in rows:
                        out.write(json.dumps(dict(r, ben=ben)) + '\n')
                    done += 1
                    if done % 20 == 0:
                        print(f'{ben}: {done}/{len(jobs)} held-out tables', flush=True)


if __name__ == '__main__':
    main()
