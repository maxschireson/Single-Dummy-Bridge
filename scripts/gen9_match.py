#!/usr/bin/env python3
"""Duplicate matches for Gen 9 experiments: scripts/gen8_match.py with Gen 9 bots allowed.

Design in progress (docs/gen9/architecture.md). Not an arena cohort: nothing here is pooled
into arena scores. Arguments, deals, outputs and resuming are exactly those of
scripts/gen8_match.py; read its help.

What this adds:

- A bot whose entry in --bots has "engine": "gen9" is built by bridge_harness.gen9 (the Gen 8
  prototype player reading each partnership through a PlayerModel). Its "gen9" block is passed
  through as written; every other bot is built as before.
- Before each table the players are told who made the calls (auction_by): the common bidder
  at all four seats in the common regime, each side's own bidder in the native one. The model
  of a bidder is looked up by bot id in the player's own "gen9": {"players": ...}.
- TEST ONLY, with BRIDGE_ALLOW_ORACLE=1: a bot whose "gen9" block has an "oracle" entry is
  shown the deal (experiment E9-0: what a nat of reading is worth). Such a bot must never be
  rostered in an arena; the player refuses to be built without that variable.

  BRIDGE_DDS_CACHE= python scripts/gen9_match.py --source CAPSULE/recovery --bots configs/gen9-proto-bots.json \\
      --pair 9t1-32~8p-32 --deals 800 --seed 91 --workers 8 --out ~/work/g9/runs/e9-0-t1
"""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import gen5_arena, gen9  # noqa: E402

_spec = importlib.util.spec_from_file_location('gen8_match', ROOT / 'scripts' / 'gen8_match.py')
g8 = importlib.util.module_from_spec(_spec)
sys.modules['gen8_match'] = g8
_spec.loader.exec_module(g8)

SEEN = {}                           # the board in hand and the players built for it, per worker process
_deal, _start, _auction = g8.deal, g8.start, None


def deal(seed, index):
    board = _deal(seed, index)
    SEEN.update(board=board, players=[])
    return board


def player(spec, root, reference=None):
    p = gen9.player(spec, root, reference)
    SEEN.setdefault('players', []).append(p)
    if getattr(p, 'oracle', None) is not None:
        p.peek(SEEN['board'].hands)
    return p


def auction_any(board, bidders):
    """gen8_match's auction, after telling every Gen 9 player at the table who is bidding. run_board bids the common
    auction once with four copies of the common bidder, then each native table with the seats' own bidders: four
    copies of the common bidder are announced as such, anything else as "each side bid for itself"."""
    common = g8.STATE['m'].get('common_bidder')
    same = all(b is bidders[0] for b in bidders) and bidders[0] is g8.STATE['bidders'].get(common)
    for p in SEEN.get('players', ()):
        if hasattr(p, 'auction_by'):
            p.auction_by([common] * 4 if same else None)
    return _auction(board, bidders)


def start(source, manifest, book=None):
    global _auction
    _start(source, manifest, book)                  # sets gen5_arena.auction to gen8_match's auction_any
    _auction = gen5_arena.auction
    gen5_arena.auction = auction_any


g8.deal, g8.player, g8.start = deal, player, start

if __name__ == '__main__':
    g8.main()
