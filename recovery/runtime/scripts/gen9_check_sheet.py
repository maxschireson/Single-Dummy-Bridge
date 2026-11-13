"""A card's check sheet (G9-B6): what the compiled card opens and responds on a fixed set of hands.

For a person (or the card's owner) to confirm an intake: 40 fixed hands, and for each what the card
opens in first seat, responds to partner's 1H and 1NT, and overcalls over a 1D opening on the right,
with the rule that made the call. Calls the card does not cover show as '-'.

    python scripts/gen9_check_sheet.py acbl-sayc --out reports/gen9-cards-2026-11-12/acbl-sayc-check.md
"""
import argparse
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness.cards.card import load_card                     # noqa: E402
from bridge_harness.cards.context import Context                    # noqa: E402
from bridge_harness.cards.features import features_of_hands          # noqa: E402
from bridge_harness.cards.system import CardSystem                   # noqa: E402

SITUATIONS = (('Open, 1st seat', [], 0, 0), ('Partner 1H', ['1H', 'PASS'], 2, 0), ('Partner 1NT', ['1N', 'PASS'], 2, 0),
              ('Over RHO 1D', ['1D'], 3, 0))


def hands(n=40, seed=2026):
    """A fixed, varied set: random hands, plus some shaped and strong ones so every opening comes up."""
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        deck = list(range(52))
        rng.shuffle(deck)
        h = sorted(deck[:13])
        f = features_of_hands([h])
        k = len(out)
        want = (k % 4 == 0 and f['hcp'][0] >= 15) or (k % 4 == 1 and f['longest'][0] >= 6) or k % 4 in (2, 3)
        if want:
            out.append(h)
    return out


def show(hand):
    return ' '.join(s + ''.join('23456789TJQKA'[c % 13] for c in sorted((c for c in hand if c // 13 == i), reverse=True)) or s + '-'
                    for i, s in enumerate('♠♥♦♣'))


def sheet(card_id, n=40):
    card = load_card(card_id)
    system = CardSystem(card)
    rows = []
    for h in hands(n):
        f = features_of_hands([h])
        cells = []
        for _, calls, seat_of_me, dealer in SITUATIONS:
            seat = (dealer + len(calls)) % 4
            rules = system.rules(Context.make(calls, dealer, seat, 'None'))
            if rules is None:
                cells.append('-')
                continue
            r = next(r for r in rules if r.pred.dist(f)[0] == 0)
            cells.append(f'{r.call.replace("PASS", "Pass").replace("N", "NT") if r.call != "PASS" else "Pass"} ({r.label})')
        rows.append(f'| {show(h)} | {int(f["hcp"][0])} | ' + ' | '.join(cells) + ' |')
    head = (f'# Check sheet: {card.d.get("name") or card.id}\n\n'
            f'Card `{card.id}`, compiled by `bridge_harness/cards/system.py`. Nobody vulnerable; first seat for the opening.\n'
            f'Not compiled from this card (reported, not executed): {", ".join(card.unsupported()) or "nothing"}.\n\n'
            '| Hand | HCP | ' + ' | '.join(s[0] for s in SITUATIONS) + ' |\n| --- | ---: |' + ' --- |' * len(SITUATIONS) + '\n')
    return head + '\n'.join(rows) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('card')
    ap.add_argument('--hands', type=int, default=40)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    text = sheet(a.card, a.hands)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
    else:
        print(text)


if __name__ == '__main__':
    main()
