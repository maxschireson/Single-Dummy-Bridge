#!/usr/bin/env python3
"""E9-14: a per-player head on the policy net, fitted on BEN's own recorded cards, as a curve over boards of experience.

Gen 9 work in progress (sam, signals). Prediction evidence.

Data and split are E9-7's (scripts/gen9_ben_reading.py): the Gen 7 and 7.1 feeds against BEN (16) and BEN (64), deal
families split four to one, the first 300 held-out tables of each version scored.

  1. extract  On every table, each decision in tricks 1 to 6 with more than one legal card, from the chooser's own view
              (the encoding the reader uses, Gen7Player.play_arrays with the cards the chooser then held): the net's
              decoder state, the legal cards and the choice. BEN as declarer (its own and dummy's cards) and the house
              defenders choose a card; BEN's defenders choose a class (the signal model's class rule under E9-7's
              count-everywhere descriptor), since their spots stay with the emission tables.
  2. fit      bridge_harness.play_head heads per BEN version and role on 50, 200 and 1,000 fit tables (5 random subsets
              each) and on all of them, the penalty chosen by 3-fold cross-validation over tables. Control: the same
              head fitted on the house defenders' own cards (all fit tables where BEN declares).
  3. score    At the house bot's decisions after the opening lead and before trick 7, against 256 auction-weighted
              layouts (gen8_play_info's measure), the true layout's gain when
                house defender, BEN declaring: BEN's declarer plays are read by the net at factor 0, 0.3, 0.5, 1
                  (`decl<f>`, E9-7) or by a head at 0.3, 0.5, 1 (`<head>@<f>`); partner's plays in full, by the net or
                  (`ctrl@<f>`) by the house head
                house declarer, BEN defending: the class term at 0.3 or 1 plus E9-7's emission tables (`emission<f>`),
                  or a head's class term at 0.3, 0.5, 1 plus the same tables
              and, on every held-out decision of BEN's (true hand, the player's own view), the log-likelihood of its
              choice under the net and under each head.

  python scripts/gen9_play_head.py FEED_EPISODES_DIRS... --source CAPSULE/recovery --fit E9-7.fit.json --out DIR
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Game, card  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen7 import Gen7Player, hidden_plays  # noqa: E402
from bridge_harness.gen9_play import SignalPlayer  # noqa: E402
from bridge_harness.play_head import PlayHead, choice_log_likelihood, decoder_state, fit_cv, policy_column  # noqa: E402
from bridge_harness.signals import SPOT, SPOT_MASK, SUIT_MASK, SignalModel, situation  # noqa: E402
from gen9_ben_reading import BEN_CARD, ben_tables, load  # noqa: E402
from gen9_reading_gain import gains, pool_layouts  # noqa: E402

UNTIL = 7
ROLES = ('ben.declarer', 'ben.defender', 'house.defender')
SIZES = (50, 200, 1000)
SUBSETS = 5
FACTORS = (.3, .5, 1.)
STATE = {}


def player(source, bot):
    if 'p' not in STATE:
        m = json.loads((Path(source) / 'manifest.json').read_text())
        STATE['p'] = SignalPlayer(dict(m['bots'][bot], gen9={}), source)
        STATE['W'], STATE['b'] = policy_column(STATE['p'].net.params)
    return STATE['p']


def class_mask(history, i, c, held, model):
    """[n, 52] the class the signal model reads play i as (signal_row's rule): the card, or the spots of its suit held."""
    played = history[i][1]
    sit = situation(history, i, c)
    key = sit[0] if sit else 'none'
    kind = model.signal(key) if sit else 'none'
    if kind is None or (played % 13 > SPOT and key != 'lead.opening'):
        K = np.zeros_like(held)
        K[:, played] = True
        return K
    return held & (SUIT_MASK[played // 13] if key == 'lead.opening' else SPOT_MASK[played // 13])[None, :]


def extract(job):
    """{role: dict of arrays} for one table: every choice in tricks 1 to 6, from the chooser's own view."""
    path, key, source, bot = job
    p = player(source, bot)
    board, actions, ben_side = load(path, key)
    if board is None or ben_side is None:
        return {}
    c = board.contract
    game = Game(board)
    for a in actions[:max(1, min(len(actions), 4 * (UNTIL - 1)))]:
        if game.done:
            break
        game.play(card(a['card']))
    o = game.observation()
    history = o.history
    model = SignalModel(BEN_CARD)
    out = {}
    for i, (seat, played) in enumerate(history):
        if i >= 4 * (UNTIL - 1):
            break
        chooser = c.declarer if seat == c.dummy else seat
        role = ('ben.' if chooser % 2 == ben_side else 'house.') + ('declarer' if chooser == c.declarer else 'defender')
        if role not in ROLES:
            continue
        held = np.zeros((1, 52), bool)
        held[0, list(board.hands[chooser])] = True
        held[0, [x for s, x in history[:i] if s == chooser]] = False
        batch = p.play_arrays(o, i, seat, chooser, held)
        legal = np.asarray(batch['legal'])
        if legal.sum() < 2:
            continue
        d, _ = decoder_state(p.net.params, batch)
        if role == 'ben.defender':
            K = class_mask(history, i, c, held, model) & legal
        else:
            K = np.zeros((1, 52), bool)
            K[0, played] = True
        r = out.setdefault(role, dict(d=[], legal=[], K=[], played=[], trick=[], dummy=[]))
        r['d'].append(d[0].astype(np.float16))
        r['legal'].append(legal[0])
        r['K'].append(K[0])
        r['played'].append(played)
        r['trick'].append(i // 4 + 1)
        r['dummy'].append(seat == c.dummy)
    return {role: {k: np.array(v) for k, v in r.items()} for role, r in out.items()}


def gather(pool, tables, source, bot):
    """{(ben, held, role): arrays with a `table` index} over many tables."""
    acc = {}
    jobs = [(p_, k, source, bot) for p_, k, _, _ in tables]
    for t, ((p_, k, ben, held), res) in enumerate(zip(tables, pool.map(extract, jobs, chunksize=8))):
        for role, arrs in res.items():
            a = acc.setdefault((ben, held, role), {})
            for name, v in arrs.items():
                a.setdefault(name, []).append(v)
            a.setdefault('table', []).append(np.full(len(arrs['d']), t))
        if (t + 1) % 500 == 0:
            print(f'extract: {t + 1}/{len(tables)} tables', flush=True)
    return {key: {n: np.concatenate(v) for n, v in a.items()} for key, a in acc.items()}


LAMS_SMALL = (10., 30., 100., 300., 1000., 3000.)
LAMS_LARGE = (3., 10., 30., 100.)         # from 1,000 tables on (the first run's cross-validation never chose above 100 there)


def load_decisions(cache):
    z = np.load(cache)
    data = {}
    for name in z.files:
        ben, held, role, field = name.split('|')
        data.setdefault((ben, held == '1', role), {})[field] = z[name]
    return data


def fit_one(job):
    """One head: (ben, role, name, PlayHead, log entry). The worker reads the decisions file once."""
    ben, role, name, rows, seed, W, b, cache = job
    if STATE.get('data_from') != cache:
        STATE['data'], STATE['data_from'] = load_decisions(cache), cache
    arr = STATE['data'][(ben, False, role)]
    d, legal, K, table = arr['d'][rows], arr['legal'][rows], arr['K'][rows], arr['table'][rows]
    t0 = time.time()
    lams = LAMS_LARGE if len(np.unique(table)) >= 1000 else LAMS_SMALL
    head, cv = fit_cv(d, legal, K, table, W, b, lams=lams, seed=seed)
    entry = dict(ben=ben, role=role, head=name, tables=int(len(np.unique(table))), decisions=int(len(d)), lam=head.lam, tau=head.tau,
                 cv={str(k): round(v, 5) for k, v in cv.items()}, seconds=round(time.time() - t0, 1))
    return ben, role, name, head, entry


def fit_heads(data, seed, pool, cache):
    """{ben: {role: {name: PlayHead}}} and a log of the cross-validation; the fits run in the worker processes."""
    rng = np.random.default_rng(seed)
    jobs = []
    for ben in ('ben', 'ben64'):
        for role in ROLES:
            arr = data.get((ben, False, role))
            if arr is None:
                continue
            tables = np.unique(arr['table'])
            plan = [('all', tables)]
            if role != 'house.defender':
                plan = [(f'n{n}.{s}', rng.choice(tables, n, replace=False)) for n in SIZES if n < len(tables)
                        for s in range(SUBSETS)] + plan
            for name, pick in plan:
                rows = np.isin(arr['table'], pick)
                jobs.append((ben, role, name, np.flatnonzero(rows), seed, STATE['W'], STATE['b'], str(cache)))
    jobs.sort(key=lambda j: -len(j[3]))                # the biggest fits first, so the two workers end together
    heads, log = {}, []
    for ben, role, name, head, entry in pool.map(fit_one, jobs, chunksize=1):
        heads.setdefault(ben, {}).setdefault(role, {})[name] = head
        log.append(entry)
        print(json.dumps(entry), flush=True)
    return heads, log


def choice_rows(data, heads, W, b):
    """Held-out log-likelihood of BEN's own choices (and the house defenders') under the net and each head."""
    out = []
    for ben in ('ben', 'ben64'):
        other = 'ben64' if ben == 'ben' else 'ben'
        for role in ROLES:
            arr = data.get((ben, True, role))
            if arr is None:
                continue
            d = arr['d'].astype(np.float64)
            hs = dict(net=PlayHead.identity(d.shape[2]), **heads[ben][role])
            if role in heads.get(other, {}):
                hs['other.all'] = heads[other][role]['all']
            ll = {name: choice_log_likelihood(h, d, arr['legal'], arr['K'], W, b) for name, h in hs.items()}
            for j in range(len(d)):
                out.append(dict(ben=ben, role=role, table=int(arr['table'][j]), trick=int(arr['trick'][j]), dummy=bool(arr['dummy'][j]),
                                options=int(arr['legal'][j].sum()), ll={k: round(float(v[j]), 5) for k, v in ll.items()}))
    return out


def head_values(p, o, i, seat, chooser, held, K, heads, cache):
    """[n, 1 + H] the floored log-probability of the choice K (n layouts) under the net and each head."""
    W, b = STATE['W'], STATE['b']
    f = p.g7.play_floor
    keys = (held.astype(np.uint64) @ (np.uint64(1) << np.arange(52, dtype=np.uint64))).tolist()
    out = np.zeros((len(held), 1 + len(heads)))
    todo = [r for r, k in enumerate(keys) if (i, k) not in cache]
    if todo:
        batch = p.play_arrays(o, i, seat, chooser, held[todo])
        legal = np.asarray(batch['legal'])
        count = legal.sum(axis=1)
        vals = np.zeros((len(todo), 1 + len(heads)))
        choice = np.flatnonzero(count > 1)
        if len(choice):
            sub = {k: batch[k][choice] for k in batch}
            d, _ = decoder_state(p.net.params, sub)
            d = d.astype(np.float64)
            lg, Kc, n = legal[choice], K[np.array(todo)[choice]] & legal[choice], count[choice]
            for h, head in enumerate([PlayHead.identity(d.shape[2])] + list(heads)):
                pr = np.exp(head.log_policy(d, lg, W, b))
                vals[choice, h] = np.log((1 - f) * (pr * Kc).sum(axis=1) + f * Kc.sum(axis=1) / n)
        for j, r in enumerate(todo):
            cache[(i, keys[r])] = vals[j]
    for r, k in enumerate(keys):
        out[r] = cache[(i, k)]
    return out


def scored(job):
    path, key, source, bot, pool, seed, emit_model, decl_heads, def_heads, ctrl_head = job
    p = player(source, bot)
    board, actions, ben_side = load(path, key)
    if board is None or ben_side is None:
        return []
    c = board.contract
    ben_declares = ben_side == c.declarer % 2
    em = SignalModel(BEN_CARD, emit_model['honesty'], .05, emission={k: np.array(v) for k, v in emit_model['emission'].items()})
    plain = SignalModel(BEN_CARD)
    names = list((decl_heads if ben_declares else def_heads).keys())
    heads = [PlayHead.from_json(h) for h in (decl_heads if ben_declares else def_heads).values()]
    ctrl = [PlayHead.from_json(ctrl_head)] if ctrl_head else []
    rng = np.random.default_rng(zlib.crc32(f'{Path(path).name}/{key}/{seed}'.encode()))
    truth = tuple(tuple(sorted(h)) for h in board.hands)
    game = Game(board)
    rows, cache, ccache = [], {}, {}
    for a in actions:
        if game.done or len(game.history) // 4 + 1 >= UNTIL:
            break
        o = game.observation()
        house = o.controller % 2 != ben_side
        if house and o.history and len(o.legal) > 1:
            view = View(o)
            hidden = hidden_plays(o, True)
            if len(view.hidden) == 2 and hidden:
                src, assign = pool_layouts(p, o, view, truth, pool, rng)
                n = len(assign)
                if ben_declares:                                      # house defender reading BEN's declarer
                    partner, decl = np.zeros(n), np.zeros((n, 1 + len(heads)))
                    partner_ctrl = np.zeros(n)
                    for (i, seat, chooser) in hidden:
                        held = p.held_then(o, view, assign, i, chooser)
                        K = np.zeros_like(held)
                        K[:, o.history[i][1]] = True
                        if chooser == c.declarer:
                            v = head_values(p, o, i, seat, chooser, held, K, heads, cache)
                            if not rows:                              # once a table: the net's column is E9-7's reading
                                ref = Gen7Player.play_log_likelihood(p, o, view, assign, [(i, seat, chooser)])
                                if not np.allclose(ref, v[:, 0], atol=1e-4):
                                    raise RuntimeError(f'card term disagrees with play_log_likelihood: {np.abs(ref - v[:, 0]).max()}')
                            decl += v
                        else:
                            v = head_values(p, o, i, seat, chooser, held, K, ctrl, ccache)
                            partner += v[:, 0]
                            partner_ctrl += v[:, -1]
                    g = {f'decl{f:g}': gains(partner + f * decl[:, 0]) for f in (0.,) + FACTORS}
                    g.update({f'{name}@{f:g}': gains(partner + f * decl[:, 1 + h]) for h, name in enumerate(names) for f in FACTORS})
                    if ctrl:
                        g.update({f'ctrl@{f:g}': gains(partner_ctrl + f * decl[:, 0]) for f in FACTORS})
                    role = 'defender'
                else:                                                 # house declarer reading BEN's defenders
                    cls, sig = np.zeros((n, 1 + len(heads))), np.zeros(n)
                    for play in hidden:
                        i, seat, chooser = play
                        held = p.held_then(o, view, assign, i, chooser)
                        K = class_mask(o.history, i, c, held, plain)
                        v = head_values(p, o, i, seat, chooser, held, K, heads, cache)
                        _, lk, le = p.signal_row(o, view, assign, *play, em)
                        if not np.allclose(lk, v[:, 0], atol=1e-4):
                            raise RuntimeError(f'class term disagrees with signal_row: {np.abs(lk - v[:, 0]).max()}')
                        cls += v
                        sig += le
                    g = {f'emission{f:g}': gains(f * cls[:, 0] + sig) for f in (.3, 1.)}
                    g.update({f'{name}@{f:g}': gains(f * cls[:, 1 + h] + sig) for h, name in enumerate(names) for f in FACTORS})
                    role = 'declarer'
                rows.append(dict(episode=Path(path).name, table=key, role=role, trick=len(o.history) // 4 + 1, source=src,
                                 gains={k: round(v, 5) for k, v in g.items()}))
        game.play(card(a['card']))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes', nargs='+')
    ap.add_argument('--source', required=True)
    ap.add_argument('--fit', required=True, help="E9-7's fit file (emission tables), e.g. reports/gen9-ben-reading-2026-11-12/fit.json")
    ap.add_argument('--bot', default='7s-32')
    ap.add_argument('--tables', type=int, default=300)
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--seed', type=int, default=9)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', required=True)
    ap.add_argument('--stop-after', choices=('extract', 'fit', 'score'), default='score')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    source = str(Path(args.source).resolve())
    p = player(source, args.bot)
    W, b = STATE['W'], STATE['b']
    tables = ben_tables(args.episodes)
    held_by = {ben: [t for t in tables if t[2] == ben and t[3]][:args.tables] for ben in ('ben', 'ben64')}
    chosen = [t for t in tables if not t[3]] + held_by['ben'] + held_by['ben64']
    cache = out / 'decisions.npz'
    with ProcessPoolExecutor(args.workers) as pool:
        if cache.exists():
            data = load_decisions(cache)
        else:
            t0 = time.time()
            data = gather(pool, chosen, source, args.bot)
            np.savez(cache, **{f'{k[0]}|{int(k[1])}|{k[2]}|{f}': v for k, a in data.items() for f, v in a.items()})
            print(f'extracted in {time.time() - t0:.0f} s:', {f'{k[0]}/{"held" if k[1] else "fit"}/{k[2]}': len(a['d']) for k, a in data.items()}, flush=True)
        if args.stop_after == 'extract':
            return
        hfile = out / 'heads.json'
        if hfile.exists():
            j = json.loads(hfile.read_text())
            heads = {ben: {role: {n: PlayHead.from_json(h) for n, h in hs.items()} for role, hs in r.items()} for ben, r in j['heads'].items()}
        else:
            heads, log = fit_heads(data, args.seed, pool, cache)
            hfile.write_text(json.dumps(dict(log=log, heads={ben: {role: {n: h.to_json() for n, h in hs.items()} for role, hs in r.items()}
                                                             for ben, r in heads.items()})))
        with open(out / 'choices.jsonl', 'w') as f:
            for r in choice_rows(data, heads, W, b):
                f.write(json.dumps(r) + '\n')
        if args.stop_after == 'fit':
            return
        fit = json.loads(Path(args.fit).read_text())
        with open(out / 'rows.jsonl', 'w') as f:
            for ben in ('ben', 'ben64'):
                other = 'ben64' if ben == 'ben' else 'ben'
                decl = {n: h.to_json() for n, h in heads[ben]['ben.declarer'].items()}
                decl['other.all'] = heads[other]['ben.declarer']['all'].to_json()
                dfd = {n: h.to_json() for n, h in heads[ben]['ben.defender'].items()}
                dfd['other.all'] = heads[other]['ben.defender']['all'].to_json()
                ctrl = heads[ben]['house.defender']['all'].to_json()
                jobs = [(p_, k, source, args.bot, args.pool, args.seed, fit[ben]['emission'], decl, dfd, ctrl) for p_, k, _, _ in held_by[ben]]
                for done, rows in enumerate(pool.map(scored, jobs, chunksize=1), 1):
                    for r in rows:
                        f.write(json.dumps(dict(r, ben=ben)) + '\n')
                    if done % 20 == 0:
                        print(f'{ben}: {done}/{len(jobs)} held-out tables', flush=True)


if __name__ == '__main__':
    main()
