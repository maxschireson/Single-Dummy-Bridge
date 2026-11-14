#!/usr/bin/env python3
"""An auction book for scripts/gen9_match.py --book (E9-12): the deals of a match bid beforehand by a rule bidder.

The deals are gen8_match's (a function of --seed and the index), so the book fits a match with the same seed and
range. All four seats bid with the rule bidder's settings; the table's declared systems are written as given.

    python scripts/gen9_make_book.py --settings precision --seed 9121 --deals 600 --out ~/runs/book-rb-precision.json.gz
"""
import argparse
from dataclasses import asdict
import gzip
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import rule_bidder as rb  # noqa: E402
from bridge_harness.cards.bidder import bid_table  # noqa: E402

_spec = importlib.util.spec_from_file_location('gen8_match', ROOT / 'scripts' / 'gen8_match.py')
g8 = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('gen8_match', g8)
_spec.loader.exec_module(g8)

SETTINGS = {'precision': rb.Settings(), 'standard': rb.STANDARD}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--settings', default='precision', help='precision | standard | a JSON dict of Settings fields')
    ap.add_argument('--system', default=None, help='declared system id for both sides (default rb-<settings>)')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--deals', type=int, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    g = SETTINGS.get(a.settings) or rb.Settings(**json.loads(a.settings))
    system = a.system or f'rb-{a.settings if a.settings in SETTINGS else "custom"}'
    bidder = rb.RuleSystemBidder(g, 'standard')
    keys, auctions, skipped = [], [], 0
    for i in range(a.first, a.first + a.deals):
        board = g8.deal(a.seed, i)
        try:
            calls, _ = bid_table([bidder] * 4, [list(h) for h in board.hands], board.dealer, board.vulnerability)
        except (ValueError, IndexError):             # rule_bidder.py edge cases: pass the deal out
            calls, skipped = ['PASS'] * 4, skipped + 1
        keys.append(board.id)
        auctions.append(calls)
    book = dict(seed=a.seed, first=a.first, tables=[[system, system]], keys=keys, table_of=[0] * len(keys), auctions=auctions,
                settings=asdict(g), skipped=skipped)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(a.out, 'wt') as f:
        json.dump(book, f)
    print(f'{len(keys)} auctions ({skipped} passed out after a rule-bidder error) -> {a.out}')


if __name__ == '__main__':
    main()
