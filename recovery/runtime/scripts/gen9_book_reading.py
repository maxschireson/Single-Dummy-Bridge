#!/usr/bin/env python3
"""E9-12's record of reading: for every board of an auction book (scripts/gen9_make_book.py), what the auction
tells each reader about the true layout, at the two decisions E9-1 used (the opening leader before the lead,
declarer at trick 1). One row per board and role, to join with the played boards (gen9_match.py results by
board index) and to separate "stop misreading" from "read by the card".

    G(R) = log(w_R(true) / sum_pool w_R) - log(1 / n)     (nats; 0 = no information, the 9u-32 reading)

Readers, one per bot of E9-12:
    S   the hand-fit scorer v0 (8p-32: every call read as the house's)
    F   the declared card's rule filter alone, eps 0.05 (9c-32's 'card' profile; its prior eps is 0.05)
    R   replay of the rule bidder with the book's settings, eps 0.02 (9x-32; the shell's pool is drawn by S
        and reweighted to R, so this is R's reading on a uniform pool, not 9x-32's exactly)

    python scripts/gen9_book_reading.py --book ~/runs/book-rb-precision-9121.json.gz --card rb-precision \\
        --pool 512 --out reports/gen9-e9-12-2026-11-12/reading-precision.jsonl
"""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import random
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import rule_bidder as rb                              # noqa: E402
from bridge_harness.cards.replay import RuleReplay                         # noqa: E402
from bridge_harness.core import auction_contract                           # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types                  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / path)
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, m)
    spec.loader.exec_module(m)
    return m


e91 = load('gen9_e9_1', 'gen9_e9_1.py')
g8 = load('gen8_match', 'gen8_match.py')
KEYS = ('S', 'F', 'R')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', type=Path, required=True)
    ap.add_argument('--card', required=True, help='the declared card (configs/cards/<id>.json)')
    ap.add_argument('--pool', type=int, default=512)
    ap.add_argument('--boards', type=int, default=None, help='the first N boards of the book (default all)')
    ap.add_argument('--seed', type=int, default=9120)
    ap.add_argument('--scorer', default='models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    with gzip.open(a.book, 'rt') as f:
        book = json.load(f)
    scorer = FitScorer(a.scorer)
    replay = RuleReplay(rb.RuleSystemBidder(book['settings'], 'standard'), eps=0.02)
    card = json.loads(Path(a.card).read_text()) if a.card.endswith('.json') else a.card     # an id in configs/cards, or a file
    reads = e91.Readers(scorer, card, None, replay)
    rng = random.Random(a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    n = len(book['keys']) if a.boards is None else min(a.boards, len(book['keys']))
    with a.out.open('w') as out:
        for k in range(n):
            i = book['first'] + k
            board = g8.deal(book['seed'], i)
            hands = [sorted(h) for h in board.hands]
            dealer, vul, calls = board.dealer, board.vulnerability, book['auctions'][k]
            contract = auction_contract(dealer, calls)
            if contract is None:
                continue
            decl = contract.declarer
            dummy, leader = (decl + 2) % 4, (decl + 1) % 4
            for role, viewer, hidden in (('leader', leader, [decl, dummy, (leader + 2) % 4]), ('declarer', decl, [leader, (decl + 3) % 4])):
                seen = set(hands[viewer]) | (set(hands[dummy]) if role == 'declarer' else set())
                hidden_cards = [c for c in range(52) if c not in seen]
                layouts = [[hands[s] for s in hidden]] + e91.pool_layouts(rng, hidden_cards, [13] * len(hidden), a.pool - 1)
                total = None
                for j, s in enumerate(hidden):
                    length, hon = hand_types(e91.membership([lay[j] for lay in layouts]))
                    sc = reads.seat(length, hon, s, dealer, vul, calls, exact=False)
                    total = sc if total is None else {x: total[x] + sc[x] for x in sc}
                row = {'index': i, 'key': book['keys'][k], 'role': role, 'contract': f'{contract.level}{contract.strain}',
                       'calls': len(calls)} | {x: round(e91.gain(total[x]), 4) for x in KEYS}
                out.write(json.dumps(row) + '\n')
                rows.append(row)
    summary = {'book': str(a.book), 'card': a.card, 'pool': a.pool, 'rows': len(rows)}
    for role in ('leader', 'declarer', None):
        sel = [r for r in rows if role is None or r['role'] == role]
        summary[role or 'all'] = {x: [round(float(np.mean([r[x] for r in sel])), 3), round(float(np.std([r[x] for r in sel]) / np.sqrt(max(len(sel), 1))), 3)]
                                  for x in KEYS} | {'n': len(sel)}
    a.out.with_suffix('.summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
