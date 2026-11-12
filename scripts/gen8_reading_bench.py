#!/usr/bin/env python3
"""What the net's reading of the play is worth, net by net: each decision's layouts solved once, every reading scored on them.

Written for Task 1 of the Gen 8 hand-over (box/coordination, 12 Nov 2026, 06:48 UTC). The run and its results are in
reports/gen8-reading-by-net-2026-11-12/README.md.

  python scripts/gen8_reading_bench.py pools  --episodes DIR [--episodes DIR ...] --out OUT --net NAME=POLICY.npz [--net ...]
                                              [--shard 0/8] [--tables N] [--pool 512] [--skip-families SET.npz]
  python scripts/gen8_reading_bench.py fits   --out OUT --net NAME=POLICY.npz          (a net added later: no solving)
  python scripts/gen8_reading_bench.py owners --out OUT --episodes DIR --net NAME=POLICY.npz [--net ...]
  python scripts/gen8_reading_bench.py cards  --out OUT --episodes DIR [--net ANY=POLICY.npz] [--redo]
  python scripts/gen8_reading_bench.py report --out OUT --mechanism      (where the nets' information sits, and what directed information is worth)
  python scripts/gen8_reading_bench.py report --out OUT --aim 1.05 --aim 1.85 [--against v4]   (a reading plus aimed information)
  python scripts/gen8_reading_bench.py report --out OUT --near 0.2 --near 0.4 --near-split 0.2   (the same at given strengths)
  python scripts/gen8_reading_bench.py report --out OUT [--json FILE]

pools   For every decision of the recorded root tables after the opening lead where the decider has a choice: the layouts
        the prototype's engine would weigh there. Before the deal list that is the pool Gen7Player.early_layouts draws by
        the hand-fit scorer's class weights (the same draw for every net); from the deal list on it is the listed layouts
        (resampled by scorer weight above play_max_layouts, as the engine does). Every one of those layouts is solved once,
        double dummy, for every legal card, and so is the true deal. Stored with them, for each --net: the net's
        log-probability of the hidden seats' plays so far in each layout and in the true layout (the floored sum
        Gen7Player.play_log_likelihood makes), split into the opening lead, partner's other plays and the opponents'.
fits    The same log-probabilities for one more net, from the stored layouts. Nothing is solved again.
floors  One net's log-probabilities again at other floors (--floor, repeatable), from the stored pools alone: each table is
        replayed from tab-<part>.json.gz, so the episodes are not needed. `report` then has a net NAME@FLOOR for each.
owners  For each --net, its owner head's log-probability of every stored layout and of the true one, from the decider's own
        view (one net row a decision): own-<part>.npz beside each part file. `report --owner B` then adds B times it to
        every layout's log-weight, to see what beliefs learned from the true hands add to the reading or replace of it.
cards   Which card each stored column is (the unseen cards at each decision), which seats a layout's 0 and 1 are, who decides:
        uns-<part>.npz; and each table's board and cards played: tab-<part>.json.gz. `report --mechanism` needs the first.
report  For every net and setting, per decision and by trick: the log-weight the true layout gains from the reading, and
        the double-dummy cost on the true deal of the card the search would choose, against no reading. Two ways of
        choosing: as the engine does (early: the `early_min_effective` halving, then 32 layouts resampled from the pool,
        averaged over evenly spaced resampling offsets; deal list: `list_solve` layouts), and from every stored layout with
        its exact weight. The tree and the tie-break are left out: the cost is the mean over the cards the weighted solves
        rate equal best. Standard errors have the deal as the unit.
        `--opponent-weights 0.2 0.5 1.0 --against v4.1 --net v4`: the opponents' plays alone and on top of partner's at
        these weights, by which bot the opponents were. `--honours 0.25 0.5 ... --against v4.1`: information aimed at
        the honours on top of a net's reading.
        `--list-exponents 0.5 1.0 ...`: the deal list alone, which is all a bot without the early read (Gen 7) reads,
        at these exponents, each against the first and each net against `--against`, on the same decisions.

The settings are the prototype's (`8p-32`: play_weight 1.0, early_play_weight 1.0, early_pool 512, early_min_effective 8,
play_floor 0.05, play_lead) on the live 6-32 search after the lead; `report` can vary them because the solves are stored.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
import gzip
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import Classes, View, _effective, spaced, systematic  # noqa: E402
from bridge_harness.gen7 import Gen7Player, floored, hidden_plays, utilities  # noqa: E402

SCORER = 'models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz'
GEN5_POLICY = 'models/cardplay/gen5-2026-11-10/policy.npz'
FAST = dict(lead_source='scorer', mid_from_trick=14, mid_samples=32, list_from_trick=7, list_solve=256)     # the live 6-32 after the lead
PROTO = dict(play_weight=1.0, play_floor=.05, play_max_layouts=1024, play_lead=True, tie_break='net',
             early_play_weight=1.0, early_pool=512, early_min_effective=8.)                                   # 8p-32 without its tree
PARTS = ('lead', 'partner', 'opp')
BANDS = ('tricks 1-2', 'tricks 3-4', 'tricks 5-6', 'tricks 7-9', 'tricks 10-13', 'before the deal list', 'deal list',
         'declarer deciding', 'defender deciding', 'all')


def band_mask(band, trick, regime, declaring):
    if band.startswith('tricks'):
        lo, hi = (int(x) for x in band.split()[1].split('-'))
        return (trick >= lo) & (trick <= hi)
    return {'before the deal list': regime == 0, 'deal list': regime == 1, 'declarer deciding': declaring, 'defender deciding': ~declaring,
            'all': np.ones(len(trick), bool)}[band]


def spec(policy, pool):
    return dict(id='8p-bench', engine='gen7', samples=32, near_tie=0., exploration=0., policy=GEN5_POLICY, scorer=SCORER,
                gen6=dict(FAST), gen7_policy=str(Path(policy).resolve()), gen7=dict(PROTO, early_pool=pool))


def tables(directories, skip):
    """(episode path, table key, family, bot of each seat's controller, record) of every played root table, in file order."""
    for directory in directories:
        for path in sorted(Path(directory).glob('*.json.gz')):
            with gzip.open(path, 'rt') as f:
                d = json.load(f)
            if d['family'] in skip:
                continue
            who = {'candidate': d['candidate'], 'opponent': d['opponent']}
            for key, e in d['unique_tables'].items():
                if e.get('schema_version') != 'v4-passed-out-v1' and e['tables'][0].get('actions'):
                    yield str(path), key, d['family'], [who[x] for x in e['assignments']], e


def decisions(e):
    """(ply, observation, game) at every decision of the root table where the reading has something to say."""
    game = Game(Board.from_dict(e['board']))
    for k, act in enumerate(e['tables'][0]['actions']):
        o = game.observation()
        if len(o.legal) > 1 and o.history and sum(h is None for h in o.known_hands) == 2 and hidden_plays(o, True):
            yield k, o, game
        game.play(card(act['card']))


def layouts(p, o, view, rng, pool):
    """(owner of each unseen card per layout [L, U], log prior weight [L], regime, layouts card-fit in all)."""
    source = p.source(o, view)
    if source == 'list':
        assign = view.every()
        logw = p.layout_log_weights(o, view, assign)
        listed = len(assign)
        if listed > p.g7.play_max_layouts:
            index, share = systematic(np.exp(logw - logw.max()), p.g7.play_max_layouts, rng)
            assign, logw = assign[index], np.log(share)
        return assign, logw - logw.max() - math.log(np.exp(logw - logw.max()).sum()), 1, listed
    if source not in ('scorer', 'lead_net'):
        return None
    classes = Classes(view)
    logw = classes.logmult + p.type_log_weights(o, view, classes.length, classes.hon, source)
    worlds = classes.worlds(spaced(logw, pool, rng.random()), rng)
    owner = np.zeros(52, np.int8)
    assign = np.empty((len(worlds), len(view.unseen)), np.int8)
    for k, world in enumerate(worlds):
        owner[list(world[view.hidden[1]])] = 1
        owner[list(world[view.hidden[0]])] = 0
        assign[k] = owner[view.unseen]
    return assign, np.full(len(worlds), -math.log(len(worlds))), 0, len(classes)


def fit_parts(p, o, view, assign):
    """[3, layouts] the floored log-probability of the hidden seats' plays: the opening lead, partner's other plays, the opponents'."""
    plays = hidden_plays(o, True)
    logp, options = p.play_log_probabilities(o, view, assign, plays)
    fit = floored(logp, options, p.g7.play_floor)
    out = np.zeros((3, assign.shape[0]), np.float32)
    for row, (i, _, chooser) in enumerate(plays):
        out[0 if i == 0 else 1 if chooser % 2 == o.controller % 2 else 2] += fit[row]
    return out


def owner_fit(p, o, view, assign):
    """[layouts] the owner head's log-probability of a layout from the decider's own view: the sum over the unseen cards of
    log P(the seat the layout gives the card), the head's three seats cut to the two hidden ones."""
    out = np.asarray(p.net.heads([o])['owner'][0], np.float64)
    cols = [(s - o.controller) % 4 - 1 for s in view.hidden]
    logits = out[view.unseen][:, cols]
    logp = logits - np.logaddexp(logits[:, 0], logits[:, 1])[:, None]
    return logp[np.arange(len(view.unseen))[None, :], assign.astype(np.int64)].sum(axis=1).astype(np.float32)


class Store:
    """Decisions appended to lists, written as flat arrays with offsets."""
    FLAT = (('assign', np.int8), ('truth', np.int8), ('u', np.int8), ('u_true', np.int8), ('prior', np.float32), ('legal', np.int8))
    META = ('table', 'ply', 'trick', 'declaring', 'regime', 'layouts', 'unseen', 'cards', 'listed', 'plays', 'solve_seconds', 'hidden_house')

    def __init__(self, nets):
        self.flat = {k: [] for k, _ in self.FLAT}
        self.meta = {k: [] for k in self.META}
        self.fits = {n: [] for n in nets}
        self.tables = []

    def save(self, path):
        out = {k: np.concatenate([np.asarray(x, t).ravel() for x in v]) if v else np.zeros(0, t) for (k, t), v in zip(self.FLAT, self.flat.values())}
        out.update({k: np.asarray(v) for k, v in self.meta.items()})
        out.update({f'fit:{n}': np.concatenate([x.ravel() for x in v]) if v else np.zeros(0, np.float32) for n, v in self.fits.items()})
        out['tables'] = np.array([json.dumps(t) for t in self.tables])
        tmp = Path(str(path) + '.tmp.npz')
        np.savez_compressed(tmp, **out)
        tmp.replace(path)


def load(path):
    """A part file as a list of decisions (dicts of arrays) and its tables."""
    with np.load(path) as z:
        d = {k: z[k] for k in z.files}
    tables_ = [json.loads(t) for t in d['tables'].tolist()]
    rows, at = [], dict(assign=0, truth=0, u=0, u_true=0, prior=0, legal=0, fit=0)
    names = [k[4:] for k in d if k.startswith('fit:')]
    for i in range(len(d['ply'])):
        L, U, C = int(d['layouts'][i]), int(d['unseen'][i]), int(d['cards'][i])
        r = {k: d[k][i] for k in Store.META}
        for k, n, shape in (('assign', L * U, (L, U)), ('truth', U, (U,)), ('u', L * C, (L, C)), ('u_true', C, (C,)), ('prior', L, (L,)), ('legal', C, (C,))):
            r[k] = d[k][at[k]:at[k] + n].reshape(shape)
            at[k] += n
        r['fit'] = {n: d[f'fit:{n}'][at['fit']:at['fit'] + 3 * (L + 1)].reshape(3, L + 1) for n in names}
        at['fit'] += 3 * (L + 1)
        r['family'] = tables_[int(r['table'])]['family']
        r['bots'] = tables_[int(r['table'])].get('bots')
        rows.append(r)
    return rows, tables_, names


def pools(a):
    nets = dict(x.split('=', 1) for x in a.net)
    players = {n: Gen7Player(spec(path, a.pool), ROOT) for n, path in nets.items()}
    p = next(iter(players.values()))
    skip = set()
    for s in a.skip_families:
        with np.load(s) as z:
            skip.update(z['family'].tolist())
    shard, of = (int(x) for x in a.shard.split('/'))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    store, part, started, done, seen = Store(nets), a.part_offset, time.time(), 0, 0
    log = open(out / f'pools-{shard:02d}.log', 'a')
    house = ('6-32', '6-256', '7s-32', '71s-32')
    for index, (path, key, family, bots, e) in enumerate(tables(a.episodes, skip)):
        if index % of != shard:
            continue
        seen += 1
        if seen <= a.skip_tables:
            continue
        if done >= a.tables or time.time() - started > a.seconds:
            break
        t0, n0 = time.time(), len(store.meta['ply'])
        store.tables.append(dict(path=os.path.basename(path), directory=os.path.basename(os.path.dirname(path)), key=key, family=family, bots=bots, index=index))
        for k, o, game in decisions(e):
            view = View(o)
            rng = np.random.default_rng([a.seed, index, k])
            got = layouts(p, o, view, rng, a.pool)
            if got is None:
                continue
            assign, prior, regime, listed = got
            truth = np.array([next(j for j, s in enumerate(view.hidden) if int(x) in game.hands[s]) for x in view.unseen], np.int8)
            legal = sorted(o.legal)
            t1 = time.time()
            fixed = [s for s, h in enumerate(o.known_hands) if h is not None]
            solved = p.dds.solve_batch([view.world(row) for row in assign] + [tuple(tuple(sorted(h)) for h in game.hands)], o.contract.trump, o.leader, o.trick, fixed_seats=fixed)
            u = np.array([[utilities(o, values)[x] for x in legal] for values, _ in solved], np.int8)
            seconds = time.time() - t1
            both = np.concatenate([assign, truth[None]])
            for n, q in players.items():
                store.fits[n].append(fit_parts(q, o, view, both))
            for name, value in (('assign', assign), ('truth', truth), ('u', u[:-1]), ('u_true', u[-1]), ('prior', prior), ('legal', legal)):
                store.flat[name].append(value)
            hidden_bots = [bots[o.contract.declarer if s == o.contract.dummy else s] for s in view.hidden]
            for name, value in (('table', len(store.tables) - 1), ('ply', k), ('trick', len(o.history) // 4 + 1), ('declaring', o.controller % 2 == o.contract.declarer % 2),
                                ('regime', regime), ('layouts', len(assign)), ('unseen', len(view.unseen)), ('cards', len(legal)), ('listed', listed),
                                ('plays', len(hidden_plays(o, True))), ('solve_seconds', seconds), ('hidden_house', all(b in house for b in hidden_bots))):
                store.meta[name].append(value)
        done += 1
        print(json.dumps(dict(table=index, family=family[:12], decisions=len(store.meta['ply']) - n0, seconds=round(time.time() - t0, 1),
                              solve_seconds=round(float(sum(store.meta['solve_seconds'][n0:])), 1), elapsed=round(time.time() - started))), file=log, flush=True)
        if done % a.part == 0:
            store.save(out / f'pools-{shard:02d}-{part:04d}.npz')
            store, part = Store(nets), part + 1
    if store.tables:
        store.save(out / f'pools-{shard:02d}-{part:04d}.npz')
    print(json.dumps(dict(done=done, seconds=round(time.time() - started))), file=log, flush=True)
    for q in players.values():
        q.close()


def fits(a):
    """One more net's log-probabilities for the stored layouts: fit-NAME-<part>.npz beside each part file."""
    name, path = a.net[0].split('=', 1)
    q = Gen7Player(spec(path, 512), ROOT)
    out = Path(a.out)
    for part in sorted(out.glob('pools-*-*.npz')):
        target = out / part.name.replace('pools-', f'fit-{name}-')
        if target.exists():
            continue
        rows, tables_, _ = load(part)
        by_table = {}
        for r in rows:
            by_table.setdefault(int(r['table']), {})[int(r['ply'])] = r
        result = []
        for t, wanted in by_table.items():
            info = tables_[t]
            with gzip.open(Path(a.episodes[0]).parent / info['directory'] / info['path'], 'rt') as f:
                e = json.load(f)['unique_tables'][info['key']]
            for k, o, game in decisions(e):
                if k in wanted:
                    r = wanted[k]
                    wanted[k]['new'] = fit_parts(q, o, View(o), np.concatenate([r['assign'], r['truth'][None]]))
        for r in rows:
            result.append(r['new'].ravel())
        np.savez_compressed(target, fit=np.concatenate(result) if result else np.zeros(0, np.float32))
    q.close()


def floors(a):
    """A net's fits again at other floors, from the stored pools alone (each table replayed from tab-<part>.json.gz, so the
    episodes are not needed): fit-NAME@FLOOR-<part>.npz beside each part file, which `report` reads as one more net named
    NAME@FLOOR. The floor is the share of a uniform choice among the legal cards mixed into the net's probability."""
    name, path = a.net[0].split('=', 1)
    q = Gen7Player(spec(path, 512), ROOT)
    out = Path(a.out)
    shard, of = (int(x) for x in a.shard.split('/'))
    for number, part in enumerate(sorted(out.glob('pools-*-*.npz'))):
        targets = {f: out / part.name.replace('pools-', f'fit-{name}@{f:g}-') for f in a.floor}
        if number % of != shard or all(t.exists() for t in targets.values()):
            continue
        rows, tables_, _ = load(part)
        with gzip.open(out / part.name.replace('pools-', 'tab-').replace('.npz', '.json.gz'), 'rt') as f:
            tabs = json.load(f)
        by_table = {}
        for r in rows:
            by_table.setdefault(int(r['table']), {})[int(r['ply'])] = r
        for t, wanted in by_table.items():
            if (tabs[t]['path'], tabs[t]['key']) != (tables_[t]['path'], tables_[t]['key']):
                raise SystemExit(f'{part.name}: the tab file lists other tables')
            e = dict(board=tabs[t]['board'], tables=[dict(actions=[dict(card=c) for c in tabs[t]['played']])])
            for k, o, game in decisions(e):
                if k in wanted:
                    r = wanted[k]
                    assign = np.concatenate([r['assign'], r['truth'][None]])
                    plays = hidden_plays(o, True)
                    logp, options = q.play_log_probabilities(o, View(o), assign, plays)
                    r['new'] = {}
                    for f in a.floor:
                        fit, parts = floored(logp, options, f), np.zeros((3, assign.shape[0]), np.float32)
                        for row, (i, _, chooser) in enumerate(plays):
                            parts[0 if i == 0 else 1 if chooser % 2 == o.controller % 2 else 2] += fit[row]
                        r['new'][f] = parts
        for f, target in targets.items():
            tmp = Path(str(target) + '.tmp.npz')
            np.savez_compressed(tmp, fit=np.concatenate([r['new'][f].ravel() for r in rows]) if rows else np.zeros(0, np.float32))
            tmp.replace(target)
        if a.verbose:
            print(part.name, len(rows), 'decisions', flush=True)
    q.close()


def owners(a):
    nets = dict(x.split('=', 1) for x in a.net)
    players = {n: Gen7Player(spec(path, 512), ROOT) for n, path in nets.items()}
    out = Path(a.out)
    for part in sorted(out.glob('pools-*-*.npz')):
        target = out / part.name.replace('pools-', 'own-')
        if target.exists():
            continue
        rows, tables_, _ = load(part)
        by_table = {}
        for r in rows:
            by_table.setdefault(int(r['table']), {})[int(r['ply'])] = r
        for t, wanted in by_table.items():
            info = tables_[t]
            with gzip.open(Path(a.episodes[0]).parent / info['directory'] / info['path'], 'rt') as f:
                e = json.load(f)['unique_tables'][info['key']]
            for k, o, game in decisions(e):
                if k in wanted:
                    r = wanted[k]
                    both = np.concatenate([r['assign'], r['truth'][None]])
                    r['own_new'] = {n: owner_fit(q, o, View(o), both) for n, q in players.items()}
        np.savez_compressed(target, **{f'own:{n}': np.concatenate([r['own_new'][n] for r in rows]) if rows else np.zeros(0, np.float32) for n in nets})
    for q in players.values():
        q.close()


def cards(a):
    """uns-<part>.npz: per decision the unseen cards (the columns of the stored layouts), the two hidden seats (a layout's 0 and 1),
    the deciding seat and the seat whose card it is. tab-<part>.json.gz: each table's board and the cards played, so that the
    stored decisions can be replayed without the episode files. With --net (any net): scw-<part>.npz, the hand-fit scorer's
    auction log-weight of every stored layout and of the true one, which is what drew the pools."""
    out = Path(a.out)
    p = Gen7Player(spec(a.net[0].split('=', 1)[1], 512), ROOT) if a.net else None      # any net: only its scorer is used
    for part in sorted(out.glob('pools-*-*.npz')):
        target = out / part.name.replace('pools-', 'uns-')
        if target.exists() and not a.redo:
            continue
        rows, tables_, _ = load(part)
        by_table = {}
        for r in rows:
            by_table.setdefault(int(r['table']), {})[int(r['ply'])] = r
        for t, wanted in by_table.items():
            info = tables_[t]
            with gzip.open(Path(a.episodes[0]).parent / info['directory'] / info['path'], 'rt') as f:
                e = json.load(f)['unique_tables'][info['key']]
            info['board'], info['played'] = e['board'], [act['card'] for act in e['tables'][0]['actions']]
            for k, o, game in decisions(e):
                if k in wanted:
                    view = View(o)
                    wanted[k].update(cards_new=view.unseen.astype(np.int8), hidden_new=np.array(view.hidden, np.int8), who_new=(o.controller, o.actor))
                    if p is not None:           # the hand-fit scorer's auction log-weight of every stored layout and of the true one
                        both = np.concatenate([wanted[k]['assign'], wanted[k]['truth'][None]])
                        wanted[k]['scorer_new'] = np.asarray(p.layout_log_weights(o, view, both), np.float32)
        flat = lambda key: np.concatenate([r[key] for r in rows]) if rows else np.zeros(0, np.int8)
        np.savez_compressed(target, cards=flat('cards_new'), hidden=flat('hidden_new'), controller=np.array([r['who_new'][0] for r in rows], np.int8),
                            actor=np.array([r['who_new'][1] for r in rows], np.int8))
        with gzip.open(out / part.name.replace('pools-', 'tab-').replace('.npz', '.json.gz'), 'wt') as f:
            json.dump(tables_, f)
        if p is not None:
            np.savez_compressed(out / part.name.replace('pools-', 'scw-'), scorer=np.concatenate([r['scorer_new'] for r in rows]) if rows else np.zeros(0, np.float32))
    if p is not None:
        p.close()


# ---- report -------------------------------------------------------------------------------------------------------------

def choice_cost(weights, u, cost):
    """Mean true-deal cost over the cards rated equal best by the weighted solves."""
    means = weights @ u
    return float(cost[means >= means.max() - 1e-9].mean())


def resampled_cost(w, u, cost, n, offsets):
    """The same when only n layouts are solved, drawn in proportion to w with evenly spaced picks: mean over the offsets."""
    c = np.cumsum(w, dtype=np.float64)
    c /= c[-1]
    total = 0.
    for r in offsets:
        picks = np.minimum(np.searchsorted(c, (r + np.arange(n)) / n, side='right'), len(c) - 1)
        means = np.bincount(picks, minlength=len(w)).astype(np.float64) @ u
        total += float(cost[means >= means.max() - 1e-9].mean())
    return total / len(offsets)


def score(r, fit, power, min_effective=8., solved=32, list_solve=256, offsets=8, parts=(1., 1., 1.), stride=1, own=None, beta=0.):
    """One decision under one reading: (log-weight gained by the true layout, engine-way cost, every-layout cost, exponent used, effective layouts).
    With `own` (the owner head's log-probability of each layout) and beta, beta times it is added to the reading's sum."""
    L = int(r['layouts'])
    u, cost = r['u'].astype(np.float64), (r['u_true'].max() - r['u_true']).astype(np.float64)
    f = parts[0] * fit[0] + parts[1] * fit[1] + parts[2] * fit[2]
    if beta:
        f = f + beta * own
    pool, true = f[:L].astype(np.float64), float(f[L])
    prior = r['prior'].astype(np.float64)
    keep = slice(None, None, stride if r['regime'] == 0 else 1)         # a smaller pool; the deal list is never thinned
    if r['regime'] == 0:
        used = power
        while used > 1e-3 and _effective(used * pool[keep]) < min_effective:
            used /= 2
    else:
        used = power
    logw = prior[keep] + used * pool[keep]
    logw_n = logw - logw.max()
    w = np.exp(logw_n)
    pw = np.exp(prior[keep] - prior[keep].max())
    gain = used * true - (math.log((pw * np.exp(used * pool[keep] - (used * pool[keep]).max())).sum() / pw.sum()) + (used * pool[keep]).max())
    uu = u[keep]
    wn = w / w.sum()
    every = choice_cost(wn, uu, cost)
    grid = (np.arange(offsets) + .5) / offsets
    if r['regime'] == 0:
        engine = resampled_cost(w, uu, cost, solved, grid)
    else:
        engine = resampled_cost(w, uu, cost, list_solve, grid) if len(w) > list_solve else every
    # what the weights themselves expect the best single card to cost (equal to the real cost on average if they are the true odds)
    expected = float(wn @ uu.max(axis=1) - (wn @ uu).max())
    # the part of the reading that bears on this decision: the weight on layouts in which a card that is best in the true deal is best
    right = (uu[:, cost <= 1e-9].max(axis=1) >= uu.max(axis=1) - 1e-9)
    before, after = float((pw / pw.sum()) @ right), float(wn @ right)
    relevant = math.log(after / before) if before > 0 and after > 0 else float('nan')
    return gain, engine, every, used, _effective(logw), expected, relevant


def mean_se(values, families):
    v = np.asarray(values, float)
    _, inv = np.unique(families, return_inverse=True)
    totals, counts = np.bincount(inv, v), np.bincount(inv)
    mean, k = totals.sum() / counts.sum(), len(counts)
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * k / (k - 1)) / counts.sum() if k > 1 else float('nan')
    return float(mean), float(se)


def read_all(out):
    rows, names = [], None
    for part in sorted(Path(out).glob('pools-*-*.npz')):
        got, _, n = load(part)
        for extra in sorted(Path(out).glob(part.name.replace('pools-', 'fit-*-'))):
            name = extra.name[len('fit-'):-len(part.name[len('pools'):])]
            with np.load(extra) as z:
                flat, at = z['fit'], 0
            for r in got:
                size = 3 * (int(r['layouts']) + 1)
                r['fit'][name] = flat[at:at + size].reshape(3, -1)
                at += size
            n = n + [name]
        own = Path(out) / part.name.replace('pools-', 'own-')
        if own.exists():
            with np.load(own) as z:
                flat = {k[4:]: z[k] for k in z.files}
            at = 0
            for r in got:
                size = int(r['layouts']) + 1
                r['own'] = {k: v[at:at + size] for k, v in flat.items()}
                at += size
        uns = Path(out) / part.name.replace('pools-', 'uns-')
        if uns.exists():
            with np.load(uns) as z:
                flat, who = z['cards'], z['controller']
            at = 0
            for r, c in zip(got, who):
                r['cards'] = flat[at:at + int(r['unseen'])]
                r['controller'] = int(c)
                at += int(r['unseen'])
        for r in got:
            r['uid'] = (part.name, int(r['table']))
        rows += got
        names = n if names is None else [x for x in names if x in n]
    return rows, names or []


def weights_of(r, fit, power=1., min_effective=8.):
    """Normalised weights of the stored layouts under a reading (as score() makes them), and under no reading."""
    L = int(r['layouts'])
    pool = (fit[0] + fit[1] + fit[2])[:L].astype(np.float64)
    prior = r['prior'].astype(np.float64)
    used = power
    if r['regime'] == 0:
        while used > 1e-3 and _effective(used * pool) < min_effective:
            used /= 2
    logw = prior + used * pool
    w, pw = np.exp(logw - logw.max()), np.exp(prior - prior.max())
    return w / w.sum(), pw / pw.sum()


def mechanism(a):
    """Where a net's information sits (honours or small cards), and what information aimed at the true deal would be worth."""
    rows, names = read_all(a.out)
    rows = [r for r in rows if 'cards' in r and (r['hidden_house'] or not a.house)]
    fam = np.array([r['family'] for r in rows])
    regime = np.array([int(r['regime']) for r in rows])
    trick = np.array([int(r['trick']) for r in rows])
    declaring = np.array([bool(r['declaring']) for r in rows])
    tables_n = len({r['uid'] for r in rows})
    print(f"{len(rows)} decisions on {tables_n} tables of {len(set(fam))} deals; nets {names}")
    result = dict(decisions=len(rows), tables=tables_n, nets=names, cards={}, directed={})
    # 1. per unseen card: the weight on the layouts that give the card to its true holder, as a log-score, against no reading
    print("\n== the true holder of an unseen card: mean log-probability under the weights (cards either hidden hand could hold; 0 is certainty, -0.693 a coin toss)")
    kinds = (('honours (T to A)', lambda c: c % 13 >= 8), ('small cards', lambda c: c % 13 < 8))
    for band in ('before the deal list', 'deal list'):
        m = regime == (0 if band == 'before the deal list' else 1)
        if m.sum() < 30:
            continue
        for label, pick in kinds:
            line, entry = [], {}
            for n in ['no reading'] + names:
                per, fams = [], []
                for r, f in zip([rows[i] for i in np.flatnonzero(m)], fam[m]):
                    w, pw = weights_of(r, r['fit'][n]) if n != 'no reading' else (None, None)
                    if n == 'no reading':
                        _, pw = weights_of(r, r['fit'][names[0]])
                        w = pw
                    right = (r['assign'] == r['truth'][None, :])                       # [L, U]
                    prior_p = weights_of(r, r['fit'][names[0]])[1] @ right
                    free = (prior_p > 1e-6) & (prior_p < 1 - 1e-6) & np.array([pick(int(c)) for c in r['cards']])
                    if free.any():
                        per.append(float(np.log(np.clip(w @ right, 1e-6, 1.))[free].mean()))
                        fams.append(f)
                e = mean_se(per, np.array(fams))
                entry[n] = e
                line.append(f"{n} {e[0]:+.4f} +- {e[1]:.4f}")
            result['cards'][f'{band} | {label}'] = entry
            print(f"  {band:21s} {label:17s} " + ' | '.join(line))
    # 2. information aimed at the true deal: every layout's log-weight raised by kappa for each card (of a kind) it gives to its true holder
    base = np.array([score(r, np.zeros((3, int(r['layouts']) + 1), np.float32), 0.)[1] for r in rows])
    print("\n== information aimed at the true deal: log-weight + kappa x (cards given to their true holder); the true layout's gain in nats, tricks saved a table")
    share = len(rows) / tables_n
    for label, pick in (('every unseen card', lambda c: True), *kinds):
        line = []
        for kappa in (.125, .25, .5, 1., 2.):
            out = []
            for r in rows:
                sel = np.array([pick(int(c)) for c in r['cards']])
                match = (r['assign'][:, sel] == r['truth'][None, sel]).sum(axis=1).astype(np.float32)
                fit = np.zeros((3, int(r['layouts']) + 1), np.float32)
                fit[0, :-1], fit[0, -1] = match, sel.sum()
                out.append(score(r, fit, power=kappa, min_effective=1.)[:2])
            out = np.array(out)
            g, sv = mean_se(out[:, 0], fam), mean_se(base - out[:, 1], fam)
            result['directed'][f'{label} | {kappa}'] = dict(nats=g, saved_a_table=[sv[0] * share, sv[1] * share])
            line.append(f"k {kappa:g}: {g[0]:+.2f} nats, {sv[0] * share:+.3f} +- {sv[1] * share:.3f}")
        print(f"  {label:17s} " + ' | '.join(line))
    print("\n== the nets, as built, for comparison")
    for n in names:
        sc = np.array([score(r, r['fit'][n], power=1.)[:2] for r in rows])
        g, sv = mean_se(sc[:, 0], fam), mean_se(base - sc[:, 1], fam)
        result['directed'][f'net | {n}'] = dict(nats=g, saved_a_table=[sv[0] * share, sv[1] * share])
        print(f"  {n:8s} {g[0]:+.2f} nats, {sv[0] * share:+.3f} +- {sv[1] * share:.3f} tricks a table")
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1))


def aimed(a):
    """A net's reading plus information aimed at the true deal, as the Gen 9 session's E9-0 plays it (box/coordination, 12 Nov
    2026, 12:03 UTC): each layout's weight times exp(-near x misplaced cards), a misplaced card counting 0.5 (2 to 9), 1 (T),
    1.5 (J), 2 (Q), 3 (K), 4 (A). near is set so that the true layout gains a target number of nats a decision on top of the
    net's reading, over all decisions. Printed: what the proxy expects each setting to add to the net's reading, paired."""
    rows, names = read_all(a.out)
    rows = [r for r in rows if 'cards' in r]
    net = a.against or 'v4'
    worth = np.array([.5] * 8 + [1., 1.5, 2., 3., 4.])
    fam = np.array([r['family'] for r in rows])
    trick = np.array([int(r['trick']) for r in rows])
    tables_n = len({r['uid'] for r in rows})
    share = len(rows) / tables_n
    base, miss, prior = [], [], []
    for r in rows:
        w = worth[r['cards'].astype(np.int64) % 13]
        m = ((r['assign'] != r['truth'][None, :]) * w[None, :]).sum(axis=1)
        miss.append(np.concatenate([m, [0.]]))
        base.append(r['fit'][net].sum(axis=0).astype(np.float64))
        pw = np.exp(r['prior'].astype(np.float64) - r['prior'].max())
        prior.append(pw / pw.sum())

    def gain(i, x):
        top = x[:-1].max()
        return x[-1] - (math.log(float(prior[i] @ np.exp(x[:-1] - top))) + top)
    plain = np.array([gain(i, base[i]) for i in range(len(rows))])

    def extra(near, mask):
        return float(np.mean([gain(i, base[i] - near * miss[i]) - plain[i] for i in np.flatnonzero(mask)]))

    def alone(near, mask):
        """The true layout's gain from the aim with no play reading (the Gen 9 session's measure of a setting's nats)."""
        return float(np.mean([gain(i, -near * miss[i]) for i in np.flatnonzero(mask)]))
    everywhere = np.ones(len(rows), bool)
    declaring = np.array([bool(r['declaring']) for r in rows])
    nears = {}
    for target in a.aim:
        lo, hi = 0., 8.
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if extra(mid, everywhere) < target else (lo, mid)
        nears[target] = (lo + hi) / 2
    stack = lambda x: np.stack([x, np.zeros_like(x), np.zeros_like(x)]).astype(np.float32)
    none = np.array([score(r, np.zeros((3, int(r['layouts']) + 1), np.float32), 0.)[1] for r in rows])
    read = np.array([score(r, stack(base[i]), power=1., min_effective=1.)[1] for i, r in enumerate(rows)])
    b = mean_se(none - read, fam)
    print(f"{len(rows)} decisions on {tables_n} tables of {len(set(fam))} deals; the reading is {net}'s: +{b[0] * share:.3f} +- {b[1] * share:.3f} tricks a board against no reading;"
          f" the true layout gains {plain.mean():+.2f} nats from it")
    result = dict(net=net, decisions=len(rows), tables=tables_n, settings={})
    settings = [(f'+{t:g} nats, every decision', nears[t], everywhere) for t in a.aim] + [(f'near {x:g}, every decision', x, everywhere) for x in a.near]
    split = a.near_split if a.near_split is not None else (nears[a.aim[0]] if a.aim else a.near[0])
    settings += [(f'near {split:.3g}, tricks 1 to 6 only', split, trick <= 6), (f'near {split:.3g}, from trick 7 only', split, trick >= 7),
                 (f'near {split:.3g}, declarer only', split, declaring), (f'near {split:.3g}, defenders only', split, ~declaring)]
    for label, near, mask in settings:
        cost = read.copy()
        for i in np.flatnonzero(mask):
            cost[i] = score(rows[i], stack(base[i] - near * miss[i]), power=1., min_effective=1.)[1]
        d = mean_se(read - cost, fam)
        nats, before = extra(near, mask), alone(near, mask)
        result['settings'][label] = dict(near=near, helped=int(mask.sum()), nats_a_helped_decision=nats, nats_without_the_reading=before,
                                         tricks_a_board_over_reading=[d[0] * share, d[1] * share])
        print(f"  {label:34s} near {near:.3f} | {int(mask.sum()):6d} decisions helped, {nats:+.2f} nats each on top of the reading ({before:+.2f} without it)"
              f" | over the reading {d[0] * share:+.3f} +- {d[1] * share:.3f} tricks a board")
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1))


def list_only(a):
    """The reading from the deal list alone, which is all a bot without the early read (the Gen 7 bot) reads: tricks saved a
    table by exponent and net, then each exponent against the first one given and each net against --against, paired on the
    same decisions."""
    rows, names = read_all(a.out)
    if a.house:
        rows = [r for r in rows if r['hidden_house']]
    tables_n = len({r['uid'] for r in rows})
    rows = [r for r in rows if int(r['regime']) == 1]
    fam = np.array([r['family'] for r in rows])
    share = len(rows) / tables_n
    powers = list(a.list_exponents)
    base = np.array([score(r, r['fit'][names[0]], 0.)[1] for r in rows])
    cost = {(n, p): np.array([score(r, r['fit'][n], p)[1] for r in rows]) for n in names for p in powers}
    result = dict(decisions=len(rows), tables=tables_n, deals=len(set(fam.tolist())), nets=names, exponents=powers, rows=[])

    def line(name, v):
        m, se = mean_se(v, fam)
        result['rows'].append(dict(name=name, tricks_a_table=[m * share, se * share]))
        print(f"  {name:46s} {m * share:+.4f} +- {se * share:.4f}")
    print(f"{len(rows)} decisions from the deal list on, on {tables_n} tables of {result['deals']} deals; tricks saved a table")
    print('\n== against no reading')
    for n in names:
        for p in powers:
            line(f'{n} at {p:g}', base - cost[(n, p)])
    print(f'\n== each exponent against {powers[0]:g}, same net, same decisions')
    for n in names:
        for p in powers[1:]:
            line(f'{n}: {p:g} minus {powers[0]:g}', cost[(n, powers[0])] - cost[(n, p)])
    ref = a.against or names[0]
    print(f'\n== each net against {ref}, same exponent, same decisions')
    for n in names:
        for p in powers if n != ref else ():
            line(f'{n} minus {ref} at {p:g}', cost[(ref, p)] - cost[(n, p)])
    print(f'\n== each net and exponent against {ref} at {powers[0]:g}, same decisions')
    for n in names:
        for p in powers:
            if (n, p) != (ref, powers[0]):
                line(f'{n} at {p:g} minus {ref} at {powers[0]:g}', cost[(ref, powers[0])] - cost[(n, p)])
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1))


def by_opponent(a):
    """What reading the opponents' plays is worth by who the opponents were (the bot recorded at the seats against the
    decider's): their plays alone at each weight against no reading; the same on top of partner read in full, which is how
    the engine scales a reading by opponent; the last weight given against each lower one; and with --net NAME, the
    --against net against that one as the reader. Tricks for the side doing the reading, a board being that side's
    decisions at two tables; a stage's figure counts its own decisions only, so the stages add up."""
    rows, names = read_all(a.out)
    rows = [r for r in rows if 'controller' in r and r.get('bots')]
    net = a.against or names[0]
    others = [n for n in a.net if n in names and n != net]
    W = list(a.opponent_weights)
    kind = lambda x: 'BEN' if str(x).startswith('ben') else str(x)
    fam = np.array([r['family'] for r in rows])
    own = np.array([kind(r['bots'][r['controller']]) for r in rows])
    opp = np.array([kind(r['bots'][(r['controller'] + 1) % 4]) for r in rows])
    unit = np.array([f"{r['uid'][0]}:{r['uid'][1]}:{r['controller'] % 2}" for r in rows])
    regime = np.array([int(r['regime']) for r in rows])
    cost = {k: np.zeros(len(rows)) for k in ['none', 'partner'] + [(x, w) for x in ('alone', 'with') for w in W] + [('alone', n) for n in others]}
    for j, r in enumerate(rows):
        d, f = bool(r['declaring']), r['fit'][net]
        cost['none'][j] = score(r, f, 0.)[1]
        cost['partner'][j] = score(r, f, 1., parts=(0. if d else 1., 1., 0.))[1]
        for w in W:                                 # the lead is the opponents' when the decider is on declarer's side
            cost[('alone', w)][j] = score(r, f, 1., parts=(w if d else 0., 0., w))[1]
            cost[('with', w)][j] = score(r, f, 1., parts=(w if d else 1., 1., w))[1]
        for n in others:
            cost[('alone', n)][j] = score(r, r['fit'][n], 1., parts=(W[-1] if d else 0., 0., W[-1]))[1]
    groups = [(t, opp == t) for t, _ in sorted(((t, -int((opp == t).sum())) for t in set(opp.tolist())), key=lambda x: x[1])]
    groups += [(f'{t} facing {o}', (opp == t) & (own == o)) for t, _ in list(groups) for o in sorted(set(own[opp == t].tolist())) if len(set(own[opp == t].tolist())) > 1]
    groups.append(('everyone', np.ones(len(rows), bool)))
    result = dict(net=net, weights=W, decisions=len(rows), groups={})
    show = lambda v: f"{v[0]:+.3f} +- {v[1]:.3f}"
    print(f"{len(rows)} decisions; the reader is {net}; tricks a board for the side reading (its decisions at two tables)")
    for stage, m0 in (('every decision', np.ones(len(rows), bool)), ('before the deal list', regime == 0), ('from the deal list', regime == 1)):
        print(f"\n=== {stage}")
        for name, g in groups:
            if g.sum() < 200:
                continue
            units = len(set(unit[g].tolist()))
            scale = g.sum() / units * 2

            def saved(x, y):
                mean, se = mean_se(np.where(m0, cost[x] - cost[y], 0.)[g], fam[g])
                return mean * scale, se * scale
            entry = dict(side_tables=units, decisions=int((g & m0).sum()),
                         alone={w: saved('none', ('alone', w)) for w in W}, on_partner={w: saved('partner', ('with', w)) for w in W},
                         last_over={w: saved(('with', w), ('with', W[-1])) for w in W[:-1]},
                         reader_over={n: saved(('alone', n), ('alone', W[-1])) for n in others})
            result['groups'][f'{stage} | {name}'] = entry
            print(f"{name:24s} {units:4d} side-tables, {entry['decisions']:6d} decisions")
            print('    their plays alone against no reading:  ' + ' | '.join(f"w {w:g}: {show(entry['alone'][w])}" for w in W))
            print('    on top of partner read in full:        ' + ' | '.join(f"w {w:g}: {show(entry['on_partner'][w])}" for w in W))
            print(f"    weight {W[-1]:g} over a lower one, the same:   " + ' | '.join(f"over {w:g}: {show(entry['last_over'][w])}" for w in W[:-1]))
            for n in others:
                print(f"    {net} over {n} as the reader, their plays alone at {W[-1]:g}: {show(entry['reader_over'][n])}")
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1, default=lambda o: {str(k): v for k, v in o.items()} if isinstance(o, dict) else str(o)))


def honours_on_top(a):
    """Information aimed at the honours on top of a net's reading: k added to a layout's log-weight for every honour (T to
    A) it gives to its true holder, the same k at every decision. Per k: the mechanism table's measure of an unseen
    honour (mean log-probability of its true holder) by stage, the true layout's gain in nats over the reading, and tricks
    saved a table over the reading, in all and by where it is applied."""
    rows, names = read_all(a.out)
    rows = [r for r in rows if 'cards' in r and (r['hidden_house'] or not a.house)]
    net = a.against or 'v4'
    K = [0.] + [k for k in a.honours if k]
    fam = np.array([r['family'] for r in rows])
    trick = np.array([int(r['trick']) for r in rows])
    regime = np.array([int(r['regime']) for r in rows])
    tables_n = len({r['uid'] for r in rows})
    cost, gain = np.zeros((len(K), len(rows))), np.zeros((len(K), len(rows)))
    hon, bare = np.full((len(K), len(rows)), np.nan), np.full(len(rows), np.nan)
    for j, r in enumerate(rows):
        sel = np.array([int(c) % 13 >= 8 for c in r['cards']])
        right = (r['assign'] == r['truth'][None, :])
        match = np.concatenate([right[:, sel].sum(axis=1), [sel.sum()]]).astype(np.float32)
        f = r['fit'][net]
        prior_p = weights_of(r, f)[1] @ right
        free = (prior_p > 1e-6) & (prior_p < 1 - 1e-6) & sel
        if free.any():
            bare[j] = float(np.log(np.clip(prior_p, 1e-6, 1.))[free].mean())
        for i, k in enumerate(K):
            gain[i, j], cost[i, j] = score(r, f, 1., own=match, beta=k)[:2]
            if free.any():
                g = np.zeros((3, int(r['layouts']) + 1), np.float32)
                g[0] = f[0] + f[1] + f[2] + k * match
                hon[i, j] = float(np.log(np.clip(weights_of(r, g)[0] @ right, 1e-6, 1.))[free].mean())
    stages = (('trick 6', trick == 6), ('tricks 5-6', (trick >= 5) & (trick <= 6)), ('before the deal list', regime == 0), ('deal list', regime == 1),
              ('all', np.ones(len(rows), bool)))

    def level(v, m):
        ok = m & ~np.isnan(v)
        return mean_se(v[ok], fam[ok])
    share = len(rows) / tables_n
    result = dict(net=net, decisions=len(rows), tables=tables_n, no_reading={n: level(bare, m) for n, m in stages}, rows=[])
    print(f"{len(rows)} decisions on {tables_n} tables; {net}'s reading plus k for every honour a layout gives to its true holder")
    print('an unseen honour with no reading: ' + '; '.join(f"{n} {level(bare, m)[0]:+.3f}" for n, m in stages))
    for i, k in enumerate(K):
        row = dict(k=k, honours={n: level(hon[i], m) for n, m in stages}, nats_over_reading=mean_se(gain[i] - gain[0], fam), tricks={})
        text = [f"k {k:5.3f} | an unseen honour: " + '; '.join(f"{n} {row['honours'][n][0]:+.3f}" for n, _ in stages) + f" | nats over the reading {row['nats_over_reading'][0]:+.2f}"]
        for n, m in (('at every decision', np.ones(len(rows), bool)), ('tricks 1-6 only', trick <= 6), ('from trick 7 only', trick >= 7)):
            v = mean_se(np.where(m, cost[0] - cost[i], 0.), fam)
            row['tricks'][n] = [v[0] * share, v[1] * share]
            text.append(f"{n} {v[0] * share:+.3f} +- {v[1] * share:.3f}")
        result['rows'].append(row)
        print(' | '.join(text))
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1))


def report(a):
    if a.opponent_weights:
        return by_opponent(a)
    if a.honours:
        return honours_on_top(a)
    if a.list_exponents:
        return list_only(a)
    if a.mechanism:
        return mechanism(a)
    if a.aim or a.near:
        return aimed(a)
    rows, names = read_all(a.out)
    if a.house:
        rows = [r for r in rows if r['hidden_house']]
    fam = np.array([r['family'] for r in rows])
    trick = np.array([int(r['trick']) for r in rows])
    regime = np.array([int(r['regime']) for r in rows])
    declaring = np.array([bool(r['declaring']) for r in rows])
    tables_n = len({r['uid'] for r in rows})
    print(f"{len(rows)} decisions on {tables_n} tables of {len(set(fam))} deals; nets {names}; mean layouts {np.mean([r['layouts'] for r in rows]):.0f};"
          f" before the deal list {int((regime == 0).sum())}, deal list {int((regime == 1).sum())}")
    zero = np.zeros((3, 1), np.float32)
    settings = [('as built', dict(power=1.))]
    if a.sweep:
        settings += [('exponent 0.25', dict(power=.25)), ('exponent 0.5', dict(power=.5)), ('exponent 0.75', dict(power=.75)),
                     ('exponent 1.5', dict(power=1.5)), ('exponent 2', dict(power=2.)), ('exponent 3', dict(power=3.)),
                     ('no halving', dict(power=1., min_effective=1.)), ('halving below 32', dict(power=1., min_effective=32.)),
                     ('128 solved', dict(power=1., solved=128)), ('pool 128', dict(power=1., stride=4)), ('pool 256', dict(power=1., stride=2)),
                     ('no lead', dict(power=1., parts=(0., 1., 1.))), ('lead only', dict(power=1., parts=(1., 0., 0.))),
                     ('partner only', dict(power=1., parts=(0., 1., 0.))), ('opponents only', dict(power=1., parts=(0., 0., 1.)))]
    if a.owner:
        rows = [r for r in rows if 'own' in r]
        fam, trick = np.array([r['family'] for r in rows]), np.array([int(r['trick']) for r in rows])
        regime, declaring = np.array([int(r['regime']) for r in rows]), np.array([bool(r['declaring']) for r in rows])
        tables_n = len({r['uid'] for r in rows})
        names = [n for n in names if all(n in r['own'] for r in rows)]
        print(f"with the owner head: {len(rows)} decisions on {tables_n} tables; nets {names}")
        settings = [('as built', dict(power=1.))]
        for beta in a.owner:
            settings += [(f'owner x{beta:g} alone', dict(power=1., parts=(0., 0., 0.), beta=beta)), (f'reading + owner x{beta:g}', dict(power=1., beta=beta))]
    base_all = np.array([score(r, np.zeros((3, int(r['layouts']) + 1), np.float32), 0.) for r in rows])
    base = base_all[:, 1:3]                                                                                     # no reading: engine way, every layout
    b32, ball, bexp = mean_se(base[:, 0], fam), mean_se(base[:, 1], fam), mean_se(base_all[:, 5], fam)
    print(f"no reading: cost {b32[0]:.4f} +- {b32[1]:.4f} a decision with 32 layouts solved (deal list: up to 256), {ball[0]:.4f} +- {ball[1]:.4f} with every stored layout;"
          f" the weights themselves expect {bexp[0]:.4f} +- {bexp[1]:.4f}")
    result = dict(decisions=len(rows), tables=tables_n, deals=len(set(fam)), nets=names, groups={})
    per_table = len(rows) / tables_n
    for label, kw in ([] if a.pairs_only else settings):
        for n in names:
            s = np.array([score(r, r['fit'][n], **dict(kw, own=r['own'][n] if kw.get('beta') else None)) for r in rows])
            entry = {}
            for band in BANDS:
                m = band_mask(band, trick, regime, declaring)
                if m.sum() < 30:
                    continue
                g = mean_se(s[m, 0], fam[m])
                saved_e, saved_a = mean_se(base[m, 0] - s[m, 1], fam[m]), mean_se(base[m, 1] - s[m, 2], fam[m])
                share = m.sum() / tables_n          # decisions of this band in a table, all four seats
                ok = m & np.isfinite(s[:, 6])
                entry[band] = dict(decisions=int(m.sum()), log_weight_gain=g, cost_no_reading=mean_se(base[m, 0], fam[m]), cost=mean_se(s[m, 1], fam[m]),
                                   saved=saved_e, saved_every_layout=saved_a, saved_a_table=[saved_e[0] * share, saved_e[1] * share],
                                   exponent=float(s[m, 3].mean()), effective=float(np.median(s[m, 4])),
                                   cost_every_layout=mean_se(s[m, 2], fam[m]), cost_expected_by_weights=mean_se(s[m, 5], fam[m]),
                                   relevant_log_weight_gain=mean_se(s[ok, 6], fam[ok]) if ok.sum() > 1 else None)
            result['groups'][f'{label} | {n}'] = entry
            if label == 'as built' or a.verbose or a.owner:
                print(f"\n== {label}, {n}")
                for band, e in entry.items():
                    print(f"  {band:21s} {e['decisions']:6d} decisions | true layout's log-weight {e['log_weight_gain'][0]:+.3f} +- {e['log_weight_gain'][1]:.3f}"
                          f" | cost without {e['cost_no_reading'][0]:.4f}, with {e['cost'][0]:.4f} | saved {e['saved'][0]:+.4f} +- {e['saved'][1]:.4f} a decision,"
                          f" {e['saved_a_table'][0]:+.3f} +- {e['saved_a_table'][1]:.3f} a table | every layout {e['saved_every_layout'][0]:+.4f} +- {e['saved_every_layout'][1]:.4f}"
                          f" | exponent {e['exponent']:.2f}, effective {e['effective']:.0f}"
                          f" | every layout costs {e['cost_every_layout'][0]:.4f}, its weights expect {e['cost_expected_by_weights'][0]:.4f} +- {e['cost_expected_by_weights'][1]:.4f}"
                          + (f" | weight on layouts where the true best card is best: log gain {e['relevant_log_weight_gain'][0]:+.3f} +- {e['relevant_log_weight_gain'][1]:.3f}" if e['relevant_log_weight_gain'] else ''))
    # nets against the first, paired
    if a.against and a.against in names:
        names = [a.against] + [n for n in names if n != a.against]
    if len(names) > 1:
        print(f"\n== each net against {names[0]}, as built, paired on the same decisions (tricks saved a decision; positive = better than {names[0]})")
        first = np.array([score(r, r['fit'][names[0]], power=1.) for r in rows])
        for n in names[1:]:
            s = np.array([score(r, r['fit'][n], power=1.) for r in rows])
            for band in BANDS:
                m = band_mask(band, trick, regime, declaring)
                if m.sum() < 30:
                    continue
                d, g = mean_se(first[m, 1] - s[m, 1], fam[m]), mean_se(s[m, 0] - first[m, 0], fam[m])
                dall = mean_se(first[m, 2] - s[m, 2], fam[m])
                share = m.sum() / tables_n
                result['groups'].setdefault(f'paired | {n}', {})[band] = dict(saved_more=d, log_weight_more=g, saved_more_every_layout=dall, a_table=[d[0] * share, d[1] * share])
                print(f"  {n:8s} {band:21s} log-weight {g[0]:+.3f} +- {g[1]:.3f} | saved {d[0]:+.5f} +- {d[1]:.5f} a decision, {d[0] * share:+.4f} +- {d[1] * share:.4f} a table"
                      f" | every layout {dall[0]:+.5f} +- {dall[1]:.5f}")
    if a.sweep or a.owner:
        print('\n== settings, all tricks: tricks saved a table (engine way) by net')
        for label, _ in settings:
            line = []
            for n in names:
                e = result['groups'][f'{label} | {n}'].get('all')
                line.append(f"{n} {e['saved_a_table'][0]:+.3f}+-{e['saved_a_table'][1]:.3f} (lw {e['log_weight_gain'][0]:+.2f})")
            print(f"  {label:18s} " + ' | '.join(line))
    print(f"\n(a table has {per_table:.1f} such decisions over its four seats; one side of one table is half of the per-table figure)")
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=('pools', 'fits', 'floors', 'owners', 'cards', 'report'))
    ap.add_argument('--episodes', action='append', default=[])
    ap.add_argument('--out', required=True)
    ap.add_argument('--net', action='append', default=[])
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--tables', type=int, default=10 ** 9)
    ap.add_argument('--seconds', type=float, default=1e9)
    ap.add_argument('--part', type=int, default=4, help='tables per part file')
    ap.add_argument('--skip-tables', type=int, default=0, help="pools: leave out this many of the shard's first tables (a run continued)")
    ap.add_argument('--part-offset', type=int, default=0, help='pools: number of the first part file written (a run continued)')
    ap.add_argument('--pool', type=int, default=512)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--skip-families', action='append', default=[], help='a built set whose deals are left out')
    ap.add_argument('--house', action='store_true', help='report: only decisions whose hidden seats were played by house bots')
    ap.add_argument('--sweep', action='store_true', help='report: other settings on the same solves')
    ap.add_argument('--owner', type=float, action='append', default=[], help='report: add this many times the owner head\'s log-probability (repeatable)')
    ap.add_argument('--redo', action='store_true', help='cards: write the files again')
    ap.add_argument('--near', type=float, action='append', default=[], help='report: the same with near given (repeatable)')
    ap.add_argument('--near-split', type=float, help='report: the near used for the tricks 1-6, trick 7 on, declarer and defender settings')
    ap.add_argument('--aim', type=float, action='append', default=[], help='report: nats of information aimed at the true deal, on top of the --against net (default v4)')
    ap.add_argument('--against', help='report: the net the others are paired against (default: the first)')
    ap.add_argument('--pairs-only', action='store_true', help='report: only the paired comparison')
    ap.add_argument('--mechanism', action='store_true', help='report: where the information sits and what directed information is worth')
    ap.add_argument('--opponent-weights', type=float, nargs='+', default=[], help="report: the opponents' plays at these weights, by who the opponents were; reader --against, compared with --net NAME")
    ap.add_argument('--honours', type=float, nargs='+', default=[], help='report: information aimed at the honours at these strengths, on top of the --against net (default v4)')
    ap.add_argument('--list-exponents', type=float, nargs='+', default=[], help='report: the deal list alone at these exponents, by net; each against the first, and each net against --against')
    ap.add_argument('--floor', type=float, action='append', default=[], help='floors: a floor to compute the fits at (repeatable)')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--json')
    a = ap.parse_args()
    {'pools': pools, 'fits': fits, 'floors': floors, 'owners': owners, 'cards': cards, 'report': report}[a.step](a)


if __name__ == '__main__':
    main()
