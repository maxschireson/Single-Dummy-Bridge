#!/usr/bin/env python3
"""Bid a set of deals beforehand at tables where the two sides play given systems (Gen 8 prototype, WIP).

  python scripts/gen8_auction_book.py --source CAPSULE/recovery --seed 91 --deals 2880 \
      --tables rules-precision~house-gen6,house-gen6~rules-precision,rules-precision~rules-precision,house-gen6~house-gen6 \
      --out configs/gen8-books/NAME.json.gz

The deals are those of scripts/gen8_match.py for the same seed and indices. Table k of the list is used for the
deals whose index is k modulo the length of the list, so every match on these deals sees the same mix. A table
is NS~EW by system id (configs/systems). 'house-gen6' is bid by the capsule's 6-32 bidder, exactly as the match
runner bids it; any other system by its package's generator. A machine that plays the book needs no bidder.

The book: seed, first, tables (the list), keys (deal ids), table_of (index into tables per deal), auctions (calls).
"""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import CALL_ID, CALLS, BidObservation, encode, legal_mask, normalize_bid, pack_inputs  # noqa: E402
from bridge_harness.core import auction_contract  # noqa: E402
from bridge_harness.system_bidders import NumpyPolicy, make_bidder  # noqa: E402
from bridge_harness.systems import SystemRegistry  # noqa: E402

VUL = ('None', 'NS', 'EW', 'Both')
HOUSE = 'house-gen6'


def match_module():
    spec = importlib.util.spec_from_file_location('gen8_match', ROOT / 'scripts' / 'gen8_match.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Bidders:
    """The bidder for a side that plays `own` against `opp`, made once."""

    def __init__(self, source, registry):
        self.source, self.registry, self.made = Path(source), registry, {}

    def get(self, own, opp):
        if own not in self.made:
            if own == HOUSE:
                manifest = json.loads((self.source / 'manifest.json').read_text())
                self.made[own] = NumpyPolicy(str((self.source / manifest['bots']['6-32']['bidding']).resolve()))
            else:
                self.made[own] = make_bidder(self.registry[own].generator(), ROOT)
                self.registry.require_generator(own, self.made[own].sha256)
        b = self.made[own]
        return b.facing(own == opp) if hasattr(b, 'facing') else b


def bid(board, sides):
    """The calls of one deal; sides = (NS bidder, EW bidder). An illegal call from a rule engine is read as a pass."""
    calls = []
    for _ in range(320):
        seat = (board.dealer + len(calls)) % 4
        mask = legal_mask(board.dealer, calls)
        b = sides[seat % 2]
        if hasattr(b, 'predict'):
            xs, lengths = pack_inputs([encode(BidObservation(board.hands[seat], seat, board.dealer, board.vulnerability, tuple(calls)))])
            action = int(np.argmax(np.where(mask, b.predict(xs, lengths)[0][0], -np.inf)))
        else:
            action = int(b.call(board.hands[seat], seat, board.dealer, VUL.index(board.vulnerability), [CALL_ID[normalize_bid(c)] for c in calls]))
            if not mask[action]:
                action = CALL_ID['PASS']
        calls.append(CALLS[action])
        try:
            auction_contract(board.dealer, calls)
        except ValueError as e:
            if str(e) != 'Incomplete auction':
                raise
            continue
        return calls
    raise ValueError('Auction exceeded legal length bound')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, required=True, help='capsule recovery folder (for the house bidder)')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--deals', type=int, required=True)
    ap.add_argument('--tables', required=True, help='comma-separated NS~EW system ids, cycled over the deals')
    ap.add_argument('--registry', default=str(ROOT / 'configs' / 'systems'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    tables = [tuple(t.split('~')) for t in args.tables.split(',')]
    registry = SystemRegistry.load(args.registry)
    for t in tables:
        for system in t:
            registry.check_declared(system)
    deal = match_module().deal
    bidders = Bidders(args.source.resolve(), registry)
    keys, table_of, auctions, started = [], [], [], time.time()
    for k in range(args.deals):
        board = deal(args.seed, args.first + k)
        t = (args.first + k) % len(tables)
        ns, ew = tables[t]
        keys.append(board.id)
        table_of.append(t)
        auctions.append(bid(board, (bidders.get(ns, ew), bidders.get(ew, ns))))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    generators = {s: registry[s].generator().get('sha256') for t in tables for s in t}
    with gzip.open(args.out, 'wt') as f:
        json.dump(dict(seed=args.seed, first=args.first, tables=[list(t) for t in tables], keys=keys, table_of=table_of, auctions=auctions,
                       made=dict(generators=generators, seconds=round(time.time() - started, 1))), f, separators=(',', ':'))
    passed = sum(all(c == 'PASS' for c in a) for a in auctions)
    print(f'{len(auctions)} deals, {len(tables)} table kinds, {passed} passed out, mean length {np.mean([len(a) for a in auctions]):.1f} calls, '
          f'{time.time() - started:.0f}s -> {args.out}')


if __name__ == '__main__':
    main()
