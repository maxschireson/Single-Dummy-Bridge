"""Where a generator breaks a card: for G9-B2 (cards written for the rule bidder) and G9-B4 (distance).

Bids deals with a generator at all four seats and, for every call the card covers, checks whether
the card's first satisfied rule is the call made. Prints break rates by family and examples.

    python scripts/gen9_card_breaks.py --card rb-standard --gen rb:standard --deals 2000
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness.cards.bidder import CardBidder, bid_table          # noqa: E402
from bridge_harness.cards.context import Context                       # noqa: E402
from bridge_harness.cards.features import features_of_hands             # noqa: E402
from bridge_harness.cards.system import CardSystem                      # noqa: E402
from bridge_harness import rule_bidder as rb                             # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')
SUITS = 'SHDC'


def generator(name):
    if name.startswith('rb:'):
        spec = name[3:]
        if spec == 'standard':
            return rb.RuleSystemBidder(rb.STANDARD, 'standard')
        if spec == 'precision':
            return rb.RuleSystemBidder(rb.Settings(), 'standard')
        return rb.RuleSystemBidder(json.loads(spec), 'standard')
    return CardBidder(name)


def show(hand):
    return '.'.join(''.join('23456789TJQKA'[c % 13] for c in sorted((c for c in hand if c // 13 == s), reverse=True)) or '-' for s in range(4))


def breaks(card, gen, deals, seed, examples=3):
    system = CardSystem(card)
    g = generator(gen)
    rng = random.Random(seed)
    tally = defaultdict(Counter)
    ex = defaultdict(list)
    covered = total = 0
    for i in range(deals):
        deck = list(range(52))
        rng.shuffle(deck)
        hands = [sorted(deck[13 * k:13 * k + 13]) for k in range(4)]
        dealer, vul = i % 4, VULS[(i // 4) % 4]
        try:
            calls, _ = bid_table([g] * 4, hands, dealer, vul)
        except (ValueError, IndexError):            # rule_bidder.py edge cases (reported to g9); skip the deal
            continue
        for t, call in enumerate(calls):
            seat = (dealer + t) % 4
            total += 1
            ctx = Context.make(calls[:t], dealer, seat, vul)
            rules = system.rules(ctx)
            if rules is None:
                continue
            covered += 1
            f = features_of_hands([hands[seat]])
            first = next(r for r in rules if r.pred.dist(f)[0] == 0)
            fam = first.family
            ok = first.call == call
            tally[fam]['ok' if ok else 'break'] += 1
            if not ok and len(ex[fam]) < examples:
                ex[fam].append(f'{ctx.after_open or ctx.key} | {show(hands[seat])} hcp={int(f["hcp"][0])} made {call}, card says {first.call} ({first.label})')
    return covered, total, tally, ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', required=True)
    ap.add_argument('--gen', required=True)
    ap.add_argument('--deals', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=4242)
    a = ap.parse_args()
    covered, total, tally, ex = breaks(a.card, a.gen, a.deals, a.seed)
    nb = sum(c['break'] for c in tally.values())
    print(f'{a.card} vs {a.gen}: {covered}/{total} calls covered ({covered / total:.1%}), {nb} breaks ({nb / max(covered, 1):.2%})')
    for fam, c in sorted(tally.items(), key=lambda kv: -kv[1]['break']):
        if c['break']:
            print(f'  {fam:16s} {c["break"]:5d} / {c["ok"] + c["break"]:5d}')
            for e in ex[fam]:
                print('      ', e)


if __name__ == '__main__':
    main()
