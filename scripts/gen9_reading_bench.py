#!/usr/bin/env python3
"""G9-X2: Gen 9 readers on p41's reading bench, scored in double-dummy tricks saved on the true deal, with nats beside.

Gen 9 work in progress (sam, signals). scripts/gen8_reading_bench.py (a snapshot of p41's bench, cdde42a) does the solving and the
scoring; this script chooses the tables and decisions and adds Gen 9 readings to the stored pools.

  python scripts/gen9_reading_bench.py pools    --feeds DIR... --opponent ben --tables 300 --out OUT [--seconds 7200] [--pool 512]
  python scripts/gen9_reading_bench.py readings --feeds DIR... --out OUT --source CAPSULE/recovery --bots BOTS.json --reading NAME=BOT [...]
  python scripts/gen9_reading_bench.py relabel  --episodes DIR --cell std-80 --tables 300 --out OUT    (E9-4 part 1's tables)
  python scripts/gen9_reading_bench.py pools    --episodes OUT/episodes --deciders declarer --out OUT ...
  python scripts/gen9_reading_bench.py report   --out OUT [--against NAME] [--json FILE]       (the bench's report)
  python scripts/gen9_reading_bench.py box      --opponent ben --first 60 --tables 240 --workers 8 --feeds-dir DIR --out OUT
                                                --source CAPSULE/recovery --reading NAME=BOT [...]     (a box job: all of it)

pools     The bench's `pools` on E9-7's held-out tables against one BEN version (scripts/gen9_ben_reading.py: deal families
          with crc32 % 5 == 0, the first --tables of them in that script's order), at the decisions of the house bots only:
          BEN's own decisions say nothing about how a house bot reads. --net (default: Gen 8's net v4) is stored as the bench
          stores a net, unfactored.
relabel   E9-4 part 1's tables (scripts/gen9_reading_gain.py: the first --tables main tables of --episodes, in its order),
          the defenders' spots and opening leads drawn again by a declared scheme at an honesty (--cell, e.g. std-80) with
          that script's seeds, so the plays are the ones E9-4 part 1 scored. Written as one-table episodes under OUT/episodes.
          `pools --episodes OUT/episodes` then takes every table there, and `--deciders declarer` only declarer's decisions
          (where a reader of the defenders' cards decides).
readings  (On an --out folder without tables.json, such as p41's published house pools, the boards and cards are read from
          its tab-<part>.json.gz files and every decision is kept.) For every stored decision, the log weight a bot spec from --bots (built on the --source capsule's bots, as
          scripts/gen9_match.py builds it) gives each stored layout and the true one, after meet(the table's opponent), from
          the decider's view. Stored as the bench stores a net (fit-NAME-<part>.npz, split into the opening lead, partner's
          other plays and the opponents'), with the bot's own factors and signal terms already in it, so the bench's report
          scores it at exponent 1 like a net. Nothing is solved again. NAME=BOT@ID meets ID in place of the table's opponent.
          --head-reading NAME=HEADS.json:VERSION:HEAD:FACTOR is --head-base (8x-32) with the opposing declarer's plays read by
          an E9-14 head (scripts/gen9_play_head.py's heads.json, role ben.declarer) at FACTOR in place of the net at 0.3;
          HEAD written defender:NAME or both:NAME also reads the opposing defenders' classes by the ben.defender head, on
          --expert-base (r9b-32), whose signal model keeps the spots.
          --expert-reading NAME=MODELS.json:VERSION:SIZE:MODEL is --expert-base (r9b-32) with the opposing defenders' spots,
          wherever bridge_harness.signal_expert finds an occasion, read by an E9-15 model (m1, m2 or m3 of
          scripts/gen9_signal_expert.py's models.json; MODEL-first reads first rounds only) in place of its emission table;
          its class term is unchanged.
report    The bench's report on OUT; `--against` pairs every reading with one.
box       For a box job: fetch the version's BEN feeds into --feeds-dir (sparse clones of their episodes) if they are not
          there, run `pools` in --workers shards on tables [--first, --first + --tables) of the held-out list, then
          `readings`. progress.jsonl gets a line a table saved. Restarted (a preemptible job), each shard carries on after
          the tables its part files hold.

Hidden hands are labels: the true deal is solved and scored, never read.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness import gen9  # noqa: E402
from bridge_harness.core import symbol  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen7 import hidden_plays  # noqa: E402
from bridge_harness.signals import SPOT, SPOT_MASK  # noqa: E402
from gen9_ben_reading import ben_tables  # noqa: E402

_spec = importlib.util.spec_from_file_location('gen8_reading_bench', ROOT / 'scripts' / 'gen8_reading_bench.py')
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

GEN8_NET = 'v4=models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz'
PATH_KEYS = ('gen7_policy', 'scorer', 'bidding', 'lead_belief', 'system_scorer')


def held_out(feeds, opponent, n):
    """E9-7's first n held-out tables against `opponent`, as (episode path, table key)."""
    return [(p, k) for p, k, ben, held in ben_tables(feeds) if ben == opponent and held][:n]


def kept(decisions, deciders):
    """The bench's decisions, kept where `deciders` decide: 'house' (the episode's candidate side: against BEN, the house
    bots), 'declarer', or 'all'."""
    def wrapped(e):
        roles = e.get('assignments')
        for k, o, game in decisions(e):
            if deciders == 'all' or (deciders == 'house' and roles[o.controller] != 'opponent') \
                    or (deciders == 'declarer' and o.controller == o.contract.declarer):
                yield k, o, game
    return wrapped


def every_table(directory):
    out = []
    for path in sorted(Path(directory).glob('*.json.gz')):
        with gzip.open(path, 'rt') as f:
            out += [(str(path), k) for k in sorted(json.load(f)['unique_tables'])]
    return out


def chosen_tables(a):
    if a.episodes:
        return every_table(a.episodes)[a.first:a.first + a.tables]
    return held_out(a.feeds, a.opponent, a.first + a.tables)[a.first:]


def table_source(chosen):
    """A replacement for the bench's `tables`: exactly the chosen tables, in order."""
    def tables(directories, skip):
        for path, key in chosen:
            with gzip.open(path, 'rt') as f:
                d = json.load(f)
            who = {'candidate': d['candidate'], 'opponent': d['opponent']}
            e = d['unique_tables'][key]
            if e.get('schema_version') != 'v4-passed-out-v1' and e['tables'][0].get('actions'):
                yield str(path), key, d['family'], [who[x] for x in e['assignments']], e
    return tables


def pools(a):
    chosen = chosen_tables(a)
    bench.tables = table_source(chosen)
    bench.decisions = kept(bench.decisions, a.deciders)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    listing = out / 'tables.json'
    if a.shard == '0/1' or not listing.exists():
        tmp = out / f'tables.json.{os.getpid()}'
        tmp.write_text(json.dumps(dict(opponent=None if a.episodes else a.opponent, deciders=a.deciders, first=a.first,
                                       tables=[[str(p), k] for p, k in chosen]), indent=0))
        tmp.replace(listing)
    args = argparse.Namespace(episodes=[], out=a.out, net=a.net or [GEN8_NET], shard=a.shard, tables=a.tables, seconds=a.seconds,
                              part=a.part, skip_tables=a.skip_tables, part_offset=a.part_offset, pool=a.pool, seed=a.seed, skip_families=[])
    bench.pools(args)


def bot_spec(source, bots_file, bot):
    """A bot of --bots on the capsule's base bot, as scripts/gen8_match.build_manifest makes it (no table opponent)."""
    old = json.loads((Path(source) / 'manifest.json').read_text())
    defined = json.loads(Path(bots_file).read_text())
    if bot not in defined:
        return deepcopy(old['bots'][bot])
    entry = dict(defined[bot])
    spec = deepcopy(old['bots'][entry.pop('base')])
    for key in PATH_KEYS:
        if key in entry:
            entry[key] = str((ROOT / entry[key]).resolve())
    entry.pop('label', None)
    if 'gen6' in entry:
        entry['gen6'] = dict(spec.get('gen6', {}), **entry['gen6'])
    spec.update(entry, id=bot)
    spec.pop('identity', None)
    return spec


def reading_parts(q, o, view, both):
    """[3, layouts] the reader's log weight of the hidden seats' plays, play by play: the opening lead, partner's other plays,
    the opponents'. A Gen 9 reader's signal part is added as its play_log_likelihood adds it (untempered: / the exponent)."""
    out = np.zeros((3, len(both)), np.float32)
    exponent = max(q.reading_exponent(o, view), 1e-6) if hasattr(q, 'reading_exponent') else 1.
    for play in hidden_plays(o, q.g7.play_lead):
        i, _, chooser = play
        if hasattr(q, 'play_log_terms'):
            net, signal = q.play_log_terms(o, view, both, [play])
            value = net + signal / exponent
        else:
            value = q.play_log_likelihood(o, view, both, [play])
        out[0 if i == 0 else 1 if chooser % 2 == o.controller % 2 else 2] += value
    return out


class HeadReading:
    """A bot's reading with an opponent's choices read by per-player heads (E9-14): the opposing declarer's cards by
    `declarer` at `factor`; the opposing defenders' classes of card by `defender` in place of the net's class term (their
    spots stay with the base's signal model, so the base must read signals: r9b-32). A head left None reads as the base."""

    def __init__(self, base, declarer=None, factor=.3, defender=None):
        from bridge_harness.play_head import policy_column
        self.base, self.declarer, self.factor, self.defender = base, declarer, factor, defender
        self.g7 = base.g7
        self.W, self.b = policy_column(base.net.params)
        self.cache = (None, {})

    def meet(self, opponent):
        self.base.meet(opponent)

    def head_log_likelihood(self, o, view, assign, play, head, K=None):
        """[layouts] the floored log-probability of the card (or, with K [layouts, 52], of its class) under a head."""
        from bridge_harness.play_head import decoder_state
        i, seat, chooser = play
        ident = (o.auction, o.dealer, o.contract)
        if self.cache[0] != ident:
            self.cache = (ident, {})
        cache = self.cache[1]
        q, f, played = self.base, self.g7.play_floor, o.history[i][1]
        held = q.held_then(o, view, assign, i, chooser)
        if K is None:
            K = np.zeros_like(held)
            K[:, played] = True
        bit = np.uint64(1) << np.arange(52, dtype=np.uint64)
        keys = list(zip((held.astype(np.uint64) @ bit).tolist(), (K.astype(np.uint64) @ bit).tolist()))
        tag = id(head)
        todo = [r for r, k in enumerate(keys) if (tag, i, k) not in cache]
        if todo:
            batch = q.play_arrays(o, i, seat, chooser, held[todo])
            legal = np.asarray(batch['legal'])
            count = legal.sum(axis=1)
            vals = np.zeros(len(todo))
            choice = np.flatnonzero(count > 1)
            if len(choice):
                d, _ = decoder_state(q.net.params, {k: batch[k][choice] for k in batch})
                members = K[np.array(todo)[choice]] & legal[choice]
                pr = (np.exp(head.log_policy(d, legal[choice], self.W, self.b)) * members).sum(axis=1)
                vals[choice] = np.log((1 - f) * pr + f * members.sum(axis=1) / count[choice])
            for j, r in enumerate(todo):
                cache[(tag, i, keys[r])] = vals[j]
        return np.array([cache[(tag, i, k)] for k in keys])

    def play_log_likelihood(self, o, view, assign, plays):
        q, c = self.base, o.contract
        out = np.zeros(len(assign))
        exponent = max(q.reading_exponent(o, view), 1e-6) if hasattr(q, 'reading_exponent') else 1.
        for play in plays:
            i, seat, chooser = play
            opponent = chooser % 2 != o.controller % 2
            if opponent and chooser == c.declarer and self.declarer is not None:
                out += self.factor * self.head_log_likelihood(o, view, assign, play, self.declarer)
                continue
            if opponent and chooser != c.declarer and self.defender is not None and getattr(q, 'opponent_signals', None) is not None:
                from gen9_play_head import class_mask
                held = q.held_then(o, view, assign, i, chooser)
                K = class_mask(o.history, i, c, held, q.opponent_signals)
                _, _, ls = q.signal_row(o, view, assign, *play, q.opponent_signals)
                out += q.opponent_phi * self.head_log_likelihood(o, view, assign, play, self.defender, K) + ls / exponent
                continue
            if hasattr(q, 'play_log_terms'):
                net, signal = q.play_log_terms(o, view, assign, [play])
                out += net + signal / exponent
            else:
                out += q.play_log_likelihood(o, view, assign, [play])
        return out


class ClassReading:
    """E9-16 part 1b: each hidden seat's play read by the net's probability of its class of equal cards, the card inside
    the class chosen evenly; `who` ('all', 'opponents' or 'partner') says whose plays are read so (the others by the
    card). Classes: 'spots' (E9-3's: the spots nine and below of the suit held, or the card itself if higher),
    'touching' (the cards of the suit held that touch the card played, honours included, two cards touching when only
    cards already played lie between them), or 'card' (the net on the card: the prototype's reading). Readings on one
    base share its net rows."""

    def __init__(self, base, kind='spots', who='all'):
        self.base, self.kind, self.who = base, kind, who
        self.g7 = base.g7

    def meet(self, opponent):
        self.base.meet(opponent)

    def probabilities(self, o, i, seat, chooser, held):
        """([n, 52] the net's probabilities, [n] legal cards) for the chooser's view at play i in each layout, cached on
        the base player for every ClassReading built on it."""
        q = self.base
        ident = (o.auction, o.dealer, o.contract)
        cache = getattr(q, '_class_reading_cache', (None, {}))
        if cache[0] != ident:
            cache = (ident, {})
            q._class_reading_cache = cache
        cache = cache[1]
        bit = np.uint64(1) << np.arange(52, dtype=np.uint64)
        keys = (held.astype(np.uint64) @ bit).tolist()
        todo = [r for r, k in enumerate(keys) if (i, k) not in cache]
        if todo:
            batch = q.play_arrays(o, i, seat, chooser, held[todo])
            legal = np.asarray(batch['legal'])
            p = np.exp(q.net.log_policy_arrays(batch).astype(np.float64)) * legal
            for j, r in enumerate(todo):
                cache[(i, keys[r])] = (p[j], int(legal[j].sum()))
        got = [cache[(i, k)] for k in keys]
        return np.stack([g[0] for g in got]), np.array([g[1] for g in got])

    def klass(self, o, i, held):
        played = o.history[i][1]
        suit, rank = played // 13, played % 13
        K = np.zeros_like(held)
        if self.kind == 'spots':
            if rank <= SPOT:
                K = held & SPOT_MASK[suit][None, :]
            else:
                K[:, played] = True
            return K
        gone = np.zeros(13, bool)                                   # this suit's cards played before this one
        gone[[x % 13 for _, x in o.history[:i] if x // 13 == suit]] = True
        mine = held[:, suit * 13:suit * 13 + 13]
        ok = mine | gone[None, :]
        out = np.zeros_like(mine)
        out[:, rank] = True
        if rank < 12:                                               # upward: every rank between is held or gone
            run = np.cumprod(ok[:, rank + 1:], axis=1).astype(bool)
            out[:, rank + 1:] = run & mine[:, rank + 1:]
        if rank > 0:
            run = np.cumprod(ok[:, :rank][:, ::-1], axis=1).astype(bool)[:, ::-1]
            out[:, :rank] = run & mine[:, :rank]
        K[:, suit * 13:suit * 13 + 13] = out
        return K

    def play_log_likelihood(self, o, view, assign, plays):
        q, f = self.base, self.g7.play_floor
        out = np.zeros(len(assign))
        for play in plays:
            i, seat, chooser = play
            partner = chooser % 2 == o.controller % 2
            held = q.held_then(o, view, assign, i, chooser)
            p, count = self.probabilities(o, i, seat, chooser, held)
            played = o.history[i][1]
            if self.kind == 'card' or (self.who == 'opponents' and partner) or (self.who == 'partner' and not partner):
                v = np.log((1 - f) * p[:, played] + f / np.maximum(count, 1))
                if q.opponent_factor != 1. and not partner:
                    v = v * q.opponent_factor
            else:
                K = self.klass(o, i, held) & (p > 0)
                K[:, played] = True
                size = K.sum(axis=1)
                v = np.log((1 - f) * (p * K).sum(axis=1) + f * size / np.maximum(count, 1)) - np.log(size)
            out += np.where(count > 1, v, 0.)
        return out


class ExpertReading:
    """A Gen 9 reader whose opposing defenders' spots are read by an E9-15 signal model at every occasion it defines."""

    def __init__(self, base, model, first_round_only=False):
        self.base, self.model, self.first_round_only = base, model, first_round_only
        self.g7 = base.g7

    def meet(self, opponent):
        self.base.meet(opponent)

    def play_log_likelihood(self, o, view, assign, plays):
        from bridge_harness.signal_expert import occasion
        q, c = self.base, o.contract
        out = np.zeros(len(assign))
        exponent = max(q.reading_exponent(o, view), 1e-6)
        for play in plays:
            i, seat, chooser = play
            if chooser != c.declarer and chooser % 2 != o.controller % 2 and q.opponent_signals is not None:
                original = view.original(assign, view.hidden.index(chooser)).astype(bool)
                oc = occasion(o.history, i, c, o.original_hand(c.dummy), original)
                if oc is not None and not (self.first_round_only and oc.key.endswith('.r2')):
                    _, lk, _ = q.signal_row(o, view, assign, *play, q.opponent_signals)
                    out += q.opponent_phi * lk + np.log(self.model.probability(oc)) / exponent
                    continue
            net, signal = q.play_log_terms(o, view, assign, [play])
            out += net + signal / exponent
        return out


def readings(a):
    out = Path(a.out)
    from_tab = not (out / 'tables.json').exists()             # p41's published pools: boards and cards in tab-<part>.json.gz
    if from_tab:
        listed = dict(deciders='all')
    else:
        listed = json.loads((out / 'tables.json').read_text())
        # the bench numbers its tables in the order `pools` took them (passed-out tables left out): the same order here
        yielded = [(path, key) for path, key, *_ in table_source([tuple(x) for x in listed['tables']])(None, None)]
    source = str(Path(a.source).resolve())
    readers, meets, built = {}, {}, {}

    def player_of(bot):
        """One player per bot spec, shared by the readings built on it, so that their nets' rows are computed once."""
        if bot not in built:
            built[bot] = gen9.player(bot_spec(source, a.bots, bot), source)
        return built[bot]
    for item in a.reading:
        name, bot = item.split('=', 1)
        bot, _, meets[name] = bot.partition('@')
        readers[name] = player_of(bot) if not meets[name] else gen9.player(bot_spec(source, a.bots, bot), source)
    for item in a.head_reading:
        from bridge_harness.play_head import PlayHead
        name, rest = item.split('=', 1)
        path, tail = rest.split('.json:', 1)
        version, *middle, factor = tail.split(':')
        head_name = ':'.join(middle)
        heads = json.loads(Path(path + '.json').read_text())['heads'][version]
        which = 'both' if head_name.startswith('both:') else 'defender' if head_name.startswith('defender:') else 'declarer'
        head_name = head_name.split(':', 1)[1] if ':' in head_name else head_name
        decl = PlayHead.from_json(heads['ben.declarer'][head_name]) if which in ('declarer', 'both') else None
        dfd = PlayHead.from_json(heads['ben.defender'][head_name]) if which in ('defender', 'both') else None
        base = player_of(a.head_base if dfd is None else a.expert_base)
        readers[name], meets[name] = HeadReading(base, decl, float(factor), dfd), ''
    for item in a.class_reading:
        name, rest = item.split('=', 1)
        kind, _, who = rest.partition(':')
        readers[name], meets[name] = ClassReading(player_of(a.class_base), kind, who or 'all'), ''
    for item in a.expert_reading:
        from gen9_signal_expert import build
        name, rest = item.split('=', 1)
        path, version, size, which = rest.rsplit(':', 3)
        first = which.endswith('-first')                  # e.g. m3-first: the second rounds left as today (uniform)
        spec = json.loads(Path(path).read_text())['models'][version][size]
        base = player_of(a.expert_base)
        readers[name], meets[name] = ExpertReading(base, build(spec)[which.replace('-first', '')], first), ''
    decisions = kept(bench.decisions, listed.get('deciders', 'house'))
    for part in sorted(out.glob('pools-*-*.npz')):
        todo = {n: out / part.name.replace('pools-', f'fit-{n}-') for n in readers}
        todo = {n: t for n, t in todo.items() if not t.exists()}
        if not todo:
            continue
        rows, tables_, _ = bench.load(part)
        by_table = {}
        for r in rows:
            by_table.setdefault(int(r['table']), {})[int(r['ply'])] = r
        if from_tab:
            with gzip.open(out / part.name.replace('pools-', 'tab-').replace('.npz', '.json.gz'), 'rt') as f:
                tabs = json.load(f)
        for t, wanted in by_table.items():
            info = tables_[t]
            if from_tab:
                tab = tabs[t]
                e = dict(board=tab['board'], tables=[dict(actions=[dict(card=c) for c in tab['played']])])
                opponent = None
            else:
                path, key = yielded[info['index']]
                if os.path.basename(path) != info['path'] or key != info['key']:
                    raise SystemExit(f"{part.name}: table {info['index']} is {info['path']}/{info['key']} in the store, {path}/{key} here")
                with gzip.open(path, 'rt') as f:
                    d = json.load(f)
                e = d['unique_tables'][info['key']]
                opponent = d['opponent']
            for n in todo:
                readers[n].meet(meets[n] or opponent)
            for k, o, game in decisions(e):
                if k in wanted:
                    r = wanted[k]
                    both = np.concatenate([r['assign'], r['truth'][None]])
                    view = View(o)
                    r.setdefault('new', {}).update({n: reading_parts(readers[n], o, view, both) for n in todo})
        for n, target in todo.items():
            missing = [i for i, r in enumerate(rows) if n not in r.get('new', {})]
            if missing:
                raise SystemExit(f'{part.name}: {len(missing)} stored decisions were not found again')
            np.savez_compressed(target, fit=np.concatenate([r['new'][n].ravel() for r in rows]) if rows else np.zeros(0, np.float32))
        print(f'{part.name}: {len(rows)} decisions, readings {sorted(todo)}', flush=True)


def relabel(a):
    """E9-4 part 1's relabelled tables as one-table episodes."""
    from bridge_harness.core import Board
    from gen9_reading_gain import cell_model, relabel_consistent
    import zlib
    out = Path(a.out) / 'episodes'
    out.mkdir(parents=True, exist_ok=True)
    model = cell_model(a.cell)
    kept_, dropped = 0, 0
    for path, key in every_table(a.source_episodes)[:a.tables]:
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        record = d['unique_tables'][key]
        board = Board.from_dict(record['board'])
        main = [t for t in record['tables'] if t.get('depth', 0) == 0]
        if board.contract is None or not main or len(main[0]['actions']) < 8:
            continue
        got = relabel_consistent(board, main[0]['actions'], model, zlib.crc32(f'{Path(path).name}/{key}/{a.cell}/{a.seed}'.encode()))
        if got is None:
            dropped += 1
            continue
        plays = got[0]
        table = dict(main[0], actions=[dict(x, card=symbol(c)) for x, (_, c) in zip(main[0]['actions'], plays)], relabelled=a.cell)
        e = dict(record, tables=[table])
        name = Path(path).name.replace('.json.gz', '') + f'__{key}.json.gz'
        with gzip.open(out / name, 'wt') as f:
            json.dump(dict(family=d['family'], candidate=d['candidate'], opponent=d['opponent'], unique_tables={key: e},
                           relabelled=dict(cell=a.cell, seed=a.seed, swaps=len(got[1]), undone=got[3], source=str(path))), f)
        kept_ += 1
    print(json.dumps(dict(cell=a.cell, tables=kept_, dropped=dropped)))


FEED_URL = 'https://github.com/maxschireson/Single-Dummy-Bridge'
FEED_PATTERN = r'^arena-gen7.*ben(16|64)-[0-9]-feed$'


def fetch_feeds(directory, opponent=None, names=None, commit=None):
    """Episode folders of feed branches, sparse-cloned into `directory` if they are not there: the BEN feeds of one version,
    or the branches named."""
    import re
    import subprocess
    if names is None:
        want = 'ben64' if opponent == 'ben64' else 'ben16'
        heads = subprocess.run(['git', 'ls-remote', '--heads', FEED_URL], check=True, capture_output=True, text=True).stdout.split()
        names = sorted(h[len('refs/heads/'):] for h in heads if h.startswith('refs/heads/'))
        names = [n for n in names if re.match(FEED_PATTERN, n) and want in n]
    Path(directory).mkdir(parents=True, exist_ok=True)
    out = []
    for name in names:
        target = Path(directory) / name
        if not (target / 'recovery' / 'episodes').is_dir():
            subprocess.run(['git', 'clone', '-q', '--depth', '1', '--filter=blob:none', '--sparse', '--single-branch', '-b', name, FEED_URL,
                            str(target)], check=True)
            subprocess.run(['git', 'sparse-checkout', 'set', '--no-cone', '/recovery/episodes/', '/recovery/manifest.json'], cwd=target, check=True)
            if commit:                                  # the feed as it was when it was measured
                subprocess.run(['git', 'fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', commit], cwd=target, check=True)
                subprocess.run(['git', 'checkout', '-q', commit], cwd=target, check=True)
        out.append(str(target / 'recovery' / 'episodes'))
    return out


def box(a):
    """The BEN held-out tables (default), or with --house-feed BRANCH and --cell, E9-4 part 1's tables of that feed relabelled
    by the cell's scheme and scored at declarer's decisions."""
    import subprocess
    import time
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    me = [sys.executable, str(Path(__file__).resolve())]
    if a.house_feed:
        branch, _, commit = a.house_feed.partition('@')
        source_episodes = fetch_feeds(a.feeds_dir, names=[branch], commit=commit or None)[0]
        subprocess.run(me + ['relabel', '--source-episodes', source_episodes, '--cell', a.cell, '--tables', str(a.first + a.tables),
                             '--seed', str(a.relabel_seed), '--out', str(out)], check=True)
        common = ['--episodes', str(out / 'episodes'), '--deciders', 'declarer', '--out', str(out)]
        chosen = every_table(out / 'episodes')[a.first:a.first + a.tables]
        deciders, opponent = 'declarer', None
    else:
        feeds = fetch_feeds(a.feeds_dir, a.opponent)
        common = ['--feeds', *feeds, '--opponent', a.opponent, '--out', str(out)]
        chosen = held_out(feeds, a.opponent, a.first + a.tables)[a.first:]
        deciders, opponent = 'house', a.opponent
    (out / 'tables.json').write_text(json.dumps(dict(opponent=opponent, deciders=deciders, first=a.first,
                                                     tables=[[str(p), k] for p, k in chosen]), indent=0))
    def resume(k):
        """(tables a shard has saved, its next part number): a restarted job carries on where its part files end."""
        saved, last = 0, None
        for q in sorted(out.glob(f'pools-{k:02d}-*.npz')):
            with np.load(q) as z:
                saved += len(z['tables'])
            last = int(q.stem.rsplit('-', 1)[1])
        return saved, (a.part_offset if last is None else last + 1)
    starts = [resume(k) for k in range(a.workers)]
    procs = [subprocess.Popen(me + ['pools', *common, '--first', str(a.first), '--tables', str(a.tables), '--pool', str(a.pool), '--part', str(a.part),
                                    '--seconds', str(a.seconds), '--shard', f'{k}/{a.workers}', '--part-offset', str(starts[k][1]),
                                    '--skip-tables', str(starts[k][0])] + [f'--net={n}' for n in a.net]) for k in range(a.workers)]
    def progress():
        """One line a table saved in a part file (a table logged but not yet saved is redone after a restart)."""
        lines = []
        for q in sorted(out.glob('pools-*-*.npz')):
            try:
                with np.load(q) as z:
                    lines += [json.dumps(dict(part=q.name, **json.loads(t))) for t in z['tables'].tolist()]
            except (OSError, ValueError, KeyError):
                pass
        (out / 'progress.jsonl').write_text(''.join(line + '\n' for line in lines))
    while any(p.poll() is None for p in procs):
        time.sleep(30)
        progress()
    progress()
    if any(p.returncode for p in procs):
        raise SystemExit(f'pools: exit codes {[p.returncode for p in procs]}')
    if a.reading or a.expert_reading or a.head_reading:
        subprocess.run(me + ['readings', *common, '--source', a.source, '--bots', a.bots] + [f'--reading={r}' for r in a.reading]
                       + [f'--expert-reading={r}' for r in a.expert_reading] + [f'--head-reading={r}' for r in a.head_reading], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=('relabel', 'pools', 'readings', 'report', 'box'))
    ap.add_argument('--feeds', nargs='+', default=[], help='episode directories of the BEN feeds')
    ap.add_argument('--opponent', default='ben', choices=('ben', 'ben64'))
    ap.add_argument('--episodes', help='pools: every table of this folder, in place of the BEN held-out list')
    ap.add_argument('--deciders', default='house', choices=('house', 'declarer', 'all'))
    ap.add_argument('--source-episodes', help='relabel: the house feed E9-4 part 1 used')
    ap.add_argument('--cell', default='std-80', help='relabel: scheme-honesty')
    ap.add_argument('--house-feed', help='box: BRANCH[@COMMIT], the feed whose tables are relabelled (E9-4 part 1: arena-gen7-phase1-azure1-feed@f9dad79...)')
    ap.add_argument('--relabel-seed', type=int, default=9, help="box: relabel's seed (E9-4 part 1's: 9)")
    ap.add_argument('--out', required=True)
    ap.add_argument('--first', type=int, default=0, help='the first table of the held-out list to take')
    ap.add_argument('--tables', type=int, default=300)
    ap.add_argument('--shard', default='0/1', help='pools: this process takes the tables k, k + n, ... of its list (k/n)')
    ap.add_argument('--workers', type=int, default=1, help='box: shards run at once')
    ap.add_argument('--feeds-dir', help='box: where the BEN feeds are, or are fetched to')
    ap.add_argument('--seconds', type=float, default=1e9)
    ap.add_argument('--part', type=int, default=4)
    ap.add_argument('--skip-tables', type=int, default=0)
    ap.add_argument('--part-offset', type=int, default=0)
    ap.add_argument('--pool', type=int, default=512)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--net', action='append', default=[])
    ap.add_argument('--source')
    ap.add_argument('--bots', default=str(ROOT / 'configs' / 'gen9-signal-run-bots.json'))
    ap.add_argument('--reading', action='append', default=[], help='NAME=BOT[@ID]: a reading by a bot of --bots')
    ap.add_argument('--head-reading', action='append', default=[], help='NAME=HEADS.json:VERSION:HEAD:FACTOR (E9-14)')
    ap.add_argument('--head-base', default='8x-32')
    ap.add_argument('--expert-reading', action='append', default=[], help='NAME=MODELS.json:VERSION:SIZE:MODEL (E9-15)')
    ap.add_argument('--expert-base', default='r9b-32')
    ap.add_argument('--class-reading', action='append', default=[], help='NAME=KIND[:WHO], KIND spots|touching|card, WHO all|opponents|partner (E9-16)')
    ap.add_argument('--class-base', default='8p-32')
    ap.add_argument('--against')
    ap.add_argument('--sweep', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--json')
    a = ap.parse_args()
    if a.step == 'pools':
        pools(a)
    elif a.step == 'readings':
        readings(a)
    elif a.step == 'relabel':
        relabel(a)
    elif a.step == 'box':
        box(a)
    else:
        report(a)


def report(a):
    """The bench's report on the part files that every reading has reached (pools may still be adding parts)."""
    import shutil
    import tempfile
    out = Path(a.out)
    parts = sorted(out.glob('pools-*-*.npz'))
    names = sorted({f.name[len('fit-'):].rsplit('-', 2)[0] for f in out.glob('fit-*-*-*.npz')})
    done = [q for q in parts if all((out / q.name.replace('pools-', f'fit-{n}-')).exists() for n in names)]
    view = Path(tempfile.mkdtemp(prefix='bench-view-'))
    try:
        for q in done:
            for f in [q] + [out / q.name.replace('pools-', f'fit-{n}-') for n in names]:
                (view / f.name).symlink_to(f.resolve())
        print(f'{len(done)} of {len(parts)} part files have every reading ({", ".join(names)})')
        bench.report(argparse.Namespace(out=str(view), mechanism=False, house=False, sweep=a.sweep, owner=[], against=a.against,
                                        pairs_only=False, verbose=a.verbose, json=a.json, aim=[], near=[], near_split=None, redo=False))
    finally:
        shutil.rmtree(view)


if __name__ == '__main__':
    main()
