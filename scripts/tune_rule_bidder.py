#!/usr/bin/env python3
"""Measure and tune the rule bidder (bridge_harness/rule_bidder.py) by double-dummy IMPs (Gen 8 prototype, WIP).

A team match without card play: on each deal the rule bidder's pair sits North-South at one table and
East-West at the other, against a reference pair. Each final contract is scored by the double-dummy
table of the deal, and the two scores are compared in IMPs. The reference is the house bidder of a
run capsule (--source) or the same rules in their plain natural form (--reference standard).

  python scripts/tune_rule_bidder.py measure --source CAPSULE/recovery --deals 2000 --seed 301 --cache DIR
  python scripts/tune_rule_bidder.py tune    --source CAPSULE/recovery --deals 4000 --seed 301 --cache DIR \
      --test-deals 4000 --test-seed 302 --out configs/rule-systems/precision-tuned.json

`measure` prints IMPs a board for the rule pair, how often it declares, and how often its contract goes
three or more down. `tune` walks the numeric settings one at a time, keeps a change when the paired gain
on the tuning deals is at least --keep standard errors, and reports the result on deals it never saw.
The deals are a function of seed and index. Double-dummy tables are computed once and kept in --cache.
"""
import argparse
from dataclasses import asdict, replace
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import CALLS, BidObservation, TableSolver, deal_key, encode, legal_mask, pack_inputs  # noqa: E402
from bridge_harness.core import Board, auction_contract, imps, score, vulnerable  # noqa: E402
from bridge_harness.rule_bidder import PASS, STANDARD, RuleSystemBidder, Settings  # noqa: E402

VUL = ('None', 'NS', 'EW', 'Both')
STEPS = {           # setting -> the values tried around the current one, and its limits
    'club_min': (1, 15, 18), 'open_min': (1, 10, 13), 'open_light': (1, 0, 2), 'limited_max': (1, 14, 16),
    'nt_lo': (1, 12, 15), 'nt_hi': (1, 14, 17), 'weak_lo': (1, 3, 7), 'weak_hi': (1, 8, 11), 'weak_quality': (1, 1, 3),
    'preempt_len': (1, 6, 8), 'neg_max': (1, 6, 8), 'resp_min': (1, 5, 7), 'two_over_one': (1, 10, 13),
    'game': (1, 23, 27), 'game_minor': (1, 26, 30), 'slam': (1, 31, 35), 'invite_width': (1, 1, 3),
    'overcall_min1': (1, 6, 10), 'overcall_min2': (1, 9, 13), 'overcall_quality': (1, 1, 3), 'takeout_min': (1, 10, 14),
    'nt_overcall_lo': (1, 14, 16), 'balance': (1, 1, 4), 'compete': (1, -1, 1), 'penalty': (1, 22, 28),
}
SWITCHES = ('two_diamonds', 'nt_five_major', 'jump_overcalls')


def deal(seed, index):
    rng = np.random.default_rng(np.random.SeedSequence([seed, index]))
    deck = rng.permutation(52)
    hands = tuple(tuple(sorted(map(int, deck[13 * s:13 * s + 13]))) for s in range(4))
    return Board(deal_key(hands), hands, None, int(rng.integers(4)), VUL[int(rng.integers(4))])


def _tables(args):
    seed, indices = args
    solver = TableSolver()
    return [solver.solve(deal(seed, i).hands) for i in indices]


def dd_tables(seed, n, cache, workers):
    """[n, 5, 4] double-dummy tricks (strain, declarer) for deals 0..n-1 of a seed, computed once."""
    path = Path(cache) / f'dd-{seed}.npz'
    have = np.load(path)['t'] if path.exists() else np.zeros((0, 5, 4), np.int8)
    if len(have) < n:
        todo = list(range(len(have), n))
        chunks = [todo[k::workers] for k in range(workers)]
        started = time.time()
        with mp.get_context('fork').Pool(workers) as pool:
            parts = pool.map(_tables, [(seed, c) for c in chunks])
        new = np.zeros((n, 5, 4), np.int8)
        new[:len(have)] = have
        for c, part in zip(chunks, parts):
            for i, t in zip(c, part):
                new[i] = t
        Path(cache).mkdir(parents=True, exist_ok=True)
        np.savez(path, t=new)
        print(f'double-dummy tables for {len(todo)} deals of seed {seed}: {time.time() - started:.0f}s', flush=True)
        have = new
    return have[:n]


class House:
    """The capsule's bidder, one call at a time, remembering what it has already been asked."""

    def __init__(self, source):
        from bridge_harness.system_bidders import NumpyPolicy
        manifest = json.loads((Path(source) / 'manifest.json').read_text())
        self.net = NumpyPolicy(str((Path(source) / manifest['bots']['6-32']['bidding']).resolve()))
        self.memo = {}

    def call(self, key, board, seat, calls):
        k = (key, seat, calls)
        if k not in self.memo:
            xs, lengths = pack_inputs([encode(BidObservation(board.hands[seat], seat, board.dealer, board.vulnerability, tuple(CALLS[c] for c in calls)))])
            mask = legal_mask(board.dealer, [CALLS[c] for c in calls])
            self.memo[k] = int(np.argmax(np.where(mask, self.net.predict(xs, lengths)[0][0], -np.inf)))
        return self.memo[k]


def auction(board, key, sides):
    """The calls of one table; sides = (North-South bidder, East-West bidder)."""
    calls, v = [], VUL.index(board.vulnerability)
    for _ in range(100):
        seat = (board.dealer + len(calls)) % 4
        b = sides[seat % 2]
        token = b.call(key, board, seat, tuple(calls)) if isinstance(b, House) else b.call(board.hands[seat], seat, board.dealer, v, calls)
        names = [CALLS[c] for c in calls]
        if not legal_mask(board.dealer, names)[token]:
            token = PASS
        calls.append(token)
        try:
            return calls, auction_contract(board.dealer, [CALLS[c] for c in calls])
        except ValueError as e:
            if str(e) != 'Incomplete auction':
                raise
    raise ValueError('auction did not end')


def table_score(board, contract, table):
    """North-South's double-dummy score for a final contract, and the tricks short of it (0 when made)."""
    if contract is None:
        return 0, 0
    tricks = int(table[contract.trump][contract.declarer])
    s = score(contract, tricks, vulnerable(board.vulnerability, contract.declarer))
    return (s if contract.declarer % 2 == 0 else -s), max(0, contract.level + 6 - tricks)


def worker(conn, shard, of, source, reference):
    ref = House(source) if reference == 'house' else None
    data, bidders = {}, {}
    while True:
        msg = conn.recv()
        if msg is None:
            return
        seed, n, tables, settings, opponents = msg
        if settings not in bidders:
            if len(bidders) > 400:
                bidders.clear()
            bidders[settings] = RuleSystemBidder(Settings(**json.loads(settings)), opponents=opponents)
        cand = bidders[settings]
        other = ref if ref is not None else bidders.setdefault('standard', RuleSystemBidder(STANDARD, opponents=Settings(**json.loads(settings))))
        rows = []
        for i in range(shard, n, of):
            if (seed, i) not in data:
                data[(seed, i)] = deal(seed, i)
            board = data[(seed, i)]
            (_, ca), (_, cb) = auction(board, (seed, i), (cand, other)), auction(board, (seed, i), (other, cand))
            (sa, da), (sb, db) = table_score(board, ca, tables[i]), table_score(board, cb, tables[i])
            ours = [(c, d) for c, d, side in ((ca, da, 0), (cb, db, 1)) if c is not None and c.declarer % 2 == side]
            rows.append((i, imps(sa - sb), len(ours), sum(d >= 3 for _, d in ours), sum(c.level >= 6 for c, _ in ours),
                         sum(c.level >= 6 and d == 0 for c, d in ours)))
        conn.send(rows)


class Field:
    """Worker processes, each owning a share of the deals and its own memory of the reference bidder's calls."""

    def __init__(self, source, reference, workers):
        self.pipes, self.procs = [], []
        for k in range(workers):
            a, b = mp.Pipe()
            p = mp.get_context('fork').Process(target=worker, args=(b, k, workers, source, reference), daemon=True)
            p.start()
            self.pipes.append(a)
            self.procs.append(p)
        self.opponents = 'standard'

    def play(self, settings, seed, n, tables):
        text = json.dumps(asdict(settings), sort_keys=True)
        for pipe in self.pipes:
            pipe.send((seed, n, tables, text, self.opponents))
        rows = sorted(r for pipe in self.pipes for r in pipe.recv())
        return np.array(rows, float)

    def close(self):
        for pipe in self.pipes:
            pipe.send(None)


def report(rows):
    x = rows[:, 1]
    declared = rows[:, 2].sum()
    return dict(boards=len(x), imps_per_board=round(float(x.mean()), 3), se=round(float(x.std(ddof=1) / math.sqrt(len(x))), 3),
                won=int((x > 0).sum()), lost=int((x < 0).sum()), flat=int((x == 0).sum()),
                lost_10_or_more=round(float((x <= -10).mean()), 4), declared_per_board=round(float(declared / len(x)), 3),
                three_down_share=round(float(rows[:, 3].sum() / max(declared, 1)), 4),
                slams_bid=int(rows[:, 4].sum()), slams_made=int(rows[:, 5].sum()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=('measure', 'tune'))
    ap.add_argument('--source', type=Path, help='capsule recovery folder, for the house bidder')
    ap.add_argument('--reference', choices=('house', 'standard'), default='house')
    ap.add_argument('--settings', help='JSON file of settings to start from (default: the built-in precision settings)')
    ap.add_argument('--deals', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=301)
    ap.add_argument('--test-deals', type=int, default=0)
    ap.add_argument('--test-seed', type=int, default=302)
    ap.add_argument('--cache', default=str(Path.home() / '.cache' / 'rule-bidder'))
    ap.add_argument('--workers', type=int, default=os.cpu_count())
    ap.add_argument('--keep', type=float, default=2.0, help='tune: keep a change that gains at least this many standard errors')
    ap.add_argument('--passes', type=int, default=2)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    if args.reference == 'house' and not args.source:
        raise SystemExit('the house reference needs --source')
    start = Settings(**json.loads(Path(args.settings).read_text())['settings']) if args.settings else Settings()
    tables = dd_tables(args.seed, args.deals, args.cache, args.workers)
    field = Field(str(args.source) if args.source else None, args.reference, args.workers)
    t0 = time.time()
    base = field.play(start, args.seed, args.deals, tables)
    print(f'start: {json.dumps(report(base))}  ({time.time() - t0:.0f}s)', flush=True)
    best, best_rows, log = start, base, []
    if args.mode == 'tune':
        for sweep in range(args.passes):
            changed = False
            trials = [(name, getattr(best, name) + d * step) for name, (step, lo, hi) in STEPS.items() for d in (-1, 1)
                      if lo <= getattr(best, name) + d * step <= hi] + [(name, not getattr(best, name)) for name in SWITCHES]
            for name, value in trials:
                if getattr(best, name) == value:
                    continue
                try:
                    cand = replace(best, **{name: value})
                except ValueError:
                    continue
                rows = field.play(cand, args.seed, args.deals, tables)
                diff = rows[:, 1] - best_rows[:, 1]
                gain, se = float(diff.mean()), float(diff.std(ddof=1) / math.sqrt(len(diff)))
                keep = se > 0 and gain >= args.keep * se
                log.append(dict(sweep=sweep, setting=name, value=value, gain=round(gain, 4), se=round(se, 4), kept=keep))
                print(f'  {name} {getattr(best, name)} -> {value}: {gain:+.3f} +- {se:.3f}{"  kept" if keep else ""}', flush=True)
                if keep:
                    best, best_rows, changed = cand, rows, True
            print(f'after sweep {sweep + 1}: {json.dumps(report(best_rows))}', flush=True)
            if not changed:
                break
    result = dict(settings=asdict(best), reference=args.reference, tuning=dict(seed=args.seed, deals=args.deals, **report(best_rows)),
                  start=report(base), changes=[c for c in log if c['kept']])
    if args.test_deals:
        test_tables = dd_tables(args.test_seed, args.test_deals, args.cache, args.workers)
        result['test'] = dict(seed=args.test_seed, tuned=report(field.play(best, args.test_seed, args.test_deals, test_tables)),
                              start=report(field.play(start, args.test_seed, args.test_deals, test_tables)))
        print(f'unseen deals: tuned {json.dumps(result["test"]["tuned"])}', flush=True)
        print(f'unseen deals: start {json.dumps(result["test"]["start"])}', flush=True)
    field.close()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1) + '\n')
        print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
