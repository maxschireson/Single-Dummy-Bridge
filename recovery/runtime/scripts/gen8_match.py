#!/usr/bin/env python3
"""Duplicate matches for Gen 8 experiments: two bots, fresh random deals, no forks, no TensorFlow.

Work in progress (Gen 8 prototype). Not an arena cohort: nothing here is pooled into arena scores.

Each board is played through gen5_arena.run_board, the function the arena's collectors use: bid
once by the common bidder and played at two tables with the bots' seats swapped ("common"), and
again with each side bidding for itself ("native"), which reuses the same two tables whenever the
auctions are identical. Audit and gap forks are off, so a board costs two tables, or four when
the two sides bid differently.

  python scripts/gen8_match.py --source CAPSULE/recovery --bots configs/gen8-proto-bots.json \\
      --pair 8s-32~7s-32 --deals 2000 --seed 81 --workers 8 --out ~/work/g8/runs/8s-vs-7s

--source is a run folder whose manifest.json defines the base bots and whose artifacts/ holds
their nets (the Gen 7 capture capsule). --bots defines experiment bots as a base bot plus
overrides: {"id": {"base": "6-32", "engine": "gen7", "gen7": {...}, "gen7_policy": "path"}};
paths are absolute or relative to the repository. Ids not defined there are source bots as
they are. Deals are a function of (--seed, index), so two matches with the same seed and range
play the same deals. The run resumes: boards already in results.jsonl are skipped.

Outputs in --out: results.jsonl (one line per board), summary.json, and with --episodes the full
records as episodes/<index>.json.gz in the collectors' format.
"""
import os
import subprocess
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import gzip
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataclasses import replace  # noqa: E402
from bridge_harness import gen5_arena  # noqa: E402
from bridge_harness.bidding_env import deal_key  # noqa: E402
from bridge_harness.core import Board, auction_contract  # noqa: E402
from bridge_harness.gen5_arena import run_board  # noqa: E402
from bridge_harness.gen7 import player  # noqa: E402
from bridge_harness.system_bidders import NumpyPolicy, make_bidder  # noqa: E402
from bridge_harness.training import digest  # noqa: E402

VUL = ('None', 'NS', 'EW', 'Both')
HOUSE = 'house-gen6'                # the registry id of the system the capsule's bidding net plays
NO_FORKS = dict(probability=0., multiplier=1., max_depth=0, max_forks=0)
STATE = {}


def deal(seed, index):
    rng = np.random.default_rng(np.random.SeedSequence([seed, index]))
    deck = rng.permutation(52)
    hands = tuple(tuple(sorted(map(int, deck[13 * s:13 * s + 13]))) for s in range(4))
    return Board(deal_key(hands), hands, None, int(rng.integers(4)), VUL[int(rng.integers(4))])


def build_manifest(source, bots_file, pair, seed):
    """An in-memory manifest for run_board: the pair's bots, one scheduled pair, forks off."""
    old = json.loads((source / 'manifest.json').read_text())
    defined = json.loads(Path(bots_file).read_text()) if bots_file else {}
    a, b = pair.split('~')
    bots = {}
    for key in {a, b, old['audit_references'].get('6-32', '3'), old.get('common_bidder', '6-32')}:
        if key in defined:
            entry = dict(defined[key])
            spec = deepcopy(old['bots'][entry.pop('base')])
            for path_key in ('gen7_policy', 'scorer', 'bidding', 'lead_belief', 'system_scorer'):
                if path_key in entry:
                    path = (ROOT / entry[path_key]).resolve()
                    if not path.exists():           # a model kept in the repository as parts: rebuild it once
                        for restore in sorted(path.parent.glob('restore*.py')):
                            subprocess.run([sys.executable, restore.name], cwd=path.parent, check=True, stdout=subprocess.DEVNULL)
                    entry[path_key] = str(path)
            entry.pop('label', None)
            for block in ('gen6',):
                if block in entry:
                    entry[block] = dict(spec.get(block, {}), **entry[block])
            spec.update(entry, id=key)
            if key in (a, b):
                spec['table_opponent'] = b if key == a else a       # who sits against this bot, for settings keyed by opponent type
            spec.pop('identity', None)
            spec['identity'] = digest(spec)
            bots[key] = spec
        else:
            bots[key] = deepcopy(old['bots'][key])
    reference = old['audit_references'].get('6-32', '3')
    m = dict(schema=old['schema'], campaign='gen8-proto', seed=seed, roster=[a, b], bots=bots, pair_schedule=[pair],
             pair_weights={pair: 1}, audit_references={a: reference, b: reference}, common_bidder=old.get('common_bidder', '6-32'),
             audit=dict(NO_FORKS), ben_audit=dict(NO_FORKS), target=1 << 30)
    for key in ('independent_room_seeds', 'two_self_rooms'):
        if key in old:
            m[key] = old[key]
    if any('system' in spec or 'system_scorer' in spec for spec in bots.values()):
        # the system each bot declares for its own bidding (HOUSE unless its entry says otherwise); run_board tells the players
        m['systems'] = {key: spec.get('system', HOUSE) for key, spec in bots.items()}
    m['identity'] = digest(m)
    return m


def auction_booked(board, bidders, systems=None):
    """In place of gen5_arena.auction when the table's auction was bid beforehand (--book): the booked calls, with
    the board labelled by the systems the book declares for North-South and East-West."""
    systems, calls = STATE['booked']
    decisions = [dict(seat=(board.dealer + k) % 4, ply=k, call=c, behavior='book', behavior_probability=1.) for k, c in enumerate(calls)]
    return replace(board, contract=auction_contract(board.dealer, list(calls)), auction=tuple(calls), opening_lead=None,
                   auction_source=gen5_arena.table_source(systems)), decisions


def load_book(path):
    """index -> (deal key, (NS system, EW system), calls) from a book: gzip JSON with seed, first, tables (a list of
    [NS system, EW system]), keys (deal ids), table_of (index into tables per deal) and auctions (calls per deal)."""
    with gzip.open(path, 'rt') as f:
        book = json.load(f)
    return book['seed'], {book['first'] + k: (key, tuple(book['tables'][t]), tuple(calls))
                          for k, (key, t, calls) in enumerate(zip(book['keys'], book['table_of'], book['auctions']))}


def start(source, manifest, book=None):
    STATE.update(source=source, m=manifest, bidders={}, book=load_book(book)[1] if book else None, booked=None)
    loaded = {}
    for key, spec in manifest['bots'].items():
        entry = spec.get('bidder')                      # a system bidder (rules); otherwise the bot's own bidding net
        name = json.dumps(entry, sort_keys=True) if entry else str((Path(source) / spec['bidding']).resolve())
        if name not in loaded:
            loaded[name] = make_bidder(entry, ROOT) if entry else NumpyPolicy(name)
        STATE['bidders'][key] = loaded[name]
    if book:
        gen5_arena.auction = auction_booked


def summarise_actions(record, roles):
    """Small per-board facts about the search, by role."""
    out = {r: dict(decisions=0, seconds=0., pool=0, effective=0., power=0., tree=0, tree_moved=0) for r in roles}
    for table in record.values():
        for t in table['tables'][:1]:
            for a in t['actions']:
                role = a.get('role') or a.get('player')
                g = a.get('gen6')
                if role not in out or not g:
                    continue
                s = out[role]
                s['decisions'] += 1
                s['seconds'] += g.get('layout_seconds', 0.) + g.get('dds_seconds', 0.)
                if g.get('pick') == 'play-pool':
                    s['pool'] += 1
                    s['effective'] += g['effective_with_play']
                    s['power'] += g['play_power']
                note = a.get('gen7_tree')
                if note and note.get('consulted'):
                    s['tree'] += 1
                    s['tree_moved'] += a.get('selected_pimc_gap', 0.) > 1e-9
    return out


def play(index, seed, episodes):
    m, source = STATE['m'], STATE['source']
    started = time.process_time()
    board, systems = deal(seed, index), None
    if STATE['book'] is not None:       # this board's table: who declared what, and the auction they bid
        key, systems, calls = STATE['book'][index]
        if key != board.id:
            raise ValueError(f'the auction book was made for other deals (board {index})')
        STATE['booked'] = (systems, calls)
        m = dict(m, table_systems=list(systems))        # the book's systems go with the directions, whoever sits there
    r = run_board(source, m, board.to_dict(), index, STATE['bidders'], player_factory=player)
    cpu = time.process_time() - started
    if episodes:
        with gzip.open(Path(episodes) / f'{index:06d}.json.gz', 'wt') as f:
            json.dump(r, f, separators=(',', ':'))
    a = m['roster'][0]
    sign = 1 if r['candidate'] == a else -1
    row = dict(index=index, family=r['family'], candidate=r['candidate'], opponent=r['opponent'], cpu=round(cpu, 2), tables=len(r['unique_tables']),
               contract=r['board'].get('contract'), auction_len=len(r['board'].get('auction') or ()))
    if systems:
        row['systems'] = '~'.join(systems)
    for regime, v in r['regimes'].items():
        row[regime] = None if v['imps'] is None else sign * v['imps']
        row[regime + '_score'] = None if v['score_difference'] is None else sign * v['score_difference']
    row['search'] = summarise_actions(r['unique_tables'], ('candidate', 'opponent'))
    return row


def summary(rows, a, b, started=None):
    out = dict(pair=f'{a}~{b}', boards=len(rows), cpu_per_board=round(float(np.mean([r['cpu'] for r in rows])), 2) if rows else None)
    for regime in ('common', 'native'):
        x = np.array([r[regime] for r in rows if r.get(regime) is not None], float)
        if len(x) > 1:
            out[regime] = dict(imps_per_board=round(float(x.mean()), 4), se=round(float(x.std(ddof=1) / math.sqrt(len(x))), 4), boards=len(x),
                               won=int((x > 0).sum()), lost=int((x < 0).sum()), flat=int((x == 0).sum()))
    kinds = sorted({r['systems'] for r in rows if r.get('systems')})
    if kinds:                           # by what the two sides declared (NS~EW), common regime
        out['by_systems'] = {}
        for kind in kinds:
            x = np.array([r['common'] for r in rows if r.get('systems') == kind and r.get('common') is not None], float)
            if len(x) > 1:
                out['by_systems'][kind] = dict(imps_per_board=round(float(x.mean()), 4), se=round(float(x.std(ddof=1) / math.sqrt(len(x))), 4), boards=len(x))
    if started:
        out['boards_per_hour'] = round(len(rows) / max(time.time() - started, 1e-9) * 3600)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--bots')
    ap.add_argument('--pair', required=True, help='A~B: the result is from A\'s side')
    ap.add_argument('--deals', type=int, required=True)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--workers', type=int, default=os.cpu_count())
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--episodes', action='store_true', help='keep full records (collector format) under episodes/')
    ap.add_argument('--book', help='auctions bid beforehand, with each table\'s declared systems (see load_book for the format); '
                                   'both rooms of a board then play the same auction')
    args = ap.parse_args()
    if args.book and load_book(args.book)[0] != args.seed:
        raise SystemExit('the auction book was made with another seed')
    source = args.source.resolve()
    m = build_manifest(source, args.bots, args.pair, args.seed)
    a, b = m['roster']
    args.out.mkdir(parents=True, exist_ok=True)
    episodes = None
    if args.episodes:
        episodes = args.out / 'episodes'
        episodes.mkdir(exist_ok=True)
    (args.out / 'manifest.json').write_text(json.dumps(dict(m, source=str(source), first=args.first, deals=args.deals,
                                                             source_commit=os.popen(f'git -C {ROOT} rev-parse HEAD 2>/dev/null').read().strip()), indent=1))
    results = args.out / 'results.jsonl'
    rows = [json.loads(line) for line in results.read_text().splitlines()] if results.exists() else []
    done = {r['index'] for r in rows}
    todo = [i for i in range(args.first, args.first + args.deals) if i not in done]
    print(f'{a} v {b}: {len(todo)} boards to play ({len(done)} done), {args.workers} workers', flush=True)
    started, fresh, failed, pending = time.time(), [], [], todo
    with ProcessPoolExecutor(args.workers, initializer=start, initargs=(str(source), m, args.book)) as pool, results.open('a') as f:
        for attempt in (1, 2):                          # a board that failed is played once more
            jobs = {pool.submit(play, i, args.seed, str(episodes) if episodes else None): i for i in pending}
            failed = []
            for n, job in enumerate(as_completed(jobs), 1):
                try:
                    row = job.result()
                except Exception as e:                  # one bad board must not end the match; it is reported and counted
                    failed.append(jobs[job])
                    print(f'board {jobs[job]} failed (attempt {attempt}): {type(e).__name__}: {e}'[:300], flush=True)
                    continue
                rows.append(row)
                fresh.append(row)
                f.write(json.dumps(row) + '\n')
                f.flush()
                if n % 50 == 0 or n == len(jobs):
                    s = summary(rows, a, b)
                    c = s.get('common', {})
                    print(f'{len(rows)} boards: {c.get("imps_per_board")} +- {c.get("se")} IMPs/board for {a}; '
                          f'{len(fresh) / (time.time() - started) * 3600:.0f} boards/hour; {len(failed)} failed', flush=True)
                    (args.out / 'summary.json').write_text(json.dumps(dict(s, failures=len(failed), boards_per_hour=round(len(fresh) / (time.time() - started) * 3600)), indent=1))
            if not failed:
                break
            pending = failed
    failures = len(failed)
    s = summary(rows, a, b)
    (args.out / 'summary.json').write_text(json.dumps(dict(s, failures=failures, boards_per_hour=round(len(fresh) / max(time.time() - started, 1e-9) * 3600)), indent=1))
    print(json.dumps(s))


if __name__ == '__main__':
    main()
