#!/usr/bin/env python3
"""How much the hidden seats' plays say about their hands when the reader's model of them is the bot itself.

  python scripts/plan_reading_bound.py --episodes DIR --net gen7_policy.npz [--trick 6] [--pool 2000] [--candidates 96]
        [--seeds 2] [--files 200] [--workers 8] [--out rows.json]

Gen 7 and the Gen 8 prototype weigh layouts by the policy net's probability of every card a hidden hand has played.
The net is a model of the house bots; this bench replaces it by the house bot. One sample is one seat of one played
table (Gen 6 self-play) at its first decision of --trick. Candidate layouts are drawn from Gen 6's own beliefs there,
and the true layout is added. For every candidate and every earlier card chosen by a hidden hand (the opening lead
left out), Gen 6 is run --seeds times from the view that hand would have had in that candidate: did it play the card
that was played, and how far behind its best card did it rate that card. The net's log-probability of the same plays
in the same candidates is stored beside it. scripts/plan_reading_report.py turns the rows into nats.

With --swaps the candidates are instead the true layout's neighbours: one honour moved to the other hidden hand for a
small card, or two small cards exchanged. The log-likelihood ratio of the true layout to such a neighbour is the
evidence the plays hold about where that one card is, read by the net or by the bot.

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
from bridge_harness.gen6 import Classes, View, systematic
from bridge_harness.gen7 import floored, hidden_plays, past_view, player
import gen7_check as check

STATE = {}
PRUNE = 9.          # a candidate this many nats behind the best (by the crude count) is not simulated further
MISS, HIT = np.log(.05), np.log(.9)


def start(net, trick, candidates, seeds, seed, pool=2000, floor=.05, swaps=False, inner=0, inner_list=0, chain=0, chains=2, betas=(1.,), table=None):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    six = player(check.spec('gen6'), ROOT)
    sim = six
    if inner:           # a cheaper stand-in for the bot: the same search on fewer layouts
        spec = check.spec('gen6')
        spec = dict(spec, samples=inner, id=f'6-{inner}', gen6=dict(spec['gen6'], list_solve=inner_list or spec['gen6']['list_solve']))
        sim = player(spec, ROOT)
    STATE.update(six=six, sim=sim, seven=player(check.spec('gen7', policy=net), ROOT), trick=trick,
                 candidates=candidates, seeds=seeds, seed=seed, pool=pool, floor=floor, swaps=swaps, chain=chain, chains=chains, betas=tuple(betas), table=table)


def assignment(view, world):
    """Index of the hidden seat holding each unseen card."""
    where = {c: j for j, s in enumerate(view.hidden) for c in world[s]}
    return np.array([where[c] for c in view.unseen], np.int8)


def consistent(o, view, assign):
    """False if the layout would have made a hidden hand revoke: it did not follow suit at some play although, in this
    layout, it then held a card of the suit led."""
    for j, seat in enumerate(view.hidden):
        now = {int(c) for c, h in zip(view.unseen, assign) if h == j}
        for i, (s, c) in enumerate(o.history):
            if s != seat or i % 4 == 0:
                continue
            led = o.history[i - i % 4][1] // 13
            if c // 13 != led and any(x // 13 == led for x in now | {x for t, x in o.history[i:] if t == seat}):
                return False
    return True


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
                row = (chain if STATE.get('chain') else one)(d['family'], key, board, o)
                if row:
                    row['seconds'] = round(time.time() - started, 1)
                    out.append(row)
            game.play(card(x['card']))
    return out


TABLE = (.965, .103, .34, .2, .111, .031, .004, .001, .001)     # chance that the bot plays a card, by how one run of it rated the card
EDGES = (1e-9, .03125, .0625, .125, .25, .5, 1.)                # (played it; level but another played; behind by up to ...): rb1's pairs of runs


def chain(family, key, board, o):
    """A random walk over layouts whose resting distribution is the reading with the simulated bot as the model: Gen 6's
    own weight of the layout times, for every past play of a hidden hand, the chance (TABLE) that the bot plays that card
    given how one run of it from that hand rated it. Steps exchange two cards between the hidden hands."""
    six, seven, sim = STATE['six'], STATE['seven'], STATE['sim']
    view = View(o)
    if len(view.hidden) != 2:
        return None
    rng = np.random.default_rng([STATE['seed'], o.controller, int(family[:8], 16), 7])
    plays = hidden_plays(o, False)
    unseen = [int(c) for c in view.unseen]
    source = six.source(o, view)
    classes = Classes(view)
    logw = classes.logmult + six.type_log_weights(o, view, classes.length, classes.hon, 'scorer' if source == 'list' else source)
    p = np.exp(logw - logw.max())
    worlds = classes.worlds(rng.choice(len(p), STATE['pool'], p=p / p.sum()), rng)
    truth = assignment(view, [tuple(c for c in board.hands[s] if c in set(view.unseen)) if s in view.hidden else () for s in range(4)])
    pool = np.unique(np.array([assignment(view, w) for w in worlds]), axis=0)
    pool = pool[~(pool == truth[None, :]).all(1)]
    logp, opts = seven.play_log_probabilities(o, view, pool, plays)
    read = floored(logp, opts, STATE['floor']).sum(axis=0)
    w = np.exp(read - read.max())
    agree = pool == truth[None, :]
    info = dict(n=len(pool), effective=float(w.sum() ** 2 / (w ** 2).sum()), prior_agree=np.round(agree.mean(0), 4).tolist(),
                net_agree=np.round((w / w.sum()) @ agree, 4).tolist())
    later = {(i, chooser): frozenset(int(x) for s, x in o.history[i:] if s == chooser) for i, _, chooser in plays}
    table = np.log(np.array(STATE.get('table') or TABLE))
    cache, calls = {}, [0]

    def play_loglik(a, row):
        i, seat, chooser = plays[row]
        j = view.hidden.index(chooser)
        hand = frozenset(c for c, h in zip(unseen, a) if h == j) | later[(i, chooser)]
        k = (i, hand)
        if k not in cache:
            then = past_view(o, i, hand)
            if len(then.legal) <= 1:
                cache[k] = 0.
            else:
                played = o.history[i][1]
                dec = sim.choose(then, random.Random(f"{STATE['seed']}/{family}/{o.controller}/{i}/{calls[0]}"))
                calls[0] += 1
                est = dec.details.get('estimates') or {}
                gap = est[symbol(played)]['gap_to_best'] if symbol(played) in est else 9.
                cache[k] = float(table[0 if dec.card == played else 1 + int(np.searchsorted(EDGES, gap, side='left'))])
        return cache[k]

    prior = lambda a: float(six.layout_log_weights(o, view, a[None, :])[0])
    betas = STATE['betas']                                          # the last is 1: the reading itself; the others are flatter and help it move
    out = []
    for c in range(STATE['chains']):
        states = []
        for _ in betas:
            a = pool[rng.choice(len(pool), p=w / w.sum())].copy()
            states.append([a, [play_loglik(a, row) for row in range(len(plays))], prior(a)])
        counts, kept, accepted, proposed, exchanged = np.zeros(len(unseen)), 0, 0, 0, 0
        steps = STATE['chain']
        for t in range(steps):
            for k, beta in enumerate(betas):
                a, la, pa = states[k]
                x, y = rng.integers(len(unseen), size=2)
                if a[x] == a[y]:
                    continue
                b = a.copy()
                b[x], b[y] = a[y], a[x]
                if not consistent(o, view, b):
                    continue
                proposed += beta == 1
                pb = prior(b)
                bar = (np.log(rng.random()) - (pb - pa)) / beta         # the plays' log-likelihood must rise by more than this
                lb, delta, room = [], 0., sum(table[0] - v for v in la)
                for row in range(len(plays)):                           # stop as soon as the rest cannot make up the deficit
                    v = play_loglik(b, row)
                    lb.append(v)
                    delta += v - la[row]
                    room -= table[0] - la[row]
                    if delta + room < bar:
                        break
                else:
                    if delta > bar:
                        states[k] = [b, lb, pb]
                        accepted += beta == 1
            if t % 4 == 3 and len(betas) > 1:                            # exchange the layouts of two neighbouring temperatures
                k = int(rng.integers(len(betas) - 1))
                gain = (betas[k + 1] - betas[k]) * (sum(states[k][1]) - sum(states[k + 1][1]))
                if np.log(rng.random()) < gain:
                    states[k], states[k + 1] = states[k + 1], states[k]
                    exchanged += 1
            if t >= steps // 3:
                counts += states[-1][0] == 0
                kept += 1
        a, la, pa = states[-1]
        out.append(dict(marginal=np.round(counts / max(1, kept), 4).tolist(), accepted=int(accepted), proposed=int(proposed), exchanged=exchanged,
                        end_loglik=float(sum(la)), end_prior=pa, end_agree=float((a == truth).mean())))
    lt = float(sum(play_loglik(truth, row) for row in range(len(plays))))
    c = o.contract
    return dict(family=family, table=key, viewer=SEATS[o.controller], declaring=o.controller % 2 == c.declarer % 2, trick=STATE['trick'],
                unseen=[symbol(x) for x in view.unseen], truth=truth.tolist(), pool=info, chains=out, true_loglik=lt, true_prior=prior(truth),
                plays=len(plays), calls=calls[0])


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
    worlds = classes.worlds(rng.choice(len(p), STATE['pool'], p=p / p.sum()), rng)
    truth = assignment(view, [tuple(c for c in board.hands[s] if c in set(view.unseen)) if s in view.hidden else () for s in range(4)])
    kinds = None
    if STATE['swaps']:
        # the true layout and its neighbours: one honour (T to A) moved to the other hidden hand for a small card of that hand
        # (of the same suit when it has one, so the lengths stay), and a few exchanges of two small cards of one suit
        unseen = [int(c) for c in view.unseen]
        rows, kinds = [truth], [['truth', -1, -1]]
        small = lambda k: unseen[k] % 13 < 8
        for pos, c in enumerate(unseen):
            j = int(truth[pos])
            there = [k for k in range(len(unseen)) if truth[k] != j and small(k)]
            if c % 13 >= 8:
                same = [k for k in there if unseen[k] // 13 == c // 13]
                pick = same or there
                kind = 'honour' if same else 'honour and length'
            else:
                pick = [k for k in there if unseen[k] // 13 == c // 13 and k > pos]
                kind = 'small'
                if rng.random() > .25:
                    continue
            if not pick:
                continue
            k = pick[int(rng.integers(len(pick)))]
            other = truth.copy()
            other[pos], other[k] = truth[k], j
            if consistent(o, view, other):
                rows.append(other)
                kinds.append([kind, c, unseen[k]])
        assign = np.array(rows)
        share = np.concatenate([[0.], np.full(len(rows) - 1, 1 / max(1, len(rows) - 1))])
        pool_info = dict(n=len(rows) - 1)
    else:
        pool = np.unique(np.array([assignment(view, w) for w in worlds]), axis=0)
        pool = pool[~(pool == truth[None, :]).all(1)]
        # the net reads the whole pool; the candidates the bot is run on are drawn from the pool by the net's reading
        logp, opts = seven.play_log_probabilities(o, view, np.concatenate([truth[None, :], pool]), plays)
        read = floored(logp, opts, STATE['floor']).sum(axis=0)
        true_net, read = float(read[0]), read[1:]
        w = np.exp(read - read.max())
        index, share = systematic(w, STATE['candidates'], rng)
        agree = pool == truth[None, :]
        pool_info = dict(n=len(pool), logz_net=float(read.max() + np.log(w.mean())), true_net=true_net, effective=float(w.sum() ** 2 / (w ** 2).sum()),
                         prior_agree=np.round(agree.mean(0), 4).tolist(), net_agree=np.round((w / w.sum()) @ agree, 4).tolist())
        assign = np.concatenate([truth[None, :], pool[index]])
        share = np.concatenate([[0.], share])
    net_logp, options = seven.play_log_probabilities(o, view, assign, plays)       # [plays, candidates]
    n, m = len(assign), STATE['seeds']
    same = np.full((len(plays), n, m), -1, np.int8)                                  # -1 = not simulated (pruned)
    gap = np.full((len(plays), n, m), np.nan, np.float32)
    eligible = np.zeros((len(plays), n, m), np.int8)
    crude = np.zeros(n)
    calls = 0
    rated = []                  # on the true hand: how each run rated every legal card, and which one was really played
    for row, (i, seat, chooser) in enumerate(plays):
        played = o.history[i][1]
        j = view.hidden.index(chooser)
        later = {x for s, x in o.history[i:] if s == chooser}
        alive = crude >= crude.max() - (1e9 if STATE['swaps'] else PRUNE)
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
                dec = STATE['sim'].choose(then, r)
                calls += 1
                est = dec.details.get('estimates') or {}
                if k == 0 and est:
                    cards_ = sorted(est)
                    rated.append(dict(play=row, gaps=[round(est[c]['gap_to_best'], 4) for c in cards_], chosen=cards_.index(symbol(dec.card)),
                                      played=cards_.index(symbol(played))))
                same[row, k, s] = dec.card == played
                gap[row, k, s] = est[symbol(played)]['gap_to_best'] if symbol(played) in est else np.nan
                eligible[row, k, s] = sum(v > 0 for v in (dec.details.get('proposal_probabilities') or dec.details.get('behavior_probabilities') or {}).values())
            crude[k] += np.mean(np.where(same[row, k] == 1, HIT, MISS))
    c = o.contract
    return dict(family=family, table=key, viewer=SEATS[o.controller], declaring=o.controller % 2 == c.declarer % 2, trick=STATE['trick'],
                plays=[dict(i=i, trick=i // 4 + 1, seat=SEATS[seat], chooser=SEATS[chooser], card=symbol(o.history[i][1]),
                            partner=chooser % 2 == o.controller % 2) for i, seat, chooser in plays],
                unseen=[symbol(x) for x in view.unseen], hidden=[SEATS[s] for s in view.hidden],
                pool=pool_info, share=np.round(share, 5).tolist(), kinds=kinds, rated=rated,
                assign=assign.tolist(), net_logp=np.round(net_logp, 4).tolist(), options=options.tolist(),
                same=same.tolist(), gap=np.where(np.isnan(gap), -1., np.round(gap, 4)).tolist(), eligible=eligible.tolist(), calls=calls)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--episodes', required=True)
    p.add_argument('--net', required=True)
    p.add_argument('--trick', type=int, default=6)
    p.add_argument('--candidates', type=int, default=96)
    p.add_argument('--pool', type=int, default=2000)
    p.add_argument('--floor', type=float, default=.05)
    p.add_argument('--inner-samples', type=int, default=0, help='run the bot on this many layouts instead of its 32 (a cheaper model of it)')
    p.add_argument('--inner-list', type=int, default=0, help='and solve at most this many layouts of its deal list')
    p.add_argument('--chain', type=int, default=0, help='instead: walk over layouts for this many steps a chain (the reading with the bot as the model)')
    p.add_argument('--chains', type=int, default=2)
    p.add_argument('--table', help='nine chances for the walk in place of TABLE (the full bot\'s): a card the run played; rated level; behind by up to 1/32, 1/16, 1/8, 1/4, 1/2, 1; more')
    p.add_argument('--betas', default='0.3,0.6,1', help='exponents on the plays\' likelihood of the parallel walks; the last must be 1')
    p.add_argument('--swaps', action='store_true', help='candidates are the true layout with one honour (or two small cards) exchanged between the hidden hands')
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
        part.write_text(json.dumps(dict(settings=dict(net=a.net, trick=a.trick, candidates=a.candidates, pool=a.pool, floor=a.floor, swaps=a.swaps, inner_samples=a.inner_samples, inner_list=a.inner_list, chain=a.chain, chains=a.chains, betas=a.betas, table=a.table, seeds=a.seeds, files=done,
                                                      skip_files=a.skip_files, seed=a.seed, seconds=round(time.time() - started)), rows=rows)))
        part.replace(a.out)

    with Pool(a.workers, initializer=start, initargs=(str(Path(a.net).resolve()), a.trick, a.candidates, a.seeds, a.seed, a.pool, a.floor, a.swaps, a.inner_samples, a.inner_list, a.chain, a.chains, [float(x) for x in a.betas.split(',')], [float(x) for x in a.table.split(',')] if a.table else None)) as pool:
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
