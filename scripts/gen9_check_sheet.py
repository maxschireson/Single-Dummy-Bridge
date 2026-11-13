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

from bridge_harness.cards.card import Card, load_card               # noqa: E402
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


def vul_string(seat, when):
    """A vulnerability string for `seat` (0..3) that makes `when` (a variant's vul) hold."""
    ns = seat % 2 == 0
    we, they = ('NS', 'EW') if ns else ('EW', 'NS')
    return {'any': 'None', 'none': 'None', 'nv': 'None', 'we': we, 'unfav': we, 'fav': they, 'both': 'Both'}[when]


def first_rule(system, ctx, f):
    rules = system.rules(ctx)
    if rules is None:
        return None
    return next(r for r in rules if r.pred.dist(f)[0] == 0)


def variant_rows(card, per=4, tries=20000, seed=7):
    """For each variant: hands on which it changes the call, against the same card without variants, in the
    variant's first seat (an opening, everybody passing before) and vulnerability. Only that variant is applied,
    so a change is the variant's own."""
    base = CardSystem(Card(dict(card.raw, variants=[])))
    docs = card.variant_doc()
    rng = random.Random(seed)
    out = []
    for i, v in enumerate(card.variants):
        full = CardSystem(Card(dict(card.raw, variants=[docs[i]])))
        pos = v['seats'][0]
        seat, dealer = pos - 1, 0
        calls = ['PASS'] * (pos - 1)
        vul = vul_string(seat, v['vul'])
        ctx = Context.make(calls, dealer, seat, vul)
        found = 0
        for _ in range(tries):
            deck = list(range(52))
            rng.shuffle(deck)
            h = sorted(deck[:13])
            f = features_of_hands([h])
            a, b = first_rule(base, ctx, f), first_rule(full, ctx, f)
            if a is not None and b is not None and a.call != b.call:
                out.append((i, h, int(f['hcp'][0]), f'seat {pos}, {vul}', f'{a.call} ({a.label})', f'{b.call} ({b.label})'))
                found += 1
                if found == per:
                    break
        if not found:
            out.append((i, None, None, f'seat {pos}, {vul}', '-', f'no change found in {tries} random hands'))
    return out


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
    text = head + '\n'.join(rows) + '\n'
    if card.variants:
        text += ('\n## Variants by seat and vulnerability\n\nHands on which a variant, applied alone, changes the opening against the same card '
                 'without variants, in the variant\'s first seat with everybody passing before. Vulnerability as dealt (N-S, E-W); '
                 'the caller is North in seat 1, West in seat 4.\n\n'
                 '| Variant | When | Hand | HCP | Situation | Without variants | With variants |\n| --- | --- | --- | ---: | --- | --- | --- |\n')
        for i, h, hcp, sit, a, b in variant_rows(card):
            v = card.variants[i]
            when = f'seats {v["seats"]}, vul {v["vul"]}, {v["scoring"]}'
            text += f'| {i} | {when} | {show(h) if h else "-"} | {hcp if hcp is not None else ""} | {sit} | {a.replace("PASS", "Pass")} | {b.replace("PASS", "Pass")} |\n'
    return text


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
